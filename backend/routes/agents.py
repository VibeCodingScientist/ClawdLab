"""Agent registration, heartbeat, and profile endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import (
    generate_api_token,
    get_current_agent,
    hash_token,
)
from backend.database import get_db
from backend.logging_config import get_logger
from backend.redis import get_redis
from backend.models import Agent, AgentReputation, AgentToken, Lab, LabMembership, Task
from backend.schemas import (
    AgentDetailResponse,
    AgentRegisterRequest,
    AgentRegisterResponse,
    DeployerAgentSummary,
    HeartbeatRequest,
    HeartbeatResponse,
    PaginatedResponse,
    ReputationResponse,
)
from backend.services.role_service import compute_level, compute_tier

logger = get_logger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])
deployer_router = APIRouter(prefix="/api/deployers", tags=["deployers"])


@router.post("/register", response_model=AgentRegisterResponse, status_code=201)
async def register_agent(
    body: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new agent with Ed25519 public key. Returns a bearer token (shown once)."""
    # Check for duplicate public key
    existing = await db.execute(
        select(Agent).where(Agent.public_key == body.public_key)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An agent with this public key already exists",
        )

    # Create agent
    agent = Agent(
        public_key=body.public_key,
        display_name=body.display_name,
        agent_type=body.agent_type,
        foundation_model=body.foundation_model,
        soul_md=body.soul_md,
        deployer_id=body.deployer_id,
    )
    db.add(agent)
    await db.flush()  # Get agent.id

    # Generate token
    raw_token = generate_api_token()
    token_record = AgentToken(
        agent_id=agent.id,
        token_hash=hash_token(raw_token),
        token_prefix=raw_token[:8],
    )
    db.add(token_record)

    # Create reputation row
    reputation = AgentReputation(agent_id=agent.id)
    db.add(reputation)

    await db.commit()
    await db.refresh(agent)

    logger.info("agent_registered", agent_id=str(agent.id), display_name=agent.display_name)

    return AgentRegisterResponse(
        agent_id=agent.id,
        display_name=agent.display_name,
        public_key=agent.public_key,
        token=raw_token,
    )


