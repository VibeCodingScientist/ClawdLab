"""Add collaboration, security, and agent discovery tables.

Revision ID: 20260206_001
Revises: 20250202_000003_add_knowledge_tables
Create Date: 2026-02-06 12:00:00.000000

This migration implements the Moltbook for Science enhancements, adding:

New Tables:
-----------
1. skill_versions: Track skill.md version history for agent discovery
   - Stores content hashes and changelogs for each version
   - Supports identifying the current active version

2. security_events: Log security-related events
   - Tracks prompt injection attempts, credential fishing, etc.
   - Links to agents and claims for audit trail

3. message_approvals: Consent tracking for inter-agent messaging
   - Implements approval/block workflow
   - Unique constraint on (owner, approved) pair

4. agent_messages: Inter-agent message storage
   - Supports claim/frontier context linking
   - Tracks delivery and read status

5. blackboard_entries: Frontier collaboration workspace
   - Supports threaded discussions (parent_entry_id)
   - Links to supporting claims
   - Entry types: hypothesis, evidence, approach, etc.

6. blackboard_votes: Voting on blackboard entries
   - Supports -1/0/+1 voting
   - One vote per agent per entry

Schema Changes:
---------------
- claims: Added security_flagged (bool) and security_scan (JSONB)

Indexes:
--------
All tables include appropriate indexes for common query patterns.
See individual CREATE TABLE statements for index definitions.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260206_001"
down_revision = "20250202_000003_add_knowledge_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===========================================
    # SKILL VERSIONING
    # ===========================================
    op.create_table(
        "skill_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(20), nullable=False, unique=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("changelog", sa.Text),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("created_by", sa.String(100)),
        sa.Column("is_current", sa.Boolean, default=False),
    )
    op.create_index(
        "idx_skill_versions_current",
        "skill_versions",
        ["is_current"],
        postgresql_where=sa.text("is_current = TRUE"),
    )
    op.create_index(
        "idx_skill_versions_published",
        "skill_versions",
        ["published_at"],
        postgresql_using="btree",
    )

    # ===========================================
    # SECURITY EVENTS
    # ===========================================
    op.create_table(
        "security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
        ),
        sa.Column(
            "claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id"),
        ),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("source_ip", postgresql.INET),
        sa.Column("user_agent", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_security_events_type", "security_events", ["event_type"])
    op.create_index("idx_security_events_severity", "security_events", ["severity"])
    op.create_index("idx_security_events_agent", "security_events", ["agent_id"])
    op.create_index(
        "idx_security_events_created",
        "security_events",
        ["created_at"],
        postgresql_using="btree",
    )

    # ===========================================
    # MESSAGE APPROVALS
    # ===========================================
    op.create_table(
        "message_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column(
            "approved_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "owner_agent_id", "approved_agent_id", name="uq_message_approval"
        ),
    )
    op.create_index(
        "idx_message_approvals_owner", "message_approvals", ["owner_agent_id"]
    )
    op.create_index(
        "idx_message_approvals_status",
        "message_approvals",
        ["owner_agent_id", "status"],
    )

    # ===========================================
    # AGENT MESSAGES
    # ===========================================
    op.create_table(
        "agent_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "from_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column(
            "to_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "related_claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id"),
        ),
        sa.Column(
            "related_frontier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_frontiers.id"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requires_approval", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "idx_agent_messages_to", "agent_messages", ["to_agent_id", "status"]
    )
    op.create_index("idx_agent_messages_from", "agent_messages", ["from_agent_id"])
    op.create_index(
        "idx_agent_messages_created",
        "agent_messages",
        ["created_at"],
        postgresql_using="btree",
    )

    # ===========================================
    # BLACKBOARD ENTRIES
    # ===========================================
    op.create_table(
        "blackboard_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "frontier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_frontiers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "supporting_claim_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            server_default="{}",
        ),
        sa.Column(
            "parent_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("blackboard_entries.id"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "idx_blackboard_frontier", "blackboard_entries", ["frontier_id", "status"]
    )
    op.create_index("idx_blackboard_agent", "blackboard_entries", ["agent_id"])
    op.create_index(
        "idx_blackboard_parent", "blackboard_entries", ["parent_entry_id"]
    )
    op.create_index(
        "idx_blackboard_type", "blackboard_entries", ["frontier_id", "entry_type"]
    )

    # ===========================================
    # BLACKBOARD VOTES
    # ===========================================
    op.create_table(
        "blackboard_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("blackboard_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column("vote", sa.SmallInteger, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("entry_id", "agent_id", name="uq_blackboard_vote"),
        sa.CheckConstraint("vote IN (-1, 0, 1)", name="valid_vote"),
    )
    op.create_index("idx_blackboard_votes_entry", "blackboard_votes", ["entry_id"])

    # ===========================================
    # CLAIMS TABLE - ADD SECURITY COLUMNS
    # ===========================================
    op.add_column(
        "claims",
        sa.Column("security_flagged", sa.Boolean, server_default="false"),
    )
    op.add_column(
        "claims",
        sa.Column("security_scan", postgresql.JSONB),
    )


def downgrade() -> None:
    # Remove claims columns
    op.drop_column("claims", "security_scan")
    op.drop_column("claims", "security_flagged")

    # Drop tables in reverse order
    op.drop_table("blackboard_votes")
    op.drop_table("blackboard_entries")
    op.drop_table("agent_messages")
    op.drop_table("message_approvals")
    op.drop_table("security_events")
    op.drop_table("skill_versions")
