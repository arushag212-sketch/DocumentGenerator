"""Data-driven document recommendation.

Each template declares *when it is useful* in its schema, so adding a document type never
needs code changes:

    recommend:
      keywords: [permission, book, seminar hall]   # phrases that explicitly ask for it
      auto_when: [budget]          # signals that on their own call for it
      requires: [budget, bundle]   # at least one must hold (empty = no requirement)
      general_event: true          # include for a plain event description / full package
      suppress_when: [bills]       # not for these requests (unless a full package is asked for)
      reason: "Why it is recommended"
      reason_not: "Why it is not"

Templates without a ``recommend`` block (e.g. AI-drafted club templates) are recommended
only when their own trigger words appear in the request.
"""

from __future__ import annotations

import re
from typing import Any

EVENT_WORDS = re.compile(
    r"\b(workshop|hackathon|seminar|webinar|competition|contest|fest|festival|conference|bootcamp|"
    r"session|talk|lecture|meetup|expo|exhibition|tournament|challenge|camp|drive|night|event|jam|symposium|quiz|orientation|screening|ceremony|concert|show|performance|marathon|trek|summit|olympiad|ideathon|datathon)s?\b",
    re.IGNORECASE,
)
DESCRIBING_WORDS = re.compile(
    r"\b(conduct|conducting|organi[sz]e|organi[sz]ing|host|hosting|holding|planning|plan to|"
    r"we are|we're|we will|we'll|will be held|is being held|going to|run|running|scheduled)\b",
    re.IGNORECASE,
)
BUNDLE_WORDS = re.compile(
    r"\b(start to finish|full event|entire event|complete event|lifecycle|all documents|bundle|package|all stages)\b",
    re.IGNORECASE,
)
VENUE_WORDS = re.compile(
    r"\b(book|booking|hall|room|seminar hall|venue|lab|ground|auditorium)\b", re.IGNORECASE
)


NEED_WORDS = re.compile(r"\b(need|needs|needed|want|require|requires|required|request|requesting|get|use|using)\b", re.IGNORECASE)
CERTIFICATE_WORDS = re.compile(r"\bcertificates?\b", re.IGNORECASE)


def compute_signals(text: str, has_budget: bool, has_winners: bool, has_bills: bool, is_meeting: bool) -> dict[str, bool]:
    """Request features that templates' rules refer to by name."""
    describes_event = bool(EVENT_WORDS.search(text) and DESCRIBING_WORDS.search(text)) and not is_meeting
    return {
        "budget": has_budget,
        "winners": has_winners,
        "bills": has_bills,
        "meeting": is_meeting,
        "venue": bool(VENUE_WORDS.search(text)),
        # Asking for a place ("need the auditorium"), not just naming where something happens
        "venue_request": bool(VENUE_WORDS.search(text) and NEED_WORDS.search(text)),
        "bundle": bool(BUNDLE_WORDS.search(text)),
        "event_description": describes_event,
        "certificate": bool(CERTIFICATE_WORDS.search(text)),
    }


def _phrase_in(text_lower: str, phrase: str) -> bool:
    phrase = phrase.strip().lower()
    return bool(phrase) and re.search(rf"\b{re.escape(phrase)}\b", text_lower) is not None


DOC_NOUNS = {
    "certificate", "certificates", "form", "letter", "sheet", "pass", "report", "notice", "receipt",
    "requisition", "note", "memo", "invitation", "agreement", "undertaking", "list", "register", "minutes",
}
NAME_STOPWORDS = {"of", "and", "the", "a", "an", "to", "for", "in", "on", "with", "&", "-", "/"}


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def names_document(name: str, text_lower: str, club_words: set[str] | None = None) -> bool:
    """True when the request names this document: its document noun (if it has one) plus a
    distinctive word of its title, or every distinctive word when it has no document noun.

    "for ..." qualifiers and the club's own name are ignored, so "a sponsorship letter for our
    BAJA team" does not pull in "Travel Permission Letter for BAJA SAE India".
    """
    core = name.lower().split(" for ")[0]
    words = [w for w in re.findall(r"[a-z0-9]+", core) if w not in NAME_STOPWORDS]
    skip = {w.lower() for w in (club_words or set())}
    text_words = {_stem(w) for w in re.findall(r"[a-z0-9]+", text_lower)}
    nouns = [w for w in words if w in DOC_NOUNS]
    distinctive = [w for w in words if w not in DOC_NOUNS and w not in skip and not w.isdigit()]
    if not distinctive:
        return False
    hits = [w for w in distinctive if _stem(w) in text_words]
    if nouns and any(_stem(n) in text_words for n in nouns) and hits:
        return True
    # Without its document noun, every distinctive word must appear ("lab access" → Lab Access Requisition)
    return len(hits) == len(distinctive) and len(distinctive) <= 3


def evaluate(
    schema: dict[str, Any],
    signals: dict[str, bool],
    text: str,
    is_system: bool,
    name: str = "",
    club_words: set[str] | None = None,
) -> tuple[bool, str]:
    """(recommended, reason) for one template from its declared rules."""
    text_lower = text.lower()
    rules = schema.get("recommend")
    if not isinstance(rules, dict):
        # Club templates without rules: only when the request names the document itself.
        if not is_system and name and names_document(name, text_lower, club_words):
            return True, f"You asked for a {name.split(' for ')[0].strip()}."
        return False, "Club template; mention it by name to include it."

    keywords = [k for k in rules.get("keywords") or [] if isinstance(k, str)]
    auto_when = [s for s in rules.get("auto_when") or [] if isinstance(s, str)]
    requires = [s for s in rules.get("requires") or [] if isinstance(s, str)]
    suppress = [s for s in rules.get("suppress_when") or [] if isinstance(s, str)]
    general = bool(rules.get("general_event"))
    bundle = signals.get("bundle", False)

    requirement_met = not requires or any(signals.get(s) for s in requires)
    asked = any(_phrase_in(text_lower, k) for k in keywords)
    suppressed = any(signals.get(s) for s in suppress) and not bundle and not asked
    triggered = any(signals.get(s) for s in auto_when)
    general_match = general and (signals.get("event_description") or bundle)
    package_match = bundle and ("bundle" in requires or general)

    recommended = requirement_met and not suppressed and (asked or triggered or general_match or package_match)
    reason = rules.get("reason") if recommended else rules.get("reason_not")
    return recommended, str(reason or ("Recommended for this request." if recommended else "Not needed for this request."))
