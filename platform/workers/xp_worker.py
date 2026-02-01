"""Background worker for XP event processing.

This worker consumes events from Kafka and processes XP
awards for agents based on verification results, claims,
frontiers, roundtable activity, and challenges.
"""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime, timezone
from typing import Any, Final

from platform.infrastructure.database.session import get_async_session
from platform.experience.handlers import XPEventHandler
from platform.shared.clients.kafka_client import KafkaConsumer
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# Type alias for health status
HealthStatus = dict[str, Any]


class XPWorker:
    """
    Background worker for processing XP events.

    Listens to multiple Kafka topics and awards XP
    to agents accordingly. Supports graceful shutdown via signals.
    """

    TOPICS: Final[list[str]] = [
        "verification.results",       # Claim verification results
        "claims",                      # Claim events (verified, cited)
        "frontiers",                   # Frontier events
        "roundtable.proposals",        # Proposal approved events
        "roundtable.reviews",          # Review accepted events
        "challenges",                  # Challenge resolved events
    ]

    # Reconnection delay after errors
    RECONNECT_DELAY_SECONDS: Final[int] = 5

    def __init__(self) -> None:
        self.consumer = KafkaConsumer(
            topics=self.TOPICS,
            group_id="xp-processor",
        )
        self.running = False
        self._shutdown_event = asyncio.Event()
        self._messages_processed = 0
        self._errors_count = 0
        self._started_at: datetime | None = None

    def get_health_status(self) -> dict[str, Any]:
        """Return health status for monitoring."""
        return {
            "healthy": self.running,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "messages_processed": self._messages_processed,
            "errors_count": self._errors_count,
            "topics": self.TOPICS,
        }

    async def start(self) -> None:
        """Start the XP worker with graceful shutdown support."""
        logger.info("starting_xp_worker", topics=self.TOPICS)
        self.running = True
        self._started_at = datetime.now(timezone.utc)

        while self.running and not self._shutdown_event.is_set():
            async for session in get_async_session():
                handler = XPEventHandler(session)

                try:
                    async for message in self.consumer.consume():
                        if not self.running or self._shutdown_event.is_set():
                            break

                        try:
                            await self._process_message(handler, message)
                            self._messages_processed += 1
                        except Exception as e:
                            self._errors_count += 1
                            logger.exception(
                                "xp_processing_error",
                                error=str(e),
                                message=message,
                            )

                except Exception as e:
                    self._errors_count += 1
                    logger.error("xp_worker_error", error=str(e))

                    if self.running and not self._shutdown_event.is_set():
                        # Reconnect after delay
                        logger.info(
                            "xp_worker_reconnecting",
                            delay_seconds=self.RECONNECT_DELAY_SECONDS,
                        )
                        await asyncio.sleep(self.RECONNECT_DELAY_SECONDS)
                    break  # Exit the session loop to get a fresh session

    async def stop(self) -> None:
        """Stop the XP worker gracefully."""
        logger.info(
            "stopping_xp_worker",
            messages_processed=self._messages_processed,
            errors_count=self._errors_count,
        )
        self.running = False
        self._shutdown_event.set()
        await self.consumer.close()

    def request_shutdown(self) -> None:
        """Signal the worker to shut down (called from signal handlers)."""
        self._shutdown_event.set()

    async def _process_message(
        self,
        handler: XPEventHandler,
        message: dict[str, Any],
    ) -> None:
        """
        Process a single Kafka message and route to the XP event handler.

        Args:
            handler: The XP event handler instance
            message: The Kafka message payload containing event_type and data
        """
        event_type = message.get("event_type", "")
        data = message.get("data", message)

        logger.debug(
            "processing_xp_event",
            event_type=event_type,
            agent_id=message.get("agent_id"),
        )

        # Route all events through the centralized handler
        await handler.handle_event(event_type, data)


async def start_xp_worker() -> XPWorker:
    """Start the XP worker as an async task with signal handling."""
    worker = XPWorker()

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    def handle_signal(sig: signal.Signals) -> None:
        logger.info("received_shutdown_signal", signal=sig.name)
        worker.request_shutdown()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        await worker.start()
    finally:
        await worker.stop()

    return worker


def run_xp_worker() -> None:
    """Entry point for running the XP worker as a standalone process."""
    logger.info("xp_worker_starting")

    try:
        asyncio.run(start_xp_worker())
        logger.info("xp_worker_stopped_cleanly")
    except KeyboardInterrupt:
        logger.info("xp_worker_interrupted")
    except Exception as e:
        logger.error("xp_worker_fatal_error", error=str(e))
        raise


if __name__ == "__main__":
    run_xp_worker()


__all__ = ["XPWorker", "start_xp_worker", "run_xp_worker"]
