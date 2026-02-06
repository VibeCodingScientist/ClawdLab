"""Background worker for verification orchestration.

This worker consumes claim submission events from Kafka
and dispatches them to the appropriate verification engines.
"""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime, timezone
from typing import Any, Final

from platform.infrastructure.database.session import get_async_session
from platform.services.verification_orchestrator.orchestrator import (
    ClaimEventConsumer,
    VerificationOrchestrator,
)
from platform.shared.clients.kafka_client import KafkaConsumer
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class VerificationWorker:
    """
    Background worker for verification orchestration.

    Listens to claim events and dispatches verification jobs
    to domain-specific verifiers via Celery.
    """

    TOPICS: Final[list[str]] = [
        "claims",  # Claim submitted/retracted events
    ]

    RECONNECT_DELAY_SECONDS: Final[int] = 5

    def __init__(self) -> None:
        self.consumer = KafkaConsumer(
            topics=self.TOPICS,
            group_id="verification-orchestrator",
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
        """Start the verification worker with graceful shutdown support."""
        logger.info("starting_verification_worker", topics=self.TOPICS)
        self.running = True
        self._started_at = datetime.now(timezone.utc)

        while self.running and not self._shutdown_event.is_set():
            async for session in get_async_session():
                orchestrator = VerificationOrchestrator(session)

                try:
                    async for message in self.consumer.consume():
                        if not self.running or self._shutdown_event.is_set():
                            break

                        try:
                            await self._process_message(orchestrator, session, message)
                            self._messages_processed += 1
                        except Exception as e:
                            self._errors_count += 1
                            logger.exception(
                                "verification_dispatch_error",
                                error=str(e),
                                message=message,
                            )

                except Exception as e:
                    self._errors_count += 1
                    logger.error("verification_worker_error", error=str(e))

                    if self.running and not self._shutdown_event.is_set():
                        logger.info(
                            "verification_worker_reconnecting",
                            delay_seconds=self.RECONNECT_DELAY_SECONDS,
                        )
                        await asyncio.sleep(self.RECONNECT_DELAY_SECONDS)
                    break

    async def stop(self) -> None:
        """Stop the verification worker gracefully."""
        logger.info(
            "stopping_verification_worker",
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
        orchestrator: VerificationOrchestrator,
        session,
        message: dict[str, Any],
    ) -> None:
        """Process a single Kafka message."""
        event_type = message.get("event_type", "")

        logger.debug(
            "processing_verification_event",
            event_type=event_type,
            claim_id=message.get("claim_id"),
        )

        if event_type == "claim.submitted":
            await self._handle_claim_submitted(orchestrator, session, message)

        elif event_type == "claim.retracted":
            await self._handle_claim_retracted(orchestrator, message)

        else:
            logger.debug("unhandled_verification_event", event_type=event_type)

    async def _handle_claim_submitted(
        self,
        orchestrator: VerificationOrchestrator,
        session,
        message: dict[str, Any],
    ) -> None:
        """Handle claim submission - dispatch verification."""
        claim_id = message.get("claim_id")
        domain = message.get("domain")
        claim_type = message.get("claim_type")

        if not all([claim_id, domain, claim_type]):
            logger.error("invalid_claim_submitted_event", message=message)
            return

        # Get full claim payload from database
        from platform.infrastructure.database.models import Claim
        from sqlalchemy import select

        result = await session.execute(
            select(Claim).where(Claim.id == claim_id)
        )
        claim = result.scalar_one_or_none()

        if not claim:
            logger.error("claim_not_found_for_verification", claim_id=claim_id)
            return

        # Dispatch verification
        job_id = await orchestrator.dispatch_verification(
            claim_id=claim_id,
            domain=domain,
            claim_type=claim_type,
            payload=claim.content,
        )

        logger.info(
            "verification_dispatched",
            claim_id=claim_id,
            job_id=job_id,
            domain=domain,
        )

    async def _handle_claim_retracted(
        self,
        orchestrator: VerificationOrchestrator,
        message: dict[str, Any],
    ) -> None:
        """Handle claim retraction - cancel pending verification."""
        claim_id = message.get("claim_id")

        if not claim_id:
            logger.error("invalid_claim_retracted_event", message=message)
            return

        # Get verification job
        link = await orchestrator.cache.get(f"claim_verification:{claim_id}")
        if link and link.get("status") in ("queued", "dispatched", "running"):
            job_id = link.get("job_id")
            if job_id:
                job_data = await orchestrator.cache.get(f"verification_job:{job_id}")
                if job_data and job_data.get("celery_task_id"):
                    try:
                        from platform.infrastructure.celery.app import celery_app
                        celery_app.control.revoke(job_data["celery_task_id"], terminate=True)

                        logger.info(
                            "verification_cancelled_on_retraction",
                            job_id=job_id,
                            claim_id=claim_id,
                        )
                    except Exception as e:
                        logger.error(
                            "failed_to_cancel_verification",
                            error=str(e),
                            job_id=job_id,
                        )


class VerificationResultWorker:
    """
    Background worker for processing verification results.

    Listens to verification result events from the Celery workers
    and updates claim status + triggers karma processing.
    """

    TOPICS: Final[list[str]] = [
        "verification.completed",  # Results from verifiers
    ]

    RECONNECT_DELAY_SECONDS: Final[int] = 5

    def __init__(self) -> None:
        self.consumer = KafkaConsumer(
            topics=self.TOPICS,
            group_id="verification-result-processor",
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
        """Start the verification result worker with graceful shutdown support."""
        logger.info("starting_verification_result_worker", topics=self.TOPICS)
        self.running = True
        self._started_at = datetime.now(timezone.utc)

        while self.running and not self._shutdown_event.is_set():
            async for session in get_async_session():
                orchestrator = VerificationOrchestrator(session)

                try:
                    async for message in self.consumer.consume():
                        if not self.running or self._shutdown_event.is_set():
                            break

                        try:
                            await self._process_result(orchestrator, message)
                            self._messages_processed += 1
                        except Exception as e:
                            self._errors_count += 1
                            logger.exception(
                                "verification_result_processing_error",
                                error=str(e),
                                message=message,
                            )

                except Exception as e:
                    self._errors_count += 1
                    logger.error("verification_result_worker_error", error=str(e))

                    if self.running and not self._shutdown_event.is_set():
                        await asyncio.sleep(self.RECONNECT_DELAY_SECONDS)
                    break

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        logger.info(
            "stopping_verification_result_worker",
            messages_processed=self._messages_processed,
            errors_count=self._errors_count,
        )
        self.running = False
        self._shutdown_event.set()
        await self.consumer.close()

    def request_shutdown(self) -> None:
        """Signal the worker to shut down (called from signal handlers)."""
        self._shutdown_event.set()

    async def _process_result(
        self,
        orchestrator: VerificationOrchestrator,
        message: dict[str, Any],
    ) -> None:
        """Process a verification result."""
        job_id = message.get("job_id")
        status = message.get("status")
        result = message.get("result")
        error = message.get("error")

        if not job_id or not status:
            logger.error("invalid_verification_result", message=message)
            return

        await orchestrator.handle_verification_result(
            job_id=job_id,
            status=status,
            result=result,
            error=error,
        )


async def start_verification_worker() -> VerificationWorker:
    """Start the verification worker as an async task with signal handling."""
    worker = VerificationWorker()

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


async def start_verification_result_worker() -> VerificationResultWorker:
    """Start the verification result worker as an async task with signal handling."""
    worker = VerificationResultWorker()

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


def run_verification_worker() -> None:
    """Entry point for running the verification worker as a standalone process."""
    logger.info("verification_worker_starting")

    try:
        asyncio.run(start_verification_worker())
        logger.info("verification_worker_stopped_cleanly")
    except KeyboardInterrupt:
        logger.info("verification_worker_interrupted")
    except Exception as e:
        logger.error("verification_worker_fatal_error", error=str(e))
        raise


if __name__ == "__main__":
    run_verification_worker()
