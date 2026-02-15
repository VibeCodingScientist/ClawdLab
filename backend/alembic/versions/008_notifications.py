"""Create notifications table.

Revision ID: 008
Revises: 007
Create Date: 2026-02-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_notifications_user_read", "notifications", ["user_id", "read_at"])
    op.create_index("idx_notifications_user_created", "notifications", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_notifications_user_created", table_name="notifications")
    op.drop_index("idx_notifications_user_read", table_name="notifications")
    op.drop_table("notifications")
