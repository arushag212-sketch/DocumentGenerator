"""SQLAlchemy 2.0 models for ClubDocs platform.

All tables have id (UUID string), created_at, updated_at.
Club-scoped tables have club_id with an index.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.app.core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    """Standard UUID primary key and timestamp tracking."""
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    disabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Session revocation & token versioning
    token_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Password reset tracking (single-use, hashed, 30 min expiry)
    password_reset_token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    password_reset_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    password_reset_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Rate limiting & Lockout
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")


class Club(TimestampMixin, Base):
    __tablename__ = "clubs"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(String(50), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    chapter_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    head_of_account: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    academic_year_default: Mapped[str] = mapped_column(String(20), default="2026-27", nullable=False)
    default_letterhead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    disabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    memberships = relationship("Membership", back_populates="club", cascade="all, delete-orphan")


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    club_id: Mapped[str] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), default="editor", nullable=False)  # owner | admin | editor | viewer
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "club_id", name="uq_membership_user_club"),
    )

    user = relationship("User", back_populates="memberships")
    club = relationship("Club", back_populates="memberships")


class Invite(TimestampMixin, Base):
    __tablename__ = "invites"

    club_id: Mapped[str] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    email_or_code: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="editor", nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"

    club_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)  # logo | letterhead | signature | other
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str] = mapped_column(String(100), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Letterhead(TimestampMixin, Base):
    __tablename__ = "letterheads"

    club_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    left_logo_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    right_logo_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    institute_logo_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # locked SVNIT logo
    title_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    subtitle_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    colors: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    fonts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    footer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    layout: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Person(TimestampMixin, Base):
    __tablename__ = "people"

    club_id: Mapped[str] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    roll_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    branch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # encrypted at rest
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RoleHeld(TimestampMixin, Base):
    __tablename__ = "roles_held"

    club_id: Mapped[str] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    role_key: Mapped[str] = mapped_column(String(100), nullable=False)  # student_head, faculty_chairman, etc.
    designation_label: Mapped[str] = mapped_column(String(255), nullable=False)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    academic_year: Mapped[str] = mapped_column(String(20), default="2026-27", nullable=False)


class Venue(TimestampMixin, Base):
    __tablename__ = "venues"

    club_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    addressee_default: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tech_assistant_person_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    faculty_incharge_person_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class Template(TimestampMixin, Base):
    __tablename__ = "templates"

    club_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    forked_from_template_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)  # draft | published | archived
    current_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class TemplateVersion(TimestampMixin, Base):
    __tablename__ = "template_versions"

    template_id: Mapped[str] = mapped_column(String(36), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    editor_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    docx_storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    letterhead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    validation_report: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    change_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint("template_id", "version_no", name="uq_template_version"),
    )


class Clause(TimestampMixin, Base):
    __tablename__ = "clauses"

    club_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body_jinja: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class NumberingSeries(TimestampMixin, Base):
    __tablename__ = "numbering_series"

    club_id: Mapped[str] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)  # ROOM | MOM | <event_code>
    format: Mapped[str] = mapped_column(String(255), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    last_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("club_id", "key", "academic_year", name="uq_numbering_series_key_year"),
    )


class NumberReservation(TimestampMixin, Base):
    __tablename__ = "number_reservations"

    club_id: Mapped[str] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    series_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    sequence_num: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_no: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="reserved", nullable=False)  # reserved | used | released
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    document_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("club_id", "ref_no", name="uq_reservation_club_ref_no"),
    )


class Event(TimestampMixin, Base):
    __tablename__ = "events"

    club_id: Mapped[str] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    event_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    record: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    club_id: Mapped[str] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)
    template_id: Mapped[str] = mapped_column(String(36), ForeignKey("templates.id", ondelete="RESTRICT"), nullable=False, index=True)
    template_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("template_versions.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    ref_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)  # draft | needs_info | ready | finalized
    current_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("club_id", "ref_no", name="uq_document_club_ref_no"),
    )


class DocumentVersion(TimestampMixin, Base):
    __tablename__ = "document_versions"

    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    record_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    docx_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pdf_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    diff_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="generated", nullable=False)  # generated | manually_edited_upload

    __table_args__ = (
        UniqueConstraint("document_id", "version_no", name="uq_doc_version"),
    )


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    club_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)  # render | pdf | batch | ai
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)  # queued | running | completed | failed
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AIRequest(TimestampMixin, Base):
    __tablename__ = "ai_requests"

    club_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_log"

    club_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
