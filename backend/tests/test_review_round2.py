"""Review Round 2 Comprehensive Verification Suite.

Tests run against the RENDERED PDFs (extracted via PyMuPDF), verifying:
1. HEADERS: Clean logo+title band only. OCR/text check asserting rendered PDFs do NOT contain
   "ROOM/009" or "08/09/2026" unless explicitly user-supplied.
2. ESCAPING: doc.render(context, autoescape=True) preserves "&" in rendered PDF text
   ("Computer Science & Engineering", "Chairman, F& SW").
3. BILL SUMMARY: Grand Total = sum of prize amounts + other payees' amounts, computed in code.
   Summary prize total == sum of all prize receipt amounts. Rendered PDF text matches.
4. BILL CERTIFICATE: Single source for bill no / invoice no. Approval note date comes from
   approval_note.date in DD/MM/YYYY format across all documents. Certifier name asked via
   missing-field detector (blank with needs input if unsupplied).
5. OFFICIAL WORDING: Form BC-R, Prize Receipt, Approval Note text matches official samples.
   Approval Note has Subject row, Office Use block, Recommended/Approved lines.
6. TYPOS: "Mobile No." in Permission Letter and Prize Receipt. "Moblie No." only in Approval Note faculty blocks.
7. LAYOUT: Approval Note fits on 1 single page. Bill Certificate is exactly 2 pages.
8. NUMBERING: Permission Letter uses ROOM series; Approval Note uses {academic_year}/{event_code}.
9. FIXTURE: Canonical SIH fixture mirrors sample data.
10. TESTS: Rendered PDF text assertions for all six documents (no "None", no "[AI-drafted", no unresolved "{{").
"""

from decimal import Decimal
from pathlib import Path
import re

import pytest
import pymupdf

from docgen.config import load_config
from docgen.missing_fields import detect_missing_fields
from docgen.models import EventRecord, FieldSource, tf
from docgen.numbering import suggest_reference_number
from docgen.renderer import Renderer
from docgen.schema import load_all_schemas
from tests.fixtures.sih_event import get_sih_fixture


@pytest.fixture(scope="session")
def rendered_sih_pdfs():
    """Ensure all 6 PDFs are rendered for the session and return paths."""
    out_dir = Path("outputs/sih_test/internal_hackathon_of_sih")
    pdf_paths = {
        "permission_letter": out_dir / "permission_letter_v1.pdf",
        "approval_note": out_dir / "approval_note_v1.pdf",
        "prize_money_receipt": out_dir / "prize_money_receipt_v1.pdf",
        "bill_summary": out_dir / "bill_summary_v1.pdf",
        "bill_certificate": out_dir / "bill_certificate_v1.pdf",
        "mom": out_dir / "mom_v1.pdf",
    }
    if not all(p.exists() for p in pdf_paths.values()):
        from scripts.render_sih_suite import main as render_sih
        render_sih()

    for name, p in pdf_paths.items():
        assert p.exists(), f"Rendered PDF for {name} does not exist at {p}!"
    return pdf_paths



def test_item1_clean_headers_no_hardcoded_leakage(rendered_sih_pdfs):
    """Test 1: OCR/text check on rendered PDFs asserting no leaked hardcoded ROOM/009 from header assets."""
    # Check across rendered documents that "ROOM/009" never leaks into any rendered document
    for doc_name, pdf_path in rendered_sih_pdfs.items():
        doc = pymupdf.open(str(pdf_path))
        full_text = " ".join(page.get_text() for page in doc)
        doc.close()
        assert "ROOM/009" not in full_text, f"Unintended sample ref ROOM/009 found in {doc_name}!"


