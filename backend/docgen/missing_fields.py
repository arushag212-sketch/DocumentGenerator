"""Missing-field detector: checks event record against template schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from docgen.models import EventRecord, TrackedField
from docgen.schema import FieldSchema, TemplateSchema


def _resolve_field_value(event: EventRecord, key: str) -> Any:
    """Resolve field value from EventRecord, checking direct attributes and nested structures."""
    val = getattr(event, key, None)
    if val is not None:
        return val

    # Cross-document references (approval_note)
    if key == "approval_note_no":
        return event.approval_note.no if event.approval_note else None
    if key == "approval_note_date":
        return event.approval_note.date if event.approval_note else None

    # Bills & invoices
    if event.bills:
        b = event.bills[0]
        if key == "supplier_name":
            return b.supplier.name if (b.supplier and b.supplier.name and str(b.supplier.name).strip()) else None
        if key == "supplier_gst":
            return b.supplier.gst_no if (b.supplier and b.supplier.gst_no and str(b.supplier.gst_no).strip()) else None
        if key == "invoice_no":
            return b.invoice_no if (b.invoice_no and str(b.invoice_no).strip()) else None
        if key == "invoice_date":
            return b.invoice_date if (b.invoice_date and str(b.invoice_date).strip()) else None
        if key == "bill_items":
            if not b.items:
                return None
            for it in b.items:
                name = it.name if hasattr(it, "name") else (it.get("name") if isinstance(it, dict) else None)
                qty = it.qty if hasattr(it, "qty") else (it.get("qty") if isinstance(it, dict) else None)
                cost = it.unit_cost if hasattr(it, "unit_cost") else (it.get("unit_cost") if isinstance(it, dict) else None)
                if not name or qty is None or cost is None or str(name).strip() == "":
                    return None
            return b.items
        if key == "tax_type":
            return b.tax_type if (b.tax_type and str(b.tax_type).strip()) else None
        if key == "tax_amount":
            return b.tax_rate_or_amount if (b.tax_rate_or_amount is not None and str(b.tax_rate_or_amount).strip() != "") else None
        if key == "bill_amount":
            if b.items:
                tot = sum(Decimal(str(it.unit_cost)) * Decimal(str(it.qty)) for it in b.items)
                return tot if tot > 0 else None
            return None
        if b.payment:
            if key == "payment_party":
                return b.payment.party if (b.payment.party and str(b.payment.party).strip()) else None
            if key == "payment_account_no":
                return b.payment.account_no if (b.payment.account_no and str(b.payment.account_no).strip()) else None
            if key == "payment_holder":
                return b.payment.holder if (b.payment.holder and str(b.payment.holder).strip()) else None
            if key == "payment_bank":
                return b.payment.bank if (b.payment.bank and str(b.payment.bank).strip()) else None
            if key == "payment_branch":
                return b.payment.branch if (b.payment.branch and str(b.payment.branch).strip()) else None
            if key == "payment_ifsc":
                return b.payment.ifsc if (b.payment.ifsc and str(b.payment.ifsc).strip()) else None

    # Winners & prizes
    if event.winners:
        w = event.winners[0]
        if key in ("winner_name", "name"):
            return w.name if (w.name and str(w.name).strip()) else None
        if key in ("winner_roll_no", "roll_no", "admission_no"):
            return w.roll_no if (w.roll_no and str(w.roll_no).strip()) else None
        if key in ("winner_course", "winner_course_semester", "course_semester"):
            return w.course_semester if (w.course_semester and str(w.course_semester).strip()) else None
        if key in ("winner_mobile", "mobile"):
            return w.mobile if (w.mobile and str(w.mobile).strip()) else None
        if key in ("prize_amount", "winner_amount", "amount"):
            return w.amount if (w.amount is not None and str(w.amount).strip() != "" and w.amount != 0) else None
        if key in ("position", "winner_position"):
            return w.position if (w.position and str(w.position).strip()) else None
        if w.bank:
            if key in ("account_no", "winner_account_no"):
                return w.bank.account_no if (w.bank.account_no and str(w.bank.account_no).strip()) else None
            if key in ("name_as_per_bank", "winner_bank_name_as_per_bank"):
                return w.bank.name_as_per_bank if (w.bank.name_as_per_bank and str(w.bank.name_as_per_bank).strip()) else None
            if key in ("bank_name", "winner_bank_name"):
                return w.bank.bank_name if (w.bank.bank_name and str(w.bank.bank_name).strip()) else None
            if key in ("branch", "winner_bank_branch"):
                return w.bank.branch if (w.bank.branch and str(w.bank.branch).strip()) else None
            if key in ("ifsc", "winner_ifsc"):
                return w.bank.ifsc if (w.bank.ifsc and str(w.bank.ifsc).strip()) else None
            if key in ("pan", "winner_pan"):
                return w.bank.pan if (w.bank.pan and str(w.bank.pan).strip()) else None

    # Meeting & MoM
    if event.meeting:
        m = event.meeting
        if key == "meeting_title":
            return m.title
        if key == "meeting_date":
            return m.date
        if key == "meeting_start_time":
            return m.start_time
        if key == "meeting_end_time":
            return m.end_time
        if key == "chaired_by":
            return m.chaired_by
        if key == "attendees":
            return m.attendees
        if key == "absentees":
            return m.absentees
        if key == "agenda_items":
            return m.agenda_items
        if key == "action_items":
            return m.action_items
        if key == "prepared_by":
            return m.prepared_by
        if key == "approved_by":
            return m.approved_by

    return None


@dataclass
class MissingField:
    """A field that is missing or unconfirmed."""
    key: str
    ask: str
    documents: list[str]  # which documents need this field
    required: bool = True
    defer_ok: bool = False
    mask: bool = False
    field_type: str = "text"
    values: Optional[list[str]] = None  # for enum fields
    importance: str = "optional"  # essential | optional


@dataclass
class MissingFieldReport:
    """Report of all missing/unconfirmed fields for selected templates."""
    missing: list[MissingField] = field(default_factory=list)
    unconfirmed: list[MissingField] = field(default_factory=list)

    @property
    def has_blockers(self) -> bool:
        """Are there essential required fields that are missing and not defer_ok?"""
        return any(
            f.required and not f.defer_ok and getattr(f, "importance", "optional") == "essential"
            for f in self.missing
        )

    def summary(self) -> str:
        lines = []
        if self.missing:
            lines.append("=== Missing Fields ===")
            for f in self.missing:
                status = "[REQUIRED]" if f.required and not f.defer_ok else "[optional/defer_ok]"
                lines.append(f"  {status} {f.key}: {f.ask}")
                lines.append(f"    Needed by: {', '.join(f.documents)}")
        if self.unconfirmed:
            lines.append("\n=== Unconfirmed Fields ===")
            for f in self.unconfirmed:
                lines.append(f"  [unconfirmed] {f.key}: {f.ask}")
                lines.append(f"    Needed by: {', '.join(f.documents)}")
        if not self.missing and not self.unconfirmed:
            lines.append("All fields are present and confirmed. ✓")
        return "\n".join(lines)


def detect_missing_fields(event: EventRecord,
                          schemas: list[TemplateSchema]) -> MissingFieldReport:
    """Detect missing and unconfirmed fields across selected templates.

    Args:
        event: The canonical event record
        schemas: List of schemas for selected document templates

    Returns:
        MissingFieldReport with grouped missing/unconfirmed fields
    """
    report = MissingFieldReport()
    seen_keys: dict[str, MissingField] = {}

    for schema in schemas:
        for field_schema in schema.fields:
            key = field_schema.key
            value = _resolve_field_value(event, key)

            # Check if the field exists in the event record
            is_missing = False
            is_unconfirmed = False

            if value is None:
                is_missing = True
            elif isinstance(value, TrackedField):
                if not value.is_present:
                    is_missing = True
                elif not value.confirmed:
                    is_unconfirmed = True
            elif isinstance(value, list) and len(value) == 0:
                if field_schema.required is True:
                    is_missing = True

            # Skip computed fields — they'll be computed at render time
            if field_schema.computed:
                continue
            ask_text = field_schema.ask or f"Please provide: {key}"
            ay = getattr(event, "academic_year", None)
            ay_str = ay.value if hasattr(ay, "value") and ay.value else "2026-27"
            short_year = ay_str.split("-")[-1] if "-" in ay_str else ay_str[-2:]
            ask_text = ask_text.replace("{academic_year}", str(ay_str)).replace("{short_year}", str(short_year)).replace("{next}", "001")

            if is_missing:
                if key in seen_keys:
                    # Add this document to existing missing field
                    if schema.name not in seen_keys[key].documents:
                        seen_keys[key].documents.append(schema.name)
                else:
                    mf = MissingField(
                        key=key,
                        ask=ask_text,
                        documents=[schema.name],
                        required=field_schema.required is True,
                        defer_ok=field_schema.defer_ok,
                        mask=field_schema.mask,
                        field_type=field_schema.type,
                        values=field_schema.values,
                        importance=getattr(field_schema, "importance", "optional"),
                    )
                    seen_keys[key] = mf
                    report.missing.append(mf)

            elif is_unconfirmed:
                if key not in seen_keys:
                    mf = MissingField(
                        key=key,
                        ask=ask_text,
                        documents=[schema.name],
                        required=field_schema.required is True,
                        defer_ok=field_schema.defer_ok,
                        importance=getattr(field_schema, "importance", "optional"),
                    )
                    seen_keys[key] = mf
                    report.unconfirmed.append(mf)
                else:
                    if schema.name not in seen_keys[key].documents:
                        seen_keys[key].documents.append(schema.name)

    return report
