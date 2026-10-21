"""Tests for Phase W1: Foundations.

Verifies:
1. Database schema and tables creation via SQLAlchemy 2.0 and Alembic.
2. Database seeding of Platform Admin, System Assets, System Letterheads, 6 System Templates, and Demo Club 'ACM'.
3. Building ClubConfig and TemplateSource exclusively from DB rows.
4. docgen Engine renders all 6 system documents from DB data alone without relying on YAML files.
5. Verification that rendered documents match formatting rules and LibreOffice converter operates properly.
"""

from __future__ import annotations

import os
from pathlib import Path
from decimal import Decimal
import pytest

from docgen.models import EventRecord
from docgen.renderer import Renderer
from docgen.sources import DatabaseTemplateSource, build_club_config_from_db
from server.app.core.database import SessionLocal
from server.app.models import Club, Template, TemplateVersion, Asset, Letterhead, Person, Venue
from tests.fixtures.sih_event import get_sih_fixture


@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    yield session
    session.close()


def test_w1_database_models_and_seeds(db_session):
    """Verify that all seed data is properly populated in SQLite."""
    # Check Club
    club = db_session.query(Club).filter(Club.slug == "acm").first()
    assert club is not None
    assert club.name == "ACM Student Chapter, SVNIT"
    assert club.short_name == "ACM"

    # No shared letterhead images: each club's letterhead is generated from its own logo
    assert db_session.query(Asset).filter(Asset.is_system == True).count() == 0
    # Letterheads are generated per club; no letterhead records or images are seeded
    assert db_session.query(Letterhead).count() == 0

    # The 6 institute forms plus the template library (templates/library/*.json)
    from server.app.core.template_library import load_specs
    templates = db_session.query(Template).filter(Template.is_system == True).all()
    assert len(templates) == 6 + len(load_specs())
    template_slugs = {t.slug for t in templates}
    expected_slugs = {
        "permission_letter",
        "approval_note",
        "prize_money_receipt",
        "bill_summary",
        "bill_certificate",
        "mom",
    }
    assert expected_slugs.issubset(template_slugs)

    # Check Template Versions
    for tmpl in templates:
        assert tmpl.current_version_id is not None
        ver = db_session.query(TemplateVersion).filter(TemplateVersion.id == tmpl.current_version_id).first()
        assert ver is not None
        assert ver.version_no == 1
        assert len(ver.schema_yaml) > 50
        assert Path(ver.docx_storage_key).exists()

    # Check People seeded for ACM
    people = db_session.query(Person).filter(Person.club_id == club.id).all()
    names = {p.full_name for p in people}
    assert "Demo Student Head" in names
    assert "Demo Faculty Chairman" in names


def test_w1_render_all_six_documents_from_db_data(db_session):
    """GATE W1: Verify that docgen renders all 6 system documents using only DB-injected sources."""
    # 1. Build ClubConfig directly from DB rows
    db_config = build_club_config_from_db(db_session, "acm")
    assert db_config.club_short == "ACM"
    assert db_config.student_head.name == "Demo Student Head"
    assert db_config.faculty_chairman.name == "Demo Faculty Chairman"
    assert "Seminar Hall" in db_config.venues

    # 2. Build DatabaseTemplateSource directly from DB rows
    db_source = DatabaseTemplateSource(db_session)

    # Delete stale outputs before rendering so tests cannot pass on old files
    out_dir = Path("outputs/tests_w1_gate")
    if out_dir.exists():
        import shutil
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    renderer = Renderer(
        config=db_config,
        template_source=db_source,
        outputs_dir=out_dir,
    )

    event = get_sih_fixture()
    extra_ctx = {}

    # Render all 5 event documents
    templates_to_test = [
        "permission_letter",
        "approval_note",
        "bill_summary",
        "bill_certificate",
        "mom",
    ]

    for tmpl_slug in templates_to_test:
        result = renderer.render(
            template_id=tmpl_slug,
            event=event,
            extra_context=extra_ctx,
            output_dir=out_dir,
            convert_pdf=True,
        )
        assert result.docx_path.exists(), f"DOCX not generated for {tmpl_slug}"
        assert result.pdf_path.exists(), f"PDF not generated for {tmpl_slug}"
        assert result.converter.lower() == "libreoffice", f"Converter was not LibreOffice: {result.converter}"

    # Also render prize_money_receipt for winner 1
    winner1 = event.winners[0]
    winner1_ctx = {
        "sr_no": 1,
        "winner_name": winner1.name,
        "winner_position": winner1.position,
        "winner_amount": winner1.amount,
        "winner_amount_words": "Five Thousand Rupees Only",
        "winner_roll_no": winner1.roll_no,
        "winner_course_semester": winner1.course_semester,
        "winner_mobile": winner1.mobile,
        "winner_bank_name_as_per_bank": winner1.bank.name_as_per_bank if winner1.bank else "",
        "winner_bank_name": winner1.bank.bank_name if winner1.bank else "",
        "winner_bank_branch": winner1.bank.branch if winner1.bank else "",
        "winner_account_no": winner1.bank.account_no if winner1.bank else "",
        "winner_ifsc": winner1.bank.ifsc if winner1.bank else "",
        "winner_pan": winner1.bank.pan if winner1.bank else "",
    }

    prize_result = renderer.render(
        template_id="prize_money_receipt",
        event=event,
        extra_context=winner1_ctx,
        output_dir=out_dir,
        convert_pdf=True,
    )
    assert prize_result.docx_path.exists()
    assert prize_result.pdf_path.exists()
    assert prize_result.converter.lower() == "libreoffice"


