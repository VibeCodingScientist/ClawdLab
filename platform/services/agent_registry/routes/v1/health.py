"""Health check endpoints."""

from fastapi import APIRouter, status
from pydantic import BaseModel

from platform.infrastructure.database.session import get_db_session
from platform.shared.clients.redis_client import health_check as redis_health
from platform.shared.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str
    checks: dict[str, bool]


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    ready: bool
    checks: dict[str, bool]


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns basic service health status.
    """
    from platform.services.agent_registry.config import get_settings

    settings = get_settings()

    return HealthResponse(
        status="healthy",
        service=settings.service_name,
        version=settings.service_version,
        checks={"alive": True},
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        503: {"description": "Service not ready"},
    },
)
async def readiness_check():
    """
    Readiness check endpoint.

    Verifies all dependencies are available.
    """
    checks = {}

    # Check database
    try:
        async with get_db_session() as session:
            await session.execute("SELECT 1")
        checks["database"] = True
    except Exception as e:
        logger.error("database_check_failed", error=str(e))
        checks["database"] = False

    # Check Redis
    checks["redis"] = await redis_health()

    # Determine overall readiness
    all_ready = all(checks.values())

    if not all_ready:
        from fastapi import Response

        return Response(
            content=ReadinessResponse(ready=False, checks=checks).model_dump_json(),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json",
        )

    return ReadinessResponse(ready=True, checks=checks)


@router.get("/live")
async def liveness_check():
    """
    Liveness check endpoint.

    Simple check that the service is running.
    """
    return {"alive": True}
