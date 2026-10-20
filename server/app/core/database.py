"""Core database engine and session configuration using SQLAlchemy 2.0."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Database URL: default to SQLite in data/clubdocs.db, overridable by DATABASE_URL env var
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/clubdocs.db")

# Ensure parent directory exists for SQLite
if DATABASE_URL.startswith("sqlite:///"):
    sqlite_path = DATABASE_URL.replace("sqlite:///", "")
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

# Hosting dashboards often hand out "postgres://", which SQLAlchemy no longer accepts
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

connect_args = {}
engine_kwargs: dict = {}
if DATABASE_URL.startswith("sqlite"):
    # Wait for a writer (e.g. a batch rendering PDFs) instead of failing with "database is locked"
    connect_args = {"check_same_thread": False, "timeout": 30}
else:
    # Hosted Postgres (e.g. Supabase's pooler) closes idle connections and caps how many
    # a free project may hold, so check each connection before use and keep the pool small.
    engine_kwargs = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "5")),
    }

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=os.environ.get("SQL_ECHO", "false").lower() in ("true", "1"),
    **engine_kwargs,
)

# Enable foreign keys and WAL mode for SQLite
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Mirror saved template/document/logo files to remote storage after each commit (no-op on local
# storage). Registered on the Session class so every process and test-rebound factory gets it.
from server.app.core.storage import register_persistence_hooks  # noqa: E402

register_persistence_hooks(Session)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy 2.0 models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """Yield one request transaction and commit only after a successful handler.

    Keeping the transaction boundary at the request layer prevents repository
    and audit helpers from partially committing a request.  Exceptions roll
    back all pending work before the session is closed.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
