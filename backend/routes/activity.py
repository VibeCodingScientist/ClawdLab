"""Activity log and SSE stream endpoints."""

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.database import get_db
from backend.logging_config import get_logger
from backend.redis import get_redis
from backend.models import Lab, LabActivityLog
from backend.schemas import ActivityLogResponse, PaginatedResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/api/labs/{slug}/activity", tags=["activity"])


async def _get_lab(db, slug):
    result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    return lab


@router.get("", response_model=PaginatedResponse)
async def list_activity(
    slug: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List paginated activity log for a lab."""
    lab = await _get_lab(db, slug)

    query = select(LabActivityLog).where(LabActivityLog.lab_id == lab.id)
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(LabActivityLog.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    entries = result.scalars().all()

    items = [
        ActivityLogResponse(
            id=e.id,
            lab_id=e.lab_id,
            agent_id=e.agent_id,
            activity_type=e.activity_type,
            message=e.message,
            task_id=e.task_id,
            metadata=e.metadata_,
            created_at=e.created_at,
        )
        for e in entries
    ]

    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/stream")
async def activity_stream(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """SSE stream of lab activity via Redis pub/sub."""
    lab = await _get_lab(db, slug)
    channel = f"lab:{lab.slug}:activity"

    async def event_generator():
        redis = get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    yield {
                        "event": "activity",
                        "data": message["data"],
                    }

                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return EventSourceResponse(event_generator())
