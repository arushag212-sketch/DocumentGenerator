"""Join requests carry the access level the applicant asks for; admins grant it (or override) on approval."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.core.rate_limit import clear_rate_limits


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def owner_and_club(client: TestClient):
    clear_rate_limits()
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"},
    )
    assert res.status_code == 200, res.text
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    clubs = client.get("/api/v1/clubs/search?q=", headers=headers).json()
    acm = next(c for c in clubs if c["slug"] == "acm")
    return headers, acm["id"]


def _new_applicant(client: TestClient) -> dict:
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"applicant_{uuid.uuid4().hex[:8]}@svnit.ac.in",
            "password": "ApplicantPass123!",
            "name": "Applicant Test",
        },
    )
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_requested_role_is_granted_by_default(client: TestClient, owner_and_club):
    owner_headers, club_id = owner_and_club
    applicant = _new_applicant(client)

    jr = client.post(
        f"/api/v1/clubs/{club_id}/join-requests",
        json={"position": "Secretary", "requested_role": "viewer", "message": "Need to read past letters"},
        headers=applicant,
    )
    assert jr.status_code == 201, jr.text
    body = jr.json()
    assert body["requested_role"] == "viewer"
    assert body["message"] == "Need to read past letters"

    # Pending applicants have no club permissions yet
    assert client.get(f"/api/v1/clubs/{club_id}/permissions", headers=applicant).status_code == 403

    listed = client.get(f"/api/v1/clubs/{club_id}/join-requests?status=pending", headers=owner_headers).json()
    assert any(r["id"] == body["id"] and r["requested_role"] == "viewer" for r in listed)

    # Approve without specifying a role -> requested role is granted
    ok = client.post(f"/api/v1/clubs/{club_id}/join-requests/{body['id']}/approve", json={}, headers=owner_headers)
    assert ok.status_code == 200, ok.text

    perms = client.get(f"/api/v1/clubs/{club_id}/permissions", headers=applicant).json()
    assert perms["role"] == "viewer"
    assert perms["can_create_documents"] is False


def test_admin_can_override_requested_role(client: TestClient, owner_and_club):
    owner_headers, club_id = owner_and_club
    applicant = _new_applicant(client)

    jr = client.post(
        f"/api/v1/clubs/{club_id}/join-requests",
        json={"position": "Treasurer", "requested_role": "viewer"},
        headers=applicant,
    ).json()
    ok = client.post(
        f"/api/v1/clubs/{club_id}/join-requests/{jr['id']}/approve",
        json={"role": "editor"},
        headers=owner_headers,
    )
    assert ok.status_code == 200, ok.text

    perms = client.get(f"/api/v1/clubs/{club_id}/permissions", headers=applicant).json()
    assert perms["role"] == "editor"
    assert perms["can_create_documents"] is True


def test_applicant_cannot_request_admin_and_defaults_to_editor(client: TestClient, owner_and_club):
    _, club_id = owner_and_club
    applicant = _new_applicant(client)

    bad = client.post(
        f"/api/v1/clubs/{club_id}/join-requests",
        json={"position": "Secretary", "requested_role": "admin"},
        headers=applicant,
    )
    assert bad.status_code == 422

    default = client.post(
        f"/api/v1/clubs/{club_id}/join-requests",
        json={"position": "Secretary"},
        headers=applicant,
    )
    assert default.status_code == 201
    assert default.json()["requested_role"] == "editor"


def test_applicant_can_withdraw_pending_request(client: TestClient, owner_and_club):
    _, club_id = owner_and_club
    applicant = _new_applicant(client)

    jr = client.post(
        f"/api/v1/clubs/{club_id}/join-requests",
        json={"position": "Secretary"},
        headers=applicant,
    ).json()
    res = client.post(f"/api/v1/clubs/{club_id}/join-requests/{jr['id']}/cancel", headers=applicant)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "cancelled"

    mine = client.get(f"/api/v1/clubs/{club_id}/join-requests/my", headers=applicant).json()
    assert mine["status"] == "cancelled"
