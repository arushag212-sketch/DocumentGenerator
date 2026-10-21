"""Profile: display name, change/set password, sign out other devices."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.core.database import SessionLocal
from server.app.core.rate_limit import clear_rate_limits
from server.app.core.security import create_access_token, get_password_hash
from server.app.main import app
from server.app.models import User


@pytest.fixture
def client():
    clear_rate_limits()
    return TestClient(app)


def _user(password: str | None = "OldPassword123!", google: bool = False) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=f"profile_{uuid.uuid4().hex[:8]}@svnit.ac.in",
            name="Profile Tester",
            password_hash=get_password_hash(password) if password else None,
            google_sub=f"sub_{uuid.uuid4().hex[:8]}" if google else None,
            token_version=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.email, user.token_version)}"}


def test_update_name(client):
    user = _user()
    res = client.patch("/api/v1/auth/me", json={"name": "  Asha   Patel "}, headers=_auth(user))
    assert res.status_code == 200
    assert res.json()["name"] == "Asha Patel"
    assert res.json()["has_password"] is True


def test_change_password_needs_current_and_revokes_other_sessions(client):
    user = _user()
    old_headers = _auth(user)

    wrong = client.post("/api/v1/auth/change-password", json={"current_password": "nope-nope-nope", "new_password": "BrandNewPass456!"}, headers=old_headers)
    assert wrong.status_code == 400
    assert wrong.json()["detail"]["code"] == "WRONG_PASSWORD"

    ok = client.post("/api/v1/auth/change-password", json={"current_password": "OldPassword123!", "new_password": "BrandNewPass456!"}, headers=old_headers)
    assert ok.status_code == 200
    new_token = ok.json()["access_token"]

    # The old token (another device) no longer works; the new one does
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200

    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": "BrandNewPass456!"})
    assert login.status_code == 200


def test_google_only_account_can_set_a_password(client):
    user = _user(password=None, google=True)
    res = client.post("/api/v1/auth/change-password", json={"new_password": "FirstPassword789!"}, headers=_auth(user))
    assert res.status_code == 200
    body = res.json()["user"]
    assert body["has_password"] is True and body["uses_google"] is True


def test_weak_password_rejected(client):
    user = _user()
    res = client.post("/api/v1/auth/change-password", json={"current_password": "OldPassword123!", "new_password": "password123"}, headers=_auth(user))
    assert res.status_code in (400, 422)


def test_sign_out_other_devices_keeps_this_session(client):
    user = _user()
    old_headers = _auth(user)
    res = client.post("/api/v1/auth/sign-out-others", headers=old_headers)
    assert res.status_code == 200
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {res.json()['access_token']}"}).status_code == 200


def test_refresh_cookie_issues_a_new_session(client):
    """Refresh keeps people signed in after the 30-minute access token expires."""
    user = _user()
    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": "OldPassword123!"})
    assert login.status_code == 200
    res = client.post("/api/v1/auth/refresh", json={})
    assert res.status_code == 200, res.text
    assert res.json()["user"]["email"] == user.email
