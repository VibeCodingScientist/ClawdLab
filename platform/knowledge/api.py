"""FastAPI endpoints for Knowledge Management System."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from platform.knowledge.base import (
    EntryType,
    RelationshipType,
    VerificationStatus,
)
from platform.knowledge.service import get_knowledge_service
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class CreateEntryRequest(BaseModel):
    """Request to create a knowledge entry."""

    entry_type: str = Field(description="Entry type (claim, finding, hypothesis, etc.)")
    title: str = Field(description="Entry title")
    content: str = Field(description="Entry content")
    domain: str = Field(description="Domain category")
    subdomain: str = Field(default="", description="Subdomain category")
    tags: list[str] = Field(default_factory=list, description="Entry tags")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    source_id: str | None = Field(default=None, description="Original source ID")


class UpdateEntryRequest(BaseModel):
    """Request to update a knowledge entry."""

    title: str | None = None
    content: str | None = None
    domain: str | None = None
    subdomain: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    confidence_score: float | None = None
    reason: str = Field(default="", description="Reason for update")


class VerifyEntryRequest(BaseModel):
    """Request to verify an entry."""

    verifier_id: str = Field(description="ID of verifier")
    status: str = Field(description="Verification status")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    evidence: str = Field(default="", description="Textual evidence")
    evidence_entry_ids: list[str] = Field(default_factory=list, description="Evidence entry IDs")


class SearchRequest(BaseModel):
    """Request to search knowledge entries."""

    query: str = Field(description="Search query")
    entry_types: list[str] = Field(default_factory=list, description="Filter by entry types")
    domains: list[str] = Field(default_factory=list, description="Filter by domains")
    verification_statuses: list[str] = Field(default_factory=list, description="Filter by status")
    tags: list[str] = Field(default_factory=list, description="Filter by tags")
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Min confidence")
    use_semantic: bool = Field(default=True, description="Use semantic search")
    limit: int = Field(default=20, ge=1, le=100, description="Max results")
    offset: int = Field(default=0, ge=0, description="Result offset")


class AddCitationRequest(BaseModel):
    """Request to add a citation."""

    source_entry_id: str = Field(description="Citing entry ID")
    target_entry_id: str = Field(description="Cited entry ID")
    citation_type: str = Field(default="reference", description="Citation type")
    context: str = Field(default="", description="Citation context")


class AddSourceRequest(BaseModel):
    """Request to add a source reference."""

    source_type: str = Field(description="Source type (arxiv, doi, github, etc.)")
    source_id: str = Field(description="External source ID")
    url: str = Field(default="", description="Source URL")
    title: str = Field(default="", description="Source title")
    authors: list[str] = Field(default_factory=list, description="Source authors")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AddRelationshipRequest(BaseModel):
    """Request to add a relationship."""

    source_id: str = Field(description="Source entry ID")
    target_id: str = Field(description="Target entry ID")
    relationship_type: str = Field(description="Relationship type")
    strength: float = Field(default=1.0, ge=0.0, le=1.0, description="Relationship strength")
    evidence: str = Field(default="", description="Supporting evidence")


class GraphQueryRequest(BaseModel):
    """Request for graph query."""

    entry_id: str = Field(description="Center entry ID")
    depth: int = Field(default=2, ge=1, le=5, description="Graph depth")
    relationship_types: list[str] = Field(default_factory=list, description="Filter by types")


class BulkImportRequest(BaseModel):
    """Request to import multiple entries."""

    entries: list[dict[str, Any]] = Field(description="List of entry data")


# ===========================================
# ENTRY ENDPOINTS
# ===========================================


@router.post("/entries")
async def create_entry(
    request: CreateEntryRequest,
    created_by: str = Query(default="", description="Creator ID"),
):
    """Create a new knowledge entry."""
    service = get_knowledge_service()

    try:
        entry_type = EntryType(request.entry_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entry type: {request.entry_type}",
        )

    result = await service.create_entry(
        entry_type=entry_type,
        title=request.title,
        content=request.content,
        domain=request.domain,
        subdomain=request.subdomain,
        tags=request.tags,
        metadata=request.metadata,
        created_by=created_by,
        confidence_score=request.confidence_score,
        source_id=request.source_id,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return result.data


@router.get("/entries/{entry_id}")
async def get_entry(entry_id: str):
    """Get a knowledge entry by ID."""
    service = get_knowledge_service()
    entry = await service.get_entry(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    return entry.to_dict()


@router.put("/entries/{entry_id}")
async def update_entry(
    entry_id: str,
    request: UpdateEntryRequest,
    updated_by: str = Query(default="", description="Updater ID"),
):
    """Update a knowledge entry."""
    service = get_knowledge_service()

    updates = {k: v for k, v in request.model_dump().items() if v is not None and k != "reason"}

    result = await service.update_entry(
        entry_id=entry_id,
        updates=updates,
        updated_by=updated_by,
        reason=request.reason,
    )

    if not result.success:
        raise HTTPException(status_code=404 if "not found" in result.message else 400, detail=result.message)

    return result.data


@router.delete("/entries/{entry_id}")
async def delete_entry(
    entry_id: str,
    deleted_by: str = Query(default="", description="Deleter ID"),
    reason: str = Query(default="", description="Deletion reason"),
):
    """Delete (archive) a knowledge entry."""
    service = get_knowledge_service()

    result = await service.delete_entry(
        entry_id=entry_id,
        deleted_by=deleted_by,
        reason=reason,
    )

    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)

    return {"status": "archived", "entry_id": entry_id}


@router.get("/entries")
async def list_entries(
    entry_type: str | None = Query(default=None, description="Filter by entry type"),
    domain: str | None = Query(default=None, description="Filter by domain"),
    verification_status: str | None = Query(default=None, description="Filter by status"),
    include_archived: bool = Query(default=False, description="Include archived entries"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Result offset"),
):
    """List knowledge entries with filtering."""
    service = get_knowledge_service()

    # Convert string filters to enums
    entry_type_enum = EntryType(entry_type) if entry_type else None
    status_enum = VerificationStatus(verification_status) if verification_status else None

    entries = await service.list_entries(
        entry_type=entry_type_enum,
        domain=domain,
        verification_status=status_enum,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )

    return {
        "entries": [e.to_dict() for e in entries],
        "count": len(entries),
        "limit": limit,
        "offset": offset,
    }


# ===========================================
# SEARCH ENDPOINTS
# ===========================================


@router.post("/search")
async def search_entries(request: SearchRequest):
    """Search knowledge entries."""
    service = get_knowledge_service()

    # Convert string filters to enums
    entry_types = [EntryType(t) for t in request.entry_types] if request.entry_types else None
    statuses = (
        [VerificationStatus(s) for s in request.verification_statuses]
        if request.verification_statuses
        else None
    )

    response = await service.search(
        query=request.query,
        entry_types=entry_types,
        domains=request.domains if request.domains else None,
        verification_statuses=statuses,
        tags=request.tags if request.tags else None,
        min_confidence=request.min_confidence,
        use_semantic=request.use_semantic,
        limit=request.limit,
        offset=request.offset,
    )

    return response.to_dict()


@router.get("/entries/{entry_id}/similar")
async def find_similar_entries(
    entry_id: str,
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    min_similarity: float = Query(default=0.7, ge=0.0, le=1.0, description="Min similarity"),
):
    """Find entries similar to the given entry."""
    service = get_knowledge_service()

    entries = await service.find_similar(
        entry_id=entry_id,
        limit=limit,
        min_similarity=min_similarity,
    )

    return {
        "entry_id": entry_id,
        "similar": [e.to_dict() for e in entries],
        "count": len(entries),
    }


# ===========================================
# VERIFICATION ENDPOINTS
# ===========================================


@router.post("/entries/{entry_id}/verify")
async def verify_entry(entry_id: str, request: VerifyEntryRequest):
    """Record verification of an entry."""
    service = get_knowledge_service()

    try:
        status = VerificationStatus(request.status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid verification status: {request.status}",
        )

    result = await service.verify_entry(
        entry_id=entry_id,
        verifier_id=request.verifier_id,
        status=status,
        confidence=request.confidence,
        evidence=request.evidence,
        evidence_entry_ids=request.evidence_entry_ids if request.evidence_entry_ids else None,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return result.data


@router.get("/entries/{entry_id}/history")
async def get_entry_history(entry_id: str):
    """Get modification history for an entry."""
    service = get_knowledge_service()

    entry = await service.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    history = await service.get_entry_history(entry_id)

    return {
        "entry_id": entry_id,
        "history": history,
    }


# ===========================================
# CITATION ENDPOINTS
# ===========================================


@router.post("/citations")
async def add_citation(request: AddCitationRequest):
    """Add a citation between entries."""
    service = get_knowledge_service()

    result = await service.add_citation(
        source_entry_id=request.source_entry_id,
        target_entry_id=request.target_entry_id,
        citation_type=request.citation_type,
        context=request.context,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return result.data


@router.get("/entries/{entry_id}/citations")
async def get_entry_citations(entry_id: str):
    """Get citations for an entry."""
    service = get_knowledge_service()

    entry = await service.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    citations = await service.get_citations(entry_id)

    return {
        "entry_id": entry_id,
        "citations_made": [c.to_dict() for c in citations["made"]],
        "citations_received": [c.to_dict() for c in citations["received"]],
    }


# ===========================================
# SOURCE REFERENCE ENDPOINTS
# ===========================================


@router.post("/entries/{entry_id}/sources")
async def add_source_reference(entry_id: str, request: AddSourceRequest):
    """Add a source reference to an entry."""
    service = get_knowledge_service()

    entry = await service.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    result = await service.add_source(
        entry_id=entry_id,
        source_type=request.source_type,
        source_id=request.source_id,
        url=request.url,
        title=request.title,
        authors=request.authors,
        metadata=request.metadata,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return result.data


@router.get("/entries/{entry_id}/sources")
async def get_entry_sources(entry_id: str):
    """Get source references for an entry."""
    service = get_knowledge_service()

    entry = await service.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    sources = await service.get_entry_sources(entry_id)

    return {
        "entry_id": entry_id,
        "sources": [s.to_dict() for s in sources],
    }


# ===========================================
# RELATIONSHIP ENDPOINTS
# ===========================================


@router.post("/relationships")
async def add_relationship(
    request: AddRelationshipRequest,
    created_by: str = Query(default="", description="Creator ID"),
):
    """Add a relationship between entries."""
    service = get_knowledge_service()

    try:
        rel_type = RelationshipType(request.relationship_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid relationship type: {request.relationship_type}",
        )

    result = await service.add_relationship(
        source_id=request.source_id,
        target_id=request.target_id,
        relationship_type=rel_type,
        strength=request.strength,
        evidence=request.evidence,
        created_by=created_by,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return result.data


@router.get("/entries/{entry_id}/related")
async def get_related_entries(
    entry_id: str,
    relationship_type: str | None = Query(default=None, description="Filter by type"),
    min_strength: float = Query(default=0.0, ge=0.0, le=1.0, description="Min strength"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
):
    """Get entries related to the given entry."""
    service = get_knowledge_service()

    entry = await service.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    rel_type = RelationshipType(relationship_type) if relationship_type else None

    related = await service.get_related_entries(
        entry_id=entry_id,
        relationship_type=rel_type,
        min_strength=min_strength,
        limit=limit,
    )

    return {
        "entry_id": entry_id,
        "related": [
            {"entry": e.to_dict(), "strength": s}
            for e, s in related
        ],
    }


# ===========================================
# GRAPH ENDPOINTS
# ===========================================


@router.post("/graph")
async def get_knowledge_graph(request: GraphQueryRequest):
    """Get knowledge graph centered on an entry."""
    service = get_knowledge_service()

    entry = await service.get_entry(request.entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Convert relationship types
    rel_types = (
        [RelationshipType(t) for t in request.relationship_types]
        if request.relationship_types
        else None
    )

    graph = await service.get_knowledge_graph(
        entry_id=request.entry_id,
        depth=request.depth,
        relationship_types=rel_types,
    )

    return graph.to_dict()


@router.get("/graph/path")
async def find_path(
    source_id: str = Query(description="Source entry ID"),
    target_id: str = Query(description="Target entry ID"),
    max_depth: int = Query(default=5, ge=1, le=10, description="Max path length"),
):
    """Find paths between two entries."""
    service = get_knowledge_service()

    # Verify entries exist
    source = await service.get_entry(source_id)
    target = await service.get_entry(target_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source entry not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target entry not found")

    paths = await service.find_path(
        source_id=source_id,
        target_id=target_id,
        max_depth=max_depth,
    )

    return {
        "source_id": source_id,
        "target_id": target_id,
        "paths": paths,
        "path_count": len(paths),
    }


# ===========================================
# SUMMARY AND BULK ENDPOINTS
# ===========================================


@router.get("/summary")
async def get_knowledge_summary():
    """Get summary of knowledge base state."""
    service = get_knowledge_service()
    summary = await service.get_summary()

    return {
        "total_entries": summary.total_entries,
        "entries_by_type": summary.entries_by_type,
        "entries_by_domain": summary.entries_by_domain,
        "entries_by_status": summary.entries_by_status,
        "total_citations": summary.total_citations,
        "total_relationships": summary.total_relationships,
        "total_sources": summary.total_sources,
        "recent_entries": [e.to_dict() for e in summary.recent_entries],
        "top_domains": summary.top_domains,
    }


@router.post("/import")
async def bulk_import(
    request: BulkImportRequest,
    created_by: str = Query(default="", description="Creator ID"),
):
    """Import multiple entries in bulk."""
    service = get_knowledge_service()

    results = await service.import_entries(
        entries=request.entries,
        created_by=created_by,
    )

    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    return {
        "total": len(results),
        "successful": successful,
        "failed": failed,
        "results": [
            {
                "success": r.success,
                "entry_id": r.entry_id,
                "message": r.message,
            }
            for r in results
        ],
    }


@router.post("/reindex")
async def reindex_all():
    """Re-index all entries for search."""
    service = get_knowledge_service()
    count = await service.reindex_all()

    return {
        "status": "completed",
        "entries_indexed": count,
    }
