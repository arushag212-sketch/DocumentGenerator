"""Unit and integration tests for Google OAuth sign-in and SVNIT domain enforcement."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from server.app.core.config import settings
from server.app.core.database import SessionLocal
from server.app.core.email_domain import (
    EMAIL_DOMAIN_ERROR_CODE,
    EMAIL_DOMAIN_REJECTION_MESSAGE,
    is_allowed_email,
)
from server.app.core.rate_limit import clear_rate_limits
from server.app.core.security import get_password_hash
from server.app.main import app
from server.app.models import Club, Invite, Membership, User


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


@pytest.fixture
def test_club_and_invite(db: Session):
    """Fixture providing a test club and a valid invite code."""
    import hashlib
    club = db.query(Club).first()
    if not club:
        club = Club(
            id=str(uuid.uuid4()),
            name="Test Google Club",
            short_name="TGC",
            slug=f"tgc-{uuid.uuid4().hex[:6]}",
        )
        db.add(club)
        db.flush()

    raw_code = f"INV-{uuid.uuid4().hex[:8].upper()}"
    code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
    invite = Invite(
        id=str(uuid.uuid4()),
        club_id=club.id,
        code=raw_code,
        code_hash=code_hash,
        role="editor",
        max_uses=5,
        use_count=0,
        revoked=False,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return club, invite, raw_code


# ---------------- 1. UNIT TESTS: is_allowed_email ----------------


def test_is_allowed_email_policy(monkeypatch):
    """Test domain matching against settings.ALLOWED_EMAIL_DOMAIN."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")

    # Allowed domains and subdomains
    assert is_allowed_email("name@svnit.ac.in") is True
    assert is_allowed_email("u21cs001@coed.svnit.ac.in") is True
    assert is_allowed_email("x@amhd.svnit.ac.in") is True
    assert is_allowed_email("FACULTY@MED.SVNIT.AC.IN") is True

    # Rejected domains
    assert is_allowed_email("x@gmail.com") is False
    assert is_allowed_email("x@svnit.ac.in.evil.com") is False
    assert is_allowed_email("x@fakesvnit.ac.in") is False
    assert is_allowed_email("x@evilsvnit.ac.in") is False
    assert is_allowed_email("x@yahoo.com") is False
    assert is_allowed_email("svnit.ac.in") is False
    assert is_allowed_email("") is False
    assert is_allowed_email(None) is False


def test_is_allowed_email_empty_in_development(monkeypatch):
    """When ALLOWED_EMAIL_DOMAIN is empty and ENVIRONMENT is dev/test, allow all."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    assert is_allowed_email("anyone@gmail.com") is True
    assert is_allowed_email("student@svnit.ac.in") is True

    # In production, empty allowed domain rejects
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert is_allowed_email("anyone@gmail.com") is False


# ---------------- 2. BACKEND /api/v1/auth/google TESTS ----------------


def test_google_auth_success_creates_user(client: TestClient, monkeypatch, db: Session):
    """Allowed @svnit.ac.in email signs in, creates User, and sets cookies."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client-id")

    unique_email = f"student_{uuid.uuid4().hex[:6]}@svnit.ac.in"
    sub_id = f"sub_{uuid.uuid4().hex[:12]}"

    import google.oauth2.id_token
    monkeypatch.setattr(
        google.oauth2.id_token,
        "verify_oauth2_token",
        lambda credential, req, audience, clock_skew_in_seconds: {
            "iss": "https://accounts.google.com",
            "email_verified": True,
            "email": unique_email,
            "sub": sub_id,
            "name": "SVNIT Student",
        },
    )

    res = client.post("/api/v1/auth/google", json={"credential": "mock_token"})
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["user"]["email"] == unique_email
    assert data["user"]["name"] == "SVNIT Student"
    assert "access_token" in data
    assert "refresh_token" in data
    assert "csrf_token" in data

    # Verify cookies
    assert "access_token" in res.cookies
    assert "refresh_token" in res.cookies
    assert "csrf_token" in res.cookies

    # Verify database state
    user = db.query(User).filter(User.email == unique_email).first()
    assert user is not None
    assert user.google_sub == sub_id
    assert user.password_hash is None
    assert user.email_verified_at is not None


