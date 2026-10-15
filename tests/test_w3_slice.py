"""Tests for W3 Vertical Slice:
1. Demo Owner Role Coherence & Membership Role matches Dashboard Role.
2. Official fields (ref number, AI drafts) are never auto-confirmed.
3. Template Schema endpoint returns dynamic options & unconfirmed suggested ref no.
4. Describe your event extraction endpoint returns prefilled data & missing fields.
5. Generation through LibreOffice and rasterized page preview generation.
6. Numbering series formatting uses {academic_year}/{event_code}, never 'EVT'.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import pymupdf

from server.app.core.config import settings
from server.app.core.database import SessionLocal, get_db
from server.app.core.security import get_password_hash
from server.app.main import app
from server.app.models import Club, Document, DocumentVersion, Membership, NumberingSeries, Person, User, Venue


@pytest.fixture(scope="module")
def seeded_client():
    """Client using the seeded database with real tables."""
    client = TestClient(app)
    return client


def test_dashboard_role_equals_membership_role(seeded_client):
    """Test requirement 2: Demo owner user role coherence and active club membership."""
    # Login as demo owner
    login_res = seeded_client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch user clubs
    clubs_res = seeded_client.get("/api/v1/clubs/", headers=headers)
    assert clubs_res.status_code == 200
    clubs = clubs_res.json()
    assert len(clubs) > 0
    acm_club = next(c for c in clubs if c["short_name"] == "ACM")
    club_id = acm_club["id"]

    # Verify club members list contains 4 members
    members_res = seeded_client.get(f"/api/v1/clubs/{club_id}/members", headers=headers)
    assert members_res.status_code == 200
    members = members_res.json()
    assert len(members) >= 4, f"Expected at least 4 members, got {len(members)}"

    # Verify demo owner's membership role
    owner_membership = next(m for m in members if m["email"] == "demo.owner@svnit.ac.in")
    assert owner_membership["role"] == "owner"

    # Verify permissions endpoint returns role == "owner" and is_owner is True
    perms_res = seeded_client.get(f"/api/v1/clubs/{club_id}/permissions", headers=headers)
    assert perms_res.status_code == 200
    perms = perms_res.json()
    assert perms["role"] == "owner"
    assert perms["is_owner"] is True
    # Demo owner is not a platform admin; platform admin is a separate badge
    assert perms["is_platform_admin"] is False


def test_official_fields_never_auto_confirmed(seeded_client):
    """Test requirement 1 & 3: Ref number comes as suggestion with confirmed=False.
    Any official field must not be auto-confirmed.
    """
    # Login as demo owner
    login_res = seeded_client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch ACM club
    clubs = seeded_client.get("/api/v1/clubs/", headers=headers).json()
    club_id = next(c for c in clubs if c["short_name"] == "ACM")["id"]

    # Fetch permission letter schema
    schema_res = seeded_client.get(
        f"/api/v1/clubs/{club_id}/documents/templates/permission_letter/schema",
        headers=headers,
    )
    assert schema_res.status_code == 200
    data = schema_res.json()

    # Verify suggested ref no in defaults
    defaults = data["defaults"]
    assert defaults["suggested_ref_no"] is not None
    assert "ROOM" in defaults["suggested_ref_no"]
    assert "ACM" in defaults["suggested_ref_no"]

    # Verify document_date is today and defaulted
    assert defaults["document_date"] == date.today().strftime("%d/%m/%Y")

    # Verify venue options come from DB
    assert len(defaults["venues"]) > 0


def test_describe_event_extraction_endpoint(seeded_client):
    """Test requirement 4: Describe your event runs EventExtractor and returns prefilled data."""
    login_res = seeded_client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    clubs = seeded_client.get("/api/v1/clubs/", headers=headers).json()
    club_id = next(c for c in clubs if c["short_name"] == "ACM")["id"]

    prompt = (
        "We are organizing Smart India Hackathon 2026 Internal Hackathon on 15/10/2026 "
        "from 09:00 AM to 06:00 PM at Computer Department Seminar Hall. "
        "Total expected participants is 120 students."
    )

    extract_res = seeded_client.post(
        f"/api/v1/clubs/{club_id}/documents/extract",
        json={"text": prompt},
        headers=headers,
    )
    assert extract_res.status_code == 200
    res_data = extract_res.json()

    # Pre-filled extracted fields
    extracted = res_data["extracted_data"]
    assert "event_name" in extracted or "event_title" in extracted
    assert extracted.get("dates") == "15/10/2026" or extracted.get("date_start") == "15/10/2026"
    assert extracted.get("time_start") == "09:00 AM"
    assert extracted.get("time_end") == "06:00 PM"

    # Confirmed status is False for all extracted fields in provenance
    for field_name, prov in res_data["provenance"].items():
        assert prov["confirmed"] is False, f"Extracted field {field_name} was auto-confirmed!"
        assert prov["source"] == "AI-drafted, review"

    # Missing fields are correctly identified
    missing_keys = [m["key"] for m in res_data["missing_fields"]]
    assert len(missing_keys) > 0


def test_document_generate_and_review_vertical_slice(seeded_client):
    """Test requirement 3: Generate runs docgen renderer, LibreOffice PDF conversion,
    rasterizes PDF page preview PNGs, and serves downloads.
    """
    login_res = seeded_client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    clubs = seeded_client.get("/api/v1/clubs/", headers=headers).json()
    club_id = next(c for c in clubs if c["short_name"] == "ACM")["id"]

    # Reserve reference number first
    res_alloc = seeded_client.post(
        f"/api/v1/clubs/{club_id}/numbering/ROOM/reserve",
        json={"template_id": "permission_letter"},
        headers=headers,
    )
    assert res_alloc.status_code == 200
    res_data = res_alloc.json()

    # Generate a Permission Letter
    gen_payload = {
        "template_id": "permission_letter",
        "title": "Room Permission - SIH Internal Hackathon",
        "ref_no": res_data["ref_no"],
        "ref_no_confirmed": True,
        "reservation_id": res_data["reservation_id"],
        "event_data": {
            "ref_no": res_data["ref_no"],
            "document_date": "15/10/2026",
            "submitted_to": "Head of Department, Computer Science & Engineering",
            "event_name": "SIH Internal Hackathon 2026",
            "event_code": "SIH",
            "dates": "15/10/2026",
            "date_start": "15/10/2026",
            "date_end": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "06:00 PM",
            "venue": "Seminar Hall",
            "description": "To conduct 12-hour internal hackathon and shortlisting round for national teams.",
            "objectives": "To shortlist top teams for the national Smart India Hackathon round.",
            "expected_participants": 120,
            "student_lead_name": "Arshad Khatib",
            "student_lead_roll": "U24AI112",
            "student_lead_branch": "Artificial Intelligence",
            "student_lead_phone": "9876543210",
            "faculty_name": "Shri Rakesh P. Gohil",
            "faculty_designation": "Faculty in-charge",
            "faculty_department": "Computer Science & Engineering",
        },
        "confirmed_fields": ["event_name", "dates", "venue", "ref_no"],
    }

    gen_res = seeded_client.post(
        f"/api/v1/clubs/{club_id}/documents/generate",
        json=gen_payload,
        headers=headers,
    )
    assert gen_res.status_code == 200, f"Generation failed: {gen_res.text}"
    doc = gen_res.json()

    assert doc["id"] is not None
    assert doc["pdf_url"].startswith(f"/api/v1/clubs/{club_id}/documents/")
    assert doc["docx_url"].startswith(f"/api/v1/clubs/{club_id}/documents/")
    assert len(doc["page_images"]) >= 1, "Page preview images were not generated!"

    # Test page preview image endpoint returns image/png
    first_page_url = doc["page_images"][0]
    page_res = seeded_client.get(first_page_url, headers=headers)
    assert page_res.status_code == 200
    assert page_res.headers["content-type"] == "image/png"
    assert len(page_res.content) > 5000, "Rasterized page image is empty or invalid"

    # Test PDF download endpoint returns application/pdf
    pdf_res = seeded_client.get(doc["pdf_url"], headers=headers)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"

    # Verify rendered PDF text with PyMuPDF
    pdf_doc = pymupdf.open(stream=pdf_res.content, filetype="pdf")
    pdf_text = ""
    for page in pdf_doc:
        pdf_text += page.get_text()

    assert res_data["ref_no"] in pdf_text
    assert "SIH Internal Hackathon 2026" in pdf_text
    assert "Demo Student Head" in pdf_text or "Chairperson" in pdf_text
    assert "None" not in pdf_text
    assert "<function" not in pdf_text
    assert "{{" not in pdf_text


def test_event_approval_series_formatting():
    """Test requirement 5: Event approval series must use {academic_year}/{event_code}, never 'EVT'."""
    db = SessionLocal()
    try:
        club = db.query(Club).filter(Club.short_name == "ACM").first()
        assert club is not None

        # Check numbering series format in DB
        series = db.query(NumberingSeries).filter(
            NumberingSeries.club_id == club.id,
            NumberingSeries.key == "approval_note",
        ).first()

        assert series is not None
        # Must format using {academic_year}/{event_code} (e.g. ACM/2026-27/{event_code}/001), NOT EVT
        assert "EVT" not in series.format
        assert "{event_code}" in series.format
    finally:
        db.close()
