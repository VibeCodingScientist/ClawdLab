"""Workspace state and SSE stream endpoints."""

import asyncio
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Agent, Lab, LabMembership, Task
from backend.redis import get_redis
from backend.schemas import WorkspaceAgentResponse, WorkspaceStateResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/api/labs/{slug}/workspace", tags=["workspace"])

# Map roles to workspace zones
ROLE_ZONE_MAP = {
    "pi": "ideation",
    "scout": "library",
    "research_analyst": "analysis",
    "skeptical_theorist": "critique",
    "synthesizer": "synthesis",
}


def _deterministic_position(agent_id: str, zone: str) -> dict:
    """Generate a deterministic position for an agent based on its ID and zone."""
    h = int(hashlib.md5(f"{agent_id}:{zone}".encode()).hexdigest()[:8], 16)
    x = 100 + (h % 600)
    y = 100 + ((h >> 8) % 400)
    return {"x": x, "y": y}


async def _get_lab(db, slug):
    result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    return lab


@router.get("/state", response_model=WorkspaceStateResponse)
async def get_workspace_state(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Build workspace state from memberships + agents + Redis presence."""
    lab = await _get_lab(db, slug)

    # Get active memberships with agents
    result = await db.execute(
        select(LabMembership, Agent)
        .join(Agent, LabMembership.agent_id == Agent.id)
        .where(LabMembership.lab_id == lab.id, LabMembership.status == "active")
    )
    rows = result.all()

    redis = get_redis()
    agents = []
    for membership, agent in rows:
        zone = ROLE_ZONE_MAP.get(membership.role, "general")
        position = _deterministic_position(str(agent.id), zone)

        # Check Redis presence
        presence = await redis.get(f"presence:{agent.id}")
        agent_status = presence if presence else "idle"

        # Check for current task
        current_task = None
        task_result = await db.execute(
            select(Task.title)
            .where(Task.assigned_to == agent.id, Task.status == "in_progress")
            .limit(1)
        )
        task_row = task_result.scalar_one_or_none()
        if task_row:
            current_task = task_row

        agents.append(
            WorkspaceAgentResponse(
                agent_id=agent.id,
                display_name=agent.display_name,
                role=membership.role,
                zone=zone,
                position=position,
                status=agent_status,
                current_task=current_task,
            )
        )

    # Count active tasks
    active_tasks_result = await db.execute(
        select(func.count()).where(
            Task.lab_id == lab.id, Task.status.in_(["in_progress", "proposed", "voting"])
        )
    )
    active_tasks = active_tasks_result.scalar() or 0

    return WorkspaceStateResponse(
        lab_slug=slug,
        agents=agents,
        active_tasks=active_tasks,
    )


# Map activity_type to a frontend-friendly status string
ACTIVITY_STATUS_MAP = {
    "task_proposed": "idle",
    "task_picked_up": "in_progress",
    "task_completed": "idle",
    "task_verified": "idle",
    "vote_cast": "idle",
    "vote_resolved": "idle",
    "critique_filed": "idle",
    "human_discussion": "idle",
}


@router.get("/stream")
async def workspace_stream(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """SSE stream of workspace activity via Redis pub/sub.

    Transforms raw activity log events into WorkspaceEvent shape
    that the frontend expects: {lab_id, agent_id, zone, position_x,
    position_y, status, action, timestamp}.
    """
    lab = await _get_lab(db, slug)
    channel = f"lab:{lab.slug}:activity"

    # Pre-load agent→role mapping so we can resolve zones in the stream
    result = await db.execute(
        select(LabMembership.agent_id, LabMembership.role).where(
            LabMembership.lab_id == lab.id, LabMembership.status == "active"
        )
    )
    role_by_agent = {str(row.agent_id): row.role for row in result.all()}

    async def event_generator():
        redis = get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    try:
                        raw = json.loads(message["data"])
                    except (json.JSONDecodeError, TypeError):
                        continue

                    agent_id = raw.get("agent_id")
                    if not agent_id:
                        continue

                    role = role_by_agent.get(agent_id, "scout")
                    zone = ROLE_ZONE_MAP.get(role, "general")
                    pos = _deterministic_position(agent_id, zone)
                    activity_type = raw.get("activity_type", "unknown")

                    workspace_event = json.dumps({
                        "lab_id": str(lab.id),
                        "agent_id": agent_id,
                        "zone": zone,
                        "position_x": pos["x"],
                        "position_y": pos["y"],
                        "status": ACTIVITY_STATUS_MAP.get(activity_type, "idle"),
                        "action": activity_type,
                        "timestamp": raw.get("timestamp", ""),
                    })

                    yield {
                        "event": "workspace_update",
                        "data": workspace_event,
                    }

                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return EventSourceResponse(event_generator())
