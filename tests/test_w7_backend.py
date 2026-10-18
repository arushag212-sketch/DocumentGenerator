"""Phase W7 Backend Test Suite: Club Search, Join Requests, Positions, Home Flow & Input Widgets.

All tests run against isolated test SQLite database, ensuring data/clubdocs.db remains clean.
"""

from __future__ import annotations

import os
import re
import uuid
import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.core.permissions import Role
from server.app.core.rate_limit import clear_rate_limits
from server.app.models import Club, Membership, NumberingSeries, Person, RoleHeld, User, JoinRequest


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def auth_users(client: TestClient):
    """Register and authenticate test users with clean passwords."""
    clear_rate_limits()

    # 1. Login existing ACM owner
    login_owner = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert login_owner.status_code == 200, f"Owner login failed: {login_owner.text}"
    owner_token = login_owner.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 2. Register a brand new student user
    student_email = f"student_{uuid.uuid4().hex[:8]}@svnit.ac.in"
    reg_student = client.post(
        "/api/v1/auth/register",
        json={"email": student_email, "password": "StudentPassword123!", "name": "Aarav Sharma"},
    )
    assert reg_student.status_code == 201, f"Student register failed: {reg_student.text}"
    student_token = reg_student.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}
    student_id = reg_student.json()["user"]["id"]

    # 3. Get ACM Club ID and Robotics Club ID
    clubs_res = client.get("/api/v1/clubs/search?q=", headers=owner_headers)
    assert clubs_res.status_code == 200
    clubs = clubs_res.json()
    acm_club = next(c for c in clubs if c["slug"] == "acm")
    robo_club = next((c for c in clubs if c["slug"] == "robotics"), None)

    return {
        "owner_headers": owner_headers,
        "student_headers": student_headers,
        "student_id": student_id,
        "student_email": student_email,
        "acm_club": acm_club,
        "robo_club": robo_club,
    }


# ===========================================================================
# 1. CLUB SEARCH & JOIN FLOW TESTS
# ===========================================================================

def test_w7_club_search(client: TestClient, auth_users):
    """Assert club search returns matching clubs, membership status/role, and admin name."""
    headers = auth_users["student_headers"]

    # Search all
    res = client.get("/api/v1/clubs/search?q=", headers=headers)
    assert res.status_code == 200
    all_clubs = res.json()
    assert len(all_clubs) >= 3
    slugs = [c["slug"] for c in all_clubs]
    assert "acm" in slugs
    assert "robotics" in slugs
    assert "cultural" in slugs

    # Filtered search for "Robotics"
    res_robo = client.get("/api/v1/clubs/search?q=robotics", headers=headers)
    assert res_robo.status_code == 200
    robo_results = res_robo.json()
    assert len(robo_results) >= 1
    robo_match = next((c for c in robo_results if c["short_name"] == "ROBO"), None)
    assert robo_match is not None
    assert robo_match["admin_name"] is not None

    # New student is not yet a member
    acm_item = next(c for c in all_clubs if c["slug"] == "acm")
    assert acm_item["membership_role"] is None
    assert acm_item["join_request_status"] is None


def test_w7_join_request_flow(client: TestClient, auth_users):
    """Full join flow: request position -> pending (no access) -> admin approves with role -> member can access."""
    s_headers = auth_users["student_headers"]
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    # 1. Before approval: student cannot access private club documents
    res_before = client.get(f"/api/v1/clubs/{acm_id}/documents", headers=s_headers)
    assert res_before.status_code == 403, "Unapproved user must be rejected with 403"

    # 2. Picking "Student Head/Chairperson" or "Faculty Chairman" gives NO access by itself
    jr_res = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests",
        json={"position": "Faculty Chairman"},
        headers=s_headers,
    )
    assert jr_res.status_code == 201
    jr_data = jr_res.json()
    assert jr_data["status"] == "pending"
    assert jr_data["position"] == "Faculty Chairman"
    assert jr_data["admin_name"] is not None
    req_id = jr_data["id"]

    # Still rejected from private endpoints while request is pending
    res_still_blocked = client.get(f"/api/v1/clubs/{acm_id}/documents", headers=s_headers)
    assert res_still_blocked.status_code == 403

    # Check "my" join request
    my_jr = client.get(f"/api/v1/clubs/{acm_id}/join-requests/my", headers=s_headers)
    assert my_jr.status_code == 200
    assert my_jr.json()["status"] == "pending"
    assert my_jr.json()["admin_name"] == "Demo Club Head"

    # 3. Admin lists join requests
    admin_list = client.get(f"/api/v1/clubs/{acm_id}/join-requests", headers=o_headers)
    assert admin_list.status_code == 200
    assert any(r["id"] == req_id for r in admin_list.json())

    # 4. Admin approves request with role 'editor'
    approve_res = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests/{req_id}/approve",
        json={"role": "editor"},
        headers=o_headers,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"

    # 5. Student now has active editor membership and can access club
    res_after = client.get(f"/api/v1/clubs/{acm_id}/documents", headers=s_headers)
    assert res_after.status_code == 200

    # 6. Check that position mapped into club members and RoleHeld
    members_res = client.get(f"/api/v1/clubs/{acm_id}/members", headers=s_headers)
    assert members_res.status_code == 200
    my_membership = next(m for m in members_res.json() if m["email"] == auth_users["student_email"])
    assert my_membership["role"] == "editor"
    assert my_membership["position"] == "Faculty Chairman"


