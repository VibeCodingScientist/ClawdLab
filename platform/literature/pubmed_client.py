"""PubMed/NCBI API client for biomedical literature."""

import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import httpx

from platform.literature.base import (
    Author,
    Paper,
    PaperSource,
    PublicationType,
    SearchResponse,
    SearchResult,
)
from platform.literature.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class PubMedClient:
    """
    Client for PubMed/NCBI E-utilities API.

    Provides methods for searching biomedical literature,
    fetching abstracts, and retrieving citation data.
    """

    def __init__(self):
        """Initialize PubMed client."""
        self._base_url = settings.pubmed_base_url
        self._api_key = settings.pubmed_api_key
        self._rate_limit = settings.pubmed_rate_limit
        self._max_results = settings.pubmed_max_results
        self._last_request_time: float = 0
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=settings.request_timeout)
        return self._client

    async def _rate_limit_wait(self) -> None:
        """Wait to respect rate limits."""
        # With API key, can do 10 requests/sec; without, 3 requests/sec
        rate_limit = 0.1 if self._api_key else self._rate_limit

        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < rate_limit:
            await asyncio.sleep(rate_limit - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    def _get_params(self) -> dict[str, str]:
        """Get base parameters including API key."""
        params = {}
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    async def search(
        self,
        query: str,
        max_results: int = 20,
        start: int = 0,
        sort: str = "relevance",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> SearchResponse:
        """
        Search PubMed.

        Args:
            query: Search query
            max_results: Maximum results
            start: Starting index
            sort: Sort order (relevance, pub_date)
            date_from: Start date (YYYY/MM/DD)
            date_to: End date (YYYY/MM/DD)

        Returns:
            Search response with papers
        """
        start_time = datetime.utcnow()

        # First, search to get PMIDs
        pmids = await self._esearch(
            query=query,
            max_results=max_results,
            start=start,
            sort=sort,
            date_from=date_from,
            date_to=date_to,
        )

        if not pmids:
            return SearchResponse(
                results=[],
                total_count=0,
                sources_queried=["pubmed"],
            )

        # Then fetch paper details
        papers = await self._efetch(pmids)

        query_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        results = [
            SearchResult(
                paper=paper,
                score=1.0 - (i * 0.01),
                source=PaperSource.PUBMED,
            )
            for i, paper in enumerate(papers)
        ]

        logger.info(
            "pubmed_search_completed",
            query=query[:50],
            results=len(results),
            query_time_ms=round(query_time_ms, 2),
        )

        return SearchResponse(
            results=results,
            total_count=len(results),
            query_time_ms=query_time_ms,
            sources_queried=["pubmed"],
        )

    async def get_paper(self, pmid: str) -> Paper | None:
        """
        Get a paper by PubMed ID.

        Args:
            pmid: PubMed identifier

        Returns:
            Paper or None if not found
        """
        papers = await self._efetch([pmid])

        if papers:
            logger.info("pubmed_paper_fetched", pmid=pmid)
            return papers[0]

        return None

    async def get_papers(self, pmids: list[str]) -> list[Paper]:
        """
        Get multiple papers by PubMed IDs.

        Args:
            pmids: List of PubMed identifiers

        Returns:
            List of papers
        """
        papers = await self._efetch(pmids)
        logger.info("pubmed_papers_fetched", count=len(papers))
        return papers

    async def search_mesh(
        self,
        mesh_terms: list[str],
        max_results: int = 20,
    ) -> list[Paper]:
        """
        Search by MeSH terms.

        Args:
            mesh_terms: MeSH terms to search
            max_results: Maximum results

        Returns:
            List of papers
        """
        query = " AND ".join(f'"{term}"[MeSH Terms]' for term in mesh_terms)
        response = await self.search(query=query, max_results=max_results)
        return [r.paper for r in response.results]

    async def get_citations(self, pmid: str) -> list[str]:
        """
        Get PMIDs of papers that cite this paper.

        Args:
            pmid: PubMed ID

        Returns:
            List of citing PMIDs
        """
        await self._rate_limit_wait()

        client = await self._get_client()
        params = {
            **self._get_params(),
            "dbfrom": "pubmed",
            "db": "pubmed",
            "id": pmid,
            "linkname": "pubmed_pubmed_citedin",
            "retmode": "json",
        }

        try:
            response = await client.get(f"{self._base_url}/elink.fcgi", params=params)
            response.raise_for_status()

            data = response.json()
            citations = []

            linksets = data.get("linksets", [])
            if linksets:
                for linkset in linksets:
                    for linksetdb in linkset.get("linksetdbs", []):
                        if linksetdb.get("linkname") == "pubmed_pubmed_citedin":
                            for link in linksetdb.get("links", []):
                                citations.append(str(link))

            return citations

        except httpx.HTTPError as e:
            logger.exception("pubmed_citations_error", pmid=pmid, error=str(e))
            return []

    async def get_references(self, pmid: str) -> list[str]:
        """
        Get PMIDs of papers referenced by this paper.

        Args:
            pmid: PubMed ID

        Returns:
            List of referenced PMIDs
        """
        await self._rate_limit_wait()

        client = await self._get_client()
        params = {
            **self._get_params(),
            "dbfrom": "pubmed",
            "db": "pubmed",
            "id": pmid,
            "linkname": "pubmed_pubmed_refs",
            "retmode": "json",
        }

        try:
            response = await client.get(f"{self._base_url}/elink.fcgi", params=params)
            response.raise_for_status()

            data = response.json()
            references = []

            linksets = data.get("linksets", [])
            if linksets:
                for linkset in linksets:
                    for linksetdb in linkset.get("linksetdbs", []):
                        if linksetdb.get("linkname") == "pubmed_pubmed_refs":
                            for link in linksetdb.get("links", []):
                                references.append(str(link))

            return references

        except httpx.HTTPError as e:
            logger.exception("pubmed_references_error", pmid=pmid, error=str(e))
            return []

    async def get_related(self, pmid: str, max_results: int = 10) -> list[str]:
        """
        Get related papers.

        Args:
            pmid: PubMed ID
            max_results: Maximum results

        Returns:
            List of related PMIDs
        """
        await self._rate_limit_wait()

        client = await self._get_client()
        params = {
            **self._get_params(),
            "dbfrom": "pubmed",
            "db": "pubmed",
            "id": pmid,
            "linkname": "pubmed_pubmed",
            "retmode": "json",
        }

        try:
            response = await client.get(f"{self._base_url}/elink.fcgi", params=params)
            response.raise_for_status()

            data = response.json()
            related = []

            linksets = data.get("linksets", [])
            if linksets:
                for linkset in linksets:
                    for linksetdb in linkset.get("linksetdbs", []):
                        if linksetdb.get("linkname") == "pubmed_pubmed":
                            for link in linksetdb.get("links", [])[:max_results]:
                                related.append(str(link))

            return related

        except httpx.HTTPError as e:
            logger.exception("pubmed_related_error", pmid=pmid, error=str(e))
            return []

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _esearch(
        self,
        query: str,
        max_results: int,
        start: int = 0,
        sort: str = "relevance",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[str]:
        """Execute ESearch to get PMIDs."""
        await self._rate_limit_wait()

        client = await self._get_client()

        params = {
            **self._get_params(),
            "db": "pubmed",
            "term": query,
            "retstart": start,
            "retmax": min(max_results, self._max_results),
            "retmode": "json",
            "sort": sort,
        }

        if date_from:
            params["mindate"] = date_from
        if date_to:
            params["maxdate"] = date_to
        if date_from or date_to:
            params["datetype"] = "pdat"

        try:
            response = await client.get(f"{self._base_url}/esearch.fcgi", params=params)
            response.raise_for_status()

            data = response.json()
            return data.get("esearchresult", {}).get("idlist", [])

        except httpx.HTTPError as e:
            logger.exception("pubmed_esearch_error", query=query, error=str(e))
            return []

    async def _efetch(self, pmids: list[str]) -> list[Paper]:
        """Execute EFetch to get paper details."""
        if not pmids:
            return []

        await self._rate_limit_wait()

        client = await self._get_client()

        params = {
            **self._get_params(),
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "xml",
            "retmode": "xml",
        }

        try:
            response = await client.get(f"{self._base_url}/efetch.fcgi", params=params)
            response.raise_for_status()

            return self._parse_efetch_xml(response.text)

        except httpx.HTTPError as e:
            logger.exception("pubmed_efetch_error", error=str(e))
            return []

    def _parse_efetch_xml(self, xml_content: str) -> list[Paper]:
        """Parse EFetch XML response."""
        papers = []

        try:
            root = ET.fromstring(xml_content)

            for article in root.findall(".//PubmedArticle"):
                paper = self._parse_article(article)
                if paper:
                    papers.append(paper)

        except ET.ParseError as e:
            logger.exception("pubmed_xml_parse_error", error=str(e))

        return papers

    def _parse_article(self, article: ET.Element) -> Paper | None:
        """Parse a single PubMed article."""
        try:
            medline = article.find("MedlineCitation")
            if medline is None:
                return None

            # Get PMID
            pmid_elem = medline.find("PMID")
            pmid = pmid_elem.text if pmid_elem is not None and pmid_elem.text else ""

            article_elem = medline.find("Article")
            if article_elem is None:
                return None

            # Get title
            title_elem = article_elem.find("ArticleTitle")
            title = self._get_text(title_elem)

            # Get abstract
            abstract = ""
            abstract_elem = article_elem.find("Abstract")
            if abstract_elem is not None:
                abstract_parts = []
                for text_elem in abstract_elem.findall("AbstractText"):
                    label = text_elem.get("Label", "")
                    text = self._get_text(text_elem)
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)
                abstract = " ".join(abstract_parts)

            # Get authors
            authors = []
            author_list = article_elem.find("AuthorList")
            if author_list is not None:
                for author_elem in author_list.findall("Author"):
                    last_name = self._get_text(author_elem.find("LastName"))
                    first_name = self._get_text(author_elem.find("ForeName"))
                    initials = self._get_text(author_elem.find("Initials"))

                    if last_name:
                        name = f"{first_name} {last_name}".strip()
                        author = Author(
                            name=name,
                            first_name=first_name,
                            last_name=last_name,
                        )

                        # Get affiliations
                        for aff in author_elem.findall("AffiliationInfo/Affiliation"):
                            if aff.text:
                                author.affiliations.append(aff.text)

                        authors.append(author)

            # Get publication date
            pub_date = None
            year = None
            journal = article_elem.find("Journal")
            if journal is not None:
                pub_date_elem = journal.find("JournalIssue/PubDate")
                if pub_date_elem is not None:
                    year_elem = pub_date_elem.find("Year")
                    month_elem = pub_date_elem.find("Month")
                    day_elem = pub_date_elem.find("Day")

                    year_str = self._get_text(year_elem)
                    if year_str:
                        year = int(year_str)
                        month = self._parse_month(self._get_text(month_elem)) or 1
                        day = int(self._get_text(day_elem) or "1")
                        try:
                            pub_date = datetime(year, month, day)
                        except ValueError:
                            pub_date = datetime(year, 1, 1)

            # Get journal info
            venue = ""
            volume = ""
            issue = ""
            pages = ""
            if journal is not None:
                venue = self._get_text(journal.find("Title"))
                journal_issue = journal.find("JournalIssue")
                if journal_issue is not None:
                    volume = self._get_text(journal_issue.find("Volume"))
                    issue = self._get_text(journal_issue.find("Issue"))

            pagination = article_elem.find("Pagination/MedlinePgn")
            if pagination is not None and pagination.text:
                pages = pagination.text

            # Get DOI
            doi = ""
            article_ids = article.find("PubmedData/ArticleIdList")
            if article_ids is not None:
                for id_elem in article_ids.findall("ArticleId"):
                    if id_elem.get("IdType") == "doi" and id_elem.text:
                        doi = id_elem.text
                        break

            # Get PMC ID
            pmc_id = ""
            if article_ids is not None:
                for id_elem in article_ids.findall("ArticleId"):
                    if id_elem.get("IdType") == "pmc" and id_elem.text:
                        pmc_id = id_elem.text
                        break

            # Get keywords/MeSH
            keywords = []
            mesh_list = medline.find("MeshHeadingList")
            if mesh_list is not None:
                for mesh in mesh_list.findall("MeshHeading/DescriptorName"):
                    if mesh.text:
                        keywords.append(mesh.text)

            keyword_list = medline.find("KeywordList")
            if keyword_list is not None:
                for kw in keyword_list.findall("Keyword"):
                    if kw.text and kw.text not in keywords:
                        keywords.append(kw.text)

            # Determine publication type
            pub_type = PublicationType.JOURNAL_ARTICLE
            pub_type_list = article_elem.find("PublicationTypeList")
            if pub_type_list is not None:
                for pt in pub_type_list.findall("PublicationType"):
                    if pt.text:
                        pt_lower = pt.text.lower()
                        if "review" in pt_lower:
                            pub_type = PublicationType.REVIEW
                            break

            # Build URL
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            paper = Paper(
                title=title,
                abstract=abstract,
                authors=authors,
                publication_date=pub_date,
                year=year,
                venue=venue,
                volume=volume,
                issue=issue,
                pages=pages,
                publication_type=pub_type,
                source=PaperSource.PUBMED,
                doi=doi,
                pubmed_id=pmid,
                pmc_id=pmc_id,
                url=url,
                keywords=keywords,
                is_open_access=bool(pmc_id),
                has_pdf=bool(pmc_id),
                external_ids={"pmid": pmid, "pmc": pmc_id} if pmc_id else {"pmid": pmid},
            )

            if pmc_id:
                paper.pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/"

            return paper

        except Exception as e:
            logger.exception("pubmed_article_parse_error", error=str(e))
            return None

    def _get_text(self, element: ET.Element | None) -> str:
        """Safely get text from XML element."""
        if element is None:
            return ""
        # Handle mixed content
        text_parts = [element.text or ""]
        for child in element:
            text_parts.append(child.text or "")
            text_parts.append(child.tail or "")
        return "".join(text_parts).strip()

    def _parse_month(self, month_str: str) -> int | None:
        """Parse month string to integer."""
        if not month_str:
            return None

        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "may": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }

        try:
            return int(month_str)
        except ValueError:
            return month_map.get(month_str.lower()[:3])


# Singleton instance
_pubmed_client: PubMedClient | None = None


def get_pubmed_client() -> PubMedClient:
    """Get singleton PubMedClient instance."""
    global _pubmed_client
    if _pubmed_client is None:
        _pubmed_client = PubMedClient()
    return _pubmed_client
