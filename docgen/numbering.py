"""Numbering suggestion system.

Generates reference number suggestions from counter formats.
All suggested reference numbers MUST have confirmed=False so that users
are required to review and confirm them before finalization.
"""

from __future__ import annotations

from typing import Optional
from docgen.config import ClubConfig
from docgen.db import Database
from docgen.models import FieldSource, TrackedField, tf
from docgen.schema import TemplateSchema


def suggest_reference_number(
    schema: TemplateSchema,
    config: ClubConfig,
    db: Optional[Database] = None,
    event_code: Optional[str] = None,
) -> Optional[TrackedField[str]]:
    """Generate a reference number suggestion.
    
    The returned TrackedField ALWAYS has source=FieldSource.computed and confirmed=False.
    """
    if not schema.numbering:
        return None

    series = schema.numbering.series or "GEN"
    fmt = schema.numbering.format

    # Fetch next sequence from database counter or config
    if db:
        initial = config.numbering.get(series, None).last_used if series in config.numbering else 0
        seq = db.get_next_sequence(series, initial=initial)
    else:
        seq = config.next_number(series)

    # Format components
    short_year = config.academic_year.replace("20", "") if config.academic_year else "26-27"
    academic_year = config.academic_year or "2026-27"
    code = event_code or "EVENT"

    ref_str = fmt.format(
        short_year=short_year,
        academic_year=academic_year,
        series=series,
        event_code=code,
        seq=seq,
    )

    # RULE 1: Reference numbers come from numbering counter as a SUGGESTION, confirmed=False
    return tf(ref_str, source=FieldSource.computed, confirmed=False)
