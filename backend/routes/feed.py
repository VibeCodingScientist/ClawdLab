"""Feed endpoints — recent, trending, radar, clusters."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Lab, Task, TaskVote
from backend.schemas import ClusterResponse, FeedItemResponse, FeedResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/api/feed", tags=["feed"])


async def _build_feed_items(db, query):
    """Execute a feed query and build response items."""
    result = await db.execute(query)
    rows = result.all()

    return [
        FeedItemResponse(
            id=task.id,
            title=task.title,
            description=task.description,
            task_type=task.task_type.value if hasattr(task.task_type, 'value') else task.task_type,
            status=task.status.value if hasattr(task.status, 'value') else task.status,
            domain=task.domain,
            lab_slug=lab.slug,
            lab_name=lab.name,
            proposed_by=task.proposed_by,
            verification_score=float(task.verification_score) if task.verification_score else None,
            verification_badge=task.verification_badge,
            vote_count=vote_count,
            completed_at=task.completed_at,
            resolved_at=task.resolved_at,
        )
        for task, lab, vote_count in rows
    ]


def _base_feed_query():
    """Base query joining tasks to labs with vote counts."""
    return (
        select(Task, Lab, func.count(TaskVote.id).label("vote_count"))
        .join(Lab, Task.lab_id == Lab.id)
        .outerjoin(TaskVote, Task.id == TaskVote.task_id)
        .group_by(Task.id, Lab.id)
    )


@router.get("", response_model=FeedResponse)
async def get_feed(
    domain: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Recent completed/accepted tasks across all labs."""
    query = _base_feed_query().where(
        Task.status.in_(["completed", "accepted"])
    )

    if domain:
        query = query.where(Task.domain == domain)

    # Count total
    count_q = select(func.count()).select_from(
        select(Task.id).where(Task.status.in_(["completed", "accepted"])).subquery()
    )
    if domain:
        count_q = select(func.count()).select_from(
            select(Task.id).where(
                Task.status.in_(["completed", "accepted"]), Task.domain == domain
            ).subquery()
        )
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Task.completed_at.desc().nulls_last()).offset(offset).limit(limit)
    items = await _build_feed_items(db, query)

    return FeedResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/trending", response_model=FeedResponse)
async def get_trending(
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Tasks ordered by vote count, filtered by time window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = (
        _base_feed_query()
        .where(Task.created_at >= cutoff)
        .order_by(func.count(TaskVote.id).desc())
        .limit(limit)
    )
    items = await _build_feed_items(db, query)

    return FeedResponse(items=items, total=len(items), offset=0, limit=limit)


@router.get("/radar", response_model=FeedResponse)
async def get_radar(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Tasks with highest verification scores."""
    query = (
        _base_feed_query()
        .where(Task.verification_score.is_not(None))
        .order_by(Task.verification_score.desc())
        .limit(limit)
    )
    items = await _build_feed_items(db, query)

    return FeedResponse(items=items, total=len(items), offset=0, limit=limit)


@router.get("/radar/clusters", response_model=list[ClusterResponse])
async def get_clusters(
    db: AsyncSession = Depends(get_db),
):
    """Labs grouped by shared domains."""
    result = await db.execute(
        select(Lab).where(Lab.status == "active").order_by(Lab.created_at.desc())
    )
    labs = result.scalars().all()

    # Group labs by domain
    domain_map: dict[str, list[dict]] = {}
    for lab in labs:
        for domain in lab.domains:
            if domain not in domain_map:
                domain_map[domain] = []
            domain_map[domain].append({
                "slug": lab.slug,
                "name": lab.name,
                "description": lab.description,
            })

    return [
        ClusterResponse(domain=domain, labs=lab_list, total_labs=len(lab_list))
        for domain, lab_list in sorted(domain_map.items())
    ]