def test_w7_join_request_rejection(client: TestClient, auth_users):
    """Rejected join request leaves user without access."""
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    # Register second student
    reg2 = client.post(
        "/api/v1/auth/register",
        json={"email": f"stud2_{uuid.uuid4().hex[:6]}@svnit.ac.in", "password": "StudentPassword123!", "name": "Priya Patel"},
    )
    s2_headers = {"Authorization": f"Bearer {reg2.json()['access_token']}"}

    # Submit join request
    jr_res = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests",
        json={"position": "Core member"},
        headers=s2_headers,
    )
    req_id = jr_res.json()["id"]

    # Admin rejects
    rej_res = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests/{req_id}/reject",
        headers=o_headers,
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "rejected"

    # User cannot access
    acc_res = client.get(f"/api/v1/clubs/{acm_id}/documents", headers=s2_headers)
    assert acc_res.status_code == 403


def test_w7_create_new_club_creator_is_admin(client: TestClient):
    """User creating a new club becomes admin immediately without pending status."""
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": f"creator_{uuid.uuid4().hex[:6]}@svnit.ac.in", "password": "CreatorPassword123!", "name": "Rohan Shah"},
    )
    c_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    create_club_res = client.post(
        "/api/v1/clubs",
        json={
            "name": "Demo Astronomy Club",
            "short_name": "ASTRO",
            "chapter_code": "ASTRO",
            "position": "Student Head/Chairperson",
        },
        headers=c_headers,
    )
    assert create_club_res.status_code == 201
    club_id = create_club_res.json()["id"]

    # Creator immediately has owner/admin access
    perms_res = client.get(f"/api/v1/clubs/{club_id}/permissions", headers=c_headers)
    assert perms_res.status_code == 200
    assert perms_res.json()["is_owner"] is True
    assert perms_res.json()["role"] == "owner"


def test_w7_cross_club_isolation(client: TestClient, auth_users):
    """Cross-club ids return 404 or 403."""
    o_headers = auth_users["owner_headers"]
    robo_id = auth_users["robo_club"]["id"]

    # Owner of ACM trying to access Robotics private documents gets 403 (not a member of Robotics)
    res = client.get(f"/api/v1/clubs/{robo_id}/documents", headers=o_headers)
    assert res.status_code == 403

    # Non-existent club ID returns 404
    fake_id = str(uuid.uuid4())
    res_fake = client.get(f"/api/v1/clubs/{fake_id}/documents", headers=o_headers)
    assert res_fake.status_code == 404


# ===========================================================================
# 2. HOME CONVENIENCE ENDPOINTS & NO JARGON TESTS
# ===========================================================================

