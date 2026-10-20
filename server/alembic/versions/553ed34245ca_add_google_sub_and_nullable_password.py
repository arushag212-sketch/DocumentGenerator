"""add google_sub and nullable password_hash for google auth

Revision ID: 553ed34245ca
Revises: b8d2e3f4a5c6
Create Date: 2026-10-21 01:11:31.649622

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "553ed34245ca"
down_revision: Union[str, Sequence[str], None] = "b8d2e3f4a5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        cols = {c["name"] for c in inspector.get_columns("users")}
        indexes = {ix["name"] for ix in inspector.get_indexes("users")}
    else:
        cols = set()
        indexes = set()

    with op.batch_alter_table("users", schema=None) as batch_op:
        if "google_sub" not in cols:
            batch_op.add_column(sa.Column("google_sub", sa.String(length=255), nullable=True))
        batch_op.alter_column("password_hash", existing_type=sa.String(length=255), nullable=True)
        if "ix_users_google_sub" not in indexes:
            batch_op.create_index("ix_users_google_sub", ["google_sub"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_google_sub")
        batch_op.drop_column("google_sub")
        batch_op.alter_column("password_hash", existing_type=sa.String(length=255), nullable=False)
