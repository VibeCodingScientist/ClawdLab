"""Task lifecycle endpoints — propose, pick-up, complete, critique."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_current_agent, require_lab_membership, require_lab_role
from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Agent, Lab, Task, TaskStatusEnum, TaskTypeEnum, TaskVote
from backend.schemas import (
    CritiqueRequest,
    PaginatedResponse,
    TaskCompleteRequest,
    TaskCreate,
    TaskDetailResponse,
    TaskResponse,
    VoteResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/labs/{slug}/tasks", tags=["tasks"])

# State machine transitions
VALID_TRANSITIONS: dict[str, list[str]] = {
    "proposed": ["in_progress"],
    "in_progress": ["completed"],
    "completed": ["critique_period", "voting"],
    "critique_period": ["voting"],
    "voting": ["accepted", "rejected"],
}


async def _get_lab(db: AsyncSession, slug: str) -> Lab:
    result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    return lab


async def _get_task(db: AsyncSession, lab_id: UUID, task_id: UUID) -> Task:
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.lab_id == lab_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _validate_transition(current: str, target: str) -> None:
    allowed = VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {current} -> {target}. Allowed: {allowed}",
        )


@router.post("", response_model=TaskResponse, status_code=201)
async def propose_task(
    slug: str,
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Propose a new task in a lab. Must be a member."""
    lab = await _get_lab(db, slug)
    await require_lab_membership(db, lab.id, agent.id)

    task = Task(
        lab_id=lab.id,
        title=body.title,
        description=body.description,
        task_type=TaskTypeEnum(body.task_type),
        domain=body.domain,
        proposed_by=agent.id,
        forum_post_id=body.forum_post_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    logger.info("task_proposed", task_id=str(task.id), lab_slug=slug)
    return task


@router.get("", response_model=PaginatedResponse)
async def list_tasks(
    slug: str,
    status_filter: str | None = Query(None, alias="status"),
    task_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List tasks in a lab with optional filters."""
    lab = await _get_lab(db, slug)

    query = select(Task).where(Task.lab_id == lab.id)
    if status_filter:
        query = query.where(Task.status == TaskStatusEnum(status_filter))
    if task_type:
        query = query.where(Task.task_type == TaskTypeEnum(task_type))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Task.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    tasks = result.scalars().all()

    items = [
        TaskResponse(
            id=t.id,
            lab_id=t.lab_id,
            title=t.title,
            description=t.description,
            task_type=t.task_type.value if isinstance(t.task_type, TaskTypeEnum) else t.task_type,
            status=t.status.value if isinstance(t.status, TaskStatusEnum) else t.status,
            domain=t.domain,
            proposed_by=t.proposed_by,
            assigned_to=t.assigned_to,
            parent_task_id=t.parent_task_id,
            forum_post_id=t.forum_post_id,
            created_at=t.created_at,
            started_at=t.started_at,
            completed_at=t.completed_at,
            voting_started_at=t.voting_started_at,
            resolved_at=t.resolved_at,
        )
        for t in tasks
    ]

    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail(
    slug: str,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get task detail with votes."""
    lab = await _get_lab(db, slug)
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id, Task.lab_id == lab.id)
        .options(selectinload(Task.votes))
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    votes = [
        VoteResponse(
            id=v.id,
            task_id=v.task_id,
            agent_id=v.agent_id,
            vote=v.vote,
            reasoning=v.reasoning,
            created_at=v.created_at,
        )
        for v in task.votes
    ]

    return TaskDetailResponse(
        id=task.id,
        lab_id=task.lab_id,
        title=task.title,
        description=task.description,
        task_type=task.task_type.value if isinstance(task.task_type, TaskTypeEnum) else task.task_type,
        status=task.status.value if isinstance(task.status, TaskStatusEnum) else task.status,
        domain=task.domain,
        proposed_by=task.proposed_by,
        assigned_to=task.assigned_to,
        parent_task_id=task.parent_task_id,
        forum_post_id=task.forum_post_id,
        result=task.result,
        verification_score=float(task.verification_score) if task.verification_score else None,
        verification_badge=task.verification_badge,
        votes=votes,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        voting_started_at=task.voting_started_at,
        resolved_at=task.resolved_at,
    )


@router.patch("/{task_id}/pick-up", response_model=TaskResponse)
async def pick_up_task(
    slug: str,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Self-assign a proposed task."""
    lab = await _get_lab(db, slug)
    await require_lab_membership(db, lab.id, agent.id)
    task = await _get_task(db, lab.id, task_id)

    current_status = task.status.value if isinstance(task.status, TaskStatusEnum) else task.status
    _validate_transition(current_status, "in_progress")

    task.status = TaskStatusEnum.in_progress
    task.assigned_to = agent.id
    task.started_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(task)

    logger.info("task_picked_up", task_id=str(task_id), agent_id=str(agent.id))
    return task


@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    slug: str,
    task_id: UUID,
    body: TaskCompleteRequest,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Submit result and mark task as completed."""
    lab = await _get_lab(db, slug)
    task = await _get_task(db, lab.id, task_id)

    # Only assigned agent can complete
    if task.assigned_to != agent.id:
        raise HTTPException(status_code=403, detail="Only the assigned agent can complete this task")

    current_status = task.status.value if isinstance(task.status, TaskStatusEnum) else task.status
    _validate_transition(current_status, "completed")

    task.status = TaskStatusEnum.completed
    task.result = body.result
    task.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(task)

    logger.info("task_completed", task_id=str(task_id), agent_id=str(agent.id))
    return task


@router.patch("/{task_id}/start-voting", response_model=TaskResponse)
async def start_voting(
    slug: str,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """PI moves a completed/critique_period task to voting."""
    lab = await _get_lab(db, slug)
    await require_lab_role(db, lab.id, agent.id, "pi")
    task = await _get_task(db, lab.id, task_id)

    current_status = task.status.value if isinstance(task.status, TaskStatusEnum) else task.status
    _validate_transition(current_status, "voting")

    task.status = TaskStatusEnum.voting
    task.voting_started_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(task)

    logger.info("voting_started", task_id=str(task_id), started_by=str(agent.id))
    return task


@router.post("/{task_id}/critique", response_model=TaskResponse, status_code=201)
async def file_critique(
    slug: str,
    task_id: UUID,
    body: CritiqueRequest,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """File a critique on a completed task. Creates a child critique task."""
    lab = await _get_lab(db, slug)
    await require_lab_membership(db, lab.id, agent.id)
    parent_task = await _get_task(db, lab.id, task_id)

    parent_status = parent_task.status.value if isinstance(parent_task.status, TaskStatusEnum) else parent_task.status
    if parent_status not in ("completed", "critique_period"):
        raise HTTPException(
            status_code=400,
            detail="Can only critique tasks in 'completed' or 'critique_period' status",
        )

    # Move parent to critique_period if it was just completed
    if parent_status == "completed":
        parent_task.status = TaskStatusEnum.critique_period

    # Create the critique child task
    critique_task = Task(
        lab_id=lab.id,
        title=body.title,
        description=body.description,
        task_type=TaskTypeEnum.critique,
        domain=parent_task.domain,
        proposed_by=agent.id,
        assigned_to=agent.id,
        parent_task_id=parent_task.id,
        status=TaskStatusEnum.completed,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        result={
            "target_task_id": str(parent_task.id),
            "issues": body.issues,
            "alternative": body.alternative_task,
        },
    )
    db.add(critique_task)
    await db.commit()
    await db.refresh(critique_task)

    logger.info(
        "critique_filed",
        task_id=str(task_id),
        critique_id=str(critique_task.id),
        agent_id=str(agent.id),
    )
    return critique_task
