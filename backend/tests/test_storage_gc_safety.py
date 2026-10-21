"""Storage cleanup must never delete files that another club (or anything in the DB) still uses."""

import uuid

from server.app.core.storage import get_storage
from server.app.models import Asset, Club
from server.scripts import storage_gc


def _club(db_session, slug):
    club = Club(id=str(uuid.uuid4()), name=f"GC Club {slug}", short_name=slug.upper(), slug=slug)
    db_session.add(club)
    db_session.commit()
    return club


def _asset_file(db_session, club, name):
    storage = get_storage()
    key, sha = storage.save_content_addressed("assets", f"logo-{name}-{uuid.uuid4()}".encode(), "png")
    db_session.add(Asset(id=str(uuid.uuid4()), club_id=club.id, kind="logo", filename=f"{name}.png", mime="image/png",
                         sha256=sha, size=10, storage_key=key))
    db_session.commit()
    return storage.local_path(key)


def test_club_scoped_cleanup_keeps_other_clubs_files(db_session):
    club_a = _club(db_session, f"gca{uuid.uuid4().hex[:6]}")
    club_b = _club(db_session, f"gcb{uuid.uuid4().hex[:6]}")
    file_a = _asset_file(db_session, club_a, "a")
    file_b = _asset_file(db_session, club_b, "b")

    storage_gc.run_storage_gc(apply=True, club_id=club_a.id)

    assert file_a.exists()
    assert file_b.exists(), "cleaning club A deleted club B's logo"


def test_cleanup_deletes_nothing_when_database_unreadable(db_session, monkeypatch):
    club = _club(db_session, f"gcc{uuid.uuid4().hex[:6]}")
    logo = _asset_file(db_session, club, "c")

    def broken(*_args, **_kwargs):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(storage_gc, "get_db_protected_and_referenced_paths", broken)
    report = storage_gc.run_storage_gc(apply=True)

    assert logo.exists()
    assert report.orphans_count == 0
    assert any("Cleanup skipped" in line for line in report.logs)
