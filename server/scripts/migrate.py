"""Database migration script with legacy database auto-detection and stamping.

Usage:
    python -m server.scripts.migrate
"""

from __future__ import annotations

import sys
from pathlib import Path
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from server.app.core.database import engine


def run_migrations(alembic_ini_path: str = "alembic.ini") -> None:
    """Detect unversioned legacy database, stamp correct baseline revision, and upgrade to head."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    ini_file = root_dir / alembic_ini_path
    if not ini_file.exists():
        ini_file = Path(alembic_ini_path)

    alembic_cfg = Config(str(ini_file))

    with engine.connect() as conn:
        inspector = sa.inspect(conn)
        tables = set(inspector.get_table_names())

        has_alembic = "alembic_version" in tables
        if not has_alembic and len(tables) > 0:
            if "number_reservations" in tables:
                print("Detected unversioned legacy database with 'number_reservations'. Stamping baseline c5e70e7be8f3...")
                command.stamp(alembic_cfg, "c5e70e7be8f3")
            elif "users" in tables:
                print("Detected unversioned legacy database with 'users'. Stamping baseline 7ba99a052692...")
                command.stamp(alembic_cfg, "7ba99a052692")

    print("Upgrading database schema to head...")
    command.upgrade(alembic_cfg, "head")
    print("Database migration completed successfully.")


if __name__ == "__main__":
    run_migrations()
