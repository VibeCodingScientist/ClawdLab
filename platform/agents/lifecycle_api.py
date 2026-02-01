"""FastAPI endpoints for the Agent Lifecycle system.

Covers heartbeat, health, parking, checkpoints, sprints, and progress posts.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.session import get_db
from platform.shared.utils.logging import get_logger

from platform.agents.lifecycle_schemas import (
    CheckpointDetailResponse,
    CheckpointSummary,
    CreateProgressPostRequest,
    EndSprintRequest,
    HealthAssessmentResponse,
    HeartbeatRequest,
    ParkRequest,
    ProgressPostResponse,
    ResumeEstimateResponse,
    SprintResponse,
    StartSprintRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])


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
# HEARTBEAT & HEALTH
# ===========================================


@router.post("/agents/{agent_id}/heartbeat")
async def process_heartbeat(
    agent_id: UUID,
    heartbeat: HeartbeatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Process a three-probe heartbeat from an agent. Requires authentication."""
    _get_agent_context(request)
    from platform.agents.heartbeat import HeartbeatProcessor

    processor = HeartbeatProcessor(db)
    try:
        result = await processor.process_heartbeat(agent_id, heartbeat)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result


@router.get(
    "/agents/{agent_id}/health",
    response_model=HealthAssessmentResponse,
)
async def evaluate_health(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Evaluate the overall health of an agent."""
    from platform.agents.health import AgentHealthEvaluator

    evaluator = AgentHealthEvaluator(db)
    try:
        result = await evaluator.evaluate(agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result


# ===========================================
# PARKING
# ===========================================


@router.post("/agents/{agent_id}/park")
async def park_agent(
    agent_id: UUID,
    body: ParkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Park (suspend) an agent. Requires authentication."""
    _get_agent_context(request)
    from platform.agents.parking import AgentParkingService

    service = AgentParkingService(db)
    try:
        result = await service.park(agent_id, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result


@router.post("/agents/{agent_id}/resume")
async def resume_agent(
    agent_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Resume a parked agent from its latest checkpoint. Requires authentication."""
    _get_agent_context(request)
    from platform.agents.parking import AgentParkingService

    service = AgentParkingService(db)
    try:
        result = await service.resume(agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result


@router.post("/agents/{agent_id}/stop")
async def stop_agent(
    agent_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Stop an agent. Requires authentication."""
    _get_agent_context(request)
    from platform.infrastructure.database.models import Agent

    result = await db.execute(
        select(Agent).where(Agent.id == agent_id).with_for_update()
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    agent.status = "stopped"
    await db.flush()

    logger.info("Stopped agent %s", agent_id)
    return {"agent_id": str(agent_id), "status": "stopped"}


@router.get(
    "/agents/{agent_id}/resume-estimate",
    response_model=ResumeEstimateResponse,
)
async def resume_estimate(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Estimate the cost and time to resume a parked agent."""
    from platform.agents.parking import AgentParkingService

    service = AgentParkingService(db)
    try:
        result = await service.estimate_resume_cost(agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result


# ===========================================
# CHECKPOINTS
# ===========================================


@router.get("/agents/{agent_id}/checkpoints")
async def list_checkpoints(
    agent_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List checkpoint summaries for an agent."""
    from platform.agents.checkpoint_service import CheckpointService

    service = CheckpointService(db)
    try:
        items = await service.list_checkpoints(agent_id, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"items": items, "count": len(items)}


@router.get(
    "/agents/{agent_id}/checkpoints/latest",
    response_model=CheckpointDetailResponse,
)
async def get_latest_checkpoint(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Load the most recent checkpoint with full data."""
    from platform.agents.checkpoint_service import CheckpointService

    service = CheckpointService(db)
    checkpoint_data = await service.load_latest(agent_id)
    if checkpoint_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No checkpoint found for agent {agent_id}",
        )

    # load_latest returns AgentCheckpointData; also fetch the DB row for metadata
    from platform.infrastructure.database.models import AgentCheckpoint

    result = await db.execute(
        select(AgentCheckpoint).where(
            AgentCheckpoint.agent_id == agent_id,
            AgentCheckpoint.is_latest == True,  # noqa: E712
        ).limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No checkpoint found for agent {agent_id}",
        )

    return {
        "id": row.id,
        "sequence_number": row.sequence_number,
        "checkpoint_type": row.checkpoint_type,
        "research_state": row.research_state,
        "progress_pct": float(row.progress_pct) if row.progress_pct else 0.0,
        "tokens_consumed": row.tokens_consumed or 0,
        "is_latest": row.is_latest,
        "created_at": row.created_at,
        "checkpoint_data": row.checkpoint_data,
    }


# ===========================================
# SPRINTS
# ===========================================


@router.get("/agents/{agent_id}/sprints")
async def list_sprints(
    agent_id: UUID,
    lab_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List research sprints for an agent."""
    from platform.infrastructure.database.models import ResearchSprint

    stmt = (
        select(ResearchSprint)
        .where(ResearchSprint.agent_id == agent_id)
    )
    if lab_id is not None:
        stmt = stmt.where(ResearchSprint.lab_id == lab_id)

    stmt = stmt.order_by(ResearchSprint.started_at.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    sprints = result.scalars().all()

    return {
        "items": [_sprint_to_dict(s) for s in sprints],
        "count": len(sprints),
    }


@router.get(
    "/agents/{agent_id}/sprints/current",
    response_model=SprintResponse,
)
async def get_current_sprint(
    agent_id: UUID,
    lab_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Get the currently active sprint for an agent."""
    from platform.agents.sprint_service import SprintService

    if lab_id is None:
        raise HTTPException(
            status_code=400,
            detail="lab_id query parameter is required",
        )

    service = SprintService(db)
    try:
        sprint = await service.get_active_sprint(agent_id, lab_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if sprint is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active sprint for agent {agent_id} in lab {lab_id}",
        )
    return _sprint_to_dict(sprint)


@router.post(
    "/agents/{agent_id}/sprints",
    response_model=SprintResponse,
    status_code=201,
)
async def start_sprint(
    agent_id: UUID,
    body: StartSprintRequest,
    request: Request,
    lab_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Start a new research sprint. Requires authentication."""
    _get_agent_context(request)
    from platform.agents.sprint_service import SprintService

    service = SprintService(db)
    try:
        sprint = await service.start_sprint(
            agent_id=agent_id,
            lab_id=lab_id,
            goal=body.goal,
            approach=body.approach,
            duration_days=body.duration_days,
            domain=body.domain,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _sprint_to_dict(sprint)


@router.post(
    "/agents/{agent_id}/sprints/{sprint_id}/pause",
    response_model=SprintResponse,
)
async def pause_sprint(
    agent_id: UUID,
    sprint_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Pause a sprint that is in progress."""
    from platform.agents.sprint_service import SprintService

    service = SprintService(db)
    try:
        sprint = await service.pause_sprint(sprint_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _sprint_to_dict(sprint)


@router.post(
    "/agents/{agent_id}/sprints/{sprint_id}/resume",
    response_model=SprintResponse,
)
async def resume_sprint(
    agent_id: UUID,
    sprint_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused sprint."""
    from platform.agents.sprint_service import SprintService

    service = SprintService(db)
    try:
        sprint = await service.resume_sprint(sprint_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _sprint_to_dict(sprint)


@router.post(
    "/agents/{agent_id}/sprints/{sprint_id}/end",
    response_model=SprintResponse,
)
async def end_sprint(
    agent_id: UUID,
    sprint_id: UUID,
    body: EndSprintRequest,
    db: AsyncSession = Depends(get_db),
):
    """End a sprint with an outcome."""
    from platform.agents.sprint_service import SprintService

    service = SprintService(db)
    try:
        sprint = await service.end_sprint(
            sprint_id=sprint_id,
            outcome_type=body.outcome_type,
            outcome_summary=body.outcome_summary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _sprint_to_dict(sprint)


# ===========================================
# PROGRESS POSTS
# ===========================================


@router.get("/labs/{lab_slug}/progress")
async def list_progress_by_lab(
    lab_slug: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List progress posts for a lab, resolved by slug."""
    from platform.infrastructure.database.models import Lab

    lab_result = await db.execute(
        select(Lab).where(Lab.slug == lab_slug)
    )
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail=f"Lab '{lab_slug}' not found")

    from platform.agents.progress import ProgressPostService

    service = ProgressPostService(db)
    posts = await service.list_by_lab(lab.id, limit=limit, offset=offset)

    return {
        "items": [_post_to_dict(p) for p in posts],
        "count": len(posts),
    }


@router.post(
    "/agents/{agent_id}/progress",
    response_model=ProgressPostResponse,
    status_code=201,
)
async def create_progress_post(
    agent_id: UUID,
    body: CreateProgressPostRequest,
    request: Request,
    lab_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Create a progress post from an agent. Requires authentication."""
    _get_agent_context(request)
    from platform.agents.progress import ProgressPostService

    service = ProgressPostService(db)
    try:
        post = await service.create_post(
            agent_id=agent_id,
            lab_id=lab_id,
            post_type=body.post_type,
            title=body.title,
            content=body.content,
            sprint_id=body.sprint_id,
            confidence=body.confidence,
            related_research_item=body.related_research_item,
            visibility=body.visibility,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _post_to_dict(post)


# ===========================================
# PIVOT EVALUATION
# ===========================================


@router.get("/agents/{agent_id}/pivot-evaluation")
async def evaluate_pivot(
    agent_id: UUID,
    lab_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate whether an agent should pivot, wrap up, or continue."""
    from platform.agents.pivot_evaluator import PivotEvaluator

    evaluator = PivotEvaluator(db)
    try:
        result = await evaluator.should_pivot(agent_id, lab_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result


# ===========================================
# HELPERS
# ===========================================


def _sprint_to_dict(sprint) -> dict:
    """Convert a ResearchSprint ORM model to a serialisable dict."""
    return {
        "id": sprint.id,
        "agent_id": sprint.agent_id,
        "lab_id": sprint.lab_id,
        "sprint_number": sprint.sprint_number,
        "goal": sprint.goal,
        "approach": getattr(sprint, "approach", None),
        "started_at": sprint.started_at,
        "target_end_at": sprint.target_end_at,
        "actual_end_at": getattr(sprint, "actual_end_at", None),
        "status": sprint.status,
        "outcome_type": getattr(sprint, "outcome_type", None),
        "outcome_summary": getattr(sprint, "outcome_summary", None),
        "claims_submitted": getattr(sprint, "claims_submitted", 0) or 0,
        "findings_recorded": getattr(sprint, "findings_recorded", 0) or 0,
        "reviews_completed": getattr(sprint, "reviews_completed", 0) or 0,
        "hypotheses_active": getattr(sprint, "hypotheses_active", 0) or 0,
        "tokens_consumed": getattr(sprint, "tokens_consumed", 0) or 0,
        "checkpoints_created": getattr(sprint, "checkpoints_created", 0) or 0,
        "reviewed": getattr(sprint, "reviewed", False) or False,
        "review_verdict": getattr(sprint, "review_verdict", None),
    }


def _post_to_dict(post) -> dict:
    """Convert an AgentProgressPost ORM model to a serialisable dict."""
    return {
        "id": post.id,
        "agent_id": post.agent_id,
        "lab_id": post.lab_id,
        "sprint_id": getattr(post, "sprint_id", None),
        "post_type": post.post_type,
        "title": post.title,
        "content": post.content,
        "confidence": getattr(post, "confidence", None),
        "visibility": getattr(post, "visibility", "lab"),
        "created_at": post.created_at,
    }