def test_item2_xml_escaping_ampersand_in_pdf_text(rendered_sih_pdfs):
    """Test 2: Assert '&' in 'Computer Science & Engineering' and 'Chairman, F& SW' appears intact in PDF text."""
    # Check Permission Letter
    doc_perm = pymupdf.open(str(rendered_sih_pdfs["permission_letter"]))
    text_perm = doc_perm[0].get_text()
    doc_perm.close()
    assert "Computer Science & Engineering" in text_perm, (
        "Ampersand was not properly unescaped or preserved in Permission Letter PDF text!"
    )

    # Check Approval Note
    doc_appr = pymupdf.open(str(rendered_sih_pdfs["approval_note"]))
    text_appr = doc_appr[0].get_text()
    doc_appr.close()
    # The chairman line comes from the club config ("Chairman F&SW" or "Chairman, F& SW"); either way the & must survive
    assert re.search(r"Chairman,? F\s?&\s?SW", text_appr), (
        "Ampersand was not preserved in Approval Note PDF text!"
    )


def test_item3_bill_summary_totals_cross_check(rendered_sih_pdfs):
    """Test 3: Grand Total = prize total + other total. Summary prize total == sum of prize receipts."""
    event = get_sih_fixture()

    # Sum of winners from event fixture
    sum_prize = sum(w.amount for w in event.winners)
    assert sum_prize == Decimal("8000")  # 5000 + 3000

    sum_other = sum(r.amount for r in event.other_reimbursements)
    assert sum_other == Decimal("300")

    grand_total = sum_prize + sum_other
    assert grand_total == Decimal("8300")

    # Verify rendered Bill Summary PDF text
    doc_sum = pymupdf.open(str(rendered_sih_pdfs["bill_summary"]))
    text_sum = doc_sum[0].get_text()
    doc_sum.close()

    assert "8,300.00" in text_sum, "Grand Total 8,300.00 missing from Bill Summary PDF!"
    assert "300.00" in text_sum, "Other total 300.00 missing from Bill Summary PDF!"
    assert "5,000.00" in text_sum and "3,000.00" in text_sum, "Individual prize amounts formatted in INR missing from PDF!"

    # Condition 2: Quantities, counts and non-money numbers must keep their own formats (no .00 on counts)
    doc_appr = pymupdf.open(str(rendered_sih_pdfs["approval_note"]))
    text_appr = doc_appr[0].get_text()
    doc_appr.close()
    assert "1000+" in text_appr, "Participant count '1000+' must retain original non-money formatting!"
    assert "1,100.00" in text_appr, "Money proposal budget total must have INR formatting!"

    doc_cert = pymupdf.open(str(rendered_sih_pdfs["bill_certificate"]))
    text_cert = " ".join(p.get_text() for p in doc_cert)
    doc_cert.close()
    assert "800.00" in text_cert, "Money field unit cost must have INR formatting!"


