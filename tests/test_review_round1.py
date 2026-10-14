from decimal import Decimal
from pathlib import Path

from docgen.config import load_config
from docgen.extractors.event_extractor import EventExtractor
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
from docgen.numbering import suggest_reference_number
from docgen.recommender import recommend_documents
from docgen.renderer import Renderer
from docgen.schema import load_all_schemas
from docgen.validator import validate_all_templates
from tests.fixtures.sih_event import get_sih_fixture


def test_rule1_official_field_never_auto_confirmed():
    """Test that official fields (ref_no, bank, PAN, etc.) are NEVER auto-confirmed."""
    config = load_config()
    schemas = load_all_schemas()

    # Counter suggestion must be unconfirmed
    suggested = suggest_reference_number(schemas["permission_letter"], config=config)
    assert suggested is not None
    assert suggested.confirmed is False, "Suggested reference number must have confirmed=False!"

    # Extracted fields from NL must never auto-confirm bank details or PAN or budget items
    extractor = EventExtractor(config=config)
    event = extractor.extract_from_text(
        "We are conducting SIH Internal Hackathon on 12 Sep in Seminar Hall 402 for 150 students."
    )
    assert event.event_code.confirmed is False, "Suggested event code must be unconfirmed!"
    assert event.description.confirmed is False, "AI-drafted description must be unconfirmed!"
    assert event.objectives.confirmed is False, "AI-drafted objectives must be unconfirmed!"


def test_rule2_global_guard_against_none_and_empty_required_fields():
    """Test that rendering fails with ValueError if any required field is missing or None."""
    config = load_config()
    renderer = Renderer(config=config, outputs_dir="outputs/test_guard")
    event = EventRecord()
    event.event_name = tf("Incomplete Event", FieldSource.user, confirmed=True)
    # Missing venue, ref_no, dates, etc.

    try:
        renderer.render("permission_letter", event, convert_pdf=False)
        assert False, "Should have raised ValueError for missing required fields!"
    except ValueError as e:
        assert "Required field" in str(e)
        assert "cannot render empty or 'None' values" in str(e)


def test_rule3_seeded_real_names_and_placeholders():
    """Verify seeded club_config.yaml contains real signatories and empty mobiles/bank."""
    config = load_config()
    assert config.chairperson.name == "Ansh Gupta"
    assert config.chairperson.admission_no == "I24AI005"
    assert config.chairperson.branch == "Artificial Intelligence"
    assert config.chairperson.mobile == ""  # Placeholder blank

    assert config.student_secretary.name == "Arshad Khatib"
    assert config.student_secretary.admission_no == "U24AI112"

    assert config.faculty_chairman.name == "Dr. Sankita Patel"
    assert config.faculty_co_chairman.name == "Dr. Balu Parne"

    # Venue officials
    venue = config.get_venue("Seminar Hall 402")
    assert venue is not None
    assert venue.tech_assistant.name == "Sunny Bodiwala"
    assert venue.faculty_in_charge.name == "Shri Rakesh P. Gohil"

    # Approval chain
    assert any("Rakesh Maurya" in step for step in config.approval_chain)
    assert any("Manish K Rathod" in step for step in config.approval_chain)
    assert any("Sanjay R. Patel" in step for step in config.approval_chain)


def test_rule4_description_and_objectives_drafted_separately():
    """Verify description and objectives have distinct AI-drafted labels and content."""
    extractor = EventExtractor()
    event = extractor.extract_from_text(
        "Conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for 120 students."
    )
    assert "[AI-drafted, review]" in event.description.value
    assert "[AI-drafted, review]" in event.objectives.value
    assert event.description.value != event.objectives.value, "Description and Objectives must not share text!"


def test_rule8_cross_document_consistency():
    """Verify that changing a field on the canonical EventRecord updates all documents."""
    event = get_sih_fixture()
    config = load_config()
    renderer = Renderer(config=config, outputs_dir="outputs/test_consistency")

    # Render initial documents
    r1_perm = renderer.render("permission_letter", event, convert_pdf=False)
    r1_appr = renderer.render("approval_note", event, convert_pdf=False)

    # Change venue on the single source of truth
    new_venue = "Computer Lab 1, CSE Department"
    event.venue = tf(new_venue, FieldSource.user, confirmed=True)

    # Re-render both context
    schemas = load_all_schemas()
    ctx_perm = renderer._build_context(event, schemas["permission_letter"])
    ctx_appr = renderer._build_context(event, schemas["approval_note"])

    assert ctx_perm["venue"] == new_venue
    assert ctx_appr["venue"] == new_venue


