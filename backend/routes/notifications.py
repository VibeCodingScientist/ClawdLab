"""Notification endpoints — list, count, and mark-read for human users."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import Notification, User
from backend.schemas import (
    NotificationListResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List notifications for the current user, newest first."""
    base = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        base = base.where(Notification.read_at.is_(None))

    # Total count
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0

    # Unread count (always computed, regardless of filter)
    unread_count = (await db.execute(
        select(func.count()).where(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
    )).scalar() or 0

    # Paginated items
    query = base.order_by(Notification.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    rows = result.scalars().all()

    items = [
        NotificationResponse(
            id=n.id,
            user_id=n.user_id,
            notification_type=n.notification_type,
            title=n.title,
            body=n.body,
            link=n.link,
            metadata=n.metadata_,
            read_at=n.read_at,
            created_at=n.created_at,
        )
        for n in rows
    ]

    return NotificationListResponse(items=items, total=total, unread_count=unread_count)


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the number of unread notifications for the current user."""
    count = (await db.execute(
        select(func.count()).where(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
    )).scalar() or 0
    return NotificationUnreadCountResponse(unread_count=count)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a single notification as read."""
    from datetime import datetime, timezone

    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notif = result.scalar_one_or_none()
    if notif is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notif.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your notification")

    if notif.read_at is None:
        notif.read_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(notif)

    return NotificationResponse(
        id=notif.id,
        user_id=notif.user_id,
        notification_type=notif.notification_type,
        title=notif.title,
        body=notif.body,
        link=notif.link,
        metadata=notif.metadata_,
        read_at=notif.read_at,
        created_at=notif.created_at,
    )


@router.post("/read-all", response_model=NotificationUnreadCountResponse)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark all notifications as read for the current user."""
    from datetime import datetime, timezone
    from sqlalchemy import update

    now = datetime.now(timezone.utc)
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
        .values(read_at=now)
    )
    await db.commit()
    return NotificationUnreadCountResponse(unread_count=0)
