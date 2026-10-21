"""Dates are read the Indian way (day first), except year-first dates, which are year-month-day."""

from datetime import date

from docgen.functions import _parse_date, fn_format_date, fn_format_date_range


def test_year_first_dates_are_year_month_day():
    assert _parse_date("2026-11-08") == date(2026, 11, 8)
    assert _parse_date("2026/11/08") == date(2026, 11, 8)
    assert fn_format_date("2026-11-08") == "08/11/2026"


def test_day_first_dates_stay_day_month_year():
    assert _parse_date("08/11/2026") == date(2026, 11, 8)
    assert _parse_date("8-11-2026") == date(2026, 11, 8)
    assert fn_format_date("08/11/2026") == "08/11/2026"


def test_written_dates():
    assert _parse_date("8 November 2026") == date(2026, 11, 8)


def test_date_range_from_year_first_dates():
    assert fn_format_date_range("2026-11-08", "2026-11-08") == "08/11/2026"
    assert fn_format_date_range("2026-11-08", "2026-11-09") == "8-9 November 2026"
