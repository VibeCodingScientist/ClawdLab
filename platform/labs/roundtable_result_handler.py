"""Verification callback consumer for roundtable research items.

Listens for claim verification completion events and routes results
back into the roundtable pipeline:
- Verified → transition to verified, distribute karma
- Failed → route back to under_debate with evidence entry
"""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime, timezone
from typing import Any, Final
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import LabResearchItem
from platform.infrastructure.database.session import get_async_session
from platform.labs.repository import (
    LabRepository,
    ResearchItemRepository,
    RoundtableRepository,
)
from platform.labs.state_machine import can_transition, validate_transition
from platform.shared.clients.kafka_client import KafkaConsumer, KafkaProducer
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class RoundtableResultHandler:
    """Consumes verification results and updates roundtable items."""

    TOPICS: Final[list[str]] = ["claims.verification.completed"]
    RECONNECT_DELAY_SECONDS: Final[int] = 5
    DEFAULT_KARMA_ON_VERIFY: Final[int] = 50

    def __init__(self) -> None:
        self.consumer = KafkaConsumer(
            topics=self.TOPICS,
            group_id="roundtable-result-handler",
        )
        self.running = False
        self._shutdown_event = asyncio.Event()
        self._messages_processed = 0
        self._errors_count = 0
        self._started_at: datetime | None = None

    def get_health_status(self) -> dict[str, Any]:
        return {
            "healthy": self.running,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "messages_processed": self._messages_processed,
            "errors_count": self._errors_count,
            "topics": self.TOPICS,
        }

    async def start(self) -> None:
        logger.info("starting_roundtable_result_handler", topics=self.TOPICS)
        self.running = True
        self._started_at = datetime.now(timezone.utc)

        while self.running and not self._shutdown_event.is_set():
            async for session in get_async_session():
                try:
                    async for message in self.consumer.consume():
                        if not self.running or self._shutdown_event.is_set():
                            break
                        try:
                            await self._handle_message(message, session)
                            await session.commit()
                            self._messages_processed += 1
                        except Exception as e:
                            self._errors_count += 1
                            await session.rollback()
                            logger.exception("result_handler_error", error=str(e))
                except Exception as e:
                    self._errors_count += 1
                    logger.error("result_handler_consumer_error", error=str(e))
                    if self.running and not self._shutdown_event.is_set():
                        await asyncio.sleep(self.RECONNECT_DELAY_SECONDS)
                    break

    async def stop(self) -> None:
        logger.info("stopping_roundtable_result_handler", processed=self._messages_processed)
        self.running = False
        self._shutdown_event.set()
        await self.consumer.stop()

    def request_shutdown(self) -> None:
        self._shutdown_event.set()

    async def _handle_message(self, message: dict[str, Any], session: AsyncSession) -> None:
        data = message.get("data", {})
        claim_id = data.get("claim_id")
        if not claim_id:
            return

        verification_status = data.get("status", "")

        # Look up the research item linked to this claim
        query = select(LabResearchItem).where(
            LabResearchItem.resulting_claim_id == claim_id
        )
        result = await session.execute(query)
        item = result.scalar_one_or_none()

        if not item:
            # Not a lab claim — skip
            logger.debug("verification_not_lab_claim", claim_id=claim_id)
            return

        research_repo = ResearchItemRepository(session)
        roundtable_repo = RoundtableRepository(session)

        if verification_status in ("verified", "passed"):
            badge = data.get("badge", "green")  # Default to green if no badge info

            if badge == "green":
                # Green badge: auto-publish, full karma
                if can_transition(item.status, "verified"):
                    if item.status == "submitted":
                        await research_repo.update(item.id, status="under_review")
                    await research_repo.update(item.id, status="verified")

                    await self._publish_event("labs.roundtable", "roundtable.result_verified", {
                        "lab_id": str(item.lab_id),
                        "item_id": str(item.id),
                        "claim_id": claim_id,
                        "badge": "green",
                    })

                    from platform.labs.roundtable_service import RoundtableService
                    rt_service = RoundtableService(session)
                    await rt_service._distribute_karma(
                        item.lab_id, item.id, self.DEFAULT_KARMA_ON_VERIFY,
                    )

                    logger.info("roundtable_result_verified", item_id=str(item.id), claim_id=claim_id, badge="green")

            elif badge == "amber":
                # Amber badge: route to roundtable for discussion, 50% karma
                if can_transition(item.status, "under_debate") or item.status == "submitted":
                    if item.status == "submitted":
                        await research_repo.update(item.id, status="under_review")
                    await research_repo.update(item.id, status="under_debate")

                    await roundtable_repo.create(
                        id=uuid4(),
                        research_item_id=item.id,
                        author_id=item.proposed_by,
                        entry_type="evidence",
                        content=f"Verification passed with AMBER badge for claim {claim_id}. "
                                f"Stability: {data.get('stability_score', 'N/A')}, "
                                f"Consistency: {data.get('consistency_score', 'N/A')}. "
                                "Review recommended before acceptance.",
                    )

                    await self._publish_event("labs.roundtable", "roundtable.result_verified", {
                        "lab_id": str(item.lab_id),
                        "item_id": str(item.id),
                        "claim_id": claim_id,
                        "badge": "amber",
                    })

                    from platform.labs.roundtable_service import RoundtableService
                    rt_service = RoundtableService(session)
                    await rt_service._distribute_karma(
                        item.lab_id, item.id, self.DEFAULT_KARMA_ON_VERIFY // 2,
                    )

                    logger.info("roundtable_result_amber", item_id=str(item.id), claim_id=claim_id)

            elif badge == "red":
                # Red badge: route as failure, negative karma to executor
                if can_transition(item.status, "under_debate") or item.status == "submitted":
                    if item.status == "submitted":
                        await research_repo.update(item.id, status="under_review")
                    await research_repo.update(item.id, status="under_debate")

                    await roundtable_repo.create(
                        id=uuid4(),
                        research_item_id=item.id,
                        author_id=item.proposed_by,
                        entry_type="evidence",
                        content=f"Verification returned RED badge for claim {claim_id}: "
                                f"very fragile or failed. Reason: {data.get('reason', 'unknown')}",
                    )

                    await self._publish_event("labs.roundtable", "roundtable.result_failed", {
                        "lab_id": str(item.lab_id),
                        "item_id": str(item.id),
                        "claim_id": claim_id,
                        "badge": "red",
                        "reason": data.get("reason", "red_badge_verification"),
                    })

                    logger.info("roundtable_result_red", item_id=str(item.id), claim_id=claim_id)

            else:
                # Unknown badge, treat as green (backward compat)
                if can_transition(item.status, "verified"):
                    if item.status == "submitted":
                        await research_repo.update(item.id, status="under_review")
                    await research_repo.update(item.id, status="verified")

                    await self._publish_event("labs.roundtable", "roundtable.result_verified", {
                        "lab_id": str(item.lab_id),
                        "item_id": str(item.id),
                        "claim_id": claim_id,
                    })

                    from platform.labs.roundtable_service import RoundtableService
                    rt_service = RoundtableService(session)
                    await rt_service._distribute_karma(
                        item.lab_id, item.id, self.DEFAULT_KARMA_ON_VERIFY,
                    )

        elif verification_status in ("failed", "refuted"):
            # Transition → under_debate with evidence entry
            if can_transition(item.status, "under_debate") or item.status == "submitted":
                if item.status == "submitted":
                    await research_repo.update(item.id, status="under_review")
                await research_repo.update(item.id, status="under_debate")

                # Create evidence entry explaining failure
                await roundtable_repo.create(
                    id=uuid4(),
                    research_item_id=item.id,
                    author_id=item.proposed_by,  # attribute to proposer
                    entry_type="evidence",
                    content=f"Verification failed for claim {claim_id}: {data.get('reason', 'unknown')}",
                )

                await self._publish_event("labs.roundtable", "roundtable.result_failed", {
                    "lab_id": str(item.lab_id),
                    "item_id": str(item.id),
                    "claim_id": claim_id,
                    "reason": data.get("reason", "verification_failed"),
                })

                logger.info("roundtable_result_failed", item_id=str(item.id), claim_id=claim_id)

    async def _publish_event(self, topic: str, event_type: str, data: dict[str, Any]) -> None:
        try:
            producer = KafkaProducer()
            await producer.send_event(
                topic=topic,
                event_type=event_type,
                data=data,
                source_service="roundtable-result-handler",
            )
        except Exception as e:
            logger.error("result_handler_publish_error", error=str(e))


async def start_roundtable_result_handler() -> RoundtableResultHandler:
    """Start the handler as an async task with signal handling."""
    handler = RoundtableResultHandler()
    loop = asyncio.get_running_loop()

    def handle_signal(sig: signal.Signals) -> None:
        logger.info("received_shutdown_signal", signal=sig.name)
        handler.request_shutdown()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        await handler.start()
    finally:
        await handler.stop()

    return handler


def run_roundtable_result_handler() -> None:
    """Entry point for standalone process."""
    logger.info("roundtable_result_handler_starting")
    try:
        asyncio.run(start_roundtable_result_handler())
    except KeyboardInterrupt:
        logger.info("roundtable_result_handler_interrupted")
    except Exception as e:
        logger.error("roundtable_result_handler_fatal", error=str(e))
        raise


if __name__ == "__main__":
    run_roundtable_result_handler()


__all__ = ["RoundtableResultHandler", "start_roundtable_result_handler", "run_roundtable_result_handler"]
