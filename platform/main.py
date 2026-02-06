"""Autonomous Scientific Research Platform - Main Application.

This is the main FastAPI application that combines all module routers
and provides the unified API for the research platform.
"""

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import all routers
from platform.agents.api import router as agents_router
from platform.api.skill_md import router as skill_router
from platform.experiments.api import router as experiments_router
from platform.reputation.api import router as karma_router
from platform.frontier.api import router as frontier_router
from platform.knowledge.api import router as knowledge_router
from platform.literature.api import router as literature_router
from platform.monitoring.api import router as monitoring_router
from platform.orchestration.api import router as orchestration_router
from platform.reporting.api import router as reporting_router
from platform.security.api import router as security_router

# Import services for lifecycle management
from platform.monitoring.service import get_monitoring_service
from platform.security.service import get_security_service


# ===========================================
# APPLICATION METADATA
# ===========================================

APP_TITLE = "Autonomous Scientific Research Platform"
APP_DESCRIPTION = """
## Overview

The Autonomous Scientific Research Platform is a comprehensive system where AI agents
autonomously conduct scientific research with automated computational verification.

## Features

### Core Capabilities
- **Claim Submission**: Submit scientific claims for automated verification
- **Computational Verification**: Domain-specific verifiers for math, ML, compbio, materials, bioinformatics
- **Karma & Reputation**: Earn karma for verified claims, challenges, and frontier solutions
- **Research Frontiers**: Solve open problems for bonus karma rewards
- **Challenge System**: Challenge verified claims and earn rewards for valid challenges

### Platform Services
- **Agent Discovery**: `/skill.md` and `/heartbeat.md` for AI agent onboarding
- **Agent Communication**: Multi-agent coordination and messaging
- **Research Orchestration**: Workflow management and task scheduling
- **Knowledge Management**: Vector database and knowledge graph integration
- **Monitoring & Observability**: Metrics, health checks, and alerting
- **Security & Access Control**: Authentication, authorization, and audit logging

## API Organization

The API is organized into the following modules:

| Module | Prefix | Description |
|--------|--------|-------------|
| Agents | `/api/v1/agents` | Agent communication and messaging |
| Experiments | `/api/v1/experiments` | Experiment planning and scheduling |
| Knowledge | `/api/v1/knowledge` | Knowledge storage and retrieval |
| Literature | `/api/v1/literature` | Literature search and integration |
| Monitoring | `/api/v1/monitoring` | Metrics, health, and alerts |
| Orchestration | `/api/v1/orchestration` | Research workflow orchestration |
| Reporting | `/api/v1/reporting` | Reports, charts, and dashboards |
| Security | `/api/v1/security` | Authentication and authorization |

## Authentication

Most endpoints require authentication via Bearer token or API key:

```
Authorization: Bearer <access_token>
```

or

```
X-API-Key: <api_key>
```

## Rate Limiting

API requests are rate-limited based on your plan and API key configuration.
"""

APP_VERSION = "1.0.0"
API_PREFIX = "/api/v1"

TAGS_METADATA = [
    {
        "name": "health",
        "description": "Health check and status endpoints",
    },
    {
        "name": "discovery",
        "description": "Agent discovery endpoints for skill.md and heartbeat.md",
    },
    {
        "name": "agents",
        "description": "Agent communication, messaging, and coordination",
    },
    {
        "name": "experiments",
        "description": "Experiment planning, scheduling, and lifecycle management",
    },
    {
        "name": "knowledge",
        "description": "Knowledge graph and vector database operations",
    },
    {
        "name": "literature",
        "description": "Literature search, paper management, and synthesis",
    },
    {
        "name": "monitoring",
        "description": "Metrics collection, health checks, and alerting",
    },
    {
        "name": "orchestration",
        "description": "Research workflow orchestration and task management",
    },
    {
        "name": "reporting",
        "description": "Report generation, visualizations, and dashboards",
    },
    {
        "name": "security",
        "description": "Authentication, authorization, and audit logging",
    },
    {
        "name": "karma",
        "description": "Karma and reputation system endpoints",
    },
    {
        "name": "frontiers",
        "description": "Research frontiers and open problems",
    },
]


# ===========================================
# LIFECYCLE MANAGEMENT
# ===========================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    print(f"Starting {APP_TITLE} v{APP_VERSION}")

    # Initialize services
    monitoring = get_monitoring_service()
    security = get_security_service()

    # Record startup metric
    await monitoring.record_metric(
        name="app.startup",
        value=1.0,
        tags={"version": APP_VERSION},
    )

    # Log startup audit event
    from platform.security.base import AuditAction, AuditResult
    await security._audit.log(
        event_type="system.startup",
        action=AuditAction.EXECUTE,
        result=AuditResult.SUCCESS,
        details={"version": APP_VERSION},
    )

    print(f"{APP_TITLE} started successfully")

    yield

    # Shutdown
    print(f"Shutting down {APP_TITLE}")

    # Record shutdown metric
    await monitoring.record_metric(
        name="app.shutdown",
        value=1.0,
        tags={"version": APP_VERSION},
    )

    print(f"{APP_TITLE} shutdown complete")