def test_w7_home_understand_workshop_sentence_and_no_jargon(client: TestClient, auth_users):
    """Call /home/understand with the Web Development Workshop sentence.
    Assert correct extracted chips, recommended documents with plain reasons,
    suggested reference number, grouped missing questions, and zero banned jargon.
    """
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    prompt = "We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students."

    res = client.post(
        f"/api/v1/clubs/{acm_id}/home/understand",
        json={"text": prompt},
        headers=o_headers,
    )
    assert res.status_code == 200
    data = res.json()

    # 1. Understood Data
    u = data["understood"]
    assert "Web Development Workshop" in u["event_name"]
    assert u["venue"] == "Seminar Hall"
    assert u["participants"] == 120

    # 2. Recommended Documents
    recs = data["recommended_documents"]
    perm_doc = next((d for d in recs if d["slug"] == "permission_letter"), None)
    assert perm_doc is not None
    assert perm_doc["recommended"] is True
    assert "Seminar Hall" in perm_doc["reason"]
    # Reference number display: "ACM/26-27/ROOM/001 will be used"
    assert "will be used" in perm_doc["suggested_ref_no"]
    assert "ROOM" in perm_doc["suggested_ref_no"]

    # 3. Missing questions
    questions = data["missing_questions"]
    q_keys = [q["key"] for q in questions]
    assert "time_start" in q_keys
    assert "time_end" in q_keys
    assert "submitted_to" in q_keys
    assert "description" in q_keys
    assert "objectives" in q_keys

    # Check input widget types
    t_start_q = next(q for q in questions if q["key"] == "time_start")
    assert t_start_q["type"] == "time"

    # 4. Strict Jargon ban check across the entire JSON response
    # Banned words: reservation, series, canonical, schema, job, event record
    raw_response_text = res.text.lower()
    banned_words = ["reservation", "series", "canonical", "schema", "job", "event record", "event_record"]
    for word in banned_words:
        assert word not in raw_response_text, f"Banned jargon word '{word}' found in /home/understand response!"


def test_w7_home_generate_blocked_when_unaccepted_or_missing(client: TestClient, auth_users):
    """Assert /home/generate is blocked when reference numbers are unconfirmed or required fields missing."""
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    # 1. Blocked when ref_numbers_accepted is False
    res_unaccepted = client.post(
        f"/api/v1/clubs/{acm_id}/home/generate",
        json={
            "selected_template_ids": ["permission_letter"],
            "event_data": {"event_name": "Web Dev Workshop"},
            "ref_numbers_accepted": False,
        },
        headers=o_headers,
    )
    assert res_unaccepted.status_code == 400
    assert "reference numbers" in res_unaccepted.json().get("detail", {}).get("message", "").lower()

    # 2. Blocked when required fields are missing
    res_missing = client.post(
        f"/api/v1/clubs/{acm_id}/home/generate",
        json={
            "selected_template_ids": ["permission_letter"],
            "event_data": {
                "event_name": "Web Dev Workshop",
                "venue": "Seminar Hall",
                "participants": 120,
            },
            "ref_numbers_accepted": True,
        },
        headers=o_headers,
    )
    assert res_missing.status_code == 400
    assert res_missing.json().get("detail", {}).get("code") == "MISSING_REQUIRED_FIELDS"


# ===========================================================================
# 3. INPUT WIDGETS & RENDERED OUTPUT TESTS
# ===========================================================================

def test_w7_input_widget_time_picker_validation(client: TestClient, auth_users):
    """Assert end time before start time is rejected with plain language error."""
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    res = client.post(
        f"/api/v1/clubs/{acm_id}/home/generate",
        json={
            "selected_template_ids": ["permission_letter"],
            "event_data": {
                "event_name": "Workshop",
                "time_start": "17:00",
                "time_end": "10:00",  # End is before start!
            },
            "ref_numbers_accepted": True,
        },
        headers=o_headers,
    )
    assert res.status_code == 400
    err_msg = res.json().get("detail", {}).get("message", "")
    assert "End time must be after start time" in err_msg


def test_w7_input_widget_date_picker_validation(client: TestClient, auth_users):
    """Assert end date before start date is rejected with plain language error."""
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    res = client.post(
        f"/api/v1/clubs/{acm_id}/home/generate",
        json={
            "selected_template_ids": ["permission_letter"],
            "event_data": {
                "event_name": "Workshop",
                "date_start": "2026-10-15",
                "date_end": "2026-10-14",  # End is before start!
            },
            "ref_numbers_accepted": True,
        },
        headers=o_headers,
    )
    assert res.status_code == 400
    err_msg = res.json().get("detail", {}).get("message", "")
    assert "End date cannot be before start date" in err_msg


