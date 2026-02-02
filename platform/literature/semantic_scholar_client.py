"""Semantic Scholar API client for paper search and citation graphs."""

import asyncio
from datetime import datetime
from typing import Any

import httpx

from platform.literature.base import (
    Author,
    Citation,
    CitationIntent,
    Paper,
    PaperSource,
    PublicationType,
    Recommendation,
    SearchResponse,
    SearchResult,
)
from platform.literature.config import S2_AUTHOR_FIELDS, S2_PAPER_FIELDS, get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class SemanticScholarClient:
    """
    Client for the Semantic Scholar API.

    Provides methods for paper search, citation graphs,
    author information, and recommendations.
    """

    def __init__(self):
        """Initialize Semantic Scholar client."""
        self._base_url = settings.semantic_scholar_base_url
        self._api_key = settings.semantic_scholar_api_key
        self._rate_limit = settings.semantic_scholar_rate_limit
        self._last_request_time: float = 0
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {}
            if self._api_key:
                headers["x-api-key"] = self._api_key
            self._client = httpx.AsyncClient(
                timeout=settings.request_timeout,
                headers=headers,
            )
        return self._client

    async def _rate_limit_wait(self) -> None:
        """Wait to respect rate limits."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit:
            await asyncio.sleep(self._rate_limit - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        year: str | None = None,
        fields_of_study: list[str] | None = None,
        open_access_only: bool = False,
        min_citation_count: int | None = None,
    ) -> SearchResponse:
        """
        Search papers on Semantic Scholar.

        Args:
            query: Search query
            limit: Maximum results
            offset: Starting offset
            year: Year filter (e.g., "2020", "2020-2023", "2020-")
            fields_of_study: Filter by fields
            open_access_only: Only open access papers
            min_citation_count: Minimum citations

        Returns:
            Search response with papers
        """
        start_time = datetime.utcnow()

        await self._rate_limit_wait()

        client = await self._get_client()

        params = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "fields": ",".join(S2_PAPER_FIELDS),
        }

        if year:
            params["year"] = year
        if fields_of_study:
            params["fieldsOfStudy"] = ",".join(fields_of_study)
        if open_access_only:
            params["openAccessPdf"] = ""
        if min_citation_count:
            params["minCitationCount"] = str(min_citation_count)

        try:
            response = await client.get(
                f"{self._base_url}/paper/search",
                params=params,
            )
            response.raise_for_status()

            data = response.json()
            papers = [self._parse_paper(p) for p in data.get("data", [])]
            papers = [p for p in papers if p is not None]

            query_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            results = [
                SearchResult(
                    paper=paper,
                    score=1.0 - (i * 0.01),
                    source=PaperSource.SEMANTIC_SCHOLAR,
                )
                for i, paper in enumerate(papers)
            ]

            logger.info(
                "s2_search_completed",
                query=query[:50],
                results=len(results),
                total=data.get("total", 0),
            )

            return SearchResponse(
                results=results,
                total_count=data.get("total", len(results)),
                query_time_ms=query_time_ms,
                sources_queried=["semantic_scholar"],
            )

        except httpx.HTTPError as e:
            logger.exception("s2_search_error", query=query, error=str(e))
            return SearchResponse(
                results=[],
                total_count=0,
                sources_queried=["semantic_scholar"],
            )

    async def get_paper(self, paper_id: str) -> Paper | None:
        """
        Get a paper by Semantic Scholar ID or external ID.

        Args:
            paper_id: S2 paper ID, or prefixed ID (DOI:xxx, ARXIV:xxx, PMID:xxx)

        Returns:
            Paper or None if not found
        """
        await self._rate_limit_wait()

        client = await self._get_client()

        try:
            response = await client.get(
                f"{self._base_url}/paper/{paper_id}",
                params={"fields": ",".join(S2_PAPER_FIELDS)},
            )
            response.raise_for_status()

            data = response.json()
            paper = self._parse_paper(data)

            if paper:
                logger.info("s2_paper_fetched", paper_id=paper_id)

            return paper

        except httpx.HTTPError as e:
            logger.exception("s2_get_paper_error", paper_id=paper_id, error=str(e))
            return None

    async def get_paper_by_doi(self, doi: str) -> Paper | None:
        """Get paper by DOI."""
        return await self.get_paper(f"DOI:{doi}")

    async def get_paper_by_arxiv(self, arxiv_id: str) -> Paper | None:
        """Get paper by arXiv ID."""
        return await self.get_paper(f"ARXIV:{arxiv_id}")

    async def get_paper_by_pmid(self, pmid: str) -> Paper | None:
        """Get paper by PubMed ID."""
        return await self.get_paper(f"PMID:{pmid}")

    async def get_citations(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Citation]:
        """
        Get papers that cite this paper.

        Args:
            paper_id: Paper ID
            limit: Maximum results
            offset: Starting offset

        Returns:
            List of citations
        """
        await self._rate_limit_wait()

        client = await self._get_client()

        try:
            response = await client.get(
                f"{self._base_url}/paper/{paper_id}/citations",
                params={
                    "fields": "paperId,title,year,citationCount,contexts,intents,isInfluential",
                    "limit": limit,
                    "offset": offset,
                },
            )
            response.raise_for_status()

            data = response.json()
            citations = []

            for item in data.get("data", []):
                citing_paper_data = item.get("citingPaper", {})
                citing_paper = self._parse_paper(citing_paper_data)

                if citing_paper:
                    citation = Citation(
                        citing_paper_id=citing_paper.semantic_scholar_id,
                        cited_paper_id=paper_id,
                        citing_paper=citing_paper,
                        context="; ".join(item.get("contexts", [])),
                        is_influential=item.get("isInfluential", False),
                    )

                    # Parse intents
                    intents = item.get("intents", [])
                    if intents:
                        intent_map = {
                            "background": CitationIntent.BACKGROUND,
                            "methodology": CitationIntent.METHOD,
                            "result": CitationIntent.RESULT,
                        }
                        citation.intent = intent_map.get(
                            intents[0].lower(), CitationIntent.UNKNOWN
                        )

                    citations.append(citation)

            logger.info("s2_citations_fetched", paper_id=paper_id, count=len(citations))
            return citations

        except httpx.HTTPError as e:
            logger.exception("s2_get_citations_error", paper_id=paper_id, error=str(e))
            return []

    async def get_references(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Citation]:
        """
        Get papers referenced by this paper.

        Args:
            paper_id: Paper ID
            limit: Maximum results
            offset: Starting offset

        Returns:
            List of references as citations
        """
        await self._rate_limit_wait()

        client = await self._get_client()

        try:
            response = await client.get(
                f"{self._base_url}/paper/{paper_id}/references",
                params={
                    "fields": "paperId,title,year,citationCount,contexts,intents,isInfluential",
                    "limit": limit,
                    "offset": offset,
                },
            )
            response.raise_for_status()

            data = response.json()
            references = []

            for item in data.get("data", []):
                cited_paper_data = item.get("citedPaper", {})
                cited_paper = self._parse_paper(cited_paper_data)

                if cited_paper:
                    citation = Citation(
                        citing_paper_id=paper_id,
                        cited_paper_id=cited_paper.semantic_scholar_id,
                        cited_paper=cited_paper,
                        context="; ".join(item.get("contexts", [])),
                        is_influential=item.get("isInfluential", False),
                    )
                    references.append(citation)

            logger.info("s2_references_fetched", paper_id=paper_id, count=len(references))
            return references

        except httpx.HTTPError as e:
            logger.exception("s2_get_references_error", paper_id=paper_id, error=str(e))
            return []

    async def get_recommendations(
        self,
        paper_ids: list[str],
        limit: int = 20,
    ) -> list[Recommendation]:
        """
        Get paper recommendations based on input papers.

        Args:
            paper_ids: List of paper IDs to base recommendations on
            limit: Maximum recommendations

        Returns:
            List of recommended papers
        """
        await self._rate_limit_wait()

        client = await self._get_client()

        try:
            response = await client.post(
                f"{self._base_url}/recommendations",
                json={
                    "positivePaperIds": paper_ids,
                    "negativePaperIds": [],
                },
                params={
                    "fields": ",".join(S2_PAPER_FIELDS),
                    "limit": limit,
                },
            )
            response.raise_for_status()

            data = response.json()
            recommendations = []

            for item in data.get("recommendedPapers", []):
                paper = self._parse_paper(item)
                if paper:
                    rec = Recommendation(
                        paper=paper,
                        score=item.get("score", 0.0),
                        reason="Based on similar papers",
                        based_on=paper_ids,
                    )
                    recommendations.append(rec)

            logger.info("s2_recommendations_fetched", count=len(recommendations))
            return recommendations

        except httpx.HTTPError as e:
            logger.exception("s2_recommendations_error", error=str(e))
            return []

    async def get_author(self, author_id: str) -> Author | None:
        """
        Get author information.

        Args:
            author_id: Semantic Scholar author ID

        Returns:
            Author or None
        """
        await self._rate_limit_wait()

        client = await self._get_client()

        try:
            response = await client.get(
                f"{self._base_url}/author/{author_id}",
                params={"fields": ",".join(S2_AUTHOR_FIELDS)},
            )
            response.raise_for_status()

            data = response.json()
            return self._parse_author(data)

        except httpx.HTTPError as e:
            logger.exception("s2_get_author_error", author_id=author_id, error=str(e))
            return None

    async def get_author_papers(
        self,
        author_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """
        Get papers by an author.

        Args:
            author_id: Semantic Scholar author ID
            limit: Maximum results
            offset: Starting offset

        Returns:
            List of papers
        """
        await self._rate_limit_wait()

        client = await self._get_client()

        try:
            response = await client.get(
                f"{self._base_url}/author/{author_id}/papers",
                params={
                    "fields": ",".join(S2_PAPER_FIELDS),
                    "limit": limit,
                    "offset": offset,
                },
            )
            response.raise_for_status()

            data = response.json()
            papers = [self._parse_paper(p) for p in data.get("data", [])]
            return [p for p in papers if p is not None]

        except httpx.HTTPError as e:
            logger.exception("s2_author_papers_error", author_id=author_id, error=str(e))
            return []

    async def search_authors(
        self,
        query: str,
        limit: int = 10,
    ) -> list[Author]:
        """
        Search for authors.

        Args:
            query: Author name query
            limit: Maximum results

        Returns:
            List of authors
        """
        await self._rate_limit_wait()

        client = await self._get_client()

        try:
            response = await client.get(
                f"{self._base_url}/author/search",
                params={
                    "query": query,
                    "fields": ",".join(S2_AUTHOR_FIELDS),
                    "limit": limit,
                },
            )
            response.raise_for_status()

            data = response.json()
            authors = [self._parse_author(a) for a in data.get("data", [])]
            return [a for a in authors if a is not None]

        except httpx.HTTPError as e:
            logger.exception("s2_search_authors_error", query=query, error=str(e))
            return []

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _parse_paper(self, data: dict[str, Any]) -> Paper | None:
        """Parse paper data from API response."""
        if not data or not data.get("paperId"):
            return None

        try:
            # Parse authors
            authors = []
            for author_data in data.get("authors", []):
                author = self._parse_author(author_data)
                if author:
                    authors.append(author)

            # Parse publication date
            pub_date = None
            year = data.get("year")
            pub_date_str = data.get("publicationDate")
            if pub_date_str:
                try:
                    pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d")
                except ValueError:
                    pass

            # Parse external IDs
            external_ids = data.get("externalIds", {}) or {}
            doi = external_ids.get("DOI", "")
            arxiv_id = external_ids.get("ArXiv", "")
            pubmed_id = str(external_ids.get("PubMed", "")) if external_ids.get("PubMed") else ""

            # Parse PDF URL
            pdf_url = ""
            open_access = data.get("openAccessPdf", {})
            if open_access:
                pdf_url = open_access.get("url", "")

            # Parse publication type
            pub_type = PublicationType.OTHER
            pub_types = data.get("publicationTypes", [])
            if pub_types:
                type_map = {
                    "JournalArticle": PublicationType.JOURNAL_ARTICLE,
                    "Conference": PublicationType.CONFERENCE_PAPER,
                    "Review": PublicationType.REVIEW,
                    "Book": PublicationType.BOOK_CHAPTER,
                    "Dataset": PublicationType.DATASET,
                }
                pub_type = type_map.get(pub_types[0], PublicationType.OTHER)

            # Parse journal
            venue = data.get("venue", "")
            journal_data = data.get("journal", {}) or {}
            if journal_data:
                venue = journal_data.get("name", venue)

            paper = Paper(
                title=data.get("title", ""),
                abstract=data.get("abstract", ""),
                authors=authors,
                publication_date=pub_date,
                year=year,
                venue=venue,
                volume=journal_data.get("volume", "") if journal_data else "",
                pages=journal_data.get("pages", "") if journal_data else "",
                publication_type=pub_type,
                source=PaperSource.SEMANTIC_SCHOLAR,
                doi=doi,
                arxiv_id=arxiv_id,
                pubmed_id=pubmed_id,
                semantic_scholar_id=data.get("paperId", ""),
                url=data.get("url", ""),
                pdf_url=pdf_url,
                fields_of_study=data.get("fieldsOfStudy", []) or [],
                citation_count=data.get("citationCount", 0) or 0,
                reference_count=data.get("referenceCount", 0) or 0,
                influential_citation_count=data.get("influentialCitationCount", 0) or 0,
                is_open_access=data.get("isOpenAccess", False),
                has_pdf=bool(pdf_url),
                external_ids=external_ids,
            )

            return paper

        except Exception as e:
            logger.exception("s2_parse_paper_error", error=str(e))
            return None

    def _parse_author(self, data: dict[str, Any]) -> Author | None:
        """Parse author data from API response."""
        if not data:
            return None

        try:
            external_ids = data.get("externalIds", {}) or {}

            author = Author(
                author_id=data.get("authorId", ""),
                name=data.get("name", ""),
                affiliations=data.get("affiliations", []) or [],
                h_index=data.get("hIndex"),
                citation_count=data.get("citationCount"),
                paper_count=data.get("paperCount"),
                external_ids=external_ids,
            )

            # Try to split name
            if author.name and " " in author.name:
                parts = author.name.rsplit(" ", 1)
                author.first_name = parts[0]
                author.last_name = parts[1]

            return author

        except Exception as e:
            logger.exception("s2_parse_author_error", error=str(e))
            return None


# Singleton instance
_s2_client: SemanticScholarClient | None = None


def get_semantic_scholar_client() -> SemanticScholarClient:
    """Get singleton SemanticScholarClient instance."""
    global _s2_client
    if _s2_client is None:
        _s2_client = SemanticScholarClient()
    return _s2_client