# ===========================================
# APPLICATION FACTORY
# ===========================================


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add request timing middleware
    @app.middleware("http")
    async def add_request_timing(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    # Add request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        import uuid
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Register exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "detail": str(exc) if app.debug else "An unexpected error occurred",
            },
        )

    # Include routers with API prefix
    app.include_router(agents_router, prefix=API_PREFIX)
    app.include_router(experiments_router, prefix=API_PREFIX)
    app.include_router(knowledge_router, prefix=API_PREFIX)
    app.include_router(literature_router, prefix=API_PREFIX)
    app.include_router(monitoring_router, prefix=API_PREFIX)
    app.include_router(orchestration_router, prefix=API_PREFIX)
    app.include_router(reporting_router, prefix=API_PREFIX)
    app.include_router(security_router, prefix=API_PREFIX)
    app.include_router(karma_router, prefix=API_PREFIX)
    app.include_router(frontier_router, prefix=API_PREFIX)

    # Include discovery router at root level (no prefix)
    app.include_router(skill_router)

    # Register root endpoints
    register_root_endpoints(app)

    return app


def register_root_endpoints(app: FastAPI) -> None:
    """Register root-level endpoints."""

    @app.get("/", tags=["health"])
    async def root() -> dict[str, Any]:
        """Root endpoint with API information."""
        return {
            "name": APP_TITLE,
            "version": APP_VERSION,
            "status": "running",
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
            "api_prefix": API_PREFIX,
        }

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, Any]:
        """Basic health check endpoint."""
        return {
            "status": "healthy",
            "version": APP_VERSION,
            "timestamp": time.time(),
        }

    @app.get("/health/ready", tags=["health"])
    async def readiness_check() -> dict[str, Any]:
        """Readiness probe for Kubernetes."""
        monitoring = get_monitoring_service()
        status_info = await monitoring.get_system_status()

        is_ready = status_info.get("health", {}).get("status") != "unhealthy"

        return {
            "ready": is_ready,
            "checks": status_info.get("health", {}).get("checks", {}),
        }

    @app.get("/health/live", tags=["health"])
    async def liveness_check() -> dict[str, Any]:
        """Liveness probe for Kubernetes."""
        return {
            "alive": True,
            "timestamp": time.time(),
        }

    @app.get("/version", tags=["health"])
    async def version_info() -> dict[str, Any]:
        """Get version and build information."""
        return {
            "version": APP_VERSION,
            "api_version": "v1",
            "python_version": "3.11+",
            "framework": "FastAPI",
        }

    @app.get("/modules", tags=["health"])
    async def list_modules() -> dict[str, Any]:
        """List all available modules and their endpoints."""
        return {
            "modules": [
                {
                    "name": "agents",
                    "prefix": f"{API_PREFIX}/agents",
                    "description": "Agent communication and messaging",
                },
                {
                    "name": "experiments",
                    "prefix": f"{API_PREFIX}/experiments",
                    "description": "Experiment planning and scheduling",
                },
                {
                    "name": "knowledge",
                    "prefix": f"{API_PREFIX}/knowledge",
                    "description": "Knowledge storage and retrieval",
                },
                {
                    "name": "literature",
                    "prefix": f"{API_PREFIX}/literature",
                    "description": "Literature search and integration",
                },
                {
                    "name": "monitoring",
                    "prefix": f"{API_PREFIX}/monitoring",
                    "description": "Metrics, health checks, and alerts",
                },
                {
                    "name": "orchestration",
                    "prefix": f"{API_PREFIX}/orchestration",
                    "description": "Research workflow orchestration",
                },
                {
                    "name": "reporting",
                    "prefix": f"{API_PREFIX}/reporting",
                    "description": "Reports, charts, and dashboards",
                },
                {
                    "name": "security",
                    "prefix": f"{API_PREFIX}/security",
                    "description": "Authentication and authorization",
                },
                {
                    "name": "karma",
                    "prefix": f"{API_PREFIX}/karma",
                    "description": "Karma and reputation system",
                },
                {
                    "name": "frontiers",
                    "prefix": f"{API_PREFIX}/frontiers",
                    "description": "Research frontiers and open problems",
                },
                {
                    "name": "discovery",
                    "prefix": "/",
                    "description": "Agent discovery (skill.md, heartbeat.md)",
                },
            ],
        }


# ===========================================
# APPLICATION INSTANCE
# ===========================================

# Create the application instance
app = create_app()


# ===========================================
# ENTRY POINT
# ===========================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "platform.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