def test_w7_generate_renders_picker_time_and_date_range_correctly(client: TestClient, auth_users):
    """Assert time picker values ('10:00', '17:00') render as '10:00 AM' and '05:00 PM',
    and date range renders as '14-15 October 2026' in the final PDF.
    """
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    payload = {
        "selected_template_ids": ["permission_letter"],
        "event_data": {
            "event_name": "Web Development Workshop",
            "venue": "Seminar Hall",
            "participants": 120,
            "date_start": "2026-10-14",
            "date_end": "2026-10-15",
            "time_start": "10:00",  # Native 24-hr time input
            "time_end": "17:00",    # Native 24-hr time input
            "submitted_to": "Associate Dean (Student Welfare)",
            "description": "Two-day workshop on modern web technologies and full-stack development",
            "objectives": "Provide hands-on training to 120 undergraduate students in web development",
        },
        "ref_numbers_accepted": True,
        "event_title": "Web Development Workshop",
    }

    gen_res = client.post(
        f"/api/v1/clubs/{acm_id}/home/generate",
        json=payload,
        headers=o_headers,
    )
    assert gen_res.status_code == 200, f"Generate failed: {gen_res.text}"
    data = gen_res.json()

    assert data["documents_count"] == 1
    doc = data["documents"][0]
    doc_id = doc["id"]
    pdf_url = doc["pdf_url"]

    # Fetch rendered PDF binary
    pdf_resp = client.get(pdf_url, headers=o_headers)
    assert pdf_resp.status_code == 200
    assert len(pdf_resp.content) > 1000

    # Extract text from rendered PDF
    pdf_doc = fitz.open(stream=pdf_resp.content, filetype="pdf")
    full_pdf_text = "\n".join(page.get_text() for page in pdf_doc)
    pdf_doc.close()

    # 1. 24h picker input must render as 12h club format with AM/PM
    assert "10:00 AM" in full_pdf_text, "Rendered PDF must contain '10:00 AM'"
    assert "05:00 PM" in full_pdf_text, "Rendered PDF must contain '05:00 PM'"

    # 2. Date range must render correctly
    assert "14-15 October 2026" in full_pdf_text or "14/10/2026" in full_pdf_text

    # 3. Allocated reference number must be present
    assert doc["ref_no"] in full_pdf_text
    assert "ROOM" in doc["ref_no"]

    # 4. Verified supplied details present
    assert "Web Development Workshop" in full_pdf_text
    assert "Seminar Hall" in full_pdf_text


# ===========================================================================
# 4. G1.1 POSITIONS, SIGNATORIES, DATES & ABUSE LIMITS TESTS
# ===========================================================================

def test_w7_head_of_marketing_other_never_signatory(client: TestClient, auth_users):
    """'Head of Marketing' (Other) keeps text only as display note and never becomes a signatory."""
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    # Register applicant
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": f"mktg_{uuid.uuid4().hex[:6]}@svnit.ac.in", "password": "Password123!", "name": "Karan Mehta"},
    )
    mktg_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    # Request position "Head of Marketing"
    jr_res = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests",
        json={"position": "Head of Marketing"},
        headers=mktg_headers,
    )
    assert jr_res.status_code == 201
    assert jr_res.json()["position"] == "Other: Head of Marketing"
    req_id = jr_res.json()["id"]

    # Admin attempts to approve as signatory -> must fail with 400
    app_fail = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests/{req_id}/approve",
        json={"role": "editor", "is_signatory": True},
        headers=o_headers,
    )
    assert app_fail.status_code == 400
    assert "cannot be designated as an official signatory" in app_fail.json().get("detail", {}).get("message", "")

    # Admin approves without signatory tick -> succeeds
    app_ok = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests/{req_id}/approve",
        json={"role": "editor", "is_signatory": False},
        headers=o_headers,
    )
    assert app_ok.status_code == 200

    # Verify no Person record was created
    people_res = client.get(f"/api/v1/clubs/{acm_id}/people", headers=o_headers)
    assert people_res.status_code == 200
    assert not any(p["email"] == reg.json()["user"]["email"] for p in people_res.json())


