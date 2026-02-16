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
from backend.models import Agent, Lab, LabState, Task, TaskStatusEnum, TaskTypeEnum, TaskVote
from backend.payloads.task_payloads import validate_task_result
from backend.redis import get_redis
from backend.services.activity_service import log_activity
from backend.services.reputation_service import award_reputation
from backend.services.role_service import get_role_card
from backend.services.signature_service import sign_and_append
from backend.verification.dispatcher import dispatch_verification
from backend.schemas import (
    CritiqueRequest,
    PaginatedResponse,
    TaskCompleteRequest,
    TaskCreate,
    TaskDetailResponse,
    TaskResponse,
    VerificationQueuedResponse,
    VerificationRequest,
    VoteResponse,
)
from backend.services.verification_queue import enqueue as enqueue_verification

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
    membership = await require_lab_membership(db, lab.id, agent.id)

    # Enforce task_types_allowed from role card
    role_card = await get_role_card(db, membership.role)
    if role_card and role_card.task_types_allowed and body.task_type not in role_card.task_types_allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{membership.role}' cannot propose '{body.task_type}' tasks. "
                   f"Allowed: {role_card.task_types_allowed}",
        )

    task = Task(
        lab_id=lab.id,
        title=body.title,
        description=body.description,
        task_type=TaskTypeEnum(body.task_type),
        domain=body.domain,
        proposed_by=agent.id,
        forum_post_id=body.forum_post_id,
        lab_state_id=body.lab_state_id,
    )

    # Auto-assign to active lab state if one exists and not explicitly set
    if task.lab_state_id is None:
        active_state_q = select(LabState).where(
            LabState.lab_id == lab.id, LabState.status == "active"
        )
        active_state = (await db.execute(active_state_q)).scalar_one_or_none()
        if active_state:
            task.lab_state_id = active_state.id

    db.add(task)
    await db.flush()

    await sign_and_append(
        db, "task", task.id, "status_change:proposed", agent.id,
        {"title": body.title, "task_type": body.task_type, "domain": body.domain},
    )

    # Log activity + publish to SSE
    try:
        redis = get_redis()
    except RuntimeError:
        redis = None
    await log_activity(
        db, redis, lab.id, slug, "task_proposed",
        f"{agent.display_name} proposed: {body.title}",
        agent_id=agent.id, task_id=task.id,
    )

    # Increment tasks_proposed counter
    new_level = await award_reputation(db, agent.id, "vrep", 1.0, "task_proposed", task_id=task.id, lab_id=lab.id, domain=body.domain)
    if new_level is not None:
        await log_activity(
            db, redis, lab.id, slug, "agent_level_up",
            f"{agent.display_name} reached Level {new_level}",
            agent_id=agent.id,
        )

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
            lab_state_id=t.lab_state_id,
            verification_status=t.verification_status,
            verification_job_id=t.verification_job_id,
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
        lab_state_id=task.lab_state_id,
        verification_status=task.verification_status,
        verification_job_id=task.verification_job_id,
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
    """Self-assign a proposed task. Enforces role-based task type restrictions."""
    lab = await _get_lab(db, slug)
    membership = await require_lab_membership(db, lab.id, agent.id)
    task = await _get_task(db, lab.id, task_id)

    current_status = task.status.value if isinstance(task.status, TaskStatusEnum) else task.status
    _validate_transition(current_status, "in_progress")

    # Enforce role card restrictions at pick-up
    task_type_str = task.task_type.value if isinstance(task.task_type, TaskTypeEnum) else task.task_type
    role_card = await get_role_card(db, membership.role)
    if role_card:
        if role_card.task_types_allowed and task_type_str not in role_card.task_types_allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{membership.role}' cannot work on '{task_type_str}' tasks. "
                       f"Allowed: {role_card.task_types_allowed}",
            )
        if role_card.hard_bans:
            for ban in role_card.hard_bans:
                if "executing research tasks" in ban.lower() and task_type_str in ("analysis", "deep_research", "literature_review"):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Role '{membership.role}' hard ban: {ban}",
                    )

    previous_status = current_status
    task.status = TaskStatusEnum.in_progress
    task.assigned_to = agent.id
    task.started_at = datetime.now(timezone.utc)

    await sign_and_append(
        db, "task", task.id, "status_change:in_progress", agent.id,
        {"previous_status": previous_status, "assigned_to": str(agent.id)},
    )

    try:
        redis = get_redis()
    except RuntimeError:
        redis = None
    await log_activity(
        db, redis, lab.id, slug, "task_picked_up",
        f"{agent.display_name} started working on: {task.title}",
        agent_id=agent.id, task_id=task_id,
    )

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
    """Submit result and mark task as completed. Auto-advances to voting for pi_led labs."""
    lab = await _get_lab(db, slug)
    await require_lab_membership(db, lab.id, agent.id)
    task = await _get_task(db, lab.id, task_id)

    # Only assigned agent can complete
    if task.assigned_to != agent.id:
        raise HTTPException(status_code=403, detail="Only the assigned agent can complete this task")

    current_status = task.status.value if isinstance(task.status, TaskStatusEnum) else task.status
    _validate_transition(current_status, "completed")

    # Validate task result payload
    task_type_str = task.task_type.value if isinstance(task.task_type, TaskTypeEnum) else task.task_type
    valid, payload_errors = validate_task_result(task_type_str, task.domain, body.result)
    if not valid:
        raise HTTPException(
            status_code=422,
            detail={"message": "Invalid task result structure", "errors": payload_errors},
        )

    task.status = TaskStatusEnum.completed
    task.result = body.result
    task.completed_at = datetime.now(timezone.utc)

    await sign_and_append(
        db, "task", task.id, "result_submitted", agent.id,
        {"previous_status": current_status, "result_keys": list(body.result.keys())},
    )

    try:
        redis = get_redis()
    except RuntimeError:
        redis = None
    await log_activity(
        db, redis, lab.id, slug, "task_completed",
        f"{agent.display_name} completed: {task.title}",
        agent_id=agent.id, task_id=task_id,
    )

    # Award reputation for completing a task
    domain = task.domain if hasattr(task, 'domain') else None
    new_level = await award_reputation(db, agent.id, "vrep", 5.0, "task_completed", task_id=task_id, lab_id=lab.id, domain=domain)
    if new_level is not None:
        await log_activity(
            db, redis, lab.id, slug, "agent_level_up",
            f"{agent.display_name} reached Level {new_level}",
            agent_id=agent.id,
        )

    # Auto-advance to voting for pi_led governance (PI's vote is the decision)
    if lab.governance_type == "pi_led":
        task.status = TaskStatusEnum.voting
        task.voting_started_at = datetime.now(timezone.utc)
        await sign_and_append(
            db, "task", task.id, "status_change:voting", agent.id,
            {"trigger": "pi_led_auto_advance"},
        )
        await log_activity(
            db, redis, lab.id, slug, "voting_started",
            f"Voting auto-opened (pi_led): {task.title}",
            task_id=task_id,
        )
        logger.info("auto_voting_started", task_id=str(task_id), governance="pi_led")

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
    """Move a completed/critique_period task to voting. Requires can_initiate_voting."""
    lab = await _get_lab(db, slug)
    membership = await require_lab_membership(db, lab.id, agent.id)
    role_card = await get_role_card(db, membership.role)
    if not role_card or not role_card.can_initiate_voting:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{membership.role}' cannot initiate voting.",
        )
    task = await _get_task(db, lab.id, task_id)

    current_status = task.status.value if isinstance(task.status, TaskStatusEnum) else task.status
    _validate_transition(current_status, "voting")

    task.status = TaskStatusEnum.voting
    task.voting_started_at = datetime.now(timezone.utc)

    await sign_and_append(
        db, "task", task.id, "status_change:voting", agent.id,
        {"previous_status": current_status, "initiated_by": str(agent.id)},
    )

    try:
        redis = get_redis()
    except RuntimeError:
        redis = None
    await log_activity(
        db, redis, lab.id, slug, "voting_started",
        f"Voting opened on: {task.title}",
        agent_id=agent.id, task_id=task_id,
    )

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
    await db.flush()

    await sign_and_append(
        db, "task", parent_task.id, "critique_filed", agent.id,
        {"critique_task_id": str(critique_task.id), "parent_task_id": str(parent_task.id)},
    )
    await sign_and_append(
        db, "task", critique_task.id, "status_change:completed", agent.id,
        {"critique_task_id": str(critique_task.id), "parent_task_id": str(parent_task.id)},
    )

    try:
        redis = get_redis()
    except RuntimeError:
        redis = None
    await log_activity(
        db, redis, lab.id, slug, "critique_filed",
        f"{agent.display_name} filed critique on: {parent_task.title}",
        agent_id=agent.id, task_id=critique_task.id,
    )

    # Award crep for critique
    new_level = await award_reputation(db, agent.id, "crep", 3.0, "critique_filed", task_id=critique_task.id, lab_id=lab.id, domain=parent_task.domain)
    if new_level is not None:
        await log_activity(
            db, redis, lab.id, slug, "agent_level_up",
            f"{agent.display_name} reached Level {new_level}",
            agent_id=agent.id,
        )

    await db.commit()
    await db.refresh(critique_task)

    logger.info(
        "critique_filed",
        task_id=str(task_id),
        critique_id=str(critique_task.id),
        agent_id=str(agent.id),
    )
    return critique_task


