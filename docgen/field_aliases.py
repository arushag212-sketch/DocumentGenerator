"""Map canonical extracted event fields onto the varied keys custom templates use.

Extraction always produces canonical keys (event_name, venue, dates, date_start, ...),
but club and AI-designed templates name the same facts differently (event_date,
coordinator_name, location, ...). Without this mapping the user is asked again for
facts they already gave.

Only fills keys that are absent or blank; never overwrites a value the user supplied,
and never invents a value: every alias is copied from a canonical key that is present.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

# canonical key -> alias keys commonly produced by template authors / the AI designer
CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "event_name": ("event_title", "title", "event", "program_name", "programme_name", "workshop_name", "activity_name"),
    "venue": ("event_venue", "location", "place", "hall"),
    "dates": ("event_date", "event_dates", "date_of_event", "activity_date"),
    "date_start": ("start_date", "from_date"),
    "date_end": ("end_date", "to_date"),
    "time_start": ("start_time", "from_time"),
    "time_end": ("end_time", "to_time"),
    "participants": (
        "expected_participants",
        "participants_count",
        "number_of_participants",
        "attendees",
        "expected_attendees",
        "audience_size",
    ),
    "description": ("event_description", "about_event"),
    "objectives": ("event_objectives",),
}


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def apply_field_aliases(data: dict[str, Any], wanted: Optional[Iterable[str]] = None) -> dict[str, Any]:
    """Fill blank alias keys from their canonical value (in place); returns ``data``.

    ``wanted`` limits which alias keys get filled (e.g. the field keys of the selected
    templates) so the event record is not padded with unused synonyms.
    """
    wanted_set = set(wanted) if wanted is not None else None
    # `dates` is the human-readable range; fall back to the start date for one-day events.
    if _is_blank(data.get("dates")) and not _is_blank(data.get("date_start")):
        from docgen.functions import fn_format_date_range

        start = data.get("date_start")
        end = data.get("date_end") if not _is_blank(data.get("date_end")) else start
        try:
            data["dates"] = fn_format_date_range(start, end)
        except Exception:
            data["dates"] = start if end == start else f"{start} to {end}"

    for canonical, aliases in CANONICAL_ALIASES.items():
        value = data.get(canonical)
        if _is_blank(value):
            # Reverse direction: a user-answered alias can satisfy the canonical key.
            for alias in aliases:
                # Canonical values are scalars; a list (e.g. MoM `attendees` names) is not a count.
                if not _is_blank(data.get(alias)) and not isinstance(data.get(alias), (list, dict)):
                    data[canonical] = data[alias]
                    value = data[alias]
                    break
        if _is_blank(value) or isinstance(value, (list, dict)):
            continue
        for alias in aliases:
            if wanted_set is not None and alias not in wanted_set:
                continue
            if _is_blank(data.get(alias)):
                data[alias] = value
    return data