def test_google_auth_subdomain_success(client: TestClient, monkeypatch, db: Session):
    """Allowed sub-domain (e.g. u21cs001@coed.svnit.ac.in) signs in successfully."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client-id")

    unique_email = f"u{uuid.uuid4().hex[:4]}@coed.svnit.ac.in"
    sub_id = f"sub_{uuid.uuid4().hex[:12]}"

    import google.oauth2.id_token
    monkeypatch.setattr(
        google.oauth2.id_token,
        "verify_oauth2_token",
        lambda credential, req, audience, clock_skew_in_seconds: {
            "iss": "accounts.google.com",
            "email_verified": True,
            "email": unique_email,
            "sub": sub_id,
            "name": "Coed Student",
        },
    )

    res = client.post("/api/v1/auth/google", json={"credential": "mock_token"})
    assert res.status_code == 200
    assert res.json()["user"]["email"] == unique_email


@pytest.mark.parametrize(
    "forbidden_email",
    [
        "hacker@gmail.com",
        "attacker@svnit.ac.in.evil.com",
        "phisher@fakesvnit.ac.in",
        "user@evilsvnit.ac.in",
    ],
)
def test_google_auth_rejects_non_svnit_domains(client: TestClient, monkeypatch, forbidden_email: str):
    """gmail.com and look-alike domains are rejected with 403 EMAIL_DOMAIN_NOT_ALLOWED."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client-id")

    import google.oauth2.id_token
    monkeypatch.setattr(
        google.oauth2.id_token,
        "verify_oauth2_token",
        lambda credential, req, audience, clock_skew_in_seconds: {
            "iss": "https://accounts.google.com",
            "email_verified": True,
            "email": forbidden_email,
            "sub": f"sub_{uuid.uuid4().hex[:8]}",
            "name": "Foreign User",
        },
    )

    res = client.post("/api/v1/auth/google", json={"credential": "mock_token"})
    assert res.status_code == 403
    err = res.json()["detail"]
    assert err["code"] == EMAIL_DOMAIN_ERROR_CODE
    assert err["message"] == EMAIL_DOMAIN_REJECTION_MESSAGE


def test_google_auth_email_not_verified_rejected(client: TestClient, monkeypatch):
    """Google tokens with email_verified=False are rejected with 401."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client-id")

    import google.oauth2.id_token
    monkeypatch.setattr(
        google.oauth2.id_token,
        "verify_oauth2_token",
        lambda credential, req, audience, clock_skew_in_seconds: {
            "iss": "https://accounts.google.com",
            "email_verified": False,
            "email": "unverified@svnit.ac.in",
            "sub": "sub_unverified",
        },
    )

    res = client.post("/api/v1/auth/google", json={"credential": "mock_token"})
    assert res.status_code == 401
    assert "Google sign-in failed" in res.json()["detail"]["message"]


def test_google_auth_token_verification_failure(client: TestClient, monkeypatch):
    """Token verification raising ValueError (bad token, wrong audience) returns 401."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client-id")

    import google.oauth2.id_token

    def mock_verify_raise(*args, **kwargs):
        raise ValueError("Invalid token signature or expired audience")

    monkeypatch.setattr(google.oauth2.id_token, "verify_oauth2_token", mock_verify_raise)

    res = client.post("/api/v1/auth/google", json={"credential": "tampered_token"})
    assert res.status_code == 401
    assert res.json()["detail"]["message"] == "Google sign-in failed, please try again"


