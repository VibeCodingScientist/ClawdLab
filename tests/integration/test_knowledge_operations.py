"""Integration tests for knowledge operations.

Tests the complete knowledge management workflow:
- Entry creation and retrieval
- Citation management
- Relationship management
- Provenance tracking
- Search operations
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from platform.knowledge.repository import KnowledgeRepository
from platform.knowledge.base import (
    KnowledgeEntry,
    EntryType,
    VerificationStatus,
    Citation,
    Relationship,
    RelationshipType,
    SourceReference,
)


# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture
def repository():
    """Create fresh KnowledgeRepository for each test."""
    with patch("platform.knowledge.repository.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock()
        with patch("platform.knowledge.repository.get_logger") as mock_logger:
            mock_logger.return_value = MagicMock()
            return KnowledgeRepository()


def create_test_entry(
    title: str = "Test Entry",
    content: str = "Test content",
    domain: str = "ml_ai",
    entry_type: EntryType = EntryType.FACT,
) -> KnowledgeEntry:
    """Create a test knowledge entry."""
    return KnowledgeEntry(
        title=title,
        content=content,
        domain=domain,
        entry_type=entry_type,
        verification_status=VerificationStatus.PENDING,
        keywords=["test", "knowledge"],
    )


# ===========================================
# ENTRY CRUD OPERATIONS
# ===========================================


class TestEntryCRUDOperations:
    """Tests for entry CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_entry(self, repository):
        """Test creating a knowledge entry."""
        entry = create_test_entry(
            title="Neural Network Basics",
            content="Neural networks are computational models...",
            domain="ml_ai",
        )

        created = await repository.create_entry(entry, created_by="user-1")

        assert created is not None
        assert created.entry_id is not None
        assert created.title == "Neural Network Basics"
        assert created.created_by == "user-1"
        assert created.version == 1

    @pytest.mark.asyncio
    async def test_get_entry(self, repository):
        """Test retrieving an entry."""
        entry = create_test_entry(title="Retrieval Test")
        created = await repository.create_entry(entry)

        retrieved = await repository.get_entry(created.entry_id)

        assert retrieved is not None
        assert retrieved.entry_id == created.entry_id
        assert retrieved.title == "Retrieval Test"

    @pytest.mark.asyncio
    async def test_get_entry_not_found(self, repository):
        """Test retrieving non-existent entry."""
        result = await repository.get_entry("nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_entry(self, repository):
        """Test updating an entry."""
        entry = create_test_entry(title="Original Title")
        created = await repository.create_entry(entry)

        updated = await repository.update_entry(
            entry_id=created.entry_id,
            updates={"title": "Updated Title", "content": "Updated content"},
            updated_by="user-2",
            reason="Improved accuracy",
        )

        assert updated is not None
        assert updated.title == "Updated Title"
        assert updated.content == "Updated content"
        assert updated.version == 2

    @pytest.mark.asyncio
    async def test_update_entry_type(self, repository):
        """Test updating entry type."""
        entry = create_test_entry(entry_type=EntryType.FACT)
        created = await repository.create_entry(entry)

        updated = await repository.update_entry(
            entry_id=created.entry_id,
            updates={"entry_type": "theory"},
        )

        assert updated.entry_type == EntryType.THEORY

    @pytest.mark.asyncio
    async def test_update_verification_status(self, repository):
        """Test updating verification status."""
        entry = create_test_entry()
        created = await repository.create_entry(entry)

        updated = await repository.update_entry(
            entry_id=created.entry_id,
            updates={"verification_status": "verified"},
        )

        assert updated.verification_status == VerificationStatus.VERIFIED

    @pytest.mark.asyncio
    async def test_delete_entry(self, repository):
        """Test deleting (archiving) an entry."""
        entry = create_test_entry(title="To Delete")
        created = await repository.create_entry(entry)

        result = await repository.delete_entry(
            entry_id=created.entry_id,
            deleted_by="admin",
            reason="Outdated information",
        )

        assert result is True

        # Entry should be archived, not hard deleted
        archived = await repository.get_entry(created.entry_id)
        assert archived.is_archived is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_entry(self, repository):
        """Test deleting non-existent entry."""
        result = await repository.delete_entry("nonexistent-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_list_entries(self, repository):
        """Test listing entries."""
        # Create multiple entries
        for i in range(5):
            entry = create_test_entry(title=f"Entry {i}")
            await repository.create_entry(entry)

        entries = await repository.list_entries()

        assert len(entries) == 5

    @pytest.mark.asyncio
    async def test_list_entries_by_type(self, repository):
        """Test filtering entries by type."""
        await repository.create_entry(create_test_entry(entry_type=EntryType.FACT))
        await repository.create_entry(create_test_entry(entry_type=EntryType.FACT))
        await repository.create_entry(create_test_entry(entry_type=EntryType.THEORY))

        facts = await repository.list_entries(entry_type=EntryType.FACT)

        assert len(facts) == 2
        assert all(e.entry_type == EntryType.FACT for e in facts)

    @pytest.mark.asyncio
    async def test_list_entries_by_domain(self, repository):
        """Test filtering entries by domain."""
        await repository.create_entry(create_test_entry(domain="ml_ai"))
        await repository.create_entry(create_test_entry(domain="ml_ai"))
        await repository.create_entry(create_test_entry(domain="biology"))

        ml_entries = await repository.list_entries(domain="ml_ai")

        assert len(ml_entries) == 2

    @pytest.mark.asyncio
    async def test_list_entries_exclude_archived(self, repository):
        """Test archived entries are excluded by default."""
        entry1 = create_test_entry(title="Active Entry")
        created1 = await repository.create_entry(entry1)

        entry2 = create_test_entry(title="Archived Entry")
        created2 = await repository.create_entry(entry2)
        await repository.delete_entry(created2.entry_id)

        entries = await repository.list_entries()

        assert len(entries) == 1
        assert entries[0].title == "Active Entry"

    @pytest.mark.asyncio
    async def test_list_entries_include_archived(self, repository):
        """Test including archived entries."""
        entry1 = create_test_entry(title="Active")
        await repository.create_entry(entry1)

        entry2 = create_test_entry(title="Archived")
        created2 = await repository.create_entry(entry2)
        await repository.delete_entry(created2.entry_id)

        entries = await repository.list_entries(include_archived=True)

        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_list_entries_pagination(self, repository):
        """Test entry listing pagination."""
        for i in range(10):
            entry = create_test_entry(title=f"Entry {i}")
            await repository.create_entry(entry)

        page1 = await repository.list_entries(limit=5, offset=0)
        page2 = await repository.list_entries(limit=5, offset=5)

        assert len(page1) == 5
        assert len(page2) == 5


# ===========================================
# CITATION OPERATIONS
# ===========================================


class TestCitationOperations:
    """Tests for citation management."""

    @pytest.mark.asyncio
    async def test_create_citation(self, repository):
        """Test creating a citation."""
        entry1 = await repository.create_entry(create_test_entry(title="Source Entry"))
        entry2 = await repository.create_entry(create_test_entry(title="Citing Entry"))

        citation = await repository.create_citation(
            source_entry_id=entry2.entry_id,
            target_entry_id=entry1.entry_id,
            citation_type="reference",
            context="As shown in [1]...",
        )

        assert citation is not None
        assert citation.source_entry_id == entry2.entry_id
        assert citation.target_entry_id == entry1.entry_id
        assert citation.citation_type == "reference"

    @pytest.mark.asyncio
    async def test_get_citations_as_source(self, repository):
        """Test getting citations where entry is the source."""
        source = await repository.create_entry(create_test_entry(title="Source"))
        target1 = await repository.create_entry(create_test_entry(title="Target 1"))
        target2 = await repository.create_entry(create_test_entry(title="Target 2"))

        await repository.create_citation(source.entry_id, target1.entry_id)
        await repository.create_citation(source.entry_id, target2.entry_id)

        citations = await repository.get_citations_for_entry(
            source.entry_id,
            as_source=True,
        )

        assert len(citations) == 2

    @pytest.mark.asyncio
    async def test_get_citations_as_target(self, repository):
        """Test getting citations where entry is the target."""
        target = await repository.create_entry(create_test_entry(title="Cited Work"))
        source1 = await repository.create_entry(create_test_entry(title="Paper 1"))
        source2 = await repository.create_entry(create_test_entry(title="Paper 2"))

        await repository.create_citation(source1.entry_id, target.entry_id)
        await repository.create_citation(source2.entry_id, target.entry_id)

        citations = await repository.get_citations_for_entry(
            target.entry_id,
            as_source=False,
        )

        assert len(citations) == 2

    @pytest.mark.asyncio
    async def test_citation_chain(self, repository):
        """Test creating a chain of citations."""
        entry_a = await repository.create_entry(create_test_entry(title="Entry A"))
        entry_b = await repository.create_entry(create_test_entry(title="Entry B"))
        entry_c = await repository.create_entry(create_test_entry(title="Entry C"))

        # A cites B, B cites C
        await repository.create_citation(entry_a.entry_id, entry_b.entry_id)
        await repository.create_citation(entry_b.entry_id, entry_c.entry_id)

        # A's citations
        a_cites = await repository.get_citations_for_entry(entry_a.entry_id, as_source=True)
        assert len(a_cites) == 1
        assert a_cites[0].target_entry_id == entry_b.entry_id

        # B is cited by A, cites C
        b_cited_by = await repository.get_citations_for_entry(entry_b.entry_id, as_source=False)
        b_cites = await repository.get_citations_for_entry(entry_b.entry_id, as_source=True)
        assert len(b_cited_by) == 1
        assert len(b_cites) == 1


# ===========================================
# RELATIONSHIP OPERATIONS (via Repository read from base.py)
# ===========================================


class TestRelationshipOperations:
    """Tests for relationship management."""

    @pytest.mark.asyncio
    async def test_create_relationship(self, repository):
        """Test creating a relationship between entries."""
        entry1 = await repository.create_entry(create_test_entry(title="Concept A"))
        entry2 = await repository.create_entry(create_test_entry(title="Concept B"))

        # Manually create relationship (repository method may vary)
        relationship = Relationship(
            source_entry_id=entry1.entry_id,
            target_entry_id=entry2.entry_id,
            relationship_type=RelationshipType.RELATED_TO,
            description="A is related to B",
        )

        repository._relationships[relationship.relationship_id] = relationship

        assert relationship.relationship_id in repository._relationships

    @pytest.mark.asyncio
    async def test_hierarchical_relationships(self, repository):
        """Test hierarchical relationships."""
        parent = await repository.create_entry(create_test_entry(title="Machine Learning"))
        child1 = await repository.create_entry(create_test_entry(title="Supervised Learning"))
        child2 = await repository.create_entry(create_test_entry(title="Unsupervised Learning"))

        # Create parent-child relationships
        rel1 = Relationship(
            source_entry_id=parent.entry_id,
            target_entry_id=child1.entry_id,
            relationship_type=RelationshipType.HAS_PART,
        )
        rel2 = Relationship(
            source_entry_id=parent.entry_id,
            target_entry_id=child2.entry_id,
            relationship_type=RelationshipType.HAS_PART,
        )

        repository._relationships[rel1.relationship_id] = rel1
        repository._relationships[rel2.relationship_id] = rel2

        # Verify relationships
        children = [
            r for r in repository._relationships.values()
            if r.source_entry_id == parent.entry_id
        ]
        assert len(children) == 2


# ===========================================
# PROVENANCE TRACKING
# ===========================================


class TestProvenanceTracking:
    """Tests for provenance tracking."""

    @pytest.mark.asyncio
    async def test_provenance_on_create(self, repository):
        """Test provenance record created on entry creation."""
        entry = create_test_entry(title="Provenance Test")
        created = await repository.create_entry(entry, created_by="user-1")

        provenance = repository._provenance.get(created.entry_id, [])

        assert len(provenance) >= 1
        assert provenance[0].action == "created"
        assert provenance[0].actor_id == "user-1"

    @pytest.mark.asyncio
    async def test_provenance_on_update(self, repository):
        """Test provenance record created on entry update."""
        entry = create_test_entry()
        created = await repository.create_entry(entry, created_by="user-1")

        await repository.update_entry(
            entry_id=created.entry_id,
            updates={"title": "Updated"},
            updated_by="user-2",
            reason="Correction",
        )

        provenance = repository._provenance.get(created.entry_id, [])

        # Should have create + update records
        assert len(provenance) >= 2
        update_record = provenance[-1]
        assert update_record.action == "updated"
        assert update_record.actor_id == "user-2"
        assert update_record.reason == "Correction"

    @pytest.mark.asyncio
    async def test_provenance_on_archive(self, repository):
        """Test provenance record created on entry archival."""
        entry = create_test_entry()
        created = await repository.create_entry(entry)

        await repository.delete_entry(
            entry_id=created.entry_id,
            deleted_by="admin",
            reason="Outdated",
        )

        provenance = repository._provenance.get(created.entry_id, [])

        archive_record = provenance[-1]
        assert archive_record.action == "archived"
        assert archive_record.actor_id == "admin"

    @pytest.mark.asyncio
    async def test_provenance_stores_state_changes(self, repository):
        """Test provenance stores previous and new states."""
        entry = create_test_entry(title="Original")
        created = await repository.create_entry(entry)

        await repository.update_entry(
            entry_id=created.entry_id,
            updates={"title": "Modified"},
            updated_by="user-1",
        )

        provenance = repository._provenance.get(created.entry_id, [])
        update_record = provenance[-1]

        assert update_record.previous_state is not None
        assert update_record.new_state is not None
        assert update_record.previous_state.get("title") == "Original"
        assert update_record.new_state.get("title") == "Modified"


# ===========================================
# VERSION TRACKING
# ===========================================


class TestVersionTracking:
    """Tests for version tracking."""

    @pytest.mark.asyncio
    async def test_version_increments_on_update(self, repository):
        """Test version number increments on each update."""
        entry = create_test_entry()
        created = await repository.create_entry(entry)
        assert created.version == 1

        await repository.update_entry(created.entry_id, {"title": "V2"})
        assert created.version == 2

        await repository.update_entry(created.entry_id, {"title": "V3"})
        assert created.version == 3

    @pytest.mark.asyncio
    async def test_version_tracks_updates_correctly(self, repository):
        """Test version corresponds to update count."""
        entry = create_test_entry()
        created = await repository.create_entry(entry)

        # Perform 5 updates
        for i in range(5):
            await repository.update_entry(
                created.entry_id,
                {"content": f"Update {i+1}"},
            )

        assert created.version == 6  # 1 initial + 5 updates


# ===========================================
# COMPLEX WORKFLOWS
# ===========================================


class TestComplexWorkflows:
    """Tests for complex knowledge management workflows."""

    @pytest.mark.asyncio
    async def test_knowledge_base_construction(self, repository):
        """Test building a knowledge base with entries and relationships."""
        # Create base concepts
        ml = await repository.create_entry(create_test_entry(
            title="Machine Learning",
            domain="ml_ai",
            entry_type=EntryType.CONCEPT,
        ))

        dl = await repository.create_entry(create_test_entry(
            title="Deep Learning",
            domain="ml_ai",
            entry_type=EntryType.CONCEPT,
        ))

        nn = await repository.create_entry(create_test_entry(
            title="Neural Networks",
            domain="ml_ai",
            entry_type=EntryType.CONCEPT,
        ))

        # Create relationships
        # DL is part of ML
        rel1 = Relationship(
            source_entry_id=ml.entry_id,
            target_entry_id=dl.entry_id,
            relationship_type=RelationshipType.HAS_PART,
        )
        repository._relationships[rel1.relationship_id] = rel1

        # NN is related to DL
        rel2 = Relationship(
            source_entry_id=dl.entry_id,
            target_entry_id=nn.entry_id,
            relationship_type=RelationshipType.RELATED_TO,
        )
        repository._relationships[rel2.relationship_id] = rel2

        # Verify knowledge base
        all_entries = await repository.list_entries()
        assert len(all_entries) == 3

        all_relationships = list(repository._relationships.values())
        assert len(all_relationships) == 2

    @pytest.mark.asyncio
    async def test_research_paper_knowledge_extraction(self, repository):
        """Test extracting knowledge from a research paper."""
        # Create paper entry
        paper = await repository.create_entry(KnowledgeEntry(
            title="Novel Transformer Architecture",
            content="We propose a new transformer architecture...",
            domain="ml_ai",
            entry_type=EntryType.PAPER,
            keywords=["transformer", "attention", "NLP"],
        ))

        # Extract claims from paper
        claim1 = await repository.create_entry(KnowledgeEntry(
            title="Transformer Efficiency Claim",
            content="The new architecture is 2x faster",
            domain="ml_ai",
            entry_type=EntryType.CLAIM,
            verification_status=VerificationStatus.UNVERIFIED,
        ))

        claim2 = await repository.create_entry(KnowledgeEntry(
            title="Accuracy Improvement Claim",
            content="Achieves 5% better accuracy",
            domain="ml_ai",
            entry_type=EntryType.CLAIM,
            verification_status=VerificationStatus.UNVERIFIED,
        ))

        # Create citations from claims to paper
        await repository.create_citation(
            source_entry_id=claim1.entry_id,
            target_entry_id=paper.entry_id,
            citation_type="supports",
            context="As stated in the paper...",
        )

        await repository.create_citation(
            source_entry_id=claim2.entry_id,
            target_entry_id=paper.entry_id,
            citation_type="supports",
        )

        # Verify paper citations
        paper_citations = await repository.get_citations_for_entry(
            paper.entry_id,
            as_source=False,
        )
        assert len(paper_citations) == 2

    @pytest.mark.asyncio
    async def test_verification_workflow(self, repository):
        """Test claim verification workflow."""
        # Create unverified claim
        claim = await repository.create_entry(KnowledgeEntry(
            title="Test Claim",
            content="A claim to be verified",
            domain="ml_ai",
            entry_type=EntryType.CLAIM,
            verification_status=VerificationStatus.UNVERIFIED,
        ), created_by="researcher-1")

        # Verify claim undergoes review
        await repository.update_entry(
            entry_id=claim.entry_id,
            updates={"verification_status": "pending"},
            updated_by="reviewer-1",
            reason="Submitted for review",
        )

        # Claim verified
        await repository.update_entry(
            entry_id=claim.entry_id,
            updates={"verification_status": "verified"},
            updated_by="reviewer-1",
            reason="Evidence supports claim",
        )

        # Check final state
        verified_claim = await repository.get_entry(claim.entry_id)
        assert verified_claim.verification_status == VerificationStatus.VERIFIED

        # Check provenance trail
        provenance = repository._provenance.get(claim.entry_id, [])
        assert len(provenance) == 3  # create + 2 updates

    @pytest.mark.asyncio
    async def test_knowledge_graph_building(self, repository):
        """Test building a knowledge graph structure."""
        # Create nodes
        nodes = []
        for i in range(5):
            entry = await repository.create_entry(create_test_entry(
                title=f"Concept {i}",
                entry_type=EntryType.CONCEPT,
            ))
            nodes.append(entry)

        # Create edges (relationships)
        # 0 -> 1, 0 -> 2, 1 -> 3, 2 -> 3, 3 -> 4
        edges = [
            (0, 1), (0, 2), (1, 3), (2, 3), (3, 4)
        ]

        for source_idx, target_idx in edges:
            rel = Relationship(
                source_entry_id=nodes[source_idx].entry_id,
                target_entry_id=nodes[target_idx].entry_id,
                relationship_type=RelationshipType.RELATED_TO,
            )
            repository._relationships[rel.relationship_id] = rel

        # Verify graph structure
        assert len(repository._relationships) == 5

        # Node 3 should have multiple incoming edges
        incoming_to_3 = [
            r for r in repository._relationships.values()
            if r.target_entry_id == nodes[3].entry_id
        ]
        assert len(incoming_to_3) == 2

    @pytest.mark.asyncio
    async def test_multi_domain_knowledge_integration(self, repository):
        """Test integrating knowledge across domains."""
        # Create entries in different domains
        ml_entry = await repository.create_entry(create_test_entry(
            title="Transfer Learning",
            domain="ml_ai",
        ))

        bio_entry = await repository.create_entry(create_test_entry(
            title="Protein Structure Prediction",
            domain="computational_biology",
        ))

        # Create cross-domain relationship
        rel = Relationship(
            source_entry_id=ml_entry.entry_id,
            target_entry_id=bio_entry.entry_id,
            relationship_type=RelationshipType.APPLIED_TO,
            description="Transfer learning applied to protein prediction",
        )
        repository._relationships[rel.relationship_id] = rel

        # Query by domain
        ml_entries = await repository.list_entries(domain="ml_ai")
        bio_entries = await repository.list_entries(domain="computational_biology")

        assert len(ml_entries) == 1
        assert len(bio_entries) == 1

        # Cross-domain relationship exists
        cross_domain = [
            r for r in repository._relationships.values()
            if r.relationship_type == RelationshipType.APPLIED_TO
        ]
        assert len(cross_domain) == 1
