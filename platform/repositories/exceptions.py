"""Repository layer exceptions.

Provides a typed exception hierarchy for repository operations,
enabling precise error handling and better debugging.
"""

from typing import Any


class RepositoryError(Exception):
    """Base exception for all repository errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - {self.details}"
        return self.message


class EntityNotFoundError(RepositoryError):
    """Raised when an entity is not found in the database."""

    def __init__(
        self,
        entity_type: str,
        entity_id: str | None = None,
        **lookup_params: Any,
    ) -> None:
        details = {"entity_type": entity_type}
        if entity_id:
            details["entity_id"] = entity_id
        details.update(lookup_params)

        message = f"{entity_type} not found"
        if entity_id:
            message = f"{entity_type} with id '{entity_id}' not found"

        super().__init__(message, details)
        self.entity_type = entity_type
        self.entity_id = entity_id


class DuplicateEntityError(RepositoryError):
    """Raised when attempting to create a duplicate entity."""

    def __init__(
        self,
        entity_type: str,
        field: str,
        value: str,
    ) -> None:
        message = f"{entity_type} with {field}='{value}' already exists"
        details = {
            "entity_type": entity_type,
            "field": field,
            "value": value,
        }
        super().__init__(message, details)
        self.entity_type = entity_type
        self.field = field
        self.value = value


class ValidationError(RepositoryError):
    """Raised when entity validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        errors: list[str] | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if field:
            details["field"] = field
        if errors:
            details["errors"] = errors

        super().__init__(message, details)
        self.field = field
        self.errors = errors or []


class ConcurrencyError(RepositoryError):
    """Raised when a concurrent modification conflict occurs."""

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        message = (
            f"Concurrent modification detected for {entity_type} '{entity_id}': "
            f"expected version {expected_version}, found {actual_version}"
        )
        details = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "expected_version": expected_version,
            "actual_version": actual_version,
        }
        super().__init__(message, details)


class TransactionError(RepositoryError):
    """Raised when a transaction operation fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        details: dict[str, Any] = {}
        if original_error:
            details["original_error"] = str(original_error)
            details["error_type"] = type(original_error).__name__

        super().__init__(message, details)
        self.original_error = original_error


class ConnectionError(RepositoryError):
    """Raised when database connection fails."""

    def __init__(self, message: str, host: str | None = None, port: int | None = None) -> None:
        details: dict[str, Any] = {}
        if host:
            details["host"] = host
        if port:
            details["port"] = port

        super().__init__(message, details)


__all__ = [
    "RepositoryError",
    "EntityNotFoundError",
    "DuplicateEntityError",
    "ValidationError",
    "ConcurrencyError",
    "TransactionError",
    "ConnectionError",
]
