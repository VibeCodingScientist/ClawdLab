"""FastAPI endpoints for Agent Communication Framework."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from platform.agents.base import AgentStatus, MessagePriority
from platform.agents.service import get_agent_communication_service
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class RegisterAgentRequest(BaseModel):
    """Request to register an agent."""

    agent_type: str = Field(description="Type of agent")
    name: str = Field(description="Agent name")
    capabilities: list[str] = Field(description="Agent capabilities")
    endpoint: str = Field(default="", description="Communication endpoint")
    description: str = Field(default="", description="Agent description")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class UpdateStatusRequest(BaseModel):
    """Request to update agent status."""

    status: str = Field(description="New status (ready, busy, paused)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional metadata")


class HeartbeatRequest(BaseModel):
    """Request to record heartbeat."""

    metrics: dict[str, Any] = Field(default_factory=dict, description="Optional metrics")


class SendMessageRequest(BaseModel):
    """Request to send a message."""

    sender_id: str = Field(description="Sender agent ID")
    recipient_id: str = Field(description="Recipient agent ID")
    subject: str = Field(description="Message subject")
    payload: dict[str, Any] = Field(default_factory=dict, description="Message payload")
    timeout: float | None = Field(default=None, description="Response timeout in seconds")
    priority: str = Field(default="normal", description="Message priority")


class BroadcastRequest(BaseModel):
    """Request to broadcast a message."""

    sender_id: str = Field(description="Sender agent ID")
    subject: str = Field(description="Message subject")
    payload: dict[str, Any] = Field(default_factory=dict, description="Message payload")
    priority: str = Field(default="normal", description="Message priority")


class ScatterRequest(BaseModel):
    """Request to scatter message to multiple agents."""

    sender_id: str = Field(description="Sender agent ID")
    recipient_ids: list[str] = Field(description="List of recipient agent IDs")
    subject: str = Field(description="Message subject")
    payload: dict[str, Any] = Field(default_factory=dict, description="Message payload")
    timeout: float | None = Field(default=None, description="Response timeout in seconds")


class SubscribeRequest(BaseModel):
    """Request to subscribe to a channel."""

    agent_id: str = Field(description="Subscribing agent ID")
    channel: str = Field(description="Channel name")


class PublishEventRequest(BaseModel):
    """Request to publish an event."""

    sender_id: str = Field(description="Publisher agent ID")
    topic: str = Field(description="Topic name")
    subject: str = Field(description="Event subject")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event payload")


class CreateChannelRequest(BaseModel):
    """Request to create a channel."""

    name: str = Field(description="Channel name")
    channel_type: str = Field(description="Channel type (direct, topic, broadcast, queue)")
    description: str = Field(default="", description="Channel description")
    created_by: str = Field(default="", description="Creator ID")


class CreatePipelineRequest(BaseModel):
    """Request to create a pipeline."""

    name: str = Field(description="Pipeline name")
    stages: list[dict[str, Any]] = Field(description="Pipeline stages")
    description: str = Field(default="", description="Pipeline description")
    created_by: str = Field(default="", description="Creator ID")


class SubmitPipelineRequest(BaseModel):
    """Request to submit to a pipeline."""

    sender_id: str = Field(description="Submitter agent ID")
    payload: dict[str, Any] = Field(description="Initial payload")


# ===========================================
# AGENT ENDPOINTS
# ===========================================


@router.post("/register")
async def register_agent(request: RegisterAgentRequest):
    """Register a new agent."""
    service = get_agent_communication_service()

    agent = await service.register_agent(
        agent_type=request.agent_type,
        name=request.name,
        capabilities=request.capabilities,
        endpoint=request.endpoint,
        description=request.description,
        metadata=request.metadata,
    )

    return agent.to_dict()


@router.delete("/{agent_id}")
async def unregister_agent(agent_id: str):
    """Unregister an agent."""
    service = get_agent_communication_service()

    success = await service.unregister_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"status": "unregistered", "agent_id": agent_id}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent information."""
    service = get_agent_communication_service()

    agent = await service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agent.to_dict()


@router.put("/{agent_id}/status")
async def update_agent_status(agent_id: str, request: UpdateStatusRequest):
    """Update agent status."""
    service = get_agent_communication_service()

    status_map = {
        "ready": AgentStatus.READY,
        "busy": AgentStatus.BUSY,
        "paused": AgentStatus.PAUSED,
        "initializing": AgentStatus.INITIALIZING,
    }

    if request.status not in status_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {list(status_map.keys())}",
        )

    if request.status == "ready":
        agent = await service.set_agent_ready(agent_id)
    elif request.status == "busy":
        agent = await service.set_agent_busy(agent_id)
    elif request.status == "paused":
        agent = await service.set_agent_paused(agent_id)
    else:
        agent = await service.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agent.to_dict()


