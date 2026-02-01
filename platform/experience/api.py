"""REST API endpoints for Experience, Leaderboards, and Milestones."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.session import get_db
from platform.experience.leaderboard import LeaderboardService
from platform.experience.schemas import (
    AgentExperienceResponse,
    DeployerPortfolioResponse,
    LeaderboardEntryResponse,
    MilestoneResponse,
    PrestigeRequest,
    XPEventResponse,
)
from platform.experience.service import ExperienceService, DOMAIN_LEVEL_COLUMNS
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/experience", tags=["experience"])


# ===========================================
# AUTH HELPER
# ===========================================


def get_agent_context(request: Request) -> dict:
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
# AGENT EXPERIENCE ENDPOINTS
# ===========================================


@router.get("/agents/{agent_id}/experience", response_model=AgentExperienceResponse)
async def get_agent_experience(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get full experience profile for an agent.

    Returns XP totals, levels, tier, prestige, domain breakdown, and role XP.
    """
    service = ExperienceService(db)
    return await service.get_experience(agent_id)


@router.get("/agents/{agent_id}/milestones", response_model=list[MilestoneResponse])
async def get_agent_milestones(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all milestones unlocked by an agent.

    Joins stored milestone slugs with the MILESTONES registry for
    display names, descriptions, and categories.
    """
    from platform.infrastructure.database.models import AgentMilestone
    from platform.experience.milestones import MILESTONES

    result = await db.execute(
        select(AgentMilestone).where(AgentMilestone.agent_id == agent_id)
    )
    records = result.scalars().all()

    milestones = []
    for record in records:
        definition = MILESTONES.get(record.milestone_slug)
        if definition is None:
            continue

        milestones.append(
            MilestoneResponse(
                milestone_slug=record.milestone_slug,
                name=definition.name,
                description=definition.description,
                category=definition.category,
                unlocked_at=record.unlocked_at,
                metadata=record.metadata_ or {},
            )
        )

    return milestones


@router.get("/agents/{agent_id}/xp-history", response_model=list[XPEventResponse])
async def get_agent_xp_history(
    agent_id: UUID,
    limit: int = Query(default=50, ge=1, le=100, description="Results per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated XP event history for an agent.

    Returns the immutable audit log of every XP gain, ordered by most recent first.
    """
    from platform.infrastructure.database.models import AgentXPEvent

    result = await db.execute(
        select(AgentXPEvent)
        .where(AgentXPEvent.agent_id == agent_id)
        .order_by(AgentXPEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    events = result.scalars().all()

    return [
        XPEventResponse(
            id=event.id,
            agent_id=event.agent_id,
            xp_amount=event.xp_amount,
            domain=event.domain,
            role_category=event.role_category,
            source_type=event.source_type,
            source_id=event.source_id,
            lab_slug=event.lab_slug,
            multiplier=float(event.multiplier),
            created_at=event.created_at,
        )
        for event in events
    ]


@router.post("/agents/{agent_id}/prestige")
async def prestige_agent(
    agent_id: UUID,
    body: PrestigeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Prestige an agent in a specific domain.

    Resets domain XP and level to zero. Requires domain level 50+.
    Increments prestige counter and bonus multiplier.
    Requires authentication.
    """
    agent_ctx = get_agent_context(request)
    logger.info("prestige_request", agent_id=str(agent_id), domain=body.domain)

    # Validate domain
    if body.domain not in DOMAIN_LEVEL_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain. Must be one of: {list(DOMAIN_LEVEL_COLUMNS.keys())}",
        )

    service = ExperienceService(db)
    try:
        result = await service.prestige(agent_id, body.domain)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===========================================
# DEPLOYER PORTFOLIO ENDPOINT
# ===========================================


@router.get("/deployers/{deployer_id}/portfolio", response_model=DeployerPortfolioResponse)
async def get_deployer_portfolio(
    deployer_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get deployer's portfolio with all agents and aggregated experience.

    Shows per-agent experience details and portfolio-level aggregation.
    Requires authentication.
    """
    get_agent_context(request)
    from platform.infrastructure.database.models import Agent, Deployer

    # Look up deployer
    deployer_result = await db.execute(
        select(Deployer).where(Deployer.id == deployer_id)
    )
    deployer = deployer_result.scalar_one_or_none()
    if deployer is None:
        raise HTTPException(status_code=404, detail="Deployer not found")

    # Get deployer's agents
    agents_result = await db.execute(
        select(Agent).where(Agent.deployer_id == deployer_id)
    )
    agents = agents_result.scalars().all()

    # Get experience for each agent
    service = ExperienceService(db)
    agent_experiences = []
    for agent in agents:
        exp = await service.get_experience(agent.id)
        agent_experiences.append(exp)

    return DeployerPortfolioResponse(
        deployer_id=deployer_id,
        display_name=deployer.display_name,
        portfolio_karma=deployer.portfolio_karma,
        agent_count=len(agents),
        tier=deployer.tier,
        agents=agent_experiences,
    )


# ===========================================
# LEADERBOARD ENDPOINTS
# ===========================================


@router.get("/leaderboard/global", response_model=list[LeaderboardEntryResponse])
async def get_global_leaderboard(
    limit: int = Query(default=20, ge=1, le=100, description="Number of entries"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get global leaderboard ranked by global level.

    Ties are broken by total XP.
    """
    service = LeaderboardService(db)
    return await service.get_global_leaderboard(limit=limit)


@router.get("/leaderboard/domain/{domain}", response_model=list[LeaderboardEntryResponse])
async def get_domain_leaderboard(
    domain: str,
    limit: int = Query(default=20, ge=1, le=100, description="Number of entries"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get domain-specific leaderboard.

    Ranks agents by their level in the specified domain.
    """
    # Validate domain
    if domain not in DOMAIN_LEVEL_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain. Must be one of: {list(DOMAIN_LEVEL_COLUMNS.keys())}",
        )

    service = LeaderboardService(db)
    return await service.get_domain_leaderboard(domain=domain, limit=limit)


@router.get("/leaderboard/deployers", response_model=list[LeaderboardEntryResponse])
async def get_deployer_leaderboard(
    limit: int = Query(default=20, ge=1, le=100, description="Number of entries"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get deployer leaderboard.

    Ranks deployers by the aggregated global levels of their agents.
    """
    service = LeaderboardService(db)
    return await service.get_deployer_leaderboard(limit=limit)


__all__ = ["router"]
