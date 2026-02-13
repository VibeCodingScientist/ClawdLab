"""Monitoring and health check endpoints."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from backend.database import get_db_session
from backend.logging_config import get_logger
from backend.redis import get_redis
from backend.schemas import HealthCheckResponse, SystemStatusResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/health/status", response_model=SystemStatusResponse)
async def health_status():
    """Check DB + Redis health, return overall status with latency."""
    checks: dict[str, HealthCheckResponse] = {}

    # Check database with latency
    db_start = time.monotonic()
    try:
        async with get_db_session() as db:
            await db.execute(text("SELECT 1"))
        db_ms = (time.monotonic() - db_start) * 1000
        checks["database"] = HealthCheckResponse(status="healthy", latencyMs=round(db_ms, 1))
    except Exception as e:
        logger.error("health_check_db_failed", error=str(e))
        db_ms = (time.monotonic() - db_start) * 1000
        checks["database"] = HealthCheckResponse(status="unhealthy", latencyMs=round(db_ms, 1))

    # Check Redis with latency
    redis_start = time.monotonic()
    try:
        redis = get_redis()
        await redis.ping()
        redis_ms = (time.monotonic() - redis_start) * 1000
        checks["redis"] = HealthCheckResponse(status="healthy", latencyMs=round(redis_ms, 1))
    except Exception as e:
        logger.error("health_check_redis_failed", error=str(e))
        redis_ms = (time.monotonic() - redis_start) * 1000
        checks["redis"] = HealthCheckResponse(status="unhealthy", latencyMs=round(redis_ms, 1))

    # Overall status
    statuses = [c.status for c in checks.values()]
    if all(s == "unhealthy" for s in statuses):
        overall = "unhealthy"
    elif any(s == "unhealthy" for s in statuses):
        overall = "degraded"
    else:
        overall = "healthy"

    return SystemStatusResponse(
        status=overall,
        checks=checks,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