@router.post("/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str, request: HeartbeatRequest):
    """Record agent heartbeat."""
    service = get_agent_communication_service()

    success = await service.heartbeat(agent_id, request.metrics)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"status": "ok", "agent_id": agent_id}


@router.get("")
async def list_agents(
    agent_type: str | None = Query(default=None, description="Filter by agent type"),
    capability: str | None = Query(default=None, description="Filter by capability"),
    status: str | None = Query(default=None, description="Filter by status"),
):
    """List all agents."""
    service = get_agent_communication_service()

    status_enum = AgentStatus(status) if status else None

    agents = await service.list_agents(
        agent_type=agent_type,
        capability=capability,
        status=status_enum,
    )

    return {
        "agents": [a.to_dict() for a in agents],
        "count": len(agents),
    }


@router.get("/{agent_id}/metrics")
async def get_agent_metrics(agent_id: str):
    """Get agent metrics."""
    service = get_agent_communication_service()

    metrics = await service.get_agent_metrics(agent_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Agent not found")

    return metrics.to_dict()


@router.get("/types/available")
async def get_agent_types():
    """Get available agent types."""
    service = get_agent_communication_service()
    return service.get_agent_types()


# ===========================================
# MESSAGING ENDPOINTS
# ===========================================


@router.post("/messages/send")
async def send_message(request: SendMessageRequest):
    """Send a request message and wait for response."""
    service = get_agent_communication_service()

    priority_map = {
        "critical": MessagePriority.CRITICAL,
        "high": MessagePriority.HIGH,
        "normal": MessagePriority.NORMAL,
        "low": MessagePriority.LOW,
        "background": MessagePriority.BACKGROUND,
    }

    priority = priority_map.get(request.priority, MessagePriority.NORMAL)

    try:
        response = await service.send_request(
            sender_id=request.sender_id,
            recipient_id=request.recipient_id,
            subject=request.subject,
            payload=request.payload,
            timeout=request.timeout,
            priority=priority,
        )

        return response.to_dict()

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=408, detail="Request timed out")


@router.post("/messages/send-by-capability")
async def send_message_by_capability(
    sender_id: str = Query(description="Sender agent ID"),
    capability: str = Query(description="Required capability"),
    subject: str = Query(description="Message subject"),
    payload: dict[str, Any] = None,
    timeout: float | None = Query(default=None, description="Timeout in seconds"),
):
    """Send a request to an agent with specific capability."""
    service = get_agent_communication_service()

    try:
        response = await service.send_request_by_capability(
            sender_id=sender_id,
            capability=capability,
            subject=subject,
            payload=payload or {},
            timeout=timeout,
        )

        return response.to_dict()

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=408, detail="Request timed out")


@router.post("/messages/broadcast")
async def broadcast_message(request: BroadcastRequest):
    """Broadcast a message to all agents."""
    service = get_agent_communication_service()

    priority_map = {
        "critical": MessagePriority.CRITICAL,
        "high": MessagePriority.HIGH,
        "normal": MessagePriority.NORMAL,
        "low": MessagePriority.LOW,
        "background": MessagePriority.BACKGROUND,
    }

    priority = priority_map.get(request.priority, MessagePriority.NORMAL)

    message_id = await service.broadcast(
        sender_id=request.sender_id,
        subject=request.subject,
        payload=request.payload,
        priority=priority,
    )

    return {"message_id": message_id, "status": "broadcast"}


@router.post("/messages/scatter")
async def scatter_message(request: ScatterRequest):
    """Send requests to multiple agents and gather responses."""
    service = get_agent_communication_service()

    responses = await service.scatter(
        sender_id=request.sender_id,
        recipient_ids=request.recipient_ids,
        subject=request.subject,
        payload=request.payload,
        timeout=request.timeout,
    )

    return {
        "responses": [r.to_dict() for r in responses],
        "count": len(responses),
    }


# ===========================================
# SUBSCRIPTION ENDPOINTS
# ===========================================


@router.post("/subscriptions")
async def subscribe_to_channel(request: SubscribeRequest):
    """Subscribe an agent to a channel."""
    service = get_agent_communication_service()

    subscription = await service.subscribe(
        agent_id=request.agent_id,
        channel=request.channel,
    )

    return subscription.to_dict()


@router.delete("/subscriptions/{agent_id}/{channel}")
async def unsubscribe_from_channel(agent_id: str, channel: str):
    """Unsubscribe an agent from a channel."""
    service = get_agent_communication_service()

    success = await service.unsubscribe(agent_id, channel)

    return {"status": "unsubscribed" if success else "not_found"}


@router.get("/subscriptions/{agent_id}")
async def get_agent_subscriptions(agent_id: str):
    """Get all subscriptions for an agent."""
    service = get_agent_communication_service()

    subscriptions = await service.get_subscriptions(agent_id)

    return {
        "agent_id": agent_id,
        "subscriptions": [s.to_dict() for s in subscriptions],
    }


