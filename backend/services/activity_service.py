"""Activity logging service — insert to DB + publish to Redis."""

import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.models import LabActivityLog

logger = get_logger(__name__)


async def log_activity(
    db: AsyncSession,
    redis,
    lab_id: UUID,
    lab_slug: str,
    activity_type: str,
    message: str,
    agent_id: UUID | None = None,
    task_id: UUID | None = None,
    metadata: dict | None = None,
) -> LabActivityLog:
    """
    Insert an activity log entry and publish to Redis pub/sub.

    Args:
        db: Database session
        redis: Redis connection
        lab_id: Lab UUID
        lab_slug: Lab slug (for Redis channel name)
        activity_type: e.g. 'task_proposed', 'task_completed', 'vote_cast'
        message: Human-readable description
        agent_id: Agent performing the action (optional)
        task_id: Related task (optional)
        metadata: Additional metadata (optional)
    """
    entry = LabActivityLog(
        lab_id=lab_id,
        agent_id=agent_id,
        activity_type=activity_type,
        message=message,
        task_id=task_id,
        metadata_=metadata or {},
    )
    db.add(entry)
    await db.flush()

    # Publish to Redis channel
    if redis is not None:
        channel = f"lab:{lab_slug}:activity"
        event = json.dumps({
            "id": str(entry.id),
            "activity_type": activity_type,
            "message": message,
            "agent_id": str(agent_id) if agent_id else None,
            "task_id": str(task_id) if task_id else None,
            "metadata": metadata or {},
        }, default=str)
        try:
            await redis.publish(channel, event)
        except Exception as e:
            logger.warning("redis_publish_failed", channel=channel, error=str(e))

    logger.info(
        "activity_logged",
        lab_slug=lab_slug,
        activity_type=activity_type,
        message=message,
    )

    return entry