def test_google_auth_idempotent_and_existing_user_linking(client: TestClient, monkeypatch, db: Session):
    """Same Google user signing in twice creates one user; existing email/pass user links google_sub."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client-id")

    email1 = f"repeat_{uuid.uuid4().hex[:6]}@svnit.ac.in"
    sub1 = f"sub_{uuid.uuid4().hex[:10]}"

    import google.oauth2.id_token
    monkeypatch.setattr(
        google.oauth2.id_token,
        "verify_oauth2_token",
        lambda credential, req, audience, clock_skew_in_seconds: {
            "iss": "https://accounts.google.com",
            "email_verified": True,
            "email": email1,
            "sub": sub1,
            "name": "Repeat User",
        },
    )

    # First sign-in
    res1 = client.post("/api/v1/auth/google", json={"credential": "mock1"})
    assert res1.status_code == 200
    user_id = res1.json()["user"]["id"]

    # Second sign-in with same sub
    res2 = client.post("/api/v1/auth/google", json={"credential": "mock2"})
    assert res2.status_code == 200
    assert res2.json()["user"]["id"] == user_id

    # Existing user with email/password gets linked
    link_email = f"link_{uuid.uuid4().hex[:6]}@svnit.ac.in"
    link_sub = f"sub_link_{uuid.uuid4().hex[:6]}"
    existing_user = User(
        email=link_email,
        name="Existing Account",
        password_hash=get_password_hash("ExistingPassword123!"),
        google_sub=None,
    )
    db.add(existing_user)
    db.commit()

    monkeypatch.setattr(
        google.oauth2.id_token,
        "verify_oauth2_token",
        lambda credential, req, audience, clock_skew_in_seconds: {
            "iss": "https://accounts.google.com",
            "email_verified": True,
            "email": link_email,
            "sub": link_sub,
            "name": "Existing Account",
        },
    )

    res_link = client.post("/api/v1/auth/google", json={"credential": "mock3"})
    assert res_link.status_code == 200
    db.refresh(existing_user)
    assert existing_user.google_sub == link_sub


def test_google_auth_with_invite_code(client: TestClient, monkeypatch, db: Session, test_club_and_invite):
    """First Google sign-in with invite_code creates membership with assigned role."""
    club, invite, raw_code = test_club_and_invite
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client-id")

    unique_email = f"invited_{uuid.uuid4().hex[:6]}@svnit.ac.in"
    sub_id = f"sub_{uuid.uuid4().hex[:10]}"

    import google.oauth2.id_token
    monkeypatch.setattr(
        google.oauth2.id_token,
        "verify_oauth2_token",
        lambda credential, req, audience, clock_skew_in_seconds: {
            "iss": "https://accounts.google.com",
            "email_verified": True,
            "email": unique_email,
            "sub": sub_id,
            "name": "Invited Member",
        },
    )

    res = client.post("/api/v1/auth/google", json={"credential": "mock_token", "invite_code": raw_code})
    assert res.status_code == 200
    user_data = res.json()["user"]

    # Verify membership created
    user = db.query(User).filter(User.email == unique_email).first()
    assert user is not None
    m = db.query(Membership).filter(Membership.user_id == user.id, Membership.club_id == club.id).first()
    assert m is not None
    assert m.role == invite.role
    assert m.status == "active"


def test_register_rejects_non_svnit_email(client: TestClient, monkeypatch):
    """POST /register rejects emails outside ALLOWED_EMAIL_DOMAIN with 403."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")

    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "outsider@gmail.com",
            "password": "ValidPassword123!",
            "name": "Outsider",
        },
    )
    assert res.status_code == 403
    err = res.json()["detail"]
    assert err["code"] == EMAIL_DOMAIN_ERROR_CODE
    assert err["message"] == EMAIL_DOMAIN_REJECTION_MESSAGE


def test_login_for_google_only_user_returns_clear_400(client: TestClient, monkeypatch, db: Session):
    """POST /login and /token for Google-only users return 400 without crashing."""
    google_email = f"googleonly_{uuid.uuid4().hex[:6]}@svnit.ac.in"
    user = User(
        email=google_email,
        name="Google Only User",
        password_hash=None,
        google_sub=f"sub_{uuid.uuid4().hex[:8]}",
    )
    db.add(user)
    db.commit()

    # /login
    res = client.post(
        "/api/v1/auth/login",
        json={"email": google_email, "password": "AnyRandomPassword123!"},
    )
    assert res.status_code == 400
    assert "This account uses Google sign-in. Please use 'Sign in with Google'." in res.json()["detail"]["message"]

    # /token (form-encoded)
    res_token = client.post(
        "/api/v1/auth/token",
        data={"username": google_email, "password": "AnyRandomPassword123!"},
    )
    assert res_token.status_code == 400
    assert "This account uses Google sign-in. Please use 'Sign in with Google'." in res_token.json()["detail"]["message"]


def test_google_client_id_unset_returns_503(client: TestClient, monkeypatch):
    """When GOOGLE_CLIENT_ID is not configured, POST /google returns 503."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")

    res = client.post("/api/v1/auth/google", json={"credential": "mock_token"})
    assert res.status_code == 503
    assert res.json()["detail"]["message"] == "Google sign-in is not configured"


def test_forgot_password_does_not_send_to_google_only_or_non_svnit(client: TestClient, monkeypatch, db: Session):
    """POST /forgot-password returns generic 200 but sends no email to Google-only or non-allowed users."""
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAIN", "svnit.ac.in")

    # 1. Google-only user
    google_email = f"googleonly_{uuid.uuid4().hex[:6]}@svnit.ac.in"
    user = User(
        email=google_email,
        name="Google Only",
        password_hash=None,
    )
    db.add(user)
    db.commit()

    res1 = client.post("/api/v1/auth/forgot-password", json={"email": google_email})
    assert res1.status_code == 200
    assert "password reset instructions have been sent" in res1.json()["message"]
    db.refresh(user)
    assert user.password_reset_token_hash is None  # No token generated

    # 2. Non-SVNIT email
    res2 = client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@gmail.com"})
    assert res2.status_code == 200
    assert "password reset instructions have been sent" in res2.json()["message"]
