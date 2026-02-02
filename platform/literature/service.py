"""Main Literature Service coordinating all literature clients."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from platform.literature.arxiv_client import ArxivClient, get_arxiv_client
from platform.literature.base import (
    Author,
    Citation,
    LiteratureReview,
    Paper,
    PaperSource,
    Recommendation,
    SearchQuery,
    SearchResponse,
    SearchResult,
)
from platform.literature.config import DOMAIN_TO_CATEGORIES, get_settings
from platform.literature.pubmed_client import PubMedClient, get_pubmed_client
from platform.literature.semantic_scholar_client import (
    SemanticScholarClient,
    get_semantic_scholar_client,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class LiteratureStats:
    """Statistics about literature operations."""

    total_searches: int = 0
    total_papers_fetched: int = 0
    papers_by_source: dict[str, int] = field(default_factory=dict)
    cache_hits: int = 0
    cache_misses: int = 0


class LiteratureService:
    """
    Main service for literature integration.

    Coordinates all literature clients to provide unified search,
    paper retrieval, and citation analysis across multiple sources.
    """

    def __init__(self):
        """Initialize literature service."""
        self._arxiv = get_arxiv_client()
        self._pubmed = get_pubmed_client()
        self._s2 = get_semantic_scholar_client()
        self._cache: dict[str, Paper] = {}
        self._stats = LiteratureStats()

    # ===========================================
    # SEARCH OPERATIONS
    # ===========================================

    async def search(
        self,
        query: str,
        sources: list[PaperSource] | None = None,
        limit: int = 20,
        offset: int = 0,
        year_from: int | None = None,
        year_to: int | None = None,
        categories: list[str] | None = None,
        open_access_only: bool = False,
        min_citations: int = 0,
    ) -> SearchResponse:
        """
        Search papers across multiple sources.

        Args:
            query: Search query
            sources: Sources to search (defaults to all)
            limit: Maximum results per source
            offset: Starting offset
            year_from: Filter by start year
            year_to: Filter by end year
            categories: Filter by categories
            open_access_only: Only open access papers
            min_citations: Minimum citation count

        Returns:
            Combined search response
        """
        start_time = datetime.utcnow()
        self._stats.total_searches += 1

        # Default to all sources
        if sources is None:
            sources = [PaperSource.ARXIV, PaperSource.PUBMED, PaperSource.SEMANTIC_SCHOLAR]

        # Build year filter string for Semantic Scholar
        year_filter = None
        if year_from and year_to:
            year_filter = f"{year_from}-{year_to}"
        elif year_from:
            year_filter = f"{year_from}-"
        elif year_to:
            year_filter = f"-{year_to}"

        # Execute searches in parallel
        tasks = []

        if PaperSource.ARXIV in sources:
            tasks.append(self._search_arxiv(query, limit, offset, categories))

        if PaperSource.PUBMED in sources:
            tasks.append(self._search_pubmed(query, limit, offset, year_from, year_to))

        if PaperSource.SEMANTIC_SCHOLAR in sources:
            tasks.append(
                self._search_s2(query, limit, offset, year_filter, open_access_only, min_citations)
            )

        # Gather results
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results
        all_results: list[SearchResult] = []
        sources_queried: list[str] = []
        total_count = 0

        for result in results_list:
            if isinstance(result, Exception):
                logger.exception("search_source_error", error=str(result))
                continue

            if isinstance(result, SearchResponse):
                all_results.extend(result.results)
                sources_queried.extend(result.sources_queried)
                total_count += result.total_count

        # Deduplicate by DOI or title
        deduplicated = self._deduplicate_results(all_results)

        # Sort by relevance score
        deduplicated.sort(key=lambda r: r.score, reverse=True)

        # Apply overall limit
        final_results = deduplicated[:limit]

        # Cache papers
        for result in final_results:
            self._cache_paper(result.paper)

        query_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.info(
            "literature_search_completed",
            query=query[:50],
            sources=sources_queried,
            results=len(final_results),
            query_time_ms=round(query_time_ms, 2),
        )

        return SearchResponse(
            results=final_results,
            total_count=total_count,
            query_time_ms=query_time_ms,
            sources_queried=sources_queried,
        )

    async def search_by_domain(
        self,
        domain: str,
        query: str,
        limit: int = 20,
    ) -> SearchResponse:
        """
        Search papers filtered by research domain.

        Args:
            domain: Research domain (ml_ai, computational_biology, etc.)
            query: Search query
            limit: Maximum results

        Returns:
            Search response
        """
        categories = DOMAIN_TO_CATEGORIES.get(domain, [])

        return await self.search(
            query=query,
            limit=limit,
            categories=categories,
        )

    # ===========================================
    # PAPER RETRIEVAL
    # ===========================================

    async def get_paper(
        self,
        identifier: str,
        source: PaperSource | None = None,
    ) -> Paper | None:
        """
        Get a paper by identifier.

        Args:
            identifier: Paper ID (DOI, arXiv ID, PMID, or S2 ID)
            source: Source to query (auto-detected if None)

        Returns:
            Paper or None
        """
        # Check cache first
        if identifier in self._cache:
            self._stats.cache_hits += 1
            return self._cache[identifier]

        self._stats.cache_misses += 1

        # Auto-detect source from identifier format
        if source is None:
            source = self._detect_source(identifier)

        paper = None

        if source == PaperSource.ARXIV:
            paper = await self._arxiv.get_paper(identifier)
        elif source == PaperSource.PUBMED:
            paper = await self._pubmed.get_paper(identifier)
        elif source == PaperSource.SEMANTIC_SCHOLAR:
            paper = await self._s2.get_paper(identifier)
        elif source == PaperSource.DOI:
            # Try S2 first for DOI
            paper = await self._s2.get_paper_by_doi(identifier)

        if paper:
            self._cache_paper(paper)
            self._stats.total_papers_fetched += 1
            self._stats.papers_by_source[source.value] = (
                self._stats.papers_by_source.get(source.value, 0) + 1
            )

        return paper

    async def get_paper_by_doi(self, doi: str) -> Paper | None:
        """Get paper by DOI."""
        return await self.get_paper(doi, PaperSource.DOI)

    async def get_paper_by_arxiv(self, arxiv_id: str) -> Paper | None:
        """Get paper by arXiv ID."""
        return await self.get_paper(arxiv_id, PaperSource.ARXIV)

    async def get_paper_by_pmid(self, pmid: str) -> Paper | None:
        """Get paper by PubMed ID."""
        return await self.get_paper(pmid, PaperSource.PUBMED)

    async def get_papers(
        self,
        identifiers: list[str],
        source: PaperSource | None = None,
    ) -> list[Paper]:
        """
        Get multiple papers by identifiers.

        Args:
            identifiers: List of paper identifiers
            source: Source to query

        Returns:
            List of papers
        """
        tasks = [self.get_paper(id, source) for id in identifiers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        papers = []
        for result in results:
            if isinstance(result, Paper):
                papers.append(result)

        return papers

    # ===========================================
    # CITATION OPERATIONS
    # ===========================================

    async def get_citations(
        self,
        paper_id: str,
        source: PaperSource | None = None,
        limit: int = 100,
    ) -> list[Citation]:
        """
        Get papers that cite the given paper.

        Args:
            paper_id: Paper identifier
            source: Source to query
            limit: Maximum results

        Returns:
            List of citations
        """
        if source is None:
            source = self._detect_source(paper_id)

        if source == PaperSource.SEMANTIC_SCHOLAR or source == PaperSource.DOI:
            # Use S2 for best citation data
            s2_id = paper_id
            if source == PaperSource.DOI:
                s2_id = f"DOI:{paper_id}"
            return await self._s2.get_citations(s2_id, limit=limit)

        elif source == PaperSource.PUBMED:
            pmids = await self._pubmed.get_citations(paper_id)
            # Convert to Citation objects
            citations = []
            for pmid in pmids[:limit]:
                citations.append(
                    Citation(
                        citing_paper_id=pmid,
                        cited_paper_id=paper_id,
                    )
                )
            return citations

        return []

    async def get_references(
        self,
        paper_id: str,
        source: PaperSource | None = None,
        limit: int = 100,
    ) -> list[Citation]:
        """
        Get papers referenced by the given paper.

        Args:
            paper_id: Paper identifier
            source: Source to query
            limit: Maximum results

        Returns:
            List of references as citations
        """
        if source is None:
            source = self._detect_source(paper_id)

        if source == PaperSource.SEMANTIC_SCHOLAR or source == PaperSource.DOI:
            s2_id = paper_id
            if source == PaperSource.DOI:
                s2_id = f"DOI:{paper_id}"
            return await self._s2.get_references(s2_id, limit=limit)

        elif source == PaperSource.PUBMED:
            pmids = await self._pubmed.get_references(paper_id)
            citations = []
            for pmid in pmids[:limit]:
                citations.append(
                    Citation(
                        citing_paper_id=paper_id,
                        cited_paper_id=pmid,
                    )
                )
            return citations

        return []

    async def get_citation_graph(
        self,
        paper_id: str,
        depth: int = 1,
        direction: str = "both",  # "citations", "references", "both"
        limit_per_level: int = 20,
    ) -> dict[str, Any]:
        """
        Build citation graph around a paper.

        Args:
            paper_id: Center paper ID
            depth: How many levels to traverse
            direction: Direction to traverse
            limit_per_level: Max papers per level

        Returns:
            Graph with papers and citation edges
        """
        papers: dict[str, Paper] = {}
        edges: list[dict[str, str]] = []
        visited: set[str] = set()

        queue: list[tuple[str, int]] = [(paper_id, 0)]

        while queue:
            current_id, current_depth = queue.pop(0)

            if current_id in visited or current_depth > depth:
                continue

            visited.add(current_id)

            # Get paper
            paper = await self.get_paper(current_id)
            if paper:
                papers[current_id] = paper

            if current_depth < depth:
                # Get citations
                if direction in ("citations", "both"):
                    citations = await self.get_citations(current_id, limit=limit_per_level)
                    for cit in citations:
                        edges.append({
                            "from": cit.citing_paper_id,
                            "to": cit.cited_paper_id,
                            "type": "cites",
                        })
                        if cit.citing_paper_id not in visited:
                            queue.append((cit.citing_paper_id, current_depth + 1))

                # Get references
                if direction in ("references", "both"):
                    references = await self.get_references(current_id, limit=limit_per_level)
                    for ref in references:
                        edges.append({
                            "from": ref.citing_paper_id,
                            "to": ref.cited_paper_id,
                            "type": "cites",
                        })
                        if ref.cited_paper_id not in visited:
                            queue.append((ref.cited_paper_id, current_depth + 1))

        return {
            "papers": {pid: p.to_dict() for pid, p in papers.items()},
            "edges": edges,
            "center": paper_id,
        }

    # ===========================================
    # RECOMMENDATION OPERATIONS
    # ===========================================

    async def get_recommendations(
        self,
        paper_ids: list[str],
        limit: int = 20,
    ) -> list[Recommendation]:
        """
        Get paper recommendations based on input papers.

        Args:
            paper_ids: Paper IDs to base recommendations on
            limit: Maximum recommendations

        Returns:
            List of recommended papers
        """
        # Convert to S2 IDs
        s2_ids = []
        for pid in paper_ids:
            source = self._detect_source(pid)
            if source == PaperSource.DOI:
                s2_ids.append(f"DOI:{pid}")
            elif source == PaperSource.ARXIV:
                s2_ids.append(f"ARXIV:{pid}")
            elif source == PaperSource.PUBMED:
                s2_ids.append(f"PMID:{pid}")
            else:
                s2_ids.append(pid)

        return await self._s2.get_recommendations(s2_ids, limit=limit)

    async def get_related_papers(
        self,
        paper_id: str,
        limit: int = 20,
    ) -> list[Paper]:
        """
        Get papers related to the given paper.

        Args:
            paper_id: Paper ID
            limit: Maximum results

        Returns:
            List of related papers
        """
        source = self._detect_source(paper_id)

        if source == PaperSource.PUBMED:
            pmids = await self._pubmed.get_related(paper_id, max_results=limit)
            return await self.get_papers(pmids, PaperSource.PUBMED)

        # Use recommendations for other sources
        recs = await self.get_recommendations([paper_id], limit=limit)
        return [r.paper for r in recs]

    # ===========================================
    # AUTHOR OPERATIONS
    # ===========================================

    async def search_authors(
        self,
        query: str,
        limit: int = 10,
    ) -> list[Author]:
        """Search for authors."""
        return await self._s2.search_authors(query, limit=limit)

    async def get_author_papers(
        self,
        author_id: str,
        limit: int = 100,
    ) -> list[Paper]:
        """Get papers by an author."""
        return await self._s2.get_author_papers(author_id, limit=limit)

    # ===========================================
    # LITERATURE REVIEW
    # ===========================================

    async def create_literature_review(
        self,
        topic: str,
        query: str,
        max_papers: int = 50,
    ) -> LiteratureReview:
        """
        Create a literature review on a topic.

        Args:
            topic: Review topic
            query: Search query
            max_papers: Maximum papers to include

        Returns:
            Literature review
        """
        # Search for papers
        response = await self.search(
            query=query,
            limit=max_papers,
            sources=[PaperSource.SEMANTIC_SCHOLAR, PaperSource.ARXIV],
        )

        papers = [r.paper for r in response.results]

        # Organize by year
        sections: dict[str, list[str]] = {
            "recent": [],
            "seminal": [],
            "highly_cited": [],
        }

        current_year = datetime.utcnow().year

        for paper in papers:
            if paper.year and paper.year >= current_year - 2:
                sections["recent"].append(paper.paper_id)
            if paper.citation_count >= 100:
                sections["highly_cited"].append(paper.paper_id)

        # Sort by citations to find seminal works
        by_citations = sorted(papers, key=lambda p: p.citation_count, reverse=True)
        sections["seminal"] = [p.paper_id for p in by_citations[:10]]

        review = LiteratureReview(
            title=f"Literature Review: {topic}",
            topic=topic,
            papers=papers,
            sections=sections,
        )

        logger.info("literature_review_created", topic=topic, papers=len(papers))

        return review

    # ===========================================
    # UTILITY METHODS
    # ===========================================

    def get_stats(self) -> LiteratureStats:
        """Get service statistics."""
        return self._stats

    async def close(self) -> None:
        """Close all clients."""
        await self._arxiv.close()
        await self._pubmed.close()
        await self._s2.close()

    async def _search_arxiv(
        self,
        query: str,
        limit: int,
        offset: int,
        categories: list[str] | None,
    ) -> SearchResponse:
        """Search arXiv."""
        return await self._arxiv.search(
            query=query,
            max_results=limit,
            start=offset,
            categories=categories,
        )

    async def _search_pubmed(
        self,
        query: str,
        limit: int,
        offset: int,
        year_from: int | None,
        year_to: int | None,
    ) -> SearchResponse:
        """Search PubMed."""
        date_from = f"{year_from}/01/01" if year_from else None
        date_to = f"{year_to}/12/31" if year_to else None

        return await self._pubmed.search(
            query=query,
            max_results=limit,
            start=offset,
            date_from=date_from,
            date_to=date_to,
        )

    async def _search_s2(
        self,
        query: str,
        limit: int,
        offset: int,
        year_filter: str | None,
        open_access_only: bool,
        min_citations: int,
    ) -> SearchResponse:
        """Search Semantic Scholar."""
        return await self._s2.search(
            query=query,
            limit=limit,
            offset=offset,
            year=year_filter,
            open_access_only=open_access_only,
            min_citation_count=min_citations if min_citations > 0 else None,
        )

    def _deduplicate_results(
        self,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """Deduplicate results by DOI or title."""
        seen_dois: set[str] = set()
        seen_titles: set[str] = set()
        unique: list[SearchResult] = []

        for result in results:
            paper = result.paper

            # Check DOI
            if paper.doi:
                if paper.doi in seen_dois:
                    continue
                seen_dois.add(paper.doi)

            # Check title (normalized)
            title_key = paper.title.lower().strip()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)

            unique.append(result)

        return unique

    def _detect_source(self, identifier: str) -> PaperSource:
        """Detect source from identifier format."""
        identifier = identifier.strip()

        # Check prefixes
        if identifier.lower().startswith("doi:"):
            return PaperSource.DOI
        if identifier.lower().startswith("arxiv:"):
            return PaperSource.ARXIV
        if identifier.lower().startswith("pmid:"):
            return PaperSource.PUBMED

        # Check DOI format
        if identifier.startswith("10."):
            return PaperSource.DOI

        # Check arXiv format (YYMM.NNNNN or category/NNNNNNN)
        if "/" in identifier or (len(identifier) >= 9 and identifier[4] == "."):
            return PaperSource.ARXIV

        # Check PMID format (numeric)
        if identifier.isdigit():
            return PaperSource.PUBMED

        # Default to Semantic Scholar
        return PaperSource.SEMANTIC_SCHOLAR

    def _cache_paper(self, paper: Paper) -> None:
        """Add paper to cache."""
        # Cache by various identifiers
        if paper.doi:
            self._cache[paper.doi] = paper
        if paper.arxiv_id:
            self._cache[paper.arxiv_id] = paper
        if paper.pubmed_id:
            self._cache[paper.pubmed_id] = paper
        if paper.semantic_scholar_id:
            self._cache[paper.semantic_scholar_id] = paper
        self._cache[paper.paper_id] = paper


# Singleton instance
_literature_service: LiteratureService | None = None


def get_literature_service() -> LiteratureService:
    """Get singleton LiteratureService instance."""
    global _literature_service
    if _literature_service is None:
        _literature_service = LiteratureService()
    return _literature_service
