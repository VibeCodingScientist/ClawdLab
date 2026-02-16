"""Add verification status tracking columns to tasks.

Revision ID: 010
Revises: 009
Create Date: 2026-02-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("verification_status", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("verification_job_id", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("verification_queued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("verification_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("verification_completed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        "idx_tasks_verification_status",
        "tasks",
        ["verification_status"],
        postgresql_where=sa.text("verification_status IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_tasks_verification_status", table_name="tasks")
    op.drop_column("tasks", "verification_completed_at")
    op.drop_column("tasks", "verification_started_at")
    op.drop_column("tasks", "verification_queued_at")
    op.drop_column("tasks", "verification_job_id")
    op.drop_column("tasks", "verification_status")
