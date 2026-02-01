"""Redis client with connection pooling and retry logic."""

import json
import os
from datetime import timedelta
from typing import Any

import redis.asyncio as redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

# Global client instance
_redis_client: redis.Redis | None = None


def get_redis_url() -> str:
    """Get Redis URL from environment."""
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


async def get_redis_client() -> redis.Redis:
    """Get or create Redis client with connection pooling."""
    global _redis_client
    if _redis_client is None:
        retry = Retry(ExponentialBackoff(), retries=3)
        _redis_client = redis.from_url(
            get_redis_url(),
            encoding="utf-8",
            decode_responses=True,
            retry=retry,
            retry_on_timeout=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )
        logger.info("redis_client_created", url=get_redis_url().split("@")[-1])
    return _redis_client


async def close_redis_client() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("redis_client_closed")


class RedisCache:
    """High-level Redis cache operations."""

    def __init__(self, prefix: str = "asrp"):
        self.prefix = prefix

    def _key(self, key: str) -> str:
        """Generate prefixed key."""
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        client = await get_redis_client()
        value = await client.get(self._key(key))
        if value is not None:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | timedelta | None = None,
    ) -> bool:
        """Set value in cache with optional TTL."""
        client = await get_redis_client()
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        if isinstance(ttl, timedelta):
            ttl = int(ttl.total_seconds())
        return await client.set(self._key(key), value, ex=ttl)

    async def setex(self, key: str, ttl: int, value: Any) -> bool:
        """Set value with TTL in seconds."""
        return await self.set(key, value, ttl=ttl)

    async def delete(self, key: str) -> int:
        """Delete key from cache."""
        client = await get_redis_client()
        return await client.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        client = await get_redis_client()
        return await client.exists(self._key(key)) > 0

    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment counter."""
        client = await get_redis_client()
        return await client.incrby(self._key(key), amount)

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on key."""
        client = await get_redis_client()
        return await client.expire(self._key(key), ttl)

    async def ttl(self, key: str) -> int:
        """Get TTL of key in seconds."""
        client = await get_redis_client()
        return await client.ttl(self._key(key))


class RateLimiter:
    """Token bucket rate limiter using Redis."""

    def __init__(
        self,
        prefix: str = "ratelimit",
        default_limit: int = 100,
        default_window: int = 3600,
    ):
        self.cache = RedisCache(prefix)
        self.default_limit = default_limit
        self.default_window = default_window

    async def is_allowed(
        self,
        identifier: str,
        limit: int | None = None,
        window: int | None = None,
    ) -> tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.

        Args:
            identifier: Unique identifier (e.g., agent_id, IP)
            limit: Maximum requests in window
            window: Window size in seconds

        Returns:
            Tuple of (is_allowed, remaining_requests, reset_time_seconds)
        """
        limit = limit or self.default_limit
        window = window or self.default_window
        key = f"{identifier}:{window}"

        client = await get_redis_client()
        current = await client.get(self.cache._key(key))

        if current is None:
            # First request in window
            await client.setex(self.cache._key(key), window, 1)
            return True, limit - 1, window

        current = int(current)
        if current >= limit:
            # Rate limited
            ttl = await client.ttl(self.cache._key(key))
            return False, 0, ttl

        # Increment counter
        await client.incr(self.cache._key(key))
        remaining = limit - current - 1
        ttl = await client.ttl(self.cache._key(key))
        return True, remaining, ttl


class DistributedLock:
    """Distributed lock using Redis."""

    def __init__(self, name: str, timeout: int = 30):
        self.name = f"lock:{name}"
        self.timeout = timeout
        self._lock: redis.lock.Lock | None = None

    async def acquire(self, blocking: bool = True, blocking_timeout: float = 10) -> bool:
        """Acquire the lock."""
        client = await get_redis_client()
        self._lock = client.lock(
            self.name,
            timeout=self.timeout,
            blocking=blocking,
            blocking_timeout=blocking_timeout,
        )
        return await self._lock.acquire()

    async def release(self) -> None:
        """Release the lock."""
        if self._lock is not None:
            await self._lock.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


async def health_check() -> bool:
    """Check Redis connectivity."""
    try:
        client = await get_redis_client()
        await client.ping()
        return True
    except Exception as e:
        logger.error("redis_health_check_failed", error=str(e))
        return False
