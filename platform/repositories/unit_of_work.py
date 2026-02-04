"""Unit of Work pattern implementation.

Provides transaction management and repository coordination
for atomic operations across multiple repositories.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from platform.repositories.exceptions import TransactionError
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
from platform.repositories.user_repository import UserRepository
from platform.shared.utils.logging import get_logger

if TYPE_CHECKING:
    from platform.repositories.token_repository import TokenRepository

logger = get_logger(__name__)


class UnitOfWork:
    """Unit of Work pattern for coordinating repository operations.

    Provides a single transaction boundary for multiple repository operations,
    ensuring atomicity and consistency.

    Usage:
        async with UnitOfWork(session_factory) as uow:
            user = await uow.users.create_user(...)
            experiment = await uow.experiments.create_experiment(...)
            await uow.commit()

    If an exception occurs, the transaction is automatically rolled back.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | Callable[[], AsyncSession],
    ) -> None:
        """Initialize the Unit of Work.

        Args:
            session_factory: Factory function or sessionmaker for creating database sessions
        """
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

        # Repository instances (lazy-loaded)
        self._users: UserRepository | None = None
        self._experiments: ExperimentRepository | None = None
        self._experiment_plans: ExperimentPlanRepository | None = None
        self._experiment_results: ExperimentResultRepository | None = None
        self._hypotheses: HypothesisRepository | None = None
        self._knowledge_entries: KnowledgeEntryRepository | None = None
        self._citations: CitationRepository | None = None
        self._relationships: RelationshipRepository | None = None
        self._provenance: ProvenanceRepository | None = None

    @property
    def session(self) -> AsyncSession:
        """Get the current database session.

        Raises:
            RuntimeError: If the Unit of Work has not been entered
        """
        if self._session is None:
            raise RuntimeError("Unit of Work not started. Use 'async with' context manager.")
        return self._session

    # ===========================================
    # REPOSITORY ACCESSORS (Lazy Loading)
    # ===========================================

    @property
    def users(self) -> UserRepository:
        """Get the user repository."""
        if self._users is None:
            self._users = UserRepository(self.session)
        return self._users

    @property
    def experiments(self) -> ExperimentRepository:
        """Get the experiment repository."""
        if self._experiments is None:
            self._experiments = ExperimentRepository(self.session)
        return self._experiments

    @property
    def experiment_plans(self) -> ExperimentPlanRepository:
        """Get the experiment plan repository."""
        if self._experiment_plans is None:
            self._experiment_plans = ExperimentPlanRepository(self.session)
        return self._experiment_plans

    @property
    def experiment_results(self) -> ExperimentResultRepository:
        """Get the experiment result repository."""
        if self._experiment_results is None:
            self._experiment_results = ExperimentResultRepository(self.session)
        return self._experiment_results

    @property
    def hypotheses(self) -> HypothesisRepository:
        """Get the hypothesis repository."""
        if self._hypotheses is None:
            self._hypotheses = HypothesisRepository(self.session)
        return self._hypotheses

    @property
    def knowledge_entries(self) -> KnowledgeEntryRepository:
        """Get the knowledge entry repository."""
        if self._knowledge_entries is None:
            self._knowledge_entries = KnowledgeEntryRepository(self.session)
        return self._knowledge_entries

    @property
    def citations(self) -> CitationRepository:
        """Get the citation repository."""
        if self._citations is None:
            self._citations = CitationRepository(self.session)
        return self._citations

    @property
    def relationships(self) -> RelationshipRepository:
        """Get the relationship repository."""
        if self._relationships is None:
            self._relationships = RelationshipRepository(self.session)
        return self._relationships

    @property
    def provenance(self) -> ProvenanceRepository:
        """Get the provenance repository."""
        if self._provenance is None:
            self._provenance = ProvenanceRepository(self.session)
        return self._provenance

    # ===========================================
    # TRANSACTION MANAGEMENT
    # ===========================================

    async def __aenter__(self) -> UnitOfWork:
        """Enter the Unit of Work context.

        Creates a new database session and begins a transaction.
        """
        if callable(self._session_factory):
            self._session = self._session_factory()
        else:
            self._session = self._session_factory()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the Unit of Work context.

        If an exception occurred, the transaction is rolled back.
        Otherwise, uncommitted changes are still rolled back (explicit commit required).
        """
        if self._session is None:
            return

        try:
            if exc_type is not None:
                await self.rollback()
                logger.debug("transaction_rolled_back", exception_type=exc_type.__name__)
            else:
                # If no exception but not committed, rollback anyway
                # This ensures explicit commit is required
                await self.rollback()
        finally:
            await self._session.close()
            self._session = None
            self._reset_repositories()

    async def commit(self) -> None:
        """Commit the current transaction.

        Raises:
            TransactionError: If the commit fails
        """
        if self._session is None:
            raise RuntimeError("Unit of Work not started")

        try:
            await self._session.commit()
            logger.debug("transaction_committed")
        except Exception as e:
            await self.rollback()
            raise TransactionError("Failed to commit transaction", original_error=e) from e

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        if self._session is not None:
            await self._session.rollback()
            logger.debug("transaction_rolled_back_explicit")

    async def flush(self) -> None:
        """Flush pending changes to the database without committing.

        Useful for getting auto-generated IDs before commit.
        """
        if self._session is not None:
            await self._session.flush()

    def _reset_repositories(self) -> None:
        """Reset all repository instances."""
        self._users = None
        self._experiments = None
        self._experiment_plans = None
        self._experiment_results = None
        self._hypotheses = None
        self._knowledge_entries = None
        self._citations = None
        self._relationships = None
        self._provenance = None


@asynccontextmanager
async def create_unit_of_work(
    session_factory: async_sessionmaker[AsyncSession] | Callable[[], AsyncSession],
) -> AsyncGenerator[UnitOfWork, None]:
    """Create a Unit of Work context manager.

    This is a convenience function for creating a Unit of Work
    with automatic transaction management.

    Args:
        session_factory: Factory for creating database sessions

    Yields:
        UnitOfWork instance

    Example:
        async with create_unit_of_work(session_factory) as uow:
            user = await uow.users.create_user(...)
            await uow.commit()
    """
    uow = UnitOfWork(session_factory)
    async with uow:
        yield uow


__all__ = [
    "UnitOfWork",
    "create_unit_of_work",
]
