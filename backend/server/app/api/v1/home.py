"""Home Convenience API for Phase W7.

Provides:
- POST /clubs/{club_id}/home/understand: converts user's plain words into what was understood,
  recommended documents with one-line plain reasons and suggested reference numbers,
  and a single grouped list of missing details framed as plain questions.
- POST /clubs/{club_id}/home/generate: validates input widgets, verifies reference number acceptance,
  and executes atomic batch generation via BatchGenerator.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from docgen.numbering import compute_short_year, derive_event_code
from server.app.core.numbering_service import get_suggested_ref_no_for_series
from server.app.core.batch_generator import BatchGenerator
from server.app.core.database import get_db
from server.app.core.event_recommender import EventRecommender
from server.app.core.input_validation import (
    format_time_canonical_24h,
    format_time_display,
    validate_input_fields,
)
from server.app.core.permissions import ClubContext, Role, require_club_access
from server.app.core.rate_limit import check_rate_limit
from server.app.core.scoped_repo import ScopedRepository
from server.app.models import Club, Document, DocumentVersion, Event, NumberingSeries, Person, RoleHeld, Template, TemplateVersion, Venue


router = APIRouter(prefix="/clubs/{club_id}/home", tags=["home"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class HomeUnderstandRequest(BaseModel):
    text: str = Field(..., min_length=2)
    explicit_data: Optional[dict[str, Any]] = None
    selected_template_ids: Optional[list[str]] = None


class HomeUnderstoodData(BaseModel):
    event_name: Optional[str] = None
    dates: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    venue: Optional[str] = None
    participants: Optional[int] = None
    description: Optional[str] = None
    objectives: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class HomeRecommendedDoc(BaseModel):
    template_id: str
    name: str
    slug: str
    reason: str
    recommended: bool
    suggested_ref_no: str  # e.g. "ACM/26-27/ROOM/001 will be used"


class HomeMissingQuestion(BaseModel):
    key: str
    question: str
    label: str
    type: str  # time | time_range | date | date_range | int | money | enum | venue | person_ref | text | longtext
    required: bool = True
    importance: str = "optional"
    defer_ok: bool = False
    needed_by: list[str] = Field(default_factory=list)
    values: Optional[list[str]] = None
    current_value: Optional[Any] = None


class HomeUnderstandResponse(BaseModel):
    understood: HomeUnderstoodData
    recommended_documents: list[HomeRecommendedDoc]
    missing_questions: list[HomeMissingQuestion]


class HomeGenerateRequest(BaseModel):
    selected_template_ids: list[str] = Field(..., min_length=1)
    event_data: dict[str, Any] = Field(default_factory=dict)
    ref_numbers_accepted: bool = Field(..., description="Must be true to confirm reference numbers")
    event_id: Optional[str] = None
    event_title: Optional[str] = None
    allow_blanks: Optional[bool] = False


class HomeGeneratedDoc(BaseModel):
    id: str
    template_slug: str
    title: str
    ref_no: str
    pdf_url: str
    docx_url: str
    preview_url: str
    version_no: int
    verification_code: Optional[str] = None


class HomeGenerateResponse(BaseModel):
    batch_id: str
    event_id: str
    event_title: str
    documents_count: int
    zip_url: str
    documents: list[HomeGeneratedDoc]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ORGANISER_KEYS = {
    "organiser", "organizer", "organised_by", "organized_by", "organising_club", "organizing_club",
    "organising_body", "organizing_body", "organising_department", "organizing_department",
    "club", "club_name", "issuing_club", "hosted_by", "host_club", "organisers", "organizers",
}


def _is_organiser_key(key: str) -> bool:
    """Field keys that name the organising club (filled with the member's club by default)."""
    return (key or "").lower() in ORGANISER_KEYS


def _clean_jargon(text: str) -> str:
    """Filter out internal engineering jargon from user-facing text."""
    replacements = [
        ("reservation", "booking"),
        ("series", "numbering"),
        ("canonical", "standard"),
        ("schema", "template"),
        ("job", "task"),
        ("event record", "event details"),
        ("event_record", "event details"),
    ]
    cleaned = text
    for old, new in replacements:
        cleaned = re.sub(rf"{re.escape(old)}", new, cleaned, flags=re.IGNORECASE)
    return cleaned


def _get_suggested_ref_no(
    club: Club,
    series_key: str,
    db: Session,
    event_code: Optional[str] = None,
    format_pattern: Optional[str] = None,
) -> str:
    """Preview the next reference number exactly as generation will format it (no increment)."""
    try:
        ref_no = get_suggested_ref_no_for_series(
            db=db,
            club_id=club.id,
            series_key=series_key,
            event_code=event_code,
            format_pattern=format_pattern,
        )
    except ValueError:
        ay = club.academic_year_default or "2026-27"
        ref_no = f"{club.short_name or club.slug.upper()}/{compute_short_year(ay)}/{series_key}/001"
    return f"{ref_no} will be used"


def _page_images(club_id: str, doc_id: str, version: Any, version_no: int) -> list[str]:
    """Page preview URLs for a generated document (one per PDF page)."""
    page_count = 1
    if version and version.pdf_key:
        try:
            import pymupdf
            from server.app.core.storage import require_local_storage
            pdf_p = require_local_storage().local_path(version.pdf_key)
            if pdf_p.exists():
                with pymupdf.open(str(pdf_p)) as pdoc:
                    page_count = max(1, len(pdoc))
        except Exception:
            page_count = 1
    return [
        f"/api/v1/clubs/{club_id}/documents/{doc_id}/pages/{p}?v={version_no}"
        for p in range(1, page_count + 1)
    ]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/understand", response_model=HomeUnderstandResponse)
def understand_user_need(
    payload: HomeUnderstandRequest,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Convenience endpoint: Plain words -> what was understood + recommendations + missing questions."""
    rec = EventRecommender.recommend(
        text=payload.text,
        club_id=ctx.club.id,
        db=db,
        explicit_data=payload.explicit_data,
        selected_template_ids=payload.selected_template_ids,
    )

    extracted = rec.extracted_data

    # Canonicalize time formats for input widgets
    raw_time_start = extracted.get("time_start")
    raw_time_end = extracted.get("time_end")
    time_start_picker = format_time_canonical_24h(raw_time_start) if raw_time_start else None
    time_end_picker = format_time_canonical_24h(raw_time_end) if raw_time_end else None

    understood = HomeUnderstoodData(
        event_name=extracted.get("event_name"),
        dates=extracted.get("dates") or extracted.get("date_range_str"),
        date_start=extracted.get("date_start"),
        date_end=extracted.get("date_end"),
        time_start=time_start_picker,
        time_end=time_end_picker,
        venue=extracted.get("venue"),
        participants=extracted.get("participants") or extracted.get("expected_participants"),
        description=extracted.get("description"),
        objectives=extracted.get("objectives"),
        raw=extracted,
    )

    recommended_docs: list[HomeRecommendedDoc] = []
    # Combine active recommended and other templates
    all_recs = rec.templates + rec.other_templates
    event_code = derive_event_code(extracted.get("event_name")) if extracted.get("event_name") else None
    for t in all_recs:
        series_key = t.numbering_series or ("ROOM" if t.slug == "permission_letter" else "EVT")
        suggested_ref = _get_suggested_ref_no(ctx.club, series_key, db, event_code, t.numbering_format)
        reason_text = _clean_jargon(t.reason)
        if t.slug == "permission_letter" and extracted.get("venue"):
            reason_text = f"Official permission required to book and use {extracted.get('venue')} on campus."
        recommended_docs.append(
            HomeRecommendedDoc(
                template_id=t.template_id,
                name=t.name,
                slug=t.slug,
                reason=reason_text,
                recommended=t.recommended,
                suggested_ref_no=suggested_ref,
            )
        )

    # Transform missing fields into plain questions
    missing_questions: list[HomeMissingQuestion] = []
    for mf in rec.grouped_missing_fields:
        q_text = _clean_jargon(mf.ask)
        q_label = _clean_jargon(mf.label)

        # Infer widget type
        w_type = mf.type
        if mf.key in ("time_start", "time_end", "meeting_start_time", "meeting_end_time"):
            w_type = "time"
        elif mf.key in ("date_start", "date_end", "meeting_date", "invoice_date"):
            w_type = "date"
        elif mf.key in ("participants", "expected_participants"):
            w_type = "int"
        elif mf.key in ("amount", "prize_amount", "budget_total"):
            w_type = "money"
        elif mf.key == "venue":
            w_type = "venue"

        # Check prefilled value
        curr_val = extracted.get(mf.key)
        if not curr_val and _is_organiser_key(mf.key):
            # The member's own club organises by default; they can change it.
            curr_val = ctx.club.name
        if w_type == "time" and curr_val:
            curr_val = format_time_canonical_24h(curr_val)

        missing_questions.append(
            HomeMissingQuestion(
                key=mf.key,
                question=q_text,
                label=q_label,
                type=w_type,
                required=mf.required,
                importance=mf.importance,
                defer_ok=mf.defer_ok,
                needed_by=[_clean_jargon(n) for n in mf.needed_by],
                values=getattr(mf, "values", None),
                current_value=curr_val,
            )
        )

    # Values read from the sentence for custom templates: show them prefilled so the
    # user can check them before they go into the document.
    for ff in getattr(rec, "filled_from_text", []) or []:
        if any(q.key == ff.key for q in missing_questions):
            continue
        missing_questions.append(
            HomeMissingQuestion(
                key=ff.key,
                question=f"{_clean_jargon(ff.ask)} (from your request, please check)",
                label=_clean_jargon(ff.label),
                type=ff.type if ff.type in ("int", "money", "longtext") else "text",
                required=ff.required,
                importance=ff.importance,
                defer_ok=ff.defer_ok,
                needed_by=[_clean_jargon(n) for n in ff.needed_by],
                current_value=extracted.get(ff.key),
            )
        )

    # Check for roles with multiple active signatories
    if ctx.club.academic_year_default:
        active_role_holders = (
            db.query(RoleHeld)
            .filter(
                RoleHeld.club_id == ctx.club.id,
                RoleHeld.academic_year == ctx.club.academic_year_default,
                RoleHeld.valid_to.is_(None),
            )
            .all()
        )
        from collections import defaultdict
        holders_by_role = defaultdict(list)
        for rh in active_role_holders:
            holders_by_role[rh.role_key].append(rh)

        person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
        for r_key, r_holders in holders_by_role.items():
            if len(r_holders) > 1:
                people = [person_repo.get(h.person_id) for h in r_holders]
                names = [p.full_name for p in people if p]
                display_role = r_key.replace("_", " ").title()
                missing_questions.append(
                    HomeMissingQuestion(
                        key=f"signatory_{r_key}",
                        question=f"Who should sign as {display_role}?",
                        label=f"Signatory: {display_role}",
                        type="enum",
                        values=names,
                        required=True,
                        defer_ok=False,
                        needed_by=["Official Documents"],
                        current_value=extracted.get(f"signatory_{r_key}"),
                    )
                )

    return HomeUnderstandResponse(
        understood=understood,
        recommended_documents=recommended_docs,
        missing_questions=missing_questions,
    )


@router.post("/generate", response_model=HomeGenerateResponse)
def generate_user_need(
    payload: HomeGenerateRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Convenience endpoint: Validate widgets, verify ref numbers acceptance, and batch generate."""
    # 1. Permission check: Editor role minimum required
    if not ctx.is_editor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor access is required to generate documents.",
        )

    # 2. Reference numbers must be explicitly accepted (unless allow_blanks preview is requested)
    if not payload.ref_numbers_accepted and not payload.allow_blanks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "REF_NUMBERS_NOT_ACCEPTED",
                "message": "Please accept the suggested reference numbers before generating.",
            },
        )

    # Align participants and expected_participants in event_data
    if "participants" in payload.event_data and ("expected_participants" not in payload.event_data or not payload.event_data.get("expected_participants")):
        payload.event_data["expected_participants"] = payload.event_data["participants"]
    elif "expected_participants" in payload.event_data and ("participants" not in payload.event_data or not payload.event_data.get("participants")):
        payload.event_data["participants"] = payload.event_data["expected_participants"]

    # Sanitize list fields (judges, budget_items) if scalar string or number sent from form
    if "judges" in payload.event_data:
        from docgen.models import coerce_to_list_of_strings
        payload.event_data["judges"] = coerce_to_list_of_strings(payload.event_data["judges"])

    if "budget_items" in payload.event_data:
        from docgen.models import coerce_to_budget_items
        b_list = coerce_to_budget_items(payload.event_data["budget_items"])
        payload.event_data["budget_items"] = [b.model_dump() for b in b_list]
    elif any(payload.event_data.get(k) for k in ("estimated_budget", "budget", "budget_amount", "sanctioned_budget")):
        from docgen.models import coerce_to_budget_items
        b_val = payload.event_data.get("estimated_budget") or payload.event_data.get("budget") or payload.event_data.get("budget_amount") or payload.event_data.get("sanctioned_budget")
        b_list = coerce_to_budget_items(b_val)
        payload.event_data["budget_items"] = [b.model_dump() for b in b_list]

    if not payload.event_data.get("event_name") and payload.event_title:
        payload.event_data["event_name"] = payload.event_title

    # 3. Input widget validation (dates, times, integers, amounts)
    if not payload.allow_blanks:
        validate_input_fields(payload.event_data)

    has_picker_dates = bool(
        payload.event_data.get("date_start")
        and payload.event_data.get("date_end")
        and re.match(r"^\d{4}-\d{2}-\d{2}$", str(payload.event_data.get("date_start")))
        and re.match(r"^\d{4}-\d{2}-\d{2}$", str(payload.event_data.get("date_end")))
    )
    if has_picker_dates:
        payload.event_data["dates_confirmed"] = True
        if not payload.event_data.get("dates"):
            from docgen.functions import fn_format_date_range
            payload.event_data["dates"] = fn_format_date_range(payload.event_data["date_start"], payload.event_data["date_end"])
    elif payload.event_data.get("dates"):
        dates_val = str(payload.event_data.get("dates") or "").strip()
        is_confirmed = bool(payload.event_data.get("dates_confirmed"))
        has_full_year = bool(re.search(r"\b20\d\d\b", dates_val))
        if not is_confirmed or not has_full_year or "assumed" in dates_val.lower():
            if not is_confirmed and not payload.allow_blanks:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "DATES_NOT_CONFIRMED",
                        "message": "Event dates must be confirmed before generation.",
                    },
                )
        if not payload.event_data.get("date_start") or not payload.event_data.get("date_end"):
            from docgen.extractors.event_extractor import EventExtractor
            try:
                ext = EventExtractor()
                parsed_rec = ext.extract_from_text(dates_val)
                if parsed_rec.date_start and not payload.event_data.get("date_start"):
                    payload.event_data["date_start"] = parsed_rec.date_start.value
                if parsed_rec.date_end and not payload.event_data.get("date_end"):
                    payload.event_data["date_end"] = parsed_rec.date_end.value
            except Exception:
                pass

    # 4. Check for multiple active signatories conflict in generate
    if ctx.club.academic_year_default:
        active_role_holders = (
            db.query(RoleHeld)
            .filter(
                RoleHeld.club_id == ctx.club.id,
                RoleHeld.academic_year == ctx.club.academic_year_default,
                RoleHeld.valid_to.is_(None),
            )
            .all()
        )
        from collections import defaultdict
        holders_by_role = defaultdict(list)
        for rh in active_role_holders:
            holders_by_role[rh.role_key].append(rh)

        person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
        for r_key, r_holders in holders_by_role.items():
            if len(r_holders) > 1:
                people = [person_repo.get(h.person_id) for h in r_holders]
                names = [p.full_name for p in people if p]
                display_role = r_key.replace("_", " ").title()
                chosen_name = payload.event_data.get(f"signatory_{r_key}")
                if not chosen_name or chosen_name not in names:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "code": "SIGNATORY_SELECTION_REQUIRED",
                            "message": f"Multiple active signatories exist for {display_role}. Please choose who signs ({', '.join(names)}).",
                            "key": f"signatory_{r_key}",
                            "options": names,
                        },
                    )
                chosen_p = next(p for p in people if p and p.full_name == chosen_name)
                chosen_rh = next(h for h in r_holders if h.person_id == chosen_p.id)
                payload.event_data[r_key] = {
                    "name": chosen_p.full_name,
                    "admission_no": chosen_p.roll_no or "",
                    "branch": chosen_p.branch or "",
                    "mobile": chosen_p.mobile or "",
                    "email": chosen_p.email or "",
                    "designation": chosen_rh.designation_label,
                }

    # 5. Delegate to BatchGenerator
    batch_result = BatchGenerator.generate_batch(
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        selected_template_ids=payload.selected_template_ids,
        event_data=payload.event_data,
        event_id=payload.event_id,
        event_title=payload.event_title,
        allow_blanks=bool(payload.allow_blanks),
        db=db,
    )

    # 5. Format documents list for simplified Home result page
    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    docs_out: list[HomeGeneratedDoc] = []
    for doc_info in batch_result.get("documents", []):
        doc_id = doc_info.get("id") or doc_info.get("document_id")
        ver_no = doc_info.get("version_no", 1)
        doc_rec = doc_repo.get(doc_id) if doc_id else None
        ver_code = None
        if doc_rec and doc_rec.current_version_id:
            ver = db.query(DocumentVersion).filter(DocumentVersion.id == doc_rec.current_version_id).first()
            if ver:
                ver_code = ver.verification_code
        docs_out.append(
            HomeGeneratedDoc(
                id=doc_id,
                template_slug=doc_info.get("template_slug", "document"),
                title=doc_info.get("title", "Generated Document"),
                ref_no=doc_info.get("ref_no", ""),
                pdf_url=f"/api/v1/clubs/{ctx.club.id}/documents/{doc_id}/pdf",
                docx_url=f"/api/v1/clubs/{ctx.club.id}/documents/{doc_id}/docx",
                preview_url=f"/api/v1/clubs/{ctx.club.id}/documents/{doc_id}/preview",
                version_no=ver_no,
                verification_code=ver_code,
            )
        )

    return HomeGenerateResponse(
        batch_id=batch_result.get("batch_id"),
        event_id=batch_result.get("event_id"),
        event_title=batch_result.get("event_title"),
        documents_count=len(docs_out),
        zip_url=batch_result.get("zip_url"),
        documents=docs_out,
    )


