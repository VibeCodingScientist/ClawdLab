"""Server-Sent Events endpoint for lab workspace live updates.

Streams real-time workspace state changes to connected clients
(spectator-friendly, no auth required). Uses sse-starlette for
standards-compliant SSE delivery.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from platform.infrastructure.database.session import get_db
from platform.labs.workspace_service import WorkspaceService
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["workspace"])

# In-memory event bus for workspace updates (per-lab)
# In production, this would be backed by Redis pubsub
_workspace_events: dict[str, asyncio.Queue] = {}
_MAX_QUEUE_SIZE = 100


def get_lab_queue(slug: str) -> asyncio.Queue:
    """Get or create the event queue for a lab."""
    if slug not in _workspace_events:
        _workspace_events[slug] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
    return _workspace_events[slug]


async def publish_workspace_event(slug: str, event: dict[str, Any]) -> None:
    """Publish a workspace event to all connected SSE clients for a lab.

    If the queue is full, the oldest event is dropped.
    """
    queue = get_lab_queue(slug)
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        logger.warning("workspace_event_queue_full", slug=slug)


async def _event_generator(slug: str) -> AsyncGenerator[dict[str, str], None]:
    """Generate SSE events for a specific lab workspace.

    Yields events as dicts with 'event' and 'data' keys suitable
    for sse-starlette's EventSourceResponse.
    """
    queue = get_lab_queue(slug)

    # Send initial keepalive
    yield {
        "event": "connected",
        "data": json.dumps({"slug": slug, "message": "Connected to workspace stream"}),
    }

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=30.0)
            yield {
                "event": "workspace_update",
                "data": json.dumps(event),
            }
        except asyncio.TimeoutError:
            # Send keepalive ping every 30 seconds
            yield {
                "event": "ping",
                "data": json.dumps({"type": "keepalive"}),
            }


@router.get("/labs/{slug}/workspace/stream")
async def workspace_stream(slug: str) -> EventSourceResponse:
    """Stream live workspace updates for a lab via SSE.

    No authentication required -- spectator-friendly endpoint.
    Clients receive real-time agent position and status updates
    as agents interact with the roundtable, bench, and other zones.

    Events:
    - ``connected`` -- initial connection confirmation
    - ``workspace_update`` -- agent zone/position/status change
    - ``ping`` -- keepalive every 30 seconds
    """
    logger.info("workspace_sse_connected", slug=slug)
    return EventSourceResponse(_event_generator(slug))


@router.get("/labs/{slug}/workspace/state")
async def workspace_state(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get the current workspace state snapshot for a lab.

    Returns the current zone and position for every active agent.
    Use this to initialize the workspace view, then subscribe to
    the SSE stream for live updates.
    """
    service = WorkspaceService(db)
    states = await service.get_lab_workspace(slug)
    return {
        "slug": slug,
        "agents": states,
        "total": len(states),
    }


__all__ = ["router", "publish_workspace_event"]
