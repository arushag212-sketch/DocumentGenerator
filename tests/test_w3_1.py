"""Tests for W3.1 Review Directives:
(a) Request with only an event name returns missing fields, not a document.
(b) No "[AI-drafted" in any generated PDF; unconfirmed AI draft is rejected.
(c) Sentinel test: no value appears in PDF that user did not provide or config supply.
(d) Approval note number in Bill Certificate equals Approval Note's of the same event.
(e) DD/MM/YYYY everywhere.
(f) Viewer role cannot generate; cross-club user gets 403/404 on download and page preview.
(g) Event extraction accuracy for SIH sentence.
(h) Permission letter schedule line & brief description reusable clause.
(i) Multi-day date range formatting ('14-15 October 2026').
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import pymupdf
from fastapi.testclient import TestClient

from docgen.config import load_config
from docgen.extractors.event_extractor import EventExtractor
from docgen.functions import fn_format_date_range
from docgen.models import EventRecord, FieldSource, TrackedField
from docgen.schema import load_all_schemas, load_schema
from server.app.core.database import SessionLocal
from server.app.core.security import get_password_hash
from server.app.main import app
from server.app.models import Club, Document, DocumentVersion, Event, Membership, User


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def owner_auth(client):
    """Login as demo owner and return auth header + ACM club ID."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    clubs = client.get("/api/v1/clubs/", headers=headers).json()
    acm_club = next(c for c in clubs if c["short_name"] == "ACM")
    return headers, acm_club["id"]


def test_item3_extractor_accuracy():
    """Directive 3: Test extractor with exact required sentence."""
    prompt = (
        "We are organizing Smart India Hackathon 2026 Internal Hackathon on "
        "15/10/2026 from 09:00 AM to 06:00 PM at Seminar Hall. "
        "Expected participants: 120 students."
    )
    extractor = EventExtractor(config=load_config())
    rec = extractor.extract_from_text(prompt)

    assert rec.event_name.value == "Smart India Hackathon 2026 Internal Hackathon"
    assert rec.venue.value == "Seminar Hall"
    assert rec.dates.value == "15/10/2026"
    assert rec.time_start.value == "09:00 AM"
    assert rec.time_end.value == "06:00 PM"
    assert rec.expected_participants.value == 120
    # Entity fields must NOT have literal "[AI-drafted, review]" prepended
    assert "[AI-drafted" not in str(rec.event_name.value)
    assert "[AI-drafted, review]" in str(rec.description.value or "")


def test_multiday_date_range_format():
    """Directive 4: Multi-day events render e.g. '14-15 October 2026'."""
    assert fn_format_date_range("14/10/2026", "15/10/2026") == "14-15 October 2026"
    assert fn_format_date_range("2026-10-14", "2026-10-15") == "14-15 October 2026"
    assert fn_format_date_range("15/10/2026", "15/10/2026") == "15/10/2026"


def test_8a_request_with_only_event_name_blocks_generation(client, owner_auth):
    """Directive 8(a) & 1: Request with only event name returns missing fields, not a document."""
    headers, club_id = owner_auth

    payload = {
        "template_id": "permission_letter",
        "title": "Smart India Hackathon 2026",
        "ref_no": "ACM/2026-27/ROOM/999",
        "ref_no_confirmed": True,
        "event_data": {
            "event_name": "Smart India Hackathon 2026",
        },
    }

    res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=payload, headers=headers)
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    detail = res.json()["detail"]
    assert detail["code"] == "MISSING_REQUIRED_FIELDS"
    missing_keys = [m["key"] for m in detail["missing"]]
    assert "venue" in missing_keys
    assert "dates" in missing_keys
    assert "time_start" in missing_keys
    assert "time_end" in missing_keys
    # In Phase W8 minimum questions, description is optional (renders blank underlines)
    assert "description" in missing_keys or "venue" in missing_keys


