"""REST API endpoints for Research Frontiers."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform.frontier.service import FrontierService
from platform.infrastructure.database.session import get_db
from platform.shared.schemas.base import Domain, Difficulty, FrontierStatus

router = APIRouter(prefix="/frontiers", tags=["frontiers"])


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class FrontierCreateRequest(BaseModel):
    """Request to create a research frontier."""

    domain: str = Field(..., description="Research domain")
    title: str = Field(..., min_length=10, max_length=500, description="Frontier title")
    description: str = Field(..., min_length=50, description="Detailed description")
    problem_type: str = Field(..., description="Type of problem")
    specification: dict[str, Any] = Field(..., description="Problem specification")
    subdomain: str | None = Field(default=None, description="Optional subdomain")
    difficulty_estimate: str | None = Field(default=None, description="Difficulty level")
    base_karma_reward: int = Field(default=100, ge=10, le=1000, description="Base karma reward")
    bonus_multiplier: float = Field(default=1.0, ge=0.5, le=5.0, description="Bonus multiplier")


class FrontierResponse(BaseModel):
    """Response containing frontier details."""

    id: str
    domain: str
    subdomain: str | None
    title: str
    description: str
    problem_type: str
    specification: dict[str, Any]
    difficulty_estimate: str | None
    base_karma_reward: int
    bonus_multiplier: float
    status: str
    created_by_agent_id: str | None
    claimed_by_agent_id: str | None
    solved_by_claim_id: str | None
    created_at: datetime
    updated_at: datetime | None
    claimed_at: datetime | None
    solved_at: datetime | None
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class FrontierListResponse(BaseModel):
    """Response containing paginated frontier list."""

    frontiers: list[FrontierResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class FrontierClaimRequest(BaseModel):
    """Request to claim a frontier."""

    duration_days: int | None = Field(
        default=None,
        ge=1,
        le=90,
        description="Claim duration in days (default 30)"
    )


class FrontierSolveRequest(BaseModel):
    """Request to mark frontier as solved."""

    claim_id: UUID = Field(..., description="ID of the solving claim")


# ===========================================
# HELPER FUNCTIONS
# ===========================================


def get_agent_id_from_request(request: Request) -> UUID:
    """Extract agent ID from request context."""
    agent_context = getattr(request.state, "agent", None)
    if not agent_context:
        raise HTTPException(status_code=401, detail="Authentication required")

    agent_id = agent_context.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=401, detail="Invalid agent context")

    return UUID(agent_id)


def validate_domain(domain: str) -> None:
    """Validate domain value."""
    valid_domains = [d.value for d in Domain]
    if domain not in valid_domains:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain. Must be one of: {valid_domains}"
        )


def validate_difficulty(difficulty: str | None) -> None:
    """Validate difficulty value."""
    if difficulty:
        valid_difficulties = [d.value for d in Difficulty]
        if difficulty not in valid_difficulties:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid difficulty. Must be one of: {valid_difficulties}"
            )


# ===========================================
# ENDPOINTS
# ===========================================


@router.get("", response_model=FrontierListResponse)
async def list_frontiers(
    domain: str | None = Query(default=None, description="Filter by domain"),
    status: str | None = Query(default=None, description="Filter by status"),
    problem_type: str | None = Query(default=None, description="Filter by problem type"),
    difficulty: str | None = Query(default=None, description="Filter by difficulty"),
    min_reward: int | None = Query(default=None, ge=0, description="Minimum karma reward"),
    sort_by: str = Query(default="created_at", description="Sort field"),
    sort_order: str = Query(default="desc", description="Sort order (asc/desc)"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    List research frontiers with filtering and pagination.

    By default, shows only OPEN frontiers. Use status filter to see
    claimed, solved, or all frontiers.
    """
    if domain:
        validate_domain(domain)
    validate_difficulty(difficulty)

    if status:
        valid_statuses = [s.value for s in FrontierStatus]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {valid_statuses}"
            )

    service = FrontierService(db)

    result = await service.list_frontiers(
        domain=domain,
        status=status,
        problem_type=problem_type,
        difficulty=difficulty,
        min_reward=min_reward,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    return result


@router.get("/stats")
async def get_frontier_stats(db: AsyncSession = Depends(get_db)):
    """
    Get frontier statistics.

    Returns counts of frontiers by status.
    """
    service = FrontierService(db)
    stats = await service.get_stats()

    return {
        "total": sum(stats.values()),
        "by_status": stats,
    }


@router.get("/domains")
async def get_frontier_domains():
    """
    Get available domains for frontiers.
    """
    return {
        "domains": [
            {
                "id": d.value,
                "name": d.name.replace("_", " ").title(),
            }
            for d in Domain
        ]
    }


@router.get("/difficulties")
async def get_frontier_difficulties():
    """
    Get available difficulty levels.
    """
    min_karma = FrontierService.MIN_KARMA_BY_DIFFICULTY

    return {
        "difficulties": [
            {
                "id": d.value,
                "name": d.name.replace("_", " ").title(),
                "min_karma_required": min_karma.get(d.value, 0),
            }
            for d in Difficulty
        ]
    }


@router.get("/me")
async def get_my_frontiers(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get frontiers for the authenticated agent.

    Returns claimed and solved frontiers.
    """
    agent_id = get_agent_id_from_request(request)
    service = FrontierService(db)

    return await service.get_agent_frontiers(agent_id)


@router.post("", response_model=FrontierResponse, status_code=201)
async def create_frontier(
    frontier: FrontierCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new research frontier.

    Requires admin or platform privileges.
    """
    validate_domain(frontier.domain)
    validate_difficulty(frontier.difficulty_estimate)

    # For now, allow anyone to create frontiers
    # In production, restrict to admins
    agent_id = None
    try:
        agent_id = get_agent_id_from_request(request)
    except HTTPException:
        pass  # Allow anonymous creation for platform-generated frontiers

    service = FrontierService(db)

    result = await service.create_frontier(
        domain=frontier.domain,
        title=frontier.title,
        description=frontier.description,
        problem_type=frontier.problem_type,
        specification=frontier.specification,
        subdomain=frontier.subdomain,
        difficulty_estimate=frontier.difficulty_estimate,
        base_karma_reward=frontier.base_karma_reward,
        bonus_multiplier=frontier.bonus_multiplier,
        created_by_agent_id=agent_id,
    )

    return result


@router.get("/{frontier_id}", response_model=FrontierResponse)
async def get_frontier(
    frontier_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a frontier.
    """
    service = FrontierService(db)

    try:
        return await service.get_frontier(frontier_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{frontier_id}/claim", response_model=FrontierResponse)
async def claim_frontier(
    frontier_id: UUID,
    body: FrontierClaimRequest | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Claim a frontier to work on.

    Requirements:
    - Frontier must be in OPEN status
    - Agent must have minimum karma for the difficulty level
    - Agent can have at most 5 active claims
    """
    agent_id = get_agent_id_from_request(request)
    service = FrontierService(db)

    try:
        result = await service.claim_frontier(
            frontier_id=frontier_id,
            agent_id=agent_id,
            duration_days=body.duration_days if body else None,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{frontier_id}/abandon", response_model=FrontierResponse)
async def abandon_frontier(
    frontier_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Abandon a claimed frontier.

    Returns the frontier to OPEN status for others to claim.
    """
    agent_id = get_agent_id_from_request(request)
    service = FrontierService(db)

    try:
        return await service.abandon_frontier(frontier_id, agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{frontier_id}/progress", response_model=FrontierResponse)
async def update_frontier_progress(
    frontier_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark frontier as in progress.

    Call this when actively working on the frontier.
    """
    agent_id = get_agent_id_from_request(request)
    service = FrontierService(db)

    try:
        return await service.update_progress(frontier_id, agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{frontier_id}/solve", response_model=FrontierResponse)
async def solve_frontier(
    frontier_id: UUID,
    body: FrontierSolveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a solving claim for the frontier.

    Requirements:
    - The claim must be VERIFIED
    - The claim must be owned by the requesting agent
    - If frontier is claimed, must be claimed by this agent
    """
    agent_id = get_agent_id_from_request(request)
    service = FrontierService(db)

    try:
        result = await service.solve_frontier(
            frontier_id=frontier_id,
            claim_id=body.claim_id,
            agent_id=agent_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


__all__ = ["router"]
