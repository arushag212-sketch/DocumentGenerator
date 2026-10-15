"""Document generation, template schemas, AI extraction, and preview APIs."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pymupdf
import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session


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
from docgen.renderer import Renderer
from docgen.schema import load_all_schemas, load_schema
from docgen.sources import DatabaseTemplateSource, build_club_config_from_db
from server.app.core.audit import log_audit
from server.app.core.database import get_db
from server.app.core.permissions import (
    ClubContext,
    Role,
    get_current_user,
    require_club_access,
)
from server.app.core.scoped_repo import ScopedRepository
from server.app.models import (
    Club,
    Document,
    DocumentVersion,
    Event,
    NumberingSeries,
    NumberReservation,
    Template,
    TemplateVersion,
    User,
    Venue,
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


class DocumentVersionOut(BaseModel):
    id: str
    version_no: int
    docx_available: bool
    pdf_available: bool
    created_at: datetime
    created_by: Optional[str] = None


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
    academic_year = getattr(club, "academic_year_default", None) or "2026-27"
    if hasattr(club, "settings") and isinstance(club.settings, dict):
        academic_year = club.settings.get("academic_year", academic_year)
    short_year = academic_year.split("-")[-1] if "-" in academic_year else academic_year[-2:]
    club_prefix = getattr(club, "short_name", None) or getattr(club, "slug", "ACM").upper()

    series_repo = ScopedRepository(db, NumberingSeries, club_id=club.id)
    ns = series_repo.find_first(
        NumberingSeries.key == series_key,
        NumberingSeries.academic_year == academic_year,
    )
    next_seq = (ns.last_seq + 1) if ns else 1
    fmt = ns.format if (ns and ns.format) else (schema.numbering.format or f"{club_prefix}/{{academic_year}}/{{series}}/{{seq:03d}}")
    return fmt.format(
        academic_year=academic_year,
        short_year=short_year,
        series=series_key,
        event_code=event_code or series_key,
        seq=next_seq,
    )


def allocate_next_sequence(
    db: Session,
    club_id: str,
    series_key: str,
    academic_year: str = "2026-27",
    club_code: str = "ACM",
    format_pattern: Optional[str] = None,
) -> int:
    """Safely increment and return the next sequence number under concurrency.

    Uses `SELECT ... FOR UPDATE` on PostgreSQL or atomic `UPDATE ... RETURNING`
    so that 20 parallel confirmations produce 20 unique, gap-free numbers.
    """
    bind = db.get_bind()
    dialect = getattr(bind.dialect, "name", "")
    series_repo = ScopedRepository(db, NumberingSeries, club_id=club_id)

    if dialect == "postgresql":
        # Row-level lock until transaction commits
        stmt = (
            select(NumberingSeries)
            .where(
                NumberingSeries.club_id == club_id,
                NumberingSeries.key == series_key,
                NumberingSeries.academic_year == academic_year,
            )
            .with_for_update()
        )
        ns = db.scalars(stmt).first()
        if ns:
            ns.last_seq += 1
            db.flush()
            return ns.last_seq

    # Atomic UPDATE ... RETURNING statement for PostgreSQL / SQLite 3.35+
    stmt_upd = (
        update(NumberingSeries)
        .where(
            NumberingSeries.club_id == club_id,
            NumberingSeries.key == series_key,
            NumberingSeries.academic_year == academic_year,
        )
        .values(last_seq=NumberingSeries.last_seq + 1)
        .returning(NumberingSeries.last_seq)
    )
    val = db.execute(stmt_upd).scalar_one_or_none()
    if val is not None:
        db.flush()
        return val

    # If row does not exist yet, find or create
    ns = series_repo.find_first(
        NumberingSeries.key == series_key,
        NumberingSeries.academic_year == academic_year,
    )
    if not ns:
        ns = NumberingSeries(
            club_id=club_id,
            key=series_key,
            format=format_pattern or f"{club_code}/{academic_year}/{series_key}/{{seq:03d}}",
            academic_year=academic_year,
            last_seq=1,
        )
        db.add(ns)
        db.flush()
        return 1

    ns.last_seq += 1
    db.flush()
    return ns.last_seq


# ---------------- ENDPOINTS ----------------



@router.get("/templates/{template_id}/schema", response_model=TemplateDetailOut)
def get_template_schema_and_defaults(
    template_id: str,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Retrieve template schema fields and live club defaults for form generation."""
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
            "addressee": v.addressee_default or "Head of Department, Computer Science & Engineering",
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
        "default_addressee": venue_list[0]["addressee"] if venue_list else "Head of Department, Computer Science & Engineering",
        "academic_year": ctx.club.academic_year_default,
    }

    fields_out = []
    academic_year = ctx.club.academic_year_default or "2026-27"
    short_year = academic_year.split("-")[-1] if "-" in academic_year else academic_year[-2:]
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
                    val = defaults.get("default_addressee", "Head of Department, Computer Science & Engineering")

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

    # Detect missing fields against permission_letter & approval_note
    all_schemas = load_all_schemas()
    relevant_schemas = [s for k, s in all_schemas.items() if k in ("permission_letter", "approval_note")]
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

    # 1. Verify template exists & load schema
    tmpl = db.query(Template).filter(Template.slug == tmpl_slug).first()
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

    tmpl_schema = load_schema(tmpl_slug)

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

    if tmpl_slug == "mom" or "meeting_title" in data or "agenda_items" in data:
        event.meeting = MeetingBlock(
            title=data.get("meeting_title") or event.event_name.value,
            ref_no=ref_no,
            date=data.get("meeting_date") or doc_date,
            start_time=data.get("meeting_start_time") or data.get("time_start"),
            end_time=data.get("meeting_end_time") or data.get("time_end"),
            venue=data.get("venue"),
            mode=data.get("mode", "Offline"),
            chaired_by=data.get("chaired_by"),
            attendees=data.get("attendees", []),
            absentees=data.get("absentees", []),
            agenda_items=[AgendaItem(**it) if isinstance(it, dict) else it for it in data.get("agenda_items", [])],
            action_items=[ActionItem(**it) if isinstance(it, dict) else it for it in data.get("action_items", [])],
            prepared_by=data.get("prepared_by"),
            approved_by=data.get("approved_by"),
        )

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

    if tmpl_slug in ("bill_certificate", "bill_summary"):
        appr_doc = None
        if event_row:
            appr_tmpl = db.query(Template).filter(Template.slug == "approval_note").first()
            if appr_tmpl:
                appr_doc = doc_repo.find_first(
                    Document.event_id == event_row.id,
                    Document.template_id == appr_tmpl.id,
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
        if reservation.series_key != expected_series:
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
        if reservation.expires_at < datetime.utcnow():
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
        reservation.used_at = datetime.utcnow()
        reservation.document_id = doc_record.id
        db.flush()

    # 4. Render via Docgen Engine
    out_dir = Path("storage/documents") / doc_record.id / "v1"
    out_dir.mkdir(parents=True, exist_ok=True)

    db_config = build_club_config_from_db(db, ctx.club.slug)
    db_source = DatabaseTemplateSource(db)
    renderer = Renderer(config=db_config, template_source=db_source, outputs_dir=out_dir)

    extra_ctx: dict[str, Any] = {}
    if tmpl_slug == "prize_money_receipt" and event.winners:
        extra_ctx["winner"] = event.winners[0]
        from docgen.functions import fn_amount_in_words_inr
        extra_ctx["amount_in_words"] = fn_amount_in_words_inr(event.winners[0].amount)

    render_result = renderer.render(
        template_id=tmpl_slug,
        event=event,
        extra_context=extra_ctx,
        output_dir=out_dir,
        convert_pdf=True,
    )

    docx_path = render_result.docx_path
    pdf_path = render_result.pdf_path

    # 5. Generate high-res page preview PNGs using PyMuPDF
    preview_dir = Path("storage/previews") / doc_record.id / "v1"
    preview_dir.mkdir(parents=True, exist_ok=True)
    page_urls: list[str] = []

    pdf_doc = pymupdf.open(str(pdf_path))
    page_count = len(pdf_doc)
    for idx, page in enumerate(pdf_doc):
        pix = page.get_pixmap(dpi=150)
        img_dest = preview_dir / f"page_{idx + 1}.png"
        pix.save(str(img_dest))
        page_urls.append(f"/api/v1/clubs/{club_id}/documents/{doc_record.id}/pages/{idx + 1}?v=1")

    # 6. Save DocumentVersion
    ver_record = DocumentVersion(
        id=str(uuid.uuid4()),
        document_id=doc_record.id,
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

    # 7. Increment Numbering counter if confirmed (concurrency-safe)
    if payload.ref_no_confirmed:
        if tmpl_slug == "permission_letter":
            allocate_next_sequence(db, club_id, "ROOM", "2026-27")
        elif tmpl_slug == "mom":
            allocate_next_sequence(db, club_id, "MOM", "2026-27")
        else:
            series_repo = ScopedRepository(db, NumberingSeries, club_id=club_id)
            ns = series_repo.find_first(
                NumberingSeries.key.in_(["approval_note", "event_approval"]),
                NumberingSeries.academic_year == "2026-27",
            )
            s_key = ns.key if ns else "approval_note"
            allocate_next_sequence(db, club_id, s_key, "2026-27")

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
    preview_dir = Path("storage/previews") / doc_id / f"v{latest_ver.version_no}"
    page_urls = []
    if preview_dir.exists():
        page_files = sorted(preview_dir.glob("page_*.png"), key=lambda p: int(p.stem.split("_")[1]))
        page_urls = [
            f"/api/v1/clubs/{ctx.club.id}/documents/{doc_id}/pages/{p.stem.split('_')[1]}?v={latest_ver.version_no}"
            for p in page_files
        ]

    tmpl = db.query(Template).filter(Template.id == doc_record.template_id).first()
    tmpl_slug = tmpl.slug if tmpl else "document"

    return DocumentDetailOut(
        id=doc_record.id,
        club_id=ctx.club.id,
        template_id=tmpl_slug,
        title=doc_record.title,
        ref_no=doc_record.ref_no,
        status=doc_record.status,
        created_at=doc_record.created_at,
        current_version_no=latest_ver.version_no,
        page_count=len(page_urls) or 1,
        docx_url=f"/api/v1/clubs/{ctx.club.id}/documents/{doc_record.id}/download?format=docx",
        pdf_url=f"/api/v1/clubs/{ctx.club.id}/documents/{doc_record.id}/download?format=pdf",
        page_images=page_urls,
        versions=[
            DocumentVersionOut(
                id=v.id,
                version_no=v.version_no,
                docx_available=bool(v.docx_key and Path(v.docx_key).exists()),
                pdf_available=bool(v.pdf_key and Path(v.pdf_key).exists()),
                created_at=v.created_at,
                created_by="Author",
            )
            for v in versions
        ],
        record_snapshot=latest_ver.record_snapshot,
    )


@router.get("/{doc_id}/pages/{page_no}")
def get_document_page_preview(
    doc_id: str,
    page_no: int,
    v: int = Query(1),
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Serve high-resolution rasterized PNG page preview of rendered document."""
    page_file = Path("storage/previews") / doc_id / f"v{v}" / f"page_{page_no}.png"
    if not page_file.exists():
        raise HTTPException(status_code=404, detail="Page preview image not found")
    return FileResponse(page_file, media_type="image/png")


@router.get("/{doc_id}/download")
def download_document_file(
    doc_id: str,
    format: str = Query("pdf", pattern="^(pdf|docx)$"),
    v: Optional[int] = None,
    ctx: ClubContext = Depends(require_club_access(Role.VIEWER)),
    db: Session = Depends(get_db),
):
    """Download generated document in official PDF or editable DOCX format."""
    doc_repo = ScopedRepository(db, Document, club_id=ctx.club.id)
    doc_record = doc_repo.get(doc_id)
    if not doc_record:
        raise HTTPException(status_code=404, detail="Document not found")

    query = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc_id)
    if v is not None:
        version = query.filter(DocumentVersion.version_no == v).first()
    else:
        version = query.order_by(DocumentVersion.version_no.desc()).first()

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    if format == "pdf":
        file_path = Path(version.pdf_key) if version.pdf_key else None
        media_type = "application/pdf"
        filename = f"{doc_record.ref_no or 'document'}.pdf".replace("/", "_")
    else:
        file_path = Path(version.docx_key) if version.docx_key else None
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{doc_record.ref_no or 'document'}.docx".replace("/", "_")

    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not available on storage ({format.upper()})")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
