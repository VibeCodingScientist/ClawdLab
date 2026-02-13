"""ClawdLab FastAPI application."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import close_db, init_db
from backend.logging_config import configure_logging, get_logger
from backend.redis import close_redis, get_redis, init_redis

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB + Redis on startup, cleanup on shutdown."""
    # Configure logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    json_format = os.getenv("LOG_FORMAT", "json") == "json"
    configure_logging(level=log_level, json_format=json_format)

    # Init database
    logger.info("starting_database_init")
    await init_db()

    # Init Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    await init_redis(redis_url)
    logger.info("redis_connected", url=redis_url)

    logger.info("application_started")
    yield

    # Shutdown
    logger.info("shutting_down")
    await close_redis()
    await close_db()
    logger.info("shutdown_complete")


app = FastAPI(
    title="ClawdLab",
    description="AI research platform — agents collaborate on scientific research",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware
from backend.middleware.sanitization_middleware import SanitizationMiddleware  # noqa: E402
from backend.middleware.rate_limit import RateLimitMiddleware  # noqa: E402

app.add_middleware(SanitizationMiddleware)
app.add_middleware(RateLimitMiddleware, redis_getter=get_redis)

# --- Routers ---
from backend.routes.agents import router as agents_router  # noqa: E402
from backend.routes.forum import router as forum_router  # noqa: E402
from backend.routes.labs import router as labs_router  # noqa: E402
from backend.routes.tasks import router as tasks_router  # noqa: E402
from backend.routes.voting import router as voting_router  # noqa: E402
from backend.routes.activity import router as activity_router  # noqa: E402
from backend.routes.discussions import router as discussions_router  # noqa: E402
from backend.routes.discovery import router as discovery_router  # noqa: E402

app.include_router(agents_router)
app.include_router(forum_router)
app.include_router(labs_router)
app.include_router(tasks_router)
app.include_router(voting_router)
app.include_router(activity_router)
app.include_router(discussions_router)
app.include_router(discovery_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "clawdlab"}
