"""Repository layer for database operations.

This module provides the repository pattern implementation for
data access across different storage backends.
"""

from platform.repositories.base import BaseRepository
from platform.repositories.exceptions import (
    ConcurrencyError,
    ConnectionError,
    DuplicateEntityError,
    EntityNotFoundError,
    RepositoryError,
    TransactionError,
    ValidationError,
)
from platform.repositories.experiment_repository import (
    ExperimentPlanRepository,
    ExperimentRepository,
    ExperimentResultRepository,
    HypothesisRepository,
)
from platform.repositories.knowledge_repository import (
    CitationRepository,
    KnowledgeEntryRepository,
    ProvenanceRepository,
    RelationshipRepository,
)
from platform.repositories.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    ResilientRepository,
    RetryConfig,
    with_circuit_breaker,
    with_retry,
)
from platform.repositories.token_repository import TokenRepository
from platform.repositories.unit_of_work import UnitOfWork, create_unit_of_work
from platform.repositories.user_repository import UserRepository

__all__ = [
    # Base
    "BaseRepository",
    # Unit of Work
    "UnitOfWork",
    "create_unit_of_work",
    # Exceptions
    "RepositoryError",
    "EntityNotFoundError",
    "DuplicateEntityError",
    "ValidationError",
    "ConcurrencyError",
    "TransactionError",
    "ConnectionError",
    # Resilience
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "RetryConfig",
    "ResilientRepository",
    "with_retry",
    "with_circuit_breaker",
    # Security/Auth
    "UserRepository",
    "TokenRepository",
    # Experiments
    "ExperimentRepository",
    "ExperimentPlanRepository",
    "ExperimentResultRepository",
    "HypothesisRepository",
    # Knowledge
    "KnowledgeEntryRepository",
    "CitationRepository",
    "RelationshipRepository",
    "ProvenanceRepository",
]