# ---------------------------------------------------------------------------
# Phase: Describe -> AI Drafts -> Review & Edit (New Flow)
# ---------------------------------------------------------------------------

class HomeCreateRequest(BaseModel):
    text: str = Field(..., min_length=2)
    selected_template_id: Optional[str] = None
    explicit_data: Optional[dict[str, Any]] = None
    rows: Optional[list[dict[str, Any]]] = None


class HomeApplyAllRequest(BaseModel):
    event_id: str
    # The results page sends "updates"; "changes" is accepted too
    updates: Optional[dict[str, Any]] = None
    changes: Optional[dict[str, Any]] = None


class HomeAddDocumentRequest(BaseModel):
    event_id: str
    template_id: str
    event_data: Optional[dict[str, Any]] = None


class HomeAiInstructRequest(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=2000)
    # The results page sends current_data (+ template_slug); current_fields/available_fields also work
    current_data: Optional[dict[str, Any]] = None
    current_fields: Optional[dict[str, Any]] = None
    available_fields: Optional[list[dict[str, Any]]] = None
    template_slug: Optional[str] = None


class HomeCreateResponse(BaseModel):
    batch_id: str
    event_id: str
    event_title: str
    documents_count: int
    zip_url: str
    documents: list[dict[str, Any]]
    fields: dict[str, Any]
    missing_fields: list[dict[str, Any]]
    ai_drafted_fields: list[str]
    assumptions: list[str]
    recommended_templates: list[HomeRecommendedDoc]
    available_templates: list[dict[str, Any]]
    notice: Optional[str] = None


