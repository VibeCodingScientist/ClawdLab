"""Background worker for challenge lifecycle processing.

Consumes Kafka events related to research challenges and triggers
evaluation, scoring, and finalization workflows.  Follows the same
pattern as :mod:`platform.workers.karma_worker`.
"""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime, timezone
from typing import Any, Final

from platform.infrastructure.database.session import get_async_session
from platform.shared.clients.kafka_client import KafkaConsumer
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# Type alias for health status
HealthStatus = dict[str, Any]


class ChallengeWorker:
    """
    Background worker for processing challenge events.

    Listens to Kafka topics for challenge lifecycle events and routes
    them to the appropriate handler (evaluation, finalization, milestone
    checks, etc.).  Supports graceful shutdown via signals.
    """

    TOPICS: Final[list[str]] = [
        "challenge.created",
        "challenge.status_changed",
        "challenge.scored",
        "challenge.completed",
    ]

    # Consumer group — one logical consumer for all challenge events
    GROUP_ID: Final[str] = "challenge-processor"

    # Reconnection delay after errors
    RECONNECT_DELAY_SECONDS: Final[int] = 5

    def __init__(self) -> None:
        self.consumer = KafkaConsumer(
            topics=self.TOPICS,
            group_id=self.GROUP_ID,
        )
        self.running = False
        self._shutdown_event = asyncio.Event()
        self._messages_processed = 0
        self._errors_count = 0
        self._started_at: datetime | None = None

    def get_health_status(self) -> HealthStatus:
        """Return health status for monitoring."""
        return {
            "healthy": self.running,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "messages_processed": self._messages_processed,
            "errors_count": self._errors_count,
            "topics": self.TOPICS,
            "group_id": self.GROUP_ID,
        }

    async def start(self) -> None:
        """Start the challenge worker with graceful shutdown support."""
        logger.info("starting_challenge_worker", topics=self.TOPICS)
        self.running = True
        self._started_at = datetime.now(timezone.utc)

        while self.running and not self._shutdown_event.is_set():
            async for session in get_async_session():
                try:
                    async for message in self.consumer.consume():
                        if not self.running or self._shutdown_event.is_set():
                            break

                        try:
                            await self._process_message(session, message)
                            self._messages_processed += 1
                        except Exception as e:
                            self._errors_count += 1
                            logger.exception(
                                "challenge_processing_error",
                                error=str(e),
                                message=message,
                            )

                except Exception as e:
                    self._errors_count += 1
                    logger.error("challenge_worker_error", error=str(e))

                    if self.running and not self._shutdown_event.is_set():
                        logger.info(
                            "challenge_worker_reconnecting",
                            delay_seconds=self.RECONNECT_DELAY_SECONDS,
                        )
                        await asyncio.sleep(self.RECONNECT_DELAY_SECONDS)
                    break  # Exit the session loop to get a fresh session

    async def stop(self) -> None:
        """Stop the challenge worker gracefully."""
        logger.info(
            "stopping_challenge_worker",
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
        session: Any,
        message: dict[str, Any],
    ) -> None:
        """Route a Kafka message to the appropriate handler.

        Args:
            session: The async database session.
            message: The Kafka message payload with ``event_type`` and data.
        """
        event_type = message.get("event_type", "")

        logger.debug(
            "processing_challenge_event",
            event_type=event_type,
            challenge_id=message.get("challenge_id"),
        )

        if event_type == "challenge.created":
            await self._handle_challenge_created(session, message)

        elif event_type == "challenge.status_changed":
            await self._handle_status_changed(session, message)

        elif event_type == "challenge.scored":
            await self._handle_submission_scored(session, message)

        elif event_type == "challenge.completed":
            await self._handle_challenge_completed(session, message)

        else:
            logger.debug("unhandled_challenge_event", event_type=event_type)

    async def _handle_challenge_created(
        self,
        session: Any,
        message: dict[str, Any],
    ) -> None:
        """Handle a newly created challenge — validation, notifications."""
        challenge_id = message.get("challenge_id")
        logger.info("challenge_created_event", challenge_id=challenge_id)

        # Future: trigger notification to subscribed agents, validate
        # challenge config, etc.

    async def _handle_status_changed(
        self,
        session: Any,
        message: dict[str, Any],
    ) -> None:
        """Handle challenge status transitions.

        When a challenge transitions to 'active', we may want to notify
        registered labs.  When it transitions to 'evaluation', we kick off
        automated scoring of pending submissions.
        """
        challenge_slug = message.get("challenge_slug", "")
        new_status = message.get("new_status", "")

        logger.info(
            "challenge_status_changed",
            challenge_slug=challenge_slug,
            new_status=new_status,
        )

        if new_status == "evaluation":
            # Auto-evaluate all pending submissions
            await self._trigger_batch_evaluation(session, challenge_slug)

    async def _handle_submission_scored(
        self,
        session: Any,
        message: dict[str, Any],
    ) -> None:
        """Handle a submission being scored — check milestones."""
        from uuid import UUID as _UUID

        challenge_id = message.get("challenge_id")
        submission_id = message.get("submission_id")
        score = message.get("score")

        logger.info(
            "submission_scored_event",
            challenge_id=challenge_id,
            submission_id=submission_id,
            score=score,
        )

        # Future: check if the score qualifies for a milestone prize.

    async def _handle_challenge_completed(
        self,
        session: Any,
        message: dict[str, Any],
    ) -> None:
        """Handle challenge completion — notify participants, update feeds."""
        challenge_slug = message.get("challenge_slug", "")
        logger.info("challenge_completed_event", challenge_slug=challenge_slug)

        # Future: publish to activity feed, send notification emails, etc.

    async def _trigger_batch_evaluation(
        self,
        session: Any,
        challenge_slug: str,
    ) -> None:
        """Evaluate all pending/unevaluated submissions for a challenge."""
        from platform.infrastructure.database.models import (
            ChallengeSubmission,
            ResearchChallenge,
        )
        from sqlalchemy import select as _select

        from platform.challenges.evaluation import ChallengeEvaluator

        ch_result = await session.execute(
            _select(ResearchChallenge).where(
                ResearchChallenge.slug == challenge_slug
            )
        )
        challenge = ch_result.scalar_one_or_none()
        if challenge is None:
            logger.error(
                "challenge_not_found_for_evaluation",
                challenge_slug=challenge_slug,
            )
            return

        sub_result = await session.execute(
            _select(ChallengeSubmission).where(
                ChallengeSubmission.challenge_id == challenge.id,
                ChallengeSubmission.status == "pending",
            )
        )
        submissions = sub_result.scalars().all()

        if not submissions:
            logger.info(
                "no_pending_submissions",
                challenge_slug=challenge_slug,
            )
            return

        evaluator = ChallengeEvaluator(session)
        evaluated = 0

        for sub in submissions:
            try:
                await evaluator.evaluate_submission(sub.id)
                evaluated += 1
            except Exception as exc:
                logger.error(
                    "batch_evaluation_error",
                    submission_id=str(sub.id),
                    error=str(exc),
                )

        await session.commit()

        logger.info(
            "batch_evaluation_complete",
            challenge_slug=challenge_slug,
            evaluated=evaluated,
            total=len(submissions),
        )


async def start_challenge_worker() -> ChallengeWorker:
    """Start the challenge worker as an async task with signal handling."""
    worker = ChallengeWorker()

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


def run_challenge_worker() -> None:
    """Entry point for running the challenge worker as a standalone process."""
    logger.info("challenge_worker_starting")

    try:
        asyncio.run(start_challenge_worker())
        logger.info("challenge_worker_stopped_cleanly")
    except KeyboardInterrupt:
        logger.info("challenge_worker_interrupted")
    except Exception as e:
        logger.error("challenge_worker_fatal_error", error=str(e))
        raise


if __name__ == "__main__":
    run_challenge_worker()


__all__ = ["ChallengeWorker", "start_challenge_worker", "run_challenge_worker"]
