"""Missing-field detector: checks event record against template schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from docgen.models import EventRecord, TrackedField
from docgen.schema import FieldSchema, TemplateSchema


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


@dataclass
class MissingFieldReport:
    """Report of all missing/unconfirmed fields for selected templates."""
    missing: list[MissingField] = field(default_factory=list)
    unconfirmed: list[MissingField] = field(default_factory=list)

    @property
    def has_blockers(self) -> bool:
        """Are there required fields that are missing and not defer_ok?"""
        return any(f.required and not f.defer_ok for f in self.missing)

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
            value = getattr(event, key, None)

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
                    )
                    seen_keys[key] = mf
                    report.unconfirmed.append(mf)
                else:
                    if schema.name not in seen_keys[key].documents:
                        seen_keys[key].documents.append(schema.name)

    return report
