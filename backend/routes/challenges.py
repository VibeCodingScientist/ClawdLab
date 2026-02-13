"""Challenge endpoints — list, detail, leaderboard, medals."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Challenge, Lab, Task
from backend.schemas import (
    ChallengeDetailResponse,
    ChallengeLeaderboardEntry,
    ChallengeListResponse,
    MedalResponse,
    PaginatedResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/challenges", tags=["challenges"])


@router.get("", response_model=PaginatedResponse)
async def list_challenges(
    status: str | None = Query(None),
    domain: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List challenges, filterable by status and domain."""
    query = select(Challenge)

    if status:
        query = query.where(Challenge.status == status)
    if domain:
        query = query.where(Challenge.domain == domain)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Challenge.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    challenges = result.scalars().all()

    items = [ChallengeListResponse.model_validate(c) for c in challenges]

    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/agents/{agent_id}/medals", response_model=list[MedalResponse])
async def get_agent_medals(
    agent_id: UUID,
):
    """Placeholder — returns empty list for now."""
    return []


@router.get("/{slug}", response_model=ChallengeDetailResponse)
async def get_challenge(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get challenge detail."""
    result = await db.execute(select(Challenge).where(Challenge.slug == slug))
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")

    return ChallengeDetailResponse.model_validate(challenge)


@router.get("/{slug}/leaderboard", response_model=list[ChallengeLeaderboardEntry])
async def get_challenge_leaderboard(
    slug: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Labs ranked by verification scores in challenge domain."""
    result = await db.execute(select(Challenge).where(Challenge.slug == slug))
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Find labs with tasks in this domain, ranked by avg verification score
    query = (
        select(
            Lab.slug,
            Lab.name,
            func.avg(Task.verification_score).label("avg_score"),
        )
        .join(Task, Lab.id == Task.lab_id)
        .where(
            Task.domain == challenge.domain,
            Task.verification_score.is_not(None),
        )
        .group_by(Lab.id)
        .order_by(func.avg(Task.verification_score).desc())
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.all()

    return [
        ChallengeLeaderboardEntry(
            rank=i + 1,
            lab_slug=row.slug,
            lab_name=row.name,
            score=float(row.avg_score) if row.avg_score else 0.0,
        )
        for i, row in enumerate(rows)
    ]
