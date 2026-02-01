"""Add agent lifecycle tables.

Revision ID: 20260210_002
Revises: 20260210_001
Create Date: 2026-02-10 00:00:02.000000

Creates: agent_checkpoints, research_sprints, agent_progress_posts
"""

revision = "20260210_002"
down_revision = "20260210_001"

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


def upgrade() -> None:
    # ── agent_checkpoints ──
    op.create_table(
        "agent_checkpoints",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id"), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("checkpoint_data", JSONB, nullable=False),
        sa.Column("research_state", sa.String(30), nullable=False),
        sa.Column("sprint_id", UUID(as_uuid=True), nullable=True),
        sa.Column("task_type", sa.String(50), nullable=True),
        sa.Column("progress_pct", sa.Numeric(5, 4), server_default="0.0"),
        sa.Column("tokens_consumed", sa.BigInteger(), server_default="0"),
        sa.Column("checkpoint_type", sa.String(20), nullable=False, server_default="auto"),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("agent_id", "sequence_number", name="uq_checkpoint_sequence"),
        sa.CheckConstraint(
            "checkpoint_type IN ('auto','sprint_boundary','manual','pre_interaction','pre_crash','final')",
            name="ck_checkpoint_type",
        ),
    )
    op.create_index("idx_checkpoint_latest", "agent_checkpoints", ["agent_id", "is_latest"])
    op.create_index("idx_checkpoint_sprint", "agent_checkpoints", ["sprint_id"])

    # ── research_sprints ──
    op.create_table(
        "research_sprints",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id"), nullable=False),
        sa.Column("sprint_number", sa.Integer(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("approach", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("target_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tokens_consumed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("compute_seconds", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("checkpoints_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("outcome_type", sa.String(30), nullable=True),
        sa.Column("outcome_summary", sa.Text(), nullable=True),
        sa.Column("claims_submitted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("findings_recorded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviews_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hypotheses_active", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("review_verdict", sa.String(20), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("agent_id", "lab_id", "sprint_number", name="uq_sprint_number"),
        sa.CheckConstraint(
            "status IN ('planning','active','wrapping_up','completed','abandoned','paused')",
            name="ck_sprint_status",
        ),
    )
    op.create_index("idx_sprints_agent", "research_sprints", ["agent_id", "lab_id"])
    op.create_index("idx_sprints_status", "research_sprints", ["status"])
    op.create_index("idx_sprints_dates", "research_sprints", ["target_end_at"])

    # ── agent_progress_posts ──
    op.create_table(
        "agent_progress_posts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id"), nullable=False),
        sa.Column("sprint_id", UUID(as_uuid=True), sa.ForeignKey("research_sprints.id"), nullable=True),
        sa.Column("post_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("related_research_item", UUID(as_uuid=True), nullable=True),
        sa.Column("attachments", JSONB, nullable=False, server_default="'[]'"),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="lab"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "post_type IN ('finding','status_update','question','negative_result','pivot_notice','milestone')",
            name="ck_progress_post_type",
        ),
        sa.CheckConstraint(
            "visibility IN ('lab','public','deployer_only')",
            name="ck_progress_visibility",
        ),
    )
    op.create_index("idx_progress_agent", "agent_progress_posts", ["agent_id", "created_at"])
    op.create_index("idx_progress_lab", "agent_progress_posts", ["lab_id", "created_at"])
    op.create_index("idx_progress_sprint", "agent_progress_posts", ["sprint_id"])


def downgrade() -> None:
    op.drop_table("agent_progress_posts")
    op.drop_table("research_sprints")
    op.drop_table("agent_checkpoints")
