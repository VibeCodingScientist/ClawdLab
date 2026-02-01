"""Base repository abstract class.

Provides a generic repository interface for CRUD operations
that can be implemented by specific repositories.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import ColumnElement, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from platform.repositories.exceptions import ValidationError
from platform.shared.utils.datetime_utils import utcnow

T = TypeVar("T")

# Maximum allowed limit for pagination to prevent DoS
MAX_QUERY_LIMIT = 1000
# Maximum allowed search query length
MAX_SEARCH_LENGTH = 500


def validate_pagination(limit: int, offset: int) -> tuple[int, int]:
    """Validate pagination parameters.

    Args:
        limit: Requested limit
        offset: Requested offset

    Returns:
        Validated (limit, offset) tuple

    Raises:
        ValidationError: If parameters are invalid
    """
    if limit < 0:
        raise ValidationError("Limit must be non-negative", field="limit")
    if offset < 0:
        raise ValidationError("Offset must be non-negative", field="offset")
    if limit > MAX_QUERY_LIMIT:
        limit = MAX_QUERY_LIMIT
    return limit, offset


def validate_search_query(query_text: str) -> str:
    """Validate search query text.

    Args:
        query_text: The search query

    Returns:
        Validated query text

    Raises:
        ValidationError: If query is invalid
    """
    if not query_text or not query_text.strip():
        raise ValidationError("Search query cannot be empty", field="query")
    if len(query_text) > MAX_SEARCH_LENGTH:
        raise ValidationError(
            f"Search query too long (max {MAX_SEARCH_LENGTH} characters)",
            field="query",
        )
    return query_text.strip()


def parse_uuid(value: str | UUID, field_name: str = "id") -> UUID | None:
    """Parse a string to UUID safely.

    Args:
        value: String or UUID value
        field_name: Field name for error messages

    Returns:
        UUID if valid, None if invalid string format
    """
    if isinstance(value, UUID):
        return value
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        return None


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository providing common CRUD operations.

    This class defines the interface that all repositories should implement.
    Concrete repositories should inherit from this class and provide
    implementations for the abstract methods.

    Type Parameters:
        T: The entity type this repository manages

    Recommended Database Indexes:
        - Primary key on `id`
        - Index on `created_at` for ordering
        - Index on `status` if filtering by status is common
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session

    @property
    @abstractmethod
    def model_class(self) -> type[T]:
        """Return the SQLAlchemy model class for this repository.

        Returns:
            The model class type
        """
        pass

    async def get_by_id(self, entity_id: str | UUID) -> T | None:
        """Get an entity by its ID.

        Args:
            entity_id: The unique identifier of the entity

        Returns:
            The entity if found, None otherwise
        """
        parsed_id = parse_uuid(entity_id)
        if parsed_id is None:
            return None

        query = select(self.model_class).where(self.model_class.id == parsed_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[T]:
        """Get all entities with pagination.

        Args:
            limit: Maximum number of entities to return (max 1000)
            offset: Number of entities to skip

        Returns:
            List of entities

        Raises:
            ValidationError: If pagination parameters are invalid
        """
        limit, offset = validate_pagination(limit, offset)

        query = (
            select(self.model_class)
            .limit(limit)
            .offset(offset)
            .order_by(self.model_class.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_field(
        self,
        field_name: str,
        field_value: Any,
        limit: int = 100,
        offset: int = 0,
    ) -> list[T]:
        """List entities filtered by a single field.

        This is a generic helper to reduce code duplication in child repositories.

        Args:
            field_name: Name of the field to filter by
            field_value: Value to filter for
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching entities

        Raises:
            ValidationError: If pagination parameters are invalid
            AttributeError: If field doesn't exist on model
        """
        limit, offset = validate_pagination(limit, offset)

        field = getattr(self.model_class, field_name)
        query = (
            select(self.model_class)
            .where(field == field_value)
            .limit(limit)
            .offset(offset)
            .order_by(self.model_class.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_with_filters(
        self,
        filters: list[ColumnElement[bool]],
        limit: int = 100,
        offset: int = 0,
    ) -> list[T]:
        """List entities with multiple filter conditions.

        Args:
            filters: List of SQLAlchemy filter expressions
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching entities
        """
        limit, offset = validate_pagination(limit, offset)

        query = select(self.model_class)
        for f in filters:
            query = query.where(f)
        query = query.limit(limit).offset(offset).order_by(self.model_class.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, entity: T) -> T:
        """Create a new entity.

        Args:
            entity: The entity to create

        Returns:
            The created entity with generated ID
        """
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(
        self,
        entity_id: str | UUID,
        **kwargs: Any,
    ) -> T | None:
        """Update an entity by ID.

        Args:
            entity_id: The ID of the entity to update
            **kwargs: Fields to update

        Returns:
            The updated entity if found, None otherwise
        """
        parsed_id = parse_uuid(entity_id)
        if parsed_id is None:
            return None

        # Filter out None values and add updated_at
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            return await self.get_by_id(parsed_id)

        # Add updated_at if the model has it
        if hasattr(self.model_class, "updated_at"):
            updates["updated_at"] = utcnow()

        await self.session.execute(
            update(self.model_class)
            .where(self.model_class.id == parsed_id)
            .values(**updates)
        )
        await self.session.flush()

        return await self.get_by_id(parsed_id)

    async def delete(self, entity_id: str | UUID) -> bool:
        """Delete an entity by ID.

        Args:
            entity_id: The ID of the entity to delete

        Returns:
            True if deleted, False if not found
        """
        parsed_id = parse_uuid(entity_id)
        if parsed_id is None:
            return False

        result = await self.session.execute(
            delete(self.model_class).where(self.model_class.id == parsed_id)
        )
        return result.rowcount > 0

    async def exists(self, entity_id: str | UUID) -> bool:
        """Check if an entity exists by ID.

        Args:
            entity_id: The ID to check

        Returns:
            True if exists, False otherwise
        """
        parsed_id = parse_uuid(entity_id)
        if parsed_id is None:
            return False

        query = select(self.model_class.id).where(self.model_class.id == parsed_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def count(self) -> int:
        """Count total entities.

        Returns:
            Total count of entities
        """
        query = select(func.count()).select_from(self.model_class)
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def count_by_field(self, field_name: str, field_value: Any) -> int:
        """Count entities matching a field value.

        Args:
            field_name: Name of the field to filter by
            field_value: Value to filter for

        Returns:
            Count of matching entities
        """
        field = getattr(self.model_class, field_name)
        query = select(func.count()).select_from(self.model_class).where(field == field_value)
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def save(self, entity: T) -> T:
        """Save an entity (create or update).

        If the entity has an ID, it will be updated.
        Otherwise, it will be created.

        Args:
            entity: The entity to save

        Returns:
            The saved entity
        """
        if hasattr(entity, "id") and entity.id:
            existing = await self.get_by_id(entity.id)
            if existing:
                # Merge the entity into the session
                entity = await self.session.merge(entity)
                await self.session.flush()
                return entity

        return await self.create(entity)

    async def bulk_create(self, entities: list[T]) -> list[T]:
        """Create multiple entities in a batch.

        Args:
            entities: List of entities to create

        Returns:
            List of created entities
        """
        if not entities:
            return []

        self.session.add_all(entities)
        await self.session.flush()
        return entities

    async def bulk_delete(self, entity_ids: list[str | UUID]) -> int:
        """Delete multiple entities by IDs.

        Args:
            entity_ids: List of entity IDs to delete

        Returns:
            Number of entities deleted
        """
        if not entity_ids:
            return 0

        # Parse all UUIDs, filtering out invalid ones
        parsed_ids = [parse_uuid(eid) for eid in entity_ids]
        valid_ids = [pid for pid in parsed_ids if pid is not None]

        if not valid_ids:
            return 0

        result = await self.session.execute(
            delete(self.model_class).where(self.model_class.id.in_(valid_ids))
        )
        return result.rowcount


__all__ = [
    "BaseRepository",
    "MAX_QUERY_LIMIT",
    "MAX_SEARCH_LENGTH",
    "parse_uuid",
    "validate_pagination",
    "validate_search_query",
]
