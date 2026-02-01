"""Resilience patterns for repository operations.

Provides retry logic, circuit breaker, and other resilience patterns
for handling transient failures in database operations.
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ParamSpec, TypeVar

from platform.repositories.exceptions import ConnectionError, TransactionError
from platform.shared.utils.datetime_utils import utcnow
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def _sanitize_error_for_logging(error: Exception) -> str:
    """Sanitize an error for safe logging.

    Removes potentially sensitive information like:
    - File paths
    - Connection strings
    - SQL queries
    - Stack traces

    Args:
        error: The exception to sanitize

    Returns:
        Safe error description for logging
    """
    error_type = type(error).__name__

    # Map known error types to generic descriptions
    safe_messages = {
        "ConnectionError": "Database connection failed",
        "TransactionError": "Transaction operation failed",
        "TimeoutError": "Operation timed out",
        "OSError": "System I/O error",
        "OperationalError": "Database operational error",
        "IntegrityError": "Data integrity constraint violation",
        "ProgrammingError": "Query execution error",
    }

    return safe_messages.get(error_type, f"Error of type {error_type}")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff (e.g., 2 for doubling)
        jitter: Whether to add random jitter to delay
        retryable_exceptions: Exception types that should trigger retry
    """

    max_retries: int = 3
    base_delay: float = 0.1
    max_delay: float = 10.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: (
            ConnectionError,
            TransactionError,
            TimeoutError,
            OSError,
        )
    )

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number.

        Args:
            attempt: The attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay,
        )

        if self.jitter:
            import random

            delay = delay * (0.5 + random.random())

        return delay


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior.

    Attributes:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        success_threshold: Successes needed to close circuit from half-open
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    success_threshold: int = 2


class CircuitBreaker:
    """Circuit breaker for preventing cascading failures.

    Tracks failures and opens the circuit when too many occur,
    preventing further requests until the service recovers.
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Initialize the circuit breaker.

        Args:
            name: Identifier for this circuit breaker
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get the current circuit state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if the circuit is open (rejecting requests)."""
        return self._state == CircuitState.OPEN

    async def _check_state_transition(self) -> None:
        """Check and perform state transitions based on current conditions."""
        if self._state == CircuitState.OPEN:
            if (
                self._last_failure_time
                and (utcnow() - self._last_failure_time).total_seconds()
                >= self.config.recovery_timeout
            ):
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info(
                    "circuit_breaker_half_open",
                    name=self.name,
                )

    async def record_success(self) -> None:
        """Record a successful operation."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("circuit_breaker_closed", name=self.name)
            elif self._state == CircuitState.CLOSED:
                # Decay failure count on success
                self._failure_count = max(0, self._failure_count - 1)

    async def record_failure(self, error: Exception) -> None:
        """Record a failed operation.

        Args:
            error: The exception that occurred
        """
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = utcnow()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_reopened",
                    name=self.name,
                    error_type=type(error).__name__,
                    error_msg=_sanitize_error_for_logging(error),
                )
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.config.failure_threshold
            ):
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_opened",
                    name=self.name,
                    failure_count=self._failure_count,
                )

    async def call(
        self,
        func: Callable[P, Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Execute a function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            The function's return value

        Raises:
            ConnectionError: If the circuit is open
            Exception: Any exception from the wrapped function
        """
        async with self._lock:
            await self._check_state_transition()

            if self._state == CircuitState.OPEN:
                raise ConnectionError(
                    f"Circuit breaker '{self.name}' is open"
                )

        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure(e)
            raise


def with_retry(
    config: RetryConfig | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator for adding retry logic to async functions.

    Args:
        config: Retry configuration

    Returns:
        Decorated function with retry logic

    Example:
        @with_retry(RetryConfig(max_retries=5))
        async def fetch_data():
            ...
    """
    _config = config or RetryConfig()

    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(_config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except _config.retryable_exceptions as e:
                    last_exception = e
                    if attempt < _config.max_retries:
                        delay = _config.calculate_delay(attempt)
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_retries=_config.max_retries,
                            delay=round(delay, 3),
                            error_type=type(e).__name__,
                            error_msg=_sanitize_error_for_logging(e),
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            max_retries=_config.max_retries,
                            error_type=type(e).__name__,
                            error_msg=_sanitize_error_for_logging(e),
                        )

            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state: no result and no exception")

        return wrapper

    return decorator


def with_circuit_breaker(
    circuit_breaker: CircuitBreaker,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator for adding circuit breaker protection to async functions.

    Args:
        circuit_breaker: Circuit breaker instance to use

    Returns:
        Decorated function with circuit breaker protection

    Example:
        db_circuit = CircuitBreaker("database")

        @with_circuit_breaker(db_circuit)
        async def query_database():
            ...
    """

    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await circuit_breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator


class ResilientRepository:
    """Mixin class adding resilience patterns to repositories.

    Add this as a base class to repositories that need
    retry and circuit breaker functionality.

    Example:
        class MyRepository(ResilientRepository, BaseRepository[MyModel]):
            ...
    """

    _circuit_breaker: CircuitBreaker | None = None
    _retry_config: RetryConfig | None = None

    def _get_circuit_breaker(self) -> CircuitBreaker:
        """Get or create the circuit breaker for this repository."""
        if self._circuit_breaker is None:
            self._circuit_breaker = CircuitBreaker(
                name=self.__class__.__name__,
            )
        return self._circuit_breaker

    def _get_retry_config(self) -> RetryConfig:
        """Get or create the retry configuration for this repository."""
        if self._retry_config is None:
            self._retry_config = RetryConfig()
        return self._retry_config

    async def _execute_with_resilience(
        self,
        func: Callable[[], Awaitable[T]],
    ) -> T:
        """Execute a function with retry and circuit breaker protection.

        Args:
            func: Async function to execute

        Returns:
            The function's return value
        """
        circuit_breaker = self._get_circuit_breaker()
        retry_config = self._get_retry_config()

        @with_retry(retry_config)
        async def resilient_call() -> T:
            return await circuit_breaker.call(func)

        return await resilient_call()


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "ResilientRepository",
    "RetryConfig",
    "with_circuit_breaker",
    "with_retry",
]
