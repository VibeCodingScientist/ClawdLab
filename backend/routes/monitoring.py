"""Monitoring and health check endpoints."""

import time

from fastapi import APIRouter
from sqlalchemy import text

from backend.database import get_db_session
from backend.logging_config import get_logger
from backend.redis import get_redis
from backend.schemas import SystemStatusResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

_start_time = time.time()


@router.get("/health/status", response_model=SystemStatusResponse)
async def health_status():
    """Check DB + Redis health, return overall status."""
    db_status = "healthy"
    redis_status = "healthy"

    # Check database
    try:
        async with get_db_session() as db:
            await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("health_check_db_failed", error=str(e))
        db_status = "unhealthy"

    # Check Redis
    try:
        redis = get_redis()
        await redis.ping()
    except Exception as e:
        logger.error("health_check_redis_failed", error=str(e))
        redis_status = "unhealthy"

    # Overall status
    if db_status == "unhealthy" and redis_status == "unhealthy":
        overall = "unhealthy"
    elif db_status == "unhealthy" or redis_status == "unhealthy":
        overall = "degraded"
    else:
        overall = "healthy"

    uptime = time.time() - _start_time

    return SystemStatusResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        uptime_seconds=uptime,
    )
