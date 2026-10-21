"""Input validation and canonical formatting for Phase W7 input widgets.

Rules:
- time and time_range: native pickers (<input type="time">), canonical 24-hour "HH:MM".
  time_range validated so end is after start; formatted for documents as "09:00 AM" / "05:00 PM".
- date and date_range: native date pickers, canonical ISO "YYYY-MM-DD" or "DD/MM/YYYY".
  date_range validated so end is not before start; formatted as "DD/MM/YYYY" or "14-15 October 2026".
- int: min 0, non-negative whole number.
- money: non-negative decimal amount.
- All errors returned in clear, plain language without jargon.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional
from fastapi import HTTPException, status


def parse_time_to_minutes(val: Any) -> Optional[int]:
    """Parse time string into minutes since midnight."""
    if not val:
        return None
    s = str(val).strip()

    # 12-hour format e.g. "09:00 AM", "5:00 PM", "10 AM", "4 PM", "10am", "4pm"
    m12 = re.match(r'^(0?[1-9]|1[0-2])(?::([0-5]\d))?\s*(AM|PM|am|pm)$', s)
    if m12:
        h = int(m12.group(1))
        m = int(m12.group(2)) if m12.group(2) else 0
        ampm = m12.group(3).upper()
        if ampm == "PM" and h != 12:
            h += 12
        elif ampm == "AM" and h == 12:
            h = 0
        return h * 60 + m

    # 24-hour format e.g. "09:00", "17:00", "9:00"
    m24 = re.match(r'^([01]?\d|2[0-3]):([0-5]\d)$', s)
    if m24:
        h = int(m24.group(1))
        m = int(m24.group(2))
        return h * 60 + m

    # Plain hour e.g. "10", "16", "9"
    m_hour = re.match(r'^([01]?\d|2[0-3])$', s)
    if m_hour:
        h = int(m_hour.group(1))
        return h * 60

    return None


def format_time_display(val: Any) -> str:
    """Format time string into canonical 12-hour format for official documents ('09:00 AM', '05:00 PM')."""
    if not val:
        return ""
    mins = parse_time_to_minutes(val)
    if mins is None:
        return str(val)

    h24 = mins // 60
    m = mins % 60
    ampm = "AM" if h24 < 12 else "PM"
    h12 = h24 % 12
    if h12 == 0:
        h12 = 12
    return f"{h12:02d}:{m:02d} {ampm}"


def format_time_canonical_24h(val: Any) -> str:
    """Format time string into canonical 24-hour 'HH:MM' for HTML input type='time'."""
    if not val:
        return ""
    mins = parse_time_to_minutes(val)
    if mins is None:
        return ""
    h24 = mins // 60
    m = mins % 60
    return f"{h24:02d}:{m:02d}"


def parse_date_value(val: Any) -> Optional[date]:
    """Parse string or date into Python date object."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()

    # ISO format YYYY-MM-DD
    m_iso = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', s)
    if m_iso:
        try:
            return date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
        except ValueError:
            pass

    # DD/MM/YYYY format
    m_dmy = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', s)
    if m_dmy:
        try:
            return date(int(m_dmy.group(3)), int(m_dmy.group(2)), int(m_dmy.group(1)))
        except ValueError:
            pass

    try:
        from dateutil.parser import parse as parse_date
        return parse_date(s, dayfirst=True).date()
    except Exception:
        pass

    return None


def validate_time_range(time_start: Any, time_end: Any) -> None:
    """Validate that start and end times are valid and end is strictly after start."""
    if not time_start or not time_end:
        return

    start_mins = parse_time_to_minutes(time_start)
    if start_mins is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TIME", "message": f"Invalid start time: '{time_start}'."},
        )

    end_mins = parse_time_to_minutes(time_end)
    if end_mins is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TIME", "message": f"Invalid end time: '{time_end}'."},
        )

    if end_mins <= start_mins:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TIME_RANGE", "message": "End time must be after start time."},
        )


def validate_date_range(date_start: Any, date_end: Any) -> None:
    """Validate that start and end dates are valid and end is not before start."""
    if not date_start or not date_end:
        return

    d_start = parse_date_value(date_start)
    if not d_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DATE", "message": f"Invalid start date: '{date_start}'."},
        )

    d_end = parse_date_value(date_end)
    if not d_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DATE", "message": f"Invalid end date: '{date_end}'."},
        )

    if d_end < d_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DATE_RANGE", "message": "End date cannot be before start date."},
        )


def validate_input_fields(data: dict[str, Any]) -> None:
    """Validate all event inputs against widget and schema type constraints."""
    # 1. Times
    t_start = data.get("time_start")
    t_end = data.get("time_end")
    if t_start and t_end:
        validate_time_range(t_start, t_end)
    elif t_start:
        if parse_time_to_minutes(t_start) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_TIME", "message": f"Invalid time: '{t_start}'."},
            )
    elif t_end:
        if parse_time_to_minutes(t_end) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_TIME", "message": f"Invalid time: '{t_end}'."},
            )

    # 2. Dates
    d_start = data.get("date_start")
    d_end = data.get("date_end")
    if d_start and d_end:
        validate_date_range(d_start, d_end)
    elif d_start:
        if parse_date_value(d_start) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_DATE", "message": f"Invalid date: '{d_start}'."},
            )
    elif d_end:
        if parse_date_value(d_end) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_DATE", "message": f"Invalid date: '{d_end}'."},
            )

    # 3. Numeric fields
    part_key = "participants" if "participants" in data and data["participants"] is not None else ("expected_participants" if "expected_participants" in data and data["expected_participants"] is not None else None)
    if part_key and data[part_key] is not None and str(data[part_key]).strip() != "":
        try:
            p_val = int(data[part_key])
            if p_val < 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_INTEGER", "message": "Participants must be a non-negative whole number."},
            )

    # 4. Money fields in winners
    for idx, w in enumerate(data.get("winners") or []):
        if isinstance(w, dict):
            amt = w.get("amount") if w.get("amount") is not None else w.get("prize_amount")
            if amt is not None:
                try:
                    f_amt = float(amt)
                    if f_amt < 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"code": "INVALID_AMOUNT", "message": f"Winner #{idx + 1} prize amount must be a valid positive amount."},
                    )

    # 5. Budget items validation
    if "budget_items" in data and data["budget_items"]:
        from docgen.models import coerce_to_budget_items
        b_items = coerce_to_budget_items(data["budget_items"])
        for idx, b in enumerate(b_items):
            if b.amount < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "INVALID_AMOUNT", "message": f"Budget item #{idx + 1} amount cannot be negative."},
                )
