"""Unit tests for LiteratureService."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)

from platform.literature.service import LiteratureService, LiteratureStats
from platform.literature.base import (
    Author,
    Citation,
    Paper,
    PaperSource,
    PublicationType,
    Recommendation,
    SearchResponse,
    SearchResult,
)


class TestLiteratureService:
    """Tests for LiteratureService class."""

    @pytest.fixture
    def mock_arxiv(self) -> AsyncMock:
        """Create mock ArXiv client."""
        mock = AsyncMock()
        mock.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    paper=Paper(
                        paper_id="arxiv-1",
                        title="ArXiv Paper 1",
                        abstract="Abstract",
                        source=PaperSource.ARXIV,
                        arxiv_id="2301.12345",
                    ),
                    score=0.9,
                    source=PaperSource.ARXIV,
                )
            ],
            total_count=1,
            sources_queried=["arxiv"],
        )
        mock.get_paper.return_value = Paper(
            paper_id="arxiv-1",
            title="ArXiv Paper",
            arxiv_id="2301.12345",
            source=PaperSource.ARXIV,
        )
        mock.close.return_value = None
        return mock

    @pytest.fixture
    def mock_pubmed(self) -> AsyncMock:
        """Create mock PubMed client."""
        mock = AsyncMock()
        mock.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    paper=Paper(
                        paper_id="pubmed-1",
                        title="PubMed Paper 1",
                        abstract="Abstract",
                        source=PaperSource.PUBMED,
                        pubmed_id="12345678",
                    ),
                    score=0.8,
                    source=PaperSource.PUBMED,
                )
            ],
            total_count=1,
            sources_queried=["pubmed"],
        )
        mock.get_paper.return_value = Paper(
            paper_id="pubmed-1",
            title="PubMed Paper",
            pubmed_id="12345678",
            source=PaperSource.PUBMED,
        )
        mock.get_citations.return_value = ["12345679", "12345680"]
        mock.get_references.return_value = ["12345681", "12345682"]
        mock.get_related.return_value = ["12345683", "12345684"]
        mock.close.return_value = None
        return mock

    @pytest.fixture
    def mock_s2(self) -> AsyncMock:
        """Create mock Semantic Scholar client."""
        mock = AsyncMock()
        mock.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    paper=Paper(
                        paper_id="s2-1",
                        title="S2 Paper 1",
                        abstract="Abstract",
                        source=PaperSource.SEMANTIC_SCHOLAR,
                        semantic_scholar_id="abc123",
                        doi="10.1234/test",
                    ),
                    score=0.95,
                    source=PaperSource.SEMANTIC_SCHOLAR,
                )
            ],
            total_count=1,
            sources_queried=["semantic_scholar"],
        )
        mock.get_paper.return_value = Paper(
            paper_id="s2-1",
            title="S2 Paper",
            semantic_scholar_id="abc123",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        mock.get_paper_by_doi.return_value = Paper(
            paper_id="doi-paper",
            title="DOI Paper",
            doi="10.1234/test",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        mock.get_citations.return_value = [
            Citation(citing_paper_id="citer-1", cited_paper_id="s2-1"),
            Citation(citing_paper_id="citer-2", cited_paper_id="s2-1"),
        ]
        mock.get_references.return_value = [
            Citation(citing_paper_id="s2-1", cited_paper_id="ref-1"),
            Citation(citing_paper_id="s2-1", cited_paper_id="ref-2"),
        ]
        mock.get_recommendations.return_value = [
            Recommendation(
                paper=Paper(paper_id="rec-1", title="Recommended Paper 1"),
                score=0.9,
            )
        ]
        mock.search_authors.return_value = [
            Author(name="John Doe", h_index=50),
        ]
        mock.get_author_papers.return_value = [
            Paper(paper_id="author-paper-1", title="Author Paper 1"),
        ]
        mock.close.return_value = None
        return mock

    @pytest.fixture
    def service(self, mock_arxiv, mock_pubmed, mock_s2) -> LiteratureService:
        """Create service with mocked clients."""
        svc = LiteratureService()
        svc._arxiv = mock_arxiv
        svc._pubmed = mock_pubmed
        svc._s2 = mock_s2
        return svc

    # ===================================
    # SEARCH TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_search_all_sources(
        self,
        service: LiteratureService,
        mock_arxiv: AsyncMock,
        mock_pubmed: AsyncMock,
        mock_s2: AsyncMock,
    ):
        """Test searching across all sources."""
        response = await service.search(
            query="machine learning",
            limit=20,
        )

        assert response is not None
        # Should have results from all sources
        assert len(response.results) > 0
        mock_arxiv.search.assert_called_once()
        mock_pubmed.search.assert_called_once()
        mock_s2.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_specific_sources(
        self,
        service: LiteratureService,
        mock_arxiv: AsyncMock,
        mock_pubmed: AsyncMock,
        mock_s2: AsyncMock,
    ):
        """Test searching specific sources only."""
        response = await service.search(
            query="machine learning",
            sources=[PaperSource.ARXIV],
            limit=20,
        )

        mock_arxiv.search.assert_called_once()
        mock_pubmed.search.assert_not_called()
        mock_s2.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_with_year_filter(
        self,
        service: LiteratureService,
        mock_s2: AsyncMock,
    ):
        """Test searching with year filter."""
        await service.search(
            query="transformer",
            sources=[PaperSource.SEMANTIC_SCHOLAR],
            year_from=2020,
            year_to=2023,
        )

        call_kwargs = mock_s2.search.call_args[1]
        assert call_kwargs["year"] == "2020-2023"

    @pytest.mark.asyncio
    async def test_search_deduplicates_results(self, service: LiteratureService):
        """Test that search deduplicates by DOI."""
        # Add duplicate DOI to S2 response
        service._s2.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    paper=Paper(
                        paper_id="s2-1",
                        title="Paper A",
                        doi="10.1234/test",
                        source=PaperSource.SEMANTIC_SCHOLAR,
                    ),
                    score=0.9,
                )
            ],
            total_count=1,
            sources_queried=["semantic_scholar"],
        )
        service._arxiv.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    paper=Paper(
                        paper_id="arxiv-1",
                        title="Paper A",
                        doi="10.1234/test",  # Same DOI
                        source=PaperSource.ARXIV,
                    ),
                    score=0.8,
                )
            ],
            total_count=1,
            sources_queried=["arxiv"],
        )

        response = await service.search(
            query="test",
            sources=[PaperSource.ARXIV, PaperSource.SEMANTIC_SCHOLAR],
        )

        # Should deduplicate to 1 result
        assert len(response.results) == 1

    @pytest.mark.asyncio
    async def test_search_by_domain(self, service: LiteratureService):
        """Test searching by research domain."""
        response = await service.search_by_domain(
            domain="ml_ai",
            query="neural networks",
            limit=10,
        )

        assert response is not None

    @pytest.mark.asyncio
    async def test_search_caches_papers(self, service: LiteratureService):
        """Test that search caches fetched papers."""
        await service.search(
            query="test",
            sources=[PaperSource.SEMANTIC_SCHOLAR],
            limit=5,
        )

        # Papers should be cached
        assert len(service._cache) > 0

    @pytest.mark.asyncio
    async def test_search_updates_stats(self, service: LiteratureService):
        """Test that search updates statistics."""
        initial_searches = service._stats.total_searches

        await service.search(query="test", limit=5)

        assert service._stats.total_searches == initial_searches + 1

    # ===================================
    # PAPER RETRIEVAL TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_paper_from_cache(self, service: LiteratureService):
        """Test getting paper from cache."""
        # Pre-populate cache
        cached_paper = Paper(
            paper_id="cached-1",
            title="Cached Paper",
            doi="10.1234/cached",
        )
        service._cache["10.1234/cached"] = cached_paper

        paper = await service.get_paper("10.1234/cached")

        assert paper is not None
        assert paper.title == "Cached Paper"
        assert service._stats.cache_hits == 1

    @pytest.mark.asyncio
    async def test_get_paper_by_doi(
        self,
        service: LiteratureService,
        mock_s2: AsyncMock,
    ):
        """Test getting paper by DOI."""
        paper = await service.get_paper_by_doi("10.1234/test")

        assert paper is not None
        mock_s2.get_paper_by_doi.assert_called_once_with("10.1234/test")

    @pytest.mark.asyncio
    async def test_get_paper_by_arxiv(
        self,
        service: LiteratureService,
        mock_arxiv: AsyncMock,
    ):
        """Test getting paper by arXiv ID."""
        paper = await service.get_paper_by_arxiv("2301.12345")

        assert paper is not None
        mock_arxiv.get_paper.assert_called_once_with("2301.12345")

    @pytest.mark.asyncio
    async def test_get_paper_by_pmid(
        self,
        service: LiteratureService,
        mock_pubmed: AsyncMock,
    ):
        """Test getting paper by PubMed ID."""
        paper = await service.get_paper_by_pmid("12345678")

        assert paper is not None
        mock_pubmed.get_paper.assert_called_once_with("12345678")

    @pytest.mark.asyncio
    async def test_get_paper_auto_detect_source(self, service: LiteratureService):
        """Test that get_paper auto-detects source from identifier."""
        # Test DOI format
        await service.get_paper("10.1234/test")
        # DOI should use S2

        # Test arXiv format
        await service.get_paper("2301.12345")
        # arXiv format should use arxiv client

        # Test PMID format (numeric)
        await service.get_paper("12345678")
        # Numeric should use PubMed

    @pytest.mark.asyncio
    async def test_get_papers_multiple(
        self,
        service: LiteratureService,
        mock_s2: AsyncMock,
    ):
        """Test getting multiple papers."""
        papers = await service.get_papers(
            identifiers=["s2-1", "s2-2", "s2-3"],
            source=PaperSource.SEMANTIC_SCHOLAR,
        )

        # Should return papers (some may be None)
        assert isinstance(papers, list)

    # ===================================
    # CITATION TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_citations_s2(
        self,
        service: LiteratureService,
        mock_s2: AsyncMock,
    ):
        """Test getting citations using Semantic Scholar."""
        citations = await service.get_citations(
            paper_id="abc123",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )

        assert len(citations) == 2
        mock_s2.get_citations.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_citations_pubmed(
        self,
        service: LiteratureService,
        mock_pubmed: AsyncMock,
    ):
        """Test getting citations from PubMed."""
        citations = await service.get_citations(
            paper_id="12345678",
            source=PaperSource.PUBMED,
        )

        assert len(citations) == 2
        mock_pubmed.get_citations.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_references_s2(
        self,
        service: LiteratureService,
        mock_s2: AsyncMock,
    ):
        """Test getting references using Semantic Scholar."""
        references = await service.get_references(
            paper_id="abc123",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )

        assert len(references) == 2
        mock_s2.get_references.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_references_pubmed(
        self,
        service: LiteratureService,
        mock_pubmed: AsyncMock,
    ):
        """Test getting references from PubMed."""
        references = await service.get_references(
            paper_id="12345678",
            source=PaperSource.PUBMED,
        )

        assert len(references) == 2
        mock_pubmed.get_references.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_citation_graph(self, service: LiteratureService):
        """Test building citation graph."""
        # This is a complex operation, just verify it returns expected structure
        graph = await service.get_citation_graph(
            paper_id="abc123",
            depth=1,
            direction="both",
            limit_per_level=10,
        )

        assert "papers" in graph
        assert "edges" in graph
        assert "center" in graph
        assert graph["center"] == "abc123"

    # ===================================
    # RECOMMENDATION TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_recommendations(
        self,
        service: LiteratureService,
        mock_s2: AsyncMock,
    ):
        """Test getting paper recommendations."""
        recommendations = await service.get_recommendations(
            paper_ids=["paper-1", "paper-2"],
            limit=10,
        )

        assert len(recommendations) == 1
        mock_s2.get_recommendations.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_related_papers_pubmed(
        self,
        service: LiteratureService,
        mock_pubmed: AsyncMock,
    ):
        """Test getting related papers from PubMed."""
        related = await service.get_related_papers(
            paper_id="12345678",
            limit=10,
        )

        # PubMed source should be detected for numeric IDs
        mock_pubmed.get_related.assert_called_once()

    # ===================================
    # AUTHOR TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_search_authors(
        self,
        service: LiteratureService,
        mock_s2: AsyncMock,
    ):
        """Test searching for authors."""
        authors = await service.search_authors(
            query="John Doe",
            limit=10,
        )

        assert len(authors) == 1
        assert authors[0].name == "John Doe"
        mock_s2.search_authors.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_author_papers(
        self,
        service: LiteratureService,
        mock_s2: AsyncMock,
    ):
        """Test getting papers by author."""
        papers = await service.get_author_papers(
            author_id="author-123",
            limit=50,
        )

        assert len(papers) == 1
        mock_s2.get_author_papers.assert_called_once()

    # ===================================
    # LITERATURE REVIEW TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_create_literature_review(self, service: LiteratureService):
        """Test creating a literature review."""
        # Mock papers with citations for categorization
        service._s2.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    paper=Paper(
                        paper_id="recent-paper",
                        title="Recent Paper",
                        year=_utcnow().year,
                        citation_count=50,
                    ),
                    score=0.9,
                ),
                SearchResult(
                    paper=Paper(
                        paper_id="seminal-paper",
                        title="Seminal Paper",
                        year=2010,
                        citation_count=5000,
                    ),
                    score=0.8,
                ),
            ],
            total_count=2,
            sources_queried=["semantic_scholar"],
        )

        review = await service.create_literature_review(
            topic="Transformer Models",
            query="transformer neural network",
            max_papers=50,
        )

        assert review is not None
        assert review.topic == "Transformer Models"
        assert len(review.papers) == 2
        assert "recent" in review.sections
        assert "seminal" in review.sections
        assert "highly_cited" in review.sections

    # ===================================
    # SOURCE DETECTION TESTS
    # ===================================

    def test_detect_source_doi(self, service: LiteratureService):
        """Test DOI detection."""
        assert service._detect_source("10.1234/test") == PaperSource.DOI
        assert service._detect_source("DOI:10.1234/test") == PaperSource.DOI

    def test_detect_source_arxiv(self, service: LiteratureService):
        """Test arXiv ID detection."""
        assert service._detect_source("2301.12345") == PaperSource.ARXIV
        assert service._detect_source("ARXIV:2301.12345") == PaperSource.ARXIV
        assert service._detect_source("cs.LG/0601001") == PaperSource.ARXIV

    def test_detect_source_pubmed(self, service: LiteratureService):
        """Test PubMed ID detection."""
        assert service._detect_source("12345678") == PaperSource.PUBMED
        assert service._detect_source("PMID:12345678") == PaperSource.PUBMED

    def test_detect_source_default(self, service: LiteratureService):
        """Test default to Semantic Scholar."""
        assert service._detect_source("abc123") == PaperSource.SEMANTIC_SCHOLAR

    # ===================================
    # CACHING TESTS
    # ===================================

    def test_cache_paper(self, service: LiteratureService):
        """Test paper caching by multiple identifiers."""
        paper = Paper(
            paper_id="paper-1",
            title="Test Paper",
            doi="10.1234/test",
            arxiv_id="2301.12345",
            pubmed_id="12345678",
            semantic_scholar_id="abc123",
        )

        service._cache_paper(paper)

        # Should be cached by all identifiers
        assert service._cache.get("10.1234/test") == paper
        assert service._cache.get("2301.12345") == paper
        assert service._cache.get("12345678") == paper
        assert service._cache.get("abc123") == paper
        assert service._cache.get("paper-1") == paper

    # ===================================
    # STATISTICS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_stats(
        self,
        service: LiteratureService,
        mock_s2: AsyncMock,
    ):
        """Test getting service statistics."""
        # Perform some operations
        await service.search(query="test")
        await service.get_paper("abc123", source=PaperSource.SEMANTIC_SCHOLAR)

        stats = service.get_stats()

        assert isinstance(stats, LiteratureStats)
        assert stats.total_searches >= 1
        assert stats.total_papers_fetched >= 1

    # ===================================
    # CLEANUP TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_close(
        self,
        service: LiteratureService,
        mock_arxiv: AsyncMock,
        mock_pubmed: AsyncMock,
        mock_s2: AsyncMock,
    ):
        """Test closing all clients."""
        await service.close()

        mock_arxiv.close.assert_called_once()
        mock_pubmed.close.assert_called_once()
        mock_s2.close.assert_called_once()

    # ===================================
    # DEDUPLICATION TESTS
    # ===================================

    def test_deduplicate_by_doi(self, service: LiteratureService):
        """Test deduplication by DOI."""
        results = [
            SearchResult(
                paper=Paper(paper_id="1", title="Paper A", doi="10.1234/test"),
                score=0.9,
            ),
            SearchResult(
                paper=Paper(paper_id="2", title="Paper A", doi="10.1234/test"),
                score=0.8,
            ),
        ]

        deduplicated = service._deduplicate_results(results)
        assert len(deduplicated) == 1

    def test_deduplicate_by_title(self, service: LiteratureService):
        """Test deduplication by title when no DOI."""
        results = [
            SearchResult(
                paper=Paper(paper_id="1", title="Exact Same Title"),
                score=0.9,
            ),
            SearchResult(
                paper=Paper(paper_id="2", title="exact same title"),  # Case insensitive
                score=0.8,
            ),
        ]

        deduplicated = service._deduplicate_results(results)
        assert len(deduplicated) == 1

    def test_deduplicate_keeps_unique(self, service: LiteratureService):
        """Test that unique papers are kept."""
        results = [
            SearchResult(
                paper=Paper(paper_id="1", title="Paper A", doi="10.1234/a"),
                score=0.9,
            ),
            SearchResult(
                paper=Paper(paper_id="2", title="Paper B", doi="10.1234/b"),
                score=0.8,
            ),
            SearchResult(
                paper=Paper(paper_id="3", title="Paper C"),  # No DOI
                score=0.7,
            ),
        ]

        deduplicated = service._deduplicate_results(results)
        assert len(deduplicated) == 3
