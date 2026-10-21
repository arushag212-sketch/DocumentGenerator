"""Fill a selected template's own fields from the user's sentence with the LLM.

Rule extraction only knows canonical event facts (event name, venue, dates, ...). Custom and
AI-designed templates ask for things like recipient_name or position. This asks the LLM to
read those values out of the user's text, then keeps a value only when every word in it
appears in that text (tolerating small typos such as "palce" -> "Place"), so nothing the
user did not say can reach a document.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Optional

logger = logging.getLogger(__name__)

FILLABLE_TYPES = {"text", "longtext", "int", "money", "date", "date_range", "time_range", "enum"}
_WORD = re.compile(r"[a-z0-9]+")
_MONTH_OR_NUMERIC_DATE = re.compile(
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}\s*[/.-]\s*\d{1,2}|\d{4}-\d{2}-\d{2}"
)


def _words(text: str) -> list[str]:
    return _WORD.findall(str(text).lower())


def value_is_grounded(value: Any, source_text: str, min_ratio: float = 0.75) -> bool:
    """True when every word of ``value`` matches (or nearly matches) a word in ``source_text``."""
    value_words = _words(value)
    if not value_words:
        return False
    source_words = set(_words(source_text))
    for word in value_words:
        if word in source_words:
            continue
        if word.isdigit():
            return False
        if not any(len(s) >= 3 and SequenceMatcher(None, word, s).ratio() >= min_ratio for s in source_words):
            return False
    return True


def fill_template_fields(
    text: str,
    fields: list[dict[str, Any]],
    data: dict[str, Any],
    llm: Any,
) -> dict[str, Any]:
    """Return {field_key: value} for blank fields whose values the user's text states."""
    wanted = [
        f for f in fields
        if f.get("key") and (f.get("type") or "text") in FILLABLE_TYPES and data.get(f["key"]) in (None, "", [])
    ]
    if not wanted or llm is None or not getattr(llm, "is_available", lambda: False)():
        return {}

    schema = {
        "type": "object",
        "properties": {
            f["key"]: {"type": "string", "description": str(f.get("ask") or f.get("label") or f["key"])[:200]}
            for f in wanted
        },
    }
    prompt = (
        "Read the user's request and copy out the value for each field ONLY if the request states it.\n"
        "Use the user's own words; you may fix capitalisation and obvious spelling mistakes.\n"
        "Leave a field as an empty string when the request does not state it. Never guess.\n\n"
        f"USER REQUEST:\n{text}"
    )
    try:
        raw = llm.generate_json(prompt, schema) or {}
    except Exception as exc:  # AI is optional here; missing fields are simply asked for
        logger.info("Template field fill skipped: %s", exc)
        return {}

    filled: dict[str, Any] = {}
    for f in wanted:
        value: Optional[Any] = raw.get(f["key"]) if isinstance(raw, dict) else None
        if isinstance(value, str):
            value = value.strip()
            if value.lower() in ("null", "none", "n/a", "unknown"):
                continue
        if value in (None, "") or not value_is_grounded(value, text):
            continue
        if (f.get("type") or "text") in ("date", "date_range") and not _MONTH_OR_NUMERIC_DATE.search(str(value).lower()):
            continue  # a bare year ("2026") is not a date
        filled[f["key"]] = value
    return filled
