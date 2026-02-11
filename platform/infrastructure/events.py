"""Platform event dispatch — replaces Celery event_tasks.

All handlers are plain async functions. ``emit_platform_event()`` fans
out to them via ``asyncio.create_task()`` so callers don't block.
"""

from __future__ import annotations

import asyncio
from typing import Any

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# Fan-out router
# ============================================================


def emit_platform_event(topic: str, event_data: dict[str, Any]) -> None:
    """Route a platform event to appropriate async handler tasks.

    This is a synchronous function safe to call from async code.
    Handlers run as fire-and-forget background tasks on the running loop.

    Args:
        topic: Logical topic (e.g. "claims", "verification.results").
        event_data: The event payload dict.
    """
    loop = asyncio.get_running_loop()
    event_type = event_data.get("event_type", "")

    if topic == "claims":
        if event_type == "claim.submitted":
            loop.create_task(_dispatch_claim_verification(event_data))
        loop.create_task(_handle_karma_event(event_data))
        loop.create_task(_handle_xp_event(event_data))
        loop.create_task(_handle_notification_event(event_data))

    elif topic in ("verification.results", "verification.completed"):
        loop.create_task(_process_verification_result(event_data))
        loop.create_task(_handle_karma_event(event_data))
        loop.create_task(_handle_xp_event(event_data))
        loop.create_task(_handle_notification_event(event_data))
        loop.create_task(_handle_roundtable_result(event_data))

    elif topic == "frontiers":
        loop.create_task(_handle_karma_event(event_data))
        loop.create_task(_handle_xp_event(event_data))
        loop.create_task(_handle_notification_event(event_data))

    elif topic.startswith("labs."):
        loop.create_task(_handle_lab_event(event_data))
        loop.create_task(_handle_notification_event(event_data))
        if topic == "labs.roundtable":
            loop.create_task(_handle_xp_event(event_data))

    elif topic.startswith("challenge"):
        loop.create_task(_handle_challenge_event(event_data))
        loop.create_task(_handle_karma_event(event_data))
        loop.create_task(_handle_notification_event(event_data))

    elif topic == "claims.verification.completed":
        loop.create_task(_handle_roundtable_result(event_data))
        loop.create_task(_handle_notification_event(event_data))

    elif topic == "reputation.transactions":
        logger.info("reputation_event", event_type=event_type)

    else:
        logger.debug("unrouted_event", topic=topic, event_type=event_type)


# ============================================================
# Claim verification dispatch
# ============================================================


async def _dispatch_claim_verification(event_data: dict[str, Any]) -> None:
    from sqlalchemy import select

    from platform.infrastructure.database.models import Claim
    from platform.infrastructure.database.session import get_async_session
    from platform.services.verification_orchestrator.orchestrator import (
        VerificationOrchestrator,
    )

    claim_id = event_data.get("claim_id")
    domain = event_data.get("domain")
    claim_type = event_data.get("claim_type")

    if not all([claim_id, domain, claim_type]):
        logger.error("invalid_claim_submitted_event", event=event_data)
        return

    async for session in get_async_session():
        result = await session.execute(select(Claim).where(Claim.id == claim_id))
        claim = result.scalar_one_or_none()
        if not claim:
            logger.error("claim_not_found_for_verification", claim_id=claim_id)
            return

        orchestrator = VerificationOrchestrator(session)
        job_id = await orchestrator.dispatch_verification(
            claim_id=claim_id,
            domain=domain,
            claim_type=claim_type,
            payload=claim.content,
        )
        logger.info("verification_dispatched", claim_id=claim_id, job_id=job_id)


# ============================================================
# Verification result processing
# ============================================================


async def _process_verification_result(event_data: dict[str, Any]) -> None:
    from platform.infrastructure.database.session import get_async_session
    from platform.services.verification_orchestrator.orchestrator import (
        VerificationOrchestrator,
    )

    job_id = event_data.get("job_id")
    status = event_data.get("status")

    if not job_id or not status:
        logger.error("invalid_verification_result", event=event_data)
        return

    async for session in get_async_session():
        orchestrator = VerificationOrchestrator(session)
        await orchestrator.handle_verification_result(
            job_id=job_id,
            status=status,
            result=event_data.get("result"),
            error=event_data.get("error"),
        )