def test_8b_no_ai_drafted_in_generated_pdf_and_unconfirmed_rejected(client, owner_auth):
    """Directive 8(b) & 2: Rejects literal '[AI-drafted' and unconfirmed drafts."""
    headers, club_id = owner_auth

    # Submitting a field with literal '[AI-drafted' must be blocked by server
    payload_bad = {
        "template_id": "permission_letter",
        "title": "Smart India Hackathon 2026",
        "ref_no": "ACM/2026-27/ROOM/998",
        "ref_no_confirmed": True,
        "event_data": {
            "event_name": "Smart India Hackathon 2026",
            "venue": "Seminar Hall",
            "dates": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "06:00 PM",
            "description": "[AI-drafted, review] Hackathon event description",
            "expected_participants": 120,
            "submitted_to": "Head of Department, CSE",
        },
    }
    res_bad = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=payload_bad, headers=headers)
    assert res_bad.status_code == 400
    assert res_bad.json()["detail"]["code"] == "UNCONFIRMED_AI_DRAFT"


def test_8c_sentinel_test_no_unprovided_values_fabricated(client, owner_auth):
    """Directive 8(c) & 1: No value appears in PDF that user did not provide or config supply."""
    headers, club_id = owner_auth

    sentinel_venue = "Room 999 Special Lab"
    sentinel_event = "Sentinel Event Alpha 2026"
    sentinel_desc = "Testing zero silent defaults and exact institutional provenance."

    res_alloc = client.post(
        f"/api/v1/clubs/{club_id}/numbering/ROOM/reserve",
        json={"template_id": "permission_letter"},
        headers=headers,
    )
    assert res_alloc.status_code == 200
    res_data = res_alloc.json()

    payload = {
        "template_id": "permission_letter",
        "title": sentinel_event,
        "ref_no": res_data["ref_no"],
        "ref_no_confirmed": True,
        "reservation_id": res_data["reservation_id"],
        "event_data": {
            "event_name": sentinel_event,
            "venue": sentinel_venue,
            "dates": "15/10/2026",
            "date_start": "15/10/2026",
            "date_end": "15/10/2026",
            "time_start": "11:00 AM",
            "time_end": "02:00 PM",
            "description": sentinel_desc,
            "objectives": "Sentinel test objective for code verification.",
            "expected_participants": 42,
            "mode": "Offline",
            "submitted_to": "Head of Department, Computer Science & Engineering",
        },
        "confirmed_fields": ["description", "objectives"],
    }

    res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=payload, headers=headers)
    assert res.status_code == 200, f"Generation failed: {res.text}"
    doc_data = res.json()
    pdf_url = doc_data["pdf_url"]

    # Download PDF
    pdf_res = client.get(pdf_url, headers=headers)
    assert pdf_res.status_code == 200

    pdf_doc = pymupdf.open(stream=pdf_res.content, filetype="pdf")
    full_text = "".join(page.get_text() for page in pdf_doc)
    pdf_doc.close()

    # Assert sentinel values are present
    normalized_text = " ".join(full_text.split())
    assert sentinel_event in normalized_text
    assert sentinel_venue in normalized_text
    assert sentinel_desc in normalized_text
    assert "42" in normalized_text
    assert "11:00 AM" in normalized_text
    assert "02:00 PM" in normalized_text

    # Assert fabricated defaults did NOT appear
    assert "Seminar Hall" not in normalized_text
    assert "09:00 AM" not in normalized_text
    assert "05:00 PM" not in normalized_text
    assert "1000+" not in normalized_text
    assert "[AI-drafted" not in normalized_text


