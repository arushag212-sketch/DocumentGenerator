import pytest
from fastapi.testclient import TestClient
from server.app.main import app
from server.app.core.database import SessionLocal
from server.app.models import Club, User
from server.app.core.security import create_access_token

@pytest.fixture
def test_setup():
    db = SessionLocal()
    try:
        club = db.query(Club).filter(Club.slug == "acm").first()
        user = db.query(User).filter(User.email == "demo.owner@svnit.ac.in").first()
        token = create_access_token(user_id=user.id, email=user.email, token_version=user.token_version)
        headers = {"Authorization": f"Bearer {token}"}
        return {"client": TestClient(app), "club_id": club.id, "headers": headers}
    finally:
        db.close()

def test_approval_note_with_participants(test_setup):
    """Verify that giving 'participants' generates approval_note without missing field error."""
    client = test_setup["client"]
    club_id = test_setup["club_id"]
    headers = test_setup["headers"]

    payload = {
        "selected_template_ids": ["approval_note"],
        "event_data": {
            "event_name": "Annual Coding Conclave",
            "venue": "Seminar Hall",
            "date_start": "2026-11-10",
            "date_end": "2026-11-10",
            "dates_confirmed": True,
            "participants": 650,
            "budget_items": [{"item": "Refreshments", "amount": 5000}],
            "submitted_to": "Dean (Student Welfare)",
        },
        "ref_numbers_accepted": True,
    }

    res = client.post(f"/api/v1/clubs/{club_id}/home/generate", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["documents_count"] >= 1
    assert data["documents"][0]["template_slug"] == "approval_note"

def test_preview_with_blanks_when_fields_empty(test_setup):
    """Verify that allow_blanks=True generates documents even when fields are empty."""
    client = test_setup["client"]
    club_id = test_setup["club_id"]
    headers = test_setup["headers"]

    payload = {
        "selected_template_ids": ["approval_note", "permission_letter"],
        "event_data": {
            "event_name": "Annual Coding Conclave",
            # Venue, participants, budget, dates intentionally omitted
        },
        "ref_numbers_accepted": False,
        "allow_blanks": True,
    }

    res = client.post(f"/api/v1/clubs/{club_id}/home/generate", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["documents_count"] == 2
