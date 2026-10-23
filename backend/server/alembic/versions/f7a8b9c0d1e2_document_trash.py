"""documents: trash (deleted_at, deleted_by) and cancel reason

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-10-24 12:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = (
    ("deleted_at", sa.DateTime()),
    ("deleted_by", sa.String(length=36)),
    ("cancel_reason", sa.String(length=500)),
)


def upgrade() -> None:
    existing = set()
    if not context.is_offline_mode():
        existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("documents")}
    with op.batch_alter_table("documents") as batch_op:
        for name, type_ in COLUMNS:
            if name not in existing:
                batch_op.add_column(sa.Column(name, type_, nullable=True))
        if "deleted_at" not in existing:
            batch_op.create_index("ix_documents_deleted_at", ["deleted_at"])


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_index("ix_documents_deleted_at")
        for name, _ in reversed(COLUMNS):
            batch_op.drop_column(name)
