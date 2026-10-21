"""add verification_code and pdf_sha256 to document_versions

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-22 01:30:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if context.is_offline_mode():
        with op.batch_alter_table("document_versions") as batch_op:
            batch_op.add_column(sa.Column("verification_code", sa.String(length=32), nullable=True))
            batch_op.add_column(sa.Column("pdf_sha256", sa.String(length=64), nullable=True))
            batch_op.create_index("ix_document_versions_verification_code", ["verification_code"], unique=True)
        return

    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns("document_versions")]
    with op.batch_alter_table("document_versions") as batch_op:
        if "verification_code" not in cols:
            batch_op.add_column(sa.Column("verification_code", sa.String(length=32), nullable=True))
            batch_op.create_index("ix_document_versions_verification_code", ["verification_code"], unique=True)
        if "pdf_sha256" not in cols:
            batch_op.add_column(sa.Column("pdf_sha256", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("document_versions") as batch_op:
        batch_op.drop_index("ix_document_versions_verification_code")
        batch_op.drop_column("pdf_sha256")
        batch_op.drop_column("verification_code")