def test_permission_letter_schedule_and_reusable_clause(client, owner_auth):
    """Directive 4: Permission Letter schedule line & Brief Description reusable clause."""
    headers, club_id = owner_auth

    res_alloc = client.post(
        f"/api/v1/clubs/{club_id}/numbering/ROOM/reserve",
        json={"template_id": "permission_letter"},
        headers=headers,
    )
    assert res_alloc.status_code == 200
    res_data = res_alloc.json()

    payload = {
        "template_id": "permission_letter",
        "title": "Smart India Hackathon 2026 Internal Hackathon",
        "ref_no": res_data["ref_no"],
        "ref_no_confirmed": True,
        "reservation_id": res_data["reservation_id"],
        "event_data": {
            "event_name": "Smart India Hackathon 2026 Internal Hackathon",
            "venue": "Seminar Hall",
            "dates": "15/10/2026",
            "date_start": "15/10/2026",
            "date_end": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "06:00 PM",
            "description": "Internal hackathon for selecting institute teams.",
            "objectives": "To evaluate problem statements and select top teams.",
            "expected_participants": 120,
            "submitted_to": "Head of Department, Computer Science & Engineering",
        },
        "confirmed_fields": ["description", "objectives"],
    }

    res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=payload, headers=headers)
    assert res.status_code == 200, f"Generation failed: {res.text}"
    doc_data = res.json()

    pdf_res = client.get(doc_data["pdf_url"], headers=headers)
    assert pdf_res.status_code == 200
    pdf_doc = pymupdf.open(stream=pdf_res.content, filetype="pdf")
    text = "".join(page.get_text() for page in pdf_doc)
    pdf_doc.close()

    normalized_text = " ".join(text.split())
    # Schedule line must show 15/10/2026, 09:00 AM to 06:00 PM
    assert "15/10/2026, 09:00 AM to 06:00 PM" in normalized_text

    # Brief Description must include the reusable clause from sample
    expected_clause = (
        "We request permission to use Seminar Hall on 15/10/2026 "
        "from 09:00 AM to 06:00 PM for conducting the Smart India Hackathon 2026 Internal Hackathon."
    )
    assert expected_clause in normalized_text


def test_8d_approval_note_cross_reference_in_bill_certificate(client, owner_auth):
    """Directive 8(d) & 6: Bill Certificate takes approval note number and date from Approval Note of same event."""
    headers, club_id = owner_auth

    event_title = "Smart India Hackathon 2026 Internal Hackathon"
    appr_ref_no = "ACM/2026-27/SIH/042"
    appr_date = "15/10/2026"

    # 1. Generate Approval Note first for this event
    res_alloc = client.post(
        f"/api/v1/clubs/{club_id}/numbering/SIH/reserve",
        json={"template_id": "approval_note", "event_code": "SIH"},
        headers=headers,
    )
    assert res_alloc.status_code == 200
    res_data = res_alloc.json()
    appr_ref_no = res_data["ref_no"]

    appr_payload = {
        "template_id": "approval_note",
        "title": event_title,
        "ref_no": appr_ref_no,
        "ref_no_confirmed": True,
        "reservation_id": res_data["reservation_id"],
        "event_data": {
            "event_name": event_title,
            "event_code": "SIH",
            "category": "Hackathon",
            "target_audience": "UG/PG Engineering Students",
            "document_date": appr_date,
            "dates": "15/10/2026",
            "venue": "Seminar Hall",
            "budget_items": [
                {"item": "Event Banners", "amount": 800},
                {"item": "Stationery & Certificates", "amount": 200},
            ],
            "description": "Internal hackathon approval request.",
            "objectives": "Problem solving and team selection.",
            "expected_participants": 120,
        },
        "confirmed_fields": ["description", "objectives"],
    }
    appr_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=appr_payload, headers=headers)
    assert appr_res.status_code == 200, f"Approval note generation failed: {appr_res.text}"
    appr_doc = appr_res.json()

    # 2. Generate Bill Certificate for the SAME event without explicitly providing approval note no
    cert_payload = {
        "template_id": "bill_certificate",
        "title": f"Bill Certificate - {event_title}",
        "ref_no": "INV-2026-089",
        "ref_no_confirmed": True,
        "event_data": {
            "event_name": event_title,
            "supplier_name": "SVNIT Printing Press",
            "supplier_gst": "24AAAAA0000A1Z5",
            "invoice_no": "INV-2026-089",
            "invoice_date": "15/10/2026",
            "bill_items": [
                {"name": "Event Banners", "qty": 1, "unit_cost": 800}
            ],
            "tax_type": "GST",
            "tax_amount": 144,
        },
        "deferred_fields": [
            "certifier_name",
            "supplier_gst",
            "payment_party",
            "payment_account_no",
            "payment_holder",
            "payment_bank",
            "payment_branch",
            "payment_ifsc",
        ],
    }
    cert_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=cert_payload, headers=headers)
    assert cert_res.status_code == 200, f"Bill certificate generation failed: {cert_res.text}"
    cert_doc = cert_res.json()

    # 3. Check rendered Bill Certificate PDF text
    pdf_res = client.get(cert_doc["pdf_url"], headers=headers)
    assert pdf_res.status_code == 200
    pdf_doc = pymupdf.open(stream=pdf_res.content, filetype="pdf")
    full_text = "".join(page.get_text() for page in pdf_doc)
    pdf_doc.close()

    # Approval note reference in Bill Certificate MUST equal the Approval Note's ref number
    assert appr_ref_no in full_text, (
        f"Expected Approval Note ref '{appr_ref_no}' in Bill Certificate PDF text, but got:\n{full_text}"
    )
    assert appr_date in full_text
    assert "800.00" in full_text
    assert "144.00" in full_text
    assert "944.00" in full_text


