"""Events API: manage shared event context and linked document sets."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional
from pathlib import Path
import pymupdf

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from docgen.models import EventRecord
from docgen.renderer import Renderer
from docgen.sources import DatabaseTemplateSource, build_club_config_from_db
from server.app.core.audit import log_audit
from server.app.core.database import get_db
from server.app.core.permissions import ClubContext, Role, require_club_access
from server.app.core.scoped_repo import ScopedRepository
from server.app.models import Document, DocumentVersion, Event, Template, TemplateVersion
from server.app.core.event_recommender import EventRecommender, EventRecommendationResponse
from server.app.core.batch_generator import BatchGenerator

router = APIRouter(prefix="/clubs/{club_id}/events", tags=["events"])


class EventDocumentSummary(BaseModel):
    id: str
    template_slug: str
    title: str
    ref_no: Optional[str] = None
    status: str
    created_at: datetime
    current_version_no: int


class EventDetailOut(BaseModel):
    id: str
    club_id: str
    title: str
    event_code: Optional[str] = None
    status: str
    record: dict[str, Any]
    created_at: datetime
    documents: list[EventDocumentSummary]


class EventListOut(BaseModel):
    items: list[EventDetailOut]
    total: int


class EventCreateRequest(BaseModel):
    title: str = Field(..., min_length=2)
    event_code: Optional[str] = None
    record: dict[str, Any] = Field(default_factory=dict)


class EventUpdateRequest(BaseModel):
    title: Optional[str] = None
    event_code: Optional[str] = None
    record: Optional[dict[str, Any]] = None


@router.get("", response_model=EventListOut)
def list_events(
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """List all events for the active club along with their linked documents."""
    event_repo = ScopedRepository(db, Event, club_id=ctx.club.id)
    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    events = event_repo.list(limit=500)

    result = []
    for ev in events:
        docs = doc_repo.all(Document.event_id == ev.id)
        doc_summaries = []
        for d in docs:
            tmpl = db.query(Template).filter(Template.id == d.template_id).first()
            latest_v = (
                db.query(DocumentVersion)
                .filter(DocumentVersion.document_id == d.id)
                .order_by(DocumentVersion.version_no.desc())
                .first()
            )
            v_no = latest_v.version_no if latest_v else 1
            doc_summaries.append(
                EventDocumentSummary(
                    id=d.id,
                    template_slug=tmpl.slug if tmpl else "document",
                    title=d.title,
                    ref_no=d.ref_no,
                    status=d.status,
                    created_at=d.created_at,
                    current_version_no=v_no,
                )
            )

        result.append(
            EventDetailOut(
                id=ev.id,
                club_id=ev.club_id,
                title=ev.title,
                event_code=ev.event_code,
                status=ev.status,
                record=ev.record or {},
                created_at=ev.created_at,
                documents=doc_summaries,
            )
        )

    return EventListOut(items=result, total=len(result))


@router.post("", response_model=EventDetailOut, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreateRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Create a new shared event context."""
    ev = Event(
        id=str(uuid.uuid4()),
        club_id=ctx.club.id,
        title=payload.title,
        event_code=payload.event_code,
        record=payload.record,
        status="active",
        created_by=ctx.user.id,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    return EventDetailOut(
        id=ev.id,
        club_id=ev.club_id,
        title=ev.title,
        event_code=ev.event_code,
        status=ev.status,
        record=ev.record or {},
        created_at=ev.created_at,
        documents=[],
    )


@router.get("/{event_id}", response_model=EventDetailOut)
def get_event(
    event_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Get single event details with all linked documents."""
    event_repo = ScopedRepository(db, Event, club_id=ctx.club.id)
    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    ev = event_repo.get(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")

    docs = doc_repo.all(Document.event_id == ev.id)
    doc_summaries = []
    for d in docs:
        tmpl = db.query(Template).filter(Template.id == d.template_id).first()
        latest_v = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == d.id)
            .order_by(DocumentVersion.version_no.desc())
            .first()
        )
        v_no = latest_v.version_no if latest_v else 1
        doc_summaries.append(
            EventDocumentSummary(
                id=d.id,
                template_slug=tmpl.slug if tmpl else "document",
                title=d.title,
                ref_no=d.ref_no,
                status=d.status,
                created_at=d.created_at,
                current_version_no=v_no,
            )
        )

    return EventDetailOut(
        id=ev.id,
        club_id=ev.club_id,
        title=ev.title,
        event_code=ev.event_code,
        status=ev.status,
        record=ev.record or {},
        created_at=ev.created_at,
        documents=doc_summaries,
    )


@router.put("/{event_id}", response_model=EventDetailOut)
def update_event(
    event_id: str,
    payload: EventUpdateRequest,
    update_documents: bool = Query(False, description="Re-render linked documents with updated event values"),
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Update event fields, with optional cascading update to linked documents."""
    event_repo = ScopedRepository(db, Event, club_id=ctx.club.id)
    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    ev = event_repo.get(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")

    if payload.title is not None:
        ev.title = payload.title
    if payload.event_code is not None:
        ev.event_code = payload.event_code
    if payload.record is not None:
        merged = dict(ev.record or {})
        merged.update(payload.record)
        ev.record = merged

    db.commit()
    db.refresh(ev)

    docs = doc_repo.all(Document.event_id == ev.id)

    if update_documents and docs:
        db_config = build_club_config_from_db(db, ctx.club.slug)
        db_source = DatabaseTemplateSource(db)

        for d in docs:
            tmpl = db.query(Template).filter(Template.id == d.template_id).first()
            if not tmpl:
                continue

            # Fetch latest version to increment
            latest_v = (
                db.query(DocumentVersion)
                .filter(DocumentVersion.document_id == d.id)
                .order_by(DocumentVersion.version_no.desc())
                .first()
            )
            new_v_no = (latest_v.version_no + 1) if latest_v else 1

            # Prepare merged snapshot
            merged_snapshot = dict(latest_v.record_snapshot if latest_v else {})
            if ev.record:
                merged_snapshot.update(ev.record)
            if d.ref_no:
                merged_snapshot["ref_no"] = d.ref_no
            if payload.title:
                merged_snapshot["event_name"] = payload.title

            event_rec = EventRecord.from_flat_dict(merged_snapshot)
            out_dir = Path("storage/documents") / d.id / f"v{new_v_no}"
            out_dir.mkdir(parents=True, exist_ok=True)

            renderer = Renderer(config=db_config, template_source=db_source, outputs_dir=out_dir)
            try:
                render_result = renderer.render(
                    template_id=tmpl.slug,
                    event=event_rec,
                    extra_context=merged_snapshot,
                    output_dir=out_dir,
                    convert_pdf=True,
                )

                # Generate previews
                preview_dir = Path("storage/previews") / d.id / f"v{new_v_no}"
                preview_dir.mkdir(parents=True, exist_ok=True)
                pdf_doc = pymupdf.open(str(render_result.pdf_path))
                for idx, page in enumerate(pdf_doc):
                    pix = page.get_pixmap(dpi=150)
                    pix.save(str(preview_dir / f"page_{idx + 1}.png"))
                pdf_doc.close()

                new_ver = DocumentVersion(
                    id=str(uuid.uuid4()),
                    document_id=d.id,
                    version_no=new_v_no,
                    record_snapshot=merged_snapshot,
                    overrides={},
                    docx_key=str(render_result.docx_path),
                    pdf_key=str(render_result.pdf_path),
                    created_by=ctx.user.id,
                    source="cascaded_event_update",
                )
                db.add(new_ver)
                d.current_version_id = new_ver.id
            except Exception as e:
                import traceback
                print(f"[ERROR] Re-rendering document {d.id} failed: {e}")
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"Failed to re-render document {d.id}: {str(e)}")

        db.commit()

    doc_summaries = []
    for d in docs:
        tmpl = db.query(Template).filter(Template.id == d.template_id).first()
        latest_ver = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == d.id)
            .order_by(DocumentVersion.version_no.desc())
            .first()
        )
        cur_v = latest_ver.version_no if latest_ver else 1
        doc_summaries.append(
            EventDocumentSummary(
                id=d.id,
                template_slug=tmpl.slug if tmpl else "document",
                title=d.title,
                ref_no=d.ref_no,
                status=d.status,
                created_at=d.created_at,
                current_version_no=cur_v,
            )
        )

    return EventDetailOut(
        id=ev.id,
        club_id=ev.club_id,
        title=ev.title,
        event_code=ev.event_code,
        status=ev.status,
        record=ev.record or {},
        created_at=ev.created_at,
        documents=doc_summaries,
    )


