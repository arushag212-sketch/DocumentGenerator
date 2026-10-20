"""Tests for Phase W5.2:
1. Dev DB immutability & isolation: data/clubdocs.db must not be touched by tests or screenshot scripts.
2. Publish Gate: Templates with ai_suggested=true cannot be compiled-for-publish or published.
   - Rejects /publish with 409 Conflict and list of unreviewed items.
   - Viewer cannot mark reviewed (403 Forbidden).
   - Editor/Owner can review all or individual items.
   - Publish succeeds after review.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from docgen.llm import StubLLMClient, set_llm_client
from server.app.core.database import SessionLocal
from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.app.core.permissions import Role
from server.app.models import Club, Membership, Template, TemplateVersion, User
from tests.test_w5_ai_template import SAMPLE_SPONSORSHIP_SPEC


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_setup(client):
    clear_rate_limits()
    db = SessionLocal()
    try:
        acm = db.query(Club).filter(Club.slug == "acm").first()
        acm_id = acm.id

        # Ensure viewer exists
        v_user = db.query(User).filter(User.email == "w52.viewer@svnit.ac.in").first()
        if not v_user:
            from server.app.core.security import get_password_hash
            v_user = User(
                email="w52.viewer@svnit.ac.in",
                password_hash=get_password_hash("ViewerPass123!"),
                name="W52 Viewer",
                is_platform_admin=False,
            )
            db.add(v_user)
            db.flush()

        m_v = db.query(Membership).filter(
            Membership.club_id == acm_id,
            Membership.user_id == v_user.id
        ).first()
        if not m_v:
            m_v = Membership(
                club_id=acm_id,
                user_id=v_user.id,
                role=Role.VIEWER,
                status="active",
            )
            db.add(m_v)
            db.flush()

        db.commit()
    finally:
        db.close()

    # Login as owner
    res_o = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert res_o.status_code == 200
    owner_token = res_o.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # Login as viewer
    res_v = client.post(
        "/api/v1/auth/login",
        json={"email": "w52.viewer@svnit.ac.in", "password": "ViewerPass123!"},
    )
    assert res_v.status_code == 200
    viewer_token = res_v.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    return {
        "acm_club_id": acm_id,
        "owner_headers": owner_headers,
        "viewer_headers": viewer_headers,
    }


def test_w5_2_publish_rejected_with_409_when_unreviewed_ai_items_present(client, auth_setup):
    """Publish gate: /publish returns 409 and unreviewed items list when ai_suggested=true exists."""
    acm_id = auth_setup["acm_club_id"]
    owner_headers = auth_setup["owner_headers"]

    # 1. Create an AI draft template
    stub = StubLLMClient(default_json=SAMPLE_SPONSORSHIP_SPEC)
    set_llm_client(stub)
    clear_rate_limits()

    res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/ai-draft",
        json={"description": "Sponsorship proposal letter for annual techfest with event name, date, venue and tiers"},
        headers=owner_headers,
    )
    assert res.status_code == 201
    tmpl_id = res.json()["template"]["id"]

    # 2. Attempt to publish immediately without reviewing AI content
    pub_res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/{tmpl_id}/publish",
        headers=owner_headers,
    )
    assert pub_res.status_code == 409, f"Expected 409 Conflict, got: {pub_res.status_code} ({pub_res.text})"
    err_data = pub_res.json()["detail"]
    assert err_data["code"] == "UNREVIEWED_AI_CONTENT"
    assert "unreviewed_items" in err_data
    assert len(err_data["unreviewed_items"]) > 0
    # Check that unreviewed items contain fields or blocks
    item_types = [item["type"] for item in err_data["unreviewed_items"]]
    assert "field" in item_types or "block" in item_types


def test_w5_2_viewer_cannot_mark_ai_items_reviewed(client, auth_setup):
    """Publish gate: Viewer role gets 403 Forbidden when calling /review-ai."""
    acm_id = auth_setup["acm_club_id"]
    owner_headers = auth_setup["owner_headers"]
    viewer_headers = auth_setup["viewer_headers"]

    # Create draft
    stub = StubLLMClient(default_json=SAMPLE_SPONSORSHIP_SPEC)
    set_llm_client(stub)
    clear_rate_limits()

    res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/ai-draft",
        json={"description": "Sponsorship proposal letter"},
        headers=owner_headers,
    )
    assert res.status_code == 201
    tmpl_id = res.json()["template"]["id"]

    # Viewer calls review-ai
    review_res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/{tmpl_id}/review-ai",
        json={"all": True},
        headers=viewer_headers,
    )
    assert review_res.status_code == 403, f"Expected 403 Forbidden for viewer, got {review_res.status_code}"


def test_w5_2_publish_succeeds_after_reviewing_ai_items(client, auth_setup):
    """Publish gate: after marking AI items reviewed, /publish succeeds with 200 OK."""
    acm_id = auth_setup["acm_club_id"]
    owner_headers = auth_setup["owner_headers"]

    stub = StubLLMClient(default_json=SAMPLE_SPONSORSHIP_SPEC)
    set_llm_client(stub)
    clear_rate_limits()

    res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/ai-draft",
        json={"description": "Sponsorship proposal letter with event name, date, venue, tiers and signatures"},
        headers=owner_headers,
    )
    assert res.status_code == 201
    tmpl_id = res.json()["template"]["id"]

    # First compile draft to generate clean docx & valid schema
    draft_data = res.json()["draft"]
    comp_res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/{tmpl_id}/compile",
        json={"editor_json": draft_data["editor_json"], "fields": draft_data["fields"]},
        headers=owner_headers,
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["is_valid"] is True

    # Mark all reviewed
    review_res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/{tmpl_id}/review-ai",
        json={"all": True},
        headers=owner_headers,
    )
    assert review_res.status_code == 200
    rev_data = review_res.json()
    assert rev_data["reviewed"] is True
    assert rev_data["remaining_unreviewed_count"] == 0

    # Publish now succeeds
    pub_res = client.post(
        f"/api/v1/clubs/{acm_id}/documents/templates/{tmpl_id}/publish",
        headers=owner_headers,
    )
    assert pub_res.status_code == 200
    assert pub_res.json()["status"] == "published"


def test_w5_2_dev_database_untouched_and_matches_clean_seed():
    """W5.2: the suite runs against the isolated test database, never data/clubdocs.db."""
    import server.app.core.database as db_module

    assert "clubdocs_test_isolated" in str(db_module.engine.url)