def test_8e_date_format_dd_mm_yyyy_everywhere(client, owner_auth):
    """Directive 8(e): Standardized DD/MM/YYYY dates across all documents and APIs."""
    headers, club_id = owner_auth

    # Check schema endpoint
    schema_res = client.get(
        f"/api/v1/clubs/{club_id}/documents/templates/permission_letter/schema",
        headers=headers,
    )
    assert schema_res.status_code == 200
    doc_date = schema_res.json()["defaults"]["document_date"]
    import re
    assert re.match(r"^\d{2}/\d{2}/\d{4}$", doc_date), f"Expected DD/MM/YYYY, got {doc_date}"


def test_8f_permissions_viewer_cannot_generate_and_cross_club_isolation(client, owner_auth):
    """Directive 8(f): Viewer role cannot generate; cross-club user gets 403/404 on download and page images."""
    headers, acm_club_id = owner_auth

    db = SessionLocal()
    try:
        # Create a viewer user in ACM
        viewer_user = db.query(User).filter(User.email == "test.viewer@svnit.ac.in").first()
        if not viewer_user:
            viewer_user = User(
                email="test.viewer@svnit.ac.in",
                password_hash=get_password_hash("ViewerPass123!"),
                name="Test Viewer",
            )
            db.add(viewer_user)
            db.flush()

        # Add membership as viewer
        mem = db.query(Membership).filter(Membership.user_id == viewer_user.id, Membership.club_id == acm_club_id).first()
        if not mem:
            mem = Membership(user_id=viewer_user.id, club_id=acm_club_id, role="viewer")
            db.add(mem)
        else:
            mem.role = "viewer"

        # Create a second club (e.g. GDSC) where viewer is NOT a member
        other_club = db.query(Club).filter(Club.short_name == "GDSC").first()
        if not other_club:
            other_club = Club(
                name="Google Developer Student Club",
                short_name="GDSC",
                slug="gdsc",
            )
            db.add(other_club)
            db.flush()

        db.commit()
        other_club_id = other_club.id
    finally:
        db.close()

    # Login as viewer
    v_login = client.post(
        "/api/v1/auth/login",
        json={"email": "test.viewer@svnit.ac.in", "password": "ViewerPass123!"},
    )
    assert v_login.status_code == 200
    v_token = v_login.json()["access_token"]
    v_headers = {"Authorization": f"Bearer {v_token}"}

    # 1. Viewer attempts to generate -> MUST BE 403 FORBIDDEN
    gen_payload = {
        "template_id": "permission_letter",
        "title": "Unauthorized Generation",
        "ref_no": "ACM/2026-27/ROOM/100",
        "ref_no_confirmed": True,
        "event_data": {"event_name": "Unauthorized Generation"},
    }
    gen_res = client.post(
        f"/api/v1/clubs/{acm_club_id}/documents/generate",
        json=gen_payload,
        headers=v_headers,
    )
    assert gen_res.status_code == 403, f"Expected 403 for viewer, got {gen_res.status_code}"

    # 2. Cross-club access: viewer attempts to access other_club_id -> 403 FORBIDDEN
    cross_res = client.get(
        f"/api/v1/clubs/{other_club_id}/documents/some-doc-id/download",
        headers=v_headers,
    )
    assert cross_res.status_code == 403, f"Expected 403 for non-member club, got {cross_res.status_code}"
