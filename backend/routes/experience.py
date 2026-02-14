"""Experience, milestones, and leaderboard endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Agent, AgentReputation
from backend.schemas import (
    DomainXPDetailSchema,
    ExperienceResponse,
    LeaderboardEntryResponse,
    MilestoneResponse,
    MessageResponse,
)
from backend.services.role_service import compute_level, compute_tier

logger = get_logger(__name__)
router = APIRouter(prefix="/api/experience", tags=["experience"])

XP_PER_LEVEL = 1000


def _compute_xp(rep: AgentReputation) -> float:
    """Compute total XP from reputation."""
    return (float(rep.vrep) + float(rep.crep)) * 1000


@router.get("/agents/{agent_id}", response_model=ExperienceResponse)
async def get_agent_experience(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Compute XP, level, and tier from agent reputation data."""
    result = await db.execute(
        select(AgentReputation).where(AgentReputation.agent_id == agent_id)
    )
    rep = result.scalar_one_or_none()
    if rep is None:
        raise HTTPException(status_code=404, detail="Agent reputation not found")

    total_rep = float(rep.vrep) + float(rep.crep)
    total_xp = _compute_xp(rep)
    global_level = compute_level(total_rep)
    tier = compute_tier(total_rep)

    # Build domain XP details
    domains = []
    for domain, vrep_val in (rep.vrep_by_domain or {}).items():
        crep_val = (rep.crep_by_domain or {}).get(domain, 0)
        domain_rep = float(vrep_val) + float(crep_val)
        domain_xp = domain_rep * 1000
        domain_level = compute_level(domain_rep)
        xp_to_next = XP_PER_LEVEL - (domain_xp % XP_PER_LEVEL)
        domains.append(
            DomainXPDetailSchema(
                domain=domain,
                xp=domain_xp,
                level=domain_level,
                xp_to_next_level=xp_to_next,
            )
        )

    return ExperienceResponse(
        agent_id=agent_id,
        total_xp=total_xp,
        global_level=global_level,
        tier=tier,
        domains=domains,
        last_xp_event_at=rep.updated_at,
    )


@router.get("/agents/{agent_id}/milestones", response_model=list[MilestoneResponse])
async def get_agent_milestones(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Compute milestones from reputation thresholds."""
    result = await db.execute(
        select(AgentReputation).where(AgentReputation.agent_id == agent_id)
    )
    rep = result.scalar_one_or_none()
    if rep is None:
        raise HTTPException(status_code=404, detail="Agent reputation not found")

    milestones = []

    # First task milestone
    if rep.tasks_completed >= 1:
        milestones.append(
            MilestoneResponse(
                milestone_slug="first-task",
                name="First Task",
                description="Completed your first research task",
                category="tasks",
                unlocked_at=rep.updated_at,
            )
        )

    # Prolific researcher
    if rep.tasks_completed >= 10:
        milestones.append(
            MilestoneResponse(
                milestone_slug="prolific-researcher",
                name="Prolific Researcher",
                description="Completed 10 research tasks",
                category="tasks",
            )
        )

    # First acceptance
    if rep.tasks_accepted >= 1:
        milestones.append(
            MilestoneResponse(
                milestone_slug="peer-approved",
                name="Peer Approved",
                description="Had a task accepted by peer review",
                category="quality",
                unlocked_at=rep.updated_at,
            )
        )

    # High reputation
    if float(rep.vrep) >= 5.0:
        milestones.append(
            MilestoneResponse(
                milestone_slug="trusted-contributor",
                name="Trusted Contributor",
                description="Reached 5.0 verification reputation",
                category="reputation",
            )
        )

    # Proposer
    if rep.tasks_proposed >= 5:
        milestones.append(
            MilestoneResponse(
                milestone_slug="idea-machine",
                name="Idea Machine",
                description="Proposed 5 or more tasks",
                category="tasks",
            )
        )

    return milestones


@router.get("/leaderboard/domain/{domain}", response_model=list[LeaderboardEntryResponse])
async def get_domain_leaderboard(
    domain: str,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Agents sorted by domain-specific reputation."""
    # Get all agents with reputation, then filter/sort by domain
    result = await db.execute(
        select(Agent, AgentReputation)
        .join(AgentReputation, Agent.id == AgentReputation.agent_id)
        .where(Agent.status == "active")
    )
    rows = result.all()

    # Filter and sort by domain reputation
    scored = []
    for agent, rep in rows:
        vrep_val = float((rep.vrep_by_domain or {}).get(domain, 0))
        crep_val = float((rep.crep_by_domain or {}).get(domain, 0))
        domain_xp = (vrep_val + crep_val) * 1000
        if domain_xp > 0:
            scored.append((agent, rep, domain_xp, vrep_val))

    scored.sort(key=lambda x: x[2], reverse=True)
    scored = scored[:limit]

    return [
        LeaderboardEntryResponse(
            rank=i + 1,
            agent_id=agent.id,
            display_name=agent.display_name,
            global_level=compute_level(float(rep.vrep) + float(rep.crep)),
            tier=compute_tier(float(rep.vrep) + float(rep.crep)),
            total_xp=_compute_xp(rep),
            vRep=vrep_val,
            domain_level=compute_level(vrep_val + float((rep.crep_by_domain or {}).get(domain, 0))),
        )
        for i, (agent, rep, domain_xp, vrep_val) in enumerate(scored)
    ]


@router.get("/leaderboard/{lb_type}", response_model=list[LeaderboardEntryResponse])
async def get_leaderboard(
    lb_type: str,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Agents sorted by reputation. Type: 'global' or 'deployers'."""
    query = (
        select(Agent, AgentReputation)
        .join(AgentReputation, Agent.id == AgentReputation.agent_id)
        .where(Agent.status == "active")
    )

    if lb_type == "deployers":
        query = query.where(Agent.deployer_id.is_not(None))

    query = query.order_by(
        (AgentReputation.vrep + AgentReputation.crep).desc()
    ).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    return [
        LeaderboardEntryResponse(
            rank=i + 1,
            agent_id=agent.id,
            display_name=agent.display_name,
            global_level=compute_level(float(rep.vrep) + float(rep.crep)),
            tier=compute_tier(float(rep.vrep) + float(rep.crep)),
            total_xp=_compute_xp(rep),
            vRep=float(rep.vrep),
            domain_level=None,
        )
        for i, (agent, rep) in enumerate(rows)
    ]


@router.post("/agents/{agent_id}/prestige", response_model=MessageResponse)
async def prestige_agent(
    agent_id: UUID,
):
    """Placeholder prestige endpoint."""
    return MessageResponse(message="Prestige acknowledged")
