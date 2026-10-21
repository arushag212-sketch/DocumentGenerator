"""Tests for POST /api/v1/clubs/{club_id}/numbering (creating numbering series)."""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _setup_club_with_owner(client: TestClient) -> tuple[dict, str]:
    clear_rate_limits()
    suffix = uuid.uuid4().hex[:8]
    email = f"num_owner_{suffix}@svnit.ac.in"
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "name": f"Owner {suffix}",
        },
    )
    assert res.status_code == 201, res.text
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    club_res = client.post(
        "/api/v1/clubs",
        headers=headers,
        json={
            "name": f"Numbering Test Club {suffix}",
            "short_name": f"NTC{suffix[:3]}".upper(),
            "position": "Student Head/Chairperson",
            "is_signatory": True,
        },
    )
    assert club_res.status_code == 201, club_res.text
    club_id = club_res.json()["id"]
    return headers, club_id


def test_create_numbering_series_success_and_list(client: TestClient):
    """Admin creates a series, lists it, and verifies it exists."""
    headers, club_id = _setup_club_with_owner(client)

    payload = {
        "key": "CIRCULAR",
        "format": "{club}/{yy}-{next}/CIR/{seq:03d}",
        "academic_year": "2026-27",
        "last_seq": 10,
    }

    create_res = client.post(f"/api/v1/clubs/{club_id}/numbering", headers=headers, json=payload)
    assert create_res.status_code == 201, create_res.text
    created = create_res.json()

    assert created["key"] == "CIRCULAR"
    assert created["format"] == "{club}/{yy}-{next}/CIR/{seq:03d}"
    assert created["academic_year"] == "2026-27"
    assert created["last_seq"] == 10
    assert "id" in created

    # List series and verify created series is present
    list_res = client.get(f"/api/v1/clubs/{club_id}/numbering", headers=headers)
    assert list_res.status_code == 200
    series_list = list_res.json()
    found = next((s for s in series_list if s["key"] == "CIRCULAR" and s["academic_year"] == "2026-27"), None)
    assert found is not None
    assert found["format"] == "{club}/{yy}-{next}/CIR/{seq:03d}"
    assert found["last_seq"] == 10


def test_create_duplicate_numbering_series_returns_400(client: TestClient):
    """Creating a duplicate series with the same key and academic_year returns 400 SERIES_EXISTS."""
    headers, club_id = _setup_club_with_owner(client)

    payload = {
        "key": "DISPATCH",
        "format": "{club}/{yy}-{next}/DSP/{seq:03d}",
        "academic_year": "2026-27",
        "last_seq": 0,
    }

    first_res = client.post(f"/api/v1/clubs/{club_id}/numbering", headers=headers, json=payload)
    assert first_res.status_code == 201

    # Attempt to create exact duplicate key and academic year
    dup_res = client.post(f"/api/v1/clubs/{club_id}/numbering", headers=headers, json=payload)
    assert dup_res.status_code == 400
    detail = dup_res.json().get("detail", {})
    assert detail.get("code") == "SERIES_EXISTS"
    assert "already exists for academic year" in detail.get("message", "")


def test_create_numbering_series_requires_admin(client: TestClient):
    """Non-admin member cannot create numbering series (403 Forbidden)."""
    owner_headers, club_id = _setup_club_with_owner(client)

    # Register member and join as viewer
    member_email = f"viewer_{uuid.uuid4().hex[:6]}@svnit.ac.in"
    m_reg = client.post(
        "/api/v1/auth/register",
        json={"email": member_email, "password": "Password123!", "name": "Test Viewer"},
    )
    member_headers = {"Authorization": f"Bearer {m_reg.json()['access_token']}"}

    jr = client.post(
        f"/api/v1/clubs/{club_id}/join-requests",
        headers=member_headers,
        json={"position": "Member", "requested_role": "viewer"},
    )
    assert jr.status_code == 201
    req_id = jr.json()["id"]

    # Approve as viewer
    app_res = client.post(
        f"/api/v1/clubs/{club_id}/join-requests/{req_id}/approve",
        headers=owner_headers,
        json={"role": "viewer"},
    )
    assert app_res.status_code == 200

    # Viewer attempts to create series -> 403
    forbidden_res = client.post(
        f"/api/v1/clubs/{club_id}/numbering",
        headers=member_headers,
        json={"key": "VIEWER_SERIES", "format": "{club}/{seq:03d}", "academic_year": "2026-27"},
    )
    assert forbidden_res.status_code == 403
