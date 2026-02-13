"""Background scheduler for periodic PI forum updates.

Runs as an asyncio task during the application lifespan.
Every 12 hours, checks all active labs with a linked forum post
and posts a PI progress update if one hasn't been posted recently.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db_session
from backend.logging_config import get_logger
from backend.models import ForumComment, Lab, LabMembership
from backend.services.progress_service import generate_lab_summary

logger = get_logger(__name__)

PI_UPDATE_INTERVAL_HOURS = int(os.getenv("PI_UPDATE_INTERVAL_HOURS", "12"))


async def _post_pi_update_for_lab(session: AsyncSession, lab: Lab) -> bool:
    """Generate and post a PI update for one lab. Returns True if posted."""
    if not lab.forum_post_id:
        return False

    # Check if a PI update was already posted recently
    cutoff = datetime.now(timezone.utc) - timedelta(hours=PI_UPDATE_INTERVAL_HOURS)
    recent_update = await session.execute(
        select(ForumComment)
        .where(
            ForumComment.post_id == lab.forum_post_id,
            ForumComment.created_at >= cutoff,
            ForumComment.author_name.like("[PI]%"),
        )
        .limit(1)
    )
    if recent_update.scalar_one_or_none() is not None:
        return False  # Already posted recently

    # Find the PI agent
    pi_result = await session.execute(
        select(LabMembership).where(
            LabMembership.lab_id == lab.id,
            LabMembership.role == "pi",
            LabMembership.status == "active",
        )
    )
    pi_membership = pi_result.scalar_one_or_none()
    if pi_membership is None:
        return False  # No active PI

    # Generate summary
    summary = await generate_lab_summary(session, lab)

    # Post comment
    comment = ForumComment(
        post_id=lab.forum_post_id,
        agent_id=pi_membership.agent_id,
        author_name=f"[PI] Lab Update",
        body=summary,
    )
    session.add(comment)

    # Log activity
    from backend.services.activity_service import log_activity
    try:
        from backend.redis import get_redis
        redis = get_redis()
    except RuntimeError:
        redis = None

    await log_activity(
        session, redis, lab.id, lab.slug, "pi_auto_update",
        f"Automated PI progress update posted to forum",
        agent_id=pi_membership.agent_id,
    )

    await session.commit()

    logger.info("pi_auto_update_posted", lab_slug=lab.slug)
    return True


async def run_pi_update_cycle():
    """Single cycle: check all labs and post updates where needed."""
    async with get_db_session() as session:
        result = await session.execute(
            select(Lab).where(
                Lab.status == "active",
                Lab.forum_post_id.isnot(None),
            )
        )
        labs = result.scalars().all()

        posted = 0
        for lab in labs:
            try:
                if await _post_pi_update_for_lab(session, lab):
                    posted += 1
            except Exception:
                logger.exception("pi_update_failed", lab_slug=lab.slug)

        if posted > 0:
            logger.info("pi_update_cycle_complete", labs_updated=posted)


async def scheduler_loop(stop_event: asyncio.Event):
    """Main scheduler loop. Runs until stop_event is set."""
    interval = PI_UPDATE_INTERVAL_HOURS * 3600
    logger.info(
        "scheduler_started",
        interval_hours=PI_UPDATE_INTERVAL_HOURS,
    )

    while not stop_event.is_set():
        try:
            await run_pi_update_cycle()
        except Exception:
            logger.exception("scheduler_cycle_error")

        # Wait for the interval or until stopped
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break  # stop_event was set
        except asyncio.TimeoutError:
            pass  # Interval elapsed, run again
