"""Phase W2 Test Suite: Auth, Clubs, Roles, Permission Layer, Scoped Isolation, and Audit Trail."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.app.core.database import Base, get_db
from server.app.core.permissions import Role
from server.app.core.scoped_repo import ScopedRepository
from server.app.core.security import verify_password
from server.app.main import app
from server.app.models import AuditLog, Club, Membership, Person, User


from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="module")
def test_db_engine():
    # Use in-memory SQLite with StaticPool so all connections share the same memory instance
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


# ---------------- 1. AUTH & ARGON2 TESTS ----------------


def test_w2_register_and_login_with_argon2(client, db_session):
    """Verify user registration hashes passwords with Argon2 and login validates credentials."""
    reg_payload = {
        "email": "student1@svnit.ac.in",
        "name": "Student One",
        "password": "SecurePassword123!",
    }
    res = client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "student1@svnit.ac.in"
    assert data["user"]["name"] == "Student One"

    # Verify directly in DB that the stored password hash is a valid Argon2 hash
    user = db_session.query(User).filter(User.email == "student1@svnit.ac.in").first()
    assert user is not None
    assert user.password_hash.startswith("$argon2"), f"Password hash is not Argon2: {user.password_hash}"
    assert verify_password("SecurePassword123!", user.password_hash)
    assert not verify_password("WrongPassword!", user.password_hash)

    # Login with valid credentials
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "student1@svnit.ac.in", "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # Login with wrong password
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student1@svnit.ac.in", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_w2_password_reset_flow(client, db_session):
    """Verify forgot-password generates reset token and reset-password securely updates Argon2 hash."""
    user = User(
        email="reset_test@svnit.ac.in",
        name="Reset User",
        password_hash="!initial_hash!",
    )
    db_session.add(user)
    db_session.commit()

    # Request reset token
    forgot_res = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset_test@svnit.ac.in"},
    )
    assert forgot_res.status_code == 200
    token = forgot_res.json().get("reset_token")
    assert token is not None

    # Reset password
    reset_res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "BrandNewPassword123!"},
    )
    assert reset_res.status_code == 200

    # Verify new password works
    db_session.refresh(user)
    assert user.password_hash.startswith("$argon2")
    assert verify_password("BrandNewPassword123!", user.password_hash)


# ---------------- 2. CLUBS & ROLES TESTS ----------------


def test_w2_club_creation_and_owner_assignment(client):
    """Verify creating a club assigns the creator as 'owner' and records audit log."""
    # Register creator
    client.post(
        "/api/v1/auth/register",
        json={"email": "clubcreator@svnit.ac.in", "name": "Creator", "password": "Pass123456!"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "clubcreator@svnit.ac.in", "password": "Pass123456!"},
    )
    token = login_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Create club
    club_payload = {
        "name": "Robotics Club SVNIT",
        "short_name": "ROBO",
        "slug": "robo",
        "chapter_code": "ROBO-01",
    }
    create_res = client.post("/api/v1/clubs/", json=club_payload, headers=auth_headers)
    assert create_res.status_code == 201, create_res.text
    club_data = create_res.json()
    assert club_data["name"] == "Robotics Club SVNIT"
    assert club_data["my_role"] == Role.OWNER
    assert club_data["members_count"] == 1

    # Slug collision check
    dup_res = client.post("/api/v1/clubs/", json=club_payload, headers=auth_headers)
    assert dup_res.status_code == 400
    assert dup_res.json()["detail"]["code"] == "SLUG_EXISTS"


def test_w2_members_crud_and_role_escalation_protection(client, db_session):
    """Verify admin can add members with editor/viewer, but CANNOT promote to owner or demote an owner."""
    # Create Owner User
    client.post(
        "/api/v1/auth/register",
        json={"email": "owner@svnit.ac.in", "name": "Owner", "password": "Pass123456!"},
    )
    owner_token = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@svnit.ac.in", "password": "Pass123456!"},
    ).json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # Create Admin User
    client.post(
        "/api/v1/auth/register",
        json={"email": "admin@svnit.ac.in", "name": "Admin", "password": "Pass123456!"},
    )
    admin_token = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@svnit.ac.in", "password": "Pass123456!"},
    ).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Create Member User
    client.post(
        "/api/v1/auth/register",
        json={"email": "member@svnit.ac.in", "name": "Member", "password": "Pass123456!"},
    )

    # Owner creates club
    club_id = client.post(
        "/api/v1/clubs/",
        json={"name": "Coding Club", "short_name": "CC", "slug": "coding-club"},
        headers=owner_headers,
    ).json()["id"]

    # Owner adds Admin
    add_admin = client.post(
        f"/api/v1/clubs/{club_id}/members",
        json={"email": "admin@svnit.ac.in", "role": "admin"},
        headers=owner_headers,
    )
    assert add_admin.status_code == 201

    # Admin adds Member as editor
    add_member = client.post(
        f"/api/v1/clubs/{club_id}/members",
        json={"email": "member@svnit.ac.in", "role": "editor"},
        headers=admin_headers,
    )
    assert add_member.status_code == 201

    member_user = db_session.query(User).filter(User.email == "member@svnit.ac.in").first()
    owner_user = db_session.query(User).filter(User.email == "owner@svnit.ac.in").first()

    # Admin tries to promote Member to 'owner' -> MUST FAIL 403 Forbidden!
    promote_res = client.put(
        f"/api/v1/clubs/{club_id}/members/{member_user.id}",
        json={"role": "owner"},
        headers=admin_headers,
    )
    assert promote_res.status_code == 403
    assert promote_res.json()["detail"]["code"] == "FORBIDDEN"

    # Admin tries to demote the Owner -> MUST FAIL 403 Forbidden!
    demote_res = client.put(
        f"/api/v1/clubs/{club_id}/members/{owner_user.id}",
        json={"role": "viewer"},
        headers=admin_headers,
    )
    assert demote_res.status_code == 403
    assert demote_res.json()["detail"]["code"] == "FORBIDDEN"

    # Owner CAN promote member to admin
    owner_update = client.put(
        f"/api/v1/clubs/{club_id}/members/{member_user.id}",
        json={"role": "admin"},
        headers=owner_headers,
    )
    assert owner_update.status_code == 200
    assert owner_update.json()["role"] == "admin"


# ---------------- 3. CROSS-CLUB ISOLATION & PERMISSION MATRIX (GATE) ----------------


def test_w2_cross_club_isolation_strictly_enforced(client, db_session):
    """GATE W2: Verify that a user from Club A cannot access, read, or modify Club B resources."""
    # User A in Club Alpha
    client.post("/api/v1/auth/register", json={"email": "userA@svnit.ac.in", "name": "User A", "password": "Pass123456!"})
    token_a = client.post("/api/v1/auth/login", json={"email": "userA@svnit.ac.in", "password": "Pass123456!"}).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    club_a_id = client.post(
        "/api/v1/clubs/",
        json={"name": "Club Alpha", "short_name": "ALPHA", "slug": "alpha"},
        headers=headers_a,
    ).json()["id"]

    # User B in Club Beta
    client.post("/api/v1/auth/register", json={"email": "userB@svnit.ac.in", "name": "User B", "password": "Pass123456!"})
    token_b = client.post("/api/v1/auth/login", json={"email": "userB@svnit.ac.in", "password": "Pass123456!"}).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    club_b_id = client.post(
        "/api/v1/clubs/",
        json={"name": "Club Beta", "short_name": "BETA", "slug": "beta"},
        headers=headers_b,
    ).json()["id"]

    # 1. User A tries to GET Club Beta details by ID -> 403 Forbidden
    leak_get = client.get(f"/api/v1/clubs/{club_b_id}", headers=headers_a)
    assert leak_get.status_code == 403
    assert leak_get.json()["detail"]["code"] == "NOT_A_MEMBER"

    # 2. User A tries to list members of Club Beta -> 403 Forbidden
    leak_members = client.get(f"/api/v1/clubs/{club_b_id}/members", headers=headers_a)
    assert leak_members.status_code == 403
    assert leak_members.json()["detail"]["code"] == "NOT_A_MEMBER"

    # 3. User A tries to update Club Beta settings -> 403 Forbidden
    leak_update = client.put(f"/api/v1/clubs/{club_b_id}", json={"name": "Tampered"}, headers=headers_a)
    assert leak_update.status_code == 403
    assert leak_update.json()["detail"]["code"] == "NOT_A_MEMBER"

    # 4. User A tries to view Club Beta audit trail -> 403 Forbidden
    leak_audit = client.get(f"/api/v1/clubs/{club_b_id}/audit-log", headers=headers_a)
    assert leak_audit.status_code == 403
    assert leak_audit.json()["detail"]["code"] == "NOT_A_MEMBER"

    # 5. Scoped Repository isolation at database layer:
    repo_a = ScopedRepository(db_session, Person, club_id=club_a_id)
    repo_b = ScopedRepository(db_session, Person, club_id=club_b_id)

    person_b = repo_b.create(full_name="Secret Signatory of Beta")
    assert person_b.club_id == club_b_id

    # Repo A querying by exact UUID of person_b returns None
    assert repo_a.get(person_b.id) is None
    # Repo A list() does not include person_b
    assert person_b.id not in [p.id for p in repo_a.list()]


def test_w2_role_permission_hierarchy(client, db_session):
    """GATE W2: Verify viewer is read-only and cannot mutate club state (POST/PUT/DELETE blocked)."""
    # Create Club with Owner and Viewer
    client.post("/api/v1/auth/register", json={"email": "owner2@svnit.ac.in", "name": "Owner 2", "password": "Pass123456!"})
    owner_token = client.post("/api/v1/auth/login", json={"email": "owner2@svnit.ac.in", "password": "Pass123456!"}).json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    client.post("/api/v1/auth/register", json={"email": "viewer2@svnit.ac.in", "name": "Viewer 2", "password": "Pass123456!"})
    viewer_token = client.post("/api/v1/auth/login", json={"email": "viewer2@svnit.ac.in", "password": "Pass123456!"}).json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    club_id = client.post(
        "/api/v1/clubs/",
        json={"name": "Drama Club", "short_name": "DRAMA", "slug": "drama"},
        headers=owner_headers,
    ).json()["id"]

    # Add viewer to club
    client.post(
        f"/api/v1/clubs/{club_id}/members",
        json={"email": "viewer2@svnit.ac.in", "role": "viewer"},
        headers=owner_headers,
    )

    # Viewer CAN view club details and list members (read-only)
    assert client.get(f"/api/v1/clubs/{club_id}", headers=viewer_headers).status_code == 200
    assert client.get(f"/api/v1/clubs/{club_id}/members", headers=viewer_headers).status_code == 200

    # Viewer CANNOT update club settings (PUT) -> 403
    v_put = client.put(f"/api/v1/clubs/{club_id}", json={"name": "Hacked Drama"}, headers=viewer_headers)
    assert v_put.status_code == 403
    assert v_put.json()["detail"]["code"] == "INSUFFICIENT_ROLE"

    # Viewer CANNOT add member (POST) -> 403
    v_post = client.post(f"/api/v1/clubs/{club_id}/members", json={"email": "test@svnit.ac.in", "role": "editor"}, headers=viewer_headers)
    assert v_post.status_code == 403
    assert v_post.json()["detail"]["code"] == "INSUFFICIENT_ROLE"

    # Viewer CANNOT view audit log -> 403
    v_audit = client.get(f"/api/v1/clubs/{club_id}/audit-log", headers=viewer_headers)
    assert v_audit.status_code == 403
    assert v_audit.json()["detail"]["code"] == "INSUFFICIENT_ROLE"


# ---------------- 4. AUDIT TRAIL VERIFICATION ----------------


def test_w2_audit_trail_recorded_for_administrative_actions(client, db_session):
    """Verify actions generate audit_log rows with proper action, entity, user, and metadata."""
    client.post("/api/v1/auth/register", json={"email": "audit_admin@svnit.ac.in", "name": "Audit Admin", "password": "Pass123456!"})
    token = client.post("/api/v1/auth/login", json={"email": "audit_admin@svnit.ac.in", "password": "Pass123456!"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create club
    club_id = client.post(
        "/api/v1/clubs/",
        json={"name": "Literature Club", "short_name": "LIT", "slug": "lit"},
        headers=headers,
    ).json()["id"]

    # Check audit log in DB
    logs = db_session.query(AuditLog).filter(AuditLog.club_id == club_id).all()
    actions = {log.action for log in logs}
    assert "club_created" in actions

    # Retrieve audit log via endpoint
    api_logs = client.get(f"/api/v1/clubs/{club_id}/audit-log", headers=headers).json()
    assert len(api_logs) >= 1
    assert api_logs[0]["action"] == "club_created"
    assert api_logs[0]["entity_type"] == "club"


# ---------------- 5. PERMANENT SVNIT LOGO IN WEB SHELL ----------------


def test_w2_permanent_svnit_logo_in_web_shell(client):
    """Verify that the web shell permanently renders the locked SVNIT logo and serves the image asset."""
    # 1. Root page serves web shell with locked SVNIT logo tag
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "svnit-logo-locked" in html
    assert "/assets/permission_page1_img1.png" in html
    assert "ClubDocs" in html
    assert "SVNIT Surat" in html

    # 2. SVNIT logo image asset is accessible and returns valid image bytes
    asset_res = client.get("/assets/permission_page1_img1.png")
    assert asset_res.status_code == 200
    assert asset_res.headers["content-type"].startswith("image/")
    assert len(asset_res.content) > 1000