# ============================================================
# Karma handler
# ============================================================


async def _handle_karma_event(event_data: dict[str, Any]) -> None:
    from platform.infrastructure.database.session import get_async_session
    from platform.reputation.handlers import KarmaEventHandler

    event_type = event_data.get("event_type", "")

    async for session in get_async_session():
        handler = KarmaEventHandler(session)
        try:
            await handler.handle_event(event_type, event_data)
        except Exception as e:
            logger.error("karma_event_error", error=str(e), event_type=event_type)


# ============================================================
# XP handler
# ============================================================


async def _handle_xp_event(event_data: dict[str, Any]) -> None:
    from platform.experience.handlers import XPEventHandler
    from platform.infrastructure.database.session import get_async_session

    event_type = event_data.get("event_type", "")
    data = event_data.get("data", event_data)

    async for session in get_async_session():
        handler = XPEventHandler(session)
        try:
            await handler.handle_event(event_type, data)
        except Exception as e:
            logger.error("xp_event_error", error=str(e), event_type=event_type)


# ============================================================
# Notification handler
# ============================================================


async def _handle_notification_event(event_data: dict[str, Any]) -> None:
    from platform.infrastructure.database.session import get_async_session
    from platform.notifications.producers import NotificationProducer

    event_type = event_data.get("event_type", "")
    data = event_data.get("data", event_data)

    async for session in get_async_session():
        producer = NotificationProducer(session)
        try:
            await producer.handle_event(event_type, data)
        except Exception as e:
            logger.error("notification_event_error", error=str(e), event_type=event_type)


# ============================================================
# Lab event handler
# ============================================================


async def _handle_lab_event(event_data: dict[str, Any]) -> None:
    event_type = event_data.get("event_type", "")
    data = event_data.get("data", {})
    logger.info(
        "lab_event_processed",
        event_type=event_type,
        lab_id=data.get("lab_id"),
    )


# ============================================================
# Challenge event handler
# ============================================================


async def _handle_challenge_event(event_data: dict[str, Any]) -> None:
    event_type = event_data.get("event_type", "")

    if event_type == "challenge.status_changed" and event_data.get("new_status") == "evaluation":
        from sqlalchemy import select

        from platform.challenges.evaluation import ChallengeEvaluator
        from platform.infrastructure.database.models import (
            ChallengeSubmission,
            ResearchChallenge,
        )
        from platform.infrastructure.database.session import get_async_session

        challenge_slug = event_data.get("challenge_slug", "")

        async for session in get_async_session():
            ch_result = await session.execute(
                select(ResearchChallenge).where(ResearchChallenge.slug == challenge_slug)
            )
            challenge = ch_result.scalar_one_or_none()
            if not challenge:
                return

            sub_result = await session.execute(
                select(ChallengeSubmission).where(
                    ChallengeSubmission.challenge_id == challenge.id,
                    ChallengeSubmission.status == "pending",
                )
            )
            submissions = sub_result.scalars().all()
            if not submissions:
                return

            evaluator = ChallengeEvaluator(session)
            for sub in submissions:
                try:
                    await evaluator.evaluate_submission(sub.id)
                except Exception as exc:
                    logger.error(
                        "batch_evaluation_error",
                        submission_id=str(sub.id),
                        error=str(exc),
                    )
            await session.commit()
    else:
        logger.info("challenge_event_processed", event_type=event_type)


# ============================================================
# Roundtable result handler
# ============================================================


async def _handle_roundtable_result(event_data: dict[str, Any]) -> None:
    from platform.infrastructure.database.session import get_async_session
    from platform.labs.roundtable_result_handler import process_verification_for_roundtable

    async for session in get_async_session():
        try:
            await process_verification_for_roundtable(session, event_data)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("roundtable_result_error", error=str(e))
