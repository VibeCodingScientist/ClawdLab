"""Background worker for lab event processing.

This worker consumes events from Kafka lab topics and processes
notifications, index updates, and governance triggers.
"""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime, timezone
from typing import Any, Final

from platform.shared.clients.kafka_client import KafkaConsumer
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class LabWorker:
    """
    Background worker for processing lab events.

    Listens to lab-related Kafka topics and processes events
    for notifications, governance triggers, and index updates.
    """

    TOPICS: Final[list[str]] = [
        "labs.lifecycle",
        "labs.membership",
        "labs.roles",
        "labs.governance",
        "labs.research",
        "labs.roundtable",
    ]

    RECONNECT_DELAY_SECONDS: Final[int] = 5

    def __init__(self) -> None:
        self.consumer = KafkaConsumer(
            topics=self.TOPICS,
            group_id="lab-event-processor",
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
        """Start the lab worker with graceful shutdown support."""
        logger.info("starting_lab_worker", topics=self.TOPICS)
        self.running = True
        self._started_at = datetime.now(timezone.utc)

        while self.running and not self._shutdown_event.is_set():
            try:
                async for message in self.consumer.consume():
                    if not self.running or self._shutdown_event.is_set():
                        break

                    try:
                        await self._process_message(message)
                        self._messages_processed += 1
                    except Exception as e:
                        self._errors_count += 1
                        logger.exception(
                            "lab_event_processing_error",
                            error=str(e),
                        )

            except Exception as e:
                self._errors_count += 1
                logger.error("lab_worker_error", error=str(e))

                if self.running and not self._shutdown_event.is_set():
                    logger.info(
                        "lab_worker_reconnecting",
                        delay_seconds=self.RECONNECT_DELAY_SECONDS,
                    )
                    await asyncio.sleep(self.RECONNECT_DELAY_SECONDS)

    async def stop(self) -> None:
        """Stop the lab worker gracefully."""
        logger.info(
            "stopping_lab_worker",
            messages_processed=self._messages_processed,
            errors_count=self._errors_count,
        )
        self.running = False
        self._shutdown_event.set()
        await self.consumer.stop()

    def request_shutdown(self) -> None:
        """Signal the worker to shut down."""
        self._shutdown_event.set()

    async def _process_message(self, message: dict[str, Any]) -> None:
        """Process a single lab event message."""
        event_type = message.get("event_type", "")
        data = message.get("data", {})

        logger.debug(
            "processing_lab_event",
            event_type=event_type,
            lab_id=data.get("lab_id"),
        )

        if event_type == "lab.created":
            await self._handle_lab_created(data)
        elif event_type == "lab.archived":
            await self._handle_lab_archived(data)
        elif event_type == "member.joined":
            await self._handle_member_joined(data)
        elif event_type == "item.proposed":
            await self._handle_item_proposed(data)
        elif event_type == "entry.created":
            await self._handle_roundtable_entry(data)
        elif event_type == "roundtable.vote_called":
            await self._handle_vote_called(data)
        elif event_type == "roundtable.proposal_approved":
            await self._handle_proposal_approved(data)
        elif event_type == "roundtable.proposal_rejected":
            await self._handle_proposal_rejected(data)
        elif event_type == "roundtable.work_assigned":
            await self._handle_work_assigned(data)
        elif event_type == "roundtable.result_submitted":
            await self._handle_result_submitted(data)
        elif event_type == "roundtable.result_verified":
            await self._handle_result_verified(data)
        elif event_type == "roundtable.result_failed":
            await self._handle_result_failed(data)
        else:
            logger.debug("unhandled_lab_event", event_type=event_type)

    async def _handle_lab_created(self, data: dict[str, Any]) -> None:
        """Handle lab creation event."""
        logger.info(
            "lab_created_event",
            lab_id=data.get("lab_id"),
            slug=data.get("slug"),
            created_by=data.get("created_by"),
        )

    async def _handle_lab_archived(self, data: dict[str, Any]) -> None:
        """Handle lab archival event."""
        logger.info(
            "lab_archived_event",
            lab_id=data.get("lab_id"),
            slug=data.get("slug"),
        )

    async def _handle_member_joined(self, data: dict[str, Any]) -> None:
        """Handle member joined event."""
        logger.info(
            "member_joined_event",
            lab_id=data.get("lab_id"),
            agent_id=data.get("agent_id"),
        )

    async def _handle_item_proposed(self, data: dict[str, Any]) -> None:
        """Handle research item proposed event."""
        logger.info(
            "item_proposed_event",
            lab_id=data.get("lab_id"),
            item_id=data.get("item_id"),
        )

    async def _handle_roundtable_entry(self, data: dict[str, Any]) -> None:
        """Handle roundtable entry created event."""
        logger.info(
            "roundtable_entry_event",
            lab_id=data.get("lab_id"),
            item_id=data.get("item_id"),
            entry_type=data.get("entry_type"),
        )

    async def _handle_vote_called(self, data: dict[str, Any]) -> None:
        """Handle vote called event."""
        logger.info(
            "vote_called_event",
            lab_id=data.get("lab_id"),
            item_id=data.get("item_id"),
            reason=data.get("reason"),
        )

    async def _handle_proposal_approved(self, data: dict[str, Any]) -> None:
        """Handle proposal approved event."""
        logger.info(
            "proposal_approved_event",
            lab_id=data.get("lab_id"),
            item_id=data.get("item_id"),
            reason=data.get("reason"),
        )

    async def _handle_proposal_rejected(self, data: dict[str, Any]) -> None:
        """Handle proposal rejected event."""
        logger.info(
            "proposal_rejected_event",
            lab_id=data.get("lab_id"),
            item_id=data.get("item_id"),
            reason=data.get("reason"),
        )

    async def _handle_work_assigned(self, data: dict[str, Any]) -> None:
        """Handle work assigned event."""
        logger.info(
            "work_assigned_event",
            lab_id=data.get("lab_id"),
            item_id=data.get("item_id"),
            assigned_to=data.get("assigned_to"),
        )

    async def _handle_result_submitted(self, data: dict[str, Any]) -> None:
        """Handle result submitted event."""
        logger.info(
            "result_submitted_event",
            lab_id=data.get("lab_id"),
            item_id=data.get("item_id"),
            submitted_by=data.get("submitted_by"),
        )

    async def _handle_result_verified(self, data: dict[str, Any]) -> None:
        """Handle result verified event."""
        logger.info(
            "result_verified_event",
            lab_id=data.get("lab_id"),
            item_id=data.get("item_id"),
            claim_id=data.get("claim_id"),
        )

    async def _handle_result_failed(self, data: dict[str, Any]) -> None:
        """Handle result failed event."""
        logger.info(
            "result_failed_event",
            lab_id=data.get("lab_id"),
            item_id=data.get("item_id"),
            reason=data.get("reason"),
        )


async def start_lab_worker() -> LabWorker:
    """Start the lab worker as an async task with signal handling."""
    worker = LabWorker()

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


def run_lab_worker() -> None:
    """Entry point for running the lab worker as a standalone process."""
    logger.info("lab_worker_starting")

    try:
        asyncio.run(start_lab_worker())
        logger.info("lab_worker_stopped_cleanly")
    except KeyboardInterrupt:
        logger.info("lab_worker_interrupted")
    except Exception as e:
        logger.error("lab_worker_fatal_error", error=str(e))
        raise


if __name__ == "__main__":
    run_lab_worker()


__all__ = ["LabWorker", "start_lab_worker", "run_lab_worker"]
