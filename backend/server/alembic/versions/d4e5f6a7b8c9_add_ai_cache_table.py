"""add ai cache table

Revision ID: d4e5f6a7b8c9
Revises: 553ed34245ca
Create Date: 2026-10-21 22:15:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "553ed34245ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not context.is_offline_mode() and "ai_cache" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "ai_cache",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("club_id", sa.String(length=36), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_ai_cache_club_id", "ai_cache", ["club_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_cache_club_id", table_name="ai_cache")
    op.drop_table("ai_cache")
