"""Tests for approving join requests with a designated or updated club position."""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.core.database import SessionLocal
from server.app.models import User, Club, Membership, JoinRequest, Person, RoleHeld, AuditLog
from server.app.core.security import get_password_hash, create_access_token


@pytest.fixture
def client():
    return TestClient(app)


def _create_user(name: str = "Test User") -> User:
    db = SessionLocal()
    try:
        user = User(
            id=str(uuid.uuid4()),
            email=f"user_{uuid.uuid4().hex[:8]}@svnit.ac.in",
            name=name,
            password_hash=get_password_hash("TestPass123!"),
            is_platform_admin=False,
            token_version=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _create_club_and_owner() -> tuple[Club, User, dict]:
    db = SessionLocal()
    try:
        owner = User(
            id=str(uuid.uuid4()),
            email=f"owner_{uuid.uuid4().hex[:8]}@svnit.ac.in",
            name="Club Owner",
            password_hash=get_password_hash("OwnerPass123!"),
            is_platform_admin=False,
            token_version=1,
        )
        db.add(owner)
        db.flush()

        club = Club(
            id=str(uuid.uuid4()),
            name=f"Club {uuid.uuid4().hex[:6]}",
            short_name="TC",
            slug=f"club-{uuid.uuid4().hex[:6]}",
            academic_year_default="2026-27",
        )
        db.add(club)
        db.flush()

        membership = Membership(
            id=str(uuid.uuid4()),
            user_id=owner.id,
            club_id=club.id,
            role="owner",
            position="Faculty Chairman",
            status="active",
        )
        db.add(membership)
        db.commit()
        db.refresh(club)
        db.refresh(owner)

        token = create_access_token(user_id=owner.id, email=owner.email, token_version=owner.token_version)
        headers = {"Authorization": f"Bearer {token}"}
        return club, owner, headers
    finally:
        db.close()


def _create_join_request(club: Club, user: User, position: str = "Member") -> JoinRequest:
    db = SessionLocal()
    try:
        jr = JoinRequest(
            id=str(uuid.uuid4()),
            club_id=club.id,
            user_id=user.id,
            position=position,
            requested_role="editor",
            status="pending",
        )
        db.add(jr)
        db.commit()
        db.refresh(jr)
        return jr
    finally:
        db.close()


def test_approve_without_position_keeps_requested_position(client: TestClient):
    """Approve without position -> member gets the requested position."""
    club, owner, owner_headers = _create_club_and_owner()
    applicant = _create_user(name="Applicant One")
    jr = _create_join_request(club, applicant, position="Executive Member")

    res = client.post(
        f"/api/v1/clubs/{club.id}/join-requests/{jr.id}/approve",
        json={"role": "editor"},
        headers=owner_headers,
    )
    assert res.status_code == 200, res.text

    db = SessionLocal()
    try:
        m = db.query(Membership).filter(Membership.club_id == club.id, Membership.user_id == applicant.id).first()
        assert m is not None
        assert m.position == "Executive Member"
        assert m.role == "editor"
        assert m.status == "active"
    finally:
        db.close()


def test_approve_with_different_fixed_position_syncs_role_and_writes_audit(client: TestClient):
    """Approve with a different fixed position -> member gets the new one, RoleHeld synced, audit entry written."""
    club, owner, owner_headers = _create_club_and_owner()
    applicant = _create_user(name="Applicant Two")
    jr = _create_join_request(club, applicant, position="Executive Member")

    res = client.post(
        f"/api/v1/clubs/{club.id}/join-requests/{jr.id}/approve",
        json={
            "position": "Student Secretary",
            "is_signatory": True,
            "role": "editor",
        },
        headers=owner_headers,
    )
    assert res.status_code == 200, res.text

    db = SessionLocal()
    try:
        # 1. Membership position updated
        m = db.query(Membership).filter(Membership.club_id == club.id, Membership.user_id == applicant.id).first()
        assert m is not None
        assert m.position == "Student Secretary"

        # 2. RoleHeld synced
        person = db.query(Person).filter(Person.club_id == club.id, Person.email == applicant.email).first()
        assert person is not None
        rh = db.query(RoleHeld).filter(RoleHeld.club_id == club.id, RoleHeld.person_id == person.id).first()
        assert rh is not None
        assert rh.role_key == "student_secretary"
        assert rh.academic_year == club.academic_year_default

        # 3. Audit log written with requested position -> approved position, by admin
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.entity_id == jr.id, AuditLog.action == "join_request_approved")
            .first()
        )
        assert audit is not None
        assert audit.user_id == owner.id
        assert audit.meta.get("requested_position") == "Executive Member"
        assert audit.meta.get("approved_position") == "Student Secretary"
    finally:
        db.close()


def test_approve_with_custom_position_not_signatory(client: TestClient):
    """Approve with 'Other: Event Lead' -> stored as custom, not a signatory."""
    club, owner, owner_headers = _create_club_and_owner()
    applicant = _create_user(name="Applicant Three")
    jr = _create_join_request(club, applicant, position="Member")

    res = client.post(
        f"/api/v1/clubs/{club.id}/join-requests/{jr.id}/approve",
        json={"position": "Other: Event Lead"},
        headers=owner_headers,
    )
    assert res.status_code == 200, res.text

    db = SessionLocal()
    try:
        m = db.query(Membership).filter(Membership.club_id == club.id, Membership.user_id == applicant.id).first()
        assert m is not None
        assert m.position == "Other: Event Lead"

        # Should not create RoleHeld
        person = db.query(Person).filter(Person.club_id == club.id, Person.email == applicant.email).first()
        assert person is None
    finally:
        db.close()


def test_approve_with_is_signatory_true_and_non_eligible_position(client: TestClient):
    """Approve with is_signatory true and a non-eligible position -> INVALID_SIGNATORY_POSITION."""
    club, owner, owner_headers = _create_club_and_owner()
    applicant = _create_user(name="Applicant Four")
    jr = _create_join_request(club, applicant, position="Member")

    res = client.post(
        f"/api/v1/clubs/{club.id}/join-requests/{jr.id}/approve",
        json={
            "position": "Other: Event Lead",
            "is_signatory": True,
        },
        headers=owner_headers,
    )
    assert res.status_code == 400, res.text
    detail = res.json().get("detail", {})
    code = detail.get("code") if isinstance(detail, dict) else detail
    assert code == "INVALID_SIGNATORY_POSITION"


def test_approve_with_invalid_position_text(client: TestClient):
    """Invalid position text -> 400."""
    club, owner, owner_headers = _create_club_and_owner()
    applicant = _create_user(name="Applicant Five")
    jr = _create_join_request(club, applicant, position="Member")

    res = client.post(
        f"/api/v1/clubs/{club.id}/join-requests/{jr.id}/approve",
        json={
            "position": "Invalid 123 !@#$",
        },
        headers=owner_headers,
    )
    assert res.status_code == 400, res.text
    detail = res.json().get("detail", {})
    code = detail.get("code") if isinstance(detail, dict) else detail
    assert code == "INVALID_POSITION"