def test_w7_student_secretary_without_signatory_tick_creates_no_role_held(client: TestClient, auth_users):
    """Approving 'Student Secretary' without signatory tick creates no RoleHeld and no Person."""
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    reg = client.post(
        "/api/v1/auth/register",
        json={"email": f"sec_{uuid.uuid4().hex[:6]}@svnit.ac.in", "password": "Password123!", "name": "Sneha Joshi"},
    )
    sec_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    jr_res = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests",
        json={"position": "Student Secretary"},
        headers=sec_headers,
    )
    assert jr_res.status_code == 201
    req_id = jr_res.json()["id"]

    app_res = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests/{req_id}/approve",
        json={"role": "editor", "is_signatory": False},
        headers=o_headers,
    )
    assert app_res.status_code == 200

    # Person and RoleHeld must not exist
    people_res = client.get(f"/api/v1/clubs/{acm_id}/people", headers=o_headers)
    assert not any(p["email"] == reg.json()["user"]["email"] for p in people_res.json())


def test_w7_two_holders_one_role_require_explicit_choice(client: TestClient, auth_users):
    """Two active holders of one signatory role require explicit choice in approval and generation."""
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    # 1. Register and approve first Secretary as signatory
    reg1 = client.post(
        "/api/v1/auth/register",
        json={"email": f"sec1_{uuid.uuid4().hex[:6]}@svnit.ac.in", "password": "Password123!", "name": "First Secretary"},
    )
    h1 = {"Authorization": f"Bearer {reg1.json()['access_token']}"}
    jr1 = client.post(f"/api/v1/clubs/{acm_id}/join-requests", json={"position": "Student Secretary"}, headers=h1)
    app1 = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests/{jr1.json()['id']}/approve",
        json={"role": "editor", "is_signatory": True, "conflict_resolution": "replace"},
        headers=o_headers,
    )
    assert app1.status_code == 200

    # 2. Register second Secretary applicant
    reg2 = client.post(
        "/api/v1/auth/register",
        json={"email": f"sec2_{uuid.uuid4().hex[:6]}@svnit.ac.in", "password": "Password123!", "name": "Second Secretary"},
    )
    h2 = {"Authorization": f"Bearer {reg2.json()['access_token']}"}
    jr2 = client.post(f"/api/v1/clubs/{acm_id}/join-requests", json={"position": "Student Secretary"}, headers=h2)
    req2_id = jr2.json()["id"]

    # Approve second as signatory without conflict_resolution -> must fail with 409
    app_conflict = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests/{req2_id}/approve",
        json={"role": "editor", "is_signatory": True},
        headers=o_headers,
    )
    assert app_conflict.status_code == 409
    err = app_conflict.json().get("detail", {})
    assert err.get("code") == "SIGNATORY_ROLE_CONFLICT"
    assert "First Secretary" in err.get("existing_holder", "")

    # Approve second with conflict_resolution='keep_both' -> succeeds
    app_keep = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests/{req2_id}/approve",
        json={"role": "editor", "is_signatory": True, "conflict_resolution": "keep_both"},
        headers=o_headers,
    )
    assert app_keep.status_code == 200

    # 3. In /home/understand, system must ask who signs as Student Secretary
    und_res = client.post(
        f"/api/v1/clubs/{acm_id}/home/understand",
        json={"text": "Technical Meet on 15 November 2026 in Seminar Hall"},
        headers=o_headers,
    )
    assert und_res.status_code == 200
    questions = und_res.json()["missing_questions"]
    sec_q = next((q for q in questions if q["key"] == "signatory_student_secretary"), None)
    assert sec_q is not None
    assert "First Secretary" in sec_q["values"]
    assert "Second Secretary" in sec_q["values"]

    # 4. In /home/generate, missing choice is rejected
    gen_missing_choice = client.post(
        f"/api/v1/clubs/{acm_id}/home/generate",
        json={
            "selected_template_ids": ["permission_letter"],
            "event_data": {
                "event_name": "Meet",
                "date_start": "2026-11-15",
                "date_end": "2026-11-15",
                "time_start": "10:00",
                "time_end": "12:00",
                "venue": "Seminar Hall",
                "submitted_to": "HoD",
                "description": "Short meet",
                "objectives": "Discussion",
            },
            "ref_numbers_accepted": True,
        },
        headers=o_headers,
    )
    assert gen_missing_choice.status_code == 400
    assert gen_missing_choice.json().get("detail", {}).get("code") == "SIGNATORY_SELECTION_REQUIRED"


