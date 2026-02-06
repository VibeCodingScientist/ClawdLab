"""Database session management with async support."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

# Global engine and session factory
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    """Get database URL from environment."""
    url = os.getenv("DATABASE_URL", "postgresql://asrp:asrp_dev_password@localhost:5432/asrp")
    # Convert postgres:// to postgresql+asyncpg:// for async support
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def get_engine() -> AsyncEngine:
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_database_url(),
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
            pool_size=int(os.getenv("DATABASE_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "20")),
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        logger.info("database_engine_created", pool_size=10, max_overflow=20)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        logger.info("session_factory_created")
    return _session_factory


async def init_db() -> None:
    """Initialize database connection and verify connectivity."""
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        logger.info("database_connection_verified")
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        raise


async def close_db() -> None:
    """Close database connections."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database_connections_closed")


class DatabaseSession:
    """
    Context manager for database sessions.

    Usage:
        async with DatabaseSession() as session:
            result = await session.execute(query)
    """

    def __init__(self) -> None:
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        factory = get_session_factory()
        self._session = factory()
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session is not None:
            if exc_type is not None:
                await self._session.rollback()
            await self._session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.

    Usage:
        async with get_db_session() as session:
            result = await session.execute(query)
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with get_db_session() as session:
        yield session


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async generator for database sessions in background workers.

    Unlike get_db(), this is designed for long-running processes
    that need to continuously acquire and release sessions.

    Usage:
        async for session in get_async_session():
            # Process with session
            # Session is automatically closed after each iteration
    """
    while True:
        async with get_db_session() as session:
            yield session
