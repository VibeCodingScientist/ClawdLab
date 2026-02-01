"""Citation and provenance tracking for knowledge entries."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from platform.knowledge.base import (
    Citation,
    KnowledgeEntry,
    ProvenanceRecord,
    Relationship,
    RelationshipType,
    SourceReference,
    VerificationStatus,
)
from platform.knowledge.config import get_settings
from platform.knowledge.repository import get_knowledge_repository
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class CitationChain:
    """A chain of citations from source to target."""

    source_id: str
    target_id: str
    chain: list[Citation]
    total_depth: int


@dataclass
class ProvenanceChain:
    """Full provenance chain for an entry."""

    entry_id: str
    records: list[ProvenanceRecord]
    sources: list[SourceReference]
    citations_made: list[Citation]
    citations_received: list[Citation]


@dataclass
class VerificationHistory:
    """Verification history for an entry."""

    entry_id: str
    current_status: VerificationStatus
    history: list[dict[str, Any]]
    verifiers: list[str]


class CitationTracker:
    """
    Service for tracking and analyzing citations.

    Manages citation relationships between knowledge entries
    and provides citation analysis capabilities.
    """

    def __init__(self):
        """Initialize citation tracker."""
        self._repository = get_knowledge_repository()

    async def create_citation(
        self,
        source_entry_id: str,
        target_entry_id: str,
        citation_type: str = "reference",
        context: str = "",
        page_number: int | None = None,
        section: str = "",
    ) -> Citation:
        """
        Create a citation from one entry to another.

        Args:
            source_entry_id: ID of the citing entry
            target_entry_id: ID of the cited entry
            citation_type: Type of citation (inline, reference, footnote)
            context: Surrounding text context
            page_number: Page number if applicable
            section: Section where citation appears

        Returns:
            Created citation
        """
        # Verify both entries exist
        source = await self._repository.get_entry(source_entry_id)
        target = await self._repository.get_entry(target_entry_id)

        if not source:
            raise ValueError(f"Source entry not found: {source_entry_id}")
        if not target:
            raise ValueError(f"Target entry not found: {target_entry_id}")

        # Create citation
        citation = await self._repository.create_citation(
            source_entry_id=source_entry_id,
            target_entry_id=target_entry_id,
            citation_type=citation_type,
            context=context,
        )

        # Also create a CITES relationship
        await self._repository.create_relationship(
            source_id=source_entry_id,
            target_id=target_entry_id,
            relationship_type=RelationshipType.CITES,
            evidence=context,
        )

        logger.info(
            "citation_created",
            source=source_entry_id,
            target=target_entry_id,
            type=citation_type,
        )

        return citation

    async def get_citations_by(self, entry_id: str) -> list[Citation]:
        """Get all citations made by an entry."""
        return await self._repository.get_citations_for_entry(
            entry_id=entry_id,
            as_source=True,
        )

    async def get_citations_of(self, entry_id: str) -> list[Citation]:
        """Get all citations received by an entry."""
        return await self._repository.get_citations_for_entry(
            entry_id=entry_id,
            as_source=False,
        )

    async def get_citation_count(self, entry_id: str) -> dict[str, int]:
        """
        Get citation counts for an entry.

        Returns:
            Dict with 'made' and 'received' counts
        """
        made = await self.get_citations_by(entry_id)
        received = await self.get_citations_of(entry_id)

        return {
            "made": len(made),
            "received": len(received),
        }

    async def find_citation_chain(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> CitationChain | None:
        """
        Find citation chain from source to target.

        Args:
            source_id: Starting entry ID
            target_id: Target entry ID
            max_depth: Maximum chain depth

        Returns:
            Citation chain if found, None otherwise
        """
        visited = set()
        queue: list[tuple[str, list[Citation]]] = [(source_id, [])]

        while queue:
            current_id, path = queue.pop(0)

            if current_id == target_id:
                return CitationChain(
                    source_id=source_id,
                    target_id=target_id,
                    chain=path,
                    total_depth=len(path),
                )

            if current_id in visited or len(path) >= max_depth:
                continue

            visited.add(current_id)

            # Get citations from current entry
            citations = await self.get_citations_by(current_id)
            for citation in citations:
                if citation.target_entry_id not in visited:
                    queue.append((citation.target_entry_id, path + [citation]))

        return None

    async def get_co_citations(
        self,
        entry_id: str,
        limit: int = 20,
    ) -> list[tuple[str, int]]:
        """
        Find entries frequently co-cited with this entry.

        Args:
            entry_id: Entry ID
            limit: Maximum results

        Returns:
            List of (entry_id, co_citation_count) tuples
        """
        # Get entries that cite this entry
        citations_of = await self.get_citations_of(entry_id)
        citing_entries = [c.source_entry_id for c in citations_of]

        # Find other entries cited by these
        co_citation_counts: dict[str, int] = {}
        for citing_id in citing_entries:
            citations_by = await self.get_citations_by(citing_id)
            for citation in citations_by:
                target = citation.target_entry_id
                if target != entry_id:
                    co_citation_counts[target] = co_citation_counts.get(target, 0) + 1

        # Sort by count
        sorted_items = sorted(
            co_citation_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return sorted_items[:limit]


class ProvenanceTracker:
    """
    Service for tracking provenance of knowledge entries.

    Records all modifications, verifications, and source information
    to maintain full audit trail.
    """

    def __init__(self):
        """Initialize provenance tracker."""
        self._repository = get_knowledge_repository()

    async def record_action(
        self,
        entry_id: str,
        action: str,
        actor_id: str,
        actor_type: str = "agent",
        previous_state: dict[str, Any] | None = None,
        new_state: dict[str, Any] | None = None,
        reason: str = "",
        evidence_ids: list[str] | None = None,
    ) -> ProvenanceRecord:
        """
        Record a provenance action.

        Args:
            entry_id: Entry ID
            action: Action type (created, updated, verified, etc.)
            actor_id: ID of actor performing action
            actor_type: Type of actor (agent, user, system)
            previous_state: State before action
            new_state: State after action
            reason: Reason for action
            evidence_ids: IDs of supporting evidence

        Returns:
            Created provenance record
        """
        record = ProvenanceRecord(
            record_id=str(uuid4()),
            entry_id=entry_id,
            action=action,
            actor_id=actor_id,
            actor_type=actor_type,
            previous_state=previous_state or {},
            new_state=new_state or {},
            reason=reason,
            evidence_ids=evidence_ids or [],
        )

        # The repository handles internal storage
        # This is a higher-level interface for explicit provenance recording

        logger.info(
            "provenance_recorded",
            entry_id=entry_id,
            action=action,
            actor=actor_id,
        )

        return record

    async def record_verification(
        self,
        entry_id: str,
        verifier_id: str,
        new_status: VerificationStatus,
        confidence: float,
        evidence: str = "",
        evidence_ids: list[str] | None = None,
    ) -> ProvenanceRecord:
        """
        Record a verification action.

        Args:
            entry_id: Entry ID
            verifier_id: ID of verifier (agent or engine)
            new_status: New verification status
            confidence: Confidence score
            evidence: Textual evidence
            evidence_ids: IDs of evidence entries

        Returns:
            Provenance record
        """
        entry = await self._repository.get_entry(entry_id)
        if not entry:
            raise ValueError(f"Entry not found: {entry_id}")

        previous_state = entry.to_dict()

        # Update entry verification status
        await self._repository.update_entry(
            entry_id=entry_id,
            updates={
                "verification_status": new_status,
                "confidence_score": confidence,
            },
            updated_by=verifier_id,
            reason=f"Verification: {new_status.value}",
        )

        # Get updated entry
        updated_entry = await self._repository.get_entry(entry_id)

        record = await self.record_action(
            entry_id=entry_id,
            action="verified",
            actor_id=verifier_id,
            actor_type="verifier",
            previous_state=previous_state,
            new_state=updated_entry.to_dict() if updated_entry else {},
            reason=evidence,
            evidence_ids=evidence_ids,
        )

        logger.info(
            "verification_recorded",
            entry_id=entry_id,
            verifier=verifier_id,
            status=new_status.value,
            confidence=confidence,
        )

        return record

    async def add_source(
        self,
        entry_id: str,
        source: SourceReference,
        added_by: str = "",
    ) -> SourceReference:
        """
        Add a source reference to an entry.

        Args:
            entry_id: Entry ID
            source: Source reference
            added_by: ID of actor adding source

        Returns:
            Added source reference
        """
        result = await self._repository.add_source_reference(entry_id, source)

        # Record provenance
        await self.record_action(
            entry_id=entry_id,
            action="source_added",
            actor_id=added_by,
            reason=f"Added source: {source.source_type}:{source.source_id}",
        )

        return result

    async def get_provenance_chain(self, entry_id: str) -> ProvenanceChain:
        """
        Get full provenance chain for an entry.

        Args:
            entry_id: Entry ID

        Returns:
            Complete provenance chain
        """
        records = await self._repository.get_provenance(entry_id)
        sources = await self._repository.get_entry_references(entry_id)

        citations_made = await self._repository.get_citations_for_entry(
            entry_id, as_source=True
        )
        citations_received = await self._repository.get_citations_for_entry(
            entry_id, as_source=False
        )

        return ProvenanceChain(
            entry_id=entry_id,
            records=records,
            sources=sources,
            citations_made=citations_made,
            citations_received=citations_received,
        )

    async def get_verification_history(self, entry_id: str) -> VerificationHistory:
        """
        Get verification history for an entry.

        Args:
            entry_id: Entry ID

        Returns:
            Verification history
        """
        entry = await self._repository.get_entry(entry_id)
        if not entry:
            raise ValueError(f"Entry not found: {entry_id}")

        provenance = await self._repository.get_provenance(entry_id)

        # Filter verification-related records
        verification_records = [
            r for r in provenance if r.action in ("verified", "created", "updated")
        ]

        # Build history
        history = []
        verifiers = set()

        for record in verification_records:
            if record.action == "verified":
                verifiers.add(record.actor_id)

            history.append({
                "timestamp": record.timestamp.isoformat(),
                "action": record.action,
                "actor": record.actor_id,
                "status": record.new_state.get("verification_status", "unknown"),
                "confidence": record.new_state.get("confidence_score", 0.0),
                "reason": record.reason,
            })

        return VerificationHistory(
            entry_id=entry_id,
            current_status=entry.verification_status,
            history=history,
            verifiers=list(verifiers),
        )

    async def find_derived_entries(
        self,
        entry_id: str,
        max_depth: int = 3,
    ) -> list[tuple[str, int]]:
        """
        Find entries derived from this entry.

        Args:
            entry_id: Entry ID
            max_depth: Maximum derivation depth

        Returns:
            List of (entry_id, depth) tuples
        """
        derived = []
        visited = set()
        queue: list[tuple[str, int]] = [(entry_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)

            if current_id in visited or depth > max_depth:
                continue

            visited.add(current_id)

            if current_id != entry_id:
                derived.append((current_id, depth))

            # Get entries that derive from this one
            relationships = await self._repository.get_relationships(
                entry_id=current_id,
                relationship_type=RelationshipType.DERIVED_FROM,
                as_source=False,  # Find entries where this is the target (they derive from it)
            )

            for rel in relationships:
                if rel.source_id not in visited:
                    queue.append((rel.source_id, depth + 1))

        return derived


class SourceManager:
    """
    Service for managing external source references.

    Handles linking knowledge entries to external sources like
    papers, datasets, and code repositories.
    """

    def __init__(self):
        """Initialize source manager."""
        self._repository = get_knowledge_repository()

    async def add_arxiv_source(
        self,
        entry_id: str,
        arxiv_id: str,
        title: str = "",
        authors: list[str] | None = None,
        abstract: str = "",
    ) -> SourceReference:
        """Add an arXiv paper as source."""
        ref = SourceReference(
            source_type="arxiv",
            source_id=arxiv_id,
            url=f"https://arxiv.org/abs/{arxiv_id}",
            title=title,
            authors=authors or [],
            metadata={"abstract": abstract},
        )
        return await self._repository.add_source_reference(entry_id, ref)

    async def add_doi_source(
        self,
        entry_id: str,
        doi: str,
        title: str = "",
        authors: list[str] | None = None,
        venue: str = "",
        publication_date: datetime | None = None,
    ) -> SourceReference:
        """Add a DOI-referenced publication as source."""
        ref = SourceReference(
            source_type="doi",
            source_id=doi,
            url=f"https://doi.org/{doi}",
            title=title,
            authors=authors or [],
            venue=venue,
            publication_date=publication_date,
        )
        return await self._repository.add_source_reference(entry_id, ref)

    async def add_github_source(
        self,
        entry_id: str,
        repo: str,
        commit: str = "",
        file_path: str = "",
    ) -> SourceReference:
        """Add a GitHub repository as source."""
        ref = SourceReference(
            source_type="github",
            source_id=f"{repo}@{commit}" if commit else repo,
            url=f"https://github.com/{repo}",
            metadata={
                "commit": commit,
                "file_path": file_path,
            },
        )
        return await self._repository.add_source_reference(entry_id, ref)

    async def add_dataset_source(
        self,
        entry_id: str,
        dataset_name: str,
        source_url: str,
        version: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SourceReference:
        """Add a dataset as source."""
        ref = SourceReference(
            source_type="dataset",
            source_id=dataset_name,
            url=source_url,
            title=dataset_name,
            metadata={
                "version": version,
                **(metadata or {}),
            },
        )
        return await self._repository.add_source_reference(entry_id, ref)

    async def find_entries_by_source(
        self,
        source_type: str,
        source_id: str,
    ) -> list[KnowledgeEntry]:
        """Find all entries referencing a given source."""
        return await self._repository.find_by_source(source_type, source_id)

    async def get_entry_sources(self, entry_id: str) -> list[SourceReference]:
        """Get all sources for an entry."""
        return await self._repository.get_entry_references(entry_id)


# Singleton instances
_citation_tracker_instance: CitationTracker | None = None
_provenance_tracker_instance: ProvenanceTracker | None = None
_source_manager_instance: SourceManager | None = None


def get_citation_tracker() -> CitationTracker:
    """Get singleton CitationTracker instance."""
    global _citation_tracker_instance
    if _citation_tracker_instance is None:
        _citation_tracker_instance = CitationTracker()
    return _citation_tracker_instance


def get_provenance_tracker() -> ProvenanceTracker:
    """Get singleton ProvenanceTracker instance."""
    global _provenance_tracker_instance
    if _provenance_tracker_instance is None:
        _provenance_tracker_instance = ProvenanceTracker()
    return _provenance_tracker_instance


def get_source_manager() -> SourceManager:
    """Get singleton SourceManager instance."""
    global _source_manager_instance
    if _source_manager_instance is None:
        _source_manager_instance = SourceManager()
    return _source_manager_instance