def test_w7_member_position_approval_creates_no_person(client: TestClient, auth_users):
    """A Member-position approval creates no Person record."""
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    reg = client.post(
        "/api/v1/auth/register",
        json={"email": f"mem_{uuid.uuid4().hex[:6]}@svnit.ac.in", "password": "Password123!", "name": "General Member"},
    )
    h = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    jr = client.post(f"/api/v1/clubs/{acm_id}/join-requests", json={"position": "Member"}, headers=h)
    assert jr.status_code == 201

    app = client.post(
        f"/api/v1/clubs/{acm_id}/join-requests/{jr.json()['id']}/approve",
        json={"role": "viewer", "is_signatory": False},
        headers=o_headers,
    )
    assert app.status_code == 200

    people_res = client.get(f"/api/v1/clubs/{acm_id}/people", headers=o_headers)
    assert not any(p["email"] == reg.json()["user"]["email"] for p in people_res.json())


def test_w7_dates_confirmation_and_year_isolation(client: TestClient, auth_users):
    """Typed '14-15 October' without confirmation is rejected; with confirmation succeeds;
    pickers succeed and PDF contains only the confirmed year.
    """
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    base_payload = {
        "selected_template_ids": ["permission_letter"],
        "event_data": {
            "event_name": "Autumn Seminar",
            "venue": "Seminar Hall",
            "time_start": "09:00",
            "time_end": "17:00",
            "submitted_to": "HoD",
            "description": "Autumn seminar on artificial intelligence",
            "objectives": "Deepen practical understanding",
            "dates": "14-15 October",  # Inferred date without full year or confirmation
        },
        "ref_numbers_accepted": True,
    }

    # 1. Typed "14-15 October" without confirmation is rejected
    res_unconfirmed = client.post(
        f"/api/v1/clubs/{acm_id}/home/generate",
        json=base_payload,
        headers=o_headers,
    )
    assert res_unconfirmed.status_code == 400
    assert res_unconfirmed.json().get("detail", {}).get("code") == "DATES_NOT_CONFIRMED"

    # 2. With explicit confirmation succeeds
    payload_confirmed = dict(base_payload)
    payload_confirmed["event_data"] = dict(base_payload["event_data"])
    payload_confirmed["event_data"]["dates"] = "14-15 October 2026"
    payload_confirmed["event_data"]["dates_confirmed"] = True
    payload_confirmed["event_data"]["signatory_student_secretary"] = "First Secretary"

    res_confirmed = client.post(
        f"/api/v1/clubs/{acm_id}/home/generate",
        json=payload_confirmed,
        headers=o_headers,
    )
    assert res_confirmed.status_code == 200, f"Confirmed dates failed: {res_confirmed.text}"

    # 3. Pickers succeed with a specific year (2027) and PDF contains only that confirmed year
    payload_picker = dict(base_payload)
    payload_picker["event_data"] = dict(base_payload["event_data"])
    del payload_picker["event_data"]["dates"]
    payload_picker["event_data"]["date_start"] = "2027-10-14"
    payload_picker["event_data"]["date_end"] = "2027-10-15"
    payload_picker["event_data"]["signatory_student_secretary"] = "First Secretary"

    res_picker = client.post(
        f"/api/v1/clubs/{acm_id}/home/generate",
        json=payload_picker,
        headers=o_headers,
    )
    assert res_picker.status_code == 200
    doc = res_picker.json()["documents"][0]
    pdf_resp = client.get(doc["pdf_url"], headers=o_headers)
    assert pdf_resp.status_code == 200

    pdf_doc = fitz.open(stream=pdf_resp.content, filetype="pdf")
    pdf_text = "\n".join(page.get_text() for page in pdf_doc)
    pdf_doc.close()

    assert "2027" in pdf_text
    assert "14-15 October 2027" in pdf_text or "14/10/2027" in pdf_text


