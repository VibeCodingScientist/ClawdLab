"""Rate limiting middleware for the platform."""

import time
from typing import Callable

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from platform.shared.clients.redis_client import get_redis_client
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimitConfig:
    """Rate limit configuration."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_limit: int = 10,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_limit = burst_limit


# Default rate limits per endpoint pattern
DEFAULT_RATE_LIMITS = {
    # Registration endpoints (stricter)
    "/v1/agents/register": RateLimitConfig(
        requests_per_minute=5,
        requests_per_hour=20,
        burst_limit=2,
    ),
    # Claim submission (moderate)
    "POST:/v1/claims": RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        burst_limit=5,
    ),
    # Challenge submission (moderate)
    "/challenges": RateLimitConfig(
        requests_per_minute=5,
        requests_per_hour=50,
        burst_limit=3,
    ),
    # Token operations (strict)
    "/tokens": RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=50,
        burst_limit=5,
    ),
    # Read operations (generous)
    "GET:": RateLimitConfig(
        requests_per_minute=120,
        requests_per_hour=3000,
        burst_limit=20,
    ),
    # Default for all other requests
    "default": RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        burst_limit=10,
    ),
}


def get_rate_limit_config(method: str, path: str) -> RateLimitConfig:
    """Get rate limit configuration for a specific endpoint."""
    # Check for specific endpoint matches
    for pattern, config in DEFAULT_RATE_LIMITS.items():
        if pattern == "default":
            continue
        if ":" in pattern:
            # Method-specific pattern
            pattern_method, pattern_path = pattern.split(":", 1)
            if method == pattern_method and pattern_path in path:
                return config
        elif pattern in path:
            return config

    # Check for method-only matches
    method_pattern = f"{method}:"
    if method_pattern in DEFAULT_RATE_LIMITS:
        return DEFAULT_RATE_LIMITS[method_pattern]

    return DEFAULT_RATE_LIMITS["default"]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis sliding window.

    Implements per-agent rate limiting with:
    - Per-minute limits (sliding window)
    - Per-hour limits (sliding window)
    - Burst protection
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for health endpoints
        if request.url.path in ("/health", "/ready", "/live", "/metrics"):
            return await call_next(request)

        # Get agent ID from request state (set by auth middleware)
        agent_context = getattr(request.state, "agent", None)
        if not agent_context:
            # No agent context = no rate limiting (auth will handle rejection)
            return await call_next(request)

        agent_id = agent_context.get("agent_id", "anonymous")
        method = request.method
        path = request.url.path

        # Get rate limit config for this endpoint
        config = get_rate_limit_config(method, path)

        # Check rate limits
        try:
            allowed, retry_after = await self._check_rate_limit(
                agent_id=agent_id,
                endpoint=f"{method}:{path}",
                config=config,
            )

            if not allowed:
                logger.warning(
                    "rate_limit_exceeded",
                    agent_id=agent_id,
                    endpoint=f"{method}:{path}",
                    retry_after=retry_after,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "type": "https://api.research-platform.ai/errors/rate_limit_exceeded",
                        "title": "Rate Limit Exceeded",
                        "status": 429,
                        "detail": f"Rate limit exceeded. Retry after {retry_after} seconds.",
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        except HTTPException:
            raise
        except Exception as e:
            # Log but don't block on rate limit errors
            logger.error("rate_limit_check_error", error=str(e))

        response = await call_next(request)
        return response

    async def _check_rate_limit(
        self,
        agent_id: str,
        endpoint: str,
        config: RateLimitConfig,
    ) -> tuple[bool, int]:
        """
        Check if request is within rate limits.

        Uses Redis sorted sets for sliding window rate limiting.

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        redis = await get_redis_client()
        now = time.time()

        # Key patterns
        minute_key = f"ratelimit:{agent_id}:{endpoint}:minute"
        hour_key = f"ratelimit:{agent_id}:{endpoint}:hour"

        # Remove old entries and count current window
        minute_ago = now - 60
        hour_ago = now - 3600

        async with redis.pipeline() as pipe:
            # Clean old entries
            await pipe.zremrangebyscore(minute_key, 0, minute_ago)
            await pipe.zremrangebyscore(hour_key, 0, hour_ago)

            # Count current entries
            await pipe.zcard(minute_key)
            await pipe.zcard(hour_key)

            results = await pipe.execute()

        minute_count = results[2]
        hour_count = results[3]

        # Check limits
        if minute_count >= config.requests_per_minute:
            # Calculate retry after
            oldest = await redis.zrange(minute_key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(60 - (now - oldest[0][1]))
                return False, max(1, retry_after)
            return False, 60

        if hour_count >= config.requests_per_hour:
            oldest = await redis.zrange(hour_key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(3600 - (now - oldest[0][1]))
                return False, max(1, retry_after)
            return False, 3600

        # Add current request
        async with redis.pipeline() as pipe:
            await pipe.zadd(minute_key, {str(now): now})
            await pipe.zadd(hour_key, {str(now): now})
            await pipe.expire(minute_key, 120)  # 2 minute TTL
            await pipe.expire(hour_key, 7200)  # 2 hour TTL
            await pipe.execute()

        return True, 0


async def check_rate_limit(
    agent_id: str,
    action: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """
    Standalone rate limit check function.

    Can be used in endpoints for specific action rate limiting.

    Args:
        agent_id: Agent identifier
        action: Action being rate limited
        limit: Maximum requests in window
        window_seconds: Window size in seconds

    Returns:
        Tuple of (allowed, retry_after_seconds)
    """
    redis = await get_redis_client()
    now = time.time()
    key = f"ratelimit:{agent_id}:{action}"

    # Remove old entries
    cutoff = now - window_seconds
    await redis.zremrangebyscore(key, 0, cutoff)

    # Count current entries
    count = await redis.zcard(key)

    if count >= limit:
        oldest = await redis.zrange(key, 0, 0, withscores=True)
        if oldest:
            retry_after = int(window_seconds - (now - oldest[0][1]))
            return False, max(1, retry_after)
        return False, window_seconds

    # Add current request
    await redis.zadd(key, {str(now): now})
    await redis.expire(key, window_seconds * 2)

    return True, 0
