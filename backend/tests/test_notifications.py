"""Notifications: review requested -> club admins; approved / changes requested -> the creator; bell API."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.core import email as email_module
from server.app.core.database import SessionLocal
from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.app.models import Club, Membership, Notification, User


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _register(client, name):
    clear_rate_limits()
    email = f"{name}_{uuid.uuid4().hex[:8]}@svnit.ac.in"
    res = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "name": name.title()})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}, res.json()["user"]["id"]


@pytest.fixture
def setup(client, monkeypatch):
    sender = email_module.ConsoleEmailSender()
    monkeypatch.setattr(email_module, "_default_sender", sender)
    monkeypatch.setattr(email_module, "email_delivery_configured", lambda: True)
    admin_h, admin_id = _register(client, "admin")
    editor_h, editor_id = _register(client, "editor")
    with SessionLocal() as db:
        club = Club(name=f"Notify Club {uuid.uuid4().hex[:4]}", short_name="NTF", slug=f"ntf-{uuid.uuid4().hex[:6]}", settings={})
        db.add(club)
        db.flush()
        db.add(Membership(user_id=admin_id, club_id=club.id, role="owner", status="active", position="Student Head/Chairperson"))
        db.add(Membership(user_id=editor_id, club_id=club.id, role="editor", status="active", position="Member"))
        db.commit()
        club_id = club.id
    clear_rate_limits()
    gen = client.post(f"/api/v1/clubs/{club_id}/home/generate", headers=editor_h, json={
        "selected_template_ids": ["permission_letter"],
        "event_data": {"event_name": "Notify Workshop", "venue": "Hall", "participants": 10, "date_start": "2026-12-01",
                       "date_end": "2026-12-01", "time_start": "10:00", "time_end": "11:00", "submitted_to": "HoD",
                       "description": "x", "objectives": "y"},
        "ref_numbers_accepted": True, "event_title": "Notify Workshop",
    })
    assert gen.status_code == 200, gen.text
    doc_id = gen.json()["documents"][0]["id"]
    return {"admin": admin_h, "editor": editor_h, "club": club_id, "doc": doc_id, "sender": sender,
            "base": f"/api/v1/clubs/{club_id}/documents/{doc_id}"}


def test_submit_notifies_admins_and_approve_notifies_creator(client, setup):
    s = setup
    assert client.post(f"{s['base']}/submit", json={"comment": "please check"}, headers=s["editor"]).status_code == 200
    bell = client.get("/api/v1/notifications", headers=s["admin"]).json()
    assert bell["unread"] >= 1
    assert bell["items"][0]["kind"] == "review_requested" and s["doc"] in bell["items"][0]["link"]
    assert any(m.get("type") == "notification" for m in s["sender"].sent_messages)

    assert client.post(f"{s['base']}/approve", json={"comment": "ok"}, headers=s["admin"]).status_code == 200
    mine = client.get("/api/v1/notifications", headers=s["editor"]).json()
    assert mine["items"][0]["kind"] == "approved"


def test_changes_requested_notifies_creator(client, setup):
    s = setup
    client.post(f"{s['base']}/submit", json={}, headers=s["editor"])
    res = client.post(f"{s['base']}/request-changes", json={"comment": "fix the date"}, headers=s["admin"])
    assert res.status_code == 200, res.text
    mine = client.get("/api/v1/notifications", headers=s["editor"]).json()
    assert mine["items"][0]["kind"] == "changes_requested" and "fix the date" in mine["items"][0]["body"]


def test_mark_read_and_privacy(client, setup):
    s = setup
    client.post(f"{s['base']}/submit", json={}, headers=s["editor"])
    items = client.get("/api/v1/notifications", headers=s["admin"]).json()["items"]
    nid = items[0]["id"]
    # someone else can't read or mark another user's notification
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=s["editor"]).status_code == 404
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=s["admin"]).json()["read"] is True
    client.post("/api/v1/notifications/read-all", headers=s["admin"])
    assert client.get("/api/v1/notifications", headers=s["admin"]).json()["unread"] == 0
