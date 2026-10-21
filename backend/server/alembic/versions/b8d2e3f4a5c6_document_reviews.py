"""document review / approval history

Revision ID: b8d2e3f4a5c6
Revises: a7c1d2e3f4b5
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "b8d2e3f4a5c6"
down_revision: Union[str, Sequence[str], None] = "a7c1d2e3f4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not context.is_offline_mode() and "document_reviews" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "document_reviews",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("club_id", sa.String(length=36), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("verification_code", sa.String(length=32), nullable=True),
        sa.Column("pdf_sha256", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_document_reviews_club_id", "document_reviews", ["club_id"])
    op.create_index("ix_document_reviews_document_id", "document_reviews", ["document_id"])
    op.create_index("ix_document_reviews_verification_code", "document_reviews", ["verification_code"], unique=True)
    op.create_index("ix_document_reviews_user_id", "document_reviews", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_document_reviews_user_id", table_name="document_reviews")
    op.drop_index("ix_document_reviews_verification_code", table_name="document_reviews")
    op.drop_index("ix_document_reviews_document_id", table_name="document_reviews")
    op.drop_index("ix_document_reviews_club_id", table_name="document_reviews")
    op.drop_table("document_reviews")
