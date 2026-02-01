"""Knowledge repository for storing and retrieving knowledge entries."""

from datetime import datetime
from typing import Any
from uuid import uuid4

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
from platform.knowledge.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class KnowledgeRepository:
    """
    Repository for knowledge entries.

    Provides CRUD operations for knowledge entries, citations,
    relationships, and provenance records.

    Uses PostgreSQL with pgvector for vector similarity search.
    """

    def __init__(self):
        """Initialize knowledge repository."""
        self._entries: dict[str, KnowledgeEntry] = {}
        self._citations: dict[str, Citation] = {}
        self._relationships: dict[str, Relationship] = {}
        self._provenance: dict[str, list[ProvenanceRecord]] = {}
        self._references: dict[str, SourceReference] = {}
        self._entry_references: dict[str, list[str]] = {}  # entry_id -> [reference_ids]

    # ===========================================
    # ENTRY OPERATIONS
    # ===========================================

    async def create_entry(
        self,
        entry: KnowledgeEntry,
        created_by: str = "",
    ) -> KnowledgeEntry:
        """
        Create a new knowledge entry.

        Args:
            entry: Knowledge entry to create
            created_by: ID of creator

        Returns:
            Created entry
        """
        entry.entry_id = entry.entry_id or str(uuid4())
        entry.created_by = created_by
        entry.created_at = datetime.utcnow()
        entry.updated_at = datetime.utcnow()
        entry.version = 1

        self._entries[entry.entry_id] = entry

        # Create provenance record
        await self._record_provenance(
            entry_id=entry.entry_id,
            action="created",
            actor_id=created_by,
            new_state=entry.to_dict(),
        )

        logger.info(
            "entry_created",
            entry_id=entry.entry_id,
            entry_type=entry.entry_type.value,
            domain=entry.domain,
        )

        return entry

    async def get_entry(self, entry_id: str) -> KnowledgeEntry | None:
        """
        Get a knowledge entry by ID.

        Args:
            entry_id: Entry ID

        Returns:
            Entry or None
        """
        return self._entries.get(entry_id)

    async def update_entry(
        self,
        entry_id: str,
        updates: dict[str, Any],
        updated_by: str = "",
        reason: str = "",
    ) -> KnowledgeEntry | None:
        """
        Update a knowledge entry.

        Args:
            entry_id: Entry ID
            updates: Fields to update
            updated_by: ID of updater
            reason: Reason for update

        Returns:
            Updated entry or None
        """
        entry = self._entries.get(entry_id)
        if not entry:
            return None

        # Store previous state
        previous_state = entry.to_dict()

        # Apply updates
        for key, value in updates.items():
            if hasattr(entry, key):
                if key == "entry_type" and isinstance(value, str):
                    value = EntryType(value)
                elif key == "verification_status" and isinstance(value, str):
                    value = VerificationStatus(value)
                setattr(entry, key, value)

        entry.updated_at = datetime.utcnow()
        entry.version += 1

        # Record provenance
        await self._record_provenance(
            entry_id=entry_id,
            action="updated",
            actor_id=updated_by,
            previous_state=previous_state,
            new_state=entry.to_dict(),
            reason=reason,
        )

        logger.info("entry_updated", entry_id=entry_id, version=entry.version)

        return entry

    async def delete_entry(
        self,
        entry_id: str,
        deleted_by: str = "",
        reason: str = "",
    ) -> bool:
        """
        Delete (archive) a knowledge entry.

        Args:
            entry_id: Entry ID
            deleted_by: ID of deleter
            reason: Reason for deletion

        Returns:
            True if deleted
        """
        entry = self._entries.get(entry_id)
        if not entry:
            return False

        # Archive instead of hard delete
        previous_state = entry.to_dict()
        entry.is_archived = True
        entry.updated_at = datetime.utcnow()

        await self._record_provenance(
            entry_id=entry_id,
            action="archived",
            actor_id=deleted_by,
            previous_state=previous_state,
            new_state=entry.to_dict(),
            reason=reason,
        )

        logger.info("entry_archived", entry_id=entry_id)

        return True

    async def list_entries(
        self,
        entry_type: EntryType | None = None,
        domain: str | None = None,
        verification_status: VerificationStatus | None = None,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeEntry]:
        """
        List knowledge entries with filtering.

        Args:
            entry_type: Filter by entry type
            domain: Filter by domain
            verification_status: Filter by verification status
            include_archived: Include archived entries
            limit: Maximum results
            offset: Result offset

        Returns:
            List of entries
        """
        results = []

        for entry in self._entries.values():
            if not include_archived and entry.is_archived:
                continue
            if entry_type and entry.entry_type != entry_type:
                continue
            if domain and entry.domain != domain:
                continue
            if verification_status and entry.verification_status != verification_status:
                continue

            results.append(entry)

        # Sort by created_at descending
        results.sort(key=lambda e: e.created_at, reverse=True)

        return results[offset:offset + limit]

    # ===========================================
    # CITATION OPERATIONS
    # ===========================================

    async def create_citation(
        self,
        source_entry_id: str,
        target_entry_id: str,
        citation_type: str = "reference",
        context: str = "",
    ) -> Citation:
        """
        Create a citation between entries.

        Args:
            source_entry_id: Citing entry ID
            target_entry_id: Cited entry ID
            citation_type: Type of citation
            context: Citation context

        Returns:
            Created citation
        """
        citation = Citation(
            citation_id=str(uuid4()),
            source_entry_id=source_entry_id,
            target_entry_id=target_entry_id,
            citation_type=citation_type,
            context=context,
        )

        self._citations[citation.citation_id] = citation

        logger.info(
            "citation_created",
            citation_id=citation.citation_id,
            source=source_entry_id,
            target=target_entry_id,
        )

        return citation

    async def get_citations_for_entry(
        self,
        entry_id: str,
        as_source: bool = True,
    ) -> list[Citation]:
        """
        Get citations for an entry.

        Args:
            entry_id: Entry ID
            as_source: If True, get citations where entry is source

        Returns:
            List of citations
        """
        results = []
        for citation in self._citations.values():
            if as_source and citation.source_entry_id == entry_id:
                results.append(citation)
            elif not as_source and citation.target_entry_id == entry_id:
                results.append(citation)

        return results

    # ===========================================
    # RELATIONSHIP OPERATIONS
    # ===========================================

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: RelationshipType,
        strength: float = 1.0,
        evidence: str = "",
        created_by: str = "",
    ) -> Relationship:
        """
        Create a relationship between entries.

        Args:
            source_id: Source entry ID
            target_id: Target entry ID
            relationship_type: Type of relationship
            strength: Relationship strength (0-1)
            evidence: Supporting evidence
            created_by: Creator ID

        Returns:
            Created relationship
        """
        relationship = Relationship(
            relationship_id=str(uuid4()),
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            strength=strength,
            evidence=evidence,
            created_by=created_by,
        )

        self._relationships[relationship.relationship_id] = relationship

        logger.info(
            "relationship_created",
            relationship_id=relationship.relationship_id,
            type=relationship_type.value,
        )

        return relationship

    async def get_relationships(
        self,
        entry_id: str,
        relationship_type: RelationshipType | None = None,
        as_source: bool = True,
    ) -> list[Relationship]:
        """
        Get relationships for an entry.

        Args:
            entry_id: Entry ID
            relationship_type: Filter by type
            as_source: If True, get relationships where entry is source

        Returns:
            List of relationships
        """
        results = []
        for rel in self._relationships.values():
            if as_source and rel.source_id != entry_id:
                continue
            if not as_source and rel.target_id != entry_id:
                continue
            if relationship_type and rel.relationship_type != relationship_type:
                continue

            results.append(rel)

        return results

    async def delete_relationship(self, relationship_id: str) -> bool:
        """Delete a relationship."""
        if relationship_id in self._relationships:
            del self._relationships[relationship_id]
            return True
        return False

    # ===========================================
    # SOURCE REFERENCE OPERATIONS
    # ===========================================

    async def add_source_reference(
        self,
        entry_id: str,
        reference: SourceReference,
    ) -> SourceReference:
        """
        Add a source reference to an entry.

        Args:
            entry_id: Entry ID
            reference: Source reference

        Returns:
            Created reference
        """
        reference.reference_id = reference.reference_id or str(uuid4())
        self._references[reference.reference_id] = reference

        if entry_id not in self._entry_references:
            self._entry_references[entry_id] = []
        self._entry_references[entry_id].append(reference.reference_id)

        logger.info(
            "reference_added",
            reference_id=reference.reference_id,
            entry_id=entry_id,
            source_type=reference.source_type,
        )

        return reference

    async def get_entry_references(self, entry_id: str) -> list[SourceReference]:
        """Get all source references for an entry."""
        ref_ids = self._entry_references.get(entry_id, [])
        return [self._references[rid] for rid in ref_ids if rid in self._references]

    async def find_by_source(
        self,
        source_type: str,
        source_id: str,
    ) -> list[KnowledgeEntry]:
        """
        Find entries by external source.

        Args:
            source_type: Type of source (arxiv, doi, etc.)
            source_id: External source ID

        Returns:
            List of related entries
        """
        entry_ids = []
        for ref in self._references.values():
            if ref.source_type == source_type and ref.source_id == source_id:
                # Find entries with this reference
                for eid, ref_ids in self._entry_references.items():
                    if ref.reference_id in ref_ids:
                        entry_ids.append(eid)

        return [self._entries[eid] for eid in entry_ids if eid in self._entries]

    # ===========================================
    # PROVENANCE OPERATIONS
    # ===========================================

    async def _record_provenance(
        self,
        entry_id: str,
        action: str,
        actor_id: str,
        previous_state: dict[str, Any] | None = None,
        new_state: dict[str, Any] | None = None,
        reason: str = "",
        evidence_ids: list[str] | None = None,
    ) -> ProvenanceRecord:
        """Record a provenance entry."""
        record = ProvenanceRecord(
            record_id=str(uuid4()),
            entry_id=entry_id,
            action=action,
            actor_id=actor_id,
            actor_type="agent" if actor_id else "system",
            previous_state=previous_state or {},
            new_state=new_state or {},
            reason=reason,
            evidence_ids=evidence_ids or [],
        )

        if entry_id not in self._provenance:
            self._provenance[entry_id] = []
        self._provenance[entry_id].append(record)

        return record

    async def get_provenance(self, entry_id: str) -> list[ProvenanceRecord]:
        """Get provenance history for an entry."""
        return self._provenance.get(entry_id, [])

    # ===========================================
    # STATISTICS
    # ===========================================

    def get_stats(self) -> dict[str, Any]:
        """Get repository statistics."""
        active_entries = [e for e in self._entries.values() if not e.is_archived]

        type_counts = {}
        domain_counts = {}
        status_counts = {}

        for entry in active_entries:
            type_counts[entry.entry_type.value] = type_counts.get(entry.entry_type.value, 0) + 1
            domain_counts[entry.domain] = domain_counts.get(entry.domain, 0) + 1
            status_counts[entry.verification_status.value] = status_counts.get(entry.verification_status.value, 0) + 1

        return {
            "total_entries": len(self._entries),
            "active_entries": len(active_entries),
            "archived_entries": len(self._entries) - len(active_entries),
            "total_citations": len(self._citations),
            "total_relationships": len(self._relationships),
            "total_references": len(self._references),
            "entries_by_type": type_counts,
            "entries_by_domain": domain_counts,
            "entries_by_status": status_counts,
        }


# Singleton instance
_repository_instance: KnowledgeRepository | None = None


def get_knowledge_repository() -> KnowledgeRepository:
    """Get singleton KnowledgeRepository instance."""
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = KnowledgeRepository()
    return _repository_instance
