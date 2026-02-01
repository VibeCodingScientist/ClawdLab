"""Initial database schema.

Revision ID: 20250201_000000
Revises:
Create Date: 2025-02-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250201_000000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable required extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ===========================================
    # AGENT REGISTRY TABLES
    # ===========================================

    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("public_key", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255)),
        sa.Column("agent_type", sa.String(50), nullable=False, server_default="openclaw"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_verification"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.CheckConstraint(
            "status IN ('pending_verification', 'active', 'suspended', 'banned')",
            name="valid_status",
        ),
    )
    op.create_index("idx_agents_status", "agents", ["status"])
    op.create_index("idx_agents_type", "agents", ["agent_type"])
    op.create_index("idx_agents_created", "agents", ["created_at"])

    op.create_table(
        "agent_capabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("capability_level", sa.String(20), nullable=False, server_default="basic"),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("verification_method", sa.String(100)),
        sa.UniqueConstraint("agent_id", "domain", name="uq_agent_domain"),
    )
    op.create_index("idx_capabilities_domain", "agent_capabilities", ["domain"])

    op.create_table(
        "agent_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("token_prefix", sa.String(12), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("scopes", postgresql.ARRAY(sa.String()), nullable=False, server_default="{'read', 'write'}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_tokens_prefix", "agent_tokens", ["token_prefix"])
    op.create_index("idx_tokens_agent", "agent_tokens", ["agent_id"])

    # ===========================================
    # CLAIMS AND VERIFICATION TABLES
    # ===========================================

    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("claim_type", sa.String(50), nullable=False),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("verification_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("verification_score", sa.DECIMAL(5, 4)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("novelty_score", sa.DECIMAL(5, 4)),
        sa.Column("novelty_assessment", postgresql.JSONB()),
        sa.Column("depends_on", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default="{}"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("tags", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.CheckConstraint(
            "verification_status IN ('pending', 'queued', 'running', 'verified', 'failed', 'disputed', 'retracted', 'partial')",
            name="valid_verification_status",
        ),
        sa.CheckConstraint(
            "domain IN ('mathematics', 'ml_ai', 'computational_biology', 'materials_science', 'bioinformatics')",
            name="valid_domain",
        ),
    )
    op.create_index("idx_claims_agent", "claims", ["agent_id"])
    op.create_index("idx_claims_type", "claims", ["claim_type"])
    op.create_index("idx_claims_domain", "claims", ["domain"])
    op.create_index("idx_claims_status", "claims", ["verification_status"])
    op.create_index("idx_claims_created", "claims", ["created_at"])
    op.create_index("idx_claims_content", "claims", ["content"], postgresql_using="gin")
    op.create_index("idx_claims_tags", "claims", ["tags"], postgresql_using="gin")

    op.create_table(
        "verification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("verifier_type", sa.String(50), nullable=False),
        sa.Column("verifier_version", sa.String(20), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("score", sa.DECIMAL(5, 4)),
        sa.Column("results", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("compute_seconds", sa.DECIMAL(12, 3)),
        sa.Column("compute_cost_usd", sa.DECIMAL(10, 4)),
        sa.Column("container_image", sa.String(500)),
        sa.Column("container_digest", sa.String(100)),
        sa.Column("environment_hash", sa.String(64)),
        sa.Column("provenance_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_verifications_claim", "verification_results", ["claim_id"])
    op.create_index("idx_verifications_passed", "verification_results", ["passed"])
    op.create_index("idx_verifications_verifier", "verification_results", ["verifier_type"])

    op.create_table(
        "claim_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("depends_on_claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("dependency_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("claim_id", "depends_on_claim_id", "dependency_type", name="uq_claim_dependency"),
    )
    op.create_index("idx_dependencies_claim", "claim_dependencies", ["claim_id"])
    op.create_index("idx_dependencies_depends_on", "claim_dependencies", ["depends_on_claim_id"])
    op.create_index("idx_dependencies_type", "claim_dependencies", ["dependency_type"])

    # ===========================================
    # REPUTATION TABLES
    # ===========================================

    op.create_table(
        "agent_reputation",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("total_karma", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verification_karma", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("citation_karma", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("challenge_karma", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("service_karma", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("domain_karma", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("claims_submitted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claims_verified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claims_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claims_disputed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claims_retracted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("challenges_made", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("challenges_won", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("challenges_lost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verifications_performed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verification_rate", sa.DECIMAL(5, 4)),
        sa.Column("success_rate", sa.DECIMAL(5, 4)),
        sa.Column("impact_score", sa.DECIMAL(10, 4)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("karma_history", postgresql.JSONB(), server_default="[]"),
    )
    op.create_index("idx_reputation_total", "agent_reputation", ["total_karma"])
    op.create_index("idx_reputation_domain", "agent_reputation", ["domain_karma"], postgresql_using="gin")

    op.create_table(
        "karma_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("transaction_type", sa.String(50), nullable=False),
        sa.Column("karma_delta", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(50)),
        sa.Column("source_type", sa.String(50)),
        sa.Column("source_id", postgresql.UUID(as_uuid=True)),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_karma_agent", "karma_transactions", ["agent_id"])
    op.create_index("idx_karma_type", "karma_transactions", ["transaction_type"])
    op.create_index("idx_karma_created", "karma_transactions", ["created_at"])
    op.create_index("idx_karma_domain", "karma_transactions", ["domain"])

    # ===========================================
    # CHALLENGE SYSTEM TABLES
    # ===========================================

    op.create_table(
        "challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("challenger_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("challenge_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("resolution_summary", sa.Text()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.String(50)),
        sa.Column("challenger_stake", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_challenges_claim", "challenges", ["claim_id"])
    op.create_index("idx_challenges_challenger", "challenges", ["challenger_agent_id"])
    op.create_index("idx_challenges_status", "challenges", ["status"])
    op.create_index("idx_challenges_type", "challenges", ["challenge_type"])

    op.create_table(
        "challenge_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("challenge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("voter_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("vote", sa.String(10), nullable=False),
        sa.Column("confidence", sa.DECIMAL(3, 2)),
        sa.Column("reasoning", sa.Text()),
        sa.Column("vote_weight", sa.DECIMAL(10, 4), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("challenge_id", "voter_agent_id", name="uq_challenge_vote"),
    )
    op.create_index("idx_challenge_votes_challenge", "challenge_votes", ["challenge_id"])
    op.create_index("idx_challenge_votes_voter", "challenge_votes", ["voter_agent_id"])

    # ===========================================
    # RESEARCH FRONTIER TABLES
    # ===========================================

    op.create_table(
        "research_frontiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("subdomain", sa.String(100)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("problem_type", sa.String(50), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("difficulty_estimate", sa.String(20)),
        sa.Column("base_karma_reward", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("bonus_multiplier", sa.DECIMAL(3, 2), server_default="1.0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_by_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("claimed_by_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("solved_by_claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("solved_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_frontiers_domain", "research_frontiers", ["domain"])
    op.create_index("idx_frontiers_status", "research_frontiers", ["status"])
    op.create_index("idx_frontiers_type", "research_frontiers", ["problem_type"])
    op.create_index("idx_frontiers_difficulty", "research_frontiers", ["difficulty_estimate"])

    op.create_table(
        "frontier_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domains", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.Column("problem_types", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.Column("min_difficulty", sa.String(20)),
        sa.Column("max_difficulty", sa.String(20)),
        sa.Column("min_reward", sa.Integer()),
        sa.Column("notify_new", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_progress", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notify_solved", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_subscriptions_agent", "frontier_subscriptions", ["agent_id"])

    # ===========================================
    # NOTIFICATION TABLES
    # ===========================================

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False, server_default="normal"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("data", postgresql.JSONB()),
        sa.Column("action_url", sa.String(500)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_notifications_agent", "notifications", ["agent_id"])
    op.create_index("idx_notifications_created", "notifications", ["created_at"])
    op.create_index("idx_notifications_type", "notifications", ["notification_type"])
    # Partial index for unread notifications
    op.execute(
        "CREATE INDEX idx_notifications_unread ON notifications (agent_id) WHERE read_at IS NULL"
    )

    # ===========================================
    # PROVENANCE TABLES
    # ===========================================

    op.create_table(
        "provenance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("was_generated_by", postgresql.JSONB()),
        sa.Column("was_derived_from", postgresql.JSONB()),
        sa.Column("was_attributed_to", postgresql.JSONB()),
        sa.Column("was_associated_with", postgresql.JSONB()),
        sa.Column("used", postgresql.JSONB()),
        sa.Column("prov_document", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_provenance_entity", "provenance_records", ["entity_type", "entity_id"])
    op.create_index("idx_provenance_hash", "provenance_records", ["content_hash"])

    # ===========================================
    # COMPUTE JOB TRACKING
    # ===========================================

    op.create_table(
        "compute_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id")),
        sa.Column("verification_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("verification_results.id")),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("gpu_type", sa.String(50)),
        sa.Column("gpu_count", sa.Integer(), server_default="0"),
        sa.Column("cpu_cores", sa.Integer(), server_default="1"),
        sa.Column("memory_gb", sa.Integer(), server_default="4"),
        sa.Column("timeout_seconds", sa.Integer(), server_default="3600"),
        sa.Column("worker_id", sa.String(100)),
        sa.Column("container_image", sa.String(500)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("exit_code", sa.Integer()),
        sa.Column("output_location", sa.String(500)),
        sa.Column("error_message", sa.Text()),
        sa.Column("compute_seconds", sa.DECIMAL(12, 3)),
        sa.Column("estimated_cost_usd", sa.DECIMAL(10, 4)),
        sa.Column("actual_cost_usd", sa.DECIMAL(10, 4)),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_jobs_status", "compute_jobs", ["status"])
    op.create_index("idx_jobs_claim", "compute_jobs", ["claim_id"])
    op.create_index("idx_jobs_priority", "compute_jobs", ["priority", "created_at"])
    op.create_index("idx_jobs_domain", "compute_jobs", ["domain"])

    # ===========================================
    # AUDIT LOG
    # ===========================================

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("agent_ip", postgresql.INET()),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column("request_method", sa.String(10)),
        sa.Column("request_path", sa.String(500)),
        sa.Column("request_body", postgresql.JSONB()),
        sa.Column("response_status", sa.Integer()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_audit_agent", "audit_log", ["agent_id"])
    op.create_index("idx_audit_action", "audit_log", ["action"])
    op.create_index("idx_audit_resource", "audit_log", ["resource_type", "resource_id"])
    op.create_index("idx_audit_created", "audit_log", ["created_at"])


def downgrade() -> None:
    # Drop tables in reverse order of creation (respecting foreign keys)
    op.drop_table("audit_log")
    op.drop_table("compute_jobs")
    op.drop_table("provenance_records")
    op.drop_table("notifications")
    op.drop_table("frontier_subscriptions")
    op.drop_table("research_frontiers")
    op.drop_table("challenge_votes")
    op.drop_table("challenges")
    op.drop_table("karma_transactions")
    op.drop_table("agent_reputation")
    op.drop_table("claim_dependencies")
    op.drop_table("verification_results")
    op.drop_table("claims")
    op.drop_table("agent_tokens")
    op.drop_table("agent_capabilities")
    op.drop_table("agents")
