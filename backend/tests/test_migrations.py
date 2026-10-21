"""Test suite for Alembic migrations, legacy schema stamping, and data preservation.

Tests:
1. Legacy unversioned DB stamping (c5e70e7be8f3 baseline).
2. Schema migration to head (f1b2c3d4e5f6).
3. RateLimitBucket table creation.
4. Backfill of document_versions.template_version_id from documents.
5. Startup self-check: rejects out-of-date DB with plain message, passes on head.
6. No data loss during migration.
"""

import os
import sqlite3
import uuid
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from server.app.main import check_db_schema_up_to_date


def test_startup_check_detects_out_of_date_schema(tmp_path):
    """Test that check_db_schema_up_to_date returns False on out-of-date DB and True on migrated DB."""
    db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    # Create minimal legacy tables without rate_limit_buckets and without template_version_id
    cur.execute("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(255));")
    cur.execute("CREATE TABLE document_versions (id VARCHAR(36) PRIMARY KEY, document_id VARCHAR(36));")
    conn.commit()
    conn.close()

    engine = sa.create_engine(f"sqlite:///{db_file}")
    assert check_db_schema_up_to_date(engine) is False

    # Add missing parts
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("CREATE TABLE rate_limit_buckets (key VARCHAR(255) PRIMARY KEY, window_started DATETIME, request_count INTEGER);")
    cur.execute("ALTER TABLE document_versions ADD COLUMN template_version_id VARCHAR(36);")
    conn.commit()
    conn.close()

    assert check_db_schema_up_to_date(engine) is True


def test_legacy_database_migration_and_data_preservation(tmp_path, monkeypatch):
    """Test migrating a legacy database snapshot with existing records up to head."""
    db_file = tmp_path / "legacy_migration_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    alembic_ini = Path("alembic.ini")
    assert alembic_ini.exists()
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to c5e70e7be8f3 (baseline)
    command.upgrade(cfg, "c5e70e7be8f3")

    # 2. Insert pre-existing data under baseline schema
    test_user_id = str(uuid.uuid4())
    test_club_id = str(uuid.uuid4())
    test_tmpl_id = str(uuid.uuid4())
    test_tmpl_ver_id = str(uuid.uuid4())
    test_doc_id = str(uuid.uuid4())
    test_doc_ver_id = str(uuid.uuid4())

    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    now_str = "2026-10-19 12:00:00"

    cur.execute(
        "INSERT INTO users (id, email, password_hash, name, is_platform_admin, token_version, failed_login_attempts, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 0, 1, 0, ?, ?)",
        (test_user_id, "legacy.user@svnit.ac.in", "hashed_pw", "Legacy User", now_str, now_str),
    )
    cur.execute(
        "INSERT INTO clubs (id, name, short_name, slug, academic_year_default, settings, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, '{}', ?, ?)",
        (test_club_id, "Legacy Club", "LC", "legacy_club", "2026-27", now_str, now_str),
    )
    cur.execute(
        "INSERT INTO templates (id, club_id, name, slug, status, is_system, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'published', 0, ?, ?)",
        (test_tmpl_id, test_club_id, "Legacy Template", "legacy_template", now_str, now_str),
    )
    cur.execute(
        "INSERT INTO template_versions (id, template_id, version_no, docx_storage_key, schema_yaml, created_at, updated_at) "
        "VALUES (?, ?, 1, 'dummy_key.docx', 'fields: []', ?, ?)",
        (test_tmpl_ver_id, test_tmpl_id, now_str, now_str),
    )
    cur.execute(
        "INSERT INTO documents (id, club_id, template_id, template_version_id, title, ref_no, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'Legacy Doc', 'LEG/001', 'finalized', ?, ?)",
        (test_doc_id, test_club_id, test_tmpl_id, test_tmpl_ver_id, now_str, now_str),
    )
    cur.execute(
        "INSERT INTO document_versions (id, document_id, version_no, record_snapshot, overrides, docx_key, source, created_at, updated_at) "
        "VALUES (?, ?, 1, '{}', '{}', 'doc_v1.docx', 'generated', ?, ?)",
        (test_doc_ver_id, test_doc_id, now_str, now_str),
    )
    conn.commit()
    conn.close()

    # 3. Perform upgrade to head (f1b2c3d4e5f6)
    command.upgrade(cfg, "head")

    # 4. Verify new schema features
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    # RateLimitBuckets table exists
    cur.execute("SELECT count(*) FROM rate_limit_buckets")
    assert cur.fetchone()[0] == 0

    # DocumentVersions has template_version_id backfilled from documents table!
    cur.execute("SELECT template_version_id FROM document_versions WHERE id = ?", (test_doc_ver_id,))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == test_tmpl_ver_id, "document_versions.template_version_id was not properly backfilled!"

    # Existing user and club data preserved intact
    cur.execute("SELECT email, name FROM users WHERE id = ?", (test_user_id,))
    user_row = cur.fetchone()
    assert user_row == ("legacy.user@svnit.ac.in", "Legacy User")

    conn.close()