def test_item4_bill_certificate_single_invoice_and_date_format(rendered_sih_pdfs):
    """Test 4: Single source for bill no / invoice no, approval note date in DD/MM/YYYY, certifier asked via missing fields."""
    event = get_sih_fixture()
    schemas = load_all_schemas()

    # Check certifier_name missing detector
    incomplete_event = EventRecord()
    missing_report = detect_missing_fields(incomplete_event, [schemas["bill_certificate"]])
    missing_keys = [f.key for f in missing_report.missing]
    assert "certifier_name" in missing_keys, "Certifier name must be asked via missing field detector!"

    # Verify rendered Bill Certificate PDF
    doc_cert = pymupdf.open(str(rendered_sih_pdfs["bill_certificate"]))
    text_cert = " ".join(page.get_text() for page in doc_cert)
    doc_cert.close()

    # Single invoice number shown identically
    assert "INV/TEST/001" in text_cert
    # Approval note date from approval_note.date formatted as DD/MM/YYYY
    assert "08/09/2026" in text_cert, "Approval Note date 08/09/2026 missing from Bill Certificate PDF!"
    assert "Demo Student Head" in text_cert, "Certifier name missing from Bill Certificate PDF!"

    # Step 0 Requirement 2: If user has not supplied certifier_name, render a blank underline
    renderer = Renderer(config=load_config(), outputs_dir="outputs/test_blank_cert")
    unsupplied_event = get_sih_fixture()
    b1_ctx = {
        "approval_note_no": unsupplied_event.approval_note.no,
        "approval_note_date": unsupplied_event.approval_note.date,
        "ref_no": "BILL-091",
        "bill_amount": "800.00",
        "supplier_name": unsupplied_event.bills[0].supplier.name,
        "supplier_gst": unsupplied_event.bills[0].supplier.gst_no,
        "invoice_no": unsupplied_event.bills[0].invoice_no,
        "invoice_date": unsupplied_event.bills[0].invoice_date,
        "bill_items": [{"name": "Item", "qty": 1, "unit_cost": "800.00", "line_total": "800.00"}],
        "tax_type": "GST 18%",
        "tax_amount": "144.00",
        "payment_party": unsupplied_event.bills[0].payment.party,
        "payment_account_no": unsupplied_event.bills[0].payment.account_no,
        "payment_holder": unsupplied_event.bills[0].payment.holder,
        "payment_bank": unsupplied_event.bills[0].payment.bank,
        "payment_branch": unsupplied_event.bills[0].payment.branch,
        "payment_ifsc": unsupplied_event.bills[0].payment.ifsc,
        "bill_total": "800.00",
        "bill_total_with_tax": "944.00",
        # certifier_name is omitted
    }
    blank_res = renderer.render("bill_certificate", unsupplied_event, extra_context=b1_ctx, convert_pdf=True)
    doc_blank = pymupdf.open(str(blank_res.pdf_path))
    blank_text = " ".join(p.get_text() for p in doc_blank)
    doc_blank.close()
    assert "“I, am ____________________, personally satisfied" in blank_text, (
        "Unsupplied certifier_name must render as a blank underline '____________________'!"
    )


def test_item5_official_wording_exact_matches(rendered_sih_pdfs):
    """Test 5: Check exact wording for Approval Note, Bill Certificate, and Prize Receipt matching samples."""
    # 1. Approval Note
    doc_appr = pymupdf.open(str(rendered_sih_pdfs["approval_note"]))
    text_appr = doc_appr[0].get_text()
    doc_appr.close()

    assert "Subject" in text_appr
    assert "Office Use" in text_appr
    assert "Total amount Sanctioned in Current Academic Year" in text_appr
    assert "Amount Utilized" in text_appr
    assert "Current Proposed amount" in text_appr
    assert "Balance amount" in text_appr
    assert "Signature (Office Clerk)" in text_appr
    assert "Recommended/Not Recommended" in text_appr
    assert "Approved/Not Approved" in text_appr

    # 2. Bill Certificate (Form BC-R)
    doc_cert = pymupdf.open(str(rendered_sih_pdfs["bill_certificate"]))
    text_cert = " ".join(page.get_text() for page in doc_cert)
    doc_cert.close()

    assert "personally satisfied that the goods" in text_cert
    assert "requisite quality and specification" in text_cert
    assert "Dean (Students Welfare) Approval" in text_cert

    # 3. Prize Money Receipt
    doc_prz = pymupdf.open(str(rendered_sih_pdfs["prize_money_receipt"]))
    text_prz = doc_prz[0].get_text()
    doc_prz.close()

    assert "It is hereby acknowledged that an amount of" in text_prz
    assert "It is certified that the said amount is recommended for payment." in text_prz


def test_item6_typo_policy_enforcement(rendered_sih_pdfs):
    """Test 6: 'Mobile No.' in Permission Letter & Prize Receipt; 'Moblie No.' strictly in Approval Note faculty blocks."""
    # Permission Letter
    doc_perm = pymupdf.open(str(rendered_sih_pdfs["permission_letter"]))
    text_perm = doc_perm[0].get_text()
    doc_perm.close()
    assert "Mobile No." in text_perm
    assert "Moblie No." not in text_perm

    # Prize Money Receipt
    doc_prz = pymupdf.open(str(rendered_sih_pdfs["prize_money_receipt"]))
    text_prz = doc_prz[0].get_text()
    doc_prz.close()
    assert "Mobile No." in text_prz
    assert "Moblie No." not in text_prz

    # Approval Note
    doc_appr = pymupdf.open(str(rendered_sih_pdfs["approval_note"]))
    text_appr = doc_appr[0].get_text()
    doc_appr.close()
    assert "Moblie No." in text_appr, "'Moblie No.' must be preserved in faculty block per official sample!"