class EventRecommendRequest(BaseModel):
    text: str = Field(..., min_length=5)
    explicit_data: Optional[dict[str, Any]] = None
    selected_template_ids: Optional[list[str]] = None


class BatchGenerateRequest(BaseModel):
    selected_template_ids: list[str] = Field(..., min_length=1)
    event_data: dict[str, Any] = Field(default_factory=dict)
    event_id: Optional[str] = None
    event_title: Optional[str] = None


class BatchGenerateResponse(BaseModel):
    batch_id: str
    event_id: str
    event_title: str
    documents_count: int
    zip_filename: str
    zip_path: str
    zip_url: str
    documents: list[dict[str, Any]]


@router.post("/recommend", response_model=EventRecommendationResponse)
def recommend_event_documents(
    payload: EventRecommendRequest,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Analyze event description, extract fields, and return recommended documents with grouped missing fields."""
    return EventRecommender.recommend(
        text=payload.text,
        club_id=ctx.club.id,
        db=db,
        explicit_data=payload.explicit_data,
        selected_template_ids=payload.selected_template_ids,
    )


@router.post("/generate-batch", response_model=BatchGenerateResponse)
def generate_event_batch(
    payload: BatchGenerateRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Generate all selected documents for an event in one job, reserve numbers, and package as ZIP."""
    try:
        return BatchGenerator.generate_batch(
            club_id=ctx.club.id,
            user_id=ctx.user.id,
            selected_template_ids=payload.selected_template_ids,
            event_data=payload.event_data,
            event_id=payload.event_id,
            event_title=payload.event_title,
            db=db,
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

