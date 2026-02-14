"""Add tags and parent_lab_id to forum_posts and labs for lab scaling.

Revision ID: 006
Revises: 005
Create Date: 2026-02-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- forum_posts ---
    op.add_column(
        "forum_posts",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "forum_posts",
        sa.Column(
            "parent_lab_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("labs.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_forum_posts_tags",
        "forum_posts",
        ["tags"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_forum_posts_parent_lab",
        "forum_posts",
        ["parent_lab_id"],
    )

    # --- labs ---
    op.add_column(
        "labs",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "labs",
        sa.Column(
            "parent_lab_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("labs.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_labs_tags",
        "labs",
        ["tags"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_labs_parent",
        "labs",
        ["parent_lab_id"],
    )

    # Update labs.rules server_default to include max_members
    op.alter_column(
        "labs",
        "rules",
        server_default=sa.text(
            """'{"voting_threshold": 0.5, "quorum_fraction": 0.3, "pi_veto_enabled": true, "min_debate_hours": 0, "voting_check_interval_minutes": 10, "max_members": 15}'::jsonb"""
        ),
    )


def downgrade() -> None:
    # Revert labs.rules server_default
    op.alter_column(
        "labs",
        "rules",
        server_default=sa.text(
            """'{"voting_threshold": 0.5, "quorum_fraction": 0.3, "pi_veto_enabled": true, "min_debate_hours": 0, "voting_check_interval_minutes": 10}'::jsonb"""
        ),
    )

    op.drop_index("idx_labs_parent", table_name="labs")
    op.drop_index("idx_labs_tags", table_name="labs")
    op.drop_column("labs", "parent_lab_id")
    op.drop_column("labs", "tags")

    op.drop_index("idx_forum_posts_parent_lab", table_name="forum_posts")
    op.drop_index("idx_forum_posts_tags", table_name="forum_posts")
    op.drop_column("forum_posts", "parent_lab_id")
    op.drop_column("forum_posts", "tags")
