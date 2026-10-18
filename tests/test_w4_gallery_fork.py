"""Tests for Part 2: W4 Part (a) Template Gallery & Forking.

Requirements:
- Template gallery listing system and club templates with thumbnails, category, and numbering series.
- Forking creates an independent copy (draft template + version 1 + docx + schema).
- Editing the fork never changes the system template (system templates stay read-only).
- Viewers cannot fork (403 Forbidden).
- Another club cannot see the fork.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.models import (
    Club,
    Membership,
    Template,
    TemplateVersion,
    User,
)
from server.app.core.permissions import Role
from server.app.core.security import get_password_hash


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_setup(client):
    """Set up test users (owner, viewer, another club) and credentials."""
    from server.app.core.rate_limit import clear_rate_limits
    clear_rate_limits()

    # 1. Login as owner (demo.owner@svnit.ac.in)
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    owner_token = res.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # Fetch ACM club
    clubs = client.get("/api/v1/clubs/", headers=owner_headers).json()
    acm_club = next(c for c in clubs if c["short_name"] == "ACM")
    acm_club_id = acm_club["id"]

    # 2. Create / ensure viewer user and second club in DB
    from server.app.core.database import SessionLocal
    db = SessionLocal()
    try:
        # Viewer user
        viewer_user = db.query(User).filter(User.email == "test.viewer@svnit.ac.in").first()
        if not viewer_user:
            viewer_user = User(
                email="test.viewer@svnit.ac.in",
                password_hash=get_password_hash("ViewerPass123!"),
                name="Test Viewer",
                is_platform_admin=False,
            )
            db.add(viewer_user)
            db.flush()

        # Membership as viewer in ACM
        m_viewer = (
            db.query(Membership)
            .filter(Membership.club_id == acm_club_id, Membership.user_id == viewer_user.id)
            .first()
        )
        if not m_viewer:
            m_viewer = Membership(
                club_id=acm_club_id,
                user_id=viewer_user.id,
                role=Role.VIEWER,
                status="active",
            )
            db.add(m_viewer)
            db.flush()

        # Second Club (e.g. GDSC)
        other_club = db.query(Club).filter(Club.slug == "gdsc").first()
        if not other_club:
            other_club = Club(
                name="Google Developer Student Clubs, SVNIT",
                short_name="GDSC",
                slug="gdsc",
                chapter_code="7/10",
                head_of_account="7/10",
                academic_year_default="2026-27",
            )
            db.add(other_club)
            db.flush()

        other_club_id = other_club.id

        # Make demo owner an owner in GDSC as well to test cross-club visibility easily
        m_other = (
            db.query(Membership)
            .filter(Membership.club_id == other_club_id, Membership.user_id == db.query(User).filter(User.email == "demo.owner@svnit.ac.in").first().id)
            .first()
        )
        if not m_other:
            m_other = Membership(
                club_id=other_club_id,
                user_id=db.query(User).filter(User.email == "demo.owner@svnit.ac.in").first().id,
                role=Role.OWNER,
                status="active",
            )
            db.add(m_other)
            db.flush()

        db.commit()
    finally:
        db.close()

    # Login as viewer
    res_v = client.post(
        "/api/v1/auth/login",
        json={"email": "test.viewer@svnit.ac.in", "password": "ViewerPass123!"},
    )
    assert res_v.status_code == 200
    viewer_token = res_v.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    return {
        "acm_club_id": acm_club_id,
        "other_club_id": other_club_id,
        "owner_headers": owner_headers,
        "viewer_headers": viewer_headers,
    }


def test_gallery_listing_includes_system_templates(client, auth_setup):
    """Gallery lists system templates with numbering series, category, and read-only status."""
    club_id = auth_setup["acm_club_id"]
    headers = auth_setup["owner_headers"]

    res = client.get(f"/api/v1/clubs/{club_id}/documents/templates", headers=headers)
    assert res.status_code == 200, res.text
    templates = res.json()
    assert len(templates) >= 3

    # Check for expected system templates
    slugs = {t["slug"] for t in templates}
    assert "permission_letter" in slugs
    assert "approval_note" in slugs

    perm_tmpl = next(t for t in templates if t["slug"] == "permission_letter")
    assert perm_tmpl["is_system"] is True
    assert perm_tmpl["numbering_series"] == "ROOM"
    assert perm_tmpl["can_fork"] is True
    assert perm_tmpl["can_edit"] is False  # System templates are read-only
    assert "thumbnail_url" in perm_tmpl


def test_forking_creates_independent_copy(client, auth_setup):
    """Forking creates a draft copy in the club with its own template record, version, docx, and schema."""
    club_id = auth_setup["acm_club_id"]
    headers = auth_setup["owner_headers"]

    # List templates to get permission_letter ID
    res = client.get(f"/api/v1/clubs/{club_id}/documents/templates", headers=headers)
    templates = res.json()
    sys_tmpl = next(t for t in templates if t["slug"] == "permission_letter")

    # Fork it
    fork_res = client.post(
        f"/api/v1/clubs/{club_id}/documents/templates/{sys_tmpl['id']}/fork",
        headers=headers,
    )
    assert fork_res.status_code == 201, fork_res.text
    forked = fork_res.json()

    assert forked["is_system"] is False
    assert forked["status"] == "draft"
    assert forked["forked_from_template_id"] == sys_tmpl["id"]
    assert "(Custom)" in forked["name"]
    assert forked["can_edit"] is True
    assert forked["numbering_series"] == "ROOM"

    # Verify DB records
    from server.app.core.database import SessionLocal
    db = SessionLocal()
    try:
        tmpl_db = db.query(Template).filter(Template.id == forked["id"]).first()
        assert tmpl_db is not None
        assert tmpl_db.club_id == club_id
        assert tmpl_db.is_system is False
        assert tmpl_db.status == "draft"

        # Version 1 exists
        ver_db = db.query(TemplateVersion).filter(TemplateVersion.template_id == forked["id"]).first()
        assert ver_db is not None
        assert ver_db.version_no == 1

        # DOCX file exists on disk and is distinct from system template
        assert Path(ver_db.docx_storage_key).exists()
        sys_ver = db.query(TemplateVersion).filter(TemplateVersion.template_id == sys_tmpl["id"]).first()
        assert Path(ver_db.docx_storage_key).resolve() != Path(sys_ver.docx_storage_key).resolve()

        # Schema is populated
        assert ver_db.schema_yaml is not None
    finally:
        db.close()


def test_editing_fork_never_changes_system_template(client, auth_setup):
    """Editing the forked draft updates the fork while system template stays unchanged and read-only."""
    club_id = auth_setup["acm_club_id"]
    headers = auth_setup["owner_headers"]

    # 1. Fetch system template and forked template
    res = client.get(f"/api/v1/clubs/{club_id}/documents/templates", headers=headers)
    templates = res.json()
    sys_tmpl = next(t for t in templates if t["slug"] == "permission_letter" and t["is_system"])
    forked_tmpl = next(t for t in templates if not t["is_system"] and t["forked_from_template_id"] == sys_tmpl["id"])

    # 2. Direct edit on system template is rejected with 400 Bad Request
    sys_edit_res = client.put(
        f"/api/v1/clubs/{club_id}/documents/templates/{sys_tmpl['id']}",
        json={"name": "Hacked System Template"},
        headers=headers,
    )
    assert sys_edit_res.status_code in (400, 403)
    assert "System templates stay read-only" in sys_edit_res.text

    # 3. Edit the forked template
    fork_edit_res = client.put(
        f"/api/v1/clubs/{club_id}/documents/templates/{forked_tmpl['id']}",
        json={
            "name": "Custom ACM Room Permission Form",
            "description": "Tailored for CSE labs and seminar rooms.",
        },
        headers=headers,
    )
    assert fork_edit_res.status_code == 200, fork_edit_res.text
    updated_fork = fork_edit_res.json()
    assert updated_fork["name"] == "Custom ACM Room Permission Form"
    assert updated_fork["description"] == "Tailored for CSE labs and seminar rooms."

    # 4. Verify system template is completely untouched
    res_after = client.get(f"/api/v1/clubs/{club_id}/documents/templates", headers=headers)
    templates_after = res_after.json()
    sys_tmpl_after = next(t for t in templates_after if t["id"] == sys_tmpl["id"])
    assert sys_tmpl_after["name"] == sys_tmpl["name"]
    assert sys_tmpl_after["description"] == sys_tmpl["description"]


def test_viewers_cannot_fork(client, auth_setup):
    """Club viewers lack permissions to fork templates (must return 403 Forbidden)."""
    club_id = auth_setup["acm_club_id"]
    viewer_headers = auth_setup["viewer_headers"]

    # Fetch templates as viewer
    res = client.get(f"/api/v1/clubs/{club_id}/documents/templates", headers=viewer_headers)
    assert res.status_code == 200
    sys_tmpl = next(t for t in res.json() if t["slug"] == "permission_letter")

    # Viewer attempts to fork
    fork_res = client.post(
        f"/api/v1/clubs/{club_id}/documents/templates/{sys_tmpl['id']}/fork",
        headers=viewer_headers,
    )
    assert fork_res.status_code == 403, f"Expected 403 Forbidden for viewer, got {fork_res.status_code}: {fork_res.text}"


def test_another_club_cannot_see_the_fork(client, auth_setup):
    """A forked draft template belongs solely to the club that forked it."""
    acm_id = auth_setup["acm_club_id"]
    other_club_id = auth_setup["other_club_id"]
    owner_headers = auth_setup["owner_headers"]

    # Fetch ACM templates (has the fork)
    acm_tmpls = client.get(f"/api/v1/clubs/{acm_id}/documents/templates", headers=owner_headers).json()
    acm_fork_names = [t["name"] for t in acm_tmpls if not t["is_system"]]
    assert len(acm_fork_names) > 0

    # Fetch other club templates (must NOT have ACM's forked template)
    other_tmpls = client.get(f"/api/v1/clubs/{other_club_id}/documents/templates", headers=owner_headers).json()
    other_tmpl_names = [t["name"] for t in other_tmpls]

    for name in acm_fork_names:
        assert name not in other_tmpl_names, f"Fork '{name}' leaked to other club {other_club_id}!"


def test_thumbnail_generation_no_cache_returns_200_and_differs_between_templates(client, auth_setup):
    """Thumbnails with no cache return 200 PNG rendered via LibreOffice & PyMuPDF, and differ across templates."""
    club_id = auth_setup["acm_club_id"]
    headers = auth_setup["owner_headers"]
    from server.app.core.database import SessionLocal

    db = SessionLocal()
    try:
        perm = db.query(Template).filter(Template.slug == "permission_letter").first()
        appr = db.query(Template).filter(Template.slug == "approval_note").first()
        assert perm and appr
        perm_ver = (
            db.query(TemplateVersion)
            .filter(TemplateVersion.template_id == perm.id)
            .order_by(TemplateVersion.version_no.desc())
            .first()
        )
        appr_ver = (
            db.query(TemplateVersion)
            .filter(TemplateVersion.template_id == appr.id)
            .order_by(TemplateVersion.version_no.desc())
            .first()
        )
        assert perm_ver and appr_ver
    finally:
        db.close()

    # Delete cached thumbnails to guarantee fresh on-demand rendering
    perm_cache = Path("storage/thumbnails") / f"{perm_ver.id}.png"
    appr_cache = Path("storage/thumbnails") / f"{appr_ver.id}.png"
    if perm_cache.exists():
        perm_cache.unlink()
    if appr_cache.exists():
        appr_cache.unlink()

    # Request thumbnail for permission_letter
    res1 = client.get(f"/api/v1/clubs/{club_id}/documents/templates/{perm.id}/thumbnail", headers=headers)
    assert res1.status_code == 200, f"Expected 200 PNG, got {res1.status_code}: {res1.text}"
    assert res1.headers["content-type"] == "image/png"
    assert res1.content.startswith(b"\x89PNG\r\n\x1a\n"), "Response is not a valid PNG header"
    assert perm_cache.exists(), "Rendered thumbnail was not cached under template version ID"

    # Request thumbnail for approval_note
    res2 = client.get(f"/api/v1/clubs/{club_id}/documents/templates/{appr.id}/thumbnail", headers=headers)
    assert res2.status_code == 200, f"Expected 200 PNG, got {res2.status_code}: {res2.text}"
    assert res2.headers["content-type"] == "image/png"
    assert res2.content.startswith(b"\x89PNG\r\n\x1a\n"), "Response is not a valid PNG header"
    assert appr_cache.exists(), "Rendered thumbnail was not cached under template version ID"

    # Assert PNG bytes differ between distinct templates
    assert res1.content != res2.content, "Thumbnails for two distinct templates must have different PNG bytes!"


def test_no_server_reference_to_tests_visual_or_sample_docs():
    """Server code must never reference tests/visual or 'sample docs'."""
    server_dir = Path("server")
    violations = []
    for py_file in server_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        if "tests/visual" in content or "tests\\visual" in content:
            violations.append(f"{py_file.as_posix()}: references tests/visual")
        if "sample docs" in content.lower():
            violations.append(f"{py_file.as_posix()}: references 'sample docs'")

    assert not violations, (
        "Server code must never reference tests/visual or 'sample docs':\n"
        + "\n".join(violations)
    )


def test_duplicate_forks_get_unique_names(client, auth_setup):
    """Duplicate forks of the same template get unique names ('... (Custom)', '... (Custom 2)', etc.)."""
    club_id = auth_setup["acm_club_id"]
    headers = auth_setup["owner_headers"]

    # Get bill_summary template
    res = client.get(f"/api/v1/clubs/{club_id}/documents/templates", headers=headers)
    templates = res.json()
    bill_tmpl = next(t for t in templates if t["slug"] == "bill_summary" and t["is_system"])

    # 1. First fork
    f1 = client.post(
        f"/api/v1/clubs/{club_id}/documents/templates/{bill_tmpl['id']}/fork",
        headers=headers,
    )
    assert f1.status_code == 201
    f1_data = f1.json()
    assert f1_data["name"] == f"{bill_tmpl['name']} (Custom)"

    # 2. Second duplicate fork of same template
    f2 = client.post(
        f"/api/v1/clubs/{club_id}/documents/templates/{bill_tmpl['id']}/fork",
        headers=headers,
    )
    assert f2.status_code == 201
    f2_data = f2.json()
    assert f2_data["name"] == f"{bill_tmpl['name']} (Custom 2)"

    # 3. Third duplicate fork of same template
    f3 = client.post(
        f"/api/v1/clubs/{club_id}/documents/templates/{bill_tmpl['id']}/fork",
        headers=headers,
    )
    assert f3.status_code == 201
    f3_data = f3.json()
    assert f3_data["name"] == f"{bill_tmpl['name']} (Custom 3)"

    assert len({f1_data["name"], f2_data["name"], f3_data["name"]}) == 3


def test_rename_and_archive_permissions_and_viewer_rejected(client, auth_setup):
    """Rename and Archive/Delete are restricted to admins/editors, reject viewers, and keep system templates read-only."""
    club_id = auth_setup["acm_club_id"]
    owner_headers = auth_setup["owner_headers"]
    viewer_headers = auth_setup["viewer_headers"]

    # 1. Fetch system template and create a draft fork to test on
    res = client.get(f"/api/v1/clubs/{club_id}/documents/templates", headers=owner_headers)
    mom_tmpl = next(t for t in res.json() if t["slug"] == "mom" and t["is_system"])

    fork_res = client.post(
        f"/api/v1/clubs/{club_id}/documents/templates/{mom_tmpl['id']}/fork",
        headers=owner_headers,
    )
    assert fork_res.status_code == 201
    draft_tmpl = fork_res.json()

    # 2. Viewer attempts to rename -> 403 Forbidden
    v_rename = client.put(
        f"/api/v1/clubs/{club_id}/documents/templates/{draft_tmpl['id']}",
        json={"name": "Hacked Name by Viewer"},
        headers=viewer_headers,
    )
    assert v_rename.status_code == 403

    # 3. Viewer attempts to archive/delete -> 403 Forbidden
    v_delete = client.delete(
        f"/api/v1/clubs/{club_id}/documents/templates/{draft_tmpl['id']}",
        headers=viewer_headers,
    )
    assert v_delete.status_code == 403

    # 4. System template rename rejected (read-only) -> 403 Forbidden
    sys_rename = client.put(
        f"/api/v1/clubs/{club_id}/documents/templates/{mom_tmpl['id']}",
        json={"name": "Altered System MoM"},
        headers=owner_headers,
    )
    assert sys_rename.status_code == 403

    # 5. System template archive/delete rejected (read-only) -> 403 Forbidden
    sys_delete = client.delete(
        f"/api/v1/clubs/{club_id}/documents/templates/{mom_tmpl['id']}",
        headers=owner_headers,
    )
    assert sys_delete.status_code == 403

    # 6. Editor/Owner renames the draft -> 200 OK
    rename_res = client.put(
        f"/api/v1/clubs/{club_id}/documents/templates/{draft_tmpl['id']}",
        json={"name": "Executive Board Meeting Minutes (Custom)"},
        headers=owner_headers,
    )
    assert rename_res.status_code == 200
    assert rename_res.json()["name"] == "Executive Board Meeting Minutes (Custom)"

    # 7. Editor/Owner archives the draft -> 204 No Content
    delete_res = client.delete(
        f"/api/v1/clubs/{club_id}/documents/templates/{draft_tmpl['id']}",
        headers=owner_headers,
    )
    assert delete_res.status_code == 204

    # 8. Archived draft is hidden from the active gallery listing
    gallery_res = client.get(f"/api/v1/clubs/{club_id}/documents/templates", headers=owner_headers)
    gallery_ids = [t["id"] for t in gallery_res.json()]
    assert draft_tmpl["id"] not in gallery_ids, "Archived draft should not appear in active gallery!"
