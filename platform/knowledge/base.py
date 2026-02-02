"""Base classes and data structures for Knowledge Management."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class EntryType(Enum):
    """Types of knowledge entries."""

    CLAIM = "claim"
    FINDING = "finding"
    HYPOTHESIS = "hypothesis"
    METHOD = "method"
    DATASET = "dataset"
    MODEL = "model"
    PUBLICATION = "publication"


class VerificationStatus(Enum):
    """Verification status of claims."""

    VERIFIED = "verified"
    REFUTED = "refuted"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"
    PENDING = "pending"
    DISPUTED = "disputed"


class RelationshipType(Enum):
    """Types of relationships between entries."""

    SUPPORTS = "supports"
    REFUTES = "refutes"
    CITES = "cites"
    EXTENDS = "extends"
    USES = "uses"
    DERIVED_FROM = "derived_from"
    RELATED_TO = "related_to"
    PART_OF = "part_of"
    VERSION_OF = "version_of"


# ===========================================
# KNOWLEDGE ENTRY DATA CLASSES
# ===========================================


@dataclass
class KnowledgeEntry:
    """A knowledge entry in the system."""

    entry_id: str = field(default_factory=lambda: str(uuid4()))
    entry_type: EntryType = EntryType.CLAIM
    content: str = ""
    title: str = ""
    domain: str = ""
    subdomain: str = ""
    verification_status: VerificationStatus = VerificationStatus.PENDING
    confidence_score: float = 0.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    source_id: str | None = None  # Original source (workflow, agent, etc.)
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    is_archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "entry_type": self.entry_type.value,
            "content": self.content,
            "title": self.title,
            "domain": self.domain,
            "subdomain": self.subdomain,
            "verification_status": self.verification_status.value,
            "confidence_score": self.confidence_score,
            "tags": self.tags,
            "metadata": self.metadata,
            "source_id": self.source_id,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "is_archived": self.is_archived,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeEntry":
        return cls(
            entry_id=data.get("entry_id", str(uuid4())),
            entry_type=EntryType(data.get("entry_type", "claim")),
            content=data.get("content", ""),
            title=data.get("title", ""),
            domain=data.get("domain", ""),
            subdomain=data.get("subdomain", ""),
            verification_status=VerificationStatus(data.get("verification_status", "pending")),
            confidence_score=data.get("confidence_score", 0.0),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),
            source_id=data.get("source_id"),
            created_by=data.get("created_by", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
            version=data.get("version", 1),
            is_archived=data.get("is_archived", False),
        )


@dataclass
class Citation:
    """A citation linking two entries."""

    citation_id: str = field(default_factory=lambda: str(uuid4()))
    source_entry_id: str = ""
    target_entry_id: str = ""
    citation_type: str = ""  # inline, reference, footnote
    context: str = ""  # Surrounding text context
    page_number: int | None = None
    section: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "source_entry_id": self.source_entry_id,
            "target_entry_id": self.target_entry_id,
            "citation_type": self.citation_type,
            "context": self.context,
            "page_number": self.page_number,
            "section": self.section,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Relationship:
    """A relationship between two knowledge entries."""

    relationship_id: str = field(default_factory=lambda: str(uuid4()))
    source_id: str = ""
    target_id: str = ""
    relationship_type: RelationshipType = RelationshipType.RELATED_TO
    strength: float = 1.0  # Relationship strength 0-1
    evidence: str = ""  # Supporting evidence
    metadata: dict[str, Any] = field(default_factory=dict)
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relationship_id": self.relationship_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type.value,
            "strength": self.strength,
            "evidence": self.evidence,
            "metadata": self.metadata,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }


# ===========================================
# PROVENANCE DATA CLASSES
# ===========================================


@dataclass
class ProvenanceRecord:
    """Record of provenance for a knowledge entry."""

    record_id: str = field(default_factory=lambda: str(uuid4()))
    entry_id: str = ""
    action: str = ""  # created, updated, verified, refuted, archived
    actor_id: str = ""  # Agent or user who performed action
    actor_type: str = ""  # agent, user, system
    previous_state: dict[str, Any] = field(default_factory=dict)
    new_state: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "entry_id": self.entry_id,
            "action": self.action,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "reason": self.reason,
            "evidence_ids": self.evidence_ids,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SourceReference:
    """Reference to an external source."""

    reference_id: str = field(default_factory=lambda: str(uuid4()))
    source_type: str = ""  # arxiv, pubmed, doi, url, github
    source_id: str = ""  # External ID (arxiv id, DOI, etc.)
    url: str = ""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    publication_date: datetime | None = None
    venue: str = ""  # Journal, conference, etc.
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "url": self.url,
            "title": self.title,
            "authors": self.authors,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "venue": self.venue,
            "metadata": self.metadata,
        }


# ===========================================
# SEARCH DATA CLASSES
# ===========================================


@dataclass
class SearchQuery:
    """A search query for knowledge entries."""

    query: str = ""
    entry_types: list[EntryType] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    verification_statuses: list[VerificationStatus] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    min_confidence: float = 0.0
    date_from: datetime | None = None
    date_to: datetime | None = None
    created_by: str | None = None
    limit: int = 20
    offset: int = 0
    use_semantic: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "entry_types": [t.value for t in self.entry_types],
            "domains": self.domains,
            "verification_statuses": [s.value for s in self.verification_statuses],
            "tags": self.tags,
            "min_confidence": self.min_confidence,
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "created_by": self.created_by,
            "limit": self.limit,
            "offset": self.offset,
            "use_semantic": self.use_semantic,
        }


@dataclass
class SearchResult:
    """A search result."""

    entry: KnowledgeEntry
    score: float = 0.0
    highlights: list[str] = field(default_factory=list)
    matched_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry": self.entry.to_dict(),
            "score": self.score,
            "highlights": self.highlights,
            "matched_fields": self.matched_fields,
        }


@dataclass
class SearchResponse:
    """Response from a search query."""

    results: list[SearchResult] = field(default_factory=list)
    total_count: int = 0
    query_time_ms: float = 0.0
    facets: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "total_count": self.total_count,
            "query_time_ms": self.query_time_ms,
            "facets": self.facets,
        }


# ===========================================
# GRAPH DATA CLASSES
# ===========================================


@dataclass
class GraphNode:
    """A node in the knowledge graph."""

    node_id: str
    entry_type: EntryType
    title: str
    domain: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "entry_type": self.entry_type.value,
            "title": self.title,
            "domain": self.domain,
            "properties": self.properties,
        }


@dataclass
class GraphEdge:
    """An edge in the knowledge graph."""

    source_id: str
    target_id: str
    relationship_type: RelationshipType
    strength: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type.value,
            "strength": self.strength,
            "properties": self.properties,
        }


@dataclass
class GraphQueryResult:
    """Result of a graph query."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    paths: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "paths": self.paths,
        }


__all__ = [
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
]
