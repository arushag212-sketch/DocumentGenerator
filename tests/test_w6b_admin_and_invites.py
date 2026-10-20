"""Phase W6b Tests:
1. Invites:
   - Club admins create an invite (link/code with role and 7-day expiry, single-use or limited uses)
   - Roles cannot exceed inviter's own role (admin cannot create owner invite)
   - Viewer cannot create invites (403)
   - Expired invite rejected (400)
   - Revoked invite rejected (400)
   - Used-up invite rejected (400)
   - Another club's invite cannot be used with a different club's ID (400)
   - Registering with invite code creates user and auto-joins club
   - Audit log entries recorded for invite_created, invite_revoked, invite_accepted
2. Admin Pages (CRUD, permission-checked, club-scoped):
   - Letterheads & Logos: editors can view, admins can create/update, editors blocked (403)
   - People & Signatories: editors can view, mobile masked; admin can reveal; admin CRUD, editors blocked (403)
   - Venues: editors can view, admin CRUD, editors blocked (403)
   - Numbering series: editors can view, admin CRUD, changing format never rewrites existing numbers, editors blocked (403)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from server.app.core.permissions import Role
from server.app.main import app
from server.app.models import AuditLog, Club, Document, Invite, Membership, NumberingSeries, Person, RoleHeld, Template, TemplateVersion, User, Venue


from server.app.core.database import SessionLocal


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def owner_context(client):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    clubs = client.get("/api/v1/clubs/", headers=headers).json()
    acm = next(c for c in clubs if c["short_name"] == "ACM")
    return {"headers": headers, "club_id": acm["id"], "user_id": res.json()["user"]["id"]}


@pytest.fixture(scope="module")
def editor_context(client, owner_context):
    """Ensure an editor user exists and return their auth context."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "secretary@svnit.ac.in", "password": "SecretaryPass123!"},
    )
    if res.status_code == 200:
        token = res.json()["access_token"]
        return {"headers": {"Authorization": f"Bearer {token}"}, "club_id": owner_context["club_id"], "user_id": res.json()["user"]["id"]}

    # Fallback create editor
    email = "editor.test@svnit.ac.in"
    with SessionLocal() as db_session:
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            from server.app.core.security import get_password_hash
            user = User(
                email=email,
                name="Test Editor",
                password_hash=get_password_hash("EditorPass123!"),
                token_version=1,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        m = db_session.query(Membership).filter(Membership.club_id == owner_context["club_id"], Membership.user_id == user.id).first()
        if not m:
            m = Membership(club_id=owner_context["club_id"], user_id=user.id, role="editor", status="active")
            db_session.add(m)
            db_session.commit()

        uid = user.id

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "EditorPass123!"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "club_id": owner_context["club_id"], "user_id": uid}


@pytest.fixture(scope="module")
def viewer_context(client, owner_context):
    """Create and return viewer auth context."""
    email = "viewer.test@svnit.ac.in"
    with SessionLocal() as db_session:
        from server.app.core.security import get_password_hash
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                name="Test Viewer",
                password_hash=get_password_hash("ViewerPass123!"),
                token_version=1,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        m = db_session.query(Membership).filter(Membership.club_id == owner_context["club_id"], Membership.user_id == user.id).first()
        if not m:
            m = Membership(club_id=owner_context["club_id"], user_id=user.id, role="viewer", status="active")
            db_session.add(m)
            db_session.commit()

        uid = user.id

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "ViewerPass123!"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "club_id": owner_context["club_id"], "user_id": uid}


# ==============================================================================
# PART 1: INVITE TESTS
# ==============================================================================


