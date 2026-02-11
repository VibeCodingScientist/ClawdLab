"""Verification result handler for roundtable research items.

Routes claim verification results back into the roundtable pipeline:
- Verified → transition to verified, distribute karma
- Failed → route back to under_debate with evidence entry

Called by the ``events.handle_roundtable_result`` Celery task.
"""

from __future__ import annotations

from typing import Any, Final
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import LabResearchItem
from platform.labs.repository import (
    ResearchItemRepository,
    RoundtableRepository,
)
from platform.labs.state_machine import can_transition
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_KARMA_ON_VERIFY: Final[int] = 50


async def process_verification_for_roundtable(
    session: AsyncSession,
    event_data: dict[str, Any],
) -> None:
    """Process a verification result and update linked roundtable items.

    This is the core business logic extracted from the former
    ``RoundtableResultHandler._handle_message`` method.

    Args:
        session: Active async database session (caller must commit/rollback).
        event_data: Event payload with claim_id, status, badge, etc.
    """
    from platform.infrastructure.celery.event_tasks import emit_platform_event

    data = event_data.get("data", event_data)
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
        logger.debug("verification_not_lab_claim", claim_id=claim_id)
        return

    research_repo = ResearchItemRepository(session)
    roundtable_repo = RoundtableRepository(session)

    if verification_status in ("verified", "passed"):
        badge = data.get("badge", "green")

        if badge == "green":
            # Green badge: auto-publish, full karma
            if can_transition(item.status, "verified"):
                if item.status == "submitted":
                    await research_repo.update(item.id, status="under_review")
                await research_repo.update(item.id, status="verified")

                emit_platform_event("labs.roundtable", {
                    "event_type": "roundtable.result_verified",
                    "data": {
                        "lab_id": str(item.lab_id),
                        "item_id": str(item.id),
                        "claim_id": claim_id,
                        "badge": "green",
                    },
                })

                from platform.labs.roundtable_service import RoundtableService
                rt_service = RoundtableService(session)
                await rt_service._distribute_karma(
                    item.lab_id, item.id, DEFAULT_KARMA_ON_VERIFY,
                )

                logger.info(
                    "roundtable_result_verified",
                    item_id=str(item.id),
                    claim_id=claim_id,
                    badge="green",
                )

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

                emit_platform_event("labs.roundtable", {
                    "event_type": "roundtable.result_verified",
                    "data": {
                        "lab_id": str(item.lab_id),
                        "item_id": str(item.id),
                        "claim_id": claim_id,
                        "badge": "amber",
                    },
                })

                from platform.labs.roundtable_service import RoundtableService
                rt_service = RoundtableService(session)
                await rt_service._distribute_karma(
                    item.lab_id, item.id, DEFAULT_KARMA_ON_VERIFY // 2,
                )

                logger.info(
                    "roundtable_result_amber",
                    item_id=str(item.id),
                    claim_id=claim_id,
                )

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

                emit_platform_event("labs.roundtable", {
                    "event_type": "roundtable.result_failed",
                    "data": {
                        "lab_id": str(item.lab_id),
                        "item_id": str(item.id),
                        "claim_id": claim_id,
                        "badge": "red",
                        "reason": data.get("reason", "red_badge_verification"),
                    },
                })

                logger.info(
                    "roundtable_result_red",
                    item_id=str(item.id),
                    claim_id=claim_id,
                )

        else:
            # Unknown badge, treat as green (backward compat)
            if can_transition(item.status, "verified"):
                if item.status == "submitted":
                    await research_repo.update(item.id, status="under_review")
                await research_repo.update(item.id, status="verified")

                emit_platform_event("labs.roundtable", {
                    "event_type": "roundtable.result_verified",
                    "data": {
                        "lab_id": str(item.lab_id),
                        "item_id": str(item.id),
                        "claim_id": claim_id,
                    },
                })

                from platform.labs.roundtable_service import RoundtableService
                rt_service = RoundtableService(session)
                await rt_service._distribute_karma(
                    item.lab_id, item.id, DEFAULT_KARMA_ON_VERIFY,
                )

    elif verification_status in ("failed", "refuted"):
        # Transition → under_debate with evidence entry
        if can_transition(item.status, "under_debate") or item.status == "submitted":
            if item.status == "submitted":
                await research_repo.update(item.id, status="under_review")
            await research_repo.update(item.id, status="under_debate")

            await roundtable_repo.create(
                id=uuid4(),
                research_item_id=item.id,
                author_id=item.proposed_by,
                entry_type="evidence",
                content=f"Verification failed for claim {claim_id}: {data.get('reason', 'unknown')}",
            )

            emit_platform_event("labs.roundtable", {
                "event_type": "roundtable.result_failed",
                "data": {
                    "lab_id": str(item.lab_id),
                    "item_id": str(item.id),
                    "claim_id": claim_id,
                    "reason": data.get("reason", "verification_failed"),
                },
            })

            logger.info(
                "roundtable_result_failed",
                item_id=str(item.id),
                claim_id=claim_id,
            )


__all__ = ["process_verification_for_roundtable"]
