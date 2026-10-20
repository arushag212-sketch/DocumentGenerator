"""Batch Document Generator: generates multiple documents for an event in one job,
reserves reference numbers using the shared allocator, loops repeat_per collections,
renders DOCX and PDF with LibreOffice, and packages into a downloadable ZIP archive.

Strict Integrity Rules:
1. ZERO silent fabrication or synthetic defaults.
2. Unconfirmed AI-drafted values are rejected with 400 UNCONFIRMED_AI_DRAFT.
3. Detects missing required fields before rendering; rejects whole batch with 400 MISSING_REQUIRED_FIELDS.
4. Concurrency-safe atomic transaction: rolls back all allocations and document creations on any render error.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import uuid
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pymupdf
import yaml
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from docgen.functions import fn_amount_in_words_inr
from docgen.missing_fields import detect_missing_fields
from docgen.models import (
    ApprovalNote,
    BankDetails,
    BillItem,
    BillRecord,
    BudgetItem,
    EventRecord,
    FieldSource,
    PaymentDetails,
    SupplierDetails,
    TrackedField,
    Winner,
)
from docgen.renderer import Renderer
from docgen.schema import TemplateSchema, load_schema
from docgen.sources import DatabaseTemplateSource, build_club_config_from_db
from server.app.core.audit import log_audit
from docgen.field_aliases import apply_field_aliases
from docgen.numbering import derive_event_code
from server.app.core.numbering_service import reserve_number_for_document
from server.app.core.doc_retention import prune_document_versions
from server.app.core.storage import require_local_storage
from server.app.models import (
    Club,
    Document,
    DocumentVersion,
    Event,
    NumberingSeries,
    NumberReservation,
    Template,
    TemplateVersion,
    Venue,
)


def sanitize_filename(name: Any) -> str:
    """Sanitize string for clean file name inside zip archive."""
    if not name:
        return "doc"
    clean = re.sub(r'[/\\:*?"<>|]', '_', str(name))
    return re.sub(r'\s+', '_', clean).strip('_') or "doc"


MAX_BATCH_ROWS = 300


class BatchGenerator:
    @staticmethod
    def generate_batch(
        club_id: str,
        user_id: str,
        selected_template_ids: list[str],
        event_data: dict[str, Any],
        event_id: Optional[str] = None,
        event_title: Optional[str] = None,
        allow_blanks: bool = False,
        db: Session = None,
    ) -> dict[str, Any]:
        try:
            local_storage = require_local_storage()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

        storage_root = local_storage.base_dir
        club = db.query(Club).filter(Club.id == club_id).first()
        if not club:
            raise HTTPException(status_code=404, detail=f"Club '{club_id}' not found.")

        # ---------------- 0. SANITIZE LIST & SCALAR FIELDS ----------------
        if "judges" in event_data:
            from docgen.models import coerce_to_list_of_strings
            event_data["judges"] = coerce_to_list_of_strings(event_data["judges"])

        if "budget_items" in event_data:
            from docgen.models import coerce_to_budget_items
            b_list = coerce_to_budget_items(event_data["budget_items"])
            event_data["budget_items"] = [b.model_dump() for b in b_list]
        elif any(event_data.get(k) for k in ("estimated_budget", "budget", "budget_amount", "sanctioned_budget")):
            from docgen.models import coerce_to_budget_items
            b_val = event_data.get("estimated_budget") or event_data.get("budget") or event_data.get("budget_amount") or event_data.get("sanctioned_budget")
            b_list = coerce_to_budget_items(b_val)
            event_data["budget_items"] = [b.model_dump() for b in b_list]

        if "winners" in event_data and not isinstance(event_data["winners"], list):
            event_data["winners"] = []

        if "bills" in event_data and not isinstance(event_data["bills"], list):
            event_data["bills"] = []

        # ---------------- 0. INPUT DATES HANDLING ----------------
        if allow_blanks and not event_data.get("dates") and not event_data.get("date_start"):
            event_data["dates_confirmed"] = True
            event_data["dates"] = "____________________"

        has_picker_dates = bool(
            event_data.get("date_start")
            and event_data.get("date_end")
            and re.match(r"^\d{4}-\d{2}-\d{2}$", str(event_data.get("date_start")))
            and re.match(r"^\d{4}-\d{2}-\d{2}$", str(event_data.get("date_end")))
        )
        if has_picker_dates:
            event_data["dates_confirmed"] = True
            if not event_data.get("dates"):
                from docgen.functions import fn_format_date_range
                event_data["dates"] = fn_format_date_range(event_data["date_start"], event_data["date_end"])
        elif event_data.get("dates"):
            dates_val = str(event_data.get("dates") or "").strip()
            is_confirmed = bool(event_data.get("dates_confirmed"))
            has_full_year = bool(re.search(r"\b20\d\d\b", dates_val))
            if not is_confirmed or not has_full_year or "assumed" in dates_val.lower():
                if not is_confirmed:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "code": "DATES_NOT_CONFIRMED",
                            "message": "Event dates must be confirmed before generation.",
                        },
                    )
            if not event_data.get("date_start") or not event_data.get("date_end"):
                from docgen.extractors.event_extractor import EventExtractor
                try:
                    ext = EventExtractor()
                    parsed_rec = ext.extract_from_text(dates_val)
                    if parsed_rec.date_start and not event_data.get("date_start"):
                        event_data["date_start"] = parsed_rec.date_start.value
                    if parsed_rec.date_end and not event_data.get("date_end"):
                        event_data["date_end"] = parsed_rec.date_end.value
                except Exception:
                    pass

        # ---------------- 1. STRICT AI DRAFT GUARD ----------------
        # Do NOT strip '[AI-drafted, review]'. Reject any unconfirmed AI-draft values.
        for k, v in event_data.items():
            if isinstance(v, str) and "[AI-drafted" in v:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "UNCONFIRMED_AI_DRAFT",
                        "message": f"Field '{k}' contains unconfirmed AI draft. Please accept or edit before generating.",
                    },
                )
        for idx, w in enumerate(event_data.get("winners") or []):
            if isinstance(w, dict):
                for wk, wv in w.items():
                    if isinstance(wv, str) and "[AI-drafted" in wv:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail={
                                "code": "UNCONFIRMED_AI_DRAFT",
                                "message": f"Winner #{idx+1} '{wk}' contains unconfirmed AI draft. Please accept or edit before generating.",
                            },
                        )
        for idx, b in enumerate(event_data.get("bills") or []):
            if isinstance(b, dict):
                for bk, bv in b.items():
                    if isinstance(bv, str) and "[AI-drafted" in bv:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail={
                                "code": "UNCONFIRMED_AI_DRAFT",
                                "message": f"Bill #{idx+1} '{bk}' contains unconfirmed AI draft. Please accept or edit before generating.",
                            },
                        )

        # ---------------- 2. FETCH SELECTED TEMPLATES & SCHEMAS ----------------
        templates_to_render: list[tuple[Template, TemplateVersion, dict[str, Any]]] = []
        for tmpl_id in selected_template_ids:
            tmpl = (
                db.query(Template)
                .filter(
                    (Template.id == tmpl_id) | (Template.slug == tmpl_id),
                    (Template.club_id == club_id) | (Template.is_system == True),
                )
                .first()
            )
            if not tmpl:
                raise HTTPException(status_code=404, detail=f"Template '{tmpl_id}' not found.")

            tmpl_ver = (
                db.query(TemplateVersion)
                .filter(TemplateVersion.template_id == tmpl.id)
                .order_by(TemplateVersion.version_no.desc())
                .first()
            )
            if not tmpl_ver:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "TEMPLATE_VERSION_NOT_FOUND", "message": f"Template '{tmpl_id}' has no version."},
                )

            schema_dict: dict[str, Any] = {}
            if tmpl_ver and tmpl_ver.schema_yaml:
                try:
                    loaded = yaml.safe_load(tmpl_ver.schema_yaml)
                    if isinstance(loaded, dict):
                        schema_dict = loaded
                except Exception:
                    pass
            if not schema_dict:
                try:
                    s_obj = load_schema(tmpl.slug)
                    schema_dict = s_obj.dict()
                except Exception:
                    pass

            templates_to_render.append((tmpl, tmpl_ver, schema_dict))

        # Copy canonical facts onto the field names these templates use (no new facts)
        apply_field_aliases(
            event_data,
            wanted={f.get("key") for _, _, sd in templates_to_render for f in (sd.get("fields") or []) if f.get("key")},
        )

        # ---------------- 3. MISSING FIELD DETECTION (NO FABRICATION) ----------------
        # Required fields must be supplied by the user. Only document_date=today and
        # config-backed settings (e.g. mode) are permitted as system defaults.
        missing_blockers: list[dict[str, Any]] = []

        # (a) Date confirmation check. Event dates are required for every system template and
        # for custom templates that print a date; a certificate without a date field needs none.
        schedule_keys = {"dates", "date_start", "date_end", "event_dates", "date_of_event", "activity_date"}
        needs_dates = any(
            tmpl.is_system or any(f.get("key") in schedule_keys for f in (s_dict.get("fields") or []))
            for tmpl, _, s_dict in templates_to_render
        )
        dates_confirmed = bool(event_data.get("dates_confirmed"))
        dates_val = event_data.get("dates") or event_data.get("date_start")
        if not needs_dates:
            pass
        elif not dates_val:
            missing_blockers.append({
                "key": "dates",
                "ask": "Event schedule dates?",
                "defer_ok": False,
                "required": True,
            })
            missing_blockers.append({
                "key": "dates_confirmation",
                "ask": "Dates confirmation: Event dates must be confirmed before generation.",
                "defer_ok": False,
                "required": True,
            })
        elif not dates_confirmed and ("assumed" in str(dates_val).lower() or not re.search(r"\b20\d\d\b", str(dates_val))):
            missing_blockers.append({
                "key": "dates_confirmation",
                "ask": "Dates confirmation: Assumed academic year date must be explicitly confirmed.",
                "defer_ok": False,
                "required": True,
            })

        # (b) Time checks (permission_letter and pre_event schemas strictly require times)
        needs_times = any(
            any(f.get("key") in ("time_start", "time_end") and f.get("required") for f in s_dict.get("fields", []))
            for _, _, s_dict in templates_to_render
        )
        if needs_times:
            if not event_data.get("time_start"):
                missing_blockers.append({
                    "key": "time_start",
                    "ask": "Start time?",
                    "defer_ok": False,
                    "required": True,
                })
            if not event_data.get("time_end"):
                missing_blockers.append({
                    "key": "time_end",
                    "ask": "End time?",
                    "defer_ok": False,
                    "required": True,
                })

        # (c) Description & Objectives check
        needs_desc = any(
            any(f.get("key") == "description" and f.get("required") for f in s_dict.get("fields", []))
            for _, _, s_dict in templates_to_render
        )
        if needs_desc and (not event_data.get("description") or not str(event_data.get("description")).strip()):
            missing_blockers.append({
                "key": "description",
                "ask": "Brief description of the event?",
                "defer_ok": False,
                "required": True,
            })

        needs_obj = any(
            any(f.get("key") == "objectives" and f.get("required") for f in s_dict.get("fields", []))
            for _, _, s_dict in templates_to_render
        )
        if needs_obj and (not event_data.get("objectives") or not str(event_data.get("objectives")).strip()):
            missing_blockers.append({
                "key": "objectives",
                "ask": "What are the objectives?",
                "defer_ok": False,
                "required": True,
            })

        # (d) Submitted to check
        needs_submitted = any(
            any(f.get("key") == "submitted_to" and f.get("required") for f in s_dict.get("fields", []))
            for _, _, s_dict in templates_to_render
        )
        if needs_submitted and not event_data.get("submitted_to"):
            missing_blockers.append({
                "key": "submitted_to",
                "ask": "Who is this document addressed / submitted to?",
                "defer_ok": False,
                "required": True,
            })

        # (d2) Required inputs of Studio/library templates (compiled from editor JSON). Values may
        # come from the event data or, for per-row batches, from every row.
        handled_elsewhere = {"dates", "date_start", "date_end", "time_start", "time_end", "description",
                             "objectives", "submitted_to", "ref_no", "document_date"}
        row_list = [r for r in (event_data.get("rows") or []) if isinstance(r, dict)]
        if len(row_list) > MAX_BATCH_ROWS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "TOO_MANY_ROWS", "message": f"A batch can have at most {MAX_BATCH_ROWS} rows."},
            )

        def _present(v: Any) -> bool:
            return v is not None and str(v).strip() not in ("", "None", "null")

        for tmpl, tmpl_ver, s_dict in templates_to_render:
            if not (tmpl_ver and tmpl_ver.editor_json):
                continue  # legacy system forms keep their own checks above
            for f in s_dict.get("fields", []) or []:
                key = f.get("key")
                if not key or not f.get("required") or f.get("computed") or key in handled_elsewhere:
                    continue
                if f.get("type") == "table":
                    continue
                if _present(event_data.get(key)) or (row_list and all(_present(r.get(key)) for r in row_list)):
                    continue
                missing_blockers.append({
                    "key": key,
                    "ask": f.get("ask") or f.get("label") or key.replace("_", " ").title(),
                    "defer_ok": bool(f.get("defer_ok", False)),
                    "required": True,
                })

        # (e) Repeat Items validation (winners, bills)
        for tmpl, _, s_dict in templates_to_render:
            repeat_per = s_dict.get("repeat_per")
            if repeat_per == "winners" or tmpl.slug == "prize_money_receipt":
                winners = event_data.get("winners") or []
                if not winners:
                    missing_blockers.append({
                        "key": "winners",
                        "ask": "Winners list is required for prize receipts.",
                        "required": True,
                    })
                else:
                    for idx, w in enumerate(winners):
                        w_prefix = f"winner #{idx + 1}"
                        if not w.get("name") or not str(w.get("name")).strip():
                            missing_blockers.append({"key": f"{w_prefix}: name", "ask": f"{w_prefix}: name is required", "required": True})
                        if not w.get("roll_no") or not str(w.get("roll_no")).strip():
                            missing_blockers.append({"key": f"{w_prefix}: roll_no", "ask": f"{w_prefix}: roll_no is required", "required": True})
                        if not w.get("position") or not str(w.get("position")).strip():
                            missing_blockers.append({"key": f"{w_prefix}: position", "ask": f"{w_prefix}: position is required", "required": True})
                        w_amt = w.get("amount") if w.get("amount") is not None else w.get("prize_amount")
                        if w_amt is None or str(w_amt).strip() == "" or float(w_amt) <= 0:
                            missing_blockers.append({"key": f"{w_prefix}: amount", "ask": f"{w_prefix}: prize amount is required", "required": True})

            elif repeat_per == "bills" or tmpl.slug in ("bill_certificate", "bill_summary"):
                bills = event_data.get("bills") or []
                if not bills:
                    missing_blockers.append({
                        "key": "bills",
                        "ask": "Bills list is required for bill documents.",
                        "required": True,
                    })
                else:
                    for idx, b in enumerate(bills):
                        b_prefix = f"bill #{idx + 1}"
                        b_no = b.get("bill_no") or b.get("invoice_no")
                        if not b_no or not str(b_no).strip():
                            missing_blockers.append({"key": f"{b_prefix}: bill_no", "ask": f"{b_prefix}: bill number is required", "required": True})
                        b_vendor = b.get("vendor") or b.get("supplier_name")
                        if not b_vendor or not str(b_vendor).strip():
                            missing_blockers.append({"key": f"{b_prefix}: vendor", "ask": f"{b_prefix}: vendor name is required", "required": True})
                        b_amt = b.get("amount")
                        if b_amt is None or str(b_amt).strip() == "" or float(b_amt) <= 0:
                            missing_blockers.append({"key": f"{b_prefix}: amount", "ask": f"{b_prefix}: amount is required", "required": True})

        # Deduplicate missing blockers by key
        seen_keys = set()
        deduped_missing = []
        for m in missing_blockers:
            if m["key"] not in seen_keys:
                seen_keys.add(m["key"])
                deduped_missing.append(m)

        if not allow_blanks and deduped_missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "MISSING_REQUIRED_FIELDS",
                    "message": f"Cannot generate batch: {len(deduped_missing)} required field(s) missing or unconfirmed.",
                    "missing": deduped_missing,
                },
            )

        # ---------------- 4. ATOMIC EXECUTION (TRANSACTION & ROLLBACK) ----------------
        final_title = event_title or event_data.get("event_name")
        if not final_title:
            if allow_blanks:
                final_title = "College Event"
            else:
                raise HTTPException(status_code=400, detail="Event name/title is required for batch generation.")
        if not event_data.get("event_name"):
            event_data["event_name"] = final_title

        # Ensure event_code is present
        if not event_data.get("event_code"):
            event_data["event_code"] = derive_event_code(final_title)

        # Ensure category is present
        if not event_data.get("category"):
            event_data["category"] = event_data.get("event_type") or "Technical Event"

        if not event_data.get("target_audience"):
            event_data["target_audience"] = "SVNIT Students & Participants"
        if not event_data.get("submitted_to"):
            event_data["submitted_to"] = "Dean (Student Welfare), SVNIT Surat"

        batch_id = str(uuid.uuid4())
        batch_dir = storage_root / "cache" / "batches" / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        generated_docs: list[dict[str, Any]] = []
        files_for_zip: list[tuple[Path, str]] = []

        try:
            # 4.1 Resolve or create Event record
            clean_event_data = json.loads(json.dumps(event_data, default=str))
            if event_id:
                event = db.query(Event).filter(Event.id == event_id, Event.club_id == club_id).first()
                if not event:
                    raise HTTPException(status_code=404, detail="Specified event not found in active club.")
                event.record = {**(event.record or {}), **clean_event_data}
                if event_title:
                    event.title = event_title
            else:
                event = Event(
                    id=str(uuid.uuid4()),
                    club_id=club_id,
                    title=final_title,
                    event_code=event_data.get("event_code"),
                    record=clean_event_data,
                    status="active",
                    created_by=user_id,
                )
                db.add(event)
                db.flush()

            db_config = build_club_config_from_db(db, club.slug)
            db_source = DatabaseTemplateSource(db)

            # 4.2 Build generation task list
            tasks_to_run: list[tuple[Template, TemplateVersion, str, dict[str, Any]]] = []

            for tmpl, tmpl_ver, schema_dict in templates_to_render:
                repeat_per = schema_dict.get("repeat_per")

                if repeat_per == "winners" or tmpl.slug == "prize_money_receipt":
                    for w in event_data.get("winners") or []:
                        w_ctx = dict(event_data)
                        w_ctx["winner"] = w
                        w_ctx["winners"] = [w]
                        w_ctx["winner_name"] = w.get("name")
                        w_ctx["winner_position"] = w.get("position")
                        win_amt = w.get("amount") if w.get("amount") is not None else w.get("prize_amount", 0)
                        w_ctx["winner_amount"] = win_amt
                        w_ctx["winner_roll_no"] = w.get("roll_no")
                        w_ctx["winner_course_semester"] = w.get("course_semester") or ""
                        w_ctx["winner_mobile"] = w.get("mobile") or ""
                        w_ctx["amount_in_words"] = fn_amount_in_words_inr(win_amt)
                        doc_title = f"{tmpl.name} - {w.get('name')}"
                        tasks_to_run.append((tmpl, tmpl_ver, doc_title, w_ctx))

                elif repeat_per == "bills" or tmpl.slug in ("bill_certificate", "bill_summary"):
                    for b in event_data.get("bills") or []:
                        b_ctx = dict(event_data)
                        b_ctx["bill"] = b
                        b_ctx["bills"] = [b]
                        b_no = b.get("bill_no") or b.get("invoice_no")
                        b_ctx["bill_no"] = b_no
                        b_ctx["invoice_no"] = b_no
                        b_ctx["vendor"] = b.get("vendor") or b.get("supplier_name")
                        b_ctx["supplier_name"] = b_ctx["vendor"]
                        b_ctx["amount"] = b.get("amount")
                        doc_title = f"{tmpl.name} - Bill #{b_no}"
                        tasks_to_run.append((tmpl, tmpl_ver, doc_title, b_ctx))

                elif row_list and event_data.get("rows_for") in (None, "", tmpl.id, tmpl.slug):
                    # Batch from a spreadsheet: one document per row (e.g. a certificate per participant).
                    # `rows_for` names the template the sheet was mapped to; other documents stay single.
                    wanted = {f.get("key") for f in (schema_dict.get("fields") or []) if f.get("key")}
                    for idx, row in enumerate(row_list, start=1):
                        r_ctx = {k: v for k, v in event_data.items() if k not in ("rows", "rows_for")}
                        r_ctx.update({k: v for k, v in row.items() if _present(v)})
                        apply_field_aliases(r_ctx, wanted=wanted)
                        label = next((str(row[k]) for k in ("recipient_name", "name", "participant_name") if _present(row.get(k))),
                                     next((str(v) for v in row.values() if _present(v)), f"Row {idx}"))
                        tasks_to_run.append((tmpl, tmpl_ver, f"{tmpl.name} - {label}", r_ctx))

                else:
                    tasks_to_run.append((tmpl, tmpl_ver, f"{tmpl.name} - {final_title}", dict(event_data)))

            # 4.3 Execute generation tasks (allocate, render, store)
            for tmpl, tmpl_ver, task_title, task_ctx in tasks_to_run:
                # Allowed defaults: document_date=today, config mode
                if not task_ctx.get("document_date"):
                    task_ctx["document_date"] = date.today().strftime("%d/%m/%Y")
                if not task_ctx.get("mode"):
                    task_ctx["mode"] = club.settings.get("defaults", {}).get("mode", "Offline")
                if not task_ctx.get("event_code"):
                    task_ctx["event_code"] = event_data.get("event_code") or "EVT"
                if not task_ctx.get("category"):
                    task_ctx["category"] = event_data.get("category") or "Technical Event"

                has_numbering = False
                series_key = None
                format_pattern = None

                s_numbering = None
                if tmpl_ver and tmpl_ver.schema_yaml:
                    try:
                        s_yaml = yaml.safe_load(tmpl_ver.schema_yaml)
                        if isinstance(s_yaml, dict) and s_yaml.get("numbering"):
                            s_numbering = s_yaml["numbering"]
                    except Exception:
                        pass
                if not s_numbering:
                    try:
                        s_schema = load_schema(tmpl.slug)
                        if s_schema.numbering:
                            s_numbering = s_schema.numbering.dict()
                    except Exception:
                        pass

                if not s_numbering:
                    ay = club.academic_year_default
                    ns_evt = db.query(NumberingSeries).filter(
                        NumberingSeries.club_id == club_id,
                        NumberingSeries.academic_year == ay,
                        NumberingSeries.key == "EVT",
                    ).first()
                    if ns_evt:
                        s_numbering = {"series": "EVT"}

                reservation = None
                if s_numbering:
                    has_numbering = True
                    candidate_series = s_numbering.get("series") or tmpl.slug
                    format_pattern = s_numbering.get("format")

                    # Check in DB if candidate_series exists for this club's academic year
                    ay = club.academic_year_default
                    ns = db.query(NumberingSeries).filter(
                        NumberingSeries.club_id == club_id,
                        NumberingSeries.academic_year == ay,
                        NumberingSeries.key == candidate_series,
                    ).first()

                    # Fallbacks if candidate_series was not found under that exact key
                    if not ns:
                        # 1. Try tmpl.slug
                        ns_slug = db.query(NumberingSeries).filter(
                            NumberingSeries.club_id == club_id,
                            NumberingSeries.academic_year == ay,
                            NumberingSeries.key == tmpl.slug,
                        ).first()
                        if ns_slug:
                            candidate_series = tmpl.slug
                        elif task_ctx.get("event_code"):
                            # 2. Try event_code
                            ns_ev = db.query(NumberingSeries).filter(
                                NumberingSeries.club_id == club_id,
                                NumberingSeries.academic_year == ay,
                                NumberingSeries.key == task_ctx.get("event_code"),
                            ).first()
                            if ns_ev:
                                candidate_series = task_ctx.get("event_code")

                    series_key = candidate_series

                    # Allocate sequence number atomically via shared service
                    try:
                        reservation, ref_no = reserve_number_for_document(
                            db=db,
                            club_id=club_id,
                            user_id=user_id,
                            series_key=series_key,
                            academic_year=club.academic_year_default,
                            event_code=task_ctx.get("event_code"),
                            format_pattern=format_pattern,
                            expiry_minutes=1440,
                            status="used",
                            # A template that declares its own numbering format owns that
                            # series: start it at 001 on first use instead of failing.
                            allow_create=bool(format_pattern),
                        )
                    except ValueError as e:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"code": "NUMBERING_SERIES_NOT_FOUND", "message": str(e)},
                        )
                else:
                    ref_no = task_ctx.get("bill_no") or task_ctx.get("invoice_no") or task_ctx.get("ref_no") or None

                clean_ref_no = ref_no.strip() if (ref_no and isinstance(ref_no, str) and ref_no.strip()) else None
                task_ctx["ref_no"] = clean_ref_no or ""

                # Create Document record
                doc_record = Document(
                    id=str(uuid.uuid4()),
                    club_id=club_id,
                    template_id=tmpl.id,
                    template_version_id=tmpl_ver.id if tmpl_ver else tmpl.id,
                    event_id=event.id,
                    title=task_title,
                    ref_no=clean_ref_no,
                    status="ready",
                    created_by=user_id,
                )
                db.add(doc_record)
                db.flush()
                if reservation:
                    reservation.document_id = doc_record.id
                    db.flush()

                # Render via Docgen Renderer
                out_dir = storage_root / "documents" / doc_record.id / "v1"
                out_dir.mkdir(parents=True, exist_ok=True)

                event_rec = EventRecord.from_flat_dict(task_ctx)
                renderer = Renderer(config=db_config, template_source=db_source, outputs_dir=out_dir)
                render_result = renderer.render(
                    template_id=tmpl.slug,
                    event=event_rec,
                    extra_context=task_ctx,
                    output_dir=out_dir,
                    convert_pdf=True,
                    allow_blanks=allow_blanks,
                )

                docx_path = render_result.docx_path
                pdf_path = render_result.pdf_path

                # On-demand preview rendering: calculate page count without writing PNGs
                page_count = 1
                try:
                    pdf_doc = pymupdf.open(str(pdf_path))
                    page_count = len(pdf_doc)
                    pdf_doc.close()
                except Exception:
                    page_count = 1

                # DocumentVersion
                ver_record = DocumentVersion(
                    id=str(uuid.uuid4()),
                    document_id=doc_record.id,
                    template_version_id=tmpl_ver.id,
                    version_no=1,
                    record_snapshot=json.loads(json.dumps({**event_rec.flat_dict(), **task_ctx}, default=str)),
                    overrides={},
                    docx_key=str(docx_path),
                    pdf_key=str(pdf_path),
                    created_by=user_id,
                    source="batch_generated",
                )
                db.add(ver_record)
                doc_record.current_version_id = ver_record.id
                db.flush()
                prune_document_versions(db, doc_record.id)

                generated_docs.append({
                    "id": doc_record.id,
                    "template_slug": tmpl.slug,
                    "template_name": tmpl.name,
                    "title": doc_record.title,
                    "ref_no": doc_record.ref_no or "",
                    "docx_path": str(docx_path),
                    "pdf_path": str(pdf_path),
                    "page_count": page_count,
                })

                clean_ref = sanitize_filename(doc_record.ref_no or "doc")
                clean_title = sanitize_filename(task_title)
                archive_base = f"{clean_ref}_{clean_title}"
                files_for_zip.append((docx_path, f"{archive_base}.docx"))
                files_for_zip.append((pdf_path, f"{archive_base}.pdf"))

            # 4.4 Package ZIP Archive
            event_slug = sanitize_filename(final_title)
            zip_filename = f"{event_slug}_documents.zip"
            zip_path = batch_dir / zip_filename

            with zipfile.ZipFile(str(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for src_file, arc_name in files_for_zip:
                    if src_file.exists():
                        zf.write(str(src_file), arcname=arc_name)

            db.commit()

        except Exception as e:
            db.rollback()
            if batch_dir.exists():
                shutil.rmtree(batch_dir, ignore_errors=True)
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"Batch generation failed: {e}")

        # 4.5 Audit Log
        log_audit(
            db=db,
            action="documents_batch_generated",
            entity_type="event",
            entity_id=event.id,
            club_id=club_id,
            user_id=user_id,
            meta={
                "batch_id": batch_id,
                "event_title": final_title,
                "documents_count": len(generated_docs),
                "zip_filename": zip_filename,
            },
        )

        return {
            "batch_id": batch_id,
            "event_id": event.id,
            "event_title": final_title,
            "documents_count": len(generated_docs),
            "zip_filename": zip_filename,
            "zip_path": str(zip_path),
            "zip_url": f"/api/v1/clubs/{club_id}/documents/batch/{batch_id}/download-zip",
            "documents": generated_docs,
        }
