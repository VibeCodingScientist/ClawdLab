"""Base classes and data structures for Literature Integration."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class PaperSource(Enum):
    """Source of paper metadata."""

    ARXIV = "arxiv"
    PUBMED = "pubmed"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CROSSREF = "crossref"
    DOI = "doi"
    MANUAL = "manual"


class PublicationType(Enum):
    """Types of publications."""

    JOURNAL_ARTICLE = "journal_article"
    CONFERENCE_PAPER = "conference_paper"
    PREPRINT = "preprint"
    REVIEW = "review"
    BOOK_CHAPTER = "book_chapter"
    THESIS = "thesis"
    DATASET = "dataset"
    SOFTWARE = "software"
    OTHER = "other"


class CitationIntent(Enum):
    """Intent/context of a citation."""

    BACKGROUND = "background"
    METHOD = "method"
    RESULT = "result"
    COMPARISON = "comparison"
    EXTENSION = "extension"
    UNKNOWN = "unknown"


# ===========================================
# AUTHOR DATA CLASSES
# ===========================================


@dataclass
class Author:
    """An author of a publication."""

    author_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    affiliations: list[str] = field(default_factory=list)
    email: str = ""
    orcid: str = ""
    h_index: int | None = None
    citation_count: int | None = None
    paper_count: int | None = None
    external_ids: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "author_id": self.author_id,
            "name": self.name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "affiliations": self.affiliations,
            "email": self.email,
            "orcid": self.orcid,
            "h_index": self.h_index,
            "citation_count": self.citation_count,
            "paper_count": self.paper_count,
            "external_ids": self.external_ids,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Author":
        return cls(
            author_id=data.get("author_id", str(uuid4())),
            name=data.get("name", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            affiliations=data.get("affiliations", []),
            email=data.get("email", ""),
            orcid=data.get("orcid", ""),
            h_index=data.get("h_index"),
            citation_count=data.get("citation_count"),
            paper_count=data.get("paper_count"),
            external_ids=data.get("external_ids", {}),
        )


# ===========================================
# PAPER DATA CLASSES
# ===========================================


@dataclass
class Paper:
    """A scientific paper/publication."""

    paper_id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    abstract: str = ""
    authors: list[Author] = field(default_factory=list)
    publication_date: datetime | None = None
    year: int | None = None
    venue: str = ""  # Journal or conference name
    volume: str = ""
    issue: str = ""
    pages: str = ""
    publication_type: PublicationType = PublicationType.OTHER
    source: PaperSource = PaperSource.MANUAL

    # Identifiers
    doi: str = ""
    arxiv_id: str = ""
    pubmed_id: str = ""
    pmc_id: str = ""
    semantic_scholar_id: str = ""
    external_ids: dict[str, str] = field(default_factory=dict)

    # URLs
    url: str = ""
    pdf_url: str = ""

    # Content
    keywords: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    fields_of_study: list[str] = field(default_factory=list)

    # Metrics
    citation_count: int = 0
    reference_count: int = 0
    influential_citation_count: int = 0

    # Flags
    is_open_access: bool = False
    has_pdf: bool = False

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    retrieved_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": [a.to_dict() for a in self.authors],
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "year": self.year,
            "venue": self.venue,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "publication_type": self.publication_type.value,
            "source": self.source.value,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "pubmed_id": self.pubmed_id,
            "pmc_id": self.pmc_id,
            "semantic_scholar_id": self.semantic_scholar_id,
            "external_ids": self.external_ids,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "keywords": self.keywords,
            "categories": self.categories,
            "fields_of_study": self.fields_of_study,
            "citation_count": self.citation_count,
            "reference_count": self.reference_count,
            "influential_citation_count": self.influential_citation_count,
            "is_open_access": self.is_open_access,
            "has_pdf": self.has_pdf,
            "metadata": self.metadata,
            "retrieved_at": self.retrieved_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Paper":
        authors = [Author.from_dict(a) for a in data.get("authors", [])]
        pub_date = None
        if data.get("publication_date"):
            pub_date = datetime.fromisoformat(data["publication_date"])

        return cls(
            paper_id=data.get("paper_id", str(uuid4())),
            title=data.get("title", ""),
            abstract=data.get("abstract", ""),
            authors=authors,
            publication_date=pub_date,
            year=data.get("year"),
            venue=data.get("venue", ""),
            volume=data.get("volume", ""),
            issue=data.get("issue", ""),
            pages=data.get("pages", ""),
            publication_type=PublicationType(data.get("publication_type", "other")),
            source=PaperSource(data.get("source", "manual")),
            doi=data.get("doi", ""),
            arxiv_id=data.get("arxiv_id", ""),
            pubmed_id=data.get("pubmed_id", ""),
            pmc_id=data.get("pmc_id", ""),
            semantic_scholar_id=data.get("semantic_scholar_id", ""),
            external_ids=data.get("external_ids", {}),
            url=data.get("url", ""),
            pdf_url=data.get("pdf_url", ""),
            keywords=data.get("keywords", []),
            categories=data.get("categories", []),
            fields_of_study=data.get("fields_of_study", []),
            citation_count=data.get("citation_count", 0),
            reference_count=data.get("reference_count", 0),
            influential_citation_count=data.get("influential_citation_count", 0),
            is_open_access=data.get("is_open_access", False),
            has_pdf=data.get("has_pdf", False),
            metadata=data.get("metadata", {}),
        )

    def get_canonical_id(self) -> str:
        """Get the best available identifier."""
        if self.doi:
            return f"doi:{self.doi}"
        if self.arxiv_id:
            return f"arxiv:{self.arxiv_id}"
        if self.pubmed_id:
            return f"pmid:{self.pubmed_id}"
        if self.semantic_scholar_id:
            return f"s2:{self.semantic_scholar_id}"
        return self.paper_id


# ===========================================
# CITATION DATA CLASSES
# ===========================================


@dataclass
class Citation:
    """A citation relationship between papers."""

    citation_id: str = field(default_factory=lambda: str(uuid4()))
    citing_paper_id: str = ""
    cited_paper_id: str = ""
    citing_paper: Paper | None = None
    cited_paper: Paper | None = None
    context: str = ""  # Text around the citation
    intent: CitationIntent = CitationIntent.UNKNOWN
    is_influential: bool = False
    section: str = ""  # Section where citation appears
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "citing_paper_id": self.citing_paper_id,
            "cited_paper_id": self.cited_paper_id,
            "citing_paper": self.citing_paper.to_dict() if self.citing_paper else None,
            "cited_paper": self.cited_paper.to_dict() if self.cited_paper else None,
            "context": self.context,
            "intent": self.intent.value,
            "is_influential": self.is_influential,
            "section": self.section,
            "metadata": self.metadata,
        }


# ===========================================
# SEARCH DATA CLASSES
# ===========================================


@dataclass
class SearchQuery:
    """A literature search query."""

    query: str = ""
    title: str = ""
    author: str = ""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    venues: list[str] = field(default_factory=list)
    publication_types: list[PublicationType] = field(default_factory=list)
    open_access_only: bool = False
    min_citations: int = 0
    sources: list[PaperSource] = field(default_factory=list)
    limit: int = 20
    offset: int = 0
    sort_by: str = "relevance"  # relevance, date, citations

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "title": self.title,
            "author": self.author,
            "abstract": self.abstract,
            "keywords": self.keywords,
            "categories": self.categories,
            "year_from": self.year_from,
            "year_to": self.year_to,
            "venues": self.venues,
            "publication_types": [t.value for t in self.publication_types],
            "open_access_only": self.open_access_only,
            "min_citations": self.min_citations,
            "sources": [s.value for s in self.sources],
            "limit": self.limit,
            "offset": self.offset,
            "sort_by": self.sort_by,
        }


@dataclass
class SearchResult:
    """A search result with relevance score."""

    paper: Paper
    score: float = 0.0
    source: PaperSource = PaperSource.MANUAL
    highlights: list[str] = field(default_factory=list)
    matched_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper": self.paper.to_dict(),
            "score": self.score,
            "source": self.source.value,
            "highlights": self.highlights,
            "matched_fields": self.matched_fields,
        }


@dataclass
class SearchResponse:
    """Response from a literature search."""

    results: list[SearchResult] = field(default_factory=list)
    total_count: int = 0
    query_time_ms: float = 0.0
    sources_queried: list[str] = field(default_factory=list)
    facets: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "total_count": self.total_count,
            "query_time_ms": self.query_time_ms,
            "sources_queried": self.sources_queried,
            "facets": self.facets,
        }


# ===========================================
# RECOMMENDATION DATA CLASSES
# ===========================================


@dataclass
class Recommendation:
    """A paper recommendation."""

    paper: Paper
    score: float = 0.0
    reason: str = ""
    based_on: list[str] = field(default_factory=list)  # Paper IDs it's based on

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper": self.paper.to_dict(),
            "score": self.score,
            "reason": self.reason,
            "based_on": self.based_on,
        }


@dataclass
class LiteratureReview:
    """A collection of papers for a literature review."""

    review_id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    topic: str = ""
    papers: list[Paper] = field(default_factory=list)
    sections: dict[str, list[str]] = field(default_factory=dict)  # Section -> paper IDs
    summary: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "title": self.title,
            "topic": self.topic,
            "papers": [p.to_dict() for p in self.papers],
            "sections": self.sections,
            "summary": self.summary,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


# ===========================================
# UTILITY DATA CLASSES
# ===========================================


@dataclass
class PDFContent:
    """Extracted content from a PDF."""

    paper_id: str
    text: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    figures: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    extraction_method: str = ""
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "text": self.text,
            "sections": self.sections,
            "figures": self.figures,
            "tables": self.tables,
            "references": self.references,
            "extraction_method": self.extraction_method,
            "extracted_at": self.extracted_at.isoformat(),
        }


__all__ = [
    # Enums
    "PaperSource",
    "PublicationType",
    "CitationIntent",
    # Author classes
    "Author",
    # Paper classes
    "Paper",
    # Citation classes
    "Citation",
    # Search classes
    "SearchQuery",
    "SearchResult",
    "SearchResponse",
    # Recommendation classes
    "Recommendation",
    "LiteratureReview",
    # Utility classes
    "PDFContent",
]
