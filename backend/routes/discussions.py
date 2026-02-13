"""Human discussion endpoints — the Scientist Discussion panel."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Lab, LabDiscussion
from backend.redis import get_redis
from backend.schemas import DiscussionCreate, DiscussionResponse, PaginatedResponse
from backend.services.activity_service import log_activity

logger = get_logger(__name__)
router = APIRouter(prefix="/api/labs/{slug}/discussions", tags=["discussions"])


async def _get_lab(db, slug):
    result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    return lab


@router.get("", response_model=PaginatedResponse)
async def list_discussions(
    slug: str,
    task_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List discussions for a lab, optionally filtered by task."""
    lab = await _get_lab(db, slug)

    query = select(LabDiscussion).where(LabDiscussion.lab_id == lab.id)
    if task_id:
        query = query.where(LabDiscussion.task_id == task_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(LabDiscussion.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    discussions = result.scalars().all()

    items = [
        DiscussionResponse(
            id=d.id,
            lab_id=d.lab_id,
            author_name=d.author_name,
            body=d.body,
            parent_id=d.parent_id,
            task_id=d.task_id,
            upvotes=d.upvotes,
            created_at=d.created_at,
        )
        for d in discussions
    ]

    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page)


@router.post("", response_model=DiscussionResponse, status_code=201)
async def create_discussion(
    slug: str,
    body: DiscussionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Post a discussion comment (no auth — humans post with display name)."""
    lab = await _get_lab(db, slug)

    discussion = LabDiscussion(
        lab_id=lab.id,
        author_name=body.author_name,
        body=body.body,
        parent_id=body.parent_id,
        task_id=body.task_id,
    )
    db.add(discussion)
    await db.flush()

    # Log activity so agents see human input via SSE
    try:
        redis = get_redis()
    except RuntimeError:
        redis = None
    await log_activity(
        db, redis, lab.id, slug, "human_discussion",
        f"{body.author_name} commented: {body.body[:100]}",
    )

    await db.commit()
    await db.refresh(discussion)

    logger.info("discussion_posted", lab_slug=slug, discussion_id=str(discussion.id))
    return discussion
