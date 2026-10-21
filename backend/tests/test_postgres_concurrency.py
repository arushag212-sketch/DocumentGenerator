"""Tests for concurrency-safe numbering allocation on PostgreSQL and SQLite.

Ensures that 20 parallel confirmations produce 20 unique, gap-free numbers.
"""

from __future__ import annotations

import concurrent.futures
import os
import tempfile
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from server.app.api.v1.documents import allocate_next_sequence
from server.app.models import Base, Club, NumberingSeries


def test_concurrency_numbering_atomic_sqlite():
    """Verify 20 parallel threads allocate 20 unique, gap-free numbers atomically."""
    # Create a temporary SQLite database with WAL mode enabled
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.commit()

        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine)

        club_id = str(uuid.uuid4())
        with SessionLocal() as session:
            club = Club(id=club_id, name="Test Concurrency Club", short_name="TCC", slug="test-concurrency", academic_year_default="2026-27")
            session.add(club)
            ns = NumberingSeries(
                club_id=club_id,
                key="ROOM",
                format="ACM/2026-27/ROOM/{seq:03d}",
                academic_year="2026-27",
                last_seq=0,
            )
            session.add(ns)
            session.commit()

        # Run 20 concurrent threads confirming reference numbers
        allocated_numbers = []

        def worker():
            with SessionLocal() as s:
                seq = allocate_next_sequence(s, club_id, "ROOM", "2026-27")
                s.commit()
                return seq

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(worker) for _ in range(20)]
            for f in concurrent.futures.as_completed(futures):
                allocated_numbers.append(f.result())

        # Assertions: 20 unique numbers, gap-free 1 to 20
        assert len(allocated_numbers) == 20, f"Expected 20 allocations, got {len(allocated_numbers)}"
        assert len(set(allocated_numbers)) == 20, f"Duplicate sequences found: {allocated_numbers}"
        assert sorted(allocated_numbers) == list(range(1, 21)), (
            f"Numbers are not gap-free 1..20: {sorted(allocated_numbers)}"
        )

        # Check final DB state
        with SessionLocal() as s:
            ns_final = (
                s.query(NumberingSeries)
                .filter(NumberingSeries.club_id == club_id, NumberingSeries.key == "ROOM")
                .first()
            )
            assert ns_final.last_seq == 20
    finally:
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.mark.skipif(not os.environ.get("POSTGRES_TEST_URL"), reason="Set POSTGRES_TEST_URL to a PostgreSQL database to run")
def test_concurrency_numbering_postgres():
    """Verify 20 parallel threads allocate 20 unique, gap-free numbers on PostgreSQL."""
    pg_url = os.environ.get(
        "POSTGRES_TEST_URL",
        "postgresql://clubdocs_user:clubdocs_password@localhost:5432/clubdocs",
    )

    if not pg_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL is not PostgreSQL. Start postgres with `docker compose up -d` to run this test.")

    try:
        engine = create_engine(pg_url, pool_size=25, max_overflow=10)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL server not reachable at {pg_url}: {exc}")

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    club_id = str(uuid.uuid4())
    series_key = f"TEST_SERIES_{uuid.uuid4().hex[:6]}"
    with SessionLocal() as session:
        club = Club(id=club_id, name="Test PG Club", short_name="TPC", slug=f"test-pg-{uuid.uuid4().hex[:6]}", academic_year_default="2026-27")
        session.add(club)
        ns = NumberingSeries(
            club_id=club_id,
            key=series_key,
            format=f"ACM/2026-27/{series_key}/{{seq:03d}}",
            academic_year="2026-27",
            last_seq=0,
        )
        session.add(ns)
        session.commit()

    allocated_numbers = []

    def worker():
        with SessionLocal() as s:
            seq = allocate_next_sequence(s, club_id, series_key, "2026-27")
            s.commit()
            return seq

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(worker) for _ in range(20)]
        for f in concurrent.futures.as_completed(futures):
            allocated_numbers.append(f.result())

    assert len(allocated_numbers) == 20
    assert len(set(allocated_numbers)) == 20
    assert sorted(allocated_numbers) == list(range(1, 21))

    with SessionLocal() as s:
        ns_final = (
            s.query(NumberingSeries)
            .filter(NumberingSeries.club_id == club_id, NumberingSeries.key == series_key)
            .first()
        )
        assert ns_final.last_seq == 20
