"""Add parent_id and upvotes to forum_comments.

Migration 001 created forum_comments without these columns,
but the ORM model (ForumComment) defines them. This migration
adds them so the schema matches the model.

Revision ID: 003
Revises: 002
Create Date: 2026-02-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "forum_comments",
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forum_comments.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "forum_comments",
        sa.Column(
            "upvotes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("forum_comments", "upvotes")
    op.drop_column("forum_comments", "parent_id")
