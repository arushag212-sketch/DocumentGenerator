"""Tests for platform admin permissions and position handling."""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.core.database import SessionLocal
from server.app.models import User, Club, Membership
from server.app.core.security import get_password_hash, create_access_token


@pytest.fixture
def client():
    return TestClient(app)


def _create_user(is_platform_admin: bool = False, email_prefix: str = "user") -> User:
    db = SessionLocal()
    try:
        user = User(
            id=str(uuid.uuid4()),
            email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@svnit.ac.in",
            name="Test User",
            password_hash=get_password_hash("TestPass123!"),
            is_platform_admin=is_platform_admin,
            token_version=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _create_club(name_prefix: str = "Club") -> Club:
    db = SessionLocal()
    try:
        club = Club(
            id=str(uuid.uuid4()),
            name=f"{name_prefix} {uuid.uuid4().hex[:6]}",
            short_name="TC",
            slug=f"club-{uuid.uuid4().hex[:6]}",
            academic_year_default="2026-27",
        )
        db.add(club)
        db.commit()
        db.refresh(club)
        return club
    finally:
        db.close()


def _create_membership(user_id: str, club_id: str, role: str = "owner", position: str | None = None) -> Membership:
    db = SessionLocal()
    try:
        m = Membership(
            id=str(uuid.uuid4()),
            user_id=user_id,
            club_id=club_id,
            role=role,
            position=position,
            status="active",
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        return m
    finally:
        db.close()


def test_platform_admin_owns_club_a_with_position(client: TestClient):
    """Platform admin who owns club A with a position -> permissions for A: is_member true and that position."""
    admin = _create_user(is_platform_admin=True, email_prefix="admin_a")
    club_a = _create_club("Club A")
    _create_membership(admin.id, club_a.id, role="owner", position="Chairperson")

    token = create_access_token(user_id=admin.id, email=admin.email, token_version=admin.token_version)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/api/v1/clubs/{club_a.id}/permissions", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["is_member"] is True
    assert data["is_platform_admin"] is True
    assert data["role"] == "owner"
    assert data["position"] == "Chairperson"


def test_platform_admin_not_a_member_of_club_b(client: TestClient):
    """Same admin on club B where they're not a member -> is_member false, position null, still admin access."""
    admin = _create_user(is_platform_admin=True, email_prefix="admin_b")
    club_b = _create_club("Club B")

    token = create_access_token(user_id=admin.id, email=admin.email, token_version=admin.token_version)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/api/v1/clubs/{club_b.id}/permissions", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["is_member"] is False
    assert data["is_platform_admin"] is True
    assert data["position"] is None
    # Still admin access
    assert data["role"] == "owner"
    assert data["can_edit_members"] is True
    assert data["can_edit_settings"] is True


def test_normal_member_with_no_position(client: TestClient):
    """Normal member with no position -> is_member true, position empty."""
    user = _create_user(is_platform_admin=False, email_prefix="normal_mem")
    club = _create_club("Club Normal")
    _create_membership(user.id, club.id, role="editor", position=None)

    token = create_access_token(user_id=user.id, email=user.email, token_version=user.token_version)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/api/v1/clubs/{club.id}/permissions", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["is_member"] is True
    assert data["is_platform_admin"] is False
    assert not data["position"]
