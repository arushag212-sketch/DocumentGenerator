"""Comprehensive test suite for ACM Document Generator."""

from decimal import Decimal
from docgen.config import ClubConfig
from docgen.functions import (
    fn_amount_in_words_inr,
    fn_format_date_range,
    fn_format_inr,
    fn_line_total,
    fn_ordinal,
    fn_short_year,
    fn_sum,
)
from docgen.models import BudgetItem, EventRecord, FieldSource, tf
from docgen.extractors.event_extractor import EventExtractor
from docgen.recommender import recommend_documents
from docgen.missing_fields import detect_missing_fields
from docgen.schema import load_all_schemas
from docgen.validator import validate_all_templates


def test_functions():
    # Indian currency grouping
    assert fn_format_inr("100000") == "1,00,000.00"
    assert fn_format_inr(Decimal("1234567.5")) == "12,34,567.50"

    # Amount in words
    words = fn_amount_in_words_inr(Decimal("1100"))
    assert "Eleven Hundred" in words or "One Thousand One Hundred" in words

    # Ordinals
    assert fn_ordinal(1) == "1st"
    assert fn_ordinal(2) == "2nd"
    assert fn_ordinal(3) == "3rd"
    assert fn_ordinal(4) == "4th"

    # Line totals
    assert fn_line_total(3, Decimal("250.50")) == Decimal("751.50")

    # Sum
    items = [{"amount": Decimal("100")}, {"amount": Decimal("250")}]
    assert fn_sum(items) == Decimal("350")

    # Short year
    assert fn_short_year("2026-27") == "26-27"


def test_natural_language_extractor():
    text = "We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students."
    extractor = EventExtractor()
    event = extractor.extract_from_text(text)

    assert event.event_name.value == "Web Development Workshop"
    assert event.category.value == "Workshop"
    assert event.expected_participants.value == 120
    assert "Seminar Hall" in (event.venue.value or "")


def test_template_validation():
    results = validate_all_templates()
    for res in results:
        assert res.is_valid, f"Template {res.template_id} failed: {res.errors}"


def test_missing_field_detection():
    event = EventRecord()
    event.event_name = tf("Test Event", FieldSource.user, confirmed=True)
    schemas = load_all_schemas()

    report = detect_missing_fields(event, [schemas["permission_letter"]])
    missing_keys = [m.key for m in report.missing]

    assert "venue" in missing_keys
    assert "ref_no" in missing_keys


if __name__ == "__main__":
    print("Running tests...")
    test_functions()
    print("  [OK] Computed functions verified.")
    test_natural_language_extractor()
    print("  [OK] NL Event extractor verified.")
    test_template_validation()
    print("  [OK] All template schemas & DOCX tags verified.")
    test_missing_field_detection()
    print("  [OK] Missing field detector verified.")
    print("All tests passed successfully! [OK]")
