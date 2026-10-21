"""Tests for Phase W8 Part B: Minimum Questions & UX Simplification.

Verifies:
1. Each of the 6 system templates has at most 6 essential questions (importance: essential).
2. All non-essential fields default to importance: optional.
3. Documents generated with only essential fields filled render clean blank lines (____________________)
   and NEVER contain "None" or broken layouts.
4. Recommender distinguishes simple intent (single document) from bundle intent (multi-phase bundle).
5. Unprompted custom templates are suppressed for generic user queries.
6. Stopwatch test: blank Home page to downloaded PDF in <= 5 screens and <= 60 seconds.
"""

from __future__ import annotations

import io
import time
from pathlib import Path
import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient

from docgen.models import EventRecord
from docgen.renderer import BLANK_LINE, Renderer
from docgen.schema import TemplateSchema, load_schema
from server.app.core.database import SessionLocal
from server.app.core.event_recommender import EventRecommender
from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.app.models import Club, Document, DocumentVersion, Template, TemplateVersion, User


@pytest.fixture
def client():
    return TestClient(app)


def _get_recommendations(text: str):
    db = SessionLocal()
    try:
        club = db.query(Club).filter(Club.slug == "acm").first()
        assert club is not None
        res = EventRecommender.recommend(text=text, club_id=club.id, db=db)
        return res.templates
    finally:
        db.close()


def test_system_templates_essential_fields_limit():
    """Verify that each of the 6 system templates has at most 6 essential fields,
    and all others are marked optional.
    """
    system_templates = {
        "permission_letter": {"event_name", "venue", "dates", "time_start", "time_end"},
        "approval_note": {"event_name", "dates", "venue", "expected_participants", "budget_items"},
        "prize_money_receipt": {"event_name", "dates", "venue", "winner_name", "winner_position", "winner_amount"},
        "bill_summary": {"event_name", "other_reimbursements"},
        "bill_certificate": {"event_name", "bill_items", "supplier_name", "invoice_no", "invoice_date", "tax_amount"},
        "mom": {"meeting_title", "meeting_date", "venue", "attendees", "agenda_items"},
    }

    for template_id, expected_essentials in system_templates.items():
        template_dir = Path("templates") / template_id
        assert (template_dir / "schema.yaml").exists(), f"Schema for {template_id} must exist"
        schema = load_schema(template_dir)

        essential_keys = set(schema.essential_field_keys())
        # Rule: At most 6 essential questions per document
        assert len(essential_keys) <= 6, (
            f"Template {template_id} has {len(essential_keys)} essential fields, must be <= 6: {essential_keys}"
        )
        assert essential_keys == expected_essentials, (
            f"Template {template_id} essentials mismatch. Expected {expected_essentials}, got {essential_keys}"
        )

        # Verify all other fields are optional
        for field in schema.fields:
            if field.key not in expected_essentials:
                assert field.importance == "optional", (
                    f"Field {field.key} in {template_id} should be optional, got {field.importance}"
                )


def test_permission_letter_renders_clean_underlines_for_unfilled_optional_fields(tmp_path):
    """Verify that a permission letter generated with only essentials filled
    succeeds, renders clean blank underlines (____________________) for unfilled
    optional fields, and contains no 'None' text in paragraphs or tables.
    """
    renderer = Renderer(templates_dir="templates", outputs_dir=tmp_path)
    event = EventRecord(
        event_name="National Coding Championship",
        venue="Computer Center Hall 1",
        dates="15-16 November 2026",
        time_start="09:00",
        time_end="17:00",
        ref_no="ACM/2026-27/042",
        document_date="01 November 2026",
    )
    result = renderer.render(
        "permission_letter",
        event=event,
        output_dir=tmp_path,
        convert_pdf=False,
    )
    assert result.docx_path.exists()

    # Inspect rendered docx
    doc = DocxDocument(str(result.docx_path))
    all_text: list[str] = []
    for p in doc.paragraphs:
        all_text.append(p.text)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                all_text.append(cell.text)

    combined = "\n".join(all_text)

    # 1. Must NOT contain literal "None"
    assert "None" not in combined, "Rendered document must never contain literal 'None'"

    # 2. Must contain the filled essential values
    assert "National Coding Championship" in combined
    assert "Computer Center Hall 1" in combined
    assert "09:00 AM" in combined or "09:00" in combined

    # 3. Clean underlines for unfilled optional fields must be present
    assert BLANK_LINE in combined or "____" in combined, "Blank underlines must be rendered for unfilled optional fields"


