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


def compute_short_year(academic_year: str) -> str:
    """Format academic year as two-digit short year.

    Examples:
        '2026-27' -> '26-27'
        '2026-2027' -> '26-27'
        '26-27' -> '26-27'
        '2026' -> '26'
    """
    if not academic_year:
        return ""
    ay = str(academic_year).strip()
    if "-" in ay:
        parts = ay.split("-", 1)
        part1 = parts[0][-2:] if len(parts[0]) >= 2 else parts[0]
        part2 = parts[1][-2:] if len(parts[1]) >= 2 else parts[1]
        return f"{part1}-{part2}"
    return ay[-2:] if len(ay) >= 2 else ay


def format_reference_number(
    format_pattern: str,
    academic_year: str,
    series_key: str,
    seq: int,
    club_code: str = "ACM",
    event_code: Optional[str] = None,
) -> str:
    """Format reference number using a single canonical set of rules across suggest, reserve, and tests.

    Ensures {short_year} renders as e.g. '26-27' for academic year 2026-27 (matching ACM/26-27/ROOM/009),
    while event approval series renders e.g. ACM/2026-27/SIH/001.
    """
    short_year = compute_short_year(academic_year)
    code = event_code or series_key
    fmt = format_pattern
    if "{seq" not in fmt:
        fmt = f"{fmt}/{{seq:03d}}"

    return fmt.format(
        club_code=club_code,
        club_prefix=club_code,
        academic_year=academic_year,
        short_year=short_year,
        series=series_key,
        event_code=code,
        seq=seq,
    )


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

    series = schema.numbering.series or event_code or "EVENT"
    fmt = schema.numbering.format

    # Fetch next sequence from database counter or config
    if db:
        initial = config.numbering.get(series, None).last_used if series in config.numbering else 0
        seq = db.get_next_sequence(series, initial=initial)
    else:
        seq = config.next_number(series)

    academic_year = config.academic_year or ""
    club_code = getattr(config, "club_short", "ACM")

    ref_str = format_reference_number(
        format_pattern=fmt,
        academic_year=academic_year,
        series_key=series,
        seq=seq,
        club_code=club_code,
        event_code=event_code,
    )

    # RULE 1: Reference numbers come from numbering counter as a SUGGESTION, confirmed=False
    return tf(ref_str, source=FieldSource.computed, confirmed=False)

