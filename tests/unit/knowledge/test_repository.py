"""Unit tests for KnowledgeRepository."""

import asyncio
from datetime import datetime

import pytest

from platform.knowledge.repository import KnowledgeRepository
from platform.knowledge.base import (
    Citation,
    EntryType,
    KnowledgeEntry,
    ProvenanceRecord,
    Relationship,
    RelationshipType,
    SourceReference,
    VerificationStatus,
)


class TestKnowledgeRepository:
    """Tests for KnowledgeRepository class."""

    @pytest.fixture
    def repository(self) -> KnowledgeRepository:
        """Create a fresh repository instance."""
        return KnowledgeRepository()

    # ===================================
    # ENTRY CRUD TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_create_entry(self, repository: KnowledgeRepository):
        """Test creating a knowledge entry."""
        entry = KnowledgeEntry(
            entry_type=EntryType.CLAIM,
            content="Test claim content",
            title="Test Claim",
            domain="ml_ai",
        )

        created = await repository.create_entry(entry, created_by="user-1")

        assert created.entry_id is not None
        assert created.created_by == "user-1"
        assert created.version == 1
        assert created.created_at is not None

    @pytest.mark.asyncio
    async def test_create_entry_generates_id_if_missing(
        self, repository: KnowledgeRepository
    ):
        """Test that create_entry generates ID if not provided."""
        entry = KnowledgeEntry(
            entry_id="",  # Empty ID
            entry_type=EntryType.CLAIM,
            content="Test content",
        )

        created = await repository.create_entry(entry)

        assert created.entry_id != ""

    @pytest.mark.asyncio
    async def test_create_entry_records_provenance(
        self, repository: KnowledgeRepository
    ):
        """Test that creating entry records provenance."""
        entry = KnowledgeEntry(
            entry_type=EntryType.CLAIM,
            content="Test content",
        )

        created = await repository.create_entry(entry, created_by="user-1")

        provenance = await repository.get_provenance(created.entry_id)
        assert len(provenance) == 1
        assert provenance[0].action == "created"
        assert provenance[0].actor_id == "user-1"

    @pytest.mark.asyncio
    async def test_get_entry(self, repository: KnowledgeRepository):
        """Test getting entry by ID."""
        entry = KnowledgeEntry(
            entry_type=EntryType.CLAIM,
            content="Test content",
            title="Test Title",
        )
        created = await repository.create_entry(entry)

        retrieved = await repository.get_entry(created.entry_id)

        assert retrieved is not None
        assert retrieved.title == "Test Title"
        assert retrieved.entry_id == created.entry_id

    @pytest.mark.asyncio
    async def test_get_entry_not_found(self, repository: KnowledgeRepository):
        """Test getting non-existent entry returns None."""
        result = await repository.get_entry("non-existent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_entry(self, repository: KnowledgeRepository):
        """Test updating an entry."""
        entry = KnowledgeEntry(
            entry_type=EntryType.CLAIM,
            content="Original content",
            title="Original Title",
        )
        created = await repository.create_entry(entry)

        updated = await repository.update_entry(
            entry_id=created.entry_id,
            updates={
                "title": "Updated Title",
                "content": "Updated content",
                "confidence_score": 0.9,
            },
            updated_by="user-2",
            reason="Fixed typo",
        )

        assert updated is not None
        assert updated.title == "Updated Title"
        assert updated.content == "Updated content"
        assert updated.confidence_score == 0.9
        assert updated.version == 2

    @pytest.mark.asyncio
    async def test_update_entry_not_found(self, repository: KnowledgeRepository):
        """Test updating non-existent entry returns None."""
        result = await repository.update_entry(
            entry_id="non-existent",
            updates={"title": "New Title"},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_update_entry_enum_fields(self, repository: KnowledgeRepository):
        """Test updating enum fields with string values."""
        entry = KnowledgeEntry(
            entry_type=EntryType.CLAIM,
            content="Test content",
        )
        created = await repository.create_entry(entry)

        updated = await repository.update_entry(
            entry_id=created.entry_id,
            updates={
                "entry_type": "finding",
                "verification_status": "verified",
            },
        )

        assert updated.entry_type == EntryType.FINDING
        assert updated.verification_status == VerificationStatus.VERIFIED

    @pytest.mark.asyncio
    async def test_update_entry_records_provenance(
        self, repository: KnowledgeRepository
    ):
        """Test that updating entry records provenance."""
        entry = KnowledgeEntry(
            entry_type=EntryType.CLAIM,
            content="Test content",
        )
        created = await repository.create_entry(entry, created_by="user-1")

        await repository.update_entry(
            entry_id=created.entry_id,
            updates={"title": "New Title"},
            updated_by="user-2",
            reason="Updated title",
        )

        provenance = await repository.get_provenance(created.entry_id)
        assert len(provenance) == 2
        assert provenance[1].action == "updated"
        assert provenance[1].actor_id == "user-2"
        assert provenance[1].reason == "Updated title"

    @pytest.mark.asyncio
    async def test_delete_entry_archives(self, repository: KnowledgeRepository):
        """Test that delete archives instead of hard delete."""
        entry = KnowledgeEntry(
            entry_type=EntryType.CLAIM,
            content="Test content",
        )
        created = await repository.create_entry(entry)

        result = await repository.delete_entry(
            entry_id=created.entry_id,
            deleted_by="user-1",
            reason="No longer needed",
        )

        assert result is True

        # Entry should still exist but be archived
        retrieved = await repository.get_entry(created.entry_id)
        assert retrieved is not None
        assert retrieved.is_archived is True

    @pytest.mark.asyncio
    async def test_delete_entry_not_found(self, repository: KnowledgeRepository):
        """Test deleting non-existent entry returns False."""
        result = await repository.delete_entry("non-existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_entry_records_provenance(
        self, repository: KnowledgeRepository
    ):
        """Test that deleting entry records provenance."""
        entry = KnowledgeEntry(
            entry_type=EntryType.CLAIM,
            content="Test content",
        )
        created = await repository.create_entry(entry, created_by="user-1")

        await repository.delete_entry(
            entry_id=created.entry_id,
            deleted_by="user-2",
            reason="Removed",
        )

        provenance = await repository.get_provenance(created.entry_id)
        assert len(provenance) == 2
        assert provenance[1].action == "archived"

    # ===================================
    # LIST ENTRIES TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_list_entries_all(self, repository: KnowledgeRepository):
        """Test listing all entries."""
        await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 1")
        )
        await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.FINDING, content="Finding 1")
        )

        entries = await repository.list_entries()
        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_list_entries_by_type(self, repository: KnowledgeRepository):
        """Test listing entries filtered by type."""
        await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 1")
        )
        await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.FINDING, content="Finding 1")
        )
        await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 2")
        )

        claims = await repository.list_entries(entry_type=EntryType.CLAIM)
        assert len(claims) == 2
        assert all(e.entry_type == EntryType.CLAIM for e in claims)

    @pytest.mark.asyncio
    async def test_list_entries_by_domain(self, repository: KnowledgeRepository):
        """Test listing entries filtered by domain."""
        await repository.create_entry(
            KnowledgeEntry(
                entry_type=EntryType.CLAIM,
                content="ML claim",
                domain="ml_ai",
            )
        )
        await repository.create_entry(
            KnowledgeEntry(
                entry_type=EntryType.CLAIM,
                content="Math claim",
                domain="mathematics",
            )
        )

        ml_entries = await repository.list_entries(domain="ml_ai")
        assert len(ml_entries) == 1
        assert ml_entries[0].domain == "ml_ai"

    @pytest.mark.asyncio
    async def test_list_entries_by_verification_status(
        self, repository: KnowledgeRepository
    ):
        """Test listing entries filtered by verification status."""
        entry1 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 1")
        )
        entry2 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 2")
        )

        await repository.update_entry(
            entry1.entry_id,
            {"verification_status": "verified"},
        )

        verified = await repository.list_entries(
            verification_status=VerificationStatus.VERIFIED
        )
        assert len(verified) == 1

    @pytest.mark.asyncio
    async def test_list_entries_excludes_archived(self, repository: KnowledgeRepository):
        """Test that list_entries excludes archived by default."""
        entry1 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 1")
        )
        await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 2")
        )

        await repository.delete_entry(entry1.entry_id)

        entries = await repository.list_entries()
        assert len(entries) == 1

    @pytest.mark.asyncio
    async def test_list_entries_includes_archived(self, repository: KnowledgeRepository):
        """Test listing entries including archived."""
        entry1 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 1")
        )
        await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 2")
        )

        await repository.delete_entry(entry1.entry_id)

        entries = await repository.list_entries(include_archived=True)
        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_list_entries_pagination(self, repository: KnowledgeRepository):
        """Test listing entries with pagination."""
        for i in range(10):
            await repository.create_entry(
                KnowledgeEntry(entry_type=EntryType.CLAIM, content=f"Claim {i}")
            )

        page1 = await repository.list_entries(limit=5, offset=0)
        page2 = await repository.list_entries(limit=5, offset=5)

        assert len(page1) == 5
        assert len(page2) == 5

    # ===================================
    # CITATION TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_create_citation(self, repository: KnowledgeRepository):
        """Test creating a citation between entries."""
        source = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Source claim")
        )
        target = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.FINDING, content="Target finding")
        )

        citation = await repository.create_citation(
            source_entry_id=source.entry_id,
            target_entry_id=target.entry_id,
            citation_type="reference",
            context="As stated in...",
        )

        assert citation is not None
        assert citation.source_entry_id == source.entry_id
        assert citation.target_entry_id == target.entry_id
        assert citation.citation_type == "reference"

    @pytest.mark.asyncio
    async def test_get_citations_as_source(self, repository: KnowledgeRepository):
        """Test getting citations where entry is source."""
        source = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Source")
        )
        target1 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.FINDING, content="Target 1")
        )
        target2 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.FINDING, content="Target 2")
        )

        await repository.create_citation(source.entry_id, target1.entry_id)
        await repository.create_citation(source.entry_id, target2.entry_id)

        citations = await repository.get_citations_for_entry(
            source.entry_id, as_source=True
        )
        assert len(citations) == 2

    @pytest.mark.asyncio
    async def test_get_citations_as_target(self, repository: KnowledgeRepository):
        """Test getting citations where entry is target."""
        target = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.FINDING, content="Target")
        )
        source1 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Source 1")
        )
        source2 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Source 2")
        )

        await repository.create_citation(source1.entry_id, target.entry_id)
        await repository.create_citation(source2.entry_id, target.entry_id)

        citations = await repository.get_citations_for_entry(
            target.entry_id, as_source=False
        )
        assert len(citations) == 2

    # ===================================
    # RELATIONSHIP TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_create_relationship(self, repository: KnowledgeRepository):
        """Test creating a relationship between entries."""
        entry1 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 1")
        )
        entry2 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 2")
        )

        relationship = await repository.create_relationship(
            source_id=entry1.entry_id,
            target_id=entry2.entry_id,
            relationship_type=RelationshipType.SUPPORTS,
            strength=0.8,
            evidence="Both make same point",
            created_by="user-1",
        )

        assert relationship is not None
        assert relationship.relationship_type == RelationshipType.SUPPORTS
        assert relationship.strength == 0.8

    @pytest.mark.asyncio
    async def test_get_relationships_as_source(self, repository: KnowledgeRepository):
        """Test getting relationships where entry is source."""
        source = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Source")
        )
        target1 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Target 1")
        )
        target2 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Target 2")
        )

        await repository.create_relationship(
            source.entry_id, target1.entry_id, RelationshipType.SUPPORTS
        )
        await repository.create_relationship(
            source.entry_id, target2.entry_id, RelationshipType.RELATED_TO
        )

        relationships = await repository.get_relationships(source.entry_id, as_source=True)
        assert len(relationships) == 2

    @pytest.mark.asyncio
    async def test_get_relationships_by_type(self, repository: KnowledgeRepository):
        """Test getting relationships filtered by type."""
        source = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Source")
        )
        target1 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Target 1")
        )
        target2 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Target 2")
        )

        await repository.create_relationship(
            source.entry_id, target1.entry_id, RelationshipType.SUPPORTS
        )
        await repository.create_relationship(
            source.entry_id, target2.entry_id, RelationshipType.REFUTES
        )

        supports = await repository.get_relationships(
            source.entry_id,
            relationship_type=RelationshipType.SUPPORTS,
            as_source=True,
        )
        assert len(supports) == 1
        assert supports[0].relationship_type == RelationshipType.SUPPORTS

    @pytest.mark.asyncio
    async def test_delete_relationship(self, repository: KnowledgeRepository):
        """Test deleting a relationship."""
        entry1 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Entry 1")
        )
        entry2 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Entry 2")
        )

        relationship = await repository.create_relationship(
            entry1.entry_id, entry2.entry_id, RelationshipType.SUPPORTS
        )

        result = await repository.delete_relationship(relationship.relationship_id)
        assert result is True

        relationships = await repository.get_relationships(entry1.entry_id, as_source=True)
        assert len(relationships) == 0

    @pytest.mark.asyncio
    async def test_delete_relationship_not_found(self, repository: KnowledgeRepository):
        """Test deleting non-existent relationship returns False."""
        result = await repository.delete_relationship("non-existent")
        assert result is False

    # ===================================
    # SOURCE REFERENCE TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_add_source_reference(self, repository: KnowledgeRepository):
        """Test adding source reference to entry."""
        entry = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim")
        )

        reference = SourceReference(
            source_type="arxiv",
            source_id="2301.12345",
            url="https://arxiv.org/abs/2301.12345",
            title="Test Paper",
            authors=["Author 1", "Author 2"],
        )

        added = await repository.add_source_reference(entry.entry_id, reference)

        assert added is not None
        assert added.reference_id is not None
        assert added.source_type == "arxiv"

    @pytest.mark.asyncio
    async def test_get_entry_references(self, repository: KnowledgeRepository):
        """Test getting all references for an entry."""
        entry = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim")
        )

        await repository.add_source_reference(
            entry.entry_id,
            SourceReference(source_type="arxiv", source_id="2301.12345"),
        )
        await repository.add_source_reference(
            entry.entry_id,
            SourceReference(source_type="doi", source_id="10.1234/test"),
        )

        references = await repository.get_entry_references(entry.entry_id)
        assert len(references) == 2

    @pytest.mark.asyncio
    async def test_find_by_source(self, repository: KnowledgeRepository):
        """Test finding entries by external source."""
        entry1 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 1")
        )
        entry2 = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Claim 2")
        )

        await repository.add_source_reference(
            entry1.entry_id,
            SourceReference(source_type="arxiv", source_id="2301.12345"),
        )
        await repository.add_source_reference(
            entry2.entry_id,
            SourceReference(source_type="arxiv", source_id="2301.12345"),
        )

        entries = await repository.find_by_source("arxiv", "2301.12345")
        assert len(entries) == 2

    # ===================================
    # PROVENANCE TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_provenance_history(self, repository: KnowledgeRepository):
        """Test getting complete provenance history."""
        entry = await repository.create_entry(
            KnowledgeEntry(entry_type=EntryType.CLAIM, content="Original"),
            created_by="user-1",
        )

        await repository.update_entry(
            entry.entry_id,
            {"content": "Updated"},
            updated_by="user-2",
            reason="Fixed content",
        )

        await repository.delete_entry(entry.entry_id, deleted_by="user-3")

        provenance = await repository.get_provenance(entry.entry_id)

        assert len(provenance) == 3
        assert provenance[0].action == "created"
        assert provenance[1].action == "updated"
        assert provenance[2].action == "archived"

    @pytest.mark.asyncio
    async def test_provenance_stores_state_changes(
        self, repository: KnowledgeRepository
    ):
        """Test that provenance stores previous and new state."""
        entry = await repository.create_entry(
            KnowledgeEntry(
                entry_type=EntryType.CLAIM,
                content="Original content",
                title="Original Title",
            ),
            created_by="user-1",
        )

        await repository.update_entry(
            entry.entry_id,
            {"title": "New Title"},
            updated_by="user-2",
        )

        provenance = await repository.get_provenance(entry.entry_id)
        update_record = provenance[1]

        assert "title" in update_record.previous_state
        assert update_record.previous_state["title"] == "Original Title"
        assert update_record.new_state["title"] == "New Title"

    # ===================================
    # STATISTICS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_stats(self, repository: KnowledgeRepository):
        """Test getting repository statistics."""
        entry1 = await repository.create_entry(
            KnowledgeEntry(
                entry_type=EntryType.CLAIM,
                content="Claim",
                domain="ml_ai",
            )
        )
        await repository.create_entry(
            KnowledgeEntry(
                entry_type=EntryType.FINDING,
                content="Finding",
                domain="mathematics",
            )
        )
        entry3 = await repository.create_entry(
            KnowledgeEntry(
                entry_type=EntryType.CLAIM,
                content="Another claim",
                domain="ml_ai",
            )
        )

        await repository.update_entry(
            entry1.entry_id,
            {"verification_status": "verified"},
        )

        await repository.create_citation(
            entry1.entry_id, entry3.entry_id
        )

        await repository.create_relationship(
            entry1.entry_id,
            entry3.entry_id,
            RelationshipType.SUPPORTS,
        )

        # Archive one
        await repository.delete_entry(entry3.entry_id)

        stats = repository.get_stats()

        assert stats["total_entries"] == 3
        assert stats["active_entries"] == 2
        assert stats["archived_entries"] == 1
        assert stats["total_citations"] == 1
        assert stats["total_relationships"] == 1
        assert stats["entries_by_type"]["claim"] == 2
        assert stats["entries_by_type"]["finding"] == 1
        assert stats["entries_by_domain"]["ml_ai"] == 2
        assert stats["entries_by_domain"]["mathematics"] == 1
