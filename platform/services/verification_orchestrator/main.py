"""Verification Orchestrator Service - FastAPI Application."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from platform.infrastructure.database.session import close_db, init_db
from platform.services.verification_orchestrator.config import get_settings
from platform.services.verification_orchestrator.routes.v1 import health, verification
from platform.shared.clients.redis_client import close_redis_client, get_redis_client
from platform.shared.utils.logging import configure_logging, get_logger

settings = get_settings()
logger = get_logger(__name__)

# Background task for event consumer
consumer_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global consumer_task

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

    # Start event consumer in background
    # Note: In production, this would be a separate process
    # consumer_task = asyncio.create_task(start_event_consumer())

    yield

    # Shutdown
    logger.info("service_stopping")

    # Cancel consumer task
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass

    await close_db()
    await close_redis_client()
    logger.info("connections_closed")


# Create FastAPI app
app = FastAPI(
    title="Verification Orchestrator Service",
    description="""
    Orchestrates verification of research claims across domain-specific engines.

    ## Overview

    The Verification Orchestrator is responsible for:

    - **Dispatching**: Routing claims to appropriate domain verifiers
    - **Tracking**: Monitoring verification progress and status
    - **Results**: Collecting and publishing verification results
    - **Retries**: Handling failed verifications with retry logic

    ## Verification Domains

    - **Mathematics**: Lean 4, Coq, Z3/CVC5 proof verification
    - **ML/AI**: Code reproducibility, benchmark verification
    - **Computational Biology**: Protein design, structure prediction
    - **Materials Science**: Crystal structure, property prediction
    - **Bioinformatics**: Pipeline execution, statistical validation

    ## Architecture

    ```
    Claim Event -> Orchestrator -> Celery Queue -> Domain Verifier -> Result
    ```

    Each domain has dedicated Celery workers with appropriate resources
    (GPU for ML, high memory for compbio, etc.)
    """,
    version=settings.service_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(verification.router, prefix="/v1/verification", tags=["Verification"])


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "running",
        "domains": [
            "mathematics",
            "ml_ai",
            "computational_biology",
            "materials_science",
            "bioinformatics",
        ],
    }


async def start_event_consumer():
    """Start the Kafka event consumer."""
    from platform.infrastructure.database.session import get_db_session
    from platform.services.verification_orchestrator.orchestrator import ClaimEventConsumer

    async with get_db_session() as session:
        consumer = ClaimEventConsumer(session)
        await consumer.start()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
