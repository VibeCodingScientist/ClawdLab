"""Main knowledge management service coordinating all knowledge operations."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from platform.knowledge.base import (
    Citation,
    EntryType,
    GraphQueryResult,
    KnowledgeEntry,
    Relationship,
    RelationshipType,
    SearchQuery,
    SearchResponse,
    SourceReference,
    VerificationStatus,
)
from platform.knowledge.config import get_settings
from platform.knowledge.graph import KnowledgeGraphService, get_graph_service
from platform.knowledge.provenance import (
    CitationTracker,
    ProvenanceTracker,
    SourceManager,
    get_citation_tracker,
    get_provenance_tracker,
    get_source_manager,
)
from platform.knowledge.repository import KnowledgeRepository, get_knowledge_repository
from platform.knowledge.search import SemanticSearchService, get_search_service
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class KnowledgeOperationResult:
    """Result of a knowledge operation."""

    success: bool
    entry_id: str | None = None
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeSummary:
    """Summary of knowledge base state."""

    total_entries: int
    entries_by_type: dict[str, int]
    entries_by_domain: dict[str, int]
    entries_by_status: dict[str, int]
    total_citations: int
    total_relationships: int
    total_sources: int
    recent_entries: list[KnowledgeEntry]
    top_domains: list[tuple[str, int]]


class KnowledgeManagementService:
    """
    Main service for knowledge management.

    Coordinates all knowledge operations including:
    - Entry CRUD operations
    - Semantic search
    - Citation and provenance tracking
    - Knowledge graph operations
    """

    def __init__(self, mcp_tool_provider: Any | None = None):
        """
        Initialize knowledge management service.

        Args:
            mcp_tool_provider: Optional MCP tool provider
        """
        self._repository = get_knowledge_repository()
        self._search_service = get_search_service(mcp_tool_provider)
        self._graph_service = get_graph_service(mcp_tool_provider)
        self._citation_tracker = get_citation_tracker()
        self._provenance_tracker = get_provenance_tracker()
        self._source_manager = get_source_manager()
        self._mcp_provider = mcp_tool_provider

    # ===========================================
    # ENTRY OPERATIONS
    # ===========================================

    async def create_entry(
        self,
        entry_type: EntryType,
        title: str,
        content: str,
        domain: str,
        subdomain: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        created_by: str = "",
        confidence_score: float = 0.0,
        source_id: str | None = None,
        auto_index: bool = True,
    ) -> KnowledgeOperationResult:
        """
        Create a new knowledge entry.

        Args:
            entry_type: Type of entry
            title: Entry title
            content: Entry content
            domain: Domain category
            subdomain: Subdomain category
            tags: Entry tags
            metadata: Additional metadata
            created_by: Creator ID
            confidence_score: Initial confidence score
            source_id: Original source ID
            auto_index: Automatically index for search

        Returns:
            Operation result
        """
        try:
            entry = KnowledgeEntry(
                entry_id=str(uuid4()),
                entry_type=entry_type,
                title=title,
                content=content,
                domain=domain,
                subdomain=subdomain,
                tags=tags or [],
                metadata=metadata or {},
                confidence_score=confidence_score,
                source_id=source_id,
            )

            created_entry = await self._repository.create_entry(
                entry=entry,
                created_by=created_by,
            )

            # Auto-index for search
            if auto_index:
                await self._search_service.index_entry(created_entry)

            logger.info(
                "knowledge_entry_created",
                entry_id=created_entry.entry_id,
                type=entry_type.value,
                domain=domain,
            )

            return KnowledgeOperationResult(
                success=True,
                entry_id=created_entry.entry_id,
                message="Entry created successfully",
                data={"entry": created_entry.to_dict()},
            )

        except Exception as e:
            logger.exception("entry_creation_failed", error=str(e))
            return KnowledgeOperationResult(
                success=False,
                message=f"Failed to create entry: {str(e)}",
            )

    async def get_entry(self, entry_id: str) -> KnowledgeEntry | None:
        """Get a knowledge entry by ID."""
        return await self._repository.get_entry(entry_id)

    async def update_entry(
        self,
        entry_id: str,
        updates: dict[str, Any],
        updated_by: str = "",
        reason: str = "",
        reindex: bool = True,
    ) -> KnowledgeOperationResult:
        """
        Update a knowledge entry.

        Args:
            entry_id: Entry ID
            updates: Fields to update
            updated_by: ID of updater
            reason: Reason for update
            reindex: Re-index for search

        Returns:
            Operation result
        """
        try:
            updated_entry = await self._repository.update_entry(
                entry_id=entry_id,
                updates=updates,
                updated_by=updated_by,
                reason=reason,
            )

            if not updated_entry:
                return KnowledgeOperationResult(
                    success=False,
                    message=f"Entry not found: {entry_id}",
                )

            # Re-index if content changed
            if reindex and ("content" in updates or "title" in updates):
                await self._search_service.index_entry(updated_entry)

            return KnowledgeOperationResult(
                success=True,
                entry_id=entry_id,
                message="Entry updated successfully",
                data={"entry": updated_entry.to_dict()},
            )

        except Exception as e:
            logger.exception("entry_update_failed", entry_id=entry_id, error=str(e))
            return KnowledgeOperationResult(
                success=False,
                message=f"Failed to update entry: {str(e)}",
            )

    async def delete_entry(
        self,
        entry_id: str,
        deleted_by: str = "",
        reason: str = "",
    ) -> KnowledgeOperationResult:
        """
        Delete (archive) a knowledge entry.

        Args:
            entry_id: Entry ID
            deleted_by: ID of deleter
            reason: Reason for deletion

        Returns:
            Operation result
        """
        try:
            success = await self._repository.delete_entry(
                entry_id=entry_id,
                deleted_by=deleted_by,
                reason=reason,
            )

            if not success:
                return KnowledgeOperationResult(
                    success=False,
                    message=f"Entry not found: {entry_id}",
                )

            return KnowledgeOperationResult(
                success=True,
                entry_id=entry_id,
                message="Entry archived successfully",
            )

        except Exception as e:
            logger.exception("entry_deletion_failed", entry_id=entry_id, error=str(e))
            return KnowledgeOperationResult(
                success=False,
                message=f"Failed to delete entry: {str(e)}",
            )

    async def list_entries(
        self,
        entry_type: EntryType | None = None,
        domain: str | None = None,
        verification_status: VerificationStatus | None = None,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeEntry]:
        """List knowledge entries with filtering."""
        return await self._repository.list_entries(
            entry_type=entry_type,
            domain=domain,
            verification_status=verification_status,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )

    # ===========================================
    # SEARCH OPERATIONS
    # ===========================================

    async def search(
        self,
        query: str,
        entry_types: list[EntryType] | None = None,
        domains: list[str] | None = None,
        verification_statuses: list[VerificationStatus] | None = None,
        tags: list[str] | None = None,
        min_confidence: float = 0.0,
        use_semantic: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        """
        Search knowledge entries.

        Args:
            query: Search query
            entry_types: Filter by entry types
            domains: Filter by domains
            verification_statuses: Filter by verification status
            tags: Filter by tags
            min_confidence: Minimum confidence score
            use_semantic: Use semantic search
            limit: Maximum results
            offset: Result offset

        Returns:
            Search response
        """
        search_query = SearchQuery(
            query=query,
            entry_types=entry_types or [],
            domains=domains or [],
            verification_statuses=verification_statuses or [],
            tags=tags or [],
            min_confidence=min_confidence,
            use_semantic=use_semantic,
            limit=limit,
            offset=offset,
        )

        return await self._search_service.search(search_query)

    async def find_similar(
        self,
        entry_id: str,
        limit: int = 10,
        min_similarity: float | None = None,
    ) -> list[KnowledgeEntry]:
        """Find entries similar to the given entry."""
        results = await self._search_service.find_similar(
            entry_id=entry_id,
            limit=limit,
            min_similarity=min_similarity,
        )
        return [r.entry for r in results]

    # ===========================================
    # VERIFICATION OPERATIONS
    # ===========================================

    async def verify_entry(
        self,
        entry_id: str,
        verifier_id: str,
        status: VerificationStatus,
        confidence: float,
        evidence: str = "",
        evidence_entry_ids: list[str] | None = None,
    ) -> KnowledgeOperationResult:
        """
        Record verification of an entry.

        Args:
            entry_id: Entry ID
            verifier_id: ID of verifier (agent or engine)
            status: New verification status
            confidence: Confidence score
            evidence: Textual evidence
            evidence_entry_ids: IDs of evidence entries

        Returns:
            Operation result
        """
        try:
            await self._provenance_tracker.record_verification(
                entry_id=entry_id,
                verifier_id=verifier_id,
                new_status=status,
                confidence=confidence,
                evidence=evidence,
                evidence_ids=evidence_entry_ids,
            )

            # Create supporting/refuting relationships
            if evidence_entry_ids:
                rel_type = (
                    RelationshipType.SUPPORTS
                    if status in (VerificationStatus.VERIFIED, VerificationStatus.PARTIAL)
                    else RelationshipType.REFUTES
                )

                for evidence_id in evidence_entry_ids:
                    await self._graph_service.create_relationship(
                        source_id=evidence_id,
                        target_id=entry_id,
                        relationship_type=rel_type,
                        strength=confidence,
                        evidence=evidence,
                        created_by=verifier_id,
                    )

            return KnowledgeOperationResult(
                success=True,
                entry_id=entry_id,
                message=f"Entry verified as {status.value}",
                data={
                    "status": status.value,
                    "confidence": confidence,
                },
            )

        except Exception as e:
            logger.exception("verification_failed", entry_id=entry_id, error=str(e))
            return KnowledgeOperationResult(
                success=False,
                message=f"Verification failed: {str(e)}",
            )

    # ===========================================
    # CITATION OPERATIONS
    # ===========================================

    async def add_citation(
        self,
        source_entry_id: str,
        target_entry_id: str,
        citation_type: str = "reference",
        context: str = "",
    ) -> KnowledgeOperationResult:
        """
        Add a citation between entries.

        Args:
            source_entry_id: Citing entry ID
            target_entry_id: Cited entry ID
            citation_type: Type of citation
            context: Citation context

        Returns:
            Operation result
        """
        try:
            citation = await self._citation_tracker.create_citation(
                source_entry_id=source_entry_id,
                target_entry_id=target_entry_id,
                citation_type=citation_type,
                context=context,
            )

            return KnowledgeOperationResult(
                success=True,
                message="Citation created successfully",
                data={"citation": citation.to_dict()},
            )

        except Exception as e:
            logger.exception("citation_creation_failed", error=str(e))
            return KnowledgeOperationResult(
                success=False,
                message=f"Failed to create citation: {str(e)}",
            )

    async def get_citations(
        self,
        entry_id: str,
    ) -> dict[str, list[Citation]]:
        """Get citations for an entry (both made and received)."""
        made = await self._citation_tracker.get_citations_by(entry_id)
        received = await self._citation_tracker.get_citations_of(entry_id)

        return {
            "made": made,
            "received": received,
        }

    # ===========================================
    # SOURCE REFERENCE OPERATIONS
    # ===========================================

    async def add_source(
        self,
        entry_id: str,
        source_type: str,
        source_id: str,
        url: str = "",
        title: str = "",
        authors: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeOperationResult:
        """
        Add a source reference to an entry.

        Args:
            entry_id: Entry ID
            source_type: Source type (arxiv, doi, github, etc.)
            source_id: External source ID
            url: Source URL
            title: Source title
            authors: Source authors
            metadata: Additional metadata

        Returns:
            Operation result
        """
        try:
            source = SourceReference(
                source_type=source_type,
                source_id=source_id,
                url=url,
                title=title,
                authors=authors or [],
                metadata=metadata or {},
            )

            result = await self._provenance_tracker.add_source(
                entry_id=entry_id,
                source=source,
            )

            return KnowledgeOperationResult(
                success=True,
                message="Source reference added",
                data={"source": result.to_dict()},
            )

        except Exception as e:
            logger.exception("source_addition_failed", error=str(e))
            return KnowledgeOperationResult(
                success=False,
                message=f"Failed to add source: {str(e)}",
            )

    async def get_entry_sources(self, entry_id: str) -> list[SourceReference]:
        """Get all sources for an entry."""
        return await self._source_manager.get_entry_sources(entry_id)

    # ===========================================
    # RELATIONSHIP OPERATIONS
    # ===========================================

    async def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: RelationshipType,
        strength: float = 1.0,
        evidence: str = "",
        created_by: str = "",
    ) -> KnowledgeOperationResult:
        """
        Add a relationship between entries.

        Args:
            source_id: Source entry ID
            target_id: Target entry ID
            relationship_type: Type of relationship
            strength: Relationship strength
            evidence: Supporting evidence
            created_by: Creator ID

        Returns:
            Operation result
        """
        try:
            relationship = await self._graph_service.create_relationship(
                source_id=source_id,
                target_id=target_id,
                relationship_type=relationship_type,
                strength=strength,
                evidence=evidence,
                created_by=created_by,
            )

            return KnowledgeOperationResult(
                success=True,
                message="Relationship created",
                data={"relationship": relationship.to_dict()},
            )

        except Exception as e:
            logger.exception("relationship_creation_failed", error=str(e))
            return KnowledgeOperationResult(
                success=False,
                message=f"Failed to create relationship: {str(e)}",
            )

    async def get_related_entries(
        self,
        entry_id: str,
        relationship_type: RelationshipType | None = None,
        min_strength: float = 0.0,
        limit: int = 20,
    ) -> list[tuple[KnowledgeEntry, float]]:
        """Get entries related to the given entry."""
        return await self._graph_service.find_related(
            entry_id=entry_id,
            relationship_type=relationship_type,
            min_strength=min_strength,
            limit=limit,
        )

    # ===========================================
    # GRAPH OPERATIONS
    # ===========================================

    async def get_knowledge_graph(
        self,
        entry_id: str,
        depth: int = 2,
        relationship_types: list[RelationshipType] | None = None,
    ) -> GraphQueryResult:
        """
        Get knowledge graph centered on an entry.

        Args:
            entry_id: Center entry ID
            depth: Graph depth
            relationship_types: Filter by relationship types

        Returns:
            Graph with nodes and edges
        """
        return await self._graph_service.get_neighbors(
            entry_id=entry_id,
            relationship_types=relationship_types,
            max_depth=depth,
        )

    async def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> list[list[str]]:
        """Find paths between two entries."""
        result = await self._graph_service.find_paths(
            source_id=source_id,
            target_id=target_id,
            max_depth=max_depth,
        )
        return result.paths

    # ===========================================
    # PROVENANCE OPERATIONS
    # ===========================================

    async def get_entry_history(self, entry_id: str) -> list[dict[str, Any]]:
        """Get modification history for an entry."""
        chain = await self._provenance_tracker.get_provenance_chain(entry_id)
        return [r.to_dict() for r in chain.records]

    # ===========================================
    # SUMMARY OPERATIONS
    # ===========================================

    async def get_summary(self) -> KnowledgeSummary:
        """Get summary of knowledge base state."""
        stats = self._repository.get_stats()

        # Get recent entries
        recent = await self._repository.list_entries(limit=10)

        # Get top domains
        domain_counts = stats.get("entries_by_domain", {})
        top_domains = sorted(
            domain_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return KnowledgeSummary(
            total_entries=stats.get("total_entries", 0),
            entries_by_type=stats.get("entries_by_type", {}),
            entries_by_domain=stats.get("entries_by_domain", {}),
            entries_by_status=stats.get("entries_by_status", {}),
            total_citations=stats.get("total_citations", 0),
            total_relationships=stats.get("total_relationships", 0),
            total_sources=stats.get("total_references", 0),
            recent_entries=recent,
            top_domains=top_domains,
        )

    # ===========================================
    # BULK OPERATIONS
    # ===========================================

    async def import_entries(
        self,
        entries: list[dict[str, Any]],
        created_by: str = "",
    ) -> list[KnowledgeOperationResult]:
        """
        Import multiple entries.

        Args:
            entries: List of entry dictionaries
            created_by: Creator ID

        Returns:
            List of operation results
        """
        results = []

        for entry_data in entries:
            result = await self.create_entry(
                entry_type=EntryType(entry_data.get("entry_type", "claim")),
                title=entry_data.get("title", ""),
                content=entry_data.get("content", ""),
                domain=entry_data.get("domain", ""),
                subdomain=entry_data.get("subdomain", ""),
                tags=entry_data.get("tags", []),
                metadata=entry_data.get("metadata", {}),
                created_by=created_by,
                confidence_score=entry_data.get("confidence_score", 0.0),
            )
            results.append(result)

        successful = sum(1 for r in results if r.success)
        logger.info(
            "bulk_import_completed",
            total=len(entries),
            successful=successful,
        )

        return results

    async def reindex_all(self) -> int:
        """Re-index all entries for search."""
        return await self._search_service.reindex_all()


# Singleton instance
_knowledge_service_instance: KnowledgeManagementService | None = None


def get_knowledge_service(
    mcp_tool_provider: Any | None = None,
) -> KnowledgeManagementService:
    """Get singleton KnowledgeManagementService instance."""
    global _knowledge_service_instance
    if _knowledge_service_instance is None:
        _knowledge_service_instance = KnowledgeManagementService(mcp_tool_provider)
    return _knowledge_service_instance
