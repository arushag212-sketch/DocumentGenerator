"""Certificate prompts: grounded field filling, no invented dates, recognition wording, design."""

from __future__ import annotations

from docgen.extractors.event_extractor import _date_is_stated
from docgen.extractors.template_field_filler import fill_template_fields, value_is_grounded
from server.app.core.template_generator import (
    TemplateBlockSpec,
    TemplateDesignSpec,
    _is_recognition_statement,
    _sanitize_design,
)

PROMPT = (
    "create a certificate for acm summer challenge 2026 for the first palce name arush agrawal "
    "with a golden border and the sign of 3 judges"
)


class _StubLLM:
    def __init__(self, answer):
        self.answer = answer

    def is_available(self):
        return True

    def generate_json(self, prompt, schema):
        return self.answer


def test_grounding_accepts_user_words_and_typo_fixes_only():
    assert value_is_grounded("Arush Agrawal", PROMPT)
    assert value_is_grounded("First Place", PROMPT)  # "palce" typo corrected
    assert value_is_grounded("ACM Summer Challenge 2026", PROMPT)
    assert not value_is_grounded("Second Place", PROMPT)
    assert not value_is_grounded("IIT Bombay", PROMPT)
    assert not value_is_grounded("15 August 2026", PROMPT)


def test_filler_keeps_only_stated_values():
    fields = [
        {"key": "recipient_name", "type": "text"},
        {"key": "position", "type": "text"},
        {"key": "college", "type": "text"},
        {"key": "award_date", "type": "date"},
    ]
    llm = _StubLLM({
        "recipient_name": "Arush Agrawal",
        "position": "First Place",
        "college": "IIT Bombay",  # not in the prompt -> dropped
        "award_date": "2026",  # a bare year is not a date -> dropped
    })
    filled = fill_template_fields(PROMPT, fields, {}, llm)
    assert filled == {"recipient_name": "Arush Agrawal", "position": "First Place"}


def test_filler_ignores_null_like_answers_and_existing_values():
    fields = [{"key": "recipient_name", "type": "text"}, {"key": "position", "type": "text"}]
    filled = fill_template_fields(PROMPT, fields, {"position": "Winner"}, _StubLLM({"recipient_name": "null"}))
    assert filled == {}


def test_llm_dates_must_be_stated_in_text():
    text = "We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall"
    assert _date_is_stated("2026-10-14", text)
    assert _date_is_stated("2026-10-15", text)
    assert not _date_is_stated("2026-06-01", PROMPT)  # "summer" is not a date
    assert _date_is_stated("2026-03-05", "on 5/3/2026")


def test_certificate_recognition_line_is_kept_but_approvals_are_not():
    lead = TemplateBlockSpec(type="paragraph", content=[{"type": "text", "text": "This is to certify that"}])
    assert _is_recognition_statement(lead, "this is to certify that")

    achievement = TemplateBlockSpec(type="paragraph", content=[
        {"type": "text", "text": "has secured "},
        {"type": "fieldChip", "attrs": {"fieldName": "position"}},
        {"type": "text", "text": " place"},
    ])
    assert _is_recognition_statement(achievement, "has secured position place")

    approval = TemplateBlockSpec(type="paragraph", content=[
        {"type": "text", "text": "I certify the budget is approved for "},
        {"type": "fieldChip", "attrs": {"fieldName": "event_name"}},
    ])
    assert not _is_recognition_statement(approval, "i certify the budget is approved for")


def test_design_sanitizer_keeps_valid_values_only():
    design = TemplateDesignSpec(
        orientation="landscape",
        pageBorder="double",
        borderColor="b8860b",
        headingColor="gold",  # not a hex colour -> dropped
        headingFontFamily="Playfair Display",
        fontFamily="Comic Sans",  # not a bundled font -> dropped
        layout="certificate",
    )
    assert _sanitize_design(design) == {
        "orientation": "landscape",
        "pageBorder": "double",
        "borderColor": "#B8860B",
        "headingFontFamily": "Playfair Display",
        "layout": "certificate",
    }
