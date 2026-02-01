"""Add labs, role cards, memberships, research items, roundtable, workspace,
citations, and protocol versions tables.

Revision ID: 20260209_001
Revises: 20260206_001
Create Date: 2026-02-09 00:00:01.000000

This migration implements the Labs system for collaborative agent research:

New Tables:
-----------
1. labs: Research lab where agents collaborate
   - Governance types: democratic, pi_led, consensus
   - Visibility: public, unlisted, private
   - GIN index on domains array

2. lab_role_cards: Specialized role definitions within a lab
   - Archetypes: pi, theorist, experimentalist, critic, etc.
   - JSONB fields for inputs, outputs, permissions, metrics

3. lab_memberships: Agent-to-lab membership records
   - Unique constraint on (lab_id, agent_id)
   - Vote weight and lab-local karma

4. lab_research_items: Research items proposed within a lab
   - 10 valid statuses from proposed through withdrawn
   - Links to resulting claims

5. roundtable_entries: Append-only discussion entries
   - Self-referential threading via parent_entry_id
   - Entry types: proposal, argument, counter_argument, etc.
   - No updated_at (append-only by design)

6. lab_workspace_state: Agent presence/position in lab workspace
   - Zones: ideation, library, bench, roundtable, whiteboard, presentation
   - Unique constraint on (lab_id, agent_id)

7. citations: Cross-claim citation graph
   - Optional lab context
   - Unique constraint on (citing_claim_id, cited_claim_id)

8. protocol_versions: Versioned research protocol definitions
   - Unique constraint on (protocol_name, version)

Schema Changes:
---------------
- claims: Added lab_id (UUID FK labs.id, nullable)
- agent_capabilities: Added capability_embedding (JSONB, nullable)
- security_events: Added endpoint (String 500), payload_snippet (Text)

Extensions:
-----------
- pgvector: CREATE EXTENSION IF NOT EXISTS vector

Indexes:
--------
All tables include appropriate indexes for common query patterns.
See individual CREATE TABLE statements for index definitions.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260209_001"
down_revision = "20260206_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===========================================
    # PGVECTOR EXTENSION
    # ===========================================
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ===========================================
    # LABS
    # ===========================================
    op.create_table(
        "labs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column(
            "governance_type",
            sa.String(20),
            nullable=False,
            server_default="democratic",
        ),
        sa.Column(
            "domains",
            postgresql.ARRAY(sa.String),
            server_default="{}",
        ),
        sa.Column("rules", postgresql.JSONB, server_default="{}"),
        sa.Column(
            "visibility",
            sa.String(20),
            nullable=False,
            server_default="public",
        ),
        sa.Column(
            "karma_requirement",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "governance_type IN ('democratic', 'pi_led', 'consensus')",
            name="valid_governance_type",
        ),
        sa.CheckConstraint(
            "visibility IN ('public', 'unlisted', 'private')",
            name="valid_lab_visibility",
        ),
    )
    op.create_index("idx_labs_slug", "labs", ["slug"])
    op.create_index(
        "idx_labs_domains", "labs", ["domains"], postgresql_using="gin"
    )
    op.create_index("idx_labs_visibility", "labs", ["visibility"])
    op.create_index("idx_labs_created_by", "labs", ["created_by"])

    # ===========================================
    # LAB ROLE CARDS
    # ===========================================
    op.create_table(
        "lab_role_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lab_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("labs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("archetype", sa.String(30), nullable=False),
        sa.Column("persona", sa.Text),
        sa.Column("pipeline_layer", sa.String(30), nullable=False),
        sa.Column("inputs", postgresql.JSONB, server_default="{}"),
        sa.Column("outputs", postgresql.JSONB, server_default="{}"),
        sa.Column("hard_bans", postgresql.JSONB, server_default="{}"),
        sa.Column("escalation_triggers", postgresql.JSONB, server_default="{}"),
        sa.Column("metrics", postgresql.JSONB, server_default="{}"),
        sa.Column("skill_tags", postgresql.JSONB, server_default="{}"),
        sa.Column("permissions", postgresql.JSONB, server_default="{}"),
        sa.Column(
            "max_holders",
            sa.Integer,
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "min_karma",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "archetype IN ('pi', 'theorist', 'experimentalist', 'critic', 'synthesizer', 'scout', 'mentor', 'technician', 'generalist')",
            name="valid_archetype",
        ),
    )
    op.create_index("idx_role_cards_lab", "lab_role_cards", ["lab_id"])
    op.create_index("idx_role_cards_archetype", "lab_role_cards", ["archetype"])

    # ===========================================
    # LAB MEMBERSHIPS
    # ===========================================
    op.create_table(
        "lab_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lab_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("labs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_card_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lab_role_cards.id"),
            nullable=True,
        ),
        sa.Column(
            "lab_karma",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "vote_weight",
            sa.DECIMAL(5, 2),
            nullable=False,
            server_default="1.0",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("lab_id", "agent_id", name="uq_lab_membership"),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'left', 'invited')",
            name="valid_membership_status",
        ),
    )
    op.create_index("idx_memberships_lab", "lab_memberships", ["lab_id"])
    op.create_index("idx_memberships_agent", "lab_memberships", ["agent_id"])
    op.create_index(
        "idx_memberships_status", "lab_memberships", ["lab_id", "status"]
    )

    # ===========================================
    # LAB RESEARCH ITEMS
    # ===========================================
    op.create_table(
        "lab_research_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lab_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("labs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("claim_type", sa.String(50)),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column(
            "proposed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column(
            "assigned_to",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=True,
        ),
        sa.Column(
            "resulting_claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'under_debate', 'approved', 'in_progress', 'submitted', 'under_review', 'verified', 'rejected', 'archived', 'withdrawn')",
            name="valid_research_status",
        ),
    )
    op.create_index(
        "idx_research_items_lab", "lab_research_items", ["lab_id"]
    )
    op.create_index(
        "idx_research_items_status", "lab_research_items", ["lab_id", "status"]
    )
    op.create_index(
        "idx_research_items_proposed_by", "lab_research_items", ["proposed_by"]
    )

    # ===========================================
    # ROUNDTABLE ENTRIES
    # ===========================================
    op.create_table(
        "roundtable_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "research_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lab_research_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column(
            "parent_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roundtable_entries.id"),
            nullable=True,
        ),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("vote_value", sa.Integer),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "entry_type IN ('proposal', 'argument', 'counter_argument', 'evidence', 'question', 'synthesis', 'vote')",
            name="valid_entry_type",
        ),
        sa.CheckConstraint(
            "vote_value IS NULL OR vote_value IN (-1, 0, 1)",
            name="valid_roundtable_vote",
        ),
    )
    op.create_index(
        "idx_roundtable_item", "roundtable_entries", ["research_item_id"]
    )
    op.create_index(
        "idx_roundtable_author", "roundtable_entries", ["author_id"]
    )
    op.create_index(
        "idx_roundtable_parent", "roundtable_entries", ["parent_entry_id"]
    )

    # ===========================================
    # LAB WORKSPACE STATE
    # ===========================================
    op.create_table(
        "lab_workspace_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lab_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("labs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "zone",
            sa.String(30),
            nullable=False,
            server_default="ideation",
        ),
        sa.Column("position_x", sa.DECIMAL(8, 2), server_default="0"),
        sa.Column("position_y", sa.DECIMAL(8, 2), server_default="0"),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="idle",
        ),
        sa.Column(
            "last_action_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("lab_id", "agent_id", name="uq_workspace_agent"),
        sa.CheckConstraint(
            "zone IN ('ideation', 'library', 'bench', 'roundtable', 'whiteboard', 'presentation')",
            name="valid_workspace_zone",
        ),
    )
    op.create_index("idx_workspace_lab", "lab_workspace_state", ["lab_id"])
    op.create_index("idx_workspace_agent", "lab_workspace_state", ["agent_id"])

    # ===========================================
    # CITATIONS
    # ===========================================
    op.create_table(
        "citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "citing_claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id"),
            nullable=False,
        ),
        sa.Column(
            "cited_claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id"),
            nullable=False,
        ),
        sa.Column(
            "citing_lab_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("labs.id"),
            nullable=True,
        ),
        sa.Column("context", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "citing_claim_id", "cited_claim_id", name="uq_citation"
        ),
    )
    op.create_index("idx_citations_citing", "citations", ["citing_claim_id"])
    op.create_index("idx_citations_cited", "citations", ["cited_claim_id"])
    op.create_index("idx_citations_lab", "citations", ["citing_lab_id"])

    # ===========================================
    # PROTOCOL VERSIONS
    # ===========================================
    op.create_table(
        "protocol_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("protocol_name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "protocol_name", "version", name="uq_protocol_version"
        ),
    )
    op.create_index(
        "idx_protocol_name", "protocol_versions", ["protocol_name"]
    )

    # ===========================================
    # ALTER EXISTING TABLES
    # ===========================================

    # claims: add lab_id
    op.add_column(
        "claims",
        sa.Column(
            "lab_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("labs.id"),
            nullable=True,
        ),
    )
    op.create_index("idx_claims_lab", "claims", ["lab_id"])

    # agent_capabilities: add capability_embedding
    op.add_column(
        "agent_capabilities",
        sa.Column("capability_embedding", postgresql.JSONB),
    )

    # security_events: add endpoint and payload_snippet
    op.add_column(
        "security_events",
        sa.Column("endpoint", sa.String(500)),
    )
    op.add_column(
        "security_events",
        sa.Column("payload_snippet", sa.Text),
    )


def downgrade() -> None:
    # ===========================================
    # REVERT ALTER EXISTING TABLES
    # ===========================================
    op.drop_column("security_events", "payload_snippet")
    op.drop_column("security_events", "endpoint")
    op.drop_column("agent_capabilities", "capability_embedding")
    op.drop_index("idx_claims_lab", table_name="claims")
    op.drop_column("claims", "lab_id")

    # ===========================================
    # DROP NEW TABLES IN REVERSE ORDER
    # ===========================================
    op.drop_table("protocol_versions")
    op.drop_table("citations")
    op.drop_table("lab_workspace_state")
    op.drop_table("roundtable_entries")
    op.drop_table("lab_research_items")
    op.drop_table("lab_memberships")
    op.drop_table("lab_role_cards")
    op.drop_table("labs")

    # ===========================================
    # DROP EXTENSION
    # ===========================================
    op.execute("DROP EXTENSION IF EXISTS vector")
