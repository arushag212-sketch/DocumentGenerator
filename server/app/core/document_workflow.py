"""Review, revision and approval workflow for generated documents.

Status flow:  ready -> submitted -> approved
                         \\-> changes_requested -> (revise) -> ready -> submitted ...
Any revision creates a new version with the same reference number and resets approval.

Approval is an electronic sign-off, not a PKI signature: the approved PDF is stamped with
the approver, time and a verification code, and its SHA-256 is stored so anyone can check a
copy at /verify/<code>.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import yaml
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from server.app.core.storage import require_local_storage
from server.app.models import Document, DocumentReview, DocumentVersion, TemplateVersion, User

EDITABLE_TYPES = {"text", "longtext", "int", "money", "date", "date_range", "time_range", "enum", "table", "list"}

TABLE_DEFAULTS = {
    "budget_items": [
        {"key": "item", "label": "Particulars", "type": "text"},
        {"key": "amount", "label": "Amount (Rs.)", "type": "money"},
    ],
    "agenda_items": [
        {"key": "topic", "label": "Topic", "type": "text"},
        {"key": "discussion", "label": "Discussion", "type": "longtext"},
        {"key": "decision", "label": "Decision", "type": "text"},
    ],
    "action_items": [
        {"key": "task", "label": "Task", "type": "text"},
        {"key": "owner", "label": "Owner", "type": "text"},
        {"key": "deadline", "label": "Deadline", "type": "date"},
    ],
    "winners": [
        {"key": "name", "label": "Winner Name", "type": "text"},
        {"key": "roll_no", "label": "Roll No", "type": "text"},
        {"key": "position", "label": "Position", "type": "text"},
        {"key": "amount", "label": "Prize (Rs.)", "type": "money"},
    ],
    "attendees": [
        {"key": "name", "label": "Attendee Name", "type": "text"},
    ],
    "absentees": [
        {"key": "name", "label": "Absentee Name", "type": "text"},
    ],
    "bill_items": [
        {"key": "item", "label": "Item Description", "type": "text"},
        {"key": "qty", "label": "Quantity", "type": "int"},
        {"key": "unit_cost", "label": "Unit Cost (Rs.)", "type": "money"},
    ],
}
IST = timezone(timedelta(hours=5, minutes=30))


def latest_version(db: Session, doc: Document) -> DocumentVersion:
    ver = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version_no.desc())
        .first()
    )
    if ver is None:
        raise HTTPException(status_code=404, detail="Document has no generated versions")
    return ver


def _schema_fields(db: Session, ver: DocumentVersion, doc: Document) -> list[dict[str, Any]]:
    tv_id = ver.template_version_id or doc.template_version_id
    tv = db.query(TemplateVersion).filter(TemplateVersion.id == tv_id).first() if tv_id else None
    try:
        schema = yaml.safe_load(tv.schema_yaml) if tv and tv.schema_yaml else {}
    except yaml.YAMLError:
        schema = {}
    return [f for f in (schema or {}).get("fields", []) if isinstance(f, dict) and f.get("key")]


def editable_fields(db: Session, doc: Document) -> list[dict[str, Any]]:
    """The template's simple fields with this document's current values, for the edit form."""
    ver = latest_version(db, doc)
    snapshot = ver.record_snapshot or {}
    out = []
    for f in _schema_fields(db, ver, doc):
        f_type = f.get("type", "text")
        if f_type not in EDITABLE_TYPES:
            continue
        value = snapshot.get(f["key"])
        if isinstance(value, dict) and "value" in value:
            value = value["value"]
        cols = f.get("columns") or TABLE_DEFAULTS.get(f["key"])
        out.append({
            "key": f["key"],
            "label": f.get("label") or f["key"].replace("_", " ").title(),
            "type": f_type,
            "required": bool(f.get("required")),
            "value": [] if f_type in ("table", "list") and value is None else ("" if value is None else value),
            "columns": cols,
        })
    return out


def _log(db: Session, doc: Document, version_no: int, action: str, user: Optional[User],
         comment: Optional[str] = None, **extra: Any) -> DocumentReview:
    entry = DocumentReview(
        club_id=doc.club_id,
        document_id=doc.id,
        version_no=version_no,
        action=action,
        user_id=user.id if user else None,
        comment=(comment or "").strip() or None,
        **extra,
    )
    db.add(entry)
    db.flush()
    return entry


def revise_document(db: Session, doc: Document, user: User, changes: dict[str, Any], note: Optional[str] = None) -> DocumentVersion:
    """New version with edited field values; same reference number; approval is reset."""
    from server.app.core.doc_retention import regenerate_document_version

    current = latest_version(db, doc)
    allowed = {f["key"] for f in editable_fields(db, doc)}
    unknown = sorted(set(changes) - allowed)
    if unknown:
        raise HTTPException(status_code=400, detail={"code": "UNKNOWN_FIELDS", "message": f"Not editable: {', '.join(unknown)}"})

    snapshot = dict(current.record_snapshot or {})
    diffs = []
    for key, new in changes.items():
        old = snapshot.get(key)
        if isinstance(old, dict) and "value" in old:
            old = old["value"]
        if old == new or (old is None and new == "") or (isinstance(old, (int, float)) and str(old) == str(new)):
            continue
        # Sanitize single-column string tables like attendees
        if key in ("attendees", "absentees") and isinstance(new, list):
            new = [
                r.get("name") if isinstance(r, dict) and "name" in r
                else r.get("value") if isinstance(r, dict) and "value" in r
                else str(r)
                for r in new
            ]
        elif key == "budget_items" and isinstance(new, list):
            from docgen.models import coerce_to_budget_items
            b_list = coerce_to_budget_items(new)
            new = [b.model_dump() for b in b_list]

        snapshot[key] = new
        if isinstance(new, list):
            diffs.append(f"{key}: {len(old or [])} row(s) → {len(new)} row(s)")
        else:
            diffs.append(f"{key}: “{old or ''}” → “{new or ''}”")
    if not diffs:
        raise HTTPException(status_code=400, detail={"code": "NO_CHANGES", "message": "Nothing was changed."})

    new_ver = DocumentVersion(
        document_id=doc.id,
        template_version_id=current.template_version_id or doc.template_version_id,
        version_no=current.version_no + 1,
        record_snapshot=snapshot,
        overrides={**(current.overrides or {}), **changes},
        diff_summary="; ".join(diffs),
        created_by=user.id,
        source="revised",
    )
    db.add(new_ver)
    db.flush()
    regenerate_document_version(db, doc.id, new_ver.version_no, club_id=doc.club_id)
    doc.current_version_id = new_ver.id
    doc.status = "ready"
    _log(db, doc, new_ver.version_no, "revised", user, note or "; ".join(diffs))
    return new_ver


def _require_status(doc: Document, allowed: tuple[str, ...], action: str) -> None:
    if doc.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_STATUS", "message": f"Cannot {action} a document that is '{doc.status}'."},
        )


def submit_for_review(db: Session, doc: Document, user: User, comment: Optional[str]) -> None:
    _require_status(doc, ("ready", "draft", "changes_requested", "needs_info"), "submit")
    doc.status = "submitted"
    _log(db, doc, latest_version(db, doc).version_no, "submitted", user, comment)


def request_changes(db: Session, doc: Document, user: User, comment: str) -> None:
    _require_status(doc, ("submitted",), "request changes on")
    if not (comment or "").strip():
        raise HTTPException(status_code=400, detail="Say what needs to change.")
    doc.status = "changes_requested"
    _log(db, doc, latest_version(db, doc).version_no, "changes_requested", user, comment)


def _stamp_pdf(pdf_path: Path, out_path: Path, lines: list[str]) -> None:
    """Add an approval footer to every page of the PDF."""
    import pymupdf

    pdf = pymupdf.open(str(pdf_path))
    for page in pdf:
        rect = page.rect
        box = pymupdf.Rect(36, rect.height - 34, rect.width - 36, rect.height - 8)
        page.draw_line(pymupdf.Point(36, rect.height - 36), pymupdf.Point(rect.width - 36, rect.height - 36),
                       color=(0.6, 0.6, 0.6), width=0.4)
        page.insert_textbox(box, "\n".join(lines), fontsize=6.5, fontname="helv", color=(0.25, 0.25, 0.25), align=1)
    pdf.save(str(out_path))
    pdf.close()


def approve(db: Session, doc: Document, user: User, role_label: str, comment: Optional[str]) -> DocumentReview:
    _require_status(doc, ("submitted",), "approve")
    ver = latest_version(db, doc)
    storage = require_local_storage()
    if not ver.pdf_key:
        raise HTTPException(status_code=409, detail="The PDF for this version is not available.")
    pdf_path = storage.local_path(ver.pdf_key)
    if not pdf_path.exists():
        from server.app.core.doc_retention import regenerate_document_version

        regenerate_document_version(db, doc.id, ver.version_no, club_id=doc.club_id)
        pdf_path = storage.local_path(ver.pdf_key)

    code = secrets.token_hex(4).upper() + "-" + secrets.token_hex(4).upper()
    when = datetime.now(IST).strftime("%d/%m/%Y %I:%M %p IST")
    signed_path = pdf_path.with_name(pdf_path.stem + "_approved.pdf")
    _stamp_pdf(pdf_path, signed_path, [
        f"Electronically approved by {user.name} ({role_label}) on {when}.",
        f"Verification code {code} — verify this copy at /verify/{code}",
    ])
    digest = hashlib.sha256(signed_path.read_bytes()).hexdigest()
    ver.pdf_key = str(signed_path)
    doc.status = "approved"
    return _log(db, doc, ver.version_no, "approved", user, comment, verification_code=code, pdf_sha256=digest)


def add_comment(db: Session, doc: Document, user: User, comment: str) -> DocumentReview:
    if not (comment or "").strip():
        raise HTTPException(status_code=400, detail="Comment cannot be empty.")
    return _log(db, doc, latest_version(db, doc).version_no, "comment", user, comment)


def log_email(db: Session, doc: Document, user: User, recipients: list[str]) -> None:
    _log(db, doc, latest_version(db, doc).version_no, "emailed", user, "Sent to " + ", ".join(recipients))


def activity(db: Session, doc: Document) -> list[dict[str, Any]]:
    rows = (
        db.query(DocumentReview)
        .filter(DocumentReview.document_id == doc.id)
        .order_by(DocumentReview.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "action": r.action,
            "version_no": r.version_no,
            "user_name": r.user.name if r.user else "System",
            "comment": r.comment,
            "verification_code": r.verification_code,
            "created_at": r.created_at,
        }
        for r in rows
    ]
