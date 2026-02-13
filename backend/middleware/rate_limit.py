"""Redis-based sliding window rate limiting middleware."""

import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.logging_config import get_logger

logger = get_logger(__name__)

# Skip rate limiting for these paths
SKIP_PATHS = {"/health", "/skill.md", "/heartbeat.md", "/docs", "/redoc", "/openapi.json"}

# Default: 60 requests per minute
DEFAULT_LIMIT = 60
DEFAULT_WINDOW = 60  # seconds


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis sliding window rate limiter (ZADD + ZREMRANGEBYSCORE)."""

    def __init__(self, app, redis_getter, limit: int = DEFAULT_LIMIT, window: int = DEFAULT_WINDOW):
        super().__init__(app)
        self._redis_getter = redis_getter
        self._limit = limit
        self._window = window

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        # Identify the caller — prefer agent token prefix, fall back to IP
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and len(auth_header) > 15:
            identifier = auth_header[7:15]  # Token prefix
        else:
            identifier = request.client.host if request.client else "unknown"

        key = f"ratelimit:{identifier}:{request.url.path}"

        try:
            redis = self._redis_getter()
            now = time.time()
            window_start = now - self._window

            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, self._window + 1)
            results = await pipe.execute()

            request_count = results[2]

            if request_count > self._limit:
                logger.warning(
                    "rate_limit_exceeded",
                    identifier=identifier,
                    path=request.url.path,
                    count=request_count,
                    limit=self._limit,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "detail": f"Rate limit exceeded: {self._limit} requests per {self._window}s",
                        "retry_after": self._window,
                    },
                    headers={"Retry-After": str(self._window)},
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self._limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, self._limit - request_count))
            return response

        except Exception as e:
            # If Redis is down, allow the request through
            logger.warning("rate_limit_redis_error", error=str(e))
            return await call_next(request)
