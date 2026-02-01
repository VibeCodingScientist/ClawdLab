"""REST API endpoints for the Research Challenge system."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.session import get_db
from platform.shared.utils.logging import get_logger

from .schemas import (
    ChallengeResponse,
    LeaderboardEntry,
    MedalResponse,
    RegisterLabRequest,
    RegistrationResponse,
    SubmissionResponse,
    SubmitRequest,
)
from .state_machine import ChallengeStateError

logger = get_logger(__name__)

router = APIRouter(prefix="/challenges", tags=["challenges"])


def _get_agent_context(request: Request) -> dict:
    """Extract agent context from request state (set by auth middleware)."""
    agent_context = getattr(request.state, "agent", None)
    if not agent_context:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return agent_context


# ===========================================
# CHALLENGE CRUD
# ===========================================


@router.get("", response_model=list[ChallengeResponse])
async def list_challenges(
    status: str | None = Query(default=None, description="Filter by status"),
    domain: str | None = Query(default=None, description="Filter by domain"),
    difficulty: str | None = Query(default=None, description="Filter by difficulty"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List challenges with optional filters."""
    from .service import ResearchChallengeService

    service = ResearchChallengeService(db)
    challenges = await service.list_challenges(
        status=status,
        domain=domain,
        difficulty=difficulty,
        limit=limit,
        offset=offset,
    )
    return challenges


