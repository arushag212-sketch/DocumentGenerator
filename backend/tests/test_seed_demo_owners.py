"""Tests for seed_demo_clubs.py --owners-only mode."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from server.app.core import database as db_module
from server.app.core.security import get_password_hash, verify_password
from server.app.models import Asset, Club, Membership, Person, RoleHeld, User, Venue
from server.scripts.seed import seed as run_main_seed
from server.scripts.seed_demo_clubs import seed as seed_demo_clubs, ACCOUNTS_DOC


def _clean_db():
    with db_module.SessionLocal() as db:
        db.query(RoleHeld).delete()
        db.query(Venue).delete()
        db.query(Person).delete()
        db.query(Membership).delete()
        db.query(Club).delete()
        db.query(User).delete()
        db.query(Asset).filter(Asset.is_system.is_(False)).delete()
        db.commit()


@pytest.fixture(autouse=True)
def clean_and_restore_db(tmp_path, monkeypatch):
    _clean_db()
    # Avoid writing docs/DEMO_ACCOUNTS.md during tests
    temp_doc = tmp_path / "DEMO_ACCOUNTS.md"
    monkeypatch.setattr("server.scripts.seed_demo_clubs.ACCOUNTS_DOC", temp_doc)
    yield
    _clean_db()
    # Re-seed test fixtures so subsequent test files have the baseline state
    run_main_seed()


def test_without_password_exits_and_creates_nothing(monkeypatch):
    """Without DEMO_OWNER_PASSWORD it exits with an error and creates nothing."""
    monkeypatch.delenv("DEMO_OWNER_PASSWORD", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(SystemExit) as exc_info:
        seed_demo_clubs(no_ai=True, owners_only=True)
    assert exc_info.value.code != 0

    with db_module.SessionLocal() as db:
        assert db.query(Club).count() == 0

    # Also test password shorter than 12 characters
    monkeypatch.setenv("DEMO_OWNER_PASSWORD", "short_pass")
    with pytest.raises(SystemExit) as exc_info2:
        seed_demo_clubs(no_ai=True, owners_only=True)
    assert exc_info2.value.code != 0

    with db_module.SessionLocal() as db:
        assert db.query(Club).count() == 0


def test_owners_only_creates_5_clubs_and_subsequent_run_skips(monkeypatch):
    """With DEMO_OWNER_PASSWORD set, --owners-only creates exactly 5 clubs, each with

    exactly one member (the owner, role owner) and a logo.
    Rename one club and change its owner's password, then run again:
    nothing is created, the rename and password change are kept.
    """
    owner_pass = "ProductionSecurePass123!"
    monkeypatch.setenv("DEMO_OWNER_PASSWORD", owner_pass)
    monkeypatch.setenv("ENVIRONMENT", "production")

    # 1. First run creates the 5 clubs
    res = seed_demo_clubs(no_ai=True, owners_only=True)
    assert res is not None

    expected_slugs = {"acm", "gdgc", "chrd", "drishti", "raag"}
    with db_module.SessionLocal() as db:
        clubs = db.query(Club).all()
        assert len(clubs) == 5
        assert {c.slug for c in clubs} == expected_slugs

        for c in clubs:
            memberships = db.query(Membership).filter(Membership.club_id == c.id).all()
            assert len(memberships) == 1
            m = memberships[0]
            assert m.role == "owner"
            user = db.query(User).filter(User.id == m.user_id).first()
            assert user is not None
            assert user.email == f"{c.slug}.owner@demo.svnit.ac.in"
            assert verify_password(owner_pass, user.password_hash)

            # Logo uploaded and set
            assert c.settings.get("logo_asset_id") is not None
            asset = db.query(Asset).filter(Asset.id == c.settings["logo_asset_id"]).first()
            assert asset is not None
            assert asset.kind == "logo"

    # 2. Rename one club and change its owner's password in the database
    new_password = "OwnerChangedPassword456!"
    with db_module.SessionLocal() as db:
        acm = db.query(Club).filter(Club.slug == "acm").first()
        assert acm is not None
        acm.name = "Renamed ACM Student Chapter"

        acm_owner = db.query(User).filter(User.email == "acm.owner@demo.svnit.ac.in").first()
        assert acm_owner is not None
        acm_owner.password_hash = get_password_hash(new_password)
        db.commit()

    # 3. Run again: nothing is created, the rename and password change are kept
    res2 = seed_demo_clubs(no_ai=True, owners_only=True)
    assert res2 is not None

    with db_module.SessionLocal() as db:
        clubs = db.query(Club).all()
        assert len(clubs) == 5
        assert {c.slug for c in clubs} == expected_slugs

        acm = db.query(Club).filter(Club.slug == "acm").first()
        assert acm is not None
        assert acm.name == "Renamed ACM Student Chapter"

        acm_owner = db.query(User).filter(User.email == "acm.owner@demo.svnit.ac.in").first()
        assert acm_owner is not None
        assert verify_password(new_password, acm_owner.password_hash)
        assert not verify_password(owner_pass, acm_owner.password_hash)


def test_production_mode_blocks_full_mode(monkeypatch):
    """Full mode must be blocked in production; --owners-only is allowed."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEMO_OWNER_PASSWORD", "ProductionSecurePass123!")

    # Full mode blocked
    with pytest.raises(SystemExit) as exc_info:
        seed_demo_clubs(no_ai=True, owners_only=False)
    assert exc_info.value.code != 0

    # --owners-only allowed
    res = seed_demo_clubs(no_ai=True, owners_only=True)
    assert res is not None


def test_full_development_mode(monkeypatch):
    """The full (development) mode still works as before in development."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    # In dev mode, seed() from seed.py creates ACM first
    run_main_seed()

    res = seed_demo_clubs(no_ai=True, owners_only=False)
    assert res is not None
    assert len(res) > 0

    with db_module.SessionLocal() as db:
        # Check that clubs have multiple members created in full mode (admin/editor/viewer)
        gdgc = db.query(Club).filter(Club.slug == "gdgc").first()
        assert gdgc is not None
        memberships = db.query(Membership).filter(Membership.club_id == gdgc.id).all()
        assert len(memberships) >= 2
