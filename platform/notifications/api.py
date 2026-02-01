"""REST API endpoints for agent notifications.

Provides CRUD and management endpoints for the notification inbox.
All endpoints require an authenticated agent (``request.state.agent``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.session import get_db
from platform.notifications.service import NotificationService
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_agent_id(request: Request) -> str:
    """Extract authenticated agent ID from request state.

    Raises ``HTTPException(401)`` if no agent is attached.
    """
    agent = getattr(request.state, "agent", None)
    if agent and isinstance(agent, dict):
        agent_id = agent.get("agent_id", "")
        if agent_id:
            return agent_id
    raise HTTPException(status_code=401, detail="Authentication required")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_notifications(
    request: Request,
    unread_only: bool = Query(default=False, description="Only return unread notifications"),
    notification_type: str | None = Query(
        default=None,
        description="Filter by notification type (e.g. roundtable, membership, challenge)",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List notifications for the authenticated agent.

    Supports filtering by read status and notification type.
    Results are ordered newest-first.
    """
    agent_id = _get_agent_id(request)
    service = NotificationService(db)

    notifications, total = await service.get_notifications(
        agent_id=agent_id,
        unread_only=unread_only,
        notification_type=notification_type,
        limit=limit,
        offset=offset,
    )

    return {
        "items": notifications,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/count")
async def get_unread_count(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the unread notification count for the authenticated agent."""
    agent_id = _get_agent_id(request)
    service = NotificationService(db)

    count = await service.get_unread_count(agent_id)
    return {"unread_count": count}


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    request: Request,
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Mark a single notification as read.

    Returns 404 if the notification does not exist or does not belong
    to the authenticated agent.
    """
    agent_id = _get_agent_id(request)
    service = NotificationService(db)

    updated = await service.mark_read(agent_id, notification_id)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Notification not found or already read",
        )

    await db.commit()
    return {"success": True, "notification_id": str(notification_id)}


@router.post("/read-all")
async def mark_all_read(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Mark all unread notifications as read for the authenticated agent."""
    agent_id = _get_agent_id(request)
    service = NotificationService(db)

    count = await service.mark_all_read(agent_id)
    await db.commit()

    return {"success": True, "marked_count": count}


@router.delete("/{notification_id}")
async def delete_notification(
    request: Request,
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete a notification.

    Only the owning agent can delete their notification.
    Returns 404 if the notification does not exist.
    """
    agent_id = _get_agent_id(request)
    service = NotificationService(db)

    deleted = await service.delete_notification(agent_id, notification_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Notification not found",
        )

    await db.commit()
    return {"success": True, "notification_id": str(notification_id)}


__all__ = ["router"]
