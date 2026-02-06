"""Combined worker runner for all background workers.

This script starts all background workers concurrently:
- Karma worker: Processes karma transactions from events
- Verification worker: Dispatches claims to verifiers
- Verification result worker: Processes verification results

Usage:
    python -m platform.workers.run_workers
    python -m platform.workers.run_workers --workers karma verification
"""

import argparse
import asyncio
import signal
from typing import Any

from platform.workers.karma_worker import KarmaWorker
from platform.workers.verification_worker import (
    VerificationWorker,
    VerificationResultWorker,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class WorkerManager:
    """
    Manages multiple background workers.

    Handles startup, shutdown, and graceful termination.
    """

    def __init__(self):
        self.workers: list[Any] = []
        self.tasks: list[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()

    def add_worker(self, worker: Any) -> None:
        """Add a worker to manage."""
        self.workers.append(worker)

    async def start_all(self) -> None:
        """Start all workers concurrently."""
        logger.info("starting_worker_manager", worker_count=len(self.workers))

        # Create tasks for each worker
        self.tasks = [
            asyncio.create_task(worker.start())
            for worker in self.workers
        ]

        # Wait for shutdown signal
        await self.shutdown_event.wait()

        # Stop all workers
        await self.stop_all()

    async def stop_all(self) -> None:
        """Stop all workers gracefully."""
        logger.info("stopping_all_workers")

        # Signal workers to stop
        for worker in self.workers:
            await worker.stop()

        # Cancel remaining tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("all_workers_stopped")

    def shutdown(self) -> None:
        """Trigger shutdown."""
        self.shutdown_event.set()


def setup_signal_handlers(manager: WorkerManager) -> None:
    """Set up signal handlers for graceful shutdown."""
    loop = asyncio.get_event_loop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, manager.shutdown)


async def run_workers(worker_types: list[str] | None = None) -> None:
    """Run specified workers or all workers."""
    manager = WorkerManager()

    # Determine which workers to run
    if worker_types is None or "all" in worker_types:
        worker_types = ["karma", "verification", "verification_result"]

    # Create and add workers
    if "karma" in worker_types:
        manager.add_worker(KarmaWorker())
        logger.info("added_karma_worker")

    if "verification" in worker_types:
        manager.add_worker(VerificationWorker())
        logger.info("added_verification_worker")

    if "verification_result" in worker_types:
        manager.add_worker(VerificationResultWorker())
        logger.info("added_verification_result_worker")

    if not manager.workers:
        logger.error("no_workers_configured")
        return

    # Set up signal handlers
    setup_signal_handlers(manager)

    # Start all workers
    try:
        await manager.start_all()
    except Exception as e:
        logger.error("worker_manager_error", error=str(e))
        await manager.stop_all()
        raise


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run platform background workers")
    parser.add_argument(
        "--workers",
        nargs="+",
        choices=["all", "karma", "verification", "verification_result"],
        default=["all"],
        help="Workers to run (default: all)",
    )
    args = parser.parse_args()

    logger.info("platform_workers_starting", workers=args.workers)

    try:
        asyncio.run(run_workers(args.workers))
    except KeyboardInterrupt:
        logger.info("platform_workers_interrupted")
    except Exception as e:
        logger.error("platform_workers_fatal_error", error=str(e))
        raise


if __name__ == "__main__":
    main()
