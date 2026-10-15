"""Pytest configuration for SVNIT ClubDocs.

Ensures strict TEST ISOLATION:
1. Re-binds the database engine and SessionLocal to an isolated temporary SQLite database.
2. Initializes tables and seeds initial demo data into the isolated test database.
3. Preserves `data/clubdocs.db` in an untouched, clean state.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Path to isolated test database
TEST_DB_PATH = Path("data/test_isolated.db")

# Force DATABASE_URL to test DB before importing app/db modules
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"

from server.app.core.database import Base, engine as app_engine, SessionLocal as app_SessionLocal
import server.app.core.database as db_module
from server.app.main import app
from server.scripts.seed import seed


@pytest.fixture(scope="session", autouse=True)
def setup_isolated_test_database():
    """Create and seed the isolated test database, ensuring dev DB is never touched."""
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except Exception:
            pass

    test_engine = create_engine(
        f"sqlite:///{TEST_DB_PATH.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    # Rebind core database engine and SessionLocal
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db_module.engine = test_engine
    db_module.SessionLocal = TestSessionLocal

    # Create schema and seed demo data in test database
    Base.metadata.create_all(bind=test_engine)
    seed()

    yield

    # Teardown
    test_engine.dispose()
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except Exception:
            pass


@pytest.fixture(scope="function")
def db_session():
    """Yield a database session connected to the isolated test database."""
    session = db_module.SessionLocal()
    try:
        yield session
    finally:
        session.close()

