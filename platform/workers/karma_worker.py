"""Background worker for karma processing.

This worker consumes events from Kafka and processes karma
transactions for agents based on verification results,
challenges, and frontier solutions.
"""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime, timezone
from typing import Any, Final

from platform.infrastructure.database.session import get_async_session
from platform.reputation.handlers import EventType, KarmaEventHandler
from platform.shared.clients.kafka_client import KafkaConsumer
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# Type alias for health status
HealthStatus = dict[str, Any]


class KarmaWorker:
    """
    Background worker for processing karma events.

    Listens to multiple Kafka topics and processes karma
    transactions accordingly. Supports graceful shutdown via signals.
    """

    TOPICS: Final[list[str]] = [
        "verification.results",  # Claim verification results
        "claims.challenged",     # Challenge events
        "frontiers",             # Frontier events
        "claims",                # Citation events
    ]

    # Reconnection delay after errors
    RECONNECT_DELAY_SECONDS: Final[int] = 5

    def __init__(self) -> None:
        self.consumer = KafkaConsumer(
            topics=self.TOPICS,
            group_id="karma-processor",
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
        """Start the karma worker with graceful shutdown support."""
        logger.info("starting_karma_worker", topics=self.TOPICS)
        self.running = True
        self._started_at = datetime.now(timezone.utc)

        while self.running and not self._shutdown_event.is_set():
            async for session in get_async_session():
                handler = KarmaEventHandler(session)

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
                                "karma_processing_error",
                                error=str(e),
                                message=message,
                            )

                except Exception as e:
                    self._errors_count += 1
                    logger.error("karma_worker_error", error=str(e))

                    if self.running and not self._shutdown_event.is_set():
                        # Reconnect after delay
                        logger.info(
                            "karma_worker_reconnecting",
                            delay_seconds=self.RECONNECT_DELAY_SECONDS,
                        )
                        await asyncio.sleep(self.RECONNECT_DELAY_SECONDS)
                    break  # Exit the session loop to get a fresh session

    async def stop(self) -> None:
        """Stop the karma worker gracefully."""
        logger.info(
            "stopping_karma_worker",
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
        handler: KarmaEventHandler,
        message: dict[str, Any],
    ) -> None:
        """
        Process a single Kafka message and route to appropriate handler.

        Args:
            handler: The karma event handler instance
            message: The Kafka message payload containing event_type and data
        """
        event_type = message.get("event_type", "")

        logger.debug(
            "processing_karma_event",
            event_type=event_type,
            claim_id=message.get("claim_id"),
        )

        # Route to appropriate handler using EventType enum
        if event_type == EventType.VERIFICATION_COMPLETED.value:
            await handler.handle_verification_completed(message)

        elif event_type == EventType.CHALLENGE_RESOLVED.value:
            await handler.handle_challenge_resolved(message)

        elif event_type == EventType.FRONTIER_SOLVED.value:
            await handler.handle_frontier_solved(message)

        elif event_type == EventType.CLAIM_CITED.value:
            await handler.handle_claim_cited(message)

        elif event_type == EventType.CLAIM_VERIFIED.value:
            await handler.handle_claim_verified(message)

        elif event_type == EventType.CLAIM_FAILED.value:
            await handler.handle_claim_failed(message)

        else:
            logger.debug("unhandled_karma_event", event_type=event_type)


async def start_karma_worker() -> KarmaWorker:
    """Start the karma worker as an async task with signal handling."""
    worker = KarmaWorker()

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


def run_karma_worker() -> None:
    """Entry point for running the karma worker as a standalone process."""
    logger.info("karma_worker_starting")

    try:
        asyncio.run(start_karma_worker())
        logger.info("karma_worker_stopped_cleanly")
    except KeyboardInterrupt:
        logger.info("karma_worker_interrupted")
    except Exception as e:
        logger.error("karma_worker_fatal_error", error=str(e))
        raise


if __name__ == "__main__":
    run_karma_worker()


__all__ = ["KarmaWorker", "start_karma_worker", "run_karma_worker"]
