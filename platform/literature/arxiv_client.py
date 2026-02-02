"""arXiv API client for fetching papers and metadata."""

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import httpx

from platform.literature.base import (
    Author,
    Paper,
    PaperSource,
    PublicationType,
    SearchQuery,
    SearchResponse,
    SearchResult,
)
from platform.literature.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# arXiv API namespaces
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class ArxivClient:
    """
    Client for the arXiv API.

    Provides methods for searching papers, fetching by ID,
    and downloading PDFs from arXiv.
    """

    def __init__(self):
        """Initialize arXiv client."""
        self._base_url = settings.arxiv_base_url
        self._rate_limit = settings.arxiv_rate_limit
        self._max_results = settings.arxiv_max_results
        self._last_request_time: float = 0
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=settings.request_timeout)
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
        max_results: int = 20,
        start: int = 0,
        sort_by: str = "relevance",
        sort_order: str = "descending",
        categories: list[str] | None = None,
    ) -> SearchResponse:
        """
        Search arXiv papers.

        Args:
            query: Search query
            max_results: Maximum results
            start: Starting index
            sort_by: Sort field (relevance, lastUpdatedDate, submittedDate)
            sort_order: Sort order (ascending, descending)
            categories: Filter by arXiv categories

        Returns:
            Search response with papers
        """
        start_time = datetime.utcnow()

        # Build query string
        search_query = self._build_query(query, categories)

        params = {
            "search_query": search_query,
            "start": start,
            "max_results": min(max_results, self._max_results),
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }

        await self._rate_limit_wait()

        client = await self._get_client()

        try:
            response = await client.get(self._base_url, params=params)
            response.raise_for_status()

            papers = self._parse_response(response.text)

            query_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            results = [
                SearchResult(
                    paper=paper,
                    score=1.0 - (i * 0.01),  # Approximate relevance
                    source=PaperSource.ARXIV,
                )
                for i, paper in enumerate(papers)
            ]

            logger.info(
                "arxiv_search_completed",
                query=query[:50],
                results=len(results),
                query_time_ms=round(query_time_ms, 2),
            )

            return SearchResponse(
                results=results,
                total_count=len(results),  # arXiv doesn't return total count easily
                query_time_ms=query_time_ms,
                sources_queried=["arxiv"],
            )

        except httpx.HTTPError as e:
            logger.exception("arxiv_search_error", query=query, error=str(e))
            return SearchResponse(
                results=[],
                total_count=0,
                sources_queried=["arxiv"],
            )

    async def get_paper(self, arxiv_id: str) -> Paper | None:
        """
        Get a paper by arXiv ID.

        Args:
            arxiv_id: arXiv identifier (e.g., "2301.00001" or "cs/0001001")

        Returns:
            Paper or None if not found
        """
        # Clean up arXiv ID
        arxiv_id = self._normalize_arxiv_id(arxiv_id)

        params = {
            "id_list": arxiv_id,
            "max_results": 1,
        }

        await self._rate_limit_wait()

        client = await self._get_client()

        try:
            response = await client.get(self._base_url, params=params)
            response.raise_for_status()

            papers = self._parse_response(response.text)

            if papers:
                logger.info("arxiv_paper_fetched", arxiv_id=arxiv_id)
                return papers[0]

            return None

        except httpx.HTTPError as e:
            logger.exception("arxiv_get_paper_error", arxiv_id=arxiv_id, error=str(e))
            return None

    async def get_papers(self, arxiv_ids: list[str]) -> list[Paper]:
        """
        Get multiple papers by arXiv IDs.

        Args:
            arxiv_ids: List of arXiv identifiers

        Returns:
            List of papers
        """
        # Clean up IDs
        ids = [self._normalize_arxiv_id(aid) for aid in arxiv_ids]

        params = {
            "id_list": ",".join(ids),
            "max_results": len(ids),
        }

        await self._rate_limit_wait()

        client = await self._get_client()

        try:
            response = await client.get(self._base_url, params=params)
            response.raise_for_status()

            papers = self._parse_response(response.text)

            logger.info("arxiv_papers_fetched", count=len(papers))
            return papers

        except httpx.HTTPError as e:
            logger.exception("arxiv_get_papers_error", error=str(e))
            return []

    async def search_by_category(
        self,
        category: str,
        max_results: int = 20,
        days_back: int = 7,
    ) -> list[Paper]:
        """
        Search recent papers in a category.

        Args:
            category: arXiv category (e.g., "cs.AI")
            max_results: Maximum results
            days_back: Days to look back

        Returns:
            List of papers
        """
        query = f"cat:{category}"

        response = await self.search(
            query=query,
            max_results=max_results,
            sort_by="submittedDate",
            sort_order="descending",
        )

        return [r.paper for r in response.results]

    async def search_by_author(
        self,
        author_name: str,
        max_results: int = 20,
    ) -> list[Paper]:
        """
        Search papers by author.

        Args:
            author_name: Author name
            max_results: Maximum results

        Returns:
            List of papers
        """
        query = f'au:"{author_name}"'

        response = await self.search(
            query=query,
            max_results=max_results,
            sort_by="submittedDate",
            sort_order="descending",
        )

        return [r.paper for r in response.results]

    def get_pdf_url(self, arxiv_id: str) -> str:
        """Get PDF URL for an arXiv paper."""
        arxiv_id = self._normalize_arxiv_id(arxiv_id)
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    def get_abs_url(self, arxiv_id: str) -> str:
        """Get abstract page URL for an arXiv paper."""
        arxiv_id = self._normalize_arxiv_id(arxiv_id)
        return f"https://arxiv.org/abs/{arxiv_id}"

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_query(
        self,
        query: str,
        categories: list[str] | None = None,
    ) -> str:
        """Build arXiv API query string."""
        parts = []

        # Main query (search all fields)
        if query:
            # Check if query is already structured
            if any(prefix in query for prefix in ["ti:", "au:", "abs:", "cat:", "all:"]):
                parts.append(query)
            else:
                # Search in title, abstract, and all
                parts.append(f"all:{quote_plus(query)}")

        # Add category filter
        if categories:
            cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
            parts.append(f"({cat_query})")

        return " AND ".join(parts) if len(parts) > 1 else parts[0] if parts else ""

    def _normalize_arxiv_id(self, arxiv_id: str) -> str:
        """Normalize arXiv ID format."""
        # Remove "arXiv:" prefix if present
        arxiv_id = re.sub(r"^arxiv:", "", arxiv_id, flags=re.IGNORECASE)
        # Remove version suffix for base ID
        arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
        return arxiv_id.strip()

    def _parse_response(self, xml_content: str) -> list[Paper]:
        """Parse arXiv API XML response."""
        papers = []

        try:
            root = ET.fromstring(xml_content)

            for entry in root.findall("atom:entry", ARXIV_NS):
                paper = self._parse_entry(entry)
                if paper:
                    papers.append(paper)

        except ET.ParseError as e:
            logger.exception("arxiv_xml_parse_error", error=str(e))

        return papers

    def _parse_entry(self, entry: ET.Element) -> Paper | None:
        """Parse a single arXiv entry."""
        try:
            # Get arXiv ID
            id_elem = entry.find("atom:id", ARXIV_NS)
            if id_elem is None or id_elem.text is None:
                return None

            arxiv_url = id_elem.text
            arxiv_id = arxiv_url.split("/abs/")[-1]

            # Get title
            title_elem = entry.find("atom:title", ARXIV_NS)
            title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else ""

            # Get abstract
            summary_elem = entry.find("atom:summary", ARXIV_NS)
            abstract = summary_elem.text.strip().replace("\n", " ") if summary_elem is not None and summary_elem.text else ""

            # Get authors
            authors = []
            for author_elem in entry.findall("atom:author", ARXIV_NS):
                name_elem = author_elem.find("atom:name", ARXIV_NS)
                if name_elem is not None and name_elem.text:
                    author = Author(
                        name=name_elem.text.strip(),
                    )
                    # Try to split name
                    parts = author.name.rsplit(" ", 1)
                    if len(parts) == 2:
                        author.first_name = parts[0]
                        author.last_name = parts[1]
                    authors.append(author)

            # Get publication date
            published_elem = entry.find("atom:published", ARXIV_NS)
            pub_date = None
            year = None
            if published_elem is not None and published_elem.text:
                pub_date = datetime.fromisoformat(published_elem.text.replace("Z", "+00:00"))
                year = pub_date.year

            # Get categories
            categories = []
            primary_category = entry.find("arxiv:primary_category", ARXIV_NS)
            if primary_category is not None:
                cat = primary_category.get("term")
                if cat:
                    categories.append(cat)

            for cat_elem in entry.findall("atom:category", ARXIV_NS):
                cat = cat_elem.get("term")
                if cat and cat not in categories:
                    categories.append(cat)

            # Get DOI if available
            doi = ""
            doi_elem = entry.find("arxiv:doi", ARXIV_NS)
            if doi_elem is not None and doi_elem.text:
                doi = doi_elem.text.strip()

            # Get PDF link
            pdf_url = ""
            for link in entry.findall("atom:link", ARXIV_NS):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                    break

            # Create paper
            paper = Paper(
                title=title,
                abstract=abstract,
                authors=authors,
                publication_date=pub_date,
                year=year,
                publication_type=PublicationType.PREPRINT,
                source=PaperSource.ARXIV,
                arxiv_id=arxiv_id,
                doi=doi,
                url=arxiv_url,
                pdf_url=pdf_url or self.get_pdf_url(arxiv_id),
                categories=categories,
                is_open_access=True,
                has_pdf=True,
                external_ids={"arxiv": arxiv_id},
            )

            return paper

        except Exception as e:
            logger.exception("arxiv_entry_parse_error", error=str(e))
            return None


# Singleton instance
_arxiv_client: ArxivClient | None = None


def get_arxiv_client() -> ArxivClient:
    """Get singleton ArxivClient instance."""
    global _arxiv_client
    if _arxiv_client is None:
        _arxiv_client = ArxivClient()
    return _arxiv_client
