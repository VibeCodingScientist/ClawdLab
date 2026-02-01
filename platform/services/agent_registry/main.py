"""Agent Registry Service - FastAPI Application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from platform.infrastructure.database.session import close_db, init_db
from platform.services.agent_registry.config import get_settings
from platform.services.agent_registry.routes.v1 import agents, health, tokens
from platform.shared.clients.redis_client import close_redis_client, get_redis_client
from platform.shared.utils.logging import configure_logging, get_logger

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    configure_logging(
        level=settings.log_level,
        json_format=settings.log_json,
        service_name=settings.service_name,
    )
    logger.info(
        "service_starting",
        service=settings.service_name,
        version=settings.service_version,
    )

    # Initialize connections
    await init_db()
    await get_redis_client()
    logger.info("connections_initialized")

    yield

    # Shutdown
    logger.info("service_stopping")
    await close_db()
    await close_redis_client()
    logger.info("connections_closed")


# Create FastAPI app
app = FastAPI(
    title="Agent Registry Service",
    description="Manages agent identity, registration, and authentication for the Autonomous Scientific Research Platform",
    version=settings.service_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(agents.router, prefix="/v1/agents", tags=["Agents"])
app.include_router(tokens.router, prefix="/v1/agents", tags=["Tokens"])


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
