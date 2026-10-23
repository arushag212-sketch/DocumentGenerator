"""Document Trash: delete, hidden everywhere, restore, purge after 30 days, cancel approved, verify."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from server.app.core.database import SessionLocal
from server.app.core.rate_limit import clear_rate_limits
from server.app.main import app
from server.app.models import Document


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _login(client, email, password):
    clear_rate_limits()
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def setup(client: TestClient):
    h = _login(client, "demo.owner@svnit.ac.in", "DemoOwnerPass123!")
    acm = next(c for c in client.get("/api/v1/clubs/search?q=", headers=h).json() if c["slug"] == "acm")
    payload = {
        "selected_template_ids": ["permission_letter"],
        "event_data": {
            "event_name": "Trash Test Workshop", "venue": "Seminar Hall", "participants": 40,
            "date_start": "2026-12-04", "date_end": "2026-12-04", "time_start": "10:00", "time_end": "12:00",
            "submitted_to": "Head of Department", "description": "Trash test.", "objectives": "Testing.",
        },
        "ref_numbers_accepted": True,
        "event_title": "Trash Test Workshop",
    }
    gen = client.post(f"/api/v1/clubs/{acm['id']}/home/generate", json=payload, headers=h)
    assert gen.status_code == 200, gen.text
    doc_id = gen.json()["documents"][0]["id"]
    base = f"/api/v1/clubs/{acm['id']}/documents"
    return {"h": h, "club": acm["id"], "doc": doc_id, "base": base}


def _list_ids(client, s):
    res = client.get(s["base"], headers=s["h"], params={"page_size": 50, "q": "Trash Test"})
    assert res.status_code == 200, res.text
    return {d["id"] for d in res.json()["items"]}


def test_delete_hides_everywhere_and_restore_brings_back(client, setup):
    s = setup
    assert s["doc"] in _list_ids(client, s)
    res = client.delete(f"{s['base']}/{s['doc']}", headers=s["h"])
    assert res.status_code == 200, res.text
    assert res.json()["purge_on"]
    assert s["doc"] not in _list_ids(client, s)
    assert client.get(f"{s['base']}/{s['doc']}", headers=s["h"]).status_code == 404
    trash = client.get(f"{s['base']}/trash", headers=s["h"]).json()
    row = next(t for t in trash if t["id"] == s["doc"])
    assert row["can_restore"] and not row["cancelled"] and row["purge_on"]
    assert client.post(f"{s['base']}/{s['doc']}/restore", headers=s["h"]).status_code == 200
    assert s["doc"] in _list_ids(client, s)
    assert client.get(f"{s['base']}/{s['doc']}", headers=s["h"]).status_code == 200


def test_deleted_document_code_reports_deleted(client, setup):
    s = setup
    code = client.get(f"{s['base']}/{s['doc']}", headers=s["h"]).json()["verification_code"]
    assert client.get(f"/api/v1/verify/{code}").json()["valid"] is True
    client.delete(f"{s['base']}/{s['doc']}", headers=s["h"])
    body = client.get(f"/api/v1/verify/{code}").json()
    assert body["valid"] is False and body["status"] == "deleted"


def test_approved_cannot_be_deleted_but_can_be_cancelled(client, setup):
    s = setup
    doc = f"{s['base']}/{s['doc']}"
    client.post(f"{doc}/submit", json={}, headers=s["h"])
    code = client.post(f"{doc}/approve", json={"comment": "OK"}, headers=s["h"]).json()["verification_code"]
    res = client.delete(doc, headers=s["h"])
    assert res.status_code == 409 and "Cancel" in res.json()["detail"]
    assert client.post(f"{doc}/cancel", json={"reason": "Event postponed"}, headers=s["h"]).status_code == 200
    assert s["doc"] not in _list_ids(client, s)
    body = client.get(f"/api/v1/verify/{code}").json()
    assert body["valid"] is False and body["status"] == "cancelled" and "Event postponed" in body["message"]
    row = next(t for t in client.get(f"{s['base']}/trash", headers=s["h"]).json() if t["id"] == s["doc"])
    assert row["cancelled"] and not row["can_restore"] and row["purge_on"] is None
    assert client.post(f"{doc}/restore", headers=s["h"]).status_code == 409


def test_bulk_delete_reports_skipped(client, setup):
    s = setup
    res = client.post(f"{s['base']}/bulk-delete", json={"ids": [s["doc"], "does-not-exist"]}, headers=s["h"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["deleted"] == [s["doc"]]
    assert body["skipped"][0]["id"] == "does-not-exist"


def test_purge_after_30_days_but_not_cancelled(client, setup):
    s = setup
    client.delete(f"{s['base']}/{s['doc']}", headers=s["h"])
    with SessionLocal() as db:
        doc = db.query(Document).execution_options(include_deleted=True).filter(Document.id == s["doc"]).one()
        doc.deleted_at = datetime.utcnow() - timedelta(days=31)
        db.commit()
    client.get(f"{s['base']}/trash", headers=s["h"])  # listing the Trash purges expired documents
    with SessionLocal() as db:
        assert db.query(Document).execution_options(include_deleted=True).filter(Document.id == s["doc"]).first() is None


def test_outsider_cannot_delete(client, setup):
    import uuid

    s = setup
    clear_rate_limits()
    email = f"outsider_{uuid.uuid4().hex[:8]}@svnit.ac.in"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "name": "Outsider"})
    assert reg.status_code == 201, reg.text
    h = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    assert client.delete(f"{s['base']}/{s['doc']}", headers=h).status_code in (403, 404)
    assert s["doc"] in _list_ids(client, s)
