"""Agent registration, heartbeat, and profile endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
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
from backend.models import Agent, AgentReputation, AgentToken
from backend.schemas import (
    AgentDetailResponse,
    AgentRegisterRequest,
    AgentRegisterResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    PaginatedResponse,
    ReputationResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


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

    return ReputationResponse(
        agent_id=rep.agent_id,
        vrep=float(rep.vrep),
        crep=float(rep.crep),
        vrep_by_domain=rep.vrep_by_domain,
        crep_by_domain=rep.crep_by_domain,
        tasks_proposed=rep.tasks_proposed,
        tasks_completed=rep.tasks_completed,
        tasks_accepted=rep.tasks_accepted,
    )
