"""Literature Integration Module.

This module provides comprehensive literature integration capabilities:
- Paper search across arXiv, PubMed, and Semantic Scholar
- Citation and reference tracking
- Author information and paper discovery
- Literature recommendations
- Automated literature review creation

The literature integration layer enables agents to discover,
analyze, and cite scientific literature in their research.
"""

from platform.literature.arxiv_client import (
    ArxivClient,
    get_arxiv_client,
)
from platform.literature.base import (
    # Enums
    CitationIntent,
    PaperSource,
    PublicationType,
    # Author classes
    Author,
    # Paper classes
    Paper,
    # Citation classes
    Citation,
    # Search classes
    SearchQuery,
    SearchResponse,
    SearchResult,
    # Recommendation classes
    LiteratureReview,
    Recommendation,
    # Utility classes
    PDFContent,
)
from platform.literature.config import (
    ARXIV_CATEGORIES,
    DOMAIN_TO_CATEGORIES,
    PUBMED_DATABASES,
    LiteratureSettings,
    get_settings,
)
from platform.literature.pubmed_client import (
    PubMedClient,
    get_pubmed_client,
)
from platform.literature.semantic_scholar_client import (
    SemanticScholarClient,
    get_semantic_scholar_client,
)
from platform.literature.service import (
    LiteratureService,
    LiteratureStats,
    get_literature_service,
)

__all__ = [
    # Config
    "get_settings",
    "LiteratureSettings",
    "ARXIV_CATEGORIES",
    "PUBMED_DATABASES",
    "DOMAIN_TO_CATEGORIES",
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
    # Clients
    "ArxivClient",
    "get_arxiv_client",
    "PubMedClient",
    "get_pubmed_client",
    "SemanticScholarClient",
    "get_semantic_scholar_client",
    # Main service
    "LiteratureService",
    "LiteratureStats",
    "get_literature_service",
]