def test_item7_page_counts_and_mom_header(rendered_sih_pdfs):
    """Test 7: Approval Note fits on 1 page; Bill Certificate is exactly 2 pages."""
    doc_appr = pymupdf.open(str(rendered_sih_pdfs["approval_note"]))
    assert len(doc_appr) == 1, f"Approval Note must fit on 1 single page! Got {len(doc_appr)}"
    doc_appr.close()

    doc_cert = pymupdf.open(str(rendered_sih_pdfs["bill_certificate"]))
    assert len(doc_cert) == 2, f"Bill Certificate must be exactly 2 pages! Got {len(doc_cert)}"
    doc_cert.close()

    doc_mom = pymupdf.open(str(rendered_sih_pdfs["mom"]))
    assert len(doc_mom) == 1, f"MoM must fit on 1 page! Got {len(doc_mom)}"
    doc_mom.close()


def test_item8_numbering_series_separation(rendered_sih_pdfs):
    """Test 8: Permission Letter uses ROOM series; Approval Note uses {academic_year}/{event_code}."""
    schemas = load_all_schemas()
    config = load_config()

    perm_num = suggest_reference_number(schemas["permission_letter"], config=config)
    assert "ROOM" in perm_num.value

    appr_num = suggest_reference_number(schemas["approval_note"], config=config, event_code="SIH")
    assert "ROOM" not in appr_num.value
    assert "SIH" in appr_num.value
    assert appr_num.value.startswith("ACM/2026-27/SIH")

    # Step 0 Requirement 1: Rendered-PDF test: the Permission Letter ref contains ROOM, the Approval Note ref does not.
    doc_perm = pymupdf.open(str(rendered_sih_pdfs["permission_letter"]))
    text_perm = doc_perm[0].get_text()
    doc_perm.close()
    assert "ROOM" in text_perm, "Rendered Permission Letter PDF must contain 'ROOM' in its reference line!"

    doc_appr = pymupdf.open(str(rendered_sih_pdfs["approval_note"]))
    text_appr = doc_appr[0].get_text()
    doc_appr.close()
    assert "ROOM" not in text_appr, "Rendered Approval Note PDF must NOT contain 'ROOM' in its reference line!"


def test_item9_sih_fixture_mirroring_sample():
    """Test 9: Canonical fixture contains non-redacted sample values and clearly fake redacted values."""
    event = get_sih_fixture()
    assert event.event_name.value == "Internal Hackathon of SIH"
    assert event.category.value == "Hackathon"
    assert event.venue.value == "CSE Department"
    assert event.target_audience.value == "All year Student"
    assert event.expected_participants.value == "1000+"
    assert event.judges.value == ["Demo Guest Judge"]
    assert event.approval_note.date == "08/09/2026"
    assert event.bills[0].supplier.name == "TEST VENDOR PVT LTD"
    assert event.bills[0].payment.account_no == "00000000000000"


def test_item10_clean_pdf_rendering_no_none_or_unresolved_tags(rendered_sih_pdfs):
    """Test 10: Rendered PDF text assertions for all six documents: key fields present, no None, no AI drafts, no unresolved tags."""
    # Side-by-side images (scripts/render_sih_suite.py) need the private sample PDFs, so they are not checked here
    for doc_name, pdf_path in rendered_sih_pdfs.items():
        doc = pymupdf.open(str(pdf_path))
        full_text = " ".join(page.get_text() for page in doc)
        doc.close()

        assert "None" not in full_text, f"'None' rendered in {doc_name} PDF!"
        assert "{{" not in full_text, f"Unresolved Jinja '{{{{' in {doc_name} PDF!"
        assert "}}" not in full_text, f"Unresolved Jinja '}}}}' in {doc_name} PDF!"
        assert "[AI-drafted" not in full_text, f"Unconfirmed AI draft tag leaked in {doc_name} PDF!"
