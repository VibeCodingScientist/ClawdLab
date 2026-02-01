"""Add knowledge management tables.

Revision ID: 20250202_000003
Revises: 20250202_000002
Create Date: 2025-02-02 00:00:03.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250202_000003"
down_revision: Union[str, None] = "20250202_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # KNOWLEDGE ENTRIES TABLE
    # ===========================================

    op.create_table(
        "knowledge_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("entry_type", sa.String(50), nullable=False, server_default="fact"),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.Column("tags", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("embedding", postgresql.ARRAY(sa.Float())),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_knowledge_entries_title", "knowledge_entries", ["title"])
    op.create_index("idx_knowledge_entries_domain", "knowledge_entries", ["domain"])
    op.create_index("idx_knowledge_entries_type", "knowledge_entries", ["entry_type"])
    op.create_index("idx_knowledge_entries_status", "knowledge_entries", ["verification_status"])
    op.create_index("idx_knowledge_entries_archived", "knowledge_entries", ["is_archived"])
    op.create_index("idx_knowledge_entries_created", "knowledge_entries", ["created_at"])
    op.create_index("idx_knowledge_entries_keywords", "knowledge_entries", ["keywords"], postgresql_using="gin")
    op.create_index("idx_knowledge_entries_tags", "knowledge_entries", ["tags"], postgresql_using="gin")

    # ===========================================
    # CITATIONS TABLE
    # ===========================================

    op.create_table(
        "citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("source_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("citation_type", sa.String(50), nullable=False, server_default="reference"),
        sa.Column("context", sa.Text(), nullable=False, server_default=""),
        sa.Column("page_number", sa.Integer()),
        sa.Column("section", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_citations_source", "citations", ["source_entry_id"])
    op.create_index("idx_citations_target", "citations", ["target_entry_id"])
    op.create_index("idx_citations_type", "citations", ["citation_type"])

    # ===========================================
    # KNOWLEDGE RELATIONSHIPS TABLE
    # ===========================================

    op.create_table(
        "knowledge_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("source_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("bidirectional", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_knowledge_relationships_source", "knowledge_relationships", ["source_entry_id"])
    op.create_index("idx_knowledge_relationships_target", "knowledge_relationships", ["target_entry_id"])
    op.create_index("idx_knowledge_relationships_type", "knowledge_relationships", ["relationship_type"])

    # ===========================================
    # KNOWLEDGE PROVENANCE RECORDS TABLE
    # (separate from existing provenance_records for W3C PROV)
    # ===========================================

    op.create_table(
        "knowledge_provenance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("previous_state", postgresql.JSONB()),
        sa.Column("new_state", postgresql.JSONB()),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_knowledge_provenance_entry", "knowledge_provenance", ["entry_id"])
    op.create_index("idx_knowledge_provenance_action", "knowledge_provenance", ["action"])
    op.create_index("idx_knowledge_provenance_timestamp", "knowledge_provenance", ["timestamp"])

    # ===========================================
    # SOURCE REFERENCES TABLE
    # ===========================================

    op.create_table(
        "source_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("authors", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.Column("url", sa.String(1000), nullable=False, server_default=""),
        sa.Column("doi", sa.String(255), nullable=False, server_default=""),
        sa.Column("publication_date", sa.DateTime(timezone=True)),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_source_references_type", "source_references", ["source_type"])
    op.create_index("idx_source_references_source_id", "source_references", ["source_id"])
    op.create_index("idx_source_references_doi", "source_references", ["doi"])

    # ===========================================
    # ENTRY-SOURCE REFERENCES ASSOCIATION TABLE
    # ===========================================

    op.create_table(
        "entry_source_references",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_entries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_references.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("entry_source_references")
    op.drop_table("source_references")
    op.drop_table("knowledge_provenance")
    op.drop_table("knowledge_relationships")
    op.drop_table("citations")
    op.drop_table("knowledge_entries")
