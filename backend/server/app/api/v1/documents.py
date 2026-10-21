"""Document generation, template schemas, AI extraction, and preview APIs."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import uuid

logger = logging.getLogger(__name__)
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pymupdf
import yaml
from docxtpl import DocxTemplate
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from server.app.core import document_workflow as workflow
from server.app.core.club_identity import default_addressee, default_signatures
from server.app.core.template_compiler import TemplateCompiler, migrate_template_content
from server.app.core.template_generator import (
    generate_draft_template,
    resolve_club_logo_by_text,
)
from server.app.core.template_wizard import (
    WizardGenerateRequest,
    WizardQuestionsResponse,
    create_wizard_template,
    get_wizard_questions,
)
from server.app.core.document_importer import (
    convert_docx_to_tiptap_with_fields,
    convert_text_to_tiptap_with_fields,
)
from server.app.core.text_improver import (
    improve_text as core_improve_text,
    suggest_optional_details as core_suggest_details,
    translate_template_content as core_translate_content,
)
from server.app.core.document_checker import audit_document as core_audit_document


from docgen.config import ClubConfig
from docgen.extractors.event_extractor import EventExtractor
from docgen.missing_fields import detect_missing_fields
from docgen.models import (
    ActionItem,
    AgendaItem,
    ApprovalNote,
    BankDetails,
    BillItem,
    BillRecord,
    BudgetItem,
    EventRecord,
    FieldSource,
    MeetingBlock,
    PaymentDetails,
    SupplierDetails,
    Winner,
    tf,
    TrackedField,
)
from docgen.numbering import compute_short_year, format_reference_number
from docgen.renderer import Renderer
from docgen.schema import TemplateSchema, load_all_schemas, load_schema
from docgen.sources import DatabaseTemplateSource, build_club_config_from_db
from server.app.core.audit import log_audit
from server.app.core.database import get_db
from server.app.core.storage import storage
from server.app.core.storage import LocalDiskStorage, get_storage, require_local_storage
from server.app.core.tenancy import (
    asset_is_visible_to_club,
    get_asset_for_club,
    letterhead_is_visible_to_club,
    validate_letterhead_asset_refs,
)
from server.app.core.doc_retention import prune_document_versions
from server.app.core.permissions import (
    ClubContext,
    Role,
    get_current_user,
    require_club_access,
)
from server.app.core.scoped_repo import ScopedRepository
from server.app.models import (
    Asset,
    AuditLog,
    Club,
    Document,
    DocumentVersion,
    Event,
    Letterhead,
    NumberingSeries,
    NumberReservation,
    Template,
    TemplateVersion,
    User,
    Venue,
)
from server.app.core.dummy_thumbnail import (
    get_dummy_thumbnail_event_record,
    get_neutral_placeholder,
    is_placeholder_file,
    is_thumbnail_pending,
    render_template_thumbnail,
)

router = APIRouter(prefix="/clubs/{club_id}/documents", tags=["documents"])


# ---------------- SCHEMAS ----------------


class ExtractRequest(BaseModel):
    text: str = Field(..., min_length=5)


class GenerateDocumentRequest(BaseModel):
    template_id: str
    event_id: Optional[str] = None
    title: Optional[str] = None
    ref_no: Optional[str] = None
    ref_no_confirmed: bool = False
    reservation_id: Optional[str] = None
    event_data: dict[str, Any] = Field(default_factory=dict)
    confirmed_fields: list[str] = Field(default_factory=list)
    deferred_fields: list[str] = Field(default_factory=list)


class TemplateFieldOut(BaseModel):
    key: str
    type: str
    required: bool
    defer_ok: bool = False
    ask: Optional[str] = None
    default_value: Optional[Any] = None
    default_source: Optional[str] = None
    source_allowed: Optional[list[str]] = None
    values: Optional[list[str]] = None


class TemplateDetailOut(BaseModel):
    id: str
    name: str
    description: str
    stage: str
    fields: list[TemplateFieldOut]
    defaults: dict[str, Any]
    numbering_series: Optional[str] = None
    confirm_numbering: bool = False


class TemplateGalleryItemOut(BaseModel):
    id: str
    slug: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    stage: Optional[str] = None
    is_system: bool
    status: str
    forked_from_template_id: Optional[str] = None
    numbering_series: Optional[str] = None
    thumbnail_url: Optional[str] = None
    can_fork: bool = False
    can_edit: bool = False


class TemplateForkRequest(BaseModel):
    name: Optional[str] = None


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    schema_yaml: Optional[str] = None
    status: Optional[str] = None


class TemplateCreateBlankRequest(BaseModel):
    name: str = Field(..., min_length=1)
    category: Optional[str] = "Official Event Documents"
    description: Optional[str] = ""
    numbering_series: Optional[str] = None


class TemplateDraftOut(BaseModel):
    template_id: str
    slug: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    status: str
    is_system: bool
    version_no: int
    editor_json: dict[str, Any]
    fields: list[dict[str, Any]]
    letterhead_id: Optional[str] = None
    design_settings: Optional[dict[str, Any]] = None
    validation_report: Optional[dict[str, Any]] = None
    can_edit: bool = False


class TemplateDraftSaveRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    editor_json: Optional[dict[str, Any]] = None
    fields: Optional[list[dict[str, Any]]] = None
    letterhead_id: Optional[str] = None
    design_settings: Optional[dict[str, Any]] = None


def chip_labels_from_editor(editor_json: Any) -> dict[str, str]:
    """fieldName -> label of the field chips in a template's editor content."""
    out: dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "fieldChip":
                attrs = node.get("attrs") or {}
                if attrs.get("fieldName") and attrs.get("label"):
                    out.setdefault(attrs["fieldName"], attrs["label"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(editor_json or {})
    return out


def field_label(f: dict[str, Any], chip_labels: Optional[dict[str, str]] = None) -> str:
    """A field's short label ("Event Name"), not its question ("What is the event name?")."""
    key = f.get("key") or ""
    return f.get("label") or (chip_labels or {}).get(key) or key.replace("_", " ").title()


class TemplateCompileRequest(BaseModel):
    editor_json: Optional[dict[str, Any]] = None
    fields: Optional[list[dict[str, Any]]] = None
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    letterhead_id: Optional[str] = None
    numbering_series: Optional[str] = None
    design_settings: Optional[dict[str, Any]] = None
    for_publish: Optional[bool] = False
    # Preview only: example values typed in the editor sidebar, by field key
    sample_values: Optional[dict[str, Any]] = None


class TemplateReviewAIRequest(BaseModel):
    all: bool = False
    field_keys: Optional[list[str]] = None
    block_indices: Optional[list[int]] = None


class TemplateCompileResponse(BaseModel):
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    stats: dict[str, Any]
    version_no: int


class TemplatePreviewResponse(BaseModel):
    pages: list[str]
    page_count: int
    orientation: Optional[str] = "portrait"


class TemplateDescribeRequest(BaseModel):
    description: str


class TemplateDescribeResponse(BaseModel):
    template: TemplateGalleryItemOut
    draft: TemplateDraftOut
    logo_resolution: dict[str, Any]
    message: str


class ResolveLogoRequest(BaseModel):
    text: str


class LetterheadOut(BaseModel):
    id: str
    name: str
    title_text: Optional[str] = None
    subtitle_text: Optional[str] = None
    is_system: bool = False
    svnit_logo_locked: bool = True
    club_logo_url: Optional[str] = None
    svnit_logo_url: Optional[str] = None


class WizardQuestionsRequest(BaseModel):
    prompt: str


class ImportTextRequest(BaseModel):
    text: str
    name: Optional[str] = None


class ImproveTextRequest(BaseModel):
    text: str
    mode: Optional[str] = "formal"


class SuggestDetailsRequest(BaseModel):
    event_type: str = "Workshop"
    existing_fields: Optional[list[str]] = None


class CheckDocumentRequest(BaseModel):
    editor_json: Optional[dict[str, Any]] = None
    fields: Optional[list[dict[str, Any]]] = None
    design_settings: Optional[dict[str, Any]] = None


class TranslateTemplateRequest(BaseModel):
    target_lang: str = "hi"
    editor_json: Optional[dict[str, Any]] = None




class DocumentVersionOut(BaseModel):
    id: str
    version_no: int
    docx_available: bool
    pdf_available: bool
    created_at: datetime
    created_by: Optional[str] = None
    change_summary: Optional[str] = None


class DocumentDetailOut(BaseModel):
    id: str
    club_id: str
    template_id: str
    title: str
    ref_no: Optional[str] = None
    status: str
    created_at: datetime
    current_version_no: int
    page_count: int
    docx_url: str
    pdf_url: str
    page_images: list[str]
    versions: list[DocumentVersionOut]
    record_snapshot: dict[str, Any]
    editable_fields: list[dict[str, Any]] = []
    activity: list[dict[str, Any]] = []
    can_edit: bool = False
    can_review: bool = False
    template_name: Optional[str] = None


# ---------------- HELPER FUNCTIONS ----------------


def get_suggested_ref_no(
    db: Session,
    club_or_id: Any,
    template_or_schema: Any,
    event_code: Optional[str] = None,
) -> Optional[str]:
    """Dynamically compute suggested reference number without hardcoded series mappings or years."""
    if isinstance(club_or_id, str):
        club = db.query(Club).filter(Club.id == club_or_id).first()
    else:
        club = club_or_id

    if isinstance(template_or_schema, str):
        try:
            schema = load_schema(template_or_schema)
        except Exception:
            return None
    else:
        schema = template_or_schema

    if not schema or not schema.numbering:
        return None

    series_key = schema.numbering.series or event_code or "EVENT"
    academic_year = getattr(club, "academic_year_default", None) or (getattr(club, "settings", {}) or {}).get("academic_year", "")
    club_prefix = getattr(club, "short_name", None) or getattr(club, "slug", "").upper()

    series_repo = ScopedRepository(db, NumberingSeries, club_id=club.id)
    ns = series_repo.find_first(
        NumberingSeries.key == series_key,
        NumberingSeries.academic_year == academic_year,
    )
    next_seq = (ns.last_seq + 1) if ns else 1
    fmt = ns.format if (ns and ns.format) else (schema.numbering.format or f"{club_prefix}/{{academic_year}}/{{series}}/{{seq:03d}}")
    return format_reference_number(
        format_pattern=fmt,
        academic_year=academic_year,
        series_key=series_key,
        seq=next_seq,
        club_code=club_prefix,
        event_code=event_code,
    )

from server.app.core.numbering_service import allocate_next_sequence


# ---------------- ENDPOINTS ----------------



@router.get("/templates", response_model=list[TemplateGalleryItemOut])
def list_template_gallery(
    category: Optional[str] = None,
    stage: Optional[str] = None,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Template gallery listing system and club templates with category and numbering series."""
    # List system templates AND templates created by/forked into this club
    query = db.query(Template).filter(
        (Template.club_id.is_(None)) | (Template.club_id == ctx.club.id)
    )
    # Hide archived templates from active gallery listing
    query = query.filter(Template.status != "archived")

    if category:
        query = query.filter(Template.category == category)
    if stage:
        query = query.filter(Template.stage == stage)

    templates = query.order_by(Template.is_system.desc(), Template.name.asc()).all()
    user_can_manage = ctx.role in (Role.OWNER, Role.ADMIN, Role.EDITOR)

    items = []
    for t in templates:
        series_key = None
        ver = (
            db.query(TemplateVersion)
            .filter(TemplateVersion.template_id == t.id)
            .order_by(TemplateVersion.version_no.desc())
            .first()
        )
        if ver and ver.schema_yaml:
            try:
                s_data = yaml.safe_load(ver.schema_yaml)
                if isinstance(s_data, dict) and "numbering" in s_data and s_data["numbering"]:
                    series_key = s_data["numbering"].get("series")
            except Exception:
                pass
        if not series_key and (Path("templates") / t.slug / "schema.yaml").exists():
            try:
                s_obj = load_schema(t.slug)
                series_key = s_obj.numbering.series if s_obj.numbering else None
            except Exception:
                pass

        items.append(
            TemplateGalleryItemOut(
                id=t.id,
                slug=t.slug,
                name=t.name,
                description=t.description,
                category=t.category or "Official Event Documents",
                stage=t.stage,
                is_system=bool(t.is_system),
                status=t.status,
                forked_from_template_id=t.forked_from_template_id,
                numbering_series=series_key or (t.slug.upper() if t.stage == "pre_event" else None),
                thumbnail_url=f"/api/v1/clubs/{ctx.club.id}/documents/templates/{t.id}/thumbnail",
                can_fork=bool(t.is_system and user_can_manage),
                can_edit=bool(not t.is_system and user_can_manage),
            )
        )
    return items


@router.get("/templates/{template_id}/thumbnail")
def get_template_thumbnail(
    template_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Serve thumbnail image rendered from dummy sample data via LibreOffice & PyMuPDF."""
    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    tmpl = db.query(Template).filter(
        ((Template.id == template_id) | (Template.slug == template_id)),
        ((Template.club_id.is_(None)) | (Template.club_id == ctx.club.id)),
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    ver = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == tmpl.id)
        .order_by(TemplateVersion.version_no.desc())
        .first()
    )
    if not ver:
        placeholder = get_neutral_placeholder()
        return FileResponse(placeholder, media_type="image/png", headers={"Cache-Control": "no-store", "X-Thumbnail": "pending"})

    thumbnails_dir = local_storage.base_dir / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    from server.app.core.dummy_thumbnail import thumbnail_stem

    stem = thumbnail_stem(tmpl, ver, ctx.club.id)
    thumb_path = local_storage.local_path(f"thumbnails/{stem}.webp")
    if not thumb_path.exists() or is_placeholder_file(thumb_path):
        thumb_path_png = local_storage.local_path(f"thumbnails/{stem}.png")
        if thumb_path_png.exists() and not is_placeholder_file(thumb_path_png):
            thumb_path = thumb_path_png

    # Check copy-on-write fork source template version if not rendered yet
    if (not thumb_path.exists() or is_placeholder_file(thumb_path)) and tmpl.forked_from_template_id:
        src_tmpl = db.query(Template).filter(Template.id == tmpl.forked_from_template_id).first()
        if src_tmpl:
            src_ver = (
                db.query(TemplateVersion)
                .filter(TemplateVersion.template_id == src_tmpl.id)
                .order_by(TemplateVersion.version_no.desc())
                .first()
            )
            if src_ver:
                src_stem = thumbnail_stem(src_tmpl, src_ver, ctx.club.id)
                src_webp = local_storage.local_path(f"thumbnails/{src_stem}.webp")
                src_png = local_storage.local_path(f"thumbnails/{src_stem}.png")
                if src_webp.exists() and not is_placeholder_file(src_webp):
                    return FileResponse(src_webp, media_type="image/webp", headers={"Cache-Control": "no-cache", "X-Thumbnail": "ready"})
                elif src_png.exists() and not is_placeholder_file(src_png):
                    return FileResponse(src_png, media_type="image/png", headers={"Cache-Control": "no-cache", "X-Thumbnail": "ready"})

    if not thumb_path.exists() or is_placeholder_file(thumb_path):
        thumb_path = render_template_thumbnail(
            db=db,
            tmpl=tmpl,
            ver=ver,
            club_slug=ctx.club.slug,
            club_id=ctx.club.id,
        )

    is_pending = is_thumbnail_pending(stem) or is_placeholder_file(thumb_path)
    media_type = "image/webp" if str(thumb_path).endswith(".webp") else "image/png"
    headers = (
        {"Cache-Control": "no-store", "X-Thumbnail": "pending"}
        if is_pending
        else {"Cache-Control": "no-cache", "X-Thumbnail": "ready"}
    )
    return FileResponse(thumb_path, media_type=media_type, headers=headers)


def _gallery_template(db: Session, template_id: str, club_id: str):
    tmpl = db.query(Template).filter(
        (Template.id == template_id) | (Template.slug == template_id),
        ((Template.club_id.is_(None)) | (Template.club_id == club_id)),
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    ver = (
        db.query(TemplateVersion).filter(TemplateVersion.id == tmpl.current_version_id).first()
        or db.query(TemplateVersion).filter(TemplateVersion.template_id == tmpl.id)
        .order_by(TemplateVersion.version_no.desc()).first()
    )
    if not ver:
        raise HTTPException(status_code=404, detail="Template has no version")
    return tmpl, ver


@router.get("/templates/{template_id}/sample-pages")
def get_template_sample_pages(
    template_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Every page of the template filled with sample data, as this club would print it."""
    from server.app.core.dummy_thumbnail import render_template_preview_pages

    tmpl, ver = _gallery_template(db, template_id, ctx.club.id)
    try:
        pages = render_template_preview_pages(db, tmpl, ver, ctx.club.slug, ctx.club.id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if not pages:
        raise HTTPException(status_code=422, detail="This template could not be rendered for preview.")
    base = f"/api/v1/clubs/{ctx.club.id}/documents/templates/{tmpl.id}/sample-pages"
    return {
        "name": tmpl.name,
        "description": tmpl.description,
        "page_count": len(pages),
        "pages": [f"{base}/{i + 1}?v={int(p.stat().st_mtime)}" for i, p in enumerate(pages)],
    }


@router.get("/templates/{template_id}/sample-pages/{page_no}")
def get_template_sample_page(
    template_id: str,
    page_no: int,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """One page image of the sample preview."""
    from server.app.core.dummy_thumbnail import preview_page_paths, thumbnail_stem

    tmpl, ver = _gallery_template(db, template_id, ctx.club.id)
    thumb = require_local_storage().base_dir / "thumbnails" / f"{thumbnail_stem(tmpl, ver, ctx.club.id)}.webp"
    pages = preview_page_paths(thumb)
    if page_no < 1 or page_no > len(pages):
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(pages[page_no - 1], media_type="image/webp", headers={"Cache-Control": "private, max-age=300"})


@router.post("/templates/{template_id}/fork", response_model=TemplateGalleryItemOut, status_code=status.HTTP_201_CREATED)
def fork_template(
    template_id: str,
    payload: Optional[TemplateForkRequest] = None,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Customize (fork) copies the system template into the club as a draft.
    
    Creates a new template + version 1 + docx copy + schema copy,
    editable only by club admins and editors. System templates stay read-only.
    Duplicate forks of the same template get unique names automatically.
    """
    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    orig = db.query(Template).filter(
        ((Template.id == template_id) | (Template.slug == template_id)),
        ((Template.club_id.is_(None)) | (Template.club_id == ctx.club.id)),
    ).first()
    if not orig:
        raise HTTPException(status_code=404, detail="Template not found")

    orig_ver = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == orig.id)
        .order_by(TemplateVersion.version_no.desc())
        .first()
    )

    new_tmpl_id = str(uuid.uuid4())
    src_docx = None
    if orig_ver and orig_ver.docx_storage_key:
        candidate = local_storage.local_path(orig_ver.docx_storage_key)
        if candidate.exists():
            src_docx = candidate
    if src_docx is None and (Path("templates") / orig.slug / "template.docx").exists():
        src_docx = Path("templates") / orig.slug / "template.docx"

    if src_docx and src_docx.exists():
        rel_key, _ = storage.save_content_addressed("templates", src_docx.read_bytes(), "docx")
        dest_docx = local_storage.local_path(rel_key)
    else:
        storage_templates_dir = local_storage.base_dir / "templates"
        storage_templates_dir.mkdir(parents=True, exist_ok=True)
        dest_docx = storage_templates_dir / f"{new_tmpl_id}_v1.docx"
        dest_docx.touch()

    if orig_ver and orig_ver.schema_yaml:
        schema_yaml_str = orig_ver.schema_yaml
    elif (Path("templates") / orig.slug / "schema.yaml").exists():
        schema_yaml_str = (Path("templates") / orig.slug / "schema.yaml").read_text(encoding="utf-8")
    else:
        schema_yaml_str = "id: custom\nname: Custom Template\n"

    # Compute unique fork name
    existing_club_templates = (
        db.query(Template)
        .filter(Template.club_id == ctx.club.id, Template.status != "archived")
        .all()
    )
    existing_names = {t.name for t in existing_club_templates}

    if payload and payload.name and payload.name.strip():
        desired = payload.name.strip()
        if desired not in existing_names:
            forked_name = desired
        else:
            idx = 2
            while f"{desired} ({idx})" in existing_names:
                idx += 1
            forked_name = f"{desired} ({idx})"
    else:
        base_name = f"{orig.name} (Custom)"
        if base_name not in existing_names:
            forked_name = base_name
        else:
            idx = 2
            while f"{orig.name} (Custom {idx})" in existing_names:
                idx += 1
            forked_name = f"{orig.name} (Custom {idx})"

    forked_slug = f"{orig.slug}-custom-{uuid.uuid4().hex[:6]}"
    forked_tmpl = Template(
        id=new_tmpl_id,
        club_id=ctx.club.id,
        slug=forked_slug,
        name=forked_name,
        description=orig.description,
        category=orig.category,
        stage=orig.stage,
        is_system=False,
        forked_from_template_id=orig.id,
        status="draft",
    )
    db.add(forked_tmpl)
    db.flush()

    forked_editor_json = None
    if orig_ver and orig_ver.editor_json:
        forked_editor_json = copy.deepcopy(orig_ver.editor_json)
    else:
        fields_for_editor = []
        try:
            parsed = yaml.safe_load(schema_yaml_str)
            if isinstance(parsed, dict) and "fields" in parsed:
                fields_for_editor = parsed["fields"]
        except Exception:
            pass

        doc_content = [
            {"type": "heading", "attrs": {"level": 1, "textAlign": "center"}, "content": [{"type": "text", "text": forked_name}]},
            {"type": "paragraph", "content": [{"type": "text", "text": f"This official document is generated for {orig.name}."}]}
        ]
        if fields_for_editor:
            chips = []
            for f in fields_for_editor:
                f_key = f.get("key")
                if f_key:
                    chips.append({"type": "text", "text": f" {field_label(f)}: "})
                    chips.append({"type": "fieldChip", "attrs": {"fieldName": f_key, "label": field_label(f), "fieldType": f.get("type", "text")}})
                    chips.append({"type": "text", "text": " | "})
            doc_content.append({"type": "paragraph", "content": chips})

        doc_content.append({
            "type": "signatureGrid",
            "attrs": {
                "columns": 3,
                "signatures": default_signatures(ctx.club),
            }
        })
        forked_editor_json = {"type": "doc", "content": doc_content}

    forked_ver = TemplateVersion(
        id=str(uuid.uuid4()),
        template_id=forked_tmpl.id,
        version_no=1,
        schema_yaml=schema_yaml_str,
        editor_json=forked_editor_json,
        docx_storage_key=str(dest_docx),
        created_by=ctx.user.id,
        change_note=f"Forked from {orig.name}",
    )
    db.add(forked_ver)
    db.flush()
    forked_tmpl.current_version_id = forked_ver.id
    db.commit()
    db.refresh(forked_tmpl)

    log_audit(
        db=db,
        action="template_forked",
        entity_type="template",
        entity_id=forked_tmpl.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"source_template_id": orig.id, "source_template_name": orig.name, "forked_name": forked_name},
    )

    series_key = None
    try:
        parsed_yaml = yaml.safe_load(schema_yaml_str)
        if isinstance(parsed_yaml, dict):
            series_key = parsed_yaml.get("numbering", {}).get("series")
    except Exception:
        pass
    if not series_key and (Path("templates") / orig.slug / "schema.yaml").exists():
        try:
            s_obj = load_schema(orig.slug)
            series_key = s_obj.numbering.series if s_obj.numbering else None
        except Exception:
            pass

    return TemplateGalleryItemOut(
        id=forked_tmpl.id,
        slug=forked_tmpl.slug,
        name=forked_tmpl.name,
        description=forked_tmpl.description,
        category=forked_tmpl.category,
        stage=forked_tmpl.stage,
        is_system=False,
        status=forked_tmpl.status,
        forked_from_template_id=orig.id,
        numbering_series=series_key or (orig.slug.upper() if orig.stage == "pre_event" else None),
        thumbnail_url=f"/api/v1/clubs/{ctx.club.id}/documents/templates/{forked_tmpl.id}/thumbnail",
        can_fork=False,
        can_edit=True,
    )


@router.put("/templates/{template_id}", response_model=TemplateGalleryItemOut)
def update_template(
    template_id: str,
    payload: TemplateUpdateRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Edit/Rename a forked draft template. System templates stay read-only."""
    tmpl = db.query(Template).filter(
        (Template.id == template_id) | (Template.slug == template_id)
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    if tmpl.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System templates stay read-only and cannot be modified. Fork the template first.",
        )

    if tmpl.club_id != ctx.club.id:
        raise HTTPException(status_code=403, detail="Template belongs to another club")

    if payload.name is not None and payload.name.strip():
        new_name = payload.name.strip()
        conflict = (
            db.query(Template)
            .filter(
                Template.id != tmpl.id,
                # Unique among the club's own templates and the built-in ones.
                ((Template.club_id == ctx.club.id) | (Template.club_id.is_(None))),
                Template.status != "archived",
            )
            .all()
        )
        if any(t.name.strip().lower() == new_name.lower() for t in conflict):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DUPLICATE_TEMPLATE_NAME",
                    "message": f"A template named '{new_name}' already exists in this club. Please choose a unique name.",
                },
            )
        tmpl.name = new_name
    if payload.description is not None:
        tmpl.description = payload.description
    if payload.category is not None:
        tmpl.category = payload.category
    if payload.status is not None:
        tmpl.status = payload.status

    ver = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == tmpl.id)
        .order_by(TemplateVersion.version_no.desc())
        .first()
    )
    if payload.schema_yaml is not None and ver:
        ver.schema_yaml = payload.schema_yaml

    db.commit()
    db.refresh(tmpl)

    log_audit(
        db=db,
        action="template_updated",
        entity_type="template",
        entity_id=tmpl.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"updated_name": tmpl.name, "updated_status": tmpl.status},
    )

    series_key = None
    if ver and ver.schema_yaml:
        try:
            parsed = yaml.safe_load(ver.schema_yaml)
            if isinstance(parsed, dict):
                series_key = parsed.get("numbering", {}).get("series")
        except Exception:
            pass

    return TemplateGalleryItemOut(
        id=tmpl.id,
        slug=tmpl.slug,
        name=tmpl.name,
        description=tmpl.description,
        category=tmpl.category,
        stage=tmpl.stage,
        is_system=False,
        status=tmpl.status,
        forked_from_template_id=tmpl.forked_from_template_id,
        numbering_series=series_key,
        thumbnail_url=f"/api/v1/clubs/{ctx.club.id}/documents/templates/{tmpl.id}/thumbnail",
        can_fork=False,
        can_edit=True,
    )


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_or_archive_template(
    template_id: str,
    hard_delete: bool = False,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Archive or delete a club draft template. System templates stay read-only."""
    tmpl = db.query(Template).filter(
        (Template.id == template_id) | (Template.slug == template_id)
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    if tmpl.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System templates stay read-only and cannot be archived or deleted.",
        )

    if tmpl.club_id != ctx.club.id:
        raise HTTPException(status_code=403, detail="Template belongs to another club")

    if hard_delete:
        db.delete(tmpl)
    else:
        tmpl.status = "archived"
    db.commit()

    log_audit(
        db=db,
        action="template_deleted" if hard_delete else "template_archived",
        entity_type="template",
        entity_id=tmpl.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"template_name": tmpl.name, "hard_delete": hard_delete},
    )
    return None


@router.post("/templates/blank", response_model=TemplateGalleryItemOut, status_code=status.HTTP_201_CREATED)
def create_blank_template(
    payload: TemplateCreateBlankRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Create a new blank template draft for the club."""
    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Template name cannot be empty")

    existing_templates = (
        db.query(Template)
        .filter(
            # Unique among the club's own templates and the built-in ones.
            ((Template.club_id == ctx.club.id) | (Template.club_id.is_(None))),
            Template.status != "archived",
        )
        .all()
    )
    if any(t.name.strip().lower() == name.lower() for t in existing_templates):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_TEMPLATE_NAME",
                "message": f"A template named '{name}' already exists in this club. Please choose a unique name.",
            },
        )
    unique_name = name

    new_id = str(uuid.uuid4())
    slug = f"custom-{uuid.uuid4().hex[:8]}"

    initial_json = {
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 1, "textAlign": "center"}, "content": [{"type": "text", "text": unique_name if len(unique_name.strip()) > 1 else "Official Document / Notice"}]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "This document serves as an official communication for "},
                {"type": "fieldChip", "attrs": {"fieldName": "event_name", "label": "Event Name", "fieldType": "text"}},
                {"type": "text", "text": " scheduled on "},
                {"type": "fieldChip", "attrs": {"fieldName": "event_date", "label": "Event Date", "fieldType": "date"}},
                {"type": "text", "text": " at "},
                {"type": "fieldChip", "attrs": {"fieldName": "venue", "label": "Venue", "fieldType": "text"}},
                {"type": "text", "text": "."}
            ]},
            {"type": "signatureGrid", "attrs": {
                "columns": 3,
                "signatures": default_signatures(ctx.club)
            }}
        ]
    }
    initial_json = migrate_template_content(initial_json)
    initial_fields = [
        {"key": "event_name", "label": "Event Name", "type": "text", "required": True, "ask": "What is the event name?"},
        {"key": "event_date", "label": "Event Date", "type": "date", "required": True, "ask": "What is the event date?"},
        {"key": "venue", "label": "Venue", "type": "text", "required": True, "ask": "What is the event venue?"},
    ]

    docx_bytes, schema_yaml, report = TemplateCompiler.compile(
        editor_json=initial_json,
        fields=initial_fields,
        template_meta={
            "id": new_id,
            "name": unique_name,
            "category": payload.category or "Official Event Documents",
            "description": payload.description or "",
            "numbering_series": payload.numbering_series,
        },
        club_slug=ctx.club.slug,
    )
    rel_key, _ = storage.save_content_addressed("templates", docx_bytes, "docx")
    dest_docx = local_storage.local_path(rel_key)

    tmpl = Template(
        id=new_id,
        club_id=ctx.club.id,
        slug=slug,
        name=unique_name,
        description=payload.description or "",
        category=payload.category or "Official Event Documents",
        stage="custom",
        is_system=False,
        status="draft",
    )
    db.add(tmpl)
    db.flush()

    ver = TemplateVersion(
        id=str(uuid.uuid4()),
        template_id=tmpl.id,
        version_no=1,
        editor_json=initial_json,
        schema_yaml=schema_yaml,
        docx_storage_key=str(dest_docx),
        validation_report=report,
        created_by=ctx.user.id,
        change_note="Initial blank template",
    )
    db.add(ver)
    db.flush()
    tmpl.current_version_id = ver.id
    db.commit()
    db.refresh(tmpl)

    log_audit(
        db=db,
        action="template_created",
        entity_type="template",
        entity_id=tmpl.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"template_name": tmpl.name},
    )

    return TemplateGalleryItemOut(
        id=tmpl.id,
        slug=tmpl.slug,
        name=tmpl.name,
        description=tmpl.description,
        category=tmpl.category,
        stage=tmpl.stage,
        is_system=False,
        status=tmpl.status,
        numbering_series=payload.numbering_series,
        thumbnail_url=f"/api/v1/clubs/{ctx.club.id}/documents/templates/{tmpl.id}/thumbnail",
        can_fork=False,
        can_edit=True,
    )


@router.post("/templates/ai-draft", response_model=TemplateDescribeResponse, status_code=status.HTTP_201_CREATED)
def ai_draft_template(
    payload: TemplateDescribeRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Generate a draft template from plain text description using AI."""
    tmpl, ver, logo_res = generate_draft_template(
        description=payload.description,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        db=db,
    )
    fields_list = []
    chip_labels = chip_labels_from_editor(ver.editor_json)
    if ver.schema_yaml:
        try:
            s_dict = yaml.safe_load(ver.schema_yaml)
            if isinstance(s_dict, dict) and "fields" in s_dict:
                for f in s_dict["fields"]:
                    fields_list.append({
                        "key": f.get("key"),
                        "label": field_label(f, chip_labels),
                        "type": f.get("type", "text"),
                        "required": bool(f.get("required", False)),
                        "ask": f.get("ask"),
                        "defer_ok": bool(f.get("defer_ok", False)),
                        "sensitive": bool(f.get("mask", False)),
                        "values": f.get("values"),
                        "ai_suggested": True,
                    })
        except Exception:
            pass

    tmpl_out = TemplateGalleryItemOut(
        id=tmpl.id,
        slug=tmpl.slug,
        name=tmpl.name,
        category=tmpl.category,
        stage="custom",
        description=tmpl.description or "",
        is_system=False,
        status=tmpl.status,
        numbering_series=None,
        thumbnail_url=f"/api/v1/clubs/{ctx.club.id}/documents/templates/{tmpl.id}/thumbnail",
        can_fork=False,
        can_edit=True,
    )
    draft_out = TemplateDraftOut(
        template_id=tmpl.id,
        slug=tmpl.slug,
        name=tmpl.name,
        description=tmpl.description,
        category=tmpl.category,
        status=tmpl.status,
        is_system=False,
        version_no=ver.version_no,
        editor_json=ver.editor_json or {},
        fields=fields_list,
        letterhead_id=ver.letterhead_id,
        validation_report=ver.validation_report,
        can_edit=True,
    )
    return TemplateDescribeResponse(
        template=tmpl_out,
        draft=draft_out,
        logo_resolution=logo_res,
        message="AI draft generated successfully. Review and adjust fields in the editor, then Compile & Validate before publishing.",
    )


@router.post("/assets/resolve-logo")
def resolve_logo(
    payload: ResolveLogoRequest,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Resolve a club logo from a natural text description or name."""
    return resolve_club_logo_by_text(ctx.club.id, payload.text, db)


@router.get("/templates/{template_id}/draft", response_model=TemplateDraftOut)
def get_template_draft(
    template_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Fetch draft template details, editor JSON, and fields schema."""
    tmpl = db.query(Template).filter(
        (Template.id == template_id) | (Template.slug == template_id)
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    if tmpl.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System templates are immutable and cannot be edited. Fork the template first to customize it.",
        )

    if tmpl.club_id != ctx.club.id:
        raise HTTPException(status_code=403, detail="Template belongs to another club")

    ver = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == tmpl.id)
        .order_by(TemplateVersion.version_no.desc())
        .first()
    )
    if not ver:
        raise HTTPException(status_code=404, detail="Template has no version")

    editor_json = migrate_template_content(ver.editor_json) if ver.editor_json else {"type": "doc", "content": []}
    fields_list = []
    chip_labels = chip_labels_from_editor(ver.editor_json)
    if ver.schema_yaml:
        try:
            s_dict = yaml.safe_load(ver.schema_yaml)
            if isinstance(s_dict, dict) and "fields" in s_dict:
                for f in s_dict["fields"]:
                    fields_list.append({
                        "key": f.get("key"),
                        "label": field_label(f, chip_labels),
                        "type": f.get("type", "text"),
                        "required": bool(f.get("required", False)),
                        "ask": f.get("ask"),
                        "defer_ok": bool(f.get("defer_ok", False)),
                        "sensitive": bool(f.get("mask", False)),
                        "values": f.get("values"),
                        "computed": f.get("computed"),
                        "format": f.get("format"),
                        "ai_suggested": bool(f.get("ai_suggested", False)),
                    })
        except Exception:
            pass

    if not editor_json:
        editor_json = {
            "type": "doc",
            "content": [
                {"type": "heading", "attrs": {"level": 1, "textAlign": "center"}, "content": [{"type": "text", "text": tmpl.name}]},
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "This document is for "},
                    {"type": "fieldChip", "attrs": {"fieldName": "event_name", "label": "Event Name", "fieldType": "text"}},
                    {"type": "text", "text": "."}
                ]}
            ]
        }
        if not fields_list:
            fields_list = [
                {"key": "event_name", "label": "Event Name", "type": "text", "required": True, "ask": "What is the event title?"}
            ]

    can_edit = ctx.role in (Role.EDITOR, Role.ADMIN, Role.OWNER)

    draft_design_settings = None
    if isinstance(editor_json, dict):
        draft_design_settings = editor_json.get("design_settings") or editor_json.get("attrs", {}).get("design_settings")
    if not draft_design_settings and ver and isinstance(ver.editor_json, dict):
        draft_design_settings = ver.editor_json.get("design_settings") or ver.editor_json.get("attrs", {}).get("design_settings")

    return TemplateDraftOut(
        template_id=tmpl.id,
        slug=tmpl.slug,
        name=tmpl.name,
        description=tmpl.description,
        category=tmpl.category,
        status=tmpl.status,
        is_system=False,
        version_no=ver.version_no,
        editor_json=editor_json,
        fields=fields_list,
        letterhead_id=ver.letterhead_id,
        design_settings=draft_design_settings,
        validation_report=ver.validation_report,
        can_edit=can_edit,
    )


