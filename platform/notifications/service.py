"""Notification service for agent notifications.

Wraps the Notification ORM model with async CRUD operations,
filtering by type and read-status, and role-based retrieval.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import Notification
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


# Maps role archetypes to the notification types most relevant to them.
# Generalist receives all types, so it is handled as a special case.
ROLE_TYPE_MAP: dict[str, list[str]] = {
    "theorist": ["roundtable", "research", "verification", "challenge"],
    "scout": ["roundtable", "research", "verification", "challenge"],
    "experimentalist": ["work_assigned", "verification", "research", "roundtable"],
    "technician": ["work_assigned", "verification", "research", "roundtable"],
    "critic": ["review_requested", "challenge", "roundtable", "verification"],
    "pi": ["membership", "governance", "roundtable", "research", "verification"],
    "synthesizer": ["roundtable", "research", "verification"],
    "mentor": ["membership", "roundtable", "research"],
}


def _notification_to_dict(notification: Notification) -> dict[str, Any]:
    """Serialise a Notification row to a plain dictionary."""
    return {
        "id": str(notification.id),
        "agent_id": str(notification.agent_id),
        "notification_type": notification.notification_type,
        "priority": notification.priority,
        "title": notification.title,
        "body": notification.body,
        "data": notification.data,
        "action_url": notification.action_url,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }


class NotificationService:
    """Service layer for notification CRUD and queries.

    All methods operate within the caller-provided ``AsyncSession``.
    The caller is responsible for committing or rolling back.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_notification(
        self,
        agent_id: str | UUID,
        notification_type: str,
        priority: str,
        title: str,
        body: str | None = None,
        data: dict[str, Any] | None = None,
        action_url: str | None = None,
    ) -> dict[str, Any]:
        """Create a new notification for an agent.

        Args:
            agent_id: Target agent UUID.
            notification_type: Category (e.g. ``roundtable``, ``membership``).
            priority: One of ``low``, ``normal``, ``high``, ``urgent``.
            title: Short human-readable title.
            body: Optional longer description.
            data: Optional arbitrary JSON payload.
            action_url: Optional deep-link URL.

        Returns:
            Serialised notification dict.
        """
        notification = Notification(
            id=uuid4(),
            agent_id=agent_id if isinstance(agent_id, UUID) else UUID(str(agent_id)),
            notification_type=notification_type,
            priority=priority,
            title=title,
            body=body,
            data=data,
            action_url=action_url,
        )
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)

        logger.info(
            "notification_created",
            notification_id=str(notification.id),
            agent_id=str(agent_id),
            notification_type=notification_type,
            priority=priority,
        )
        return _notification_to_dict(notification)

    # ------------------------------------------------------------------
    # Read / List
    # ------------------------------------------------------------------

    async def get_notifications(
        self,
        agent_id: str | UUID,
        unread_only: bool = False,
        notification_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return notifications for an agent with optional filters.

        Args:
            agent_id: Owning agent UUID.
            unread_only: If ``True``, only return unread notifications.
            notification_type: Optional type filter.
            limit: Max rows to return.
            offset: Pagination offset.

        Returns:
            Tuple of (list of notification dicts, total count).
        """
        aid = agent_id if isinstance(agent_id, UUID) else UUID(str(agent_id))

        conditions = [Notification.agent_id == aid]
        if unread_only:
            conditions.append(Notification.read_at.is_(None))
        if notification_type:
            conditions.append(Notification.notification_type == notification_type)

        # Total count
        count_query = (
            select(func.count())
            .select_from(Notification)
            .where(and_(*conditions))
        )
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Paginated rows ordered newest-first
        rows_query = (
            select(Notification)
            .where(and_(*conditions))
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows_result = await self.session.execute(rows_query)
        notifications = [
            _notification_to_dict(n) for n in rows_result.scalars().all()
        ]

        return notifications, total

    # ------------------------------------------------------------------
    # Mark read
    # ------------------------------------------------------------------

    async def mark_read(
        self,
        agent_id: str | UUID,
        notification_id: str | UUID,
    ) -> bool:
        """Mark a single notification as read.

        Returns ``True`` if the row was found and updated, ``False``
        otherwise (e.g. wrong agent or already deleted).
        """
        aid = agent_id if isinstance(agent_id, UUID) else UUID(str(agent_id))
        nid = notification_id if isinstance(notification_id, UUID) else UUID(str(notification_id))

        result = await self.session.execute(
            update(Notification)
            .where(
                and_(
                    Notification.id == nid,
                    Notification.agent_id == aid,
                    Notification.read_at.is_(None),
                )
            )
            .values(read_at=_utc_now())
        )
        await self.session.flush()

        updated = result.rowcount > 0
        if updated:
            logger.debug(
                "notification_marked_read",
                notification_id=str(nid),
                agent_id=str(aid),
            )
        return updated

    async def mark_all_read(self, agent_id: str | UUID) -> int:
        """Mark all unread notifications for an agent as read.

        Returns the number of rows updated.
        """
        aid = agent_id if isinstance(agent_id, UUID) else UUID(str(agent_id))

        result = await self.session.execute(
            update(Notification)
            .where(
                and_(
                    Notification.agent_id == aid,
                    Notification.read_at.is_(None),
                )
            )
            .values(read_at=_utc_now())
        )
        await self.session.flush()

        count = result.rowcount
        logger.info(
            "notifications_marked_all_read",
            agent_id=str(aid),
            count=count,
        )
        return count

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_notification(
        self,
        agent_id: str | UUID,
        notification_id: str | UUID,
    ) -> bool:
        """Delete a single notification.

        Only the owning agent can delete their notification.
        Returns ``True`` if the row was deleted.
        """
        aid = agent_id if isinstance(agent_id, UUID) else UUID(str(agent_id))
        nid = notification_id if isinstance(notification_id, UUID) else UUID(str(notification_id))

        result = await self.session.execute(
            delete(Notification).where(
                and_(
                    Notification.id == nid,
                    Notification.agent_id == aid,
                )
            )
        )
        await self.session.flush()

        deleted = result.rowcount > 0
        if deleted:
            logger.debug(
                "notification_deleted",
                notification_id=str(nid),
                agent_id=str(aid),
            )
        return deleted

    # ------------------------------------------------------------------
    # Counts
    # ------------------------------------------------------------------

    async def get_unread_count(self, agent_id: str | UUID) -> int:
        """Return the number of unread notifications for an agent."""
        aid = agent_id if isinstance(agent_id, UUID) else UUID(str(agent_id))

        result = await self.session.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                and_(
                    Notification.agent_id == aid,
                    Notification.read_at.is_(None),
                )
            )
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Role-filtered retrieval
    # ------------------------------------------------------------------

    async def get_role_filtered(
        self,
        agent_id: str | UUID,
        role_archetype: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return unread notifications filtered by role relevance.

        For *generalist* agents all notification types are returned.
        For specific archetypes only the types mapped in ``ROLE_TYPE_MAP``
        are included.

        Args:
            agent_id: Owning agent UUID.
            role_archetype: One of the lab role archetypes.
            limit: Max rows to return.

        Returns:
            List of notification dicts, newest first.
        """
        aid = agent_id if isinstance(agent_id, UUID) else UUID(str(agent_id))

        conditions = [
            Notification.agent_id == aid,
            Notification.read_at.is_(None),
        ]

        # Generalist receives everything; others get role-relevant types.
        archetype_lower = role_archetype.lower()
        if archetype_lower != "generalist":
            relevant_types = ROLE_TYPE_MAP.get(archetype_lower, [])
            if relevant_types:
                conditions.append(
                    Notification.notification_type.in_(relevant_types)
                )

        query = (
            select(Notification)
            .where(and_(*conditions))
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [_notification_to_dict(n) for n in result.scalars().all()]


__all__ = ["NotificationService", "ROLE_TYPE_MAP"]
