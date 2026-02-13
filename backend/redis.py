"""Redis connection management."""

import redis.asyncio as aioredis

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Get the shared Redis connection. Must be initialized first via init_redis()."""
    if _redis is None:
        raise RuntimeError("Redis not initialized — app not started")
    return _redis


async def init_redis(url: str = "redis://localhost:6379/0") -> aioredis.Redis:
    """Initialize the global Redis connection."""
    global _redis
    _redis = aioredis.from_url(url, decode_responses=True)
    await _redis.ping()
    return _redis


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
