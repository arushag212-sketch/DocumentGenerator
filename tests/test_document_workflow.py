"""Review/edit/regenerate, approval with verification, email, event-driven regeneration."""

from __future__ import annotations

import pymupdf
import pytest
from fastapi.testclient import TestClient

from server.app.core import email as email_module
from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def setup(client: TestClient):
    clear_rate_limits()
    login = client.post("/api/v1/auth/login", json={"email": "demo.owner@svnit.ac.in", "password": "DemoOwnerPass123!"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    acm = next(c for c in client.get("/api/v1/clubs/search?q=", headers=headers).json() if c["slug"] == "acm")
    payload = {
        "selected_template_ids": ["permission_letter"],
        "event_data": {
            "event_name": "Workflow Test Workshop",
            "venue": "Seminar Hall",
            "participants": 80,
            "date_start": "2026-11-04",
            "date_end": "2026-11-04",
            "time_start": "10:00",
            "time_end": "13:00",
            "submitted_to": "Head of Department",
            "description": "A short workshop.",
            "objectives": "Learn the basics.",
        },
        "ref_numbers_accepted": True,
        "event_title": "Workflow Test Workshop",
    }
    gen = client.post(f"/api/v1/clubs/{acm['id']}/home/generate", json=payload, headers=headers)
    assert gen.status_code == 200, gen.text
    doc = gen.json()["documents"][0]
    return {"headers": headers, "club_id": acm["id"], "doc_id": doc["id"], "event_id": gen.json()["event_id"]}


def _pdf_text(client, url, headers) -> str:
    res = client.get(url, headers=headers)
    assert res.status_code == 200
    return "".join(p.get_text() for p in pymupdf.open(stream=res.content, filetype="pdf"))


def test_edit_regenerate_review_approve_and_verify(client: TestClient, setup):
    h, club, doc_id = setup["headers"], setup["club_id"], setup["doc_id"]
    base = f"/api/v1/clubs/{club}/documents/{doc_id}"

    detail = client.get(base, headers=h).json()
    keys = {f["key"] for f in detail["editable_fields"]}
    assert "venue" in keys and detail["can_review"] is True
    ref_no = detail["ref_no"]

    # Edit a value -> new version, same reference number, change recorded
    rev = client.post(f"{base}/revise", json={"changes": {"venue": "Lecture Hall 3"}}, headers=h)
    assert rev.status_code == 200, rev.text
    assert rev.json()["version_no"] == 2
    detail = client.get(base, headers=h).json()
    assert detail["ref_no"] == ref_no and detail["current_version_no"] == 2
    assert "Lecture Hall 3" in _pdf_text(client, detail["pdf_url"], h)
    assert "venue" in (detail["versions"][0]["change_summary"] or "")

    # Unknown fields are rejected
    assert client.post(f"{base}/revise", json={"changes": {"bogus": "x"}}, headers=h).status_code == 400

    # Cannot approve before submission
    assert client.post(f"{base}/approve", json={}, headers=h).status_code == 409

    assert client.post(f"{base}/submit", json={"comment": "Please review"}, headers=h).json()["status"] == "submitted"
    assert client.post(f"{base}/request-changes", json={"comment": "Fix the time"}, headers=h).json()["status"] == "changes_requested"
    client.post(f"{base}/revise", json={"changes": {"venue": "Lecture Hall 4"}}, headers=h)
    client.post(f"{base}/submit", json={}, headers=h)
    approved = client.post(f"{base}/approve", json={"comment": "OK"}, headers=h)
    assert approved.status_code == 200, approved.text
    code = approved.json()["verification_code"]

    # The approved PDF carries the stamp and verifies publicly
    pdf_res = client.get(f"{base}/download?format=pdf", headers=h)
    assert code in "".join(p.get_text() for p in pymupdf.open(stream=pdf_res.content, filetype="pdf"))
    public = client.get(f"/api/v1/verify/{code}")
    assert public.status_code == 200 and public.json()["ref_no"] == ref_no
    match = client.post(f"/api/v1/verify/{code}", files={"file": ("doc.pdf", pdf_res.content, "application/pdf")})
    assert match.json()["file_matches"] is True
    tampered = client.post(f"/api/v1/verify/{code}", files={"file": ("doc.pdf", pdf_res.content + b"x", "application/pdf")})
    assert tampered.json()["file_matches"] is False
    assert client.get("/api/v1/verify/NOPE-NOPE").status_code == 404

    actions = [a["action"] for a in client.get(base, headers=h).json()["activity"]]
    for expected in ("revised", "submitted", "changes_requested", "approved"):
        assert expected in actions


def test_email_document(client: TestClient, setup, monkeypatch):
    sender = email_module.ConsoleEmailSender()
    monkeypatch.setattr(email_module, "_default_sender", sender)
    base = f"/api/v1/clubs/{setup['club_id']}/documents/{setup['doc_id']}"
    res = client.post(f"{base}/email", json={"to": ["hod@example.com"], "attach": "both"}, headers=setup["headers"])
    assert res.status_code == 200, res.text
    assert sender.sent_messages and ".pdf" in sender.sent_messages[-1]["attachments"]
    assert ".docx" in sender.sent_messages[-1]["attachments"]
    bad = client.post(f"{base}/email", json={"to": ["not-an-email"]}, headers=setup["headers"])
    assert bad.status_code == 400


def test_event_change_regenerates_documents(client: TestClient, setup):
    h, club = setup["headers"], setup["club_id"]
    upd = client.put(f"/api/v1/clubs/{club}/events/{setup['event_id']}", json={"record": {"venue": "Auditorium"}}, headers=h)
    assert upd.status_code == 200, upd.text
    res = client.post(f"/api/v1/clubs/{club}/events/{setup['event_id']}/regenerate", headers=h)
    assert res.status_code == 200, res.text
    assert [u["id"] for u in res.json()["updated"]] == [setup["doc_id"]]
    detail = client.get(f"/api/v1/clubs/{club}/documents/{setup['doc_id']}", headers=h).json()
    assert "Auditorium" in _pdf_text(client, detail["pdf_url"], h)
