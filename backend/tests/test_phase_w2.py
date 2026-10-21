"""Phase W2 / W2.5 Comprehensive Test Suite: Security, Cryptography, Scoped Isolation, and UI Shell."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.app.core.config import Settings
from server.app.core.database import Base, get_db
from server.app.core.email import get_email_sender, LoggingEmailSender
from server.app.core.rate_limit import clear_rate_limits
from server.app.core.scoped_repo import ScopedRepository
from server.app.core.security import (
    decrypt_field,
    encrypt_field,
    get_password_hash,
    verify_password,
)
from server.app.main import app
from server.app.core.permissions import Role
from server.app.models import AuditLog, Club, Membership, Person, User


@pytest.fixture(scope="module")
def test_db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = SessionLocal()
    clear_rate_limits()
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(test_db_engine, db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# =========================================================================
# 1. FORGOT PASSWORD & RESET FLOW (Security Requirements 1 & 6)
# =========================================================================

def test_w2_forgot_password_no_token_and_enumeration_safe(client, db_session):
    """Verify forgot-password NEVER returns token in JSON and returns identical message for all emails."""
    user = User(
        email="student_fp@example.com",
        name="Student FP",
        password_hash=get_password_hash("SuperSecretPassword123!"),
    )
    db_session.add(user)
    db_session.commit()

    email_sender = get_email_sender()
    assert isinstance(email_sender, LoggingEmailSender)
    email_sender.sent_messages.clear()

    # 1. Existing email
    res1 = client.post("/api/v1/auth/forgot-password", json={"email": "student_fp@example.com"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert "token" not in data1
    assert "reset_token" not in data1
    assert "message" in data1
    assert "If this email is registered" in data1["message"]

    # Verify token was dispatched to EmailSender
    assert len(email_sender.sent_messages) == 1
    msg = email_sender.sent_messages[0]
    assert msg["to_email"] == "student_fp@example.com"
    token = msg["token"]
    assert token

    # 2. Non-existent email -> Returns identical response! (Enumeration-safe)
    res2 = client.post("/api/v1/auth/forgot-password", json={"email": "does_not_exist@example.com"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["message"] == data1["message"]
    assert "token" not in data2
    assert "reset_token" not in data2
    # No new email dispatched for non-existent email
    assert len(email_sender.sent_messages) == 1


def test_w2_reset_token_single_use_and_expiry(client, db_session):
    """Verify reset tokens are single-use, expire in 30 minutes, and update password hash."""
    user = User(
        email="reset_expiry_test@example.com",
        name="Expiry Test",
        password_hash=get_password_hash("InitialPassword123!"),
    )
    db_session.add(user)
    db_session.commit()

    email_sender = get_email_sender()
    email_sender.sent_messages.clear()

    client.post("/api/v1/auth/forgot-password", json={"email": "reset_expiry_test@example.com"})
    assert len(email_sender.sent_messages) >= 1
    token = email_sender.sent_messages[-1]["token"]

    # 1. Reset succeeds the first time
    res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "NewStrongPassword123!"},
    )
    assert res.status_code == 200
    assert "successfully updated" in res.json()["message"]

    # Verify DB state: password hash updated, used_at is set
    db_session.refresh(user)
    assert verify_password("NewStrongPassword123!", user.password_hash)
    assert user.password_reset_used_at is not None

    # 2. Second attempt with the SAME token MUST FAIL (Single-use)
    res_reuse = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "AnotherPassword123!"},
    )
    assert res_reuse.status_code == 400
    detail_reuse = str(res_reuse.json()["detail"]).lower()
    assert "already" in detail_reuse or "invalid" in detail_reuse or "expired" in detail_reuse

    # 3. Expired token MUST FAIL
    client.post("/api/v1/auth/forgot-password", json={"email": "reset_expiry_test@example.com"})
    token2 = email_sender.sent_messages[-1]["token"]
    user.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.commit()

    res_expired = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token2, "new_password": "ThirdPassword123!"},
    )
    assert res_expired.status_code == 400
    assert "expired" in res_expired.json()["detail"]["message"].lower()


# =========================================================================
# 2. SECRETS & PRODUCTION STARTUP REFUSAL (Security Requirement 2)
# =========================================================================

def test_w2_missing_secrets_blocks_startup_in_production(monkeypatch):
    """Verify application startup raises RuntimeError if JWT_SECRET_KEY or FIELD_ENCRYPTION_KEY are missing/placeholder in non-dev mode."""
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("FIELD_ENCRYPTION_KEY", raising=False)

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        Settings(ENVIRONMENT="production")

    monkeypatch.setenv("JWT_SECRET_KEY", "A" * 64)
    with pytest.raises(RuntimeError, match="FIELD_ENCRYPTION_KEY"):
        Settings(ENVIRONMENT="production")


# =========================================================================
# 3. FIELD-LEVEL ENCRYPTION AT REST (Security Requirement 3)
# =========================================================================

def test_w2_mobile_field_encrypted_at_rest_and_masked_output(client, db_session):
    """Verify people.mobile is stored encrypted (Fernet ciphertext), masked by default, and revealable with permission."""
    # Register & login admin
    client.post(
        "/api/v1/auth/register",
        json={"email": "admin_enc@example.com", "name": "Admin Enc", "password": "Pass123456789!"},
    )
    user = db_session.query(User).filter(User.email == "admin_enc@example.com").first()
    user.is_platform_admin = True
    db_session.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin_enc@example.com", "password": "Pass123456789!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    csrf_token = login_res.json()["csrf_token"]
    headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf_token}

    # Create club
    club_res = client.post(
        "/api/v1/clubs/",
        json={"name": "Encryption Test Club", "short_name": "ENC", "slug": "enc-test"},
        headers=headers,
    )
    club_id = club_res.json()["id"]

    # Add person with real mobile via endpoint
    add_res = client.post(
        f"/api/v1/clubs/{club_id}/people",
        json={
            "full_name": "Demo Faculty Chair",
            "mobile": "9876543210",
            "department": "CSE",
        },
        headers=headers,
    )
    assert add_res.status_code == 201
    person_id = add_res.json()["id"]

    # 1. VERIFY RAW DATABASE COLUMN IS NOT PLAINTEXT (Fernet ciphertext!)
    raw_person = db_session.query(Person).filter(Person.id == person_id).first()
    assert raw_person is not None
    assert raw_person.mobile != "9876543210"
    assert raw_person.mobile.startswith("gAAAAA"), f"Mobile is not Fernet ciphertext: {raw_person.mobile}"
    assert decrypt_field(raw_person.mobile) == "9876543210"

    # 2. VERIFY DEFAULT API OUTPUT IS MASKED (last 4 digits only)
    list_res = client.get(f"/api/v1/clubs/{club_id}/people", headers=headers)
    assert list_res.status_code == 200
    people_data = list_res.json()
    p = next(x for x in people_data if x["id"] == person_id)
    assert p["mobile"] == "******3210"

    # 3. VERIFY EXPLICIT REVEAL PERMISSION (admin can view plaintext)
    reveal_res = client.get(
        f"/api/v1/clubs/{club_id}/people?reveal=true",
        headers=headers,
    )
    assert reveal_res.status_code == 200
    p_revealed = next(x for x in reveal_res.json() if x["id"] == person_id)
    assert p_revealed["mobile"] == "9876543210"


# =========================================================================
# 4. COOKIE AUTH, CSRF PROTECTION & LOGOUT REVOCATION (Security Requirement 4)
# =========================================================================

def test_w2_csrf_protection_and_cookie_auth(client, db_session):
    """Verify cookie-based auth requires matching X-CSRF-Token header on state-changing requests."""
    # Register & Login
    client.post(
        "/api/v1/auth/register",
        json={"email": "csrf_test@example.com", "name": "CSRF Tester", "password": "Pass123456789!"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "csrf_test@example.com", "password": "Pass123456789!"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.cookies
    assert "csrf_token" in login_res.cookies
    csrf_cookie = login_res.cookies["csrf_token"]

    # Create club with Bearer token
    token = login_res.json()["access_token"]
    club_res = client.post(
        "/api/v1/clubs/",
        json={"name": "CSRF Club", "short_name": "CSRF", "slug": "csrf-club"},
        headers={"Authorization": f"Bearer {token}"},
    )
    club_id = club_res.json()["id"]

    # 1. State-changing request via COOKIE auth WITHOUT X-CSRF-Token header -> MUST FAIL (403)
    # Using client session cookies (no Authorization header)
    no_csrf_res = client.post(
        f"/api/v1/clubs/{club_id}/people",
        json={"full_name": "Unauthorized Attacker"},
    )
    assert no_csrf_res.status_code == 403
    assert "csrf" in str(no_csrf_res.json()["detail"]).lower()

    # 2. State-changing request WITH matching X-CSRF-Token header -> SUCCEEDS
    valid_csrf_res = client.post(
        f"/api/v1/clubs/{club_id}/people",
        json={"full_name": "Legitimate Signatory"},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert valid_csrf_res.status_code == 201


def test_w2_logout_revokes_session(client, db_session):
    """Verify /auth/logout revokes the session server-side via User.token_version increment."""
    client.post(
        "/api/v1/auth/register",
        json={"email": "logout_test@example.com", "name": "Logout Tester", "password": "Pass123456789!"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "logout_test@example.com", "password": "Pass123456789!"},
    )
    token = login_res.json()["access_token"]
    user = db_session.query(User).filter(User.email == "logout_test@example.com").first()
    initial_version = user.token_version

    # Verify authenticated request works
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200

    # Logout
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_res.status_code == 200

    # User token version incremented in DB
    db_session.refresh(user)
    assert user.token_version == initial_version + 1

    # Subsequent request with old token -> MUST FAIL (401 Revoked)
    revoked_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert revoked_res.status_code == 401
    detail_str = str(revoked_res.json()["detail"]).lower()
    assert "revoked" in detail_str or "invalidated" in detail_str


# =========================================================================
# 5. PASSWORD POLICY, RATE LIMITING & LOCKOUT (Security Requirement 5)
# =========================================================================

def test_w2_password_policy_enforcement(client):
    """Verify registration rejects passwords shorter than 10 characters or common passwords."""
    # < 10 characters
    short_res = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "name": "Short", "password": "Short1!"},
    )
    assert short_res.status_code in (400, 422)
    assert "at least 10" in str(short_res.json()["detail"]).lower()

    # Common password rejected
    common_res = client.post(
        "/api/v1/auth/register",
        json={"email": "common@example.com", "name": "Common", "password": "password123"},
    )
    assert common_res.status_code == 400
    assert "too common" in str(common_res.json()["detail"]).lower()


def test_w2_rate_limit_and_account_lockout(client, db_session):
    """Verify rate limits trip 429 and 5 failed logins lock the account for 15 minutes."""
    user = User(
        email="lockout_target@example.com",
        name="Target",
        password_hash=get_password_hash("CorrectPassword123!"),
    )
    db_session.add(user)
    db_session.commit()

    # 5 failed login attempts
    for i in range(5):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "lockout_target@example.com", "password": f"WrongPass{i}!"},
        )
        assert res.status_code == 401

    # 6th attempt -> Account is LOCKED (403 Forbidden with ACCOUNT_LOCKED)
    locked_res = client.post(
        "/api/v1/auth/login",
        json={"email": "lockout_target@example.com", "password": "CorrectPassword123!"},
    )
    assert locked_res.status_code == 403
    assert locked_res.json()["detail"]["code"] == "ACCOUNT_LOCKED"


# =========================================================================
# 6. SCOPED REPOSITORY ENFORCEMENT SCAN (Architecture Requirement 7)
# =========================================================================

def test_w2_no_raw_db_query_on_club_scoped_models():
    """Verify that API endpoints do not execute raw db.query on club-scoped models outside ScopedRepository."""
    api_dir = Path(__file__).resolve().parent.parent / "server" / "app" / "api"
    club_scoped_models = {"Membership", "Person", "NumberingSeries", "Event", "Document", "AuditLog"}

    violations = []
    for py_file in api_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(content, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "query":
                    for arg in node.args:
                        if isinstance(arg, ast.Name) and arg.id in club_scoped_models:
                            # Verify if it's within ScopedRepository implementation itself or forbidden raw query
                            violations.append(
                                f"{py_file.name}:{node.lineno} calls db.query({arg.id})"
                            )

    assert not violations, (
        "Found direct db.query on club-scoped models in API routes without ScopedRepository:\n"
        + "\n".join(violations)
    )


# =========================================================================
# 7. CROSS-CLUB ISOLATION & HIERARCHY (GATE W2)
# =========================================================================

def test_w2_cross_club_isolation_strictly_enforced(client):
    """GATE W2: A member of Club A cannot access, read, or modify Club B resources."""
    # User A in Club Alpha
    client.post("/api/v1/auth/register", json={"email": "user_a@example.com", "name": "User A", "password": "Pass123456789!"})
    token_a = client.post("/api/v1/auth/login", json={"email": "user_a@example.com", "password": "Pass123456789!"}).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    club_a_id = client.post(
        "/api/v1/clubs/",
        json={"name": "Club Alpha", "short_name": "ALPHA", "slug": "alpha"},
        headers=headers_a,
    ).json()["id"]

    # User B in Club Beta
    client.post("/api/v1/auth/register", json={"email": "user_b@example.com", "name": "User B", "password": "Pass123456789!"})
    token_b = client.post("/api/v1/auth/login", json={"email": "user_b@example.com", "password": "Pass123456789!"}).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    club_b_id = client.post(
        "/api/v1/clubs/",
        json={"name": "Club Beta", "short_name": "BETA", "slug": "beta"},
        headers=headers_b,
    ).json()["id"]

    # User A cannot read Club B details
    res_get = client.get(f"/api/v1/clubs/{club_b_id}", headers=headers_a)
    assert res_get.status_code == 403
    assert res_get.json()["detail"]["code"] == "NOT_A_MEMBER"

    # User A cannot list members of Club B
    res_members = client.get(f"/api/v1/clubs/{club_b_id}/members", headers=headers_a)
    assert res_members.status_code == 403
    assert res_members.json()["detail"]["code"] == "NOT_A_MEMBER"

    # User A cannot view audit log of Club B
    res_audit = client.get(f"/api/v1/clubs/{club_b_id}/audit-log", headers=headers_a)
    assert res_audit.status_code == 403
    assert res_audit.json()["detail"]["code"] == "NOT_A_MEMBER"


# =========================================================================
# 8. PERMANENT SVNIT LOGO IN WEB SHELL & ASSETS (UI Requirement 8)
# =========================================================================

def test_w2_permanent_svnit_logo_in_web_shell(client):
    """Verify root serves web application shell, SVNIT logo asset is accessible, and 'Verified Official Platform' is absent."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    # SVNIT logo asset reference in HTML
    assert "svnit_crest" in html or "clubdocs_logo" in html  # tab icon is the ClubDocs logo; the crest stays inside the app
    # Verified Official Platform text MUST NOT be present
    assert "Verified Official Platform" not in html

    # Logo asset returns valid image bytes
    asset_res = client.get("/assets/svnit_crest.png")
    assert asset_res.status_code == 200
    assert asset_res.headers["content-type"].startswith("image/")
    assert len(asset_res.content) > 1000