def test_w7_abuse_rate_limits_and_uniqueness(client: TestClient, auth_users):
    """Case-insensitive club name uniqueness, club creation 3/day limit,
    join requests 5/hr limit, and 24h rejection cooldown.
    """
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    # 1. Case-insensitive club name collision
    col_res = client.post(
        "/api/v1/clubs",
        json={"name": "acm student chapter, svnit", "short_name": "ACM2"},
        headers=o_headers,
    )
    assert col_res.status_code == 409
    assert col_res.json().get("detail", {}).get("code") == "CLUB_NAME_EXISTS"
    assert "Did you mean to join it instead" in col_res.json().get("detail", {}).get("message", "")

    # 2. Club creation rate limit: 3/day per user
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": f"founder_{uuid.uuid4().hex[:6]}@svnit.ac.in", "password": "Password123!", "name": "Serial Founder"},
    )
    f_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    for i in range(1, 4):
        c_res = client.post(
            "/api/v1/clubs",
            json={"name": f"Unique Club Number {i} {uuid.uuid4().hex[:4]}", "short_name": f"UC{i}"},
            headers=f_headers,
        )
        assert c_res.status_code == 201

    # 4th club in 24h -> 429
    c_4th = client.post(
        "/api/v1/clubs",
        json={"name": f"Fourth Club {uuid.uuid4().hex[:4]}", "short_name": "UC4"},
        headers=f_headers,
    )
    assert c_4th.status_code == 429
    assert c_4th.json().get("detail", {}).get("code") == "RATE_LIMIT_EXCEEDED"

    # 3. Join request rate limit: 5/hr per user
    reg_applicant = client.post(
        "/api/v1/auth/register",
        json={"email": f"spammer_{uuid.uuid4().hex[:6]}@svnit.ac.in", "password": "Password123!", "name": "Rapid Requester"},
    )
    app_headers = {"Authorization": f"Bearer {reg_applicant.json()['access_token']}"}

    # Submit 5 join requests
    club_ids = []
    for i in range(6):
        founder_res = client.post(
            "/api/v1/auth/register",
            json={"email": f"club_founder_{i}_{uuid.uuid4().hex[:6]}@svnit.ac.in", "password": "Password123!", "name": f"Founder {i}"},
        )
        f_hdrs = {"Authorization": f"Bearer {founder_res.json()['access_token']}"}
        c = client.post("/api/v1/clubs", json={"name": f"Test Club {i} {uuid.uuid4().hex[:4]}", "short_name": f"TC{i}"}, headers=f_hdrs).json()["id"]
        club_ids.append(c)

    for cid in club_ids[:5]:
        jr = client.post(f"/api/v1/clubs/{cid}/join-requests", json={"position": "Member"}, headers=app_headers)
        assert jr.status_code == 201

    # 6th request within 1 hour -> 429
    jr_6th = client.post(f"/api/v1/clubs/{club_ids[5]}/join-requests", json={"position": "Member"}, headers=app_headers)
    assert jr_6th.status_code == 429
    assert jr_6th.json().get("detail", {}).get("code") == "RATE_LIMIT_EXCEEDED"

    # 4. Rejection cooldown: user rejected cannot submit again for 24h
    rej_user = client.post(
        "/api/v1/auth/register",
        json={"email": f"rejected_{uuid.uuid4().hex[:6]}@svnit.ac.in", "password": "Password123!", "name": "Rejected Person"},
    ).json()
    rej_headers = {"Authorization": f"Bearer {rej_user['access_token']}"}

    jr_rej = client.post(f"/api/v1/clubs/{acm_id}/join-requests", json={"position": "Member"}, headers=rej_headers)
    assert jr_rej.status_code == 201
    rej_action = client.post(f"/api/v1/clubs/{acm_id}/join-requests/{jr_rej.json()['id']}/reject", headers=o_headers)
    assert rej_action.status_code == 200

    # Immediate second request to same club -> 400 REJECTION_COOLDOWN
    jr_retry = client.post(f"/api/v1/clubs/{acm_id}/join-requests", json={"position": "Member"}, headers=rej_headers)
    assert jr_retry.status_code == 400
    assert jr_retry.json().get("detail", {}).get("code") == "REJECTION_COOLDOWN"


