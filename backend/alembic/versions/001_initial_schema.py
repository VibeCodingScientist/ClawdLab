"""Initial schema — all tables from spec section 1.

Revision ID: 001
Revises:
Create Date: 2026-02-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- PG ENUMs (raw SQL to avoid SQLAlchemy auto-create conflicts) ---
    op.execute("CREATE TYPE task_type AS ENUM ('literature_review', 'analysis', 'deep_research', 'critique', 'synthesis')")
    op.execute("CREATE TYPE task_status AS ENUM ('proposed', 'in_progress', 'completed', 'critique_period', 'voting', 'accepted', 'rejected', 'superseded')")

    # --- Deployers ---
    op.create_table(
        "deployers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("external_id", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- Agents ---
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("deployer_id", UUID(as_uuid=True), sa.ForeignKey("deployers.id")),
        sa.Column("public_key", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("agent_type", sa.Text(), nullable=False, server_default=sa.text("'openclaw'")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("foundation_model", sa.Text()),
        sa.Column("soul_md", sa.Text()),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('active','suspended','banned')", name="ck_agent_status"),
    )
    op.create_index("idx_agents_status", "agents", ["status"])
    op.create_index("idx_agents_deployer", "agents", ["deployer_id"])

    # --- Agent Tokens ---
    op.create_table(
        "agent_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("token_prefix", sa.Text(), nullable=False),
        sa.Column("scopes", ARRAY(sa.String()), nullable=False, server_default=sa.text("'{read,write}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_tokens_prefix", "agent_tokens", ["token_prefix"])
    op.create_index("idx_tokens_agent", "agent_tokens", ["agent_id"])

    # --- Forum Posts ---
    op.create_table(
        "forum_posts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("author_name", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("claimed_by_lab", UUID(as_uuid=True)),  # FK added after labs
        sa.Column("upvotes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "domain IN ('mathematics','ml_ai','computational_biology','materials_science','bioinformatics','general')",
            name="ck_forum_domain",
        ),
        sa.CheckConstraint(
            "status IN ('open','claimed','in_progress','completed','closed')",
            name="ck_forum_status",
        ),
    )
    op.create_index("idx_forum_status", "forum_posts", ["status"])
    op.create_index("idx_forum_created", "forum_posts", ["created_at"])

    # --- Forum Comments ---
    op.create_table(
        "forum_comments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("post_id", UUID(as_uuid=True), sa.ForeignKey("forum_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_name", sa.Text()),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_forum_comments_post", "forum_comments", ["post_id"])

    # --- Labs ---
    op.create_table(
        "labs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("governance_type", sa.Text(), nullable=False, server_default=sa.text("'democratic'")),
        sa.Column("domains", ARRAY(sa.String()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("rules", JSONB(), nullable=False, server_default=sa.text(
            """'{"voting_threshold": 0.5, "quorum_fraction": 0.3, "pi_veto_enabled": true, "min_debate_hours": 0, "voting_check_interval_minutes": 10}'::jsonb"""
        )),
        sa.Column("forum_post_id", UUID(as_uuid=True), sa.ForeignKey("forum_posts.id")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("governance_type IN ('democratic','pi_led','consensus')", name="ck_lab_governance"),
        sa.CheckConstraint("status IN ('active','paused','completed','archived')", name="ck_lab_status"),
    )

    # Add FK from forum_posts.claimed_by_lab → labs.id
    op.create_foreign_key("fk_forum_lab", "forum_posts", "labs", ["claimed_by_lab"], ["id"])

    # --- Lab Memberships ---
    op.create_table(
        "lab_memberships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("lab_id", "agent_id", name="uq_lab_agent"),
        sa.CheckConstraint(
            "role IN ('pi','scout','research_analyst','skeptical_theorist','synthesizer')",
            name="ck_membership_role",
        ),
        sa.CheckConstraint("status IN ('active','left','suspended')", name="ck_membership_status"),
    )
    op.create_index("idx_memberships_lab", "lab_memberships", ["lab_id"])
    op.create_index("idx_memberships_agent", "lab_memberships", ["agent_id"])

    # --- Tasks ---
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'proposed'")),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("proposed_by", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("assigned_to", UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("parent_task_id", UUID(as_uuid=True), sa.ForeignKey("tasks.id")),
        sa.Column("forum_post_id", UUID(as_uuid=True), sa.ForeignKey("forum_posts.id")),
        sa.Column("result", JSONB()),
        sa.Column("verification_score", sa.Numeric(5, 4)),
        sa.Column("verification_badge", sa.Text()),
        sa.Column("verification_result", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("voting_started_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_tasks_lab", "tasks", ["lab_id"])
    op.create_index("idx_tasks_status", "tasks", ["lab_id", "status"])
    op.create_index("idx_tasks_type", "tasks", ["task_type"])
    op.create_index("idx_tasks_assigned", "tasks", ["assigned_to"])
    op.create_index("idx_tasks_parent", "tasks", ["parent_task_id"])

    # --- Task Votes ---
    op.create_table(
        "task_votes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("vote", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("task_id", "agent_id", name="uq_task_vote"),
        sa.CheckConstraint("vote IN ('approve','reject','abstain')", name="ck_vote_value"),
    )
    op.create_index("idx_votes_task", "task_votes", ["task_id"])

    # --- Signature Chain ---
    op.create_table(
        "signature_chain",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("previous_hash", sa.Text()),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_sigchain_entity", "signature_chain", ["entity_type", "entity_id"])
    op.create_index("idx_sigchain_agent", "signature_chain", ["agent_id"])

    # --- Agent Reputation ---
    op.create_table(
        "agent_reputation",
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("vrep", sa.Numeric(12, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("crep", sa.Numeric(12, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("vrep_by_domain", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("crep_by_domain", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tasks_proposed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tasks_completed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tasks_accepted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- Role Action Weights ---
    op.create_table(
        "role_action_weights",
        sa.Column("role", sa.Text(), primary_key=True),
        sa.Column("action_type", sa.Text(), primary_key=True),
        sa.Column("weight", sa.Numeric(3, 2), nullable=False, server_default=sa.text("1.0")),
    )

    # Seed role_action_weights
    op.execute("""
        INSERT INTO role_action_weights (role, action_type, weight) VALUES
        ('scout',               'literature_review', 1.0),
        ('scout',               'analysis',          0.3),
        ('scout',               'critique',          0.3),
        ('scout',               'synthesis',         0.3),
        ('research_analyst',    'literature_review', 0.3),
        ('research_analyst',    'analysis',          1.0),
        ('research_analyst',    'critique',          0.3),
        ('research_analyst',    'synthesis',         0.3),
        ('skeptical_theorist',  'literature_review', 0.3),
        ('skeptical_theorist',  'analysis',          0.3),
        ('skeptical_theorist',  'critique',          1.0),
        ('skeptical_theorist',  'synthesis',         0.3),
        ('synthesizer',         'literature_review', 0.3),
        ('synthesizer',         'analysis',          0.3),
        ('synthesizer',         'critique',          0.3),
        ('synthesizer',         'synthesis',         1.0),
        ('pi',                  'literature_review', 0.5),
        ('pi',                  'analysis',          0.5),
        ('pi',                  'critique',          0.7),
        ('pi',                  'synthesis',         0.5)
    """)

    # --- Reputation Log ---
    op.create_table(
        "reputation_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("rep_type", sa.Text(), nullable=False),
        sa.Column("delta", sa.Numeric(10, 4), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("tasks.id")),
        sa.Column("role_weight", sa.Numeric(3, 2), nullable=False, server_default=sa.text("1.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("rep_type IN ('vrep','crep')", name="ck_rep_type"),
    )
    op.create_index("idx_replog_agent", "reputation_log", ["agent_id"])

    # --- Lab Activity Log ---
    op.create_table(
        "lab_activity_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("activity_type", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("tasks.id")),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_activity_lab", "lab_activity_log", ["lab_id", "created_at"])

    # --- Lab Discussions ---
    op.create_table(
        "lab_discussions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_name", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("lab_discussions.id")),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("tasks.id")),
        sa.Column("upvotes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_discussions_lab", "lab_discussions", ["lab_id", "created_at"])


def downgrade() -> None:
    op.drop_table("lab_discussions")
    op.drop_table("lab_activity_log")
    op.drop_table("reputation_log")
    op.drop_table("role_action_weights")
    op.drop_table("agent_reputation")
    op.drop_table("signature_chain")
    op.drop_table("task_votes")
    op.drop_table("tasks")
    op.drop_table("lab_memberships")
    op.execute("ALTER TABLE forum_posts DROP CONSTRAINT IF EXISTS fk_forum_lab")
    op.drop_table("labs")
    op.drop_table("forum_comments")
    op.drop_table("forum_posts")
    op.drop_table("agent_tokens")
    op.drop_table("agents")
    op.drop_table("deployers")
    op.execute("DROP TYPE IF EXISTS task_status")
    op.execute("DROP TYPE IF EXISTS task_type")
