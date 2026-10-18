"""Phase W3.4 Tests:
1. Reservation is the ONLY place a number is allocated:
   - Reserve and generate N documents, series counter equals N exactly.
   - No skipped numbers except reservations that were explicitly expired or released.
2. Canonical reference formatting rules:
   - {short_year} renders as "26-27" for academic year "2026-27".
   - Permission Letter rendered PDF ref matches ^ACM/26-27/ROOM/\\d{3}$.
   - Approval Note rendered PDF ref matches ^ACM/2026-27/[A-Z0-9_]+/\\d{3}$.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from docgen.numbering import compute_short_year, format_reference_number
from server.app.main import app
from server.app.models import (
    Club,
    Document,
    Membership,
    NumberReservation,
    NumberingSeries,
    Template,
    User,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_context(client):
    """Authenticate demo owner and fetch ACM club ID."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    clubs = client.get("/api/v1/clubs/", headers=headers).json()
    acm_club = next(c for c in clubs if c["short_name"] == "ACM")
    return {
        "club_id": acm_club["id"],
        "headers": headers,
    }


def test_w3_4_short_year_canonical_rules():
    """Verify compute_short_year formats short years accurately per specification."""
    assert compute_short_year("2026-27") == "26-27"
    assert compute_short_year("2025-26") == "25-26"
    assert compute_short_year("2026-2027") == "26-27"
    assert compute_short_year("26-27") == "26-27"
    assert compute_short_year("2026") == "26"

    # Verify format_reference_number output
    room_ref = format_reference_number(
        format_pattern="ACM/{short_year}/{series}/{seq:03d}",
        academic_year="2026-27",
        series_key="ROOM",
        seq=9,
    )
    assert room_ref == "ACM/26-27/ROOM/009"

    appr_ref = format_reference_number(
        format_pattern="ACM/{academic_year}/{event_code}/{seq:03d}",
        academic_year="2026-27",
        series_key="SIH",
        seq=1,
        event_code="SIH",
    )
    assert appr_ref == "ACM/2026-27/SIH/001"


def test_w3_4_reserve_and_generate_n_documents_counter_equals_n(client, auth_context, db_session):
    """Directive 1: Reserve and generate N documents. Assert series counter equals N exactly.
    Ensure no numbers are skipped except reservations that were explicitly expired or released.
    """
    club_id = auth_context["club_id"]
    headers = auth_context["headers"]
    series_key = "ROOM"

    ns_init = db_session.query(NumberingSeries).filter(
        NumberingSeries.club_id == club_id,
        NumberingSeries.key == series_key,
    ).first()
    start_seq = ns_init.last_seq if ns_init else 0

    # Reserve and generate 3 documents
    for i in range(1, 4):
        expected_seq = start_seq + i
        res = client.post(
            f"/api/v1/clubs/{club_id}/numbering/{series_key}/reserve",
            json={"template_id": "permission_letter"},
            headers=headers,
        )
        assert res.status_code == 200
        res_data = res.json()
        assert res_data["ref_no"].endswith(f"/{expected_seq:03d}")

        gen_payload = {
            "template_id": "permission_letter",
            "title": f"Sequential Doc {expected_seq}",
            "ref_no": res_data["ref_no"],
            "ref_no_confirmed": True,
            "reservation_id": res_data["reservation_id"],
            "event_data": {
                "event_name": f"Sequential Event {expected_seq}",
                "venue": "Seminar Hall",
                "dates": "15/10/2026",
                "time_start": "09:00 AM",
                "time_end": "05:00 PM",
                "description": f"Sequential test document {expected_seq}",
                "expected_participants": 50,
                "submitted_to": "Head of Department, CSE",
            },
            "confirmed_fields": ["description"],
        }
        gen_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=gen_payload, headers=headers)
        assert gen_res.status_code == 200, f"Generation {expected_seq} failed: {gen_res.text}"

    # Allocate sequence start_seq + 4 as an intentional gap (released)
    res_gap = client.post(
        f"/api/v1/clubs/{club_id}/numbering/{series_key}/reserve",
        json={"template_id": "permission_letter"},
        headers=headers,
    )
    assert res_gap.status_code == 200
    gap_data = res_gap.json()
    assert gap_data["ref_no"].endswith(f"/{(start_seq + 4):03d}")

    # Mark sequence start_seq + 4 as released
    gap_rec = db_session.query(NumberReservation).filter(NumberReservation.id == gap_data["reservation_id"]).first()
    gap_rec.status = "released"
    db_session.commit()

    # Allocate sequence start_seq + 5 and generate final document
    res_final = client.post(
        f"/api/v1/clubs/{club_id}/numbering/{series_key}/reserve",
        json={"template_id": "permission_letter"},
        headers=headers,
    )
    assert res_final.status_code == 200
    final_data = res_final.json()
    assert final_data["ref_no"].endswith(f"/{(start_seq + 5):03d}")

    final_payload = {
        "template_id": "permission_letter",
        "title": "Sequential Doc Final",
        "ref_no": final_data["ref_no"],
        "ref_no_confirmed": True,
        "reservation_id": final_data["reservation_id"],
        "event_data": {
            "event_name": "Sequential Event Final",
            "venue": "Seminar Hall",
            "dates": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "05:00 PM",
            "description": "Sequential test document final",
            "expected_participants": 50,
            "submitted_to": "Head of Department, CSE",
        },
        "confirmed_fields": ["description"],
    }
    final_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=final_payload, headers=headers)
    assert final_res.status_code == 200

    # Assert the series counter in DB equals start_seq + 5 exactly!
    ns = db_session.query(NumberingSeries).filter(
        NumberingSeries.club_id == club_id,
        NumberingSeries.key == series_key,
    ).first()
    assert ns is not None
    assert ns.last_seq == start_seq + 5, f"Expected counter to be {start_seq + 5}, got {ns.last_seq}"

    # Verify all sequence numbers start_seq + 1 .. start_seq + 5 are recorded with no gaps except the released one
    reservations = db_session.query(NumberReservation).filter(
        NumberReservation.club_id == club_id,
        NumberReservation.series_key == series_key,
        NumberReservation.sequence_num > start_seq,
    ).order_by(NumberReservation.sequence_num.asc()).all()

    seq_map = {r.sequence_num: r.status for r in reservations}
    expected_range = list(range(start_seq + 1, start_seq + 6))
    assert list(seq_map.keys()) == expected_range
    assert seq_map[start_seq + 1] == "used"
    assert seq_map[start_seq + 2] == "used"
    assert seq_map[start_seq + 3] == "used"
    assert seq_map[start_seq + 4] == "released"
    assert seq_map[start_seq + 5] == "used"