def test_invite_creation_and_role_limits(client, owner_context, editor_context, viewer_context):
    club_id = owner_context["club_id"]

    # 1. Viewer cannot create invites (403)
    res_v = client.post(
        f"/api/v1/clubs/{club_id}/invites",
        json={"role": "editor", "max_uses": 1, "expiry_days": 7},
        headers=viewer_context["headers"],
    )
    assert res_v.status_code == 403, "Viewer must not be allowed to create invites"

    # 2. Editor cannot create invites (403)
    res_e = client.post(
        f"/api/v1/clubs/{club_id}/invites",
        json={"role": "viewer", "max_uses": 1, "expiry_days": 7},
        headers=editor_context["headers"],
    )
    assert res_e.status_code == 403, "Editor must not be allowed to create invites"

    # 3. Club owner creates valid invite
    res_o = client.post(
        f"/api/v1/clubs/{club_id}/invites",
        json={"role": "editor", "max_uses": 2, "expiry_days": 7},
        headers=owner_context["headers"],
    )
    assert res_o.status_code == 201
    data = res_o.json()
    assert len(data["code"]) >= 16
    assert not data["code"].startswith("INV-")
    assert not data["code"].startswith("ACM-")
    assert data["max_uses"] == 2
    assert data["use_count"] == 0
    assert not data["revoked"]
    assert "?invite=" in data["invite_link"]


def test_invite_role_cannot_exceed_inviter(client, owner_context, db_session):
    club_id = owner_context["club_id"]

    # Create a regular admin user (not owner)
    email = "admin.member@svnit.ac.in"
    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        from server.app.core.security import get_password_hash
        user = User(email=email, name="Admin Member", password_hash=get_password_hash("AdminPass123!"), token_version=1)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    m = db_session.query(Membership).filter(Membership.club_id == club_id, Membership.user_id == user.id).first()
    if not m:
        m = Membership(club_id=club_id, user_id=user.id, role="admin", status="active")
        db_session.add(m)
        db_session.commit()

    admin_login = client.post("/api/v1/auth/login", json={"email": email, "password": "AdminPass123!"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Admin trying to create an 'owner' invite must be rejected (403)
    res = client.post(
        f"/api/v1/clubs/{club_id}/invites",
        json={"role": "owner", "max_uses": 1, "expiry_days": 7},
        headers=admin_headers,
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "ROLE_EXCEEDS_INVITER"


def test_expired_revoked_and_used_up_invites_rejected(client, owner_context, db_session):
    club_id = owner_context["club_id"]

    # 1. Create a single-use invite
    res = client.post(
        f"/api/v1/clubs/{club_id}/invites",
        json={"role": "editor", "max_uses": 1, "expiry_days": 7},
        headers=owner_context["headers"],
    )
    assert res.status_code == 201
    inv_data = res.json()
    code = inv_data["code"]
    inv_id = inv_data["id"]

    # Preview public invite
    prev = client.get(f"/api/v1/invites/{code}")
    assert prev.status_code == 200
    assert prev.json()["is_valid"] is True

    # 2. Revoke the invite
    rev = client.post(f"/api/v1/clubs/{club_id}/invites/{inv_id}/revoke", headers=owner_context["headers"])
    assert rev.status_code == 200

    # Preview now returns generic INVALID_OR_EXPIRED_INVITE (400)
    prev_rev = client.get(f"/api/v1/invites/{code}")
    assert prev_rev.status_code == 400
    assert prev_rev.json()["detail"]["code"] == "INVALID_OR_EXPIRED_INVITE"

    # Register with revoked invite fails with generic error (400)
    reg_rev = client.post(
        "/api/v1/auth/register",
        json={
            "email": "revoked.user@example.com",
            "name": "Revoked User",
            "password": "Password123!Secure",
            "invite_code": code,
        },
    )
    assert reg_rev.status_code == 400
    assert reg_rev.json()["detail"]["code"] == "INVALID_OR_EXPIRED_INVITE"

    # 3. Create an invite and simulate expiry
    res_exp = client.post(
        f"/api/v1/clubs/{club_id}/invites",
        json={"role": "viewer", "max_uses": 1, "expiry_days": 1},
        headers=owner_context["headers"],
    )
    code_exp = res_exp.json()["code"]
    inv_rec = db_session.query(Invite).filter(Invite.id == res_exp.json()["id"]).first()
    inv_rec.expires_at = datetime.utcnow() - timedelta(days=2)
    db_session.commit()

    reg_exp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "expired.user@example.com",
            "name": "Expired User",
            "password": "Password123!Secure",
            "invite_code": code_exp,
        },
    )
    assert reg_exp.status_code == 400
    assert reg_exp.json()["detail"]["code"] == "INVALID_OR_EXPIRED_INVITE"

    # 4. Create single-use invite, consume it, and verify second use is rejected
    res_use = client.post(
        f"/api/v1/clubs/{club_id}/invites",
        json={"role": "editor", "max_uses": 1, "expiry_days": 7},
        headers=owner_context["headers"],
    )
    code_use = res_use.json()["code"]

    reg1 = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user.first@example.com",
            "name": "First User",
            "password": "Password123!Secure",
            "invite_code": code_use,
        },
    )
    assert reg1.status_code == 201

    reg2 = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user.second@example.com",
            "name": "Second User",
            "password": "Password123!Secure",
            "invite_code": code_use,
        },
    )
    assert reg2.status_code == 400
    assert reg2.json()["detail"]["code"] == "INVALID_OR_EXPIRED_INVITE"

    # 5. Unknown code returns identical response
    prev_unknown = client.get("/api/v1/invites/completely_random_unknown_token_123")
    assert prev_unknown.status_code == 400
    assert prev_unknown.json() == prev_rev.json() == reg_rev.json() == reg_exp.json() == reg2.json()

    # 6. Audit log records failed attempts
    failed_logs = db_session.query(AuditLog).filter(AuditLog.action == "invite_failed").all()
    assert len(failed_logs) >= 4