@router.put("/templates/{template_id}/draft", response_model=TemplateDraftOut)
def save_template_draft(
    template_id: str,
    payload: TemplateDraftSaveRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Save editor draft (autosave / manual save). Published templates get a new version."""
    tmpl = db.query(Template).filter(
        (Template.id == template_id) | (Template.slug == template_id)
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    if tmpl.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System templates are immutable and cannot be edited.",
        )

    if tmpl.club_id != ctx.club.id:
        raise HTTPException(status_code=403, detail="Template belongs to another club")

    try:
        from server.app.core.template_compiler import validate_template_identifiers
        validate_template_identifiers(payload.editor_json, payload.fields)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    latest_ver = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == tmpl.id)
        .order_by(TemplateVersion.version_no.desc())
        .first()
    )

    # If currently published, create a new draft version
    target_ver = latest_ver
    if tmpl.status == "published":
        next_ver_no = (latest_ver.version_no + 1) if latest_ver else 1
        target_ver = TemplateVersion(
            id=str(uuid.uuid4()),
            template_id=tmpl.id,
            version_no=next_ver_no,
            editor_json=latest_ver.editor_json if latest_ver else None,
            schema_yaml=latest_ver.schema_yaml if latest_ver else "",
            docx_storage_key=latest_ver.docx_storage_key if latest_ver else "",
            letterhead_id=latest_ver.letterhead_id if latest_ver else None,
            created_by=ctx.user.id,
            change_note=f"Draft version {next_ver_no}",
        )
        db.add(target_ver)
        tmpl.status = "draft"
        tmpl.current_version_id = target_ver.id
        db.flush()

    if payload.name:
        new_name = payload.name.strip()
        conflict = (
            db.query(Template)
            .filter(
                Template.id != tmpl.id,
                # Unique among the club's own templates and the built-in ones.
                ((Template.club_id == ctx.club.id) | (Template.club_id.is_(None))),
                Template.status != "archived",
            )
            .all()
        )
        if any(t.name.strip().lower() == new_name.lower() for t in conflict):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DUPLICATE_TEMPLATE_NAME",
                    "message": f"A template named '{new_name}' already exists in this club. Please choose a unique name.",
                },
            )
        tmpl.name = new_name
    if payload.description is not None:
        tmpl.description = payload.description
    if payload.category:
        tmpl.category = payload.category

    if payload.editor_json is not None:
        target_ver.editor_json = payload.editor_json
        if payload.design_settings is not None and isinstance(target_ver.editor_json, dict):
            target_ver.editor_json["design_settings"] = payload.design_settings
    elif payload.design_settings is not None and target_ver.editor_json and isinstance(target_ver.editor_json, dict):
        target_ver.editor_json["design_settings"] = payload.design_settings
    # Letterheads are generated per club; a template no longer picks one
    target_ver.letterhead_id = None

    fields_to_return = payload.fields or []
    if payload.fields is not None:
        prev_num = None
        if target_ver.schema_yaml:
            try:
                parsed_prev = yaml.safe_load(target_ver.schema_yaml)
                if isinstance(parsed_prev, dict) and "numbering" in parsed_prev:
                    prev_num = parsed_prev["numbering"]
            except Exception:
                pass

        s_dict = {
            "id": tmpl.id,
            "name": tmpl.name,
            "category": tmpl.category,
            "description": tmpl.description or "",
            "stage": tmpl.stage or "custom",
            "letterhead": "club",
            "numbering": prev_num or {
                "series": "DOC",
                "format": f"{ctx.club.slug.upper()}/{{short_year}}/DOC/{{seq:03d}}",
                "confirm": True,
            },
            "fields": [
                {
                    "key": f["key"],
                    "type": f.get("type", "text"),
                    "required": bool(f.get("required", False)),
                    "ask": f.get("ask") or f.get("label"),
                    **({"defer_ok": True} if f.get("defer_ok") else {}),
                    **({"mask": True} if f.get("sensitive") else {}),
                    **({"values": f.get("values")} if f.get("values") else {}),
                    **({"computed": f.get("computed")} if f.get("computed") else {}),
                    **({"format": f.get("format")} if f.get("format") else {}),
                }
                for f in payload.fields if f.get("key")
            ],
        }
        target_ver.schema_yaml = yaml.dump(s_dict, sort_keys=False)

    db.commit()
    db.refresh(tmpl)
    db.refresh(target_ver)

    return TemplateDraftOut(
        template_id=tmpl.id,
        slug=tmpl.slug,
        name=tmpl.name,
        description=tmpl.description,
        category=tmpl.category,
        status=tmpl.status,
        is_system=False,
        version_no=target_ver.version_no,
        editor_json=target_ver.editor_json or {},
        fields=fields_to_return,
        letterhead_id=target_ver.letterhead_id,
        design_settings=payload.design_settings or (target_ver.editor_json.get("design_settings") if isinstance(target_ver.editor_json, dict) else None),
        validation_report=target_ver.validation_report,
        can_edit=True,
    )


@router.post("/templates/{template_id}/compile", response_model=TemplateCompileResponse)
def compile_template(
    template_id: str,
    payload: TemplateCompileRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Compile TipTap JSON into template.docx and schema.yaml with strict validation."""
    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    tmpl = db.query(Template).filter(
        (Template.id == template_id) | (Template.slug == template_id)
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    if tmpl.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System templates are immutable and cannot be compiled or edited.",
        )

    if tmpl.club_id != ctx.club.id:
        raise HTTPException(status_code=403, detail="Template belongs to another club")

    ver = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == tmpl.id)
        .order_by(TemplateVersion.version_no.desc())
        .first()
    )
    if not ver:
        raise HTTPException(status_code=404, detail="Template version not found")

    editor_json = payload.editor_json or ver.editor_json or {"type": "doc", "content": []}
    fields = payload.fields or []
    if not fields and ver.schema_yaml:
        try:
            s_dict = yaml.safe_load(ver.schema_yaml)
            raw_fields = s_dict.get("fields", [])
            fields = raw_fields if isinstance(raw_fields, list) else []
        except Exception:
            pass

    if payload.for_publish:
        from server.app.core.template_compiler import find_unreviewed_ai_items
        unreviewed = find_unreviewed_ai_items(editor_json, fields)
        if unreviewed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "UNREVIEWED_AI_CONTENT",
                    "message": f"Cannot compile for publish: contains {len(unreviewed)} unreviewed AI-suggested item(s). Please review all AI-suggested content first.",
                    "unreviewed_items": unreviewed,
                },
            )

    try:
        from server.app.core.template_compiler import validate_template_identifiers
        validate_template_identifiers(editor_json, fields)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    template_name = payload.name or tmpl.name
    category = payload.category or tmpl.category
    description = payload.description if payload.description is not None else tmpl.description

    # Every template prints the club's generated letterhead
    letterhead_cfg = {"banner_placeholder": True}
    letterhead_id = None
    existing_series = None
    if ver.schema_yaml:
        try:
            parsed = yaml.safe_load(ver.schema_yaml)
            if isinstance(parsed, dict):
                existing_series = parsed.get("numbering", {}).get("series")
        except Exception:
            pass

    from server.app.core.template_generator import derive_unique_series_key
    if payload.numbering_series:
        num_series = derive_unique_series_key(payload.numbering_series, ctx.club.id, db, exclude_template_id=tmpl.id)
    elif existing_series:
        num_series = existing_series
    else:
        num_series = derive_unique_series_key(template_name, ctx.club.id, db, exclude_template_id=tmpl.id)

    comp_design_settings = payload.design_settings
    if not comp_design_settings and isinstance(editor_json, dict):
        comp_design_settings = editor_json.get("design_settings")

    docx_bytes, schema_yaml, report = TemplateCompiler.compile(
        editor_json=editor_json,
        fields=fields,
        template_meta={
            "id": tmpl.id,
            "name": template_name,
            "category": category,
            "description": description,
            "numbering_series": num_series,
        },
        club_slug=ctx.club.slug,
        letterhead_cfg=letterhead_cfg,
        design_settings=comp_design_settings,
    )

    rel_key, _ = storage.save_content_addressed("templates", docx_bytes, "docx")
    docx_dest = local_storage.local_path(rel_key)

    ver.docx_storage_key = str(docx_dest)
    ver.schema_yaml = schema_yaml
    ver.editor_json = editor_json
    ver.validation_report = report
    ver.letterhead_id = letterhead_id
    tmpl.name = template_name
    tmpl.category = category
    tmpl.description = description

    thumbnails_dir = local_storage.base_dir / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumbnails_dir / f"{ver.id}.webp"
    thumb_path_png = thumbnails_dir / f"{ver.id}.png"
    if thumb_path.exists():
        thumb_path.unlink()
    if thumb_path_png.exists():
        thumb_path_png.unlink()

    db.commit()

    return TemplateCompileResponse(
        is_valid=report["is_valid"],
        errors=report.get("errors", []),
        warnings=report.get("warnings", []),
        stats=report.get("stats", {}),
        version_no=ver.version_no,
    )


