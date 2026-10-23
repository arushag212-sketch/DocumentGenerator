"""New accounts join the demo club (DEMO_CLUB_SLUG) as editors, by email sign-up and by Google."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.core.config import settings
from server.app.core.database import SessionLocal
from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.app.models import Club, Membership, User


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def demo_club(monkeypatch):
    slug = f"demo-{uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        club = Club(name="Demo Club SVNIT", short_name="DEMO", slug=slug, settings={})
        db.add(club)
        db.commit()
        club_id = club.id
    monkeypatch.setattr(settings, "DEMO_CLUB_SLUG", slug)
    clear_rate_limits()
    yield slug, club_id
    with SessionLocal() as db:
        db.query(Membership).filter(Membership.club_id == club_id).delete()
        db.query(Club).filter(Club.id == club_id).delete()
        db.commit()


def _membership(email: str, club_id: str):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        return db.query(Membership).filter(Membership.user_id == user.id, Membership.club_id == club_id).first()


def test_email_signup_joins_demo_club_as_editor(client, demo_club):
    slug, club_id = demo_club
    email = f"new_{uuid.uuid4().hex[:8]}@svnit.ac.in"
    res = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "name": "New Student"})
    assert res.status_code == 201, res.text
    body = res.json()["user"]
    assert body["demo_club_slug"] == slug
    assert any(m["club_slug"] == slug and m["role"] == "editor" for m in body["memberships"])
    m = _membership(email, club_id)
    assert m is not None and m.role == "editor" and m.status == "active" and m.position == "Member"


def test_google_signup_joins_demo_club_once(client, demo_club, monkeypatch):
    _, club_id = demo_club
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client-id")
    email = f"g_{uuid.uuid4().hex[:8]}@aied.svnit.ac.in"
    sub = f"sub_{uuid.uuid4().hex[:12]}"
    import google.oauth2.id_token

    monkeypatch.setattr(
        google.oauth2.id_token,
        "verify_oauth2_token",
        lambda credential, req, audience, clock_skew_in_seconds: {
            "iss": "https://accounts.google.com", "email_verified": True, "email": email, "sub": sub, "name": "G Student",
        },
    )
    for _ in range(2):  # signing in again must not add a second membership
        res = client.post("/api/v1/auth/google", json={"credential": "mock_token"})
        assert res.status_code == 200, res.text
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        rows = db.query(Membership).filter(Membership.user_id == user.id, Membership.club_id == club_id).all()
    assert len(rows) == 1 and rows[0].role == "editor"


def test_no_demo_club_configured_changes_nothing(client, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_CLUB_SLUG", "")
    clear_rate_limits()
    email = f"plain_{uuid.uuid4().hex[:8]}@svnit.ac.in"
    res = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "name": "Plain"})
    assert res.status_code == 201, res.text
    assert res.json()["user"]["memberships"] == []
    assert res.json()["user"]["demo_club_slug"] is None
