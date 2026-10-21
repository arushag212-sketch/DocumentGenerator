"""Tests for password login domain validation and institute email messaging."""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from server.app.core.config import settings
from server.app.core.database import SessionLocal
from server.app.core.email_domain import (
    EMAIL_DOMAIN_ERROR_CODE,
    EMAIL_DOMAIN_REJECTION_MESSAGE,
)
from server.app.core.rate_limit import clear_rate_limits
from server.app.core.security import get_password_hash
from server.app.main import app
from server.app.models import User


@pytest.fixture
def client():
    clear_rate_limits()
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_password_login_rejects_non_svnit_domain(client: TestClient, monkeypatch):
    """Password login with someone@gmail.com -> 403 with EMAIL_DOMAIN_ERROR_CODE and rejection message."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")

    # JSON login endpoint (/api/v1/auth/login)
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "someone@gmail.com", "password": "AnySecretPassword123!"},
    )
    assert res.status_code == 403
    err = res.json()["detail"]
    assert err["code"] == EMAIL_DOMAIN_ERROR_CODE
    assert err["message"] == EMAIL_DOMAIN_REJECTION_MESSAGE

    # OAuth2 form login endpoint (/api/v1/auth/token)
    res_form = client.post(
        "/api/v1/auth/token",
        data={"username": "someone@gmail.com", "password": "AnySecretPassword123!"},
    )
    assert res_form.status_code == 403
    err_form = res_form.json()["detail"]
    assert err_form["code"] == EMAIL_DOMAIN_ERROR_CODE
    assert err_form["message"] == EMAIL_DOMAIN_REJECTION_MESSAGE


def test_password_login_allowed_subdomain_wrong_password(client: TestClient, monkeypatch):
    """Password login with u00xx000@coed.svnit.ac.in and a wrong password -> still 401 INVALID_CREDENTIALS."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "u00xx000@coed.svnit.ac.in", "password": "WrongPassword123!"},
    )
    assert res.status_code == 401
    err = res.json()["detail"]
    assert err["code"] == "INVALID_CREDENTIALS"
    assert err["message"] == "Invalid email or password"


def test_rejected_attempt_does_not_increase_failed_login_attempts(client: TestClient, monkeypatch, db: Session):
    """The rejected attempt does not increase failed_login_attempts for any user, nor locks any account."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")

    # 1. Create a user with a non-institute email in the DB
    test_email = f"user_{uuid.uuid4().hex[:8]}@gmail.com"
    user = User(
        email=test_email,
        name="Gmail User",
        password_hash=get_password_hash("ValidPass12345!"),
        failed_login_attempts=0,
        locked_until=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.failed_login_attempts == 0
    assert user.locked_until is None

    # 2. Attempt login with non-institute email multiple times
    for _ in range(6):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "WrongPassword123!"},
        )
        assert res.status_code == 403
        assert res.json()["detail"]["code"] == EMAIL_DOMAIN_ERROR_CODE

    # 3. Verify user's failed_login_attempts did NOT increase and account is NOT locked
    db.refresh(user)
    assert user.failed_login_attempts == 0
    assert user.locked_until is None

    # 4. Also verify an institute domain user's failed attempts are untouched
    inst_user = User(
        email=f"student_{uuid.uuid4().hex[:8]}@svnit.ac.in",
        name="Institute Student",
        password_hash=get_password_hash("StudentPass12345!"),
        failed_login_attempts=0,
        locked_until=None,
    )
    db.add(inst_user)
    db.commit()
    db.refresh(inst_user)

    # Attempting to log in as someone else (gmail) doesn't touch the institute user
    res_other = client.post(
        "/api/v1/auth/login",
        json={"email": "attacker@yahoo.com", "password": "Password123!"},
    )
    assert res_other.status_code == 403

    db.refresh(inst_user)
    assert inst_user.failed_login_attempts == 0
    assert inst_user.locked_until is None


def test_password_login_allows_any_domain_when_allowed_domain_empty_in_test(client: TestClient, monkeypatch, db: Session):
    """When ALLOWED_EMAIL_DOMAIN is empty in dev/test, local demo accounts (e.g. admin@example.com) can log in."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")

    demo_email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=demo_email,
        name="Admin Example",
        password_hash=get_password_hash("AdminPass123!"),
    )
    db.add(user)
    db.commit()

    res = client.post(
        "/api/v1/auth/login",
        json={"email": demo_email, "password": "AdminPass123!"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()
