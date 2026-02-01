"""Add experience system tables.

Revision ID: 20260210_001
Revises: 20260209_002
Create Date: 2026-02-10 00:00:01.000000

Creates: agent_experience, agent_xp_events, agent_milestones, deployers
Modifies: agents (adds deployer_id column)
"""

revision = "20260210_001"
down_revision = "20260209_002"

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


def upgrade() -> None:
    # ── deployers table ──
    op.create_table(
        "deployers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("external_id", sa.String(255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("portfolio_karma", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("agent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tier", sa.String(20), nullable=False, server_default="novice"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # ── agents.deployer_id ──
    op.add_column("agents", sa.Column("deployer_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_agents_deployer", "agents", "deployers", ["deployer_id"], ["id"])
    op.create_index("idx_agents_deployer", "agents", ["deployer_id"])

    # ── agent_experience table ──
    op.create_table(
        "agent_experience",
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
        # Global XP
        sa.Column("total_xp", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("global_level", sa.Integer(), nullable=False, server_default="1"),
        # Domain XP
        sa.Column("math_xp", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("math_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ml_ai_xp", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("ml_ai_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comp_bio_xp", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("comp_bio_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("materials_xp", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("materials_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bioinformatics_xp", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("bioinformatics_level", sa.Integer(), nullable=False, server_default="0"),
        # Role XP
        sa.Column("theory_xp", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("execution_xp", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("review_xp", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("scouting_xp", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("coordination_xp", sa.BigInteger(), nullable=False, server_default="0"),
        # Tier & prestige
        sa.Column("tier", sa.String(20), nullable=False, server_default="novice"),
        sa.Column("prestige_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prestige_bonus", sa.Numeric(5, 4), nullable=False, server_default="1.0000"),
        # Tracking
        sa.Column("last_xp_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        # Constraints
        sa.CheckConstraint(
            "tier IN ('novice','contributor','specialist','expert','master','grandmaster')",
            name="ck_experience_tier",
        ),
    )
    op.create_index("idx_experience_level", "agent_experience", ["global_level"], postgresql_using="btree")
    op.create_index("idx_experience_tier", "agent_experience", ["tier"])

    # ── agent_xp_events table ──
    op.create_table(
        "agent_xp_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("xp_amount", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(30), nullable=True),
        sa.Column("role_category", sa.String(20), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("lab_slug", sa.String(100), nullable=True),
        sa.Column("multiplier", sa.Numeric(5, 4), nullable=False, server_default="1.0000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_xp_events_agent", "agent_xp_events", ["agent_id", "created_at"])
    op.create_index("idx_xp_events_source", "agent_xp_events", ["source_type"])

    # ── agent_milestones table ──
    op.create_table(
        "agent_milestones",
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("milestone_slug", sa.String(100), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("metadata", JSONB, nullable=False, server_default="'{}'"),
        sa.PrimaryKeyConstraint("agent_id", "milestone_slug"),
    )


def downgrade() -> None:
    op.drop_table("agent_milestones")
    op.drop_table("agent_xp_events")
    op.drop_table("agent_experience")
    op.drop_index("idx_agents_deployer", table_name="agents")
    op.drop_constraint("fk_agents_deployer", "agents", type_="foreignkey")
    op.drop_column("agents", "deployer_id")
    op.drop_table("deployers")
