"""Create lab_states table and add lab_state_id FK to tasks.

Revision ID: 009
Revises: 008
Create Date: 2026-02-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lab_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("labs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("objectives", postgresql.ARRAY(sa.String()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("conclusion_summary", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','active','concluded_proven','concluded_disproven','concluded_pivoted','concluded_inconclusive')",
            name="ck_lab_state_status",
        ),
        sa.UniqueConstraint("lab_id", "version", name="uq_lab_state_version"),
    )
    op.create_index("idx_lab_states_lab", "lab_states", ["lab_id"])
    op.create_index("idx_lab_states_lab_version", "lab_states", ["lab_id", "version"])

    # Add lab_state_id FK to tasks
    op.add_column("tasks", sa.Column("lab_state_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_tasks_lab_state_id", "tasks", "lab_states", ["lab_state_id"], ["id"])
    op.create_index("idx_tasks_lab_state", "tasks", ["lab_state_id"])


def downgrade() -> None:
    op.drop_index("idx_tasks_lab_state", table_name="tasks")
    op.drop_constraint("fk_tasks_lab_state_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "lab_state_id")
    op.drop_index("idx_lab_states_lab_version", table_name="lab_states")
    op.drop_index("idx_lab_states_lab", table_name="lab_states")
    op.drop_table("lab_states")