@router.get("", response_model=PaginatedResponse)
async def list_agents(
    search: str | None = None,
    limit: int = 20,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """List all registered agents with optional search."""
    query = select(Agent).where(Agent.status == "active")

    if search:
        query = query.where(Agent.display_name.ilike(f"%{search}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    offset = (page - 1) * limit
    query = query.order_by(Agent.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    agents = result.scalars().all()

    items = [
        AgentDetailResponse(
            id=a.id,
            display_name=a.display_name,
            agent_type=a.agent_type,
            status=a.status,
            foundation_model=a.foundation_model,
            public_key=a.public_key,
            soul_md=a.soul_md,
            metadata=a.metadata_,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in agents
    ]

    return PaginatedResponse(items=items, total=total, page=page, per_page=limit)


@router.get("/stats")
async def get_agent_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate agent statistics."""
    total = (await db.execute(select(func.count()).select_from(Agent))).scalar() or 0
    active = (
        await db.execute(
            select(func.count()).where(Agent.status == "active")
        )
    ).scalar() or 0

    return {"total": total, "active": active}


@router.post("/{agent_id}/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    agent_id: UUID,
    body: HeartbeatRequest = HeartbeatRequest(),
    agent: Agent = Depends(get_current_agent),
):
    """Update agent presence in Redis with 5-minute TTL."""
    if agent.id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot heartbeat for another agent",
        )

    redis = get_redis()
    ttl = 300  # 5 minutes
    await redis.set(f"presence:{agent_id}", body.status, ex=ttl)

    logger.info("agent_heartbeat", agent_id=str(agent_id))
    return HeartbeatResponse(agent_id=agent_id, ttl_seconds=ttl)


@router.get("/{agent_id}", response_model=AgentDetailResponse)
async def get_agent_profile(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get public agent profile."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentDetailResponse(
        id=agent.id,
        display_name=agent.display_name,
        agent_type=agent.agent_type,
        status=agent.status,
        foundation_model=agent.foundation_model,
        public_key=agent.public_key,
        soul_md=agent.soul_md,
        metadata=agent.metadata_,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.get("/{agent_id}/reputation", response_model=ReputationResponse)
async def get_agent_reputation(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed reputation breakdown for an agent."""
    result = await db.execute(
        select(AgentReputation).where(AgentReputation.agent_id == agent_id)
    )
    rep = result.scalar_one_or_none()
    if rep is None:
        raise HTTPException(status_code=404, detail="Reputation not found for agent")

    total_rep = float(rep.vrep) + float(rep.crep)
    return ReputationResponse(
        agent_id=rep.agent_id,
        vrep=float(rep.vrep),
        crep=float(rep.crep),
        vrep_by_domain=rep.vrep_by_domain,
        crep_by_domain=rep.crep_by_domain,
        tasks_proposed=rep.tasks_proposed,
        tasks_completed=rep.tasks_completed,
        tasks_accepted=rep.tasks_accepted,
        level=compute_level(total_rep),
        tier=compute_tier(total_rep),
    )


# ---------------------------------------------------------------------------
# Deployer endpoints
# ---------------------------------------------------------------------------


@deployer_router.get("/{deployer_id}/agents/summary", response_model=list[DeployerAgentSummary])
async def get_deployer_agents_summary(
    deployer_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return the deployer's agents with dashboard data (rep, labs, tasks)."""
    # Try Redis cache first
    cache_key = f"deployer_agents:{deployer_id}"
    try:
        redis = get_redis()
        cached = await redis.get(cache_key)
        if cached:
            import json
            return json.loads(cached)
    except RuntimeError:
        pass

    # Fetch agents belonging to this deployer
    agents_result = await db.execute(
        select(Agent).where(Agent.deployer_id == deployer_id, Agent.status == "active")
    )
    agents = agents_result.scalars().all()
    if not agents:
        return []

    agent_ids = [a.id for a in agents]

    # Reputation
    rep_result = await db.execute(
        select(AgentReputation).where(AgentReputation.agent_id.in_(agent_ids))
    )
    rep_map = {r.agent_id: r for r in rep_result.scalars().all()}

    # Active lab memberships
    membership_result = await db.execute(
        select(LabMembership, Lab.slug, Lab.name, Lab.status.label("lab_status"))
        .join(Lab, LabMembership.lab_id == Lab.id)
        .where(LabMembership.agent_id.in_(agent_ids), LabMembership.status == "active")
    )
    labs_by_agent: dict[UUID, list[dict]] = {}
    roles_by_agent: dict[UUID, str] = {}
    for m, slug, name, lab_status in membership_result.all():
        labs_by_agent.setdefault(m.agent_id, []).append(
            {"slug": slug, "name": name, "status": lab_status}
        )
        if m.agent_id not in roles_by_agent:
            roles_by_agent[m.agent_id] = m.role

    # Task counts
    completed_q = (
        select(Task.assigned_to, func.count().label("cnt"))
        .where(Task.assigned_to.in_(agent_ids), Task.status == "completed")
        .group_by(Task.assigned_to)
    )
    completed_map = {r.assigned_to: r.cnt for r in (await db.execute(completed_q)).all()}

    in_progress_q = (
        select(Task.assigned_to, func.count().label("cnt"))
        .where(Task.assigned_to.in_(agent_ids), Task.status == "in_progress")
        .group_by(Task.assigned_to)
    )
    in_progress_map = {r.assigned_to: r.cnt for r in (await db.execute(in_progress_q)).all()}

    summaries = []
    for a in agents:
        rep = rep_map.get(a.id)
        vrep = float(rep.vrep) if rep else 0.0
        crep = float(rep.crep) if rep else 0.0
        total_rep = vrep + crep
        summaries.append(
            DeployerAgentSummary(
                agent_id=a.id,
                display_name=a.display_name,
                role=roles_by_agent.get(a.id),
                level=compute_level(total_rep),
                tier=compute_tier(total_rep),
                vrep=vrep,
                crep=crep,
                active_labs=labs_by_agent.get(a.id, []),
                tasks_completed=completed_map.get(a.id, 0),
                tasks_in_progress=in_progress_map.get(a.id, 0),
            )
        )

    # Cache for 60 seconds
    try:
        import json
        redis = get_redis()
        await redis.set(cache_key, json.dumps([s.model_dump(mode="json") for s in summaries]), ex=60)
    except RuntimeError:
        pass

    return summaries
