"""Club-specific defaults built from the club's own record (never another club's values)."""

from __future__ import annotations

from typing import Any, Optional


def club_department(club: Any) -> tuple[str, str]:
    """(full, short) department names from club settings; empty when not configured."""
    settings = (getattr(club, "settings", None) or {}) if club is not None else {}
    full = str(settings.get("department") or "").strip()
    short = str(settings.get("department_short") or "").strip() or full
    return full, short


def institute_short(club: Any) -> str:
    settings = (getattr(club, "settings", None) or {}) if club is not None else {}
    return str(settings.get("institute_short") or "SVNIT")


def default_addressee(club: Any) -> str:
    """Who permission letters go to when a venue has no addressee of its own."""
    full, _ = club_department(club)
    return f"Head of Department, {full}" if full else "Head of Department"


def default_signatures(club: Any, columns: int = 3) -> list[dict[str, str]]:
    """Signature boxes for new templates: the club's own name and department."""
    _, short = club_department(club)
    inst = institute_short(club)
    dept_line = f"{short}, {inst}" if short else inst
    club_name: Optional[str] = getattr(club, "name", None) if club is not None else None
    signatures = [
        {"label": "Student Coordinator", "designation": club_name or ""},
        {"label": "Faculty Advisor", "designation": dept_line},
        {"label": "Head of Department", "designation": dept_line},
    ]
    return signatures[:columns]