def test_cross_club_invite_mismatch_rejected(client, owner_context, db_session):
    club_id = owner_context["club_id"]

    # Create a secondary club
    club2 = Club(
        id=str(uuid.uuid4()),
        name="Secondary Robotics Club",
        short_name="SRC",
        slug="src",
        chapter_code="7/88",
        academic_year_default="2026-27",
    )
    db_session.add(club2)
    db_session.commit()

    # Create invite for primary ACM club
    res_inv = client.post(
        f"/api/v1/clubs/{club_id}/invites",
        json={"role": "editor", "max_uses": 1, "expiry_days": 7},
        headers=owner_context["headers"],
    )
    acm_code = res_inv.json()["code"]

    # Register an independent user
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "neutral.user@svnit.ac.in", "name": "Neutral User", "password": "Password123!Secure"},
    )
    user_token = reg.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Attempt to accept ACM invite with secondary club's ID must fail (400)
    res_accept = client.post(
        f"/api/v1/invites/{acm_code}/accept",
        json={"club_id": club2.id},
        headers=user_headers,
    )
    assert res_accept.status_code == 400
    assert res_accept.json()["detail"]["code"] == "INVALID_CLUB_INVITE"

    # Accepting with matching club_id or omitted club_id succeeds
    res_ok = client.post(
        f"/api/v1/invites/{acm_code}/accept",
        json={"club_id": club_id},
        headers=user_headers,
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["club_id"] == club_id


def test_invite_audit_log_entries(client, owner_context, db_session):
    club_id = owner_context["club_id"]

    res_inv = client.post(
        f"/api/v1/clubs/{club_id}/invites",
        json={"role": "viewer", "max_uses": 1, "expiry_days": 7},
        headers=owner_context["headers"],
    )
    code = res_inv.json()["code"]
    inv_id = res_inv.json()["id"]

    # Verify invite_created in audit log
    audit_create = db_session.query(AuditLog).filter(
        AuditLog.club_id == club_id,
        AuditLog.action == "invite_created",
        AuditLog.entity_id == inv_id,
    ).first()
    import hashlib
    assert audit_create.meta["code_hash"] == hashlib.sha256(code.encode()).hexdigest()[:16]
    assert "code" not in audit_create.meta

    # Revoke and verify invite_revoked in audit log
    client.post(f"/api/v1/clubs/{club_id}/invites/{inv_id}/revoke", headers=owner_context["headers"])
    audit_rev = db_session.query(AuditLog).filter(
        AuditLog.club_id == club_id,
        AuditLog.action == "invite_revoked",
        AuditLog.entity_id == inv_id,
    ).first()
    assert audit_rev is not None


# ==============================================================================
# PART 2: ADMIN PAGES & PERMISSION BOUNDARIES
# ==============================================================================


def test_people_and_signatories_crud_and_mobile_masking(client, owner_context, editor_context):
    club_id = owner_context["club_id"]

    # 1. Create a person as Admin
    person_payload = {
        "full_name": "Dr. Rajesh Sharma",
        "department": "Computer Science & Engineering",
        "branch": "CSE",
        "roll_no": "FAC-042",
        "mobile": "+91 9876543210",
        "email": "rajesh@svnit.ac.in",
    }
    create_res = client.post(f"/api/v1/clubs/{club_id}/people", json=person_payload, headers=owner_context["headers"])
    assert create_res.status_code == 201
    person_id = create_res.json()["id"]

    # 2. Editor views people -> mobile MUST be masked, even if editor sets reveal=true!
    res_editor_view = client.get(f"/api/v1/clubs/{club_id}/people?reveal=true", headers=editor_context["headers"])
    assert res_editor_view.status_code == 200
    p_editor = next(p for p in res_editor_view.json() if p["id"] == person_id)
    assert p_editor["mobile"] not in ("+91 9876543210", "9876543210"), "Editor must NEVER see plaintext mobile"
    assert "*" in p_editor["mobile"], "Editor must receive masked mobile"

    # 3. Admin views people with reveal=false -> masked
    res_admin_masked = client.get(f"/api/v1/clubs/{club_id}/people?reveal=false", headers=owner_context["headers"])
    assert res_admin_masked.status_code == 200
    p_admin_masked = next(p for p in res_admin_masked.json() if p["id"] == person_id)
    assert "*" in p_admin_masked["mobile"]

    # 4. Admin views people with reveal=true -> plaintext revealed!
    res_admin_revealed = client.get(f"/api/v1/clubs/{club_id}/people?reveal=true", headers=owner_context["headers"])
    assert res_admin_revealed.status_code == 200
    p_admin_revealed = next(p for p in res_admin_revealed.json() if p["id"] == person_id)
    assert p_admin_revealed["mobile"] == "9876543210", "mobile is stored as 10 digits (prefix and spaces removed)"

    # 5. Editor cannot update or delete person (403)
    res_ed_upd = client.put(f"/api/v1/clubs/{club_id}/people/{person_id}", json={"full_name": "Hacked Name"}, headers=editor_context["headers"])
    assert res_ed_upd.status_code == 403

    res_ed_del = client.delete(f"/api/v1/clubs/{club_id}/people/{person_id}", headers=editor_context["headers"])
    assert res_ed_del.status_code == 403

    # 6. Admin assigns a role/designation to person
    role_payload = {
        "person_id": person_id,
        "role_key": "faculty_co_chair",
        "designation_label": "Co-Chairman (ACM)",
        "academic_year": "2026-27",
    }
    role_res = client.post(f"/api/v1/clubs/{club_id}/roles", json=role_payload, headers=owner_context["headers"])
    assert role_res.status_code == 201
    role_id = role_res.json()["id"]

    # Editor cannot edit or delete role (403)
    assert client.put(f"/api/v1/clubs/{club_id}/roles/{role_id}", json={"designation_label": "Unauthorized"}, headers=editor_context["headers"]).status_code == 403
    assert client.delete(f"/api/v1/clubs/{club_id}/roles/{role_id}", headers=editor_context["headers"]).status_code == 403

    # Admin updates and deletes role
    upd_role = client.put(f"/api/v1/clubs/{club_id}/roles/{role_id}", json={"designation_label": "Senior Co-Chairman (ACM)"}, headers=owner_context["headers"])
    assert upd_role.status_code == 200
    assert upd_role.json()["designation_label"] == "Senior Co-Chairman (ACM)"

    assert client.delete(f"/api/v1/clubs/{club_id}/roles/{role_id}", headers=owner_context["headers"]).status_code == 200

    # Admin deletes person
    assert client.delete(f"/api/v1/clubs/{club_id}/people/{person_id}", headers=owner_context["headers"]).status_code == 200


def test_venues_crud_and_permissions(client, owner_context, editor_context):
    club_id = owner_context["club_id"]

    # 1. Editor can view venues
    res_v = client.get(f"/api/v1/clubs/{club_id}/venues", headers=editor_context["headers"])
    assert res_v.status_code == 200
    assert isinstance(res_v.json(), list)

    # 2. Editor cannot create a venue (403)
    venue_payload = {
        "name": "Computer Center Lab 3",
        "short_name": "CC-3",
        "addressee_default": "The Faculty In-charge, CCC",
    }
    res_ed_create = client.post(f"/api/v1/clubs/{club_id}/venues", json=venue_payload, headers=editor_context["headers"])
    assert res_ed_create.status_code == 403

    # 3. Admin creates venue
    res_adm_create = client.post(f"/api/v1/clubs/{club_id}/venues", json=venue_payload, headers=owner_context["headers"])
    assert res_adm_create.status_code == 201
    venue_id = res_adm_create.json()["id"]
    assert res_adm_create.json()["name"] == "Computer Center Lab 3"

    # 4. Editor cannot update or delete venue (403)
    assert client.put(f"/api/v1/clubs/{club_id}/venues/{venue_id}", json={"name": "Tampered"}, headers=editor_context["headers"]).status_code == 403
    assert client.delete(f"/api/v1/clubs/{club_id}/venues/{venue_id}", headers=editor_context["headers"]).status_code == 403

    # 5. Admin updates and deletes venue
    upd_res = client.put(f"/api/v1/clubs/{club_id}/venues/{venue_id}", json={"short_name": "CC-03"}, headers=owner_context["headers"])
    assert upd_res.status_code == 200
    assert upd_res.json()["short_name"] == "CC-03"

    del_res = client.delete(f"/api/v1/clubs/{club_id}/venues/{venue_id}", headers=owner_context["headers"])
    assert del_res.status_code == 200


def test_numbering_series_format_update_never_rewrites_existing_numbers(client, owner_context, editor_context, db_session):
    club_id = owner_context["club_id"]
    series_key = "ROOM"

    # 1. Editor can view numbering series
    res_view = client.get(f"/api/v1/clubs/{club_id}/numbering", headers=editor_context["headers"])
    assert res_view.status_code == 200
    assert any(s["key"] == series_key for s in res_view.json())

    # 2. Editor cannot change format (403)
    res_ed_upd = client.put(
        f"/api/v1/clubs/{club_id}/numbering/{series_key}",
        json={"format": "HACKED/{seq}"},
        headers=editor_context["headers"],
    )
    assert res_ed_upd.status_code == 403

    # 3. Generate a document with current format
    res_reserve = client.post(
        f"/api/v1/clubs/{club_id}/numbering/{series_key}/reserve",
        json={"template_id": "permission_letter"},
        headers=owner_context["headers"],
    )
    assert res_reserve.status_code == 200
    res_data = res_reserve.json()
    orig_ref = res_data["ref_no"]

    gen_payload = {
        "template_id": "permission_letter",
        "title": "Existing Doc Before Numbering Update",
        "ref_no": orig_ref,
        "ref_no_confirmed": True,
        "reservation_id": res_data["reservation_id"],
        "event_data": {
            "event_name": "Existing Doc Before Numbering Update",
            "venue": "Seminar Hall",
            "dates": "15/10/2026",
            "time_start": "09:00 AM",
            "time_end": "05:00 PM",
            "description": "Verify format update never alters existing document numbers",
            "expected_participants": 40,
            "submitted_to": "Head of Department, CSE",
        },
        "confirmed_fields": ["description"],
    }
    gen_res = client.post(f"/api/v1/clubs/{club_id}/documents/generate", json=gen_payload, headers=owner_context["headers"])
    assert gen_res.status_code == 200
    doc_id = gen_res.json()["id"]

    # 4. Admin updates format pattern
    new_fmt = "ACM/{academic_year}/NEW_ROOM/{seq:04d}"
    upd_fmt = client.put(
        f"/api/v1/clubs/{club_id}/numbering/{series_key}",
        json={"format": new_fmt},
        headers=owner_context["headers"],
    )
    assert upd_fmt.status_code == 200
    assert upd_fmt.json()["format"] == new_fmt

    # 5. ASSERT existing document's ref_no was NEVER rewritten!
    doc_in_db = db_session.query(Document).filter(Document.id == doc_id).first()
    assert doc_in_db.ref_no == orig_ref, f"Expected {orig_ref} to remain unchanged, but got {doc_in_db.ref_no}"


def test_invite_rate_limit_brute_force_gets_429(client):
    """10 requests allowed per minute; 11th request triggers 429."""
    from server.app.core.rate_limit import clear_rate_limits
    clear_rate_limits()

    # Make 10 requests from same IP with different invalid tokens
    for i in range(10):
        res = client.get(f"/api/v1/invites/brute_force_token_{i}")
        assert res.status_code == 400

    # 11th request from same IP gets 429 Too Many Requests
    res_blocked = client.get("/api/v1/invites/brute_force_token_11")
    assert res_blocked.status_code == 429
    assert res_blocked.json()["detail"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_invite_code_hash_stored_in_db_not_plaintext(client, owner_context, db_session):
    """Raw code is returned once on creation; DB stores code_hash and code is None."""
    import hashlib
    club_id = owner_context["club_id"]
    res = client.post(
        f"/api/v1/clubs/{club_id}/invites",
        json={"role": "editor", "max_uses": 1, "expiry_days": 7},
        headers=owner_context["headers"],
    )
    assert res.status_code == 201
    data = res.json()
    raw_code = data["code"]
    inv_id = data["id"]

    inv_row = db_session.query(Invite).filter(Invite.id == inv_id).first()
    assert inv_row is not None
    assert inv_row.code_hash == hashlib.sha256(raw_code.encode()).hexdigest()
    assert inv_row.code is None, "Plaintext invite code must NOT be stored in the database"


def test_production_seed_creates_no_demo_users(monkeypatch):
    """When ENVIRONMENT=production, seed refuses demo users and platform admin."""
    from server.scripts.seed import seed
    monkeypatch.setenv("ENVIRONMENT", "production")

    # Explicit request for demo users in production must raise RuntimeError
    with pytest.raises(RuntimeError, match="Refusing to create demo users"):
        seed(clean=False, demo_users=True)

    # Calling seed in production mode runs cleanly without creating any demo users
    seed(clean=False)
    with SessionLocal() as session:
        demo_lead = session.query(User).filter(User.email == "demo.lead@example.com").first()
        admin = session.query(User).filter(User.email == "admin@svnit.ac.in").first()
        assert demo_lead is None
        assert admin is None


def test_template_unique_names_enforced(client, owner_context):
    """409 DUPLICATE_TEMPLATE_NAME on create, rename, and publish collisions."""
    club_id = owner_context["club_id"]

    # 1. Create a blank template
    t_name = f"Unique Workshop Form {uuid.uuid4().hex[:6]}"
    create_res = client.post(
        f"/api/v1/clubs/{club_id}/documents/templates/blank",
        json={"name": t_name},
        headers=owner_context["headers"],
    )
    assert create_res.status_code == 201
    tmpl_id = create_res.json()["id"]

    # 2. Attempting to create another blank template with same name -> 409
    dup_res = client.post(
        f"/api/v1/clubs/{club_id}/documents/templates/blank",
        json={"name": t_name},
        headers=owner_context["headers"],
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["detail"]["code"] == "DUPLICATE_TEMPLATE_NAME"

    # 3. Attempting to create with system template name "Permission Letter" -> 409
    sys_dup = client.post(
        f"/api/v1/clubs/{club_id}/documents/templates/blank",
        json={"name": "Permission Letter"},
        headers=owner_context["headers"],
    )
    assert sys_dup.status_code == 409
    assert sys_dup.json()["detail"]["code"] == "DUPLICATE_TEMPLATE_NAME"

    # 4. Create second template and rename to existing name -> 409
    t2_name = f"Second Template {uuid.uuid4().hex[:6]}"
    c2 = client.post(
        f"/api/v1/clubs/{club_id}/documents/templates/blank",
        json={"name": t2_name},
        headers=owner_context["headers"],
    )
    assert c2.status_code == 201
    t2_id = c2.json()["id"]

    rename_res = client.put(
        f"/api/v1/clubs/{club_id}/documents/templates/{t2_id}",
        json={"name": t_name},
        headers=owner_context["headers"],
    )
    assert rename_res.status_code == 409
    assert rename_res.json()["detail"]["code"] == "DUPLICATE_TEMPLATE_NAME"


def test_recommender_club_template_filtering(client, owner_context, db_session):
    """Recommender lists a club template only when the request names it, otherwise in other_templates."""
    club_id = owner_context["club_id"]

    # Create two custom published club templates:
    # 1. Matched: stage="pre_event", triggers=["coding"]
    t1 = Template(
        id=str(uuid.uuid4()),
        club_id=club_id,
        slug=f"club-code-{uuid.uuid4().hex[:6]}",
        name=f"Coding Contest Registration Form {uuid.uuid4().hex[:4]}",
        category="Official Event Documents",
        stage="pre_event",
        is_system=False,
        status="published",
    )
    db_session.add(t1)
    db_session.flush()

    s1_yaml = "id: coding\nname: Coding Contest\nstage: pre_event\ntriggers:\n  - coding\nfields: []\n"
    v1 = TemplateVersion(
        id=str(uuid.uuid4()),
        template_id=t1.id,
        version_no=1,
        schema_yaml=s1_yaml,
        docx_storage_key="storage/templates/permission_letter_v1.docx",
    )
    db_session.add(v1)
    db_session.flush()
    t1.current_version_id = v1.id

    # 2. Unmatched: stage="meeting", triggers=["agm", "executive"]
    t2 = Template(
        id=str(uuid.uuid4()),
        club_id=club_id,
        slug=f"club-agm-{uuid.uuid4().hex[:6]}",
        name=f"Annual General Meeting Protocol {uuid.uuid4().hex[:4]}",
        category="Official Event Documents",
        stage="meeting",
        is_system=False,
        status="published",
    )
    db_session.add(t2)
    db_session.flush()

    s2_yaml = "id: agm\nname: AGM Protocol\nstage: meeting\ntriggers:\n  - agm\n  - executive\nfields: []\n"
    v2 = TemplateVersion(
        id=str(uuid.uuid4()),
        template_id=t2.id,
        version_no=1,
        schema_yaml=s2_yaml,
        docx_storage_key="storage/templates/permission_letter_v1.docx",
    )
    db_session.add(v2)
    db_session.flush()
    t2.current_version_id = v2.id
    db_session.commit()

    # Query recommender for pre-event workshop (no AGM triggers)
    rec_res = client.post(
        f"/api/v1/clubs/{club_id}/events/recommend",
        json={"text": "We are conducting a coding contest on 14-15 October in Seminar Hall; prepare the registration form."},
        headers=owner_context["headers"],
    )
    assert rec_res.status_code == 200
    data = rec_res.json()

    rec_tmpl_ids = [t["template_id"] for t in data["templates"]]
    other_tmpl_ids = [t["template_id"] for t in data["other_templates"]]

    # t1 is named by the request (coding contest ... registration form) -> listed in templates
    assert t1.id in rec_tmpl_ids

    # t2 (meeting stage, no trigger match) does not match -> hidden under other_templates
    assert t2.id in other_tmpl_ids
    assert t2.id not in rec_tmpl_ids

