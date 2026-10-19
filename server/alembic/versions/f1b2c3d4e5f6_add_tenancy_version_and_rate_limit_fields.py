"""add tenancy, historical version, invite and rate-limit fields

Revision ID: f1b2c3d4e5f6
Revises: c5e70e7be8f3
"""

from __future__ import annotations

import hashlib
from typing import Sequence, Union

from alembic import op
from alembic import context
import sqlalchemy as sa


revision: str = "f1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c5e70e7be8f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if context.is_offline_mode():
        # Static SQL generation (offline mode / --sql flag)
        with op.batch_alter_table("memberships") as batch_op:
            batch_op.add_column(sa.Column("position", sa.String(length=100), nullable=True))

        op.create_table(
            "join_requests",
            sa.Column("club_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("position", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
            sa.Column("reviewed_by", sa.String(length=36), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_join_requests_club_id", "join_requests", ["club_id"], unique=False)
        op.create_index("ix_join_requests_user_id", "join_requests", ["user_id"], unique=False)
        op.create_index("ix_join_requests_reviewed_by", "join_requests", ["reviewed_by"], unique=False)

        with op.batch_alter_table("invites") as batch_op:
            batch_op.add_column(sa.Column("code_hash", sa.String(length=64), nullable=True))
            batch_op.add_column(sa.Column("code", sa.String(length=64), nullable=True))
            batch_op.add_column(sa.Column("created_by", sa.String(length=36), nullable=True))
            batch_op.add_column(sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"))
            batch_op.add_column(sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"))
            batch_op.add_column(sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()))
            batch_op.alter_column("email_or_code", existing_type=sa.String(length=255), nullable=True)

        op.create_index("ix_invites_code_hash", "invites", ["code_hash"], unique=True)
        op.create_index("ix_invites_created_by", "invites", ["created_by"], unique=False)

        with op.batch_alter_table("document_versions") as batch_op:
            batch_op.add_column(sa.Column("template_version_id", sa.String(length=36), nullable=True))
            batch_op.create_foreign_key(
                "fk_document_versions_template_version_id",
                "template_versions",
                ["template_version_id"],
                ["id"],
                ondelete="RESTRICT",
            )
        op.create_index(
            "ix_document_versions_template_version_id",
            "document_versions",
            ["template_version_id"],
            unique=False,
        )
        op.create_index("ix_documents_template_version_id", "documents", ["template_version_id"], unique=False)

        with op.batch_alter_table("ai_requests") as batch_op:
            batch_op.alter_column("tokens_in", existing_type=sa.Integer(), nullable=True)
            batch_op.alter_column("tokens_out", existing_type=sa.Integer(), nullable=True)
            batch_op.add_column(sa.Column("usage_estimated", sa.Boolean(), nullable=False, server_default=sa.false()))

        op.create_table(
            "rate_limit_buckets",
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("window_started", sa.DateTime(), nullable=False),
            sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
            sa.PrimaryKeyConstraint("key"),
        )
        return

    # Live connection mode (inspect database for idempotency against drifted databases)
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = set(inspector.get_table_names())

    # 1. Membership position
    if "memberships" in existing_tables:
        membership_cols = {c["name"] for c in inspector.get_columns("memberships")}
        if "position" not in membership_cols:
            with op.batch_alter_table("memberships") as batch_op:
                batch_op.add_column(sa.Column("position", sa.String(length=100), nullable=True))

    # 2. Join requests table
    if "join_requests" not in existing_tables:
        op.create_table(
            "join_requests",
            sa.Column("club_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("position", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
            sa.Column("reviewed_by", sa.String(length=36), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_join_requests_club_id", "join_requests", ["club_id"], unique=False)
        op.create_index("ix_join_requests_user_id", "join_requests", ["user_id"], unique=False)
        op.create_index("ix_join_requests_reviewed_by", "join_requests", ["reviewed_by"], unique=False)

    # 3. Invites table
    if "invites" in existing_tables:
        invite_cols = {c["name"] for c in inspector.get_columns("invites")}
        with op.batch_alter_table("invites") as batch_op:
            if "code_hash" not in invite_cols:
                batch_op.add_column(sa.Column("code_hash", sa.String(length=64), nullable=True))
            if "code" not in invite_cols:
                batch_op.add_column(sa.Column("code", sa.String(length=64), nullable=True))
            if "created_by" not in invite_cols:
                batch_op.add_column(sa.Column("created_by", sa.String(length=36), nullable=True))
            if "max_uses" not in invite_cols:
                batch_op.add_column(sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"))
            if "use_count" not in invite_cols:
                batch_op.add_column(sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"))
            if "revoked" not in invite_cols:
                batch_op.add_column(sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()))
            batch_op.alter_column("email_or_code", existing_type=sa.String(length=255), nullable=True)

        existing_invites = connection.execute(sa.text("SELECT id, email_or_code FROM invites")).fetchall()
        used_hashes: set[str] = set()
        for invite_id, email_or_code in existing_invites:
            raw = str(email_or_code or invite_id)
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            if digest in used_hashes:
                digest = hashlib.sha256(f"{raw}:{invite_id}".encode("utf-8")).hexdigest()
            used_hashes.add(digest)
            connection.execute(
                sa.text("UPDATE invites SET code_hash = :code_hash WHERE id = :id"),
                {"code_hash": digest, "id": invite_id},
            )

        invites_indexes = {idx["name"] for idx in inspector.get_indexes("invites")}
        if "ix_invites_code_hash" not in invites_indexes:
            op.create_index("ix_invites_code_hash", "invites", ["code_hash"], unique=True)
        if "ix_invites_created_by" not in invites_indexes:
            op.create_index("ix_invites_created_by", "invites", ["created_by"], unique=False)

    # 4. Document versions table
    if "document_versions" in existing_tables:
        dv_cols = {c["name"] for c in inspector.get_columns("document_versions")}
        if "template_version_id" not in dv_cols:
            with op.batch_alter_table("document_versions") as batch_op:
                batch_op.add_column(sa.Column("template_version_id", sa.String(length=36), nullable=True))
                batch_op.create_foreign_key(
                    "fk_document_versions_template_version_id",
                    "template_versions",
                    ["template_version_id"],
                    ["id"],
                    ondelete="RESTRICT",
                )
        dv_indexes = {idx["name"] for idx in inspector.get_indexes("document_versions")}
        if "ix_document_versions_template_version_id" not in dv_indexes:
            op.create_index(
                "ix_document_versions_template_version_id",
                "document_versions",
                ["template_version_id"],
                unique=False,
            )
        connection.execute(
            sa.text(
                "UPDATE document_versions "
                "SET template_version_id = (SELECT template_version_id FROM documents "
                "WHERE documents.id = document_versions.document_id) "
                "WHERE template_version_id IS NULL"
            )
        )

    # 5. Documents index
    if "documents" in existing_tables:
        doc_indexes = {idx["name"] for idx in inspector.get_indexes("documents")}
        if "ix_documents_template_version_id" not in doc_indexes:
            op.create_index("ix_documents_template_version_id", "documents", ["template_version_id"], unique=False)

    # 6. AI requests table
    if "ai_requests" in existing_tables:
        air_cols = {c["name"] for c in inspector.get_columns("ai_requests")}
        with op.batch_alter_table("ai_requests") as batch_op:
            batch_op.alter_column("tokens_in", existing_type=sa.Integer(), nullable=True)
            batch_op.alter_column("tokens_out", existing_type=sa.Integer(), nullable=True)
            if "usage_estimated" not in air_cols:
                batch_op.add_column(sa.Column("usage_estimated", sa.Boolean(), nullable=False, server_default=sa.false()))

    # 7. Rate limit buckets table
    if "rate_limit_buckets" not in existing_tables:
        op.create_table(
            "rate_limit_buckets",
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("window_started", sa.DateTime(), nullable=False),
            sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
            sa.PrimaryKeyConstraint("key"),
        )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_table("rate_limit_buckets")
        with op.batch_alter_table("ai_requests") as batch_op:
            batch_op.drop_column("usage_estimated")
        op.drop_index("ix_document_versions_template_version_id", table_name="document_versions")
        with op.batch_alter_table("document_versions") as batch_op:
            batch_op.drop_column("template_version_id")
        op.drop_index("ix_documents_template_version_id", table_name="documents")
        op.drop_index("ix_invites_created_by", table_name="invites")
        op.drop_index("ix_invites_code_hash", table_name="invites")
        with op.batch_alter_table("invites") as batch_op:
            batch_op.drop_column("revoked")
            batch_op.drop_column("use_count")
            batch_op.drop_column("max_uses")
            batch_op.drop_column("created_by")
            batch_op.drop_column("code")
            batch_op.drop_column("code_hash")
        op.drop_index("ix_join_requests_reviewed_by", table_name="join_requests")
        op.drop_index("ix_join_requests_user_id", table_name="join_requests")
        op.drop_index("ix_join_requests_club_id", table_name="join_requests")
        op.drop_table("join_requests")
        with op.batch_alter_table("memberships") as batch_op:
            batch_op.drop_column("position")
        return

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = set(inspector.get_table_names())

    if "rate_limit_buckets" in existing_tables:
        op.drop_table("rate_limit_buckets")

    if "ai_requests" in existing_tables:
        air_cols = {c["name"] for c in inspector.get_columns("ai_requests")}
        with op.batch_alter_table("ai_requests") as batch_op:
            if "usage_estimated" in air_cols:
                batch_op.drop_column("usage_estimated")

    if "document_versions" in existing_tables:
        dv_indexes = {idx["name"] for idx in inspector.get_indexes("document_versions")}
        if "ix_document_versions_template_version_id" in dv_indexes:
            op.drop_index("ix_document_versions_template_version_id", table_name="document_versions")
        dv_cols = {c["name"] for c in inspector.get_columns("document_versions")}
        if "template_version_id" in dv_cols:
            with op.batch_alter_table("document_versions") as batch_op:
                batch_op.drop_column("template_version_id")

    if "documents" in existing_tables:
        doc_indexes = {idx["name"] for idx in inspector.get_indexes("documents")}
        if "ix_documents_template_version_id" in doc_indexes:
            op.drop_index("ix_documents_template_version_id", table_name="documents")

    if "invites" in existing_tables:
        inv_indexes = {idx["name"] for idx in inspector.get_indexes("invites")}
        if "ix_invites_created_by" in inv_indexes:
            op.drop_index("ix_invites_created_by", table_name="invites")
        if "ix_invites_code_hash" in inv_indexes:
            op.drop_index("ix_invites_code_hash", table_name="invites")
        inv_cols = {c["name"] for c in inspector.get_columns("invites")}
        with op.batch_alter_table("invites") as batch_op:
            for col in ["revoked", "use_count", "max_uses", "created_by", "code", "code_hash"]:
                if col in inv_cols:
                    batch_op.drop_column(col)

    if "join_requests" in existing_tables:
        jr_indexes = {idx["name"] for idx in inspector.get_indexes("join_requests")}
        for idx in ["ix_join_requests_reviewed_by", "ix_join_requests_user_id", "ix_join_requests_club_id"]:
            if idx in jr_indexes:
                op.drop_index(idx, table_name="join_requests")
        op.drop_table("join_requests")

    if "memberships" in existing_tables:
        mem_cols = {c["name"] for c in inspector.get_columns("memberships")}
        if "position" in mem_cols:
            with op.batch_alter_table("memberships") as batch_op:
                batch_op.drop_column("position")
