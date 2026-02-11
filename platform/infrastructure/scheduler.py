"""In-process periodic task scheduler.

Replaces Celery Beat. Runs async tasks on configurable intervals
inside the FastAPI event loop.
"""

import asyncio
from typing import Any, Callable, Coroutine

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class PeriodicScheduler:
    """Lightweight periodic task scheduler using asyncio."""

    def __init__(self) -> None:
        self._tasks: list[tuple[str, float, Callable[[], Coroutine[Any, Any, Any]]]] = []
        self._running = False
        self._handles: list[asyncio.Task[None]] = []

    def register(self, name: str, interval_seconds: float, func: Callable[[], Coroutine[Any, Any, Any]]) -> None:
        """Register a periodic task.

        Args:
            name: Human-readable task name (for logging).
            interval_seconds: Seconds between invocations.
            func: Async callable to run periodically.
        """
        self._tasks.append((name, interval_seconds, func))

    async def start(self) -> None:
        """Start all registered periodic tasks."""
        self._running = True
        for name, interval, func in self._tasks:
            handle = asyncio.create_task(self._run_periodic(name, interval, func))
            self._handles.append(handle)
        logger.info("scheduler_started", task_count=len(self._tasks))

    async def stop(self) -> None:
        """Stop all periodic tasks."""
        self._running = False
        for handle in self._handles:
            handle.cancel()
        self._handles.clear()
        logger.info("scheduler_stopped")

    async def _run_periodic(self, name: str, interval: float, func: Callable[[], Coroutine[Any, Any, Any]]) -> None:
        """Run a single task on a loop with the given interval."""
        while self._running:
            try:
                await func()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("periodic_task_error", task=name, error=str(e))
            await asyncio.sleep(interval)
