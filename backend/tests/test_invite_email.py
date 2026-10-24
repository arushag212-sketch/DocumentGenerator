"""Emailing invite links: sent with the full link, locked to that address, and honest when email is off or fails."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.core import email as email_module
from server.app.core.database import SessionLocal
from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.app.models import Club, Membership


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _register(client, name):
    clear_rate_limits()
    email = f"{name}_{uuid.uuid4().hex[:8]}@svnit.ac.in"
    res = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "name": name.title()})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}, res.json()["user"]["id"], email


@pytest.fixture
def club(client):
    admin_h, admin_id, _ = _register(client, "inviter")
    with SessionLocal() as db:
        c = Club(name=f"Invite Club {uuid.uuid4().hex[:4]}", short_name="INV", slug=f"inv-{uuid.uuid4().hex[:6]}", settings={})
        db.add(c)
        db.flush()
        db.add(Membership(user_id=admin_id, club_id=c.id, role="owner", status="active", position="Student Head/Chairperson"))
        db.commit()
        return {"id": c.id, "name": c.name, "admin": admin_h}


def test_invite_is_emailed_with_link_and_only_that_address_can_use_it(client, club, monkeypatch):
    sender = email_module.ConsoleEmailSender()
    monkeypatch.setattr(email_module, "_default_sender", sender)
    monkeypatch.setattr(email_module, "email_delivery_configured", lambda: True)
    monkeypatch.setenv("APP_BASE_URL", "https://clubdocs.example")
    invitee_h, _, invitee_email = _register(client, "invitee")
    other_h, _, _ = _register(client, "other")

    res = client.post(f"/api/v1/clubs/{club['id']}/invites", headers=club["admin"],
                      json={"role": "viewer", "expiry_days": 3, "email": invitee_email})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["emailed"] is True and body["email_error"] is None

    sent = [m for m in sender.sent_messages if m.get("type") == "invitation"]
    assert len(sent) == 1 and sent[0]["to_email"] == invitee_email
    assert sent[0]["link"] == f"https://clubdocs.example/login?invite={body['code']}"
    assert "invited you as viewer" in sent[0]["details"] and "works until" in sent[0]["details"]

    clear_rate_limits()
    assert client.post(f"/api/v1/invites/{body['code']}/accept", headers=other_h).status_code >= 400
    clear_rate_limits()
    assert client.post(f"/api/v1/invites/{body['code']}/accept", headers=invitee_h).status_code == 200


def test_no_email_when_email_is_not_set_up(client, club, monkeypatch):
    monkeypatch.setattr(email_module, "email_delivery_configured", lambda: False)
    res = client.post(f"/api/v1/clubs/{club['id']}/invites", headers=club["admin"],
                      json={"role": "editor", "email": "someone@svnit.ac.in"})
    assert res.status_code == 201
    assert res.json()["emailed"] is False and "not set up" in res.json()["email_error"]


def test_failed_email_still_creates_the_invite(client, club, monkeypatch):
    class Broken(email_module.ConsoleEmailSender):
        def send_invitation(self, *a, **k):
            raise RuntimeError("smtp down")

    monkeypatch.setattr(email_module, "_default_sender", Broken())
    monkeypatch.setattr(email_module, "email_delivery_configured", lambda: True)
    res = client.post(f"/api/v1/clubs/{club['id']}/invites", headers=club["admin"],
                      json={"role": "editor", "email": "someone@svnit.ac.in"})
    assert res.status_code == 201 and res.json()["code"]
    assert res.json()["emailed"] is False and "could not be sent" in res.json()["email_error"]


def test_link_only_invite_has_no_email_fields(client, club):
    res = client.post(f"/api/v1/clubs/{club['id']}/invites", headers=club["admin"], json={"role": "editor"})
    assert res.status_code == 201 and res.json()["emailed"] is None