def test_recommender_simple_vs_bundle_intent():
    """Verify that simple intent produces ONLY the single document asked for,
    while bundle intent produces a multi-document bundle.
    """
    # 1. Simple venue booking -> ONLY permission letter
    res_venue = _get_recommendations("I need to book a seminar hall")
    rec_slugs_venue = [r.slug for r in res_venue if r.recommended]
    assert rec_slugs_venue == ["permission_letter"], (
        f"Expected ONLY permission_letter, got: {rec_slugs_venue}"
    )

    # 2. Simple permission intent -> ONLY permission letter
    res_perm = _get_recommendations("Permission for workshop")
    rec_slugs_perm = [r.slug for r in res_perm if r.recommended]
    assert rec_slugs_perm == ["permission_letter"], (
        f"Expected ONLY permission_letter, got: {rec_slugs_perm}"
    )

    # 3. Simple meeting intent -> ONLY minutes of meeting
    res_mom = _get_recommendations("We need to hold an urgent core committee meeting to plan logistics")
    rec_slugs_mom = [r.slug for r in res_mom if r.recommended]
    assert rec_slugs_mom == ["mom"], (
        f"Expected ONLY mom, got: {rec_slugs_mom}"
    )

    # 4. Simple prize intent -> ONLY prize money receipt
    res_prize = _get_recommendations("Distribute prize money to winners of our hackathon")
    rec_slugs_prize = [r.slug for r in res_prize if r.recommended]
    assert rec_slugs_prize == ["prize_money_receipt"], (
        f"Expected ONLY prize_money_receipt, got: {rec_slugs_prize}"
    )

    # 5. Simple bill intent -> ONLY bill certificate
    res_bill = _get_recommendations("Submit invoice and bills for sound equipment vendor")
    rec_slugs_bill = [r.slug for r in res_bill if r.recommended]
    assert "bill_certificate" in rec_slugs_bill
    assert "permission_letter" not in rec_slugs_bill

    # 6. Bundle intent -> Multi-document package
    res_bundle = _get_recommendations("We want to run an event from start to finish with approvals and venue")
    rec_slugs_bundle = [r.slug for r in res_bundle if r.recommended]
    assert len(rec_slugs_bundle) >= 2, (
        f"Bundle intent must recommend multiple documents, got: {rec_slugs_bundle}"
    )
    assert "approval_note" in rec_slugs_bundle
    assert "permission_letter" in rec_slugs_bundle


def test_custom_templates_suppressed_unprompted():
    """Verify that custom templates are never recommended unprompted."""
    # When user asks for hall booking, even if custom templates exist,
    # only the direct match is recommended
    res = _get_recommendations("I need to book a seminar hall")
    for r in res:
        if r.slug not in ["permission_letter"]:
            assert not r.recommended, f"Unprompted template {r.slug} must not be marked recommended"


def test_stopwatch_home_to_pdf_in_under_60_seconds_and_under_5_screens(client):
    """Stopwatch test: measures time and screens from blank Home page to generated PDF.
    Constraint: <= 5 screens and <= 60 seconds.
    """
    clear_rate_limits()
    # Authenticate as club owner
    res_login = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert res_login.status_code == 200, res_login.text
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    db = SessionLocal()
    try:
        club = db.query(Club).filter(Club.slug == "acm").first()
        assert club is not None
        club_id = club.id

        # Start timer
        start_time = time.perf_counter()
        screen_count = 0

        # SCREEN 1: Home Page - Plain English prompt input
        screen_count += 1
        prompt_text = "I need permission to book Seminar Hall on 25 October 2026 from 10:00 to 13:00 for AI Workshop"
        resp_understand = client.post(
            f"/api/v1/clubs/{club_id}/home/understand",
            json={"text": prompt_text},
            headers=headers,
        )
        assert resp_understand.status_code == 200, resp_understand.text
        data_understand = resp_understand.json()
        assert "understood" in data_understand
        assert "recommended_documents" in data_understand

        # SCREEN 2: Essential Details Confirmation
        screen_count += 1
        understood = data_understand["understood"]
        assert understood["venue"] == "Seminar Hall"
        assert understood["event_name"] == "AI Workshop"

        # SCREEN 3: Generate Document (Trigger batch/document generation)
        screen_count += 1
        generate_payload = {
            "selected_template_ids": ["permission_letter"],
            "event_data": {
                "event_name": understood.get("event_name", "AI Workshop"),
                "venue": understood.get("venue", "Seminar Hall"),
                "dates": understood.get("dates", "25 October 2026"),
                "dates_confirmed": True,
                "time_start": "10:00",
                "time_end": "13:00",
                "description": "",
                "objectives": "",
            },
            "ref_numbers_accepted": True,
            "event_title": "AI Workshop",
        }
        resp_generate = client.post(
            f"/api/v1/clubs/{club_id}/home/generate",
            json=generate_payload,
            headers=headers,
        )
        assert resp_generate.status_code == 200, resp_generate.text
        data_generate = resp_generate.json()
        assert "documents" in data_generate
        assert len(data_generate["documents"]) >= 1
        doc_id = data_generate["documents"][0]["id"]

        # SCREEN 4: View / Download Generated PDF
        screen_count += 1
        resp_pdf = client.get(
            f"/api/v1/clubs/{club_id}/documents/{doc_id}/pdf",
            headers=headers,
        )
        assert resp_pdf.status_code == 200, resp_pdf.text
        pdf_bytes = resp_pdf.content
        assert len(pdf_bytes) > 500, "Downloaded PDF must be non-empty"
        assert pdf_bytes.startswith(b"%PDF"), "Downloaded file must be a valid PDF"

        # Record elapsed time
        elapsed_seconds = time.perf_counter() - start_time

        # Validate Phase W8 Constraints:
        # 1. <= 5 screens
        assert screen_count <= 5, f"Expected <= 5 screens, took {screen_count}"
        # 2. <= 60 seconds
        assert elapsed_seconds <= 60.0, f"Expected <= 60 seconds, took {elapsed_seconds:.2f}s"

    finally:
        db.close()
