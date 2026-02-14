"""Add agent_id to forum_posts for agent-created post traceability.

Revision ID: 005
Revises: 004
Create Date: 2026-02-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "forum_posts",
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=True,
        ),
    )
    op.create_index("idx_forum_posts_agent", "forum_posts", ["agent_id"])


def downgrade() -> None:
    op.drop_index("idx_forum_posts_agent", table_name="forum_posts")
    op.drop_column("forum_posts", "agent_id")