def test_w1_extracted_pdf_text_accuracy(db_session):
    """Verify that all six rendered PDFs from DB data have correct content without leakages or unresolved functions."""
    import fitz

    out_dir = Path("outputs/tests_w1_gate")
    pdf_files = {
        "permission_letter": out_dir / "permission_letter_v1.pdf",
        "approval_note": out_dir / "approval_note_v1.pdf",
        "bill_summary": out_dir / "bill_summary_v1.pdf",
        "bill_certificate": out_dir / "bill_certificate_v1.pdf",
        "mom": out_dir / "mom_v1.pdf",
        "prize_money_receipt": out_dir / "prize_money_receipt_v1.pdf",
    }

    # 1. Global assertion on ALL SIX PDFs:
    # No "<function", no "None", no "{{", no "[COMPUTE ERROR"
    for doc_name, pdf_p in pdf_files.items():
        assert pdf_p.exists(), f"Rendered PDF for {doc_name} does not exist at {pdf_p}"
        doc = fitz.open(pdf_p)
        text = "\n".join([page.get_text() for page in doc])
        doc.close()

        assert "<function" not in text, f"Unresolved function repr leaked into {doc_name} PDF text!"
        assert "<bound" not in text, f"Unresolved bound method leaked into {doc_name} PDF text!"
        assert "None" not in text, f"'None' leaked into {doc_name} PDF text!"
        assert "{{" not in text, f"Unresolved Jinja '{{{{' in {doc_name} PDF text!"
        assert "[COMPUTE ERROR" not in text, f"Compute error in {doc_name} PDF text!"

    # 2. Bill Certificate specific assertions:
    # Must contain 800.00, 144.00, 944.00, and invoice no (INV/TEST/001)
    bc_doc = fitz.open(pdf_files["bill_certificate"])
    bc_text = "\n".join([page.get_text() for page in bc_doc])
    bc_doc.close()
    assert "800.00" in bc_text, "Item cost / subtotal 800.00 missing from Bill Certificate PDF!"
    assert "144.00" in bc_text, "Tax amount 144.00 missing from Bill Certificate PDF!"
    assert "944.00" in bc_text, "Grand total with tax 944.00 missing from Bill Certificate PDF!"
    assert "INV/TEST/001" in bc_text, "Invoice number INV/TEST/001 missing from Bill Certificate PDF!"

    # 3. MoM specific assertions:
    # Ref must contain "MOM" and NOT "SIH"
    mom_doc = fitz.open(pdf_files["mom"])
    mom_text = "\n".join([page.get_text() for page in mom_doc])
    mom_doc.close()
    assert "MOM" in mom_text, "MoM reference number series 'MOM' missing from MoM PDF!"
    assert "SIH/001" not in mom_text, "SIH event reference leaked into MoM PDF reference line!"

    # 4. Prize Receipt specific assertions:
    # Contains 5,000.00
    prz_doc = fitz.open(pdf_files["prize_money_receipt"])
    prz_text = "\n".join([page.get_text() for page in prz_doc])
    prz_doc.close()
    assert "5,000.00" in prz_text, "Prize amount 5,000.00 missing from Prize Receipt PDF!"

    # 5. Bill Summary specific assertions:
    # Contains 8,300.00
    bs_doc = fitz.open(pdf_files["bill_summary"])
    bs_text = "\n".join([page.get_text() for page in bs_doc])
    bs_doc.close()
    assert "8,300.00" in bs_text, "Grand total 8,300.00 missing from Bill Summary PDF!"


def test_w1_money_formatting_vs_counts_and_quantities(db_session):
    """Verify that money formatting strictly applies only to money-typed fields and not count or quantity fields."""
    db_config = build_club_config_from_db(db_session, "acm")
    db_source = DatabaseTemplateSource(db_session)
    renderer = Renderer(config=db_config, template_source=db_source)

    event = get_sih_fixture()
    # Check approval note: expected_participants is count ("1000+"), budget total is money (1100)
    schema_appr = db_source.get_template_schema("approval_note")
    ctx_appr = renderer._build_context(event, schema_appr)
    assert ctx_appr["expected_participants"] == "1000+"
    assert ctx_appr["budget_total_inr"] == "1,100.00"

    # Check bill certificate: quantity is 1 (not 1.00), unit_cost is 800.00
    schema_bc = db_source.get_template_schema("bill_certificate")
    ctx_bc = renderer._build_context(event, schema_bc)
    item = ctx_bc["bill_items"][0]
    assert str(item["qty"]) == "1"
    assert item["unit_cost"] == "800.00"
    assert item["line_total"] == "800.00"


def test_w1_global_guard_catches_callable_and_empty_computed():
    """Verify that the extended global guard raises on callable values or empty computed fields."""
    import pytest
    renderer = Renderer()
    schema = renderer.template_source.get_template_schema("permission_letter")

    # 1. Test callable function in context
    bad_ctx = {
        "event_name": "Test",
        "bad_func": lambda x: x,
    }
    with pytest.raises(ValueError, match="is a callable function object"):
        renderer._validate_rendered_context(bad_ctx, schema)

    # 2. Test function representation string in context
    bad_repr_ctx = {
        "event_name": "Test",
        "tax": "<function fn_tax_amount at 0x7fff>",
    }
    with pytest.raises(ValueError, match="contains function repr '<function'"):
        renderer._validate_rendered_context(bad_repr_ctx, schema)
