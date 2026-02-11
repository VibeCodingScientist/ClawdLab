"""Celery event tasks — replaces Kafka workers.

Each task processes a platform event through the appropriate handler(s).
The ``emit_platform_event()`` function replaces ``KafkaProducer.send()`` /
``send_event()`` and fans out events to the relevant Celery tasks.

Replaces ~2,400 lines across 6 Kafka worker files with ~200 lines of
direct Celery dispatch.
"""

from __future__ import annotations

import asyncio
from typing import Any

from celery import shared_task

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# Fan-out router — replaces KafkaProducer
# ============================================================


def emit_platform_event(topic: str, event_data: dict[str, Any]) -> None:
    """Route a platform event to appropriate Celery handler tasks.

    This is a synchronous function safe to call from async code.
    It replaces ``KafkaProducer.send()`` / ``send_event()``.

    Args:
        topic: Logical topic (e.g. "claims", "verification.results").
        event_data: The event payload dict.
    """
    event_type = event_data.get("event_type", "")

    if topic == "claims":
        if event_type == "claim.submitted":
            dispatch_claim_verification.delay(event_data)
        handle_karma_event.delay(event_data)
        handle_xp_event.delay(event_data)
        handle_notification_event.delay(event_data)

    elif topic in ("verification.results", "verification.completed"):
        process_verification_result.delay(event_data)
        handle_karma_event.delay(event_data)
        handle_xp_event.delay(event_data)
        handle_notification_event.delay(event_data)
        handle_roundtable_result.delay(event_data)

    elif topic == "frontiers":
        handle_karma_event.delay(event_data)
        handle_xp_event.delay(event_data)
        handle_notification_event.delay(event_data)

    elif topic.startswith("labs."):
        handle_lab_event.delay(event_data)
        handle_notification_event.delay(event_data)
        if topic == "labs.roundtable":
            handle_xp_event.delay(event_data)

    elif topic.startswith("challenge"):
        handle_challenge_event.delay(event_data)
        handle_karma_event.delay(event_data)
        handle_notification_event.delay(event_data)

    elif topic == "claims.verification.completed":
        handle_roundtable_result.delay(event_data)
        handle_notification_event.delay(event_data)

    elif topic == "reputation.transactions":
        logger.info("reputation_event", event_type=event_type)

    else:
        logger.debug("unrouted_event", topic=topic, event_type=event_type)


# ============================================================
# Claim verification dispatch
# ============================================================


@shared_task(name="events.dispatch_claim_verification", ignore_result=True)
def dispatch_claim_verification(event_data: dict[str, Any]) -> None:
    """Dispatch a newly submitted claim to the verification orchestrator."""
    asyncio.run(_dispatch_claim_verification(event_data))


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


@shared_task(name="events.process_verification_result", ignore_result=True)
def process_verification_result(event_data: dict[str, Any]) -> None:
    """Process a verification result — update DB, cache, and badges."""
    asyncio.run(_process_verification_result(event_data))


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


@shared_task(name="events.handle_karma", ignore_result=True)
def handle_karma_event(event_data: dict[str, Any]) -> None:
    """Route event through the karma handler."""
    asyncio.run(_handle_karma_event(event_data))


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


@shared_task(name="events.handle_xp", ignore_result=True)
def handle_xp_event(event_data: dict[str, Any]) -> None:
    """Route event through the XP handler."""
    asyncio.run(_handle_xp_event(event_data))


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


@shared_task(name="events.handle_notification", ignore_result=True)
def handle_notification_event(event_data: dict[str, Any]) -> None:
    """Route event through the notification handler."""
    asyncio.run(_handle_notification_event(event_data))


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
# Lab event handler (logging + index updates)
# ============================================================


@shared_task(name="events.handle_lab", ignore_result=True)
def handle_lab_event(event_data: dict[str, Any]) -> None:
    """Process lab event — logging and index updates."""
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


@shared_task(name="events.handle_challenge", ignore_result=True)
def handle_challenge_event(event_data: dict[str, Any]) -> None:
    """Process challenge lifecycle event."""
    asyncio.run(_handle_challenge_event(event_data))


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


@shared_task(name="events.handle_roundtable_result", ignore_result=True)
def handle_roundtable_result(event_data: dict[str, Any]) -> None:
    """Process verification result for roundtable research items."""
    asyncio.run(_handle_roundtable_result(event_data))


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