@router.post("/create", response_model=HomeCreateResponse)
def create_documents_endpoint(
    payload: HomeCreateRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Single action create: extract details, decide documents, build shared event, generate with blanks."""
    from collections import defaultdict
    from datetime import date
    from server.app.core.club_identity import club_department, default_addressee
    import server.app.core.document_workflow as workflow

    # 1. Recommendation & Extraction
    rec = EventRecommender.recommend(
        text=payload.text,
        club_id=ctx.club.id,
        db=db,
        explicit_data=payload.explicit_data,
    )
    extracted = dict(rec.extracted_data or {})
    notice = None

    # Check which templates to generate
    if payload.selected_template_id:
        selected_ids = [payload.selected_template_id]
    else:
        selected_ids = [t.template_id for t in rec.templates if t.recommended]
        if not selected_ids:
            all_t = rec.templates + rec.other_templates
            if all_t:
                selected_ids = [all_t[0].template_id]

    assumptions: list[str] = []

    # 2. Defaults instead of questions
    # Venue and Addressee
    venue_name = extracted.get("venue")
    venue_obj = None
    if venue_name:
        venue_obj = (
            db.query(Venue)
            .filter(
                (Venue.club_id == ctx.club.id) | (Venue.club_id.is_(None)),
                (Venue.name.ilike(f"%{venue_name}%")) | (Venue.short_name.ilike(f"%{venue_name}%")),
            )
            .first()
        )
    if venue_obj and venue_obj.addressee_default:
        extracted["submitted_to"] = venue_obj.addressee_default
        assumptions.append(f"Addressee: {venue_obj.addressee_default} (from {venue_obj.name})")
    elif not extracted.get("submitted_to"):
        def_add = default_addressee(ctx.club)
        extracted["submitted_to"] = def_add
        assumptions.append(f"Addressee: {def_add} (from club settings)")

    # Organiser defaults to member's club
    for org_k in (
        "organiser", "organizer", "organised_by", "organized_by", "organising_club",
        "organizing_club", "club", "club_name", "issuing_club", "hosted_by", "host_club"
    ):
        if not extracted.get(org_k):
            extracted[org_k] = ctx.club.name
    assumptions.append(f"Organiser: {ctx.club.name}")

    # Document date defaults to today
    today_str = date.today().strftime("%d/%m/%Y")
    if not extracted.get("document_date"):
        extracted["document_date"] = today_str
    assumptions.append(f"Document date: {today_str} (today)")

    # Dates and Times
    has_picker_dates = bool(
        extracted.get("date_start")
        and extracted.get("date_end")
        and re.match(r"^\d{4}-\d{2}-\d{2}$", str(extracted.get("date_start")))
        and re.match(r"^\d{4}-\d{2}-\d{2}$", str(extracted.get("date_end")))
    )
    if has_picker_dates:
        extracted["dates_confirmed"] = True
        if not extracted.get("dates"):
            from docgen.functions import fn_format_date_range
            extracted["dates"] = fn_format_date_range(extracted["date_start"], extracted["date_end"])
    elif extracted.get("dates"):
        extracted["dates_confirmed"] = True

    if extracted.get("time_start"):
        assumptions.append(f"Start time: {extracted['time_start']}")
    if extracted.get("time_end"):
        assumptions.append(f"End time: {extracted['time_end']}")

    # Signatories from club's active role holders
    if ctx.club.academic_year_default:
        active_role_holders = (
            db.query(RoleHeld)
            .filter(
                RoleHeld.club_id == ctx.club.id,
                RoleHeld.academic_year == ctx.club.academic_year_default,
                RoleHeld.valid_to.is_(None),
            )
            .all()
        )
        holders_by_role = defaultdict(list)
        for rh in active_role_holders:
            holders_by_role[rh.role_key].append(rh)

        person_repo = ScopedRepository(db, Person, club_id=ctx.club.id)
        for r_key, r_holders in holders_by_role.items():
            if r_holders:
                chosen_rh = r_holders[0]
                chosen_p = person_repo.get(chosen_rh.person_id)
                if chosen_p and r_key not in extracted:
                    extracted[r_key] = {
                        "name": chosen_p.full_name,
                        "admission_no": chosen_p.roll_no or "",
                        "branch": chosen_p.branch or "",
                        "mobile": chosen_p.mobile or "",
                        "email": chosen_p.email or "",
                        "designation": chosen_rh.designation_label,
                    }
                    extracted[f"signatory_{r_key}"] = chosen_p.full_name
                    display_role = r_key.replace("_", " ").title()
                    assumptions.append(f"Signatory for {display_role}: {chosen_p.full_name}")

    # Track AI-drafted fields (and clean marker so it is NEVER printed in document)
    ai_drafted_fields: list[str] = []
    for k, v in list(extracted.items()):
        if isinstance(v, str) and "[AI-drafted" in v:
            ai_drafted_fields.append(k)
            extracted[k] = re.sub(r"^\[AI-drafted(?:,\s*review)?\]\s*", "", v).strip()

    if "description" in ai_drafted_fields:
        assumptions.append("Description: drafted by AI from your request")
    if "objectives" in ai_drafted_fields:
        assumptions.append("Objectives: drafted by AI from your request")

    if payload.rows:
        extracted["rows"] = payload.rows

    # 3. Batch generate documents with allow_blanks=True
    batch_result = BatchGenerator.generate_batch(
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        selected_template_ids=selected_ids,
        event_data=extracted,
        event_title=extracted.get("event_name") or "Event",
        allow_blanks=True,
        db=db,
    )

    # 4. Detect missing fields (fields in schemas left blank)
    missing_fields: list[dict[str, Any]] = []
    for mf in rec.grouped_missing_fields:
        val = extracted.get(mf.key)
        if val is None or str(val).strip() in ("", "None", "null", "____________________"):
            missing_fields.append({
                "key": mf.key,
                "label": _clean_jargon(mf.label),
                "type": mf.type,
                "needed_by": [_clean_jargon(n) for n in mf.needed_by],
                "ask": _clean_jargon(mf.ask),
            })

    # 5. Enrich generated documents with editable_fields and page_images
    docs_out: list[dict[str, Any]] = []
    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    for doc_info in batch_result.get("documents", []):
        doc_id = doc_info.get("id") or doc_info.get("document_id")
        doc_record = doc_repo.get(doc_id) if doc_id else None
        latest_ver = workflow.latest_version(db, doc_record) if doc_record else None
        ver_no = latest_ver.version_no if latest_ver else doc_info.get("version_no", 1)
        ef = workflow.editable_fields(db, doc_record) if doc_record else []
        page_images = _page_images(ctx.club.id, doc_id, latest_ver, ver_no)
        docs_out.append({
            "id": doc_id,
            "template_slug": doc_info.get("template_slug", "document"),
            "title": doc_info.get("title", "Generated Document"),
            "ref_no": doc_info.get("ref_no", ""),
            "pdf_url": f"/api/v1/clubs/{ctx.club.id}/documents/{doc_id}/pdf",
            "docx_url": f"/api/v1/clubs/{ctx.club.id}/documents/{doc_id}/docx",
            "preview_url": f"/api/v1/clubs/{ctx.club.id}/documents/{doc_id}/preview",
            "version_no": ver_no,
            "verification_code": latest_ver.verification_code if latest_ver else None,
            "editable_fields": ef,
            "page_images": page_images,
        })

    # Recommended docs info
    all_recs = rec.templates + rec.other_templates
    event_code = derive_event_code(extracted.get("event_name")) if extracted.get("event_name") else None
    recommended_docs: list[HomeRecommendedDoc] = []
    for t in all_recs:
        series_key = t.numbering_series or ("ROOM" if t.slug == "permission_letter" else "EVT")
        suggested_ref = _get_suggested_ref_no(ctx.club, series_key, db, event_code, t.numbering_format)
        recommended_docs.append(
            HomeRecommendedDoc(
                template_id=t.template_id,
                name=t.name,
                slug=t.slug,
                reason=_clean_jargon(t.reason),
                recommended=t.recommended,
                suggested_ref_no=suggested_ref,
            )
        )

    # Available templates for "+ Add document"
    all_club_tmpls = (
        db.query(Template)
        .filter(
            (Template.club_id == ctx.club.id) | (Template.is_system == True),
            Template.status == "published",
        )
        .all()
    )
    available_templates = [
        {"id": t.id, "name": t.name, "slug": t.slug}
        for t in all_club_tmpls
    ]

    return HomeCreateResponse(
        batch_id=batch_result.get("batch_id"),
        event_id=batch_result.get("event_id"),
        event_title=batch_result.get("event_title") or "Event",
        documents_count=len(docs_out),
        zip_url=batch_result.get("zip_url") or "",
        documents=docs_out,
        fields=extracted,
        missing_fields=missing_fields,
        ai_drafted_fields=ai_drafted_fields,
        assumptions=assumptions,
        recommended_templates=recommended_docs,
        available_templates=available_templates,
        notice=notice,
    )


@router.post("/apply-all")
def apply_all_endpoint(
    payload: HomeApplyAllRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Apply field changes across all documents sharing an event record."""
    import server.app.core.document_workflow as workflow

    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    docs = doc_repo.all(Document.event_id == payload.event_id)
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found for this event.")
    changes = payload.updates or payload.changes or {}

    updated_docs = []
    revised_count = 0
    for doc in docs:
        allowed = {f["key"] for f in workflow.editable_fields(db, doc)}
        relevant_changes = {k: v for k, v in changes.items() if k in allowed}
        if relevant_changes:
            try:
                workflow.revise_document(db, doc, ctx.user, relevant_changes, note="Applied across event documents")
                revised_count += 1
            except HTTPException as exc:
                if exc.detail and isinstance(exc.detail, dict) and exc.detail.get("code") == "NO_CHANGES":
                    pass
                else:
                    raise

        db.refresh(doc)
        latest_ver = workflow.latest_version(db, doc)
        ef = workflow.editable_fields(db, doc)
        page_images = _page_images(ctx.club.id, doc.id, latest_ver, latest_ver.version_no)
        tmpl = db.query(Template).filter(Template.id == doc.template_id).first()
        updated_docs.append({
            "id": doc.id,
            "template_slug": tmpl.slug if tmpl else "document",
            "title": doc.title,
            "ref_no": doc.ref_no,
            "pdf_url": f"/api/v1/clubs/{ctx.club.id}/documents/{doc.id}/pdf",
            "docx_url": f"/api/v1/clubs/{ctx.club.id}/documents/{doc.id}/docx",
            "preview_url": f"/api/v1/clubs/{ctx.club.id}/documents/{doc.id}/preview",
            "version_no": latest_ver.version_no,
            "editable_fields": ef,
            "page_images": page_images,
        })
    return {"event_id": payload.event_id, "updated_documents_count": revised_count, "documents": updated_docs}


@router.post("/add-document")
def add_document_endpoint(
    payload: HomeAddDocumentRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Generate an additional document for an existing event."""
    from server.app.models import Event
    import server.app.core.document_workflow as workflow

    event_repo = ScopedRepository(db, Event, club_id=ctx.club.id)
    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)

    event = event_repo.get(payload.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    existing_doc = doc_repo.find_first(Document.event_id == event.id)
    base_data = {}
    if existing_doc:
        ver = workflow.latest_version(db, existing_doc)
        base_data = dict(ver.record_snapshot or {})
        # Shared event details carry over, but each document gets its own reference number;
        # reusing the first document's ref_no hits the unique (club, ref_no) constraint.
        for key in [k for k in base_data if k == "ref_no" or k.endswith("_ref_no")]:
            base_data.pop(key, None)
    if payload.event_data:
        base_data.update(payload.event_data)

    batch_result = BatchGenerator.generate_batch(
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        selected_template_ids=[payload.template_id],
        event_data=base_data,
        event_id=event.id,
        event_title=event.title,
        allow_blanks=True,
        db=db,
    )

    created = batch_result.get("documents") or []
    if not created:
        raise HTTPException(status_code=422, detail="This document could not be created. Please try another template.")
    doc_id = created[0].get("id") or created[0].get("document_id")
    doc = doc_repo.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="The new document could not be found.")
    latest_ver = workflow.latest_version(db, doc)
    ef = workflow.editable_fields(db, doc)
    page_images = _page_images(ctx.club.id, doc.id, latest_ver, latest_ver.version_no)
    tmpl = db.query(Template).filter(Template.id == doc.template_id).first()
    return {
        "id": doc.id,
        "template_slug": tmpl.slug if tmpl else "document",
        "title": doc.title,
        "ref_no": doc.ref_no,
        "pdf_url": f"/api/v1/clubs/{ctx.club.id}/documents/{doc.id}/pdf",
        "docx_url": f"/api/v1/clubs/{ctx.club.id}/documents/{doc.id}/docx",
        "preview_url": f"/api/v1/clubs/{ctx.club.id}/documents/{doc.id}/preview",
        "version_no": latest_ver.version_no,
        "editable_fields": ef,
        "page_images": page_images,
    }


@router.post("/ai-instruct")
def ai_instruct_endpoint(
    payload: HomeAiInstructRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Translate plain language instruction (e.g. 'make the date 16 October') into field changes."""
    import json
    from docgen.llm import get_llm_client

    check_rate_limit(f"ai_user:{ctx.user.id}", max_requests=10, window_seconds=60, db=db)
    llm = get_llm_client()
    current = payload.current_data or payload.current_fields or {}
    if payload.available_fields:
        fields_summary = {f["key"]: f.get("label", f["key"]) for f in payload.available_fields if f.get("key")}
    else:
        fields_summary = {k: k.replace("_", " ").title() for k in current}
    schema = {
        "type": "object",
        "description": "JSON dictionary of field keys and their updated values",
    }
    prompt = (
        f"You are helping a club member update document fields.\n"
        f"Instruction: {payload.instruction}\n"
        f"Current field values: {json.dumps(current, default=str)}\n"
        f"Available fields: {json.dumps(fields_summary)}\n"
        f"Return a JSON object containing ONLY the field keys that the user's instruction explicitly asks to change. "
        f"Do not invent facts or modify fields not mentioned in the instruction. "
        f"If a date is mentioned (e.g. 16 October), update both 'dates' and if relevant 'date_start' (YYYY-MM-DD)."
    )
    try:
        changes = llm.generate_json(prompt, schema)
        if not isinstance(changes, dict):
            changes = {}
        # The model may name fields that do not exist; only offer real ones
        changes = {k: v for k, v in changes.items() if k in fields_summary}
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="AI assistant is temporarily unavailable. You can edit the fields directly in the form below.",
        )
    explanation = (
        "Updated " + ", ".join(fields_summary.get(k, k) for k in changes) + "." if changes else "No field changes were needed."
    )
    return {"proposed_updates": changes, "changes": changes, "explanation": explanation}