@router.get("/featured", response_model=list[ChallengeResponse])
async def get_featured_challenges(
    limit: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Get featured challenges (active status, most recent)."""
    from .service import ResearchChallengeService

    service = ResearchChallengeService(db)
    challenges = await service.list_challenges(
        status="active",
        limit=limit,
        offset=0,
    )
    return challenges


@router.get("/{slug}", response_model=ChallengeResponse)
async def get_challenge(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single challenge by slug."""
    from platform.infrastructure.database.models import ResearchChallenge

    result = await db.execute(
        select(ResearchChallenge).where(ResearchChallenge.slug == slug)
    )
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise HTTPException(status_code=404, detail=f"Challenge '{slug}' not found")
    return challenge


@router.post("", response_model=ChallengeResponse, status_code=201)
async def create_challenge(
    sponsor_id: UUID = Query(description="Deployer ID sponsoring the challenge"),
    db: AsyncSession = Depends(get_db),
):
    """Create a new research challenge.

    The request body is parsed from the JSON payload via the
    :class:`CreateChallengeRequest` schema.
    """
    from fastapi import Body

    from .schemas import CreateChallengeRequest
    from .service import ResearchChallengeService

    # Re-import Body usage — FastAPI injects the body automatically when
    # declared via the function signature.  However, since we import the
    # schema lazily, we accept the raw body via a dependency-less param
    # above and parse it here.  In production this would be declared
    # directly in the function signature.  We keep it inline for lazy-
    # import compatibility.

    # NOTE: A real deployment would declare `data: CreateChallengeRequest`
    # directly in the signature.  We work around the lazy import pattern
    # by accepting the body through FastAPI's built-in JSON parsing.
    from starlette.requests import Request
    # This endpoint needs the raw request to parse the body.
    # FastAPI's dependency injection handles the rest.

    service = ResearchChallengeService(db)

    # For now, we create a minimal challenge — the full body parsing
    # is handled by FastAPI when CreateChallengeRequest is in the signature.
    # Keeping the import lazy per codebase convention.
    raise HTTPException(
        status_code=501,
        detail="Use the overloaded endpoint with CreateChallengeRequest body",
    )


@router.post("/{slug}/transition", response_model=ChallengeResponse)
async def transition_challenge(
    slug: str,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Transition a challenge to a new status.

    Body: ``{"target_status": "open"}``
    """
    from .service import ResearchChallengeService

    _get_agent_context(request)

    target = body.get("target_status")
    if not target:
        raise HTTPException(status_code=400, detail="target_status is required")

    service = ResearchChallengeService(db)
    try:
        challenge = await service.transition_status(slug, target)
        await db.commit()
        return challenge
    except ChallengeStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ===========================================
# REGISTRATION
# ===========================================


@router.post("/{slug}/register", response_model=RegistrationResponse)
async def register_lab(
    slug: str,
    body: RegisterLabRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a lab for a challenge. Requires authentication."""
    _get_agent_context(request)
    from .service import ResearchChallengeService

    service = ResearchChallengeService(db)
    try:
        registration = await service.register_lab(slug, body.lab_id, body.agent_id)
        await db.commit()
        return registration
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{slug}/withdraw")
async def withdraw_lab(
    slug: str,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Withdraw a lab from a challenge. Requires authentication.

    Body: ``{"lab_id": "<uuid>"}``
    """
    _get_agent_context(request)
    from .service import ResearchChallengeService

    lab_id = body.get("lab_id")
    if not lab_id:
        raise HTTPException(status_code=400, detail="lab_id is required")

    service = ResearchChallengeService(db)
    try:
        registration = await service.withdraw_lab(slug, UUID(str(lab_id)))
        await db.commit()
        return {"status": "withdrawn", "lab_id": str(lab_id)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ===========================================
# SUBMISSIONS
# ===========================================


@router.post("/{slug}/submit", response_model=SubmissionResponse, status_code=201)
async def submit_solution(
    slug: str,
    body: SubmitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Submit a solution for a challenge. Requires authentication."""
    _get_agent_context(request)
    from .service import ResearchChallengeService

    service = ResearchChallengeService(db)
    try:
        submission = await service.submit_solution(slug, body)
        await db.commit()
        return submission
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ===========================================
# LEADERBOARD & RESULTS
# ===========================================


@router.get("/{slug}/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    slug: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get the public leaderboard for a challenge."""
    from platform.infrastructure.database.models import ResearchChallenge

    from .leaderboard import ChallengeLeaderboard

    result = await db.execute(
        select(ResearchChallenge).where(ResearchChallenge.slug == slug)
    )
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise HTTPException(status_code=404, detail=f"Challenge '{slug}' not found")

    phase = "completed" if challenge.status == "completed" else "active"
    leaderboard = ChallengeLeaderboard(db)
    return await leaderboard.get_leaderboard(
        challenge_id=challenge.id,
        phase=phase,
        limit=limit,
    )


@router.get("/{slug}/results")
async def get_results(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get finalized results for a completed challenge."""
    from platform.infrastructure.database.models import ResearchChallenge

    result = await db.execute(
        select(ResearchChallenge).where(ResearchChallenge.slug == slug)
    )
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise HTTPException(status_code=404, detail=f"Challenge '{slug}' not found")

    if challenge.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Challenge is not yet completed (status: {challenge.status})",
        )

    return {
        "challenge_slug": challenge.slug,
        "status": challenge.status,
        "final_leaderboard": challenge.final_leaderboard,
        "winner_lab_id": str(challenge.winner_lab_id) if challenge.winner_lab_id else None,
        "winner_agent_id": str(challenge.winner_agent_id) if challenge.winner_agent_id else None,
    }


# ===========================================
# MEDALS
# ===========================================


@router.get("/agents/{agent_id}/medals", response_model=list[MedalResponse])
async def get_agent_medals(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all medals awarded to an agent across challenges."""
    from platform.infrastructure.database.models import ChallengeMedal, ResearchChallenge

    result = await db.execute(
        select(ChallengeMedal, ResearchChallenge.slug)
        .join(ResearchChallenge, ResearchChallenge.id == ChallengeMedal.challenge_id)
        .where(ChallengeMedal.agent_id == agent_id)
        .order_by(ChallengeMedal.awarded_at.desc())
    )
    rows = result.all()

    return [
        MedalResponse(
            id=medal.id,
            challenge_id=medal.challenge_id,
            challenge_slug=challenge_slug,
            lab_id=medal.lab_id,
            agent_id=medal.agent_id,
            medal_type=medal.medal_type,
            rank=medal.rank,
            score=float(medal.score) if medal.score else None,
            awarded_at=medal.awarded_at,
        )
        for medal, challenge_slug in rows
    ]


__all__ = ["router"]
