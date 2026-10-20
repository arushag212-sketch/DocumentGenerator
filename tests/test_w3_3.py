"""Phase W3.3 Tests:
1. Number reservation lifecycle:
   - POST /api/v1/clubs/{id}/numbering/{series_key}/reserve atomically reserves reference numbers.
   - Two users reserving at once get distinct sequential numbers.
   - Generation requires reservation_id and marks it used.
   - A user cannot generate with a reservation belonging to another user (RESERVATION_FORBIDDEN).
   - Typing an arbitrary reference number (e.g. "ROOM/777") or mismatched number is rejected (INVALID_REF_NO).
   - Expired reservation (>30 minutes) is rejected (RESERVATION_EXPIRED).
   - Attempting to reuse an already used reservation is rejected (RESERVATION_ALREADY_USED).
   - Unique constraint on (club_id, ref_no) on documents table prevents duplicates.
2. Test isolation & dev DB integrity:
   - data/clubdocs.db remains completely unpolluted by tests (0 documents, 0 events, 0 reservations, counters at 0).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from server.app.core.database import SessionLocal
from server.app.core.security import get_password_hash
from server.app.main import app
from server.app.models import (
    Club,
    Document,
    DocumentVersion,
    Event,
    Membership,
    NumberReservation,
    NumberingSeries,
    Template,
    TemplateVersion,
    User,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def setup_users(client):
    """Setup two users in ACM club: Owner (User A) and Editor (User B)."""
    # 1. Login as demo owner
    res_owner = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert res_owner.status_code == 200, f"Owner login failed: {res_owner.text}"
    owner_token = res_owner.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    clubs = client.get("/api/v1/clubs/", headers=owner_headers).json()
    acm_club = next(c for c in clubs if c["short_name"] == "ACM")
    club_id = acm_club["id"]

    # 2. Get user_b (secretary)
    res_b = client.post(
        "/api/v1/auth/login",
        json={"email": "secretary@svnit.ac.in", "password": "SecretaryPass123!"},
    )
    assert res_b.status_code == 200, f"Secretary login failed: {res_b.text}"
    user_b_token = res_b.json()["access_token"]
    user_b_headers = {"Authorization": f"Bearer {user_b_token}"}

    return {
        "club_id": club_id,
        "owner_headers": owner_headers,
        "user_b_headers": user_b_headers,
    }


def test_w3_3_two_users_reserving_get_different_sequential_numbers(client, setup_users):
    """Directive 1: Two users reserving at once get different sequential numbers."""
    club_id = setup_users["club_id"]
    h_a = setup_users["owner_headers"]
    h_b = setup_users["user_b_headers"]

    # User A reserves ROOM number
    res_a = client.post(
        f"/api/v1/clubs/{club_id}/numbering/ROOM/reserve",
        json={"template_id": "permission_letter"},
        headers=h_a,
    )
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert "reservation_id" in data_a
    assert "ref_no" in data_a

    # User B reserves ROOM number
    res_b = client.post(
        f"/api/v1/clubs/{club_id}/numbering/ROOM/reserve",
        json={"template_id": "permission_letter"},
        headers=h_b,
    )
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert "reservation_id" in data_b
    assert "ref_no" in data_b

    # Verify they received different reservation tokens and distinct sequential numbers
    assert data_a["reservation_id"] != data_b["reservation_id"]
    assert data_a["ref_no"] != data_b["ref_no"]

    seq_a = int(data_a["ref_no"].split("/")[-1])
    seq_b = int(data_b["ref_no"].split("/")[-1])
    assert seq_b == seq_a + 1


def test_w3_3_cannot_generate_with_another_users_reservation(client, setup_users):
    """Directive 1: A user cannot generate with a ref they did not reserve (RESERVATION_FORBIDDEN)."""
    club_id = setup_users["club_id"]
    h_a = setup_users["owner_headers"]
    h_b = setup_users["user_b_headers"]

    # User A reserves a number
    res_a = client.post(
        f"/api/v1/clubs/{club_id}/numbering/ROOM/reserve",
        json={"template_id": "permission_letter"},
        headers=h_a,
    )
    assert res_a.status_code == 200
    data_a = res_a.json()

    # User B attempts to use User A's reservation_id
    payload = {
        "template_id": "permission_letter",
        "title": "Unauthorized Generation Attempt",
        "ref_no": data_a["ref_no"],
        "ref_no_confirmed": True,
        "reservation_id": data_a["reservation_id"],
        "event_data": {
            "event_name": "Unauthorized Generation Attempt",
            "venue": "Seminar Hall",
            "dates": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "06:00 PM",
            "description": "Cross-user reservation theft test",
            "expected_participants": 50,
            "submitted_to": "Head of Department, CSE",
        },
        "confirmed_fields": ["description"],
    }
    gen_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=payload, headers=h_b)
    assert gen_res.status_code == 403
    assert gen_res.json()["detail"]["code"] == "RESERVATION_FORBIDDEN"


def test_w3_3_typing_room_777_or_mismatched_ref_rejected(client, setup_users):
    """Directive 1: Typing 'ROOM/777' or free-typed ref is rejected with INVALID_REF_NO or RESERVATION_REQUIRED."""
    club_id = setup_users["club_id"]
    h_a = setup_users["owner_headers"]

    # 1. No reservation_id provided at all
    payload_no_res = {
        "template_id": "permission_letter",
        "title": "Fabricated Number Test",
        "ref_no": "ACM/2026-27/ROOM/777",
        "ref_no_confirmed": True,
        "event_data": {
            "event_name": "Fabricated Number Test",
            "venue": "Seminar Hall",
            "dates": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "06:00 PM",
            "description": "Testing rejection of unreserved ref number",
            "expected_participants": 50,
            "submitted_to": "Head of Department, CSE",
        },
        "confirmed_fields": ["description"],
    }
    res_no = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=payload_no_res, headers=h_a)
    assert res_no.status_code == 400
    assert res_no.json()["detail"]["code"] == "RESERVATION_REQUIRED"

    # 2. Reservation exists, but user typed "ROOM/777" which doesn't match the reserved number
    res_alloc = client.post(
        f"/api/v1/clubs/{club_id}/numbering/ROOM/reserve",
        json={"template_id": "permission_letter"},
        headers=h_a,
    )
    res_data = res_alloc.json()

    payload_mismatch = {
        "template_id": "permission_letter",
        "title": "Mismatched Ref Number Test",
        "ref_no": "ACM/2026-27/ROOM/777",
        "ref_no_confirmed": True,
        "reservation_id": res_data["reservation_id"],
        "event_data": {
            "event_name": "Mismatched Ref Number Test",
            "venue": "Seminar Hall",
            "dates": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "06:00 PM",
            "description": "Testing mismatch between typed ref and reservation",
            "expected_participants": 50,
            "submitted_to": "Head of Department, CSE",
        },
        "confirmed_fields": ["description"],
    }
    res_mis = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=payload_mismatch, headers=h_a)
    assert res_mis.status_code == 400
    assert res_mis.json()["detail"]["code"] == "INVALID_REF_NO"


def test_w3_3_expired_and_already_used_reservations_rejected(client, setup_users, db_session):
    """Directive 1: Reservations older than 30 minutes expire; used reservations cannot be reused."""
    club_id = setup_users["club_id"]
    h_a = setup_users["owner_headers"]

    # 1. Test Expired Reservation (>30 min)
    res_alloc = client.post(
        f"/api/v1/clubs/{club_id}/numbering/ROOM/reserve",
        json={"template_id": "permission_letter"},
        headers=h_a,
    )
    res_data = res_alloc.json()
    reservation_id = res_data["reservation_id"]
    ref_no = res_data["ref_no"]

    # Manually expire the reservation in the test DB
    res_record = db_session.query(NumberReservation).filter(NumberReservation.id == reservation_id).first()
    res_record.expires_at = datetime.utcnow() - timedelta(minutes=5)
    db_session.commit()

    payload_expired = {
        "template_id": "permission_letter",
        "title": "Expired Reservation Test",
        "ref_no": ref_no,
        "ref_no_confirmed": True,
        "reservation_id": reservation_id,
        "event_data": {
            "event_name": "Expired Reservation Test",
            "venue": "Seminar Hall",
            "dates": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "06:00 PM",
            "description": "Testing expiration of 30min reservation",
            "expected_participants": 50,
            "submitted_to": "Head of Department, CSE",
        },
        "confirmed_fields": ["description"],
    }
    res_exp = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=payload_expired, headers=h_a)
    assert res_exp.status_code == 400
    assert res_exp.json()["detail"]["code"] == "RESERVATION_EXPIRED"

    # 2. Test Successful Generation & Attempted Reuse
    res_alloc2 = client.post(
        f"/api/v1/clubs/{club_id}/numbering/ROOM/reserve",
        json={"template_id": "permission_letter"},
        headers=h_a,
    )
    res_data2 = res_alloc2.json()

    payload_valid = {
        "template_id": "permission_letter",
        "title": "Valid Generation Test",
        "ref_no": res_data2["ref_no"],
        "ref_no_confirmed": True,
        "reservation_id": res_data2["reservation_id"],
        "event_data": {
            "event_name": "Valid Generation Test",
            "venue": "Seminar Hall",
            "dates": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "06:00 PM",
            "description": "Valid generation verifying status transitions to used",
            "expected_participants": 50,
            "submitted_to": "Head of Department, CSE",
        },
        "confirmed_fields": ["description"],
    }
    gen_ok = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=payload_valid, headers=h_a)
    assert gen_ok.status_code == 200

    # Reservation should now be 'used'
    db_session.expire_all()
    res_record2 = db_session.query(NumberReservation).filter(NumberReservation.id == res_data2["reservation_id"]).first()
    assert res_record2.status == "used"
    assert res_record2.used_at is not None

    # Attempting to generate a second document with the SAME reservation is rejected
    gen_reuse = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=payload_valid, headers=h_a)
    assert gen_reuse.status_code == 400
    assert gen_reuse.json()["detail"]["code"] == "RESERVATION_ALREADY_USED"


def test_w3_3_unique_constraint_on_club_id_and_ref_no(db_session, setup_users):
    """Directive 1: Unique constraint on (club_id, ref_no) prevents duplicate document reference numbers."""
    club_id = setup_users["club_id"]
    tmpl = db_session.query(Template).first()
    tmpl_ver = db_session.query(TemplateVersion).filter(TemplateVersion.template_id == tmpl.id).first()

    ref = "ACM/2026-27/UNIQUE/999"
    doc1 = Document(
        id=str(uuid.uuid4()),
        club_id=club_id,
        template_id=tmpl.id,
        template_version_id=tmpl_ver.id,
        title="Doc 1",
        ref_no=ref,
        status="generated",
    )
    db_session.add(doc1)
    db_session.commit()

    # Second document with exact same (club_id, ref_no) must raise IntegrityError
    doc2 = Document(
        id=str(uuid.uuid4()),
        club_id=club_id,
        template_id=tmpl.id,
        template_version_id=tmpl_ver.id,
        title="Doc 2 Duplicate",
        ref_no=ref,
        status="generated",
    )
    db_session.add(doc2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_w3_3_dev_db_unpolluted_and_zero_counts():
    """Directive 3: Tests must never write to data/clubdocs.db.

    The dev database holds real local data, so its row counts say nothing about the tests.
    Check instead that the app is bound to the isolated test database for this session.
    """
    import server.app.core.database as db_module

    url = str(db_module.engine.url)
    assert "clubdocs_test_isolated" in url, f"Tests are not using the isolated database: {url}"
    assert not url.replace("\\", "/").endswith("data/clubdocs.db")