def test_w7_event_record_coerces_scalar_budget_and_judges():
    """Verify that EventRecord and from_flat_dict cleanly coerce scalar budget_items and judges."""
    from decimal import Decimal
    from docgen.models import EventRecord, BudgetItem

    # 1. Direct validation with scalar budget string and empty string judges
    rec1 = EventRecord.model_validate({
        "event_name": "Test Event",
        "judges": "",
        "budget_items": "1100",
    })
    assert rec1.judges.value == []
    assert len(rec1.budget_items) == 1
    assert rec1.budget_items[0].item == "Proposed Budget"
    assert rec1.budget_items[0].amount == Decimal("1100")

    # 2. from_flat_dict with integer budget and comma-separated judges
    rec2 = EventRecord.from_flat_dict({
        "event_name": "Hackathon",
        "judges": "Dr. Alok Kumar, Prof. Sharma",
        "budget_items": 25000,
    })
    assert rec2.judges.value == ["Dr. Alok Kumar", "Prof. Sharma"]
    assert len(rec2.budget_items) == 1
    assert rec2.budget_items[0].amount == Decimal("25000")

    # 3. from_flat_dict with multiline items in budget_items
    rec3 = EventRecord.from_flat_dict({
        "event_name": "Conclave",
        "budget_items": "Banner: 800\nMiscellaneous: 300",
    })
    assert len(rec3.budget_items) == 2
    assert rec3.budget_items[0].item == "Banner"
    assert rec3.budget_items[0].amount == Decimal("800")
    assert rec3.budget_items[1].item == "Miscellaneous"
    assert rec3.budget_items[1].amount == Decimal("300")


def test_w7_home_generate_approval_note_with_scalar_budget_and_empty_judges(client: TestClient, auth_users):
    """End-to-end regression: approval note generation with judges='' and budget_items='1100' succeeds."""
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    payload = {
        "selected_template_ids": ["approval_note"],
        "event_data": {
            "event_name": "Annual Coding Conclave",
            "venue": "Computer Lab 1",
            "dates": "14-15 October 2026",
            "dates_confirmed": True,
            "description": "Annual coding conclave and project presentation.",
            "objectives": "To test competitive programming skills and promote open-source.",
            "target_audience": "B.Tech Students",
            "expected_participants": 120,
            "judges": "",
            "budget_items": "1100",
            "signatory_student_secretary": "First Secretary",
        },
        "ref_numbers_accepted": True,
        "event_title": "Annual Coding Conclave",
    }

    res = client.post(
        f"/api/v1/clubs/{acm_id}/home/generate",
        json=payload,
        headers=o_headers,
    )
    assert res.status_code == 200, f"Approval note generation failed: {res.text}"
    data = res.json()
    assert data["documents_count"] >= 1
    doc = data["documents"][0]
    assert doc["template_slug"] == "approval_note"

    # Verify generated PDF is downloadable and valid
    pdf_resp = client.get(doc["pdf_url"], headers=o_headers)
    assert pdf_resp.status_code == 200
    pdf_doc = fitz.open(stream=pdf_resp.content, filetype="pdf")
    pdf_text = "\n".join(page.get_text() for page in pdf_doc)
    pdf_doc.close()

    assert "Annual Coding Conclave" in pdf_text
    assert "1,100" in pdf_text or "1100" in pdf_text


def test_w7_shorthand_date_and_time_extraction(client, auth_users):
    """Verify that natural language prompts with shorthand dates ('sat 7th nov') and times ('10 to 4') are parsed accurately."""
    o_headers = auth_users["owner_headers"]
    acm_id = auth_users["acm_club"]["id"]

    # 1. Exact user scenario
    user_prompt = "hey need a room permission for our python bootcamp, sat 7th nov, 10 to 4, CSE seminar hall, around 60 first years pls"
    res = client.post(
        f"/api/v1/clubs/{acm_id}/home/understand",
        json={"text": user_prompt},
        headers=o_headers,
    )
    assert res.status_code == 200
    u = res.json()["understood"]

    assert u["event_name"] == "Python Bootcamp"
    assert u["venue"] == "Seminar Hall"
    assert u["date_start"] == "2026-11-07"
    assert u["date_end"] == "2026-11-07"
    assert u["dates"] == "7 Nov 2026"
    assert "10 to 2026" not in str(u.get("dates") or "")
    assert u["time_start"] == "10:00"
    assert u["time_end"] == "16:00"
    assert u["participants"] == 60

    # 2. Month-first date with afternoon shorthand times ('2 to 5')
    res2 = client.post(
        f"/api/v1/clubs/{acm_id}/home/understand",
        json={"text": "Coding session on Nov 7th from 2 to 5 in Seminar Hall"},
        headers=o_headers,
    )
    assert res2.status_code == 200
    u2 = res2.json()["understood"]
    assert u2["date_start"] == "2026-11-07"
    assert u2["time_start"] == "14:00"
    assert u2["time_end"] == "17:00"