@router.post("/templates/{template_id}/preview", response_model=TemplatePreviewResponse)
def preview_template(
    template_id: str,
    payload: TemplateCompileRequest,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Render live preview of template with synthetic dummy data only."""
    tmpl = db.query(Template).filter(
        (Template.id == template_id) | (Template.slug == template_id)
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    if tmpl.club_id and tmpl.club_id != ctx.club.id:
        raise HTTPException(status_code=403, detail="Template belongs to another club")

    ver = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == tmpl.id)
        .order_by(TemplateVersion.version_no.desc())
        .first()
    )

    editor_json = payload.editor_json or (ver.editor_json if ver else None) or {"type": "doc", "content": []}
    fields = payload.fields or []
    if not fields and ver and ver.schema_yaml:
        try:
            s_dict = yaml.safe_load(ver.schema_yaml)
            raw_fields = s_dict.get("fields", [])
            fields = raw_fields if isinstance(raw_fields, list) else []
        except Exception:
            pass

    try:
        from server.app.core.template_compiler import validate_template_identifiers
        validate_template_identifiers(editor_json, fields)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Every template prints the club's generated letterhead
    letterhead_cfg = {"banner_placeholder": True}
    letterhead_id = None
    preview_design_settings = payload.design_settings
    if not preview_design_settings and isinstance(editor_json, dict):
        preview_design_settings = editor_json.get("design_settings")

    docx_bytes, schema_yaml, report = TemplateCompiler.compile(
        editor_json=editor_json,
        fields=fields,
        template_meta={
            "id": tmpl.id,
            "name": payload.name or tmpl.name,
            "category": payload.category or tmpl.category,
            "description": payload.description or tmpl.description,
        },
        club_slug=ctx.club.slug,
        letterhead_cfg=letterhead_cfg,
        design_settings=preview_design_settings,
    )

    pages_base64: list[str] = []

    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            tmp_dir = Path(td)
            tmpl_docx = tmp_dir / "template.docx"
            tmpl_docx.write_bytes(docx_bytes)

            schema_dict = yaml.safe_load(schema_yaml)
            schema_obj = TemplateSchema(**schema_dict)
            from server.app.core.template_compiler import _build_editor_dummy_context, safe_render_docx
            dummy_ctx = _build_editor_dummy_context(schema_obj, fields, editor_json)
            # Example values from the sidebar (or a field's default/example) replace the dummy placeholders.
            for f in fields or []:
                if isinstance(f, dict):
                    k = f.get("key")
                    val = f.get("default_value") if f.get("default_value") not in (None, "") else f.get("example") if f.get("example") not in (None, "") else f.get("sample_value")
                    if k and val not in (None, "") and f.get("type") != "table":
                        dummy_ctx[k] = val
            for key, value in (payload.sample_values or {}).items():
                if isinstance(key, str) and value not in (None, ""):
                    dummy_ctx[key] = value if isinstance(value, (list, dict)) else str(value)[:2000]
            doc = DocxTemplate(str(tmpl_docx))
            # Show the viewing club's own identity (name, footer, banner) in the preview.
            try:
                club_cfg = build_club_config_from_db(db, ctx.club.slug)
                inst = (club_cfg.institute_name or "").split("(")[0].strip()
                dummy_ctx.update({
                    "club_name": club_cfg.club_name,
                    "club_short": club_cfg.club_short,
                    "institute_name": club_cfg.institute_name,
                    "institute_short": club_cfg.institute_short,
                    "department": club_cfg.department,
                    "department_short": club_cfg.department_short or club_cfg.department,
                    "club_footer": club_cfg.footer_text or " · ".join(x for x in (club_cfg.club_name, inst) if x),
                })
                club_renderer = Renderer(config=club_cfg)
                club_renderer._apply_club_banner(doc)
                club_renderer._apply_club_logo(doc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Preview could not apply the club's letterhead: %s", exc)

            safe_render_docx(doc, dummy_ctx, timeout=30.0, strict=False)
            rendered_docx = tmp_dir / "rendered.docx"
            doc.save(str(rendered_docx))

            renderer = Renderer()
            try:
                pdf_path, _ = renderer._convert_to_pdf(rendered_docx)
            except Exception:
                import time
                time.sleep(1)
                try:
                    pdf_path, _ = renderer._convert_to_pdf(rendered_docx)
                except Exception:
                    logger.exception("Template preview: PDF conversion failed")
                    raise HTTPException(status_code=500, detail="The preview could not be made right now. Please try again in a moment.")

            pdf_doc = pymupdf.open(str(pdf_path))
            detected_orientation = "portrait"
            for page in pdf_doc:
                if page.rect.width > page.rect.height:
                    detected_orientation = "landscape"
                page_scale = max(1400.0 / max(page.rect.width, 1.0), 2.0)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(page_scale, page_scale))
                png_bytes = pix.tobytes("png")
                b64 = base64.b64encode(png_bytes).decode("ascii")
                pages_base64.append(f"data:image/png;base64,{b64}")
            pdf_doc.close()

        resolved_orientation = "portrait"
        if preview_design_settings and preview_design_settings.get("orientation") in ("portrait", "landscape"):
            resolved_orientation = preview_design_settings["orientation"]
        elif isinstance(editor_json, dict) and (editor_json.get("design_settings") or {}).get("orientation") in ("portrait", "landscape"):
            resolved_orientation = editor_json["design_settings"]["orientation"]
        else:
            resolved_orientation = detected_orientation

        return TemplatePreviewResponse(
            pages=pages_base64,
            page_count=len(pages_base64),
            orientation=resolved_orientation,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Template preview failed")
        raise HTTPException(status_code=500, detail="The preview could not be made. Check the template for empty or broken blocks and try again.")


@router.post("/templates/{template_id}/publish", response_model=TemplateGalleryItemOut)
def publish_template(
    template_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Publish a draft template into an immutable published version."""
    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    tmpl = db.query(Template).filter(
        (Template.id == template_id) | (Template.slug == template_id)
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    if tmpl.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System templates are already published and cannot be modified.",
        )

    if tmpl.club_id != ctx.club.id:
        raise HTTPException(status_code=403, detail="Template belongs to another club")

    ver = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == tmpl.id)
        .order_by(TemplateVersion.version_no.desc())
        .first()
    )
    if not ver:
        raise HTTPException(status_code=404, detail="Template has no version to publish")

    conflict = (
        db.query(Template)
        .filter(
            Template.id != tmpl.id,
            ((Template.club_id == ctx.club.id) | (Template.club_id.is_(None))),
            Template.status != "archived",
        )
        .all()
    )
    existing_names = {t.name.strip().lower() for t in conflict}
    if tmpl.name.strip().lower() in existing_names:
        base_name = tmpl.name.strip()
        idx = 2
        while f"{base_name} ({idx})".lower() in existing_names:
            idx += 1
        tmpl.name = f"{base_name} ({idx})"

    fields = []
    if ver.schema_yaml:
        try:
            s_dict = yaml.safe_load(ver.schema_yaml)
            raw_fields = s_dict.get("fields", [])
            fields = raw_fields if isinstance(raw_fields, list) else []
        except Exception:
            pass

    from server.app.core.template_compiler import find_unreviewed_ai_items
    unreviewed = find_unreviewed_ai_items(ver.editor_json, fields)
    if unreviewed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "UNREVIEWED_AI_CONTENT",
                "message": f"Cannot publish template: contains {len(unreviewed)} unreviewed AI-suggested item(s). Please review all AI-suggested content before publishing.",
                "unreviewed_items": unreviewed,
            },
        )

    if not ver.validation_report or not ver.validation_report.get("is_valid"):
        docx_bytes, schema_yaml, report = TemplateCompiler.compile(
            editor_json=ver.editor_json or {"type": "doc", "content": []},
            fields=fields,
            template_meta={"id": tmpl.id, "name": tmpl.name, "category": tmpl.category, "description": tmpl.description},
            club_slug=ctx.club.slug,
            letterhead_cfg=None if ver.letterhead_id else {"banner_placeholder": True},
            design_settings=(ver.editor_json or {}).get("design_settings") if isinstance(ver.editor_json, dict) else None,
        )
        if not report["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "TEMPLATE_VALIDATION_FAILED",
                    "message": "Cannot publish template: validation failed.",
                    "errors": report.get("errors", []),
                },
            )
        rel_key, _ = storage.save_content_addressed("templates", docx_bytes, "docx")
        docx_dest = local_storage.local_path(rel_key)
        ver.docx_storage_key = str(docx_dest)
        ver.schema_yaml = schema_yaml
        ver.validation_report = report

    tmpl.status = "published"
    tmpl.current_version_id = ver.id
    db.commit()
    db.refresh(tmpl)

    log_audit(
        db=db,
        action="template_published",
        entity_type="template",
        entity_id=tmpl.id,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        meta={"version_no": ver.version_no, "template_name": tmpl.name},
    )

    series_key = None
    if ver.schema_yaml:
        try:
            parsed = yaml.safe_load(ver.schema_yaml)
            if isinstance(parsed, dict):
                series_key = parsed.get("numbering", {}).get("series")
        except Exception:
            pass

    return TemplateGalleryItemOut(
        id=tmpl.id,
        slug=tmpl.slug,
        name=tmpl.name,
        description=tmpl.description,
        category=tmpl.category,
        stage=tmpl.stage,
        is_system=False,
        status="published",
        forked_from_template_id=tmpl.forked_from_template_id,
        numbering_series=series_key,
        thumbnail_url=f"/api/v1/clubs/{ctx.club.id}/documents/templates/{tmpl.id}/thumbnail",
        can_fork=False,
        can_edit=True,
    )


