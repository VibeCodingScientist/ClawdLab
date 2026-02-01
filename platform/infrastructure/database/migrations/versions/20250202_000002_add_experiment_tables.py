"""Add experiment management tables.

Revision ID: 20250202_000002
Revises: 20250202_000001
Create Date: 2025-02-02 00:00:02.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250202_000002"
down_revision: Union[str, None] = "20250202_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # EXPERIMENT PLAN TABLE
    # ===========================================

    op.create_table(
        "experiment_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("objective", sa.Text(), nullable=False, server_default=""),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("dependencies", postgresql.JSONB(), server_default="{}"),
        sa.Column("total_resource_estimate", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_experiment_plans_domain", "experiment_plans", ["domain"])
    op.create_index("idx_experiment_plans_status", "experiment_plans", ["status"])
    op.create_index("idx_experiment_plans_created", "experiment_plans", ["created_at"])

    # ===========================================
    # HYPOTHESES TABLE
    # ===========================================

    op.create_table(
        "hypotheses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("hypothesis_type", sa.String(50), nullable=False, server_default="descriptive"),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposed"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("evidence", postgresql.JSONB(), server_default="[]"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_hypotheses_domain", "hypotheses", ["domain"])
    op.create_index("idx_hypotheses_status", "hypotheses", ["status"])
    op.create_index("idx_hypotheses_type", "hypotheses", ["hypothesis_type"])

    # ===========================================
    # EXPERIMENTS TABLE
    # ===========================================

    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("experiment_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("variables", postgresql.JSONB(), server_default="[]"),
        sa.Column("steps", postgresql.JSONB(), server_default="[]"),
        sa.Column("config", postgresql.JSONB(), server_default="{}"),
        sa.Column("results", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("experiment_plans.id", ondelete="SET NULL")),
    )
    op.create_index("idx_experiments_domain", "experiments", ["domain"])
    op.create_index("idx_experiments_status", "experiments", ["status"])
    op.create_index("idx_experiments_type", "experiments", ["experiment_type"])
    op.create_index("idx_experiments_plan", "experiments", ["plan_id"])
    op.create_index("idx_experiments_created", "experiments", ["created_at"])
    op.create_index("idx_experiments_creator", "experiments", ["created_by"])

    # ===========================================
    # EXPERIMENT-HYPOTHESES ASSOCIATION TABLE
    # ===========================================

    op.create_table(
        "experiment_hypotheses",
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("experiments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hypotheses.id", ondelete="CASCADE"), primary_key=True),
    )

    # ===========================================
    # EXPERIMENT RESULTS TABLE
    # ===========================================

    op.create_table(
        "experiment_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), server_default="{}"),
        sa.Column("statistics", postgresql.JSONB(), server_default="{}"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("p_value", sa.Float()),
        sa.Column("effect_size", sa.Float()),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_data_path", sa.String(500), nullable=False, server_default=""),
        sa.Column("artifacts", postgresql.JSONB(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_experiment_results_experiment", "experiment_results", ["experiment_id"])
    op.create_index("idx_experiment_results_created", "experiment_results", ["created_at"])

    # ===========================================
    # EXPERIMENT CHECKPOINTS TABLE
    # ===========================================

    op.create_table(
        "experiment_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("state", postgresql.JSONB(), server_default="{}"),
        sa.Column("metrics", postgresql.JSONB(), server_default="{}"),
        sa.Column("checkpoint_path", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_experiment_checkpoints_experiment", "experiment_checkpoints", ["experiment_id"])
    op.create_index("idx_experiment_checkpoints_step", "experiment_checkpoints", ["experiment_id", "step_index"])


def downgrade() -> None:
    op.drop_table("experiment_checkpoints")
    op.drop_table("experiment_results")
    op.drop_table("experiment_hypotheses")
    op.drop_table("experiments")
    op.drop_table("hypotheses")
    op.drop_table("experiment_plans")
