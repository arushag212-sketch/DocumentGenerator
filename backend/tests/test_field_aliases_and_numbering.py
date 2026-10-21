"""Custom-template field aliases and template-declared numbering series."""

from __future__ import annotations

import uuid

from docgen.field_aliases import apply_field_aliases
from docgen.numbering import derive_event_code
from server.app.core.database import SessionLocal
from server.app.core.numbering_service import reserve_number_for_document
from server.app.models import Club, NumberingSeries, User


def test_aliases_fill_only_wanted_template_keys():
    data = {"event_name": "Web Development Workshop", "venue": "Seminar Hall", "date_start": "2026-10-14", "date_end": "2026-10-15"}
    apply_field_aliases(data, wanted={"event_date", "location"})
    assert data["dates"] == "14-15 October 2026"
    assert data["event_date"] == "14-15 October 2026"
    assert data["location"] == "Seminar Hall"
    # Unrequested synonyms are not added to the event record
    assert "event_title" not in data and "place" not in data


def test_aliases_never_overwrite_or_invent():
    data = {"event_name": "Hackathon", "event_title": "User Title", "coordinator_name": ""}
    apply_field_aliases(data, wanted={"event_title", "coordinator_name", "venue"})
    assert data["event_title"] == "User Title"
    assert data["coordinator_name"] == ""
    assert "venue" not in data


def test_alias_answer_satisfies_canonical_key():
    data = {"expected_participants": 80}
    apply_field_aliases(data, wanted=())
    assert data["participants"] == 80


def test_derive_event_code():
    assert derive_event_code("Web Development Workshop") == "WDW"
    assert derive_event_code("The Art of Code") == "AC"
    assert derive_event_code("") == "EVT"


def test_template_declared_series_is_created_on_first_use():
    db = SessionLocal()
    try:
        club = db.query(Club).filter(Club.slug == "acm").first()
        user = db.query(User).filter(User.email == "demo.owner@svnit.ac.in").first()
        key = f"T{uuid.uuid4().hex[:6].upper()}"

        _, ref_no = reserve_number_for_document(
            db=db,
            club_id=club.id,
            user_id=user.id,
            series_key=key,
            format_pattern=f"ACM/{{short_year}}/{key}/{{seq:03d}}",
            allow_create=True,
        )
        assert ref_no.endswith(f"/{key}/001")
        assert db.query(NumberingSeries).filter(NumberingSeries.club_id == club.id, NumberingSeries.key == key).count() == 1
    finally:
        db.rollback()
        db.close()