@router.post("/templates/{template_id}/review-ai")
def review_ai_template_content(
    template_id: str,
    payload: TemplateReviewAIRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Mark AI-suggested fields and blocks as reviewed by editor/owner."""
    tmpl = db.query(Template).filter(
        (Template.id == template_id) | (Template.slug == template_id)
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.is_system:
        raise HTTPException(status_code=403, detail="System templates cannot be modified")
    if tmpl.club_id != ctx.club.id:
        raise HTTPException(status_code=403, detail="Template belongs to another club")

    ver = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == tmpl.id)
        .order_by(TemplateVersion.version_no.desc())
        .first()
    )
    if not ver:
        raise HTTPException(status_code=404, detail="Template version not found")

    fields = []
    schema_dict = {}
    if ver.schema_yaml:
        try:
            schema_dict = yaml.safe_load(ver.schema_yaml) or {}
            raw_fields = schema_dict.get("fields", [])
            fields = raw_fields if isinstance(raw_fields, list) else []
        except Exception:
            pass

    from server.app.core.template_compiler import clear_ai_suggested_flags, find_unreviewed_ai_items
    new_editor, new_fields = clear_ai_suggested_flags(
        editor_json=ver.editor_json,
        fields=fields,
        review_all=payload.all,
        field_keys=payload.field_keys,
        block_indices=payload.block_indices,
    )

    ver.editor_json = new_editor
    if schema_dict:
        schema_dict["fields"] = new_fields
        ver.schema_yaml = yaml.dump(schema_dict, sort_keys=False)

    db.commit()
    db.refresh(ver)

    remaining = find_unreviewed_ai_items(ver.editor_json, new_fields)
    return {
        "reviewed": True,
        "remaining_unreviewed_count": len(remaining),
        "unreviewed_items": remaining,
    }


@router.get("/assets/{asset_id}/content")
def get_asset_content(
    asset_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Serve a system asset or an asset owned by the active club."""
    asset = get_asset_for_club(db, asset_id, ctx.club.id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    try:
        active_storage = get_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if isinstance(active_storage, LocalDiskStorage):
        f_path = active_storage.local_path(asset.storage_key)
        if not f_path.is_file():
            raise HTTPException(status_code=404, detail="Asset file not found on storage")
        return FileResponse(str(f_path), media_type=asset.mime)
    try:
        return Response(content=active_storage.load(asset.storage_key), media_type=asset.mime)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Asset file not found on storage")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))



@router.get("/templates/{template_id}/schema", response_model=TemplateDetailOut)
def get_template_schema_and_defaults(
    template_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Retrieve template schema fields and live club defaults for form generation."""
    tmpl_row = db.query(Template).filter(
        ((Template.id == template_id) | (Template.slug == template_id)),
        ((Template.club_id.is_(None)) | (Template.club_id == ctx.club.id)),
    ).first()
    schema = None
    if tmpl_row:
        tmpl_ver = None
        if tmpl_row.current_version_id:
            tmpl_ver = db.query(TemplateVersion).filter(TemplateVersion.id == tmpl_row.current_version_id).first()
        if not tmpl_ver:
            tmpl_ver = (
                db.query(TemplateVersion)
                .filter(TemplateVersion.template_id == tmpl_row.id)
                .order_by(TemplateVersion.version_no.desc())
                .first()
            )
        if tmpl_ver and tmpl_ver.schema_yaml:
            s_dict = yaml.safe_load(tmpl_ver.schema_yaml)
            schema = TemplateSchema(**s_dict)
        elif (Path("templates") / tmpl_row.slug / "schema.yaml").exists():
            schema = load_schema(tmpl_row.slug)

    if not schema:
        try:
            schema = load_schema(template_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "TEMPLATE_NOT_FOUND", "message": f"Template '{template_id}' not found: {e}"},
            )

    venue_repo = ScopedRepository(db, Venue, club_id=ctx.club.id)
    venues = venue_repo.all()
    venue_list = [
        {
            "name": v.name,
            "short_name": v.short_name,
            "addressee": v.addressee_default or default_addressee(ctx.club),
        }
        for v in venues
    ]

    suggested_ref = get_suggested_ref_no(db, ctx.club, schema)
    today_formatted = date.today().strftime("%d/%m/%Y")

    defaults: dict[str, Any] = {
        "document_date": today_formatted,
        "suggested_ref_no": suggested_ref,
        "ref_no": suggested_ref,
        "organizers": ctx.club.name,
        "mode": "Offline",
        "venues": venue_list,
        "default_venue": venue_list[0]["name"] if venue_list else "Seminar Hall",
        "default_addressee": venue_list[0]["addressee"] if venue_list else default_addressee(ctx.club),
        "academic_year": ctx.club.academic_year_default,
    }

    fields_out = []
    academic_year = ctx.club.academic_year_default or (ctx.club.settings or {}).get("academic_year") or ""
    short_year = compute_short_year(academic_year)
    db_config = build_club_config_from_db(db, ctx.club.slug)

    for f in schema.fields:
        ask_text = f.ask
        if ask_text:
            ask_text = ask_text.replace("{academic_year}", academic_year).replace("{short_year}", short_year).replace("{next}", "001")

        default_val = None
        default_src = None
        if f.default_from:
            parts = f.default_from.split(".")
            val: Any = db_config
            for part in parts[1:]:
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    val = getattr(val, part, None) if hasattr(val, part) else None

            if f.key == "submitted_to" and isinstance(val, dict):
                first_v = next(iter(val.values()), None)
                if first_v:
                    val = getattr(first_v, "default_addressee", None) or getattr(first_v, "addressee", None) or (first_v.get("addressee") if isinstance(first_v, dict) else None)
                if not val:
                    val = defaults.get("default_addressee") or default_addressee(ctx.club)

            if val is not None and not isinstance(val, (dict, list)):
                default_val = str(val)
                default_src = "club_settings"
                defaults[f.key] = val

        fields_out.append(
            TemplateFieldOut(
                key=f.key,
                type=f.type,
                required=bool(f.required),
                defer_ok=bool(f.defer_ok),
                ask=ask_text,
                default_value=default_val,
                default_source=default_src,
                source_allowed=f.source_allowed,
                values=f.values,
            )
        )

    return TemplateDetailOut(
        id=schema.id,
        name=schema.name,
        description=schema.description,
        stage=schema.stage,
        fields=fields_out,
        defaults=defaults,
        numbering_series=schema.numbering.series if schema.numbering else None,
        confirm_numbering=bool(schema.numbering.confirm) if (schema.numbering and schema.numbering.confirm) else False,
    )


@router.post("/extract")
def extract_event_from_text(
    payload: ExtractRequest,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Run NLP/regex extraction on natural-language event description."""
    db_config = build_club_config_from_db(db, ctx.club.slug)
    extractor = EventExtractor(config=db_config)
    event_record = extractor.extract_from_text(payload.text)

    # Detect missing fields against pre-event schemas
    all_schemas = load_all_schemas()
    relevant_schemas = [s for s in all_schemas.values() if s.stage == "pre_event"]
    missing_report = detect_missing_fields(event_record, relevant_schemas)

    extracted_dict = event_record.flat_dict()
    # Mark extracted fields provenance
    provenance = {}
    for k, v in extracted_dict.items():
        if v is not None:
            provenance[k] = {
                "source": "AI-drafted, review",
                "confirmed": False,
            }

    return {
        "extracted_data": extracted_dict,
        "provenance": provenance,
        "missing_fields": [
            {
                "key": m.key,
                "ask": m.ask,
                "documents": m.documents,
                "required": m.required,
            }
            for m in missing_report.missing
        ],
    }


@router.post("/generate", response_model=DocumentDetailOut)
def generate_document(
    payload: GenerateDocumentRequest,
    request: Request,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Generate DOCX & PDF using official Docgen engine and LibreOffice."""
    club_id = ctx.club.id
    tmpl_slug = payload.template_id
    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # 1. Verify template exists & load schema
    tmpl = db.query(Template).filter(
        ((Template.id == tmpl_slug) | (Template.slug == tmpl_slug)),
        ((Template.club_id.is_(None)) | (Template.club_id == club_id)),
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"Template '{tmpl_slug}' not found")

    tmpl_version = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == tmpl.id)
        .order_by(TemplateVersion.version_no.desc())
        .first()
    )
    if not tmpl_version:
        raise HTTPException(status_code=404, detail=f"Template '{tmpl_slug}' has no published version")

    if tmpl_version.schema_yaml:
        s_data = yaml.safe_load(tmpl_version.schema_yaml)
        tmpl_schema = TemplateSchema(**s_data)
    else:
        tmpl_schema = load_schema(tmpl.slug)

    # Whitelist identifiers: validate event_data keys and schema field keys on render (reject with 422)
    try:
        from server.app.core.template_compiler import validate_identifier
        for k in payload.event_data.keys():
            validate_identifier(k, "Event data field")
        if tmpl_schema and tmpl_schema.fields:
            for f in tmpl_schema.fields:
                validate_identifier(f.key, "Schema field")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    # 2. Strict AI draft guard: reject if any field contains literal draft badge or is unconfirmed
    for k, v in payload.event_data.items():
        if isinstance(v, str) and "[AI-drafted" in v:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "UNCONFIRMED_AI_DRAFT",
                    "message": f"Field '{k}' contains unconfirmed AI draft. Please accept or edit before generating.",
                },
            )

    # 3. Process fields with ZERO silent defaults
    data = payload.event_data.copy()
    event_name_val = data.get("event_name") or payload.title or data.get("title")

    # Only document_date may default to today (flagged defaulted/config)
    doc_date = data.get("document_date") or date.today().strftime("%d/%m/%Y")
    doc_date_source = FieldSource.user if data.get("document_date") else FieldSource.config

    ref_no = payload.ref_no or data.get("ref_no") or None

    submitted_to_raw = data.get("submitted_to")
    if isinstance(submitted_to_raw, dict):
        v_name = data.get("venue")
        if v_name and v_name in submitted_to_raw:
            v_cand = submitted_to_raw[v_name]
            submitted_to_raw = getattr(v_cand, "default_addressee", None) or (v_cand.get("addressee") if isinstance(v_cand, dict) else None)
        else:
            v_cand = next(iter(submitted_to_raw.values()), None)
            submitted_to_raw = (getattr(v_cand, "default_addressee", None) or (v_cand.get("addressee") if isinstance(v_cand, dict) else None)) if v_cand else None
    if not submitted_to_raw and data.get("default_addressee"):
        submitted_to_raw = data.get("default_addressee")
    if not submitted_to_raw and data.get("venue"):
        v_obj = db.query(Venue).filter(Venue.club_id == club_id, Venue.name == data.get("venue")).first()
        if not v_obj:
            v_obj = db.query(Venue).filter(Venue.name == data.get("venue")).first()
        if v_obj and getattr(v_obj, "addressee_default", None):
            submitted_to_raw = v_obj.addressee_default

    def user_field(val: Any, key: str) -> TrackedField:
        if val is None or str(val).strip() == "":
            return TrackedField(value=None, source=FieldSource.user, confirmed=False)
        if "[AI-drafted" in str(val):
            return TrackedField(value=val, source=FieldSource.llm_draft, confirmed=False)
        return TrackedField(value=val, source=FieldSource.user, confirmed=True)

    event = EventRecord(
        event_name=user_field(event_name_val, "event_name"),
        event_code=user_field(data.get("event_code"), "event_code"),
        ref_no=TrackedField(value=ref_no, source=FieldSource.user, confirmed=True if ref_no else False),
        room_ref_no=TrackedField(value=ref_no, source=FieldSource.user, confirmed=True if ref_no else False),
        document_date=TrackedField(value=doc_date, source=doc_date_source, confirmed=True),
        submitted_to=user_field(submitted_to_raw, "submitted_to"),
        venue=user_field(data.get("venue"), "venue"),
        dates=user_field(data.get("dates") or data.get("date_start"), "dates"),
        date_start=user_field(data.get("date_start") or data.get("dates"), "date_start"),
        date_end=user_field(data.get("date_end") or data.get("date_start") or data.get("dates"), "date_end"),
        time_start=user_field(data.get("time_start"), "time_start"),
        time_end=user_field(data.get("time_end"), "time_end"),
        description=user_field(data.get("description"), "description"),
        objectives=user_field(data.get("objectives"), "objectives"),
        expected_participants=TrackedField(
            value=int(data["expected_participants"]) if data.get("expected_participants") else None,
            source=FieldSource.user,
            confirmed=True if data.get("expected_participants") else False,
        ),
        category=user_field(data.get("category"), "category"),
        event_type=user_field(data.get("event_type"), "event_type"),
        target_audience=user_field(data.get("target_audience"), "target_audience"),
        mode=(
            user_field(data.get("mode"), "mode")
            if data.get("mode")
            else TrackedField(value=ctx.club.settings.get("defaults", {}).get("mode", "Offline"), source=FieldSource.config, confirmed=True)
        ),
        organizers=TrackedField(value=data.get("organizers") or ctx.club.name, source=FieldSource.config, confirmed=True),
        academic_year=TrackedField(value=ctx.club.academic_year_default, source=FieldSource.config, confirmed=True),
    )

    # Budget items, winners, and bills strictly from user payload (no synthetic fallback)
    if "budget_items" in data and isinstance(data["budget_items"], list) and data["budget_items"]:
        event.budget_items = [BudgetItem(**b) if isinstance(b, dict) else b for b in data["budget_items"]]
    else:
        event.budget_items = []

    if "winners" in data and isinstance(data["winners"], list) and data["winners"]:
        event.winners = [Winner(**w) if isinstance(w, dict) else w for w in data["winners"]]
    elif data.get("winner_name") or data.get("name"):
        bank_data = None
        if any(data.get(k) for k in (
            "winner_bank_name_as_per_bank", "name_as_per_bank",
            "winner_bank_name", "bank_name",
            "winner_bank_branch", "branch",
            "winner_account_no", "account_no",
            "winner_ifsc", "ifsc",
            "winner_pan", "pan",
        )):
            bank_data = BankDetails(
                name_as_per_bank=data.get("winner_bank_name_as_per_bank") or data.get("name_as_per_bank"),
                bank_name=data.get("winner_bank_name") or data.get("bank_name"),
                branch=data.get("winner_bank_branch") or data.get("branch"),
                account_no=data.get("winner_account_no") or data.get("account_no"),
                ifsc=data.get("winner_ifsc") or data.get("ifsc"),
                pan=data.get("winner_pan") or data.get("pan"),
            )
        event.winners = [
            Winner(
                position=data.get("winner_position") or data.get("position"),
                name=data.get("winner_name") or data.get("name"),
                roll_no=data.get("winner_roll_no") or data.get("roll_no") or data.get("admission_no") or ("" if ("winner_roll_no" in payload.deferred_fields or "roll_no" in payload.deferred_fields) else None),
                course_semester=data.get("winner_course_semester") or data.get("course_semester") or ("" if ("winner_course_semester" in payload.deferred_fields or "course_semester" in payload.deferred_fields) else None),
                mobile=data.get("winner_mobile") or data.get("mobile") or ("" if ("winner_mobile" in payload.deferred_fields or "mobile" in payload.deferred_fields) else None),
                amount=data.get("winner_amount") or data.get("amount"),
                bank=bank_data,
            )
        ]
    else:
        event.winners = []

    if "bills" in data and isinstance(data["bills"], list) and data["bills"]:
        event.bills = [BillRecord(**b) if isinstance(b, dict) else b for b in data["bills"]]
    elif data.get("supplier_name") or data.get("invoice_no") or data.get("bill_items"):
        event.bills = [
            BillRecord(
                supplier=SupplierDetails(
                    name=data.get("supplier_name") or None,
                    gst_no=data.get("supplier_gst") or ("" if "supplier_gst" in payload.deferred_fields else None),
                ),
                invoice_no=data.get("invoice_no") or None,
                invoice_date=data.get("invoice_date") or None,
                items=[BillItem(**it) if isinstance(it, dict) else it for it in data.get("bill_items", [])],
                tax_type=data.get("tax_type") or None,
                tax_rate_or_amount=data.get("tax_amount") if data.get("tax_amount") is not None else data.get("tax_rate_or_amount"),
                payment=PaymentDetails(
                    party=data.get("payment_party"),
                    account_no=data.get("payment_account_no"),
                    holder=data.get("payment_holder"),
                    bank=data.get("payment_bank"),
                    branch=data.get("payment_branch"),
                    ifsc=data.get("payment_ifsc"),
                ) if any(data.get(k) for k in ("payment_party", "payment_account_no", "payment_holder", "payment_bank", "payment_branch", "payment_ifsc")) else None,
            )
        ]
    else:
        event.bills = []

    # Standing defaults from club settings or user overrides
    club_defaults = ctx.club.settings.get("defaults", {})
    event.purchase_order = data.get("purchase_order") if data.get("purchase_order") is not None else club_defaults.get("purchase_order", "NiL")
    event.advance = data.get("advance") if data.get("advance") is not None else club_defaults.get("advance", "NiL")
    event.laboratory_office = data.get("laboratory_office") if data.get("laboratory_office") is not None else club_defaults.get("laboratory_office", "Student Council")

    if tmpl_schema.stage == "meeting" or "meeting_title" in data or "agenda_items" in data:
        event.meeting = MeetingBlock(
            title=data.get("meeting_title") or event.event_name.value,
            ref_no=ref_no,
            date=data.get("meeting_date") or doc_date,
            start_time=data.get("meeting_start_time") or data.get("time_start"),
            end_time=data.get("meeting_end_time") or data.get("time_end"),
            venue=data.get("venue"),
            mode=data.get("mode", "Offline"),
            chaired_by=data.get("chaired_by"),
            attendees=[(it if isinstance(it, str) else it.get("name", str(it))) for it in data.get("attendees", [])],
            absentees=[(it if isinstance(it, str) else it.get("name", str(it))) for it in data.get("absentees", [])],
            agenda_items=[AgendaItem(**it) if isinstance(it, dict) else it for it in data.get("agenda_items", [])],
            action_items=[ActionItem(**it) if isinstance(it, dict) else it for it in data.get("action_items", [])],
            prepared_by=data.get("prepared_by"),
            approved_by=data.get("approved_by"),
        )

    # Populate custom fields from data on event so detect_missing_fields and flat_dict find them
    for k, v in data.items():
        if not hasattr(event, k):
            setattr(event, k, user_field(v, k))

    # 4. Check existing Event for shared context linking:
    # "Bill Certificate and Bill Summary take approval note number & date
    # from the Approval Note document of the SAME event. If none exists, ask the user."
    event_repo = ScopedRepository(db, Event, club_id=club_id)
    doc_repo = ScopedRepository(db, Document, club_id=club_id)
    event_row = None
    if payload.event_id:
        event_row = event_repo.get(payload.event_id)
    elif event.event_name.value:
        event_row = event_repo.find_first(Event.title == event.event_name.value)

    if tmpl_schema.depends_on:
        appr_doc = None
        if event_row:
            dep_tmpls = db.query(Template).filter(Template.slug.in_(tmpl_schema.depends_on)).all()
            dep_ids = [t.id for t in dep_tmpls]
            if dep_ids:
                appr_doc = doc_repo.find_first(
                    Document.event_id == event_row.id,
                    Document.template_id.in_(dep_ids),
                )
        if appr_doc:
            appr_ver = (
                db.query(DocumentVersion)
                .filter(DocumentVersion.document_id == appr_doc.id)
                .order_by(DocumentVersion.version_no.desc())
                .first()
            )
            appr_date = (
                appr_ver.record_snapshot.get("document_date")
                if (appr_ver and appr_ver.record_snapshot)
                else appr_doc.created_at.strftime("%d/%m/%Y")
            )
            event.approval_note = ApprovalNote(no=appr_doc.ref_no, date=appr_date)
            data["approval_note_no"] = appr_doc.ref_no
            data["approval_note_date"] = appr_date
        elif data.get("approval_note_no") and data.get("approval_note_date"):
            event.approval_note = ApprovalNote(no=data["approval_note_no"], date=data["approval_note_date"])
        else:
            # Leave None so detect_missing_fields reports it to the user!
            event.approval_note = None

    # 5. Missing Fields Detection: block generation on required fields
    report = detect_missing_fields(event, [tmpl_schema])
    deferred_set = set(payload.deferred_fields)

    blockers = [
        m for m in report.missing
        if m.required and not (m.defer_ok and m.key in deferred_set)
    ]
    if blockers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "MISSING_REQUIRED_FIELDS",
                "message": f"Cannot generate document: {len(blockers)} required field(s) missing.",
                "missing": [
                    {"key": m.key, "ask": m.ask, "defer_ok": m.defer_ok}
                    for m in blockers
                ],
            },
        )

    unconfirmed_blockers = [
        m for m in report.unconfirmed
        if m.required and m.key not in payload.confirmed_fields
    ]
    if unconfirmed_blockers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNCONFIRMED_FIELDS",
                "message": f"Field '{unconfirmed_blockers[0].key}' is unconfirmed. Review and confirm before generating.",
                "unconfirmed": [
                    {"key": m.key, "ask": m.ask}
                    for m in unconfirmed_blockers
                ],
            },
        )

    # 6. Strict Reference Number Reservation & Confirmation Guard
    reservation = None
    if tmpl_schema.numbering:
        expected_series = tmpl_schema.numbering.series or data.get("event_code") or "EVENT"
        if not payload.reservation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "RESERVATION_REQUIRED",
                    "message": f"Template '{tmpl_schema.name}' requires a reference number reservation. Please reserve a number first.",
                },
            )
        res_repo = ScopedRepository(db, NumberReservation, club_id=club_id)
        reservation = res_repo.get(payload.reservation_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "RESERVATION_NOT_FOUND",
                    "message": "Reference number reservation not found.",
                },
            )
        if reservation.user_id != ctx.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "RESERVATION_FORBIDDEN",
                    "message": "Reference number reservation belongs to another user.",
                },
            )
        allowed_series = {expected_series}
        if tmpl_schema.numbering and tmpl_schema.numbering.series:
            allowed_series.add(tmpl_schema.numbering.series)
        if tmpl_schema.id:
            allowed_series.add(tmpl_schema.id)
        if reservation.series_key not in allowed_series:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "SERIES_MISMATCH",
                    "message": f"Reservation series '{reservation.series_key}' does not match template series '{expected_series}'.",
                },
            )
        if reservation.status != "reserved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "RESERVATION_ALREADY_USED",
                    "message": f"Reservation is already {reservation.status}.",
                },
            )
        if reservation.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "RESERVATION_EXPIRED",
                    "message": "Reference number reservation has expired (>30 minutes).",
                },
            )

        raw_ref = payload.ref_no or data.get("ref_no")
        if raw_ref and raw_ref.strip() != reservation.ref_no.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_REF_NO",
                    "message": f"Typed reference number '{raw_ref}' does not match reserved number '{reservation.ref_no}'.",
                },
            )

        ref_no = reservation.ref_no
        if hasattr(event, "meeting") and event.meeting:
            event.meeting.ref_no = ref_no
    else:
        ref_no = None

    # 7. Create or update Event record with JSON-safe dictionary
    clean_record = json.loads(json.dumps(event.flat_dict(), default=str))
    if not event_row and event.event_name.value:
        event_row = Event(
            id=str(uuid.uuid4()),
            club_id=club_id,
            title=event.event_name.value,
            event_code=event.event_code.value,
            record=clean_record,
            created_by=ctx.user.id,
            status="active",
        )
        db.add(event_row)
        db.flush()
    elif event_row:
        cur_rec = dict(event_row.record or {})
        for k, v in clean_record.items():
            if v is not None and v != "" and v != []:
                cur_rec[k] = v
        event_row.record = cur_rec

    # 8. Create Document record
    doc_repo = ScopedRepository(db, Document, club_id=club_id)
    doc_record = doc_repo.create(
        event_id=event_row.id if event_row else None,
        template_id=tmpl.id,
        template_version_id=tmpl_version.id,
        title=payload.title or event_name_val or f"{tmpl.name} Document",
        ref_no=ref_no,
        status="ready",
        created_by=ctx.user.id,
    )

    if reservation:
        reservation.status = "used"
        reservation.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
        reservation.document_id = doc_record.id
        db.flush()

    # 4. Render via Docgen Engine
    out_dir = local_storage.base_dir / "documents" / doc_record.id / "v1"
    out_dir.mkdir(parents=True, exist_ok=True)

    db_config = build_club_config_from_db(db, ctx.club.slug)
    db_source = DatabaseTemplateSource(db)
    renderer = Renderer(config=db_config, template_source=db_source, outputs_dir=out_dir)

    extra_ctx: dict[str, Any] = {}
    extra_ctx.update(data)
    if tmpl_slug == "prize_money_receipt":
        if event.winners:
            w0 = event.winners[0]
            extra_ctx["winner"] = w0
            from docgen.functions import fn_amount_in_words_inr
            amt = getattr(w0, "amount", None) or (w0.get("amount") if isinstance(w0, dict) else 0)
            if amt:
                try:
                    extra_ctx["amount_in_words"] = fn_amount_in_words_inr(amt)
                except Exception:
                    pass
        elif data.get("winner_amount") or data.get("winner_name"):
            from docgen.functions import fn_amount_in_words_inr
            amt = data.get("winner_amount") or 0
            if amt:
                try:
                    extra_ctx["amount_in_words"] = fn_amount_in_words_inr(amt)
                except Exception:
                    pass

    render_result = renderer.render(
        template_id=tmpl_slug,
        event=event,
        extra_context=extra_ctx,
        output_dir=out_dir,
        convert_pdf=True,
    )

    docx_path = render_result.docx_path
    pdf_path = render_result.pdf_path

    # 5. Previews are served on-demand via get_document_page_preview (100 dpi JPEG)
    try:
        pdf_doc = pymupdf.open(str(pdf_path))
        page_count = len(pdf_doc)
        pdf_doc.close()
    except Exception:
        page_count = 1

    page_urls = [
        f"/api/v1/clubs/{club_id}/documents/{doc_record.id}/pages/{idx + 1}?v=1"
        for idx in range(page_count)
    ]

    # 6. Save DocumentVersion
    ver_record = DocumentVersion(
        id=str(uuid.uuid4()),
        document_id=doc_record.id,
        template_version_id=tmpl_version.id,
        version_no=1,
        record_snapshot=json.loads(json.dumps(event.flat_dict(), default=str)),
        overrides={},
        docx_key=str(docx_path),
        pdf_key=str(pdf_path),
        created_by=ctx.user.id,
        source="generated",
    )
    db.add(ver_record)
    doc_record.current_version_id = ver_record.id
    prune_document_versions(db, doc_record.id)

    db.commit()

    # Log audit event
    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="document_generated",
        entity_type="document",
        entity_id=doc_record.id,
        club_id=club_id,
        user_id=ctx.user.id,
        meta={"template": tmpl_slug, "ref_no": ref_no, "version": 1},
        ip=client_ip,
    )

    return DocumentDetailOut(
        id=doc_record.id,
        club_id=club_id,
        template_id=tmpl_slug,
        title=doc_record.title,
        ref_no=doc_record.ref_no,
        status=doc_record.status,
        created_at=doc_record.created_at,
        current_version_no=1,
        page_count=page_count,
        docx_url=f"/api/v1/clubs/{club_id}/documents/{doc_record.id}/download?format=docx",
        pdf_url=f"/api/v1/clubs/{club_id}/documents/{doc_record.id}/download?format=pdf",
        page_images=page_urls,
        versions=[
            DocumentVersionOut(
                id=ver_record.id,
                version_no=1,
                docx_available=docx_path.exists(),
                pdf_available=pdf_path.exists(),
                created_at=ver_record.created_at,
                created_by=ctx.user.name,
            )
        ],
        record_snapshot=event.flat_dict(),
    )


class DocumentListItemOut(BaseModel):
    id: str
    club_id: str
    template_id: str
    template_slug: str
    template_name: str
    event_id: Optional[str] = None
    event_title: Optional[str] = None
    title: str
    ref_no: Optional[str] = None
    status: str
    created_at: datetime
    created_by: Optional[str] = None
    current_version_no: int
    page_count: int = 1
    docx_url: str
    pdf_url: str


class DocumentListResponse(BaseModel):
    items: list[DocumentListItemOut]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get("", response_model=DocumentListResponse)
def list_documents(
    q: Optional[str] = Query(None, description="Search term for title or reference number"),
    template_id: Optional[str] = Query(None, description="Filter by template id or slug"),
    status: Optional[str] = Query(None, description="Filter by status"),
    event_id: Optional[str] = Query(None, description="Filter by event id"),
    date_from: Optional[date] = Query(None, description="Filter documents created on or after date"),
    date_to: Optional[date] = Query(None, description="Filter documents created on or before date"),
    sort_by: str = Query("created_at", description="Field to sort by: created_at, title, ref_no, status"),
    sort_order: str = Query("desc", description="Sort direction: asc or desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """List documents for the active club with search, filtering, sorting, and pagination."""
    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    ev_repo = ScopedRepository(db, Event, club_id=ctx.club.id)

    filters = []
    # Search filter
    if q and q.strip():
        term = f"%{q.strip()}%"
        filters.append((Document.title.ilike(term)) | (Document.ref_no.ilike(term)))

    # Template filter
    if template_id and template_id.strip():
        tmpl_match = (
            db.query(Template)
            .filter((Template.id == template_id.strip()) | (Template.slug == template_id.strip()))
            .first()
        )
        if tmpl_match:
            filters.append(Document.template_id == tmpl_match.id)
        else:
            filters.append(Document.template_id == template_id.strip())

    # Status filter
    if status and status.strip():
        filters.append(Document.status == status.strip())

    # Event filter
    if event_id and event_id.strip():
        filters.append(Document.event_id == event_id.strip())

    # Date range filters
    if date_from:
        start_dt = datetime.combine(date_from, datetime.min.time())
        filters.append(Document.created_at >= start_dt)
    if date_to:
        end_dt = datetime.combine(date_to, datetime.max.time())
        filters.append(Document.created_at <= end_dt)

    # Sorting
    sort_col = Document.created_at
    if sort_by == "title":
        sort_col = Document.title
    elif sort_by == "ref_no":
        sort_col = Document.ref_no
    elif sort_by == "status":
        sort_col = Document.status

    if sort_order.lower() == "asc":
        order_clause = sort_col.asc()
    else:
        order_clause = sort_col.desc()

    total = doc_repo.count(*filters)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    offset = (page - 1) * page_size
    docs = doc_repo.list(skip=offset, limit=page_size, filters=filters, order_by=order_clause)

    items: list[DocumentListItemOut] = []
    for d in docs:
        tmpl = db.query(Template).filter(Template.id == d.template_id).first()
        ev = ev_repo.get(d.event_id) if d.event_id else None
        latest_ver = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == d.id)
            .order_by(DocumentVersion.version_no.desc())
            .first()
        )
        v_no = latest_ver.version_no if latest_ver else 1

        # Check page preview count
        preview_dir = local_storage.base_dir / "previews" / d.id / f"v{v_no}"
        page_count = 1
        if preview_dir.exists():
            pngs = list(preview_dir.glob("page_*.png"))
            if pngs:
                page_count = len(pngs)

        items.append(
            DocumentListItemOut(
                id=d.id,
                club_id=d.club_id,
                template_id=d.template_id,
                template_slug=tmpl.slug if tmpl else "document",
                template_name=tmpl.name if tmpl else "Document",
                event_id=d.event_id,
                event_title=ev.title if ev else None,
                title=d.title,
                ref_no=d.ref_no,
                status=d.status,
                created_at=d.created_at,
                created_by=d.created_by,
                current_version_no=v_no,
                page_count=page_count,
                docx_url=f"/api/v1/clubs/{ctx.club.id}/documents/{d.id}/download?format=docx",
                pdf_url=f"/api/v1/clubs/{ctx.club.id}/documents/{d.id}/download?format=pdf",
            )
        )

    return DocumentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/batch/{batch_id}/download-zip")
def download_batch_zip(
    batch_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Download ZIP archive of batch-generated documents with cross-club protection and on-demand regeneration."""
    import time
    import zipfile
    from server.app.core.storage import BATCH_TTL_HOURS

    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    audit_repo = ScopedRepository(db, AuditLog, club_id=ctx.club.id)
    audit_entries = audit_repo.all(AuditLog.action == "documents_batch_generated")
    matching_log = next(
        (l for l in audit_entries if l.meta and l.meta.get("batch_id") == batch_id),
        None,
    )
    if not matching_log:
        raise HTTPException(
            status_code=404,
            detail="Batch archive not found or access denied for this club.",
        )

    zip_filename = Path(
        matching_log.meta.get("zip_filename") or f"batch_{batch_id[:8]}_documents.zip"
    ).name
    cache_dir = local_storage.base_dir / "cache" / "batches" / batch_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / zip_filename

    # Also check legacy location if present
    legacy_zip = local_storage.base_dir / "batches" / batch_id / zip_filename

    ttl_seconds = BATCH_TTL_HOURS * 3600
    if zip_path.exists() and (time.time() - zip_path.stat().st_mtime) <= ttl_seconds:
        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename=zip_filename,
            headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
        )
    elif legacy_zip.exists():
        return FileResponse(
            path=legacy_zip,
            media_type="application/zip",
            filename=zip_filename,
            headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
        )

    # Build ZIP on demand from generated documents without duplicate copies
    meta_docs = matching_log.meta.get("documents", [])
    files_to_zip = []
    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    for d_info in meta_docs:
        d_id = d_info.get("id")
        if not d_id or not doc_repo.get(d_id):
            continue
        clean_ref = (d_info.get("ref_no") or "doc").replace("/", "_")
        clean_title = (d_info.get("title") or "document").replace(" ", "_").replace("/", "_")
        base_name = f"{clean_ref}_{clean_title}"
        doc_v = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == d_id)
            .order_by(DocumentVersion.version_no.desc())
            .first()
        )
        if doc_v:
            # Through storage, so moved or remote-backed files are found too
            for key, ext in ((doc_v.docx_key, "docx"), (doc_v.pdf_key, "pdf")):
                if not key:
                    continue
                try:
                    src = local_storage.local_path(key)
                except ValueError:
                    continue
                if src.exists():
                    files_to_zip.append((src, f"{base_name}.{ext}"))

    if not files_to_zip:
        raise HTTPException(status_code=404, detail="Batch documents not available on storage.")

    with zipfile.ZipFile(str(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arcname in files_to_zip:
            zf.write(str(src), arcname=arcname)

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=zip_filename,
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )


@router.get("/{doc_id}", response_model=DocumentDetailOut)
def get_document_details(
    doc_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Retrieve document details, version history, and review preview image URLs."""
    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    doc_record = doc_repo.get(doc_id)
    if not doc_record:
        raise HTTPException(status_code=404, detail="Document not found")

    versions = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version_no.desc())
        .all()
    )
    if not versions:
        raise HTTPException(status_code=404, detail="Document has no generated versions")

    latest_ver = versions[0]
    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    page_count = 1
    latest_pdf = local_storage.local_path(latest_ver.pdf_key) if latest_ver.pdf_key else None
    if latest_pdf and latest_pdf.exists():
        try:
            import pymupdf
            pdf_doc = pymupdf.open(str(latest_pdf))
            page_count = len(pdf_doc)
            pdf_doc.close()
        except Exception:
            page_count = 1

    page_urls = [
        f"/api/v1/clubs/{ctx.club.id}/documents/{doc_id}/pages/{p}?v={latest_ver.version_no}"
        for p in range(1, page_count + 1)
    ]

    tmpl = db.query(Template).filter(Template.id == doc_record.template_id).first()
    tmpl_slug = tmpl.slug if tmpl else "document"
    author_ids = {v.created_by for v in versions if v.created_by}
    authors = {u.id: u.name for u in db.query(User).filter(User.id.in_(author_ids)).all()} if author_ids else {}

    return DocumentDetailOut(
        id=doc_record.id,
        club_id=ctx.club.id,
        template_id=tmpl_slug,
        title=doc_record.title,
        ref_no=doc_record.ref_no,
        status=doc_record.status,
        created_at=doc_record.created_at,
        current_version_no=latest_ver.version_no,
        page_count=page_count,
        docx_url=f"/api/v1/clubs/{ctx.club.id}/documents/{doc_record.id}/download?format=docx",
        pdf_url=f"/api/v1/clubs/{ctx.club.id}/documents/{doc_record.id}/download?format=pdf",
        page_images=page_urls,
        versions=[
            DocumentVersionOut(
                id=v.id,
                version_no=v.version_no,
                docx_available=bool(v.docx_key and local_storage.local_path(v.docx_key).exists()),
                pdf_available=bool(v.pdf_key and local_storage.local_path(v.pdf_key).exists()),
                created_at=v.created_at,
                created_by=(authors.get(v.created_by) if v.created_by else None) or "Generated",
                change_summary=v.diff_summary,
            )
            for v in versions
        ],
        record_snapshot=latest_ver.record_snapshot,
        editable_fields=workflow.editable_fields(db, doc_record),
        activity=workflow.activity(db, doc_record),
        can_edit=ctx.is_editor,
        can_review=ctx.is_admin,
        template_name=tmpl.name if tmpl else None,
    )


@router.get("/{doc_id}/pages/{page_no}")
def get_document_page_preview(
    doc_id: str,
    page_no: int,
    v: int = Query(1),
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Serve on-demand 100 dpi JPEG page preview cached with PREVIEW_TTL_DAYS."""
    import time
    from PIL import Image
    import pymupdf
    from server.app.core.storage import PREVIEW_TTL_DAYS
    from server.app.core.doc_retention import regenerate_document_version

    # Resolve the document before touching any cache path or version row.  The
    # previous implementation authorized the club but queried only by a
    # caller-supplied document id, allowing a member of one club to preview a
    # known document id from another club.
    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    doc_record = doc_repo.get(doc_id)
    if not doc_record:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    cache_dir = local_storage.base_dir / "cache" / "previews"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{doc_id}_v{v}_p{page_no}.jpg"

    ttl_seconds = PREVIEW_TTL_DAYS * 86400
    if cache_file.exists():
        if (time.time() - cache_file.stat().st_mtime) <= ttl_seconds:
            return FileResponse(cache_file, media_type="image/jpeg")
        else:
            cache_file.unlink(missing_ok=True)

    query = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc_record.id,
        DocumentVersion.version_no == v,
    )
    version = query.first()
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")

    pdf_path = None
    if version.pdf_key:
        candidate = local_storage.local_path(version.pdf_key)
        if candidate.exists():
            pdf_path = candidate
    if pdf_path is None:
        # Check if we can regenerate on demand for an older version
        try:
            _, pdf_path = regenerate_document_version(db, doc_id, v, club_id=ctx.club.id)
        except Exception:
            pdf_path = None

    if not pdf_path or not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF source file not found on storage")

    try:
        pdf_doc = pymupdf.open(str(pdf_path))
        if 1 <= page_no <= len(pdf_doc):
            page = pdf_doc[page_no - 1]
            pix = page.get_pixmap(dpi=100)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.save(str(cache_file), format="JPEG", quality=70, optimize=True)
        pdf_doc.close()
    except Exception as e:
        logger.warning("Failed to render preview page: %s", e)

    if not cache_file.exists():
        raise HTTPException(status_code=404, detail="Page preview image not found")
    return FileResponse(cache_file, media_type="image/jpeg")


@router.post("/{doc_id}/versions/{version_no}/recreate")
def recreate_document_version_endpoint(
    doc_id: str,
    version_no: int,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Regenerate physical DOCX and PDF files for an older pruned version on demand."""
    from server.app.core.doc_retention import regenerate_document_version
    try:
        docx_p, pdf_p = regenerate_document_version(
            db, doc_id, version_no, club_id=ctx.club.id
        )
        return {
            "message": f"Version {version_no} re-created successfully.",
            "docx_path": str(docx_p),
            "pdf_path": str(pdf_p),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to re-create version: {e}")


class DocumentReviseRequest(BaseModel):
    changes: dict[str, Any]
    note: Optional[str] = Field(None, max_length=500)


class DocumentReviewAction(BaseModel):
    comment: Optional[str] = Field(None, max_length=2000)


class DocumentEmailRequest(BaseModel):
    to: list[str] = Field(..., min_length=1, max_length=20)
    message: Optional[str] = Field(None, max_length=4000)
    attach: str = Field("pdf", pattern="^(pdf|docx|both)$")


def _club_document(ctx: ClubContext, db: Session, doc_id: str) -> Document:
    doc_record = ScopedRepository(db, Document, club_id=ctx.club.id).get(doc_id)
    if not doc_record:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc_record


@router.post("/rows/parse")
async def parse_rows_endpoint(
    template_id: str = Form(...),
    sheet_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Read rows for a per-row batch from an uploaded CSV or a shared Google Sheet."""
    from server.app.core import sheet_import

    tmpl = db.query(Template).filter(
        (Template.id == template_id) | (Template.slug == template_id),
        (Template.club_id == ctx.club.id) | (Template.is_system == True),  # noqa: E712
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    ver = db.query(TemplateVersion).filter(TemplateVersion.id == tmpl.current_version_id).first()
    schema = yaml.safe_load(ver.schema_yaml) if ver and ver.schema_yaml else {}
    fields = [
        {"key": f["key"], "label": f.get("label") or f["key"].replace("_", " ").title(), "required": bool(f.get("required"))}
        for f in (schema or {}).get("fields", [])
        if isinstance(f, dict) and f.get("key") and f.get("type") != "table"
    ]
    try:
        if file is not None:
            data = await file.read(sheet_import.MAX_BYTES + 1)
            if len(data) > sheet_import.MAX_BYTES:
                raise ValueError("The file is too large (limit 2 MB).")
        elif sheet_url:
            data = sheet_import.fetch_sheet_csv(sheet_url)
        else:
            raise ValueError("Upload a CSV file or paste a Google Sheets link.")
        headers, rows = sheet_import.parse_csv(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read the rows. Check the file or sheet link.")
    return {
        "headers": headers,
        "rows": rows,
        "row_count": len(rows),
        "fields": fields,
        "mapping": sheet_import.suggest_mapping(headers, fields),
    }


@router.post("/{doc_id}/revise")
def revise_document_endpoint(
    doc_id: str,
    payload: DocumentReviseRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Edit field values and regenerate as a new version (same reference number)."""
    doc_record = _club_document(ctx, db, doc_id)
    ver = workflow.revise_document(db, doc_record, ctx.user, payload.changes, payload.note)
    log_audit(db=db, action="document_revised", entity_type="document", entity_id=doc_record.id,
              club_id=ctx.club.id, user_id=ctx.user.id, meta={"version_no": ver.version_no})
    return {"version_no": ver.version_no, "status": doc_record.status, "change_summary": ver.diff_summary}


@router.post("/{doc_id}/submit")
def submit_document_endpoint(
    doc_id: str,
    payload: DocumentReviewAction,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Send the document to the club's reviewers (admins/owners) for approval."""
    doc_record = _club_document(ctx, db, doc_id)
    workflow.submit_for_review(db, doc_record, ctx.user, payload.comment)
    return {"status": doc_record.status}


@router.post("/{doc_id}/approve")
def approve_document_endpoint(
    doc_id: str,
    payload: DocumentReviewAction,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    """Approve: stamps the PDF with the approver and a verification code."""
    doc_record = _club_document(ctx, db, doc_id)
    position = (ctx.membership.position if ctx.membership else None) or ctx.role.title()
    entry = workflow.approve(db, doc_record, ctx.user, f"{position}, {ctx.club.short_name}", payload.comment)
    log_audit(db=db, action="document_approved", entity_type="document", entity_id=doc_record.id,
              club_id=ctx.club.id, user_id=ctx.user.id, meta={"verification_code": entry.verification_code})
    return {"status": doc_record.status, "verification_code": entry.verification_code}


@router.post("/{doc_id}/request-changes")
def request_changes_endpoint(
    doc_id: str,
    payload: DocumentReviewAction,
    ctx: ClubContext = Depends(require_club_access(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    doc_record = _club_document(ctx, db, doc_id)
    workflow.request_changes(db, doc_record, ctx.user, payload.comment or "")
    return {"status": doc_record.status}


@router.post("/{doc_id}/comments")
def comment_document_endpoint(
    doc_id: str,
    payload: DocumentReviewAction,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    doc_record = _club_document(ctx, db, doc_id)
    workflow.add_comment(db, doc_record, ctx.user, payload.comment or "")
    return {"activity": workflow.activity(db, doc_record)}


@router.post("/{doc_id}/email")
def email_document_endpoint(
    doc_id: str,
    payload: DocumentEmailRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Email the latest version (PDF and/or DOCX) to up to 20 recipients."""
    from email.utils import parseaddr

    from server.app.core.email import get_email_sender
    from server.app.core.rate_limit import check_rate_limit

    recipients = []
    for raw in payload.to:
        addr = parseaddr(raw.strip())[1]
        if not addr or "@" not in addr or "." not in addr.split("@")[-1]:
            raise HTTPException(status_code=400, detail=f"Not a valid email address: {raw}")
        recipients.append(addr)
    check_rate_limit(f"email:{ctx.user.id}", max_requests=30, window_seconds=3600, db=db)

    doc_record = _club_document(ctx, db, doc_id)
    ver = workflow.latest_version(db, doc_record)
    storage = require_local_storage()
    attachments = []
    safe_title = re.sub(r"[^A-Za-z0-9 _-]+", "", doc_record.title).strip() or "document"
    wanted = ("pdf", "docx") if payload.attach == "both" else (payload.attach,)
    for kind in wanted:
        key = ver.pdf_key if kind == "pdf" else ver.docx_key
        path = storage.local_path(key) if key else None
        if not path or not path.exists():
            raise HTTPException(status_code=409, detail=f"The {kind.upper()} for this version is not available.")
        mime = "application/pdf" if kind == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        attachments.append((f"{safe_title}.{kind}", path.read_bytes(), mime))

    body = (payload.message or "").strip() or f"Please find attached {doc_record.title}."
    body += f"\n\nRef. No.: {doc_record.ref_no or '-'}\nSent by {ctx.user.name}, {ctx.club.name}"
    get_email_sender().send_document(recipients, f"{doc_record.title} — {ctx.club.name}", body, attachments,
                                     reply_to=ctx.user.email)
    workflow.log_email(db, doc_record, ctx.user, recipients)
    return {"sent_to": recipients}


@router.get("/{doc_id}/download")
def download_document_file(
    doc_id: str,
    format: str = Query("pdf", pattern="^(pdf|docx)$"),
    v: Optional[int] = None,
    disposition: str = Query("attachment", pattern="^(attachment|inline)$"),
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Download generated document in official PDF or editable DOCX format."""
    from server.app.core.doc_retention import regenerate_document_version

    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    doc_record = doc_repo.get(doc_id)
    if not doc_record:
        raise HTTPException(status_code=404, detail="Document not found")

    query = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc_id)
    latest_v = query.order_by(DocumentVersion.version_no.desc()).first()

    if v is not None:
        version = query.filter(DocumentVersion.version_no == v).first()
    else:
        version = latest_v

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    try:
        local_storage = require_local_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    is_latest = (latest_v and version.id == latest_v.id)

    if format == "pdf":
        file_path = local_storage.local_path(version.pdf_key) if version.pdf_key else None
        media_type = "application/pdf"
        filename = f"{doc_record.ref_no or 'document'}.pdf".replace("/", "_")
    else:
        file_path = local_storage.local_path(version.docx_key) if version.docx_key else None
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{doc_record.ref_no or 'document'}.docx".replace("/", "_")

    if not file_path or not file_path.exists():
        if is_latest:
            # Rule: Never regenerate silently on download of the latest version!
            raise HTTPException(status_code=404, detail=f"File not available on storage ({format.upper()})")
        else:
            # Older pruned version: regenerate on demand from immutable template version + snapshot
            docx_p, pdf_p = regenerate_document_version(
                db, doc_id, version.version_no, club_id=ctx.club.id
            )
            file_path = pdf_p if format == "pdf" else docx_p

    disp = "inline" if disposition == "inline" and format == "pdf" else "attachment"
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'{disp}; filename="{filename}"'},
    )


@router.get("/{doc_id}/pdf")
def download_document_pdf(
    doc_id: str,
    v: Optional[int] = None,
    disposition: str = Query("inline", pattern="^(attachment|inline)$"),
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Download or view generated document in official PDF format."""
    return download_document_file(doc_id=doc_id, format="pdf", v=v, disposition=disposition, ctx=ctx, db=db)


@router.get("/{doc_id}/docx")
def download_document_docx(
    doc_id: str,
    v: Optional[int] = None,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Download generated document in editable DOCX format."""
    return download_document_file(doc_id=doc_id, format="docx", v=v, disposition="attachment", ctx=ctx, db=db)


@router.get("/{doc_id}/preview")
def get_document_preview_page1(
    doc_id: str,
    v: int = Query(1),
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Serve high-resolution rasterized PNG page preview of rendered document."""
    return get_document_page_preview(doc_id=doc_id, page_no=1, v=v, ctx=ctx, db=db)


# ---------------------------------------------------------------------------
# Part 5: AI Everywhere Endpoints
# ---------------------------------------------------------------------------

@router.post("/templates/wizard/questions", response_model=WizardQuestionsResponse)
def wizard_questions(
    payload: WizardQuestionsRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
):
    """Propose at most 3 clarifying question chips for template creation."""
    return get_wizard_questions(payload.prompt, club_name=ctx.club.name)


@router.post("/templates/wizard/generate", status_code=status.HTTP_201_CREATED)
def wizard_generate(
    payload: WizardGenerateRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Generate a designed template from wizard prompt and selected answer chips."""
    tmpl, ver = create_wizard_template(
        prompt=payload.prompt,
        answers=payload.answers,
        club_id=ctx.club.id,
        user_id=ctx.user.id,
        db=db,
        numbering_series=payload.numbering_series or "DOC",
    )
    return {
        "template": {
            "id": tmpl.id,
            "slug": tmpl.slug,
            "name": tmpl.name,
            "category": tmpl.category,
            "status": tmpl.status,
            "is_system": False,
        },
        "draft": {
            "template_id": tmpl.id,
            "version_no": ver.version_no,
            "editor_json": ver.editor_json,
            "design_settings": (ver.editor_json or {}).get("design_settings") if isinstance(ver.editor_json, dict) else {},
        },
        "message": f"Designed template '{tmpl.name}' generated successfully via wizard.",
    }


@router.post("/templates/import/text")
def import_text(
    payload: ImportTextRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
):
    """Convert pasted notice/letter text into TipTap document blocks with proposed fields."""
    editor_json, fields, unsupported = convert_text_to_tiptap_with_fields(payload.text)
    name = payload.name or "Imported Document Template"
    return {
        "editor_json": editor_json,
        "fields": fields,
        "name": name,
        "unsupported_elements": unsupported,
    }


@router.post("/templates/import/docx")
async def import_docx(
    file: UploadFile = File(...),
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
):
    """Convert uploaded DOCX into TipTap document blocks with proposed fields and unsupported elements report."""
    max_bytes = 10 * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="The Word file is too large (limit 10 MB).")
    try:
        editor_json, fields, unsupported = convert_docx_to_tiptap_with_fields(content)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this file. Upload a Word document (.docx).")
    base_name = Path(file.filename or "imported.docx").stem.replace("_", " ").title()
    return {
        "editor_json": editor_json,
        "fields": fields,
        "unsupported_elements": unsupported,
        "name": base_name,
    }


@router.post("/improve-text")
def improve_text_endpoint(
    payload: ImproveTextRequest,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
):
    """Improve text description or objectives (formal, proofread, shorten, expand) with before/after diff."""
    mode = payload.mode if payload.mode in ("formal", "proofread", "shorter", "longer") else "formal"
    return core_improve_text(payload.text, mode=mode)


@router.post("/suggest-details")
def suggest_details_endpoint(
    payload: SuggestDetailsRequest,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
):
    """Propose non-official optional fields for event documentation."""
    suggestions = core_suggest_details(
        event_type=payload.event_type,
        club_name=ctx.club.name,
        existing_fields=payload.existing_fields,
    )
    return {"suggestions": suggestions}


@router.post("/templates/{template_id}/check")
def check_template_quality(
    template_id: str,
    payload: CheckDocumentRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Audit template quality, protocol consistency, contrast, and official wording with actionable fixes."""
    template = db.query(Template).filter(
        ((Template.id == template_id) | (Template.slug == template_id)),
        ((Template.club_id.is_(None)) | (Template.club_id == ctx.club.id)),
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    editor_json = payload.editor_json
    fields = payload.fields
    design_settings = payload.design_settings

    if not editor_json:
        ver = db.query(TemplateVersion).filter(TemplateVersion.template_id == template.id).order_by(TemplateVersion.version_no.desc()).first()
        if ver:
            editor_json = ver.editor_json
            design_settings = ver.design_settings
            if ver.schema_yaml:
                try:
                    s_dict = yaml.safe_load(ver.schema_yaml)
                    fields = s_dict.get("fields", []) if isinstance(s_dict, dict) else []
                except Exception:
                    fields = []

    return core_audit_document(editor_json or {}, fields or [], design_settings or {})


@router.post("/templates/{template_id}/translate")
def translate_template(
    template_id: str,
    payload: TranslateTemplateRequest,
    ctx: ClubContext = Depends(require_club_access(Role.EDITOR)),
    db: Session = Depends(get_db),
):
    """Translate template text to Hindi or Gujarati while keeping all field chips 100% intact."""
    template = db.query(Template).filter(
        ((Template.id == template_id) | (Template.slug == template_id)),
        ((Template.club_id.is_(None)) | (Template.club_id == ctx.club.id)),
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    editor_json = payload.editor_json
    if not editor_json:
        ver = db.query(TemplateVersion).filter(TemplateVersion.template_id == template.id).order_by(TemplateVersion.version_no.desc()).first()
        if ver:
            editor_json = ver.editor_json

    target_lang = payload.target_lang if payload.target_lang in ("hi", "gu", "en") else "hi"
    translated_json, design_update = core_translate_content(editor_json or {}, target_lang=target_lang)
    return {
        "editor_json": translated_json,
        "design_settings": design_update,
        "target_lang": target_lang,
    }

