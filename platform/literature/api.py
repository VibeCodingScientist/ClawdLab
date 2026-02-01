"""FastAPI endpoints for Literature Integration."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from platform.literature.base import PaperSource
from platform.literature.service import get_literature_service
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/literature", tags=["literature"])


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class SearchRequest(BaseModel):
    """Request to search literature."""

    query: str = Field(description="Search query")
    sources: list[str] = Field(
        default_factory=list,
        description="Sources to search (arxiv, pubmed, semantic_scholar)",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Starting offset")
    year_from: int | None = Field(default=None, description="Filter by start year")
    year_to: int | None = Field(default=None, description="Filter by end year")
    categories: list[str] = Field(default_factory=list, description="Filter by categories")
    open_access_only: bool = Field(default=False, description="Only open access papers")
    min_citations: int = Field(default=0, ge=0, description="Minimum citation count")


class DomainSearchRequest(BaseModel):
    """Request to search by domain."""

    domain: str = Field(description="Research domain")
    query: str = Field(description="Search query")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")


class CitationGraphRequest(BaseModel):
    """Request to build citation graph."""

    paper_id: str = Field(description="Center paper ID")
    depth: int = Field(default=1, ge=1, le=3, description="Graph depth")
    direction: str = Field(default="both", description="Direction (citations, references, both)")
    limit_per_level: int = Field(default=20, ge=1, le=50, description="Max papers per level")


class RecommendationRequest(BaseModel):
    """Request for paper recommendations."""

    paper_ids: list[str] = Field(description="Paper IDs to base recommendations on")
    limit: int = Field(default=20, ge=1, le=50, description="Maximum recommendations")


class LiteratureReviewRequest(BaseModel):
    """Request to create literature review."""

    topic: str = Field(description="Review topic")
    query: str = Field(description="Search query")
    max_papers: int = Field(default=50, ge=10, le=200, description="Maximum papers")


# ===========================================
# SEARCH ENDPOINTS
# ===========================================


@router.post("/search")
async def search_literature(request: SearchRequest):
    """Search for papers across literature sources."""
    service = get_literature_service()

    # Convert source strings to enums
    sources = None
    if request.sources:
        source_map = {
            "arxiv": PaperSource.ARXIV,
            "pubmed": PaperSource.PUBMED,
            "semantic_scholar": PaperSource.SEMANTIC_SCHOLAR,
        }
        sources = [source_map[s] for s in request.sources if s in source_map]

    response = await service.search(
        query=request.query,
        sources=sources,
        limit=request.limit,
        offset=request.offset,
        year_from=request.year_from,
        year_to=request.year_to,
        categories=request.categories if request.categories else None,
        open_access_only=request.open_access_only,
        min_citations=request.min_citations,
    )

    return response.to_dict()


@router.post("/search/domain")
async def search_by_domain(request: DomainSearchRequest):
    """Search papers filtered by research domain."""
    service = get_literature_service()

    valid_domains = ["mathematics", "ml_ai", "computational_biology", "materials_science", "bioinformatics"]
    if request.domain not in valid_domains:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain. Must be one of: {valid_domains}",
        )

    response = await service.search_by_domain(
        domain=request.domain,
        query=request.query,
        limit=request.limit,
    )

    return response.to_dict()


@router.get("/search/arxiv")
async def search_arxiv(
    query: str = Query(description="Search query"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum results"),
    categories: str | None = Query(default=None, description="Comma-separated arXiv categories"),
):
    """Search arXiv papers."""
    service = get_literature_service()

    cat_list = categories.split(",") if categories else None

    response = await service.search(
        query=query,
        sources=[PaperSource.ARXIV],
        limit=limit,
        categories=cat_list,
    )

    return response.to_dict()


@router.get("/search/pubmed")
async def search_pubmed(
    query: str = Query(description="Search query"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum results"),
    year_from: int | None = Query(default=None, description="Start year"),
    year_to: int | None = Query(default=None, description="End year"),
):
    """Search PubMed papers."""
    service = get_literature_service()

    response = await service.search(
        query=query,
        sources=[PaperSource.PUBMED],
        limit=limit,
        year_from=year_from,
        year_to=year_to,
    )

    return response.to_dict()


# ===========================================
# PAPER RETRIEVAL ENDPOINTS
# ===========================================


@router.get("/papers/{paper_id}")
async def get_paper(
    paper_id: str,
    source: str | None = Query(default=None, description="Source (arxiv, pubmed, semantic_scholar, doi)"),
):
    """Get a paper by identifier."""
    service = get_literature_service()

    source_enum = None
    if source:
        source_map = {
            "arxiv": PaperSource.ARXIV,
            "pubmed": PaperSource.PUBMED,
            "semantic_scholar": PaperSource.SEMANTIC_SCHOLAR,
            "doi": PaperSource.DOI,
        }
        source_enum = source_map.get(source)

    paper = await service.get_paper(paper_id, source_enum)

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    return paper.to_dict()


@router.get("/papers/doi/{doi:path}")
async def get_paper_by_doi(doi: str):
    """Get a paper by DOI."""
    service = get_literature_service()

    paper = await service.get_paper_by_doi(doi)

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    return paper.to_dict()


@router.get("/papers/arxiv/{arxiv_id}")
async def get_paper_by_arxiv(arxiv_id: str):
    """Get a paper by arXiv ID."""
    service = get_literature_service()

    paper = await service.get_paper_by_arxiv(arxiv_id)

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    return paper.to_dict()


@router.get("/papers/pmid/{pmid}")
async def get_paper_by_pmid(pmid: str):
    """Get a paper by PubMed ID."""
    service = get_literature_service()

    paper = await service.get_paper_by_pmid(pmid)

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    return paper.to_dict()


# ===========================================
# CITATION ENDPOINTS
# ===========================================


@router.get("/papers/{paper_id}/citations")
async def get_citations(
    paper_id: str,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum results"),
):
    """Get papers that cite the given paper."""
    service = get_literature_service()

    citations = await service.get_citations(paper_id, limit=limit)

    return {
        "paper_id": paper_id,
        "citations": [c.to_dict() for c in citations],
        "count": len(citations),
    }


@router.get("/papers/{paper_id}/references")
async def get_references(
    paper_id: str,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum results"),
):
    """Get papers referenced by the given paper."""
    service = get_literature_service()

    references = await service.get_references(paper_id, limit=limit)

    return {
        "paper_id": paper_id,
        "references": [r.to_dict() for r in references],
        "count": len(references),
    }


@router.post("/citation-graph")
async def build_citation_graph(request: CitationGraphRequest):
    """Build citation graph around a paper."""
    service = get_literature_service()

    if request.direction not in ["citations", "references", "both"]:
        raise HTTPException(
            status_code=400,
            detail="Direction must be one of: citations, references, both",
        )

    graph = await service.get_citation_graph(
        paper_id=request.paper_id,
        depth=request.depth,
        direction=request.direction,
        limit_per_level=request.limit_per_level,
    )

    return graph


# ===========================================
# RECOMMENDATION ENDPOINTS
# ===========================================


@router.post("/recommendations")
async def get_recommendations(request: RecommendationRequest):
    """Get paper recommendations based on input papers."""
    service = get_literature_service()

    if not request.paper_ids:
        raise HTTPException(status_code=400, detail="At least one paper ID required")

    recommendations = await service.get_recommendations(
        paper_ids=request.paper_ids,
        limit=request.limit,
    )

    return {
        "based_on": request.paper_ids,
        "recommendations": [r.to_dict() for r in recommendations],
        "count": len(recommendations),
    }


@router.get("/papers/{paper_id}/related")
async def get_related_papers(
    paper_id: str,
    limit: int = Query(default=20, ge=1, le=50, description="Maximum results"),
):
    """Get papers related to the given paper."""
    service = get_literature_service()

    papers = await service.get_related_papers(paper_id, limit=limit)

    return {
        "paper_id": paper_id,
        "related": [p.to_dict() for p in papers],
        "count": len(papers),
    }


# ===========================================
# AUTHOR ENDPOINTS
# ===========================================


@router.get("/authors/search")
async def search_authors(
    query: str = Query(description="Author name query"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum results"),
):
    """Search for authors."""
    service = get_literature_service()

    authors = await service.search_authors(query, limit=limit)

    return {
        "query": query,
        "authors": [a.to_dict() for a in authors],
        "count": len(authors),
    }


@router.get("/authors/{author_id}/papers")
async def get_author_papers(
    author_id: str,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum results"),
):
    """Get papers by an author."""
    service = get_literature_service()

    papers = await service.get_author_papers(author_id, limit=limit)

    return {
        "author_id": author_id,
        "papers": [p.to_dict() for p in papers],
        "count": len(papers),
    }


# ===========================================
# LITERATURE REVIEW ENDPOINTS
# ===========================================


@router.post("/review")
async def create_literature_review(request: LiteratureReviewRequest):
    """Create a literature review on a topic."""
    service = get_literature_service()

    review = await service.create_literature_review(
        topic=request.topic,
        query=request.query,
        max_papers=request.max_papers,
    )

    return review.to_dict()


# ===========================================
# UTILITY ENDPOINTS
# ===========================================


@router.get("/stats")
async def get_statistics():
    """Get literature service statistics."""
    service = get_literature_service()

    stats = service.get_stats()

    return {
        "total_searches": stats.total_searches,
        "total_papers_fetched": stats.total_papers_fetched,
        "papers_by_source": stats.papers_by_source,
        "cache_hits": stats.cache_hits,
        "cache_misses": stats.cache_misses,
    }


@router.get("/sources")
async def get_available_sources():
    """Get available literature sources."""
    return {
        "sources": [
            {
                "id": "arxiv",
                "name": "arXiv",
                "description": "Open-access preprint repository",
                "categories": ["cs", "math", "physics", "q-bio", "stat"],
            },
            {
                "id": "pubmed",
                "name": "PubMed",
                "description": "Biomedical literature database",
                "categories": ["medicine", "biology", "healthcare"],
            },
            {
                "id": "semantic_scholar",
                "name": "Semantic Scholar",
                "description": "AI-powered academic search engine",
                "categories": ["all"],
            },
        ],
    }


@router.get("/domains")
async def get_research_domains():
    """Get supported research domains."""
    return {
        "domains": [
            {
                "id": "mathematics",
                "name": "Mathematics",
                "categories": ["math.*", "cs.LO", "cs.CC"],
            },
            {
                "id": "ml_ai",
                "name": "Machine Learning / AI",
                "categories": ["cs.LG", "cs.AI", "cs.NE", "stat.ML", "cs.CL", "cs.CV"],
            },
            {
                "id": "computational_biology",
                "name": "Computational Biology",
                "categories": ["q-bio.*", "cs.CE"],
            },
            {
                "id": "materials_science",
                "name": "Materials Science",
                "categories": ["cond-mat.mtrl-sci", "physics.chem-ph", "physics.comp-ph"],
            },
            {
                "id": "bioinformatics",
                "name": "Bioinformatics",
                "categories": ["q-bio.GN", "q-bio.QM", "q-bio.BM"],
            },
        ],
    }