def test_w3_4_rendered_pdf_reference_format(client, auth_context, db_session):
    """Directive 2: Rendered-PDF test.
    The Permission Letter ref matches ^ACM/26-27/ROOM/\\d{3}$
    and the Approval Note ref matches ^ACM/2026-27/[A-Z0-9_]+/\\d{3}$.
    """
    club_id = auth_context["club_id"]
    headers = auth_context["headers"]

    # 1. Permission Letter
    res_perm = client.post(
        f"/api/v1/clubs/{club_id}/numbering/ROOM/reserve",
        json={"template_id": "permission_letter"},
        headers=headers,
    )
    assert res_perm.status_code == 200
    data_perm = res_perm.json()
    assert re.match(r"^ACM/26-27/ROOM/\d{3}$", data_perm["ref_no"]), f"Ref number '{data_perm['ref_no']}' does not match pattern"

    perm_payload = {
        "template_id": "permission_letter",
        "title": "Permission Letter PDF Ref Pattern",
        "ref_no": data_perm["ref_no"],
        "ref_no_confirmed": True,
        "reservation_id": data_perm["reservation_id"],
        "event_data": {
            "event_name": "Permission Letter PDF Ref Pattern",
            "venue": "Seminar Hall",
            "dates": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "05:00 PM",
            "description": "Rendered PDF ref number verification for permission letter",
            "expected_participants": 50,
            "submitted_to": "Head of Department, CSE",
        },
        "confirmed_fields": ["description"],
    }
    perm_doc_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=perm_payload, headers=headers)
    assert perm_doc_res.status_code == 200
    perm_doc_id = perm_doc_res.json()["id"]

    # 2. Approval Note
    res_appr = client.post(
        f"/api/v1/clubs/{club_id}/numbering/SIH/reserve",
        json={"template_id": "approval_note", "event_code": "SIH"},
        headers=headers,
    )
    assert res_appr.status_code == 200
    data_appr = res_appr.json()
    assert re.match(r"^ACM/2026-27/[A-Z0-9_]+/\d{3}$", data_appr["ref_no"]), f"Ref number '{data_appr['ref_no']}' does not match pattern"

    appr_payload = {
        "template_id": "approval_note",
        "title": "Approval Note PDF Ref Pattern",
        "ref_no": data_appr["ref_no"],
        "ref_no_confirmed": True,
        "reservation_id": data_appr["reservation_id"],
        "event_data": {
            "event_name": "Approval Note PDF Ref Pattern",
            "event_code": "SIH",
            "category": "Hackathon",
            "target_audience": "All Students",
            "document_date": "15/10/2026",
            "dates": "15/10/2026",
            "venue": "Seminar Hall",
            "budget_items": [
                {"item": "Banners", "amount": 500},
            ],
            "description": "Rendered PDF ref number verification for approval note",
            "objectives": "Verify exact ref formatting in PDF",
            "expected_participants": 100,
        },
        "confirmed_fields": ["description", "objectives"],
    }
    appr_doc_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=appr_payload, headers=headers)
    assert appr_doc_res.status_code == 200
    appr_doc_id = appr_doc_res.json()["id"]

    # Extract and assert Permission Letter PDF text
    perm_pdf_files = list((Path("storage/documents") / perm_doc_id / "v1").glob("*.pdf"))
    assert perm_pdf_files, f"No PDF found for permission letter {perm_doc_id}"
    perm_doc = pymupdf.open(str(perm_pdf_files[0]))
    perm_text = "".join(p.get_text() for p in perm_doc)
    perm_doc.close()

    assert re.search(r"ACM/26-27/ROOM/\d{3}", perm_text), (
        f"Permission Letter PDF text did not contain ^ACM/26-27/ROOM/\\d{{3}}$ pattern! Content snippet: {perm_text[:500]}"
    )

    # Extract and assert Approval Note PDF text
    appr_pdf_files = list((Path("storage/documents") / appr_doc_id / "v1").glob("*.pdf"))
    assert appr_pdf_files, f"No PDF found for approval note {appr_doc_id}"
    appr_doc = pymupdf.open(str(appr_pdf_files[0]))
    appr_text = "".join(p.get_text() for p in appr_doc)
    appr_doc.close()

    assert re.search(r"ACM/2026-27/[A-Z0-9_]+/\d{3}", appr_text), (
        f"Approval Note PDF text did not contain ^ACM/2026-27/[A-Z0-9_]+/\\d{{3}}$ pattern! Content snippet: {appr_text[:500]}"
    )
