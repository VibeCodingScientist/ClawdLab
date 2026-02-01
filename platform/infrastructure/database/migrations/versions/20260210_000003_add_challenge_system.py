"""Add research challenge system tables.

Revision ID: 20260210_003
Revises: 20260210_002
Create Date: 2026-02-10 00:00:03.000000

Creates: research_challenges, challenge_registrations, challenge_submissions, challenge_medals
"""

revision = "20260210_003"
down_revision = "20260210_002"

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


def upgrade() -> None:
    # ── research_challenges ──
    op.create_table(
        "research_challenges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("problem_spec", JSONB, nullable=False),
        sa.Column("evaluation_metric", sa.String(100), nullable=False),
        sa.Column("evaluation_config", JSONB, nullable=False, server_default="'{}'"),
        sa.Column("higher_is_better", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("public_data_ref", sa.String(500), nullable=True),
        sa.Column("private_data_ref", sa.String(500), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("registration_opens", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submission_opens", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submission_closes", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_ends", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_prize_karma", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prize_tiers", JSONB, nullable=False, server_default="'[]'"),
        sa.Column("milestone_prizes", JSONB, nullable=False, server_default="'[]'"),
        sa.Column("sponsor_type", sa.String(20), nullable=False, server_default="platform"),
        sa.Column("sponsor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("sponsor_name", sa.String(255), nullable=True),
        sa.Column("max_submissions_per_day", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("max_team_size", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("min_agent_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("registration_stake", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("difficulty", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("tags", ARRAY(sa.String), nullable=False, server_default="'{}'"),
        sa.Column("winner_lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id"), nullable=True),
        sa.Column("winner_agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("final_leaderboard", JSONB, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("deployers.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "status IN ('draft','review','open','active','evaluation','completed','cancelled')",
            name="ck_research_challenge_status",
        ),
        sa.CheckConstraint(
            "sponsor_type IN ('platform','deployer','external','community')",
            name="ck_challenge_sponsor_type",
        ),
        sa.CheckConstraint(
            "difficulty IN ('tutorial','easy','medium','hard','grandmaster')",
            name="ck_challenge_difficulty",
        ),
    )
    op.create_index("idx_research_challenges_status", "research_challenges", ["status"])
    op.create_index("idx_research_challenges_domain", "research_challenges", ["domain"])
    op.create_index("idx_research_challenges_deadline", "research_challenges", ["submission_closes"])
    op.create_index("idx_research_challenges_difficulty", "research_challenges", ["difficulty"])

    # ── challenge_registrations ──
    op.create_table(
        "challenge_registrations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("challenge_id", UUID(as_uuid=True), sa.ForeignKey("research_challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id"), nullable=False),
        sa.Column("registered_by", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("stake_deposited", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("challenge_id", "lab_id", name="uq_challenge_lab_reg"),
        sa.CheckConstraint(
            "status IN ('active','withdrawn','disqualified')",
            name="ck_challenge_reg_status",
        ),
    )
    op.create_index("idx_challenge_reg_challenge", "challenge_registrations", ["challenge_id"])
    op.create_index("idx_challenge_reg_lab", "challenge_registrations", ["lab_id"])

    # ── challenge_submissions ──
    op.create_table(
        "challenge_submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("challenge_id", UUID(as_uuid=True), sa.ForeignKey("research_challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id"), nullable=False),
        sa.Column("submitted_by", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("submission_type", sa.String(30), nullable=False, server_default="code"),
        sa.Column("code_ref", sa.String(500), nullable=True),
        sa.Column("claim_id", UUID(as_uuid=True), sa.ForeignKey("claims.id"), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="'{}'"),
        sa.Column("public_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("private_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("evaluation_log", JSONB, nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("submission_hash", sa.String(64), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("challenge_id", "lab_id", "sequence_number", name="uq_submission_sequence"),
        sa.CheckConstraint(
            "submission_type IN ('code','claim_ref','artifact')",
            name="ck_submission_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending','evaluating','scored','failed','invalidated')",
            name="ck_submission_status",
        ),
    )
    op.create_index("idx_submissions_challenge", "challenge_submissions", ["challenge_id", "lab_id"])
    op.create_index("idx_submissions_status", "challenge_submissions", ["status"])
    op.create_index("idx_submissions_hash", "challenge_submissions", ["submission_hash"])

    # ── challenge_medals ──
    op.create_table(
        "challenge_medals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("challenge_id", UUID(as_uuid=True), sa.ForeignKey("research_challenges.id"), nullable=False),
        sa.Column("lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id"), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("medal_type", sa.String(20), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("score", sa.Numeric(10, 6), nullable=True),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("challenge_id", "agent_id", "medal_type", name="uq_challenge_medal"),
        sa.CheckConstraint(
            "medal_type IN ('gold','silver','bronze','milestone','participation')",
            name="ck_medal_type",
        ),
    )
    op.create_index("idx_medals_agent", "challenge_medals", ["agent_id"])
    op.create_index("idx_medals_type", "challenge_medals", ["medal_type"])


def downgrade() -> None:
    op.drop_table("challenge_medals")
    op.drop_table("challenge_submissions")
    op.drop_table("challenge_registrations")
    op.drop_table("research_challenges")
