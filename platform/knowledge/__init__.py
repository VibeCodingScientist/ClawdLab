"""Knowledge Management System.

This module provides comprehensive knowledge management capabilities:
- Knowledge entries with versioning and provenance tracking
- Semantic search using vector embeddings
- Citation and source reference tracking
- Knowledge graph with relationship analysis
- Verification status and history tracking

The knowledge management layer integrates with all verification engines
to store and organize verified claims, findings, and research artifacts.
"""

from platform.knowledge.base import (
    # Enums
    EntryType,
    RelationshipType,
    VerificationStatus,
    # Entry classes
    Citation,
    KnowledgeEntry,
    Relationship,
    # Provenance classes
    ProvenanceRecord,
    SourceReference,
    # Search classes
    SearchQuery,
    SearchResponse,
    SearchResult,
    # Graph classes
    GraphEdge,
    GraphNode,
    GraphQueryResult,
)
from platform.knowledge.config import (
    CONFIDENCE_LEVELS,
    DOMAIN_CATEGORIES,
    ENTRY_TYPES,
    RELATIONSHIP_TYPES,
    VERIFICATION_STATUSES,
    KnowledgeSettings,
    get_settings,
)
from platform.knowledge.graph import (
    ClusterResult,
    GraphMetrics,
    KnowledgeGraphService,
    PathResult,
    get_graph_service,
)
from platform.knowledge.provenance import (
    CitationChain,
    CitationTracker,
    ProvenanceChain,
    ProvenanceTracker,
    SourceManager,
    VerificationHistory,
    get_citation_tracker,
    get_provenance_tracker,
    get_source_manager,
)
from platform.knowledge.repository import (
    KnowledgeRepository,
    get_knowledge_repository,
)
from platform.knowledge.search import (
    EmbeddingService,
    SemanticSearchService,
    get_search_service,
)
from platform.knowledge.service import (
    KnowledgeManagementService,
    KnowledgeOperationResult,
    KnowledgeSummary,
    get_knowledge_service,
)

__all__ = [
    # Config
    "get_settings",
    "KnowledgeSettings",
    "ENTRY_TYPES",
    "RELATIONSHIP_TYPES",
    "VERIFICATION_STATUSES",
    "DOMAIN_CATEGORIES",
    "CONFIDENCE_LEVELS",
    # Enums
    "EntryType",
    "VerificationStatus",
    "RelationshipType",
    # Entry classes
    "KnowledgeEntry",
    "Citation",
    "Relationship",
    # Provenance classes
    "ProvenanceRecord",
    "SourceReference",
    # Search classes
    "SearchQuery",
    "SearchResult",
    "SearchResponse",
    # Graph classes
    "GraphNode",
    "GraphEdge",
    "GraphQueryResult",
    # Repository
    "KnowledgeRepository",
    "get_knowledge_repository",
    # Search service
    "EmbeddingService",
    "SemanticSearchService",
    "get_search_service",
    # Provenance services
    "CitationTracker",
    "CitationChain",
    "ProvenanceTracker",
    "ProvenanceChain",
    "VerificationHistory",
    "SourceManager",
    "get_citation_tracker",
    "get_provenance_tracker",
    "get_source_manager",
    # Graph service
    "KnowledgeGraphService",
    "PathResult",
    "ClusterResult",
    "GraphMetrics",
    "get_graph_service",
    # Main service
    "KnowledgeManagementService",
    "KnowledgeOperationResult",
    "KnowledgeSummary",
    "get_knowledge_service",
]
