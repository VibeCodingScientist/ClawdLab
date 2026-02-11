"""Configuration for Knowledge Management System."""

from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


class KnowledgeSettings(BaseSettings):
    """Settings for knowledge management."""

    model_config = {"env_prefix": "KNOWLEDGE_", "case_sensitive": False}

    # Database Settings
    postgres_url: str = Field(
        default="postgresql://localhost/research_knowledge",
        description="PostgreSQL connection URL",
    )
    postgres_pool_size: int = Field(
        default=10,
        description="Database connection pool size",
    )

    # Vector Database Settings
    vector_db_type: str = Field(
        default="pgvector",
        description="Vector database type (pgvector, pinecone, qdrant)",
    )
    vector_dimension: int = Field(
        default=1536,
        description="Embedding vector dimension",
    )

    # Embedding Settings
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model to use",
    )
    embedding_batch_size: int = Field(
        default=100,
        description="Batch size for embedding generation",
    )

    # Search Settings
    default_search_limit: int = Field(
        default=20,
        description="Default number of search results",
    )
    similarity_threshold: float = Field(
        default=0.7,
        description="Minimum similarity score for search results",
    )
    max_search_results: int = Field(
        default=100,
        description="Maximum search results to return",
    )

    # Caching Settings
    redis_url: str = Field(
        default="redis://localhost:6379/1",
        description="Redis URL for caching",
    )
    cache_ttl_seconds: int = Field(
        default=3600,
        description="Cache TTL in seconds",
    )

    # Retention Settings
    archive_after_days: int = Field(
        default=365,
        description="Archive entries older than this",
    )
    max_versions_per_entry: int = Field(
        default=10,
        description="Maximum versions to keep per entry",
    )


@lru_cache
def get_settings() -> KnowledgeSettings:
    """Get cached knowledge settings."""
    return KnowledgeSettings()


# Knowledge Entry Types
ENTRY_TYPES = {
    "claim": {
        "name": "Verified Claim",
        "description": "A verified scientific claim",
        "required_fields": ["content", "domain", "verification_status"],
    },
    "finding": {
        "name": "Research Finding",
        "description": "A research finding or result",
        "required_fields": ["content", "domain"],
    },
    "hypothesis": {
        "name": "Hypothesis",
        "description": "A scientific hypothesis",
        "required_fields": ["content", "domain"],
    },
    "method": {
        "name": "Method",
        "description": "A research method or protocol",
        "required_fields": ["content", "domain"],
    },
    "dataset": {
        "name": "Dataset",
        "description": "Reference to a dataset",
        "required_fields": ["name", "source"],
    },
    "model": {
        "name": "Model",
        "description": "A trained model reference",
        "required_fields": ["name", "type"],
    },
    "publication": {
        "name": "Publication",
        "description": "A scientific publication reference",
        "required_fields": ["title", "authors"],
    },
}

# Verification Status Values
VERIFICATION_STATUSES = [
    "verified",
    "refuted",
    "partial",
    "inconclusive",
    "pending",
    "disputed",
]

# Relationship Types for Knowledge Graph
RELATIONSHIP_TYPES = {
    "supports": {
        "name": "Supports",
        "description": "Source supports target claim",
        "inverse": "supported_by",
    },
    "refutes": {
        "name": "Refutes",
        "description": "Source refutes target claim",
        "inverse": "refuted_by",
    },
    "cites": {
        "name": "Cites",
        "description": "Source cites target",
        "inverse": "cited_by",
    },
    "extends": {
        "name": "Extends",
        "description": "Source extends target work",
        "inverse": "extended_by",
    },
    "uses": {
        "name": "Uses",
        "description": "Source uses target (method, data, model)",
        "inverse": "used_by",
    },
    "derived_from": {
        "name": "Derived From",
        "description": "Source is derived from target",
        "inverse": "derives",
    },
    "related_to": {
        "name": "Related To",
        "description": "Source is related to target",
        "inverse": "related_to",
    },
    "part_of": {
        "name": "Part Of",
        "description": "Source is part of target",
        "inverse": "contains",
    },
    "version_of": {
        "name": "Version Of",
        "description": "Source is a version of target",
        "inverse": "has_version",
    },
}

# Domain Categories
DOMAIN_CATEGORIES = {
    "mathematics": ["algebra", "analysis", "geometry", "topology", "logic", "number_theory"],
    "ml_ai": ["deep_learning", "nlp", "computer_vision", "reinforcement_learning", "optimization"],
    "computational_biology": ["protein_structure", "genomics", "drug_discovery", "systems_biology"],
    "materials_science": ["crystallography", "thermodynamics", "electrochemistry", "catalysis"],
    "bioinformatics": ["sequence_analysis", "transcriptomics", "proteomics", "metagenomics"],
}

# Confidence Levels
CONFIDENCE_LEVELS = {
    "high": {"min_score": 0.9, "label": "High Confidence"},
    "medium": {"min_score": 0.7, "label": "Medium Confidence"},
    "low": {"min_score": 0.5, "label": "Low Confidence"},
    "uncertain": {"min_score": 0.0, "label": "Uncertain"},
}