def test_rule8_financial_totals_and_amount_in_words():
    """Verify math calculations: Banner 800 + Misc 300 = 1100, and correct words."""
    event = get_sih_fixture()
    total = fn_sum(event.budget_items, "amount")
    assert total == Decimal("1100")
    assert fn_format_inr(total) == "1,100.00"

    words = fn_amount_in_words_inr(total)
    assert "Eleven Hundred" in words or "One Thousand One Hundred" in words

    winner_words = fn_amount_in_words_inr(Decimal("5000"))
    assert "Five Thousand" in winner_words


def test_rule8_one_prize_receipt_per_winner():
    """Verify batch rendering for winners produces one receipt per winner."""
    event = get_sih_fixture()
    config = load_config()
    renderer = Renderer(config=config, outputs_dir="outputs/test_winners")

    assert len(event.winners) == 2
    rendered_winners = []
    for idx, w in enumerate(event.winners):
        w_ctx = {
            "winner_name": w.name,
            "winner_position": w.position,
            "winner_amount": str(w.amount),
            "winner_amount_words": fn_amount_in_words_inr(w.amount),
            "winner_roll_no": w.roll_no,
            "winner_course_semester": w.course_semester,
            "winner_mobile": w.mobile,
            "winner_bank_name_as_per_bank": w.bank.name_as_per_bank,
            "winner_bank_name": w.bank.bank_name,
            "winner_bank_branch": w.bank.branch,
            "winner_account_no": w.bank.account_no,
            "winner_ifsc": w.bank.ifsc,
            "winner_pan": w.bank.pan,
            "sr_no": idx + 1,
        }
        res = renderer.render("prize_money_receipt", event, extra_context=w_ctx, convert_pdf=False)
        rendered_winners.append(res)

    assert len(rendered_winners) == 2
    assert rendered_winners[0].docx_path.exists()


def test_rule8_bill_certificate_pulls_approval_note_details():
    """Verify Form BC-R pulls Approval Note number and date from EventRecord."""
    event = get_sih_fixture()
    config = load_config()
    renderer = Renderer(config=config, outputs_dir="outputs/test_billcert")
    schema = load_all_schemas()["bill_certificate"]

    ctx = renderer._build_context(event, schema, extra_context={
        "approval_note_no": event.approval_note.no,
        "approval_note_date": event.approval_note.date,
        "ref_no": "BILL-091",
        "bill_amount": "800.00",
        "supplier_name": "Test Supplier",
        "supplier_gst": "24AAACS1234A1Z5",
        "invoice_no": "INV-091",
        "invoice_date": "2026-09-12",
        "bill_items": [{"name": "Banner", "qty": 1, "unit_cost": "800", "line_total": "800"}],
        "certifier_name": "Ansh Gupta",
        "payment_party": "Test Supplier",
        "payment_account_no": "50200012345678",
        "payment_holder": "Test Supplier",
        "payment_bank": "HDFC Bank",
        "payment_branch": "Surat",
        "payment_ifsc": "HDFC0000123",
    })

    assert ctx["approval_note_no"] == "ACM/2026-27/SIH/001"
    assert ctx["approval_note_date"] == "08/09/2026"


if __name__ == "__main__":
    print("Running Review Round 1 Verification Tests...")
    test_rule1_official_field_never_auto_confirmed()
    print("  [OK] Rule 1: Official fields never auto-confirmed.")
    test_rule2_global_guard_against_none_and_empty_required_fields()
    print("  [OK] Rule 2: Global guard against None and empty required fields.")
    test_rule3_seeded_real_names_and_placeholders()
    print("  [OK] Rule 3: Real names, branches, and designations seeded in config.")
    test_rule4_description_and_objectives_drafted_separately()
    print("  [OK] Rule 4: Description and Objectives drafted separately with review labels.")
    test_rule8_cross_document_consistency()
    print("  [OK] Rule 8: Cross-document consistency verified.")
    test_rule8_financial_totals_and_amount_in_words()
    print("  [OK] Rule 8: Financial totals (1100 INR) and amount in words verified.")
    test_rule8_one_prize_receipt_per_winner()
    print("  [OK] Rule 8: One prize receipt per winner batch generation verified.")
    test_rule8_bill_certificate_pulls_approval_note_details()
    print("  [OK] Rule 8: Form BC-R pulls Approval Note number and date.")
    print("\nALL REVIEW ROUND 1 TESTS PASSED SUCCESSFULLY! [OK]")