@router.post("/events/publish")
async def publish_event(request: PublishEventRequest):
    """Publish an event to a topic."""
    service = get_agent_communication_service()

    message_id = await service.publish_event(
        sender_id=request.sender_id,
        topic=request.topic,
        subject=request.subject,
        payload=request.payload,
    )

    return {"message_id": message_id, "status": "published"}


# ===========================================
# CHANNEL ENDPOINTS
# ===========================================


@router.post("/channels")
async def create_channel(request: CreateChannelRequest):
    """Create a communication channel."""
    service = get_agent_communication_service()

    valid_types = ["direct", "topic", "broadcast", "queue"]
    if request.channel_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid channel type. Must be one of: {valid_types}",
        )

    channel = await service.create_channel(
        name=request.name,
        channel_type=request.channel_type,
        description=request.description,
        created_by=request.created_by,
    )

    return channel.to_dict()


@router.get("/channels/{name}")
async def get_channel(name: str):
    """Get channel information."""
    service = get_agent_communication_service()

    channel = await service.get_channel(name)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    return channel.to_dict()


@router.get("/channels")
async def list_channels():
    """List all channels."""
    service = get_agent_communication_service()

    channels = await service.list_channels()

    return {
        "channels": [c.to_dict() for c in channels],
        "count": len(channels),
    }


# ===========================================
# PIPELINE ENDPOINTS
# ===========================================


@router.post("/pipelines")
async def create_pipeline(request: CreatePipelineRequest):
    """Create a processing pipeline."""
    service = get_agent_communication_service()

    pipeline = await service.create_pipeline(
        name=request.name,
        stages=request.stages,
        description=request.description,
        created_by=request.created_by,
    )

    return pipeline.to_dict()


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    """Get pipeline information."""
    service = get_agent_communication_service()

    pipeline = service.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    return pipeline.to_dict()


@router.get("/pipelines")
async def list_pipelines():
    """List all pipelines."""
    service = get_agent_communication_service()

    pipelines = service.list_pipelines()

    return {
        "pipelines": [p.to_dict() for p in pipelines],
        "count": len(pipelines),
    }


@router.post("/pipelines/{pipeline_id}/submit")
async def submit_to_pipeline(pipeline_id: str, request: SubmitPipelineRequest):
    """Submit data to a pipeline."""
    service = get_agent_communication_service()

    try:
        execution_id = await service.submit_to_pipeline(
            pipeline_id=pipeline_id,
            sender_id=request.sender_id,
            payload=request.payload,
        )

        return {
            "execution_id": execution_id,
            "pipeline_id": pipeline_id,
            "status": "submitted",
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ===========================================
# MONITORING ENDPOINTS
# ===========================================


@router.get("/events")
async def get_events(
    agent_id: str | None = Query(default=None, description="Filter by agent ID"),
    event_type: str | None = Query(default=None, description="Filter by event type"),
    since: str | None = Query(default=None, description="Filter events after this ISO timestamp"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum events"),
):
    """Get agent events."""
    service = get_agent_communication_service()

    since_dt = datetime.fromisoformat(since) if since else None

    events = await service.get_agent_events(
        agent_id=agent_id,
        event_type=event_type,
        since=since_dt,
        limit=limit,
    )

    return {
        "events": [e.to_dict() for e in events],
        "count": len(events),
    }


@router.get("/dead-letters")
async def get_dead_letters(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum items"),
    since: str | None = Query(default=None, description="Filter after this ISO timestamp"),
):
    """Get dead-lettered messages."""
    service = get_agent_communication_service()

    since_dt = datetime.fromisoformat(since) if since else None

    dead_letters = await service.get_dead_letters(limit=limit, since=since_dt)

    return {
        "dead_letters": [dl.to_dict() for dl in dead_letters],
        "count": len(dead_letters),
    }


@router.post("/dead-letters/{message_id}/retry")
async def retry_dead_letter(message_id: str):
    """Retry a dead-lettered message."""
    service = get_agent_communication_service()

    success = await service.retry_dead_letter(message_id)
    if not success:
        raise HTTPException(status_code=404, detail="Dead letter not found")

    return {"status": "retrying", "message_id": message_id}


@router.get("/stats")
async def get_communication_stats():
    """Get overall communication statistics."""
    service = get_agent_communication_service()

    stats = service.get_stats()

    return {
        "total_agents": stats.total_agents,
        "agents_by_status": stats.agents_by_status,
        "agents_by_type": stats.agents_by_type,
        "total_channels": stats.total_channels,
        "total_subscriptions": stats.total_subscriptions,
        "total_messages": stats.total_messages,
        "dead_letters": stats.dead_letters,
        "pending_responses": stats.pending_responses,
    }


@router.get("/metrics")
async def get_all_metrics():
    """Get metrics for all agents."""
    service = get_agent_communication_service()

    metrics = await service.get_all_metrics()

    return {
        "metrics": [m.to_dict() for m in metrics],
        "count": len(metrics),
    }
