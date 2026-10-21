"""add requested access level and applicant message to join requests

Revision ID: a7c1d2e3f4b5
Revises: f1b2c3d4e5f6
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "a7c1d2e3f4b5"
down_revision: Union[str, Sequence[str], None] = "f1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not context.is_offline_mode():
        # Idempotent against drifted databases
        cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("join_requests")}
    else:
        cols = set()

    with op.batch_alter_table("join_requests") as batch_op:
        if "requested_role" not in cols:
            batch_op.add_column(
                sa.Column("requested_role", sa.String(length=50), nullable=False, server_default="editor")
            )
        if "message" not in cols:
            batch_op.add_column(sa.Column("message", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("join_requests") as batch_op:
        batch_op.drop_column("message")
        batch_op.drop_column("requested_role")
