"""ChallengeScheduler — automatic lifecycle transitions based on timestamps.

Designed to be called by the periodic scheduler roughly
every 60 seconds.  Each tick inspects challenge timestamps and advances
the state machine accordingly.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

from .state_machine import can_transition

logger = get_logger(__name__)


async def challenge_scheduler_tick(session: AsyncSession) -> dict:
    """Auto-transition challenges based on their timestamp columns.

    State transitions handled:

    * **open -> active**: ``submission_opens`` is past.
    * **active -> evaluation**: ``submission_closes`` is past.
    * **evaluation -> completed**: ``evaluation_ends`` is past; triggers
      :meth:`ChallengeEvaluator.finalize_challenge`.

    Returns:
        ``{"transitioned": [...], "finalized": [...]}``.
    """
    from platform.infrastructure.database.models import ResearchChallenge

    from .evaluation import ChallengeEvaluator

    now = datetime.now(timezone.utc)
    transitioned: list[dict] = []
    finalized: list[dict] = []

    # 1. Open challenges past submission_opens -> active
    open_result = await session.execute(
        select(ResearchChallenge).where(
            ResearchChallenge.status == "open",
            ResearchChallenge.submission_opens.is_not(None),
            ResearchChallenge.submission_opens <= now,
        )
    )
    for challenge in open_result.scalars().all():
        if can_transition(challenge.status, "active"):
            challenge.status = "active"
            challenge.updated_at = now
            transitioned.append({
                "slug": challenge.slug,
                "from": "open",
                "to": "active",
            })
            logger.info(
                "Scheduler: challenge '%s' transitioned open -> active",
                challenge.slug,
            )

    # 2. Active challenges past submission_closes -> evaluation
    active_result = await session.execute(
        select(ResearchChallenge).where(
            ResearchChallenge.status == "active",
            ResearchChallenge.submission_closes <= now,
        )
    )
    for challenge in active_result.scalars().all():
        if can_transition(challenge.status, "evaluation"):
            challenge.status = "evaluation"
            challenge.updated_at = now
            transitioned.append({
                "slug": challenge.slug,
                "from": "active",
                "to": "evaluation",
            })
            logger.info(
                "Scheduler: challenge '%s' transitioned active -> evaluation",
                challenge.slug,
            )

    # 3. Evaluation challenges past evaluation_ends -> finalize
    eval_result = await session.execute(
        select(ResearchChallenge).where(
            ResearchChallenge.status == "evaluation",
            ResearchChallenge.evaluation_ends.is_not(None),
            ResearchChallenge.evaluation_ends <= now,
        )
    )
    for challenge in eval_result.scalars().all():
        try:
            evaluator = ChallengeEvaluator(session)
            result = await evaluator.finalize_challenge(challenge.slug)
            finalized.append({
                "slug": challenge.slug,
                "result": result,
            })
            logger.info(
                "Scheduler: challenge '%s' finalized",
                challenge.slug,
            )
        except Exception as exc:
            logger.error(
                "Scheduler: failed to finalize challenge '%s': %s",
                challenge.slug,
                exc,
            )

    await session.flush()

    if transitioned or finalized:
        logger.info(
            "Scheduler tick: %d transitioned, %d finalized",
            len(transitioned),
            len(finalized),
        )

    return {
        "transitioned": transitioned,
        "finalized": finalized,
    }


__all__ = ["challenge_scheduler_tick"]
