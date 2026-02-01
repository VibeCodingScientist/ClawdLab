"""Configuration for Literature Integration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class LiteratureSettings(BaseSettings):
    """Settings for literature integration."""

    model_config = {"env_prefix": "LITERATURE_", "case_sensitive": False}

    # arXiv Settings
    arxiv_base_url: str = Field(
        default="http://export.arxiv.org/api/query",
        description="arXiv API base URL",
    )
    arxiv_rate_limit: float = Field(
        default=3.0,
        description="Minimum seconds between arXiv requests",
    )
    arxiv_max_results: int = Field(
        default=100,
        description="Maximum results per arXiv query",
    )

    # PubMed Settings
    pubmed_base_url: str = Field(
        default="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        description="PubMed E-utilities base URL",
    )
    pubmed_api_key: str = Field(
        default="",
        description="NCBI API key for higher rate limits",
    )
    pubmed_rate_limit: float = Field(
        default=0.34,  # 3 requests per second without key
        description="Minimum seconds between PubMed requests",
    )
    pubmed_max_results: int = Field(
        default=100,
        description="Maximum results per PubMed query",
    )

    # Semantic Scholar Settings
    semantic_scholar_base_url: str = Field(
        default="https://api.semanticscholar.org/graph/v1",
        description="Semantic Scholar API base URL",
    )
    semantic_scholar_api_key: str = Field(
        default="",
        description="Semantic Scholar API key",
    )
    semantic_scholar_rate_limit: float = Field(
        default=0.1,  # 100 requests per 5 minutes = ~10/sec
        description="Minimum seconds between S2 requests",
    )

    # CrossRef Settings
    crossref_base_url: str = Field(
        default="https://api.crossref.org",
        description="CrossRef API base URL",
    )
    crossref_email: str = Field(
        default="",
        description="Email for CrossRef polite pool",
    )

    # General Settings
    cache_ttl_seconds: int = Field(
        default=86400,  # 24 hours
        description="Cache TTL for literature data",
    )
    request_timeout: int = Field(
        default=30,
        description="HTTP request timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retries for failed requests",
    )

    # PDF Settings
    pdf_download_dir: str = Field(
        default="/tmp/literature_pdfs",
        description="Directory for downloaded PDFs",
    )
    max_pdf_size_mb: int = Field(
        default=50,
        description="Maximum PDF size to download",
    )

    # Search Settings
    default_search_limit: int = Field(
        default=20,
        description="Default number of search results",
    )
    enable_full_text_search: bool = Field(
        default=False,
        description="Enable full-text PDF search",
    )


@lru_cache
def get_settings() -> LiteratureSettings:
    """Get cached literature settings."""
    return LiteratureSettings()


# arXiv Categories
ARXIV_CATEGORIES = {
    "cs.AI": "Artificial Intelligence",
    "cs.CL": "Computation and Language",
    "cs.CV": "Computer Vision",
    "cs.LG": "Machine Learning",
    "cs.NE": "Neural and Evolutionary Computing",
    "stat.ML": "Machine Learning (Statistics)",
    "q-bio.BM": "Biomolecules",
    "q-bio.GN": "Genomics",
    "q-bio.QM": "Quantitative Methods",
    "physics.chem-ph": "Chemical Physics",
    "cond-mat.mtrl-sci": "Materials Science",
    "math.CO": "Combinatorics",
    "math.NT": "Number Theory",
    "math.AG": "Algebraic Geometry",
}

# PubMed Databases
PUBMED_DATABASES = {
    "pubmed": "PubMed citations",
    "pmc": "PubMed Central full-text",
    "mesh": "MeSH terms",
    "gene": "Gene database",
    "protein": "Protein database",
}

# Semantic Scholar Fields
S2_PAPER_FIELDS = [
    "paperId",
    "externalIds",
    "url",
    "title",
    "abstract",
    "venue",
    "year",
    "referenceCount",
    "citationCount",
    "influentialCitationCount",
    "isOpenAccess",
    "openAccessPdf",
    "fieldsOfStudy",
    "s2FieldsOfStudy",
    "publicationTypes",
    "publicationDate",
    "journal",
    "authors",
]

S2_AUTHOR_FIELDS = [
    "authorId",
    "externalIds",
    "url",
    "name",
    "affiliations",
    "homepage",
    "paperCount",
    "citationCount",
    "hIndex",
]

# Research Domains to Literature Categories Mapping
DOMAIN_TO_CATEGORIES = {
    "mathematics": ["math.*", "cs.LO", "cs.CC"],
    "ml_ai": ["cs.LG", "cs.AI", "cs.NE", "stat.ML", "cs.CL", "cs.CV"],
    "computational_biology": ["q-bio.*", "cs.CE"],
    "materials_science": ["cond-mat.mtrl-sci", "physics.chem-ph", "physics.comp-ph"],
    "bioinformatics": ["q-bio.GN", "q-bio.QM", "q-bio.BM"],
}

# Publication Types
PUBLICATION_TYPES = {
    "journal_article": "Journal Article",
    "conference_paper": "Conference Paper",
    "preprint": "Preprint",
    "review": "Review Article",
    "book_chapter": "Book Chapter",
    "thesis": "Thesis/Dissertation",
    "dataset": "Dataset",
    "software": "Software",
}

# Citation Context Types
CITATION_CONTEXTS = {
    "background": "Background/Introduction",
    "method": "Methodology",
    "result": "Results comparison",
    "discussion": "Discussion",
    "future_work": "Future work",
}
