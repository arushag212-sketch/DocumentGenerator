"""Computed-function registry for template schemas.

Every function here is pure (no side-effects), operates on Decimal where
money is involved, and is referenced by name in schema.yaml files.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable

from num2words import num2words


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Callable] = {}


def register(name: str):
    """Decorator to register a computed function."""
    def decorator(fn: Callable):
        _REGISTRY[name] = fn
        return fn
    return decorator


def get_function(name: str) -> Callable:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown computed function: {name!r}. "
                       f"Available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def list_functions() -> list[str]:
    return sorted(_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

@register("sum")
def fn_sum(items: list[Any], field: str = "amount") -> Decimal:
    """Sum a numeric field across a list of dicts or objects."""
    total = Decimal("0")
    for item in items:
        if isinstance(item, dict):
            val = item.get(field, 0)
        else:
            val = getattr(item, field, 0)
        total += Decimal(str(val))
    return total


@register("line_total")
def fn_line_total(qty: int, unit_cost: Any) -> Decimal:
    """qty × unit_cost, both converted to Decimal."""
    return Decimal(str(qty)) * Decimal(str(unit_cost))


@register("tax_amount")
def fn_tax_amount(subtotal: Any, rate: Any) -> Decimal:
    """Compute tax = subtotal × rate / 100."""
    return (Decimal(str(subtotal)) * Decimal(str(rate)) / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


@register("total_with_tax")
def fn_total_with_tax(subtotal: Any, tax: Any) -> Decimal:
    return Decimal(str(subtotal)) + Decimal(str(tax))


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

@register("format_inr")
def fn_format_inr(amount: Any) -> str:
    """Format a number in Indian grouping: 1,00,000.00"""
    d = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if d < 0 else ""
    d = abs(d)
    int_part, dec_part = str(d).split(".")

    if len(int_part) <= 3:
        formatted = int_part
    else:
        # Last 3 digits, then groups of 2
        last3 = int_part[-3:]
        rest = int_part[:-3]
        groups = []
        while rest:
            groups.append(rest[-2:])
            rest = rest[:-2]
        groups.reverse()
        formatted = ",".join(groups) + "," + last3

    return f"{sign}{formatted}.{dec_part}"


@register("amount_in_words_inr")
def fn_amount_in_words_inr(amount: Any) -> str:
    """Convert amount to Indian English words with Rupees/Paise."""
    d = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    int_part = int(d)
    paise = int((d - int_part) * 100)

    words = _indian_number_to_words(int_part)
    result = f"Rupees {words.title()}"
    if paise:
        paise_words = num2words(paise, lang="en")
        result += f" and {paise_words.title()} Paise"
    result += " Only"
    return result


def _indian_number_to_words(n: int) -> str:
    """Convert integer to Indian English words (Lakh, Crore system)."""
    if n == 0:
        return "zero"

    crore = n // 10000000
    n %= 10000000
    lakh = n // 100000
    n %= 100000
    thousand = n // 1000
    n %= 1000
    hundred = n // 100
    remainder = n % 100

    parts = []
    if crore:
        parts.append(f"{num2words(crore, lang='en')} crore")
    if lakh:
        parts.append(f"{num2words(lakh, lang='en')} lakh")
    if thousand:
        parts.append(f"{num2words(thousand, lang='en')} thousand")
    if hundred:
        parts.append(f"{num2words(hundred, lang='en')} hundred")
    if remainder:
        parts.append(num2words(remainder, lang="en"))

    return " ".join(parts)


@register("ordinal")
def fn_ordinal(n: int) -> str:
    """1 -> '1st', 2 -> '2nd', etc."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    # Year-first dates (2026-11-08, as the AI and date pickers send them) are year-month-day.
    # dayfirst=True below would read them as year-day-month.
    if re.match(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", s):
        try:
            from dateutil.parser import parse as parse_date
            return parse_date(s, yearfirst=True, dayfirst=False).date()
        except Exception:
            pass
    try:
        from dateutil.parser import parse as parse_date
        return parse_date(s, dayfirst=True).date()
    except Exception:
        pass
    try:
        import dateparser
        parsed = dateparser.parse(s)
        if parsed:
            return parsed.date()
    except Exception:
        pass
    return None


@register("format_date")
def fn_format_date(d: Any, fmt: str = "%d/%m/%Y") -> str:
    """Format a date object or string to standardized format (default: DD/MM/YYYY)."""
    if not d:
        return ""
    if isinstance(d, str):
        import re
        if re.match(r'^\d{2}/\d{2}/\d{4}$', d):
            return d
    parsed = _parse_date(d)
    if parsed:
        return parsed.strftime(fmt)
    return str(d)


@register("format_date_range")
def fn_format_date_range(start: Any, end: Any) -> str:
    """Format a date range intelligently with DD/MM/YYYY consistency."""
    if not start and not end:
        return ""
    if start and not end:
        return fn_format_date(start)
    if end and not start:
        return fn_format_date(end)

    d_start = _parse_date(start)
    d_end = _parse_date(end)

    if isinstance(d_start, date) and isinstance(d_end, date):
        if d_start == d_end:
            return d_start.strftime("%d/%m/%Y")
        if d_start.month == d_end.month and d_start.year == d_end.year:
            return f"{d_start.day}-{d_end.day} {d_start.strftime('%B %Y')}"
        elif d_start.year == d_end.year:
            return f"{d_start.day} {d_start.strftime('%B')} - {d_end.day} {d_end.strftime('%B %Y')}"
        else:
            return f"{d_start.day} {d_start.strftime('%B %Y')} - {d_end.day} {d_end.strftime('%B %Y')}"

    return f"{start} - {end}" if start != end else str(start)


@register("short_year")
def fn_short_year(academic_year: str) -> str:
    """'2026-27' -> '26-27'"""
    parts = academic_year.split("-")
    if len(parts) == 2:
        return f"{parts[0][-2:]}-{parts[1][-2:]}"
    return academic_year


@register("format_ref_no")
def fn_format_ref_no(fmt: str, **kwargs) -> str:
    """Format a reference number from a format string.
    
    Example: 'ACM/{short_year}/{series}/{seq:03d}'
    """
    return fmt.format(**kwargs)


@register("today")
def fn_today(fmt: str = "%d/%m/%Y") -> str:
    return date.today().strftime(fmt)


@register("sr_no")
def fn_sr_no(index: Any = 0) -> int:
    """1-based serial number from 0-based index."""
    if index is None:
        return 1
    try:
        return int(index) + 1
    except (ValueError, TypeError):
        return 1


@register("format_time")
def fn_format_time(val: Any) -> str:
    """Format a 24-hour time string (e.g. '10:00', '17:00') into 12-hour club format ('10:00 AM', '05:00 PM')."""
    if not val:
        return ""
    s = str(val).strip()
    m12 = re.match(r'^(0?[1-9]|1[0-2])(?::([0-5]\d))?\s*(AM|PM|am|pm)$', s)
    if m12:
        h = int(m12.group(1))
        m = int(m12.group(2)) if m12.group(2) else 0
        ampm = m12.group(3).upper()
        return f"{h:02d}:{m:02d} {ampm}"
    m24 = re.match(r'^([01]?\d|2[0-3])(?::([0-5]\d))?$', s)
    if m24:
        h24 = int(m24.group(1))
        m = int(m24.group(2)) if m24.group(2) else 0
        ampm = "AM" if h24 < 12 else "PM"
        h12 = h24 % 12
        if h12 == 0:
            h12 = 12
        return f"{h12:02d}:{m:02d} {ampm}"
    return s
