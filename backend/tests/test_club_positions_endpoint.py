"""Tests for GET /api/v1/clubs/positions and club creation with signatory positions."""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from server.app.core.database import SessionLocal
from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.app.models import Club, Membership, Person, RoleHeld, User


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _register_user(client: TestClient, prefix: str = "user") -> tuple[dict, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@svnit.ac.in"
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "name": f"Test {prefix.capitalize()}",
        },
    )
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]
    user_id = res.json()["user"]["id"]
    return {"Authorization": f"Bearer {token}"}, user_id


def test_positions_endpoint_requires_auth(client: TestClient):
    """GET /api/v1/clubs/positions must require a signed-in user."""
    res = client.get("/api/v1/clubs/positions")
    assert res.status_code == 401


def test_positions_endpoint_returns_positions(client: TestClient):
    """GET /api/v1/clubs/positions returns position catalogue without needing a club_id."""
    headers, _ = _register_user(client, "pos_viewer")
    res = client.get("/api/v1/clubs/positions", headers=headers)
    assert res.status_code == 200, res.text

    positions = res.json()
    assert isinstance(positions, list)
    assert len(positions) > 0

    # Ensure positions have expected schema
    for pos in positions:
        assert "key" in pos
        assert "label" in pos
        assert "group" in pos
        assert "signs" in pos
        assert "help" in pos
        assert isinstance(pos["signs"], bool)

    # Check key signatory positions
    signatories = [p for p in positions if p["signs"]]
    signatory_labels = {p["label"] for p in signatories}
    expected_signatories = {
        "Student Head/Chairperson",
        "Student Secretary",
        "Treasurer",
        "Faculty Chairman",
        "Faculty Co-Chairman",
    }
    assert expected_signatories.issubset(signatory_labels)

    # Check non-signatory positions
    non_signatory_labels = {p["label"] for p in positions if not p["signs"]}
    assert "Faculty In-charge (venue)" in non_signatory_labels
    assert "Technical Assistant" in non_signatory_labels
    assert "Other" in non_signatory_labels


def test_positions_endpoint_matches_club_id_positions(client: TestClient):
    """GET /api/v1/clubs/positions and GET /api/v1/clubs/{club_id}/positions return the same list."""
    clear_rate_limits()
    headers, _ = _register_user(client, "pos_comparer")

    # Create a club to get a club_id
    club_res = client.post(
        "/api/v1/clubs",
        headers=headers,
        json={
            "name": f"Positions Test Club {uuid.uuid4().hex[:6]}",
            "short_name": f"PTC{uuid.uuid4().hex[:3]}",
            "position": "Student Head/Chairperson",
            "is_signatory": True,
        },
    )
    assert club_res.status_code == 201, club_res.text
    club_id = club_res.json()["id"]

    public_positions = client.get("/api/v1/clubs/positions", headers=headers).json()
    club_positions = client.get(f"/api/v1/clubs/{club_id}/positions", headers=headers).json()

    assert public_positions == club_positions


@pytest.mark.parametrize(
    "position_label,expected_role_key",
    [
        ("Student Head/Chairperson", "student_head"),
        ("Student Secretary", "student_secretary"),
        ("Treasurer", "treasurer"),
        ("Faculty Chairman", "faculty_chairman"),
        ("Faculty Co-Chairman", "faculty_co_chairman"),
    ],
)
def test_create_club_with_each_signatory_position(client: TestClient, position_label: str, expected_role_key: str):
    """Creating a club with each signatory position and is_signatory=True must succeed,
    storing the position and creating the corresponding RoleHeld.
    """
    clear_rate_limits()
    headers, user_id = _register_user(client, f"sig_{expected_role_key}")

    club_name = f"Club {expected_role_key.replace('_', ' ').title()} {uuid.uuid4().hex[:6]}"
    short_name = f"C{uuid.uuid4().hex[:4]}".upper()

    res = client.post(
        "/api/v1/clubs",
        headers=headers,
        json={
            "name": club_name,
            "short_name": short_name,
            "position": position_label,
            "is_signatory": True,
        },
    )
    assert res.status_code == 201, res.text
    created_club = res.json()
    club_id = created_club["id"]

    # Verify membership position
    members_res = client.get(f"/api/v1/clubs/{club_id}/members", headers=headers)
    assert members_res.status_code == 200
    members = members_res.json()
    creator_member = next((m for m in members if m["user_id"] == user_id), None)
    assert creator_member is not None
    assert creator_member["position"] == position_label

    # Verify RoleHeld and Person records in database
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        club = db.query(Club).filter(Club.id == club_id).first()
        person = db.query(Person).filter(Person.club_id == club_id, Person.email == user.email).first()
        assert person is not None, f"Expected Person record created for {position_label}"

        role_held = (
            db.query(RoleHeld)
            .filter(
                RoleHeld.club_id == club_id,
                RoleHeld.person_id == person.id,
                RoleHeld.role_key == expected_role_key,
                RoleHeld.academic_year == club.academic_year_default,
                RoleHeld.valid_to.is_(None),
            )
            .first()
        )
        assert role_held is not None, f"Expected RoleHeld for {expected_role_key}"
    finally:
        db.close()


def test_create_club_with_non_signatory_position_fails_if_signatory_true(client: TestClient):
    """Creating a club with a non-signatory position when is_signatory=True must return 400."""
    clear_rate_limits()
    headers, _ = _register_user(client, "non_sig_fail")

    for bad_pos in ["Technical Assistant", "Other", "Faculty In-charge (venue)", "Volunteer"]:
        clear_rate_limits()
        res = client.post(
            "/api/v1/clubs",
            headers=headers,
            json={
                "name": f"Invalid Sig Club {uuid.uuid4().hex[:6]}",
                "short_name": f"ISC{uuid.uuid4().hex[:3]}",
                "position": bad_pos,
                "is_signatory": True,
            },
        )
        assert res.status_code == 400, f"Expected 400 for non-signatory '{bad_pos}', got {res.status_code}"
        assert res.json().get("detail", {}).get("code") == "INVALID_SIGNATORY_POSITION"


def test_create_club_with_non_signatory_position_succeeds_if_signatory_false(client: TestClient):
    """Creating a club with a non-signatory position when is_signatory=False succeeds and creates no RoleHeld."""
    clear_rate_limits()
    headers, user_id = _register_user(client, "non_sig_ok")

    res = client.post(
        "/api/v1/clubs",
        headers=headers,
        json={
            "name": f"Non Sig Ok Club {uuid.uuid4().hex[:6]}",
            "short_name": f"NSC{uuid.uuid4().hex[:3]}",
            "position": "Technical Assistant",
            "is_signatory": False,
        },
    )
    assert res.status_code == 201, res.text
    club_id = res.json()["id"]

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        roles = db.query(RoleHeld).filter(RoleHeld.club_id == club_id).all()
        assert len(roles) == 0
    finally:
        db.close()