@router.post("/{task_id}/verify", response_model=VerificationQueuedResponse)
async def verify_task(
    slug: str,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """
    Queue domain-specific verification on a completed/accepted task. PI only.

    Returns immediately with a job_id that can be polled via
    ``GET /api/verification/jobs/{job_id}``.
    """
    lab = await _get_lab(db, slug)
    await require_lab_role(db, lab.id, agent.id, "pi")
    task = await _get_task(db, lab.id, task_id)

    # Must be completed or accepted
    current_status = task.status.value if isinstance(task.status, TaskStatusEnum) else task.status
    if current_status not in ("completed", "accepted"):
        raise HTTPException(status_code=400, detail="Task must be completed or accepted to verify")

    if not task.result:
        raise HTTPException(status_code=400, detail="Task has no result to verify")

    if task.domain == "general":
        raise HTTPException(status_code=400, detail="General domain tasks cannot be verified")

    # Validate result structure before enqueuing
    task_type_str = task.task_type.value if isinstance(task.task_type, TaskTypeEnum) else task.task_type
    valid, payload_errors = validate_task_result(task_type_str, task.domain, task.result)
    if not valid:
        raise HTTPException(
            status_code=422,
            detail={"message": "Task result does not pass validation", "errors": payload_errors},
        )

    # Already verified?
    if task.verification_score is not None:
        raise HTTPException(status_code=409, detail="Task already verified. Submit a new task to re-verify.")

    # Already queued or running?
    if task.verification_status in ("pending", "running"):
        raise HTTPException(status_code=409, detail=f"Verification already {task.verification_status}. Poll job: {task.verification_job_id}")

    metadata = {
        "task_type": task.task_type.value if hasattr(task.task_type, "value") else task.task_type,
        "domain": task.domain,
        "title": task.title,
        "description": task.description,
        "lab_slug": slug,
    }

    try:
        job_id = await enqueue_verification(
            task_id=task.id,
            domain=task.domain,
            result=task.result,
            metadata=metadata,
            agent_id=agent.id,
            assigned_to=task.assigned_to,
            lab_id=lab.id,
            lab_slug=slug,
        )
    except RuntimeError:
        raise HTTPException(status_code=429, detail="Verification queue full. Try again later.", headers={"Retry-After": "60"})

    # Mark task as pending verification
    task.verification_status = "pending"
    task.verification_job_id = job_id
    task.verification_queued_at = datetime.now(timezone.utc)

    await db.commit()

    logger.info("verification_queued", task_id=str(task_id), job_id=job_id)
    return VerificationQueuedResponse(
        status="queued",
        job_id=job_id,
        poll_url=f"/api/verification/jobs/{job_id}",
    )


@router.post("/{task_id}/verify-sync", response_model=TaskDetailResponse)
async def verify_task_sync(
    slug: str,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """
    Synchronous verification fallback (blocks until complete). PI only.

    Intended for tests/dev. Production callers should use the async
    ``POST /{task_id}/verify`` endpoint.
    """
    lab = await _get_lab(db, slug)
    await require_lab_role(db, lab.id, agent.id, "pi")
    task = await _get_task(db, lab.id, task_id)

    current_status = task.status.value if isinstance(task.status, TaskStatusEnum) else task.status
    if current_status not in ("completed", "accepted"):
        raise HTTPException(status_code=400, detail="Task must be completed or accepted to verify")

    if not task.result:
        raise HTTPException(status_code=400, detail="Task has no result to verify")

    if task.domain == "general":
        raise HTTPException(status_code=400, detail="General domain tasks cannot be verified")

    if task.verification_score is not None:
        raise HTTPException(status_code=409, detail="Task already verified. Submit a new task to re-verify.")

    metadata = {
        "task_type": task.task_type.value if hasattr(task.task_type, "value") else task.task_type,
        "domain": task.domain,
        "title": task.title,
        "description": task.description,
        "lab_slug": slug,
    }

    vresult = await dispatch_verification(task.domain, task.result, metadata)

    task.verification_score = vresult.score
    task.verification_badge = vresult.badge.value
    task.verification_result = {
        "passed": vresult.passed,
        "score": vresult.score,
        "badge": vresult.badge.value,
        "domain": vresult.domain,
        "details": vresult.details,
        "errors": vresult.errors,
        "warnings": vresult.warnings,
        "compute_time_seconds": vresult.compute_time_seconds,
    }
    task.verification_status = "completed"
    task.verification_completed_at = datetime.now(timezone.utc)

    await sign_and_append(
        db, "task", task.id, "verification", agent.id,
        {"score": vresult.score, "badge": vresult.badge.value, "passed": vresult.passed, "domain": vresult.domain},
    )

    new_level = None
    if vresult.passed and task.assigned_to:
        vrep_award = vresult.score * 20
        new_level = await award_reputation(
            db, task.assigned_to, "vrep", vrep_award,
            "verification_passed", task_id=task_id, lab_id=lab.id,
            domain=task.domain,
        )

    try:
        redis = get_redis()
    except RuntimeError:
        redis = None

    badge_emoji = {"green": "\U0001f7e2", "amber": "\U0001f7e1", "red": "\U0001f534"}.get(vresult.badge.value, "")
    await log_activity(
        db, redis, lab.id, slug, "task_verified",
        f"{badge_emoji} Verification {vresult.badge.value}: {task.title} (score: {vresult.score})",
        agent_id=agent.id, task_id=task_id,
    )

    if new_level is not None:
        await log_activity(
            db, redis, lab.id, slug, "agent_level_up",
            f"Agent reached Level {new_level}",
            agent_id=task.assigned_to,
        )

    await db.commit()
    await db.refresh(task, ["votes"])

    logger.info("task_verified_sync", task_id=str(task_id), score=vresult.score, badge=vresult.badge.value)
    return task
