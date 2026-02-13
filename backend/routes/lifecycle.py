"""Agent lifecycle endpoints — sprints and health."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Agent, Task
from backend.redis import get_redis
from backend.schemas import AgentHealthResponse, SprintResponse, TaskResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/api/lifecycle", tags=["lifecycle"])


@router.get("/agents/{agent_id}/sprints", response_model=list[SprintResponse])
async def get_agent_sprints(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Tasks grouped by ISO week for an agent."""
    # Verify agent exists
    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    if agent_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await db.execute(
        select(Task)
        .where(
            (Task.proposed_by == agent_id) | (Task.assigned_to == agent_id)
        )
        .order_by(Task.created_at.desc())
    )
    tasks = result.scalars().all()

    # Group by ISO week
    weeks: dict[str, list] = {}
    for task in tasks:
        iso = task.created_at.isocalendar()
        week_key = f"{iso.year}-W{iso.week:02d}"
        if week_key not in weeks:
            weeks[week_key] = []
        weeks[week_key].append(
            TaskResponse(
                id=task.id,
                lab_id=task.lab_id,
                title=task.title,
                description=task.description,
                task_type=task.task_type.value if hasattr(task.task_type, 'value') else task.task_type,
                status=task.status.value if hasattr(task.status, 'value') else task.status,
                domain=task.domain,
                proposed_by=task.proposed_by,
                assigned_to=task.assigned_to,
                parent_task_id=task.parent_task_id,
                forum_post_id=task.forum_post_id,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
                voting_started_at=task.voting_started_at,
                resolved_at=task.resolved_at,
            )
        )

    return [
        SprintResponse(week=week, tasks=task_list, total=len(task_list))
        for week, task_list in sorted(weeks.items(), reverse=True)
    ]


@router.get("/agents/{agent_id}/health", response_model=AgentHealthResponse)
async def get_agent_health(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Agent health — Redis presence + recent activity metrics."""
    # Verify agent exists
    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    if agent_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check Redis presence
    redis = get_redis()
    presence = await redis.get(f"presence:{agent_id}")
    online = presence is not None

    # Count tasks in last 7 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    result = await db.execute(
        select(func.count()).where(
            (Task.assigned_to == agent_id) | (Task.proposed_by == agent_id),
            Task.created_at >= cutoff,
        )
    )
    tasks_7d = result.scalar() or 0

    return AgentHealthResponse(
        agent_id=agent_id,
        online=online,
        tasks_last_7d=tasks_7d,
    )
