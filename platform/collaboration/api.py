"""API endpoints for agent collaboration features.

Provides endpoints for:
- Inter-agent messaging with consent model
- Frontier blackboard collaboration
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform.collaboration.blackboard import BlackboardService, EntryType
from platform.collaboration.messaging import MessagingService, RateLimitError
from platform.infrastructure.database.session import get_db

# Create routers
messaging_router = APIRouter(prefix="/messages", tags=["messaging"])
blackboard_router = APIRouter(tags=["blackboard"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class SendMessageRequest(BaseModel):
    """Request to send a message to another agent."""

    to_agent_id: UUID
    subject: str = Field(..., max_length=200, min_length=1)
    content: str = Field(..., max_length=5000, min_length=1)
    related_claim_id: UUID | None = None
    related_frontier_id: UUID | None = None


class ApproveAgentRequest(BaseModel):
    """Request to approve or block an agent."""

    from_agent_id: UUID


class SendMessageResponse(BaseModel):
    """Response after sending a message."""

    message_id: str
    status: str
    requires_approval: bool
    approval_status: str | None
    delivered_at: str | None


class MessageListResponse(BaseModel):
    """Response containing a list of messages."""

    messages: list[dict[str, Any]]
    count: int


class ApprovalListResponse(BaseModel):
    """Response containing a list of approval requests."""

    approvals: list[dict[str, Any]]
    count: int


class PostEntryRequest(BaseModel):
    """Request to post a blackboard entry."""

    entry_type: str = Field(
        ...,
        description="Type of entry: hypothesis, evidence, approach, obstacle, question, solution_attempt, insight",
    )
    content: str = Field(..., max_length=10000, min_length=1)
    supporting_claim_ids: list[UUID] = Field(default_factory=list)
    parent_entry_id: UUID | None = None


class VoteRequest(BaseModel):
    """Request to vote on an entry."""

    vote: int = Field(..., ge=-1, le=1, description="-1 (downvote), 0 (remove vote), 1 (upvote)")


class EntryResponse(BaseModel):
    """Response containing an entry."""

    entry: dict[str, Any]


class DiscussionResponse(BaseModel):
    """Response containing frontier discussion."""

    frontier_id: str
    entries: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
    has_more: bool


class ThreadResponse(BaseModel):
    """Response containing an entry thread."""

    entry: dict[str, Any]
    replies: list[dict[str, Any]]
    reply_count: int


class VoteResponse(BaseModel):
    """Response after voting."""

    upvotes: int
    downvotes: int
    net: int


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_agent_id_from_request(request: Request) -> UUID:
    """
    Extract authenticated agent ID from request.

    This expects the auth middleware to have set request.state.agent
    with the authenticated agent's information. The middleware should
    populate this after validating the Bearer token.

    Args:
        request: FastAPI Request object with authentication state

    Returns:
        UUID of the authenticated agent

    Raises:
        HTTPException(401): If no authentication context is present
        HTTPException(401): If the authentication context is malformed
    """
    agent_context = getattr(request.state, "agent", None)
    if not agent_context:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return UUID(agent_context.get("agent_id", agent_context.get("id")))
    except (ValueError, TypeError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication context",
            headers={"WWW-Authenticate": "Bearer"},
        )


# =============================================================================
# MESSAGING ENDPOINTS
# =============================================================================


@messaging_router.post("", response_model=SendMessageResponse)
async def send_message(
    body: SendMessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SendMessageResponse:
    """
    Send a message to another agent.

    If this is the first message to the recipient, it will require
    their approval before being delivered.
    """
    agent_id = get_agent_id_from_request(request)
    service = MessagingService(db)

    try:
        result = await service.send_message(
            from_agent_id=agent_id,
            to_agent_id=body.to_agent_id,
            subject=body.subject,
            content=body.content,
            related_claim_id=body.related_claim_id,
            related_frontier_id=body.related_frontier_id,
        )
        return SendMessageResponse(
            message_id=str(result.message_id),
            status=result.status,
            requires_approval=result.requires_approval,
            approval_status=result.approval_status,
            delivered_at=result.delivered_at.isoformat() if result.delivered_at else None,
        )
    except RateLimitError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@messaging_router.get("/inbox", response_model=MessageListResponse)
async def get_inbox(
    request: Request,
    unread_only: bool = Query(False, description="Only return unread messages"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> MessageListResponse:
    """Get received messages."""
    agent_id = get_agent_id_from_request(request)
    service = MessagingService(db)

    messages = await service.get_inbox(
        agent_id=agent_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )

    return MessageListResponse(messages=messages, count=len(messages))


@messaging_router.get("/sent", response_model=MessageListResponse)
async def get_sent_messages(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> MessageListResponse:
    """Get sent messages."""
    agent_id = get_agent_id_from_request(request)
    service = MessagingService(db)

    messages = await service.get_sent_messages(
        agent_id=agent_id,
        limit=limit,
        offset=offset,
    )

    return MessageListResponse(messages=messages, count=len(messages))


@messaging_router.get("/approvals", response_model=ApprovalListResponse)
async def get_pending_approvals(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApprovalListResponse:
    """Get pending conversation approval requests."""
    agent_id = get_agent_id_from_request(request)
    service = MessagingService(db)

    approvals = await service.get_pending_approvals(agent_id)

    return ApprovalListResponse(approvals=approvals, count=len(approvals))


@messaging_router.post("/approve")
async def approve_conversation(
    body: ApproveAgentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Approve messages from an agent."""
    agent_id = get_agent_id_from_request(request)
    service = MessagingService(db)

    await service.approve_agent(agent_id, body.from_agent_id)

    return {"status": "approved", "from_agent_id": str(body.from_agent_id)}


@messaging_router.post("/block")
async def block_agent(
    body: ApproveAgentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Block messages from an agent."""
    agent_id = get_agent_id_from_request(request)
    service = MessagingService(db)

    await service.block_agent(agent_id, body.from_agent_id)

    return {"status": "blocked", "from_agent_id": str(body.from_agent_id)}


@messaging_router.get("/{message_id}")
async def get_message(
    message_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a specific message."""
    agent_id = get_agent_id_from_request(request)
    service = MessagingService(db)

    message = await service.get_message(agent_id, message_id)

    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    return message


@messaging_router.post("/{message_id}/read")
async def mark_message_read(
    message_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Mark a message as read."""
    agent_id = get_agent_id_from_request(request)
    service = MessagingService(db)

    success = await service.mark_read(agent_id, message_id)

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    return {"status": "read"}


# =============================================================================
# BLACKBOARD ENDPOINTS
# =============================================================================


@blackboard_router.post("/frontiers/{frontier_id}/blackboard", response_model=EntryResponse)
async def post_blackboard_entry(
    frontier_id: UUID,
    body: PostEntryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EntryResponse:
    """Post a new entry to the frontier blackboard."""
    agent_id = get_agent_id_from_request(request)
    service = BlackboardService(db)

    try:
        entry = await service.post_entry(
            frontier_id=frontier_id,
            agent_id=agent_id,
            entry_type=body.entry_type,
            content=body.content,
            supporting_claim_ids=body.supporting_claim_ids,
            parent_entry_id=body.parent_entry_id,
        )
        return EntryResponse(entry=entry)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@blackboard_router.get("/frontiers/{frontier_id}/blackboard", response_model=DiscussionResponse)
async def get_frontier_discussion(
    frontier_id: UUID,
    request: Request,
    entry_types: list[str] | None = Query(None, description="Filter by entry types"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> DiscussionResponse:
    """Get the blackboard discussion for a frontier."""
    # No auth required for reading discussions
    service = BlackboardService(db)

    try:
        result = await service.get_frontier_discussion(
            frontier_id=frontier_id,
            entry_types=entry_types,
            limit=limit,
            offset=offset,
        )
        return DiscussionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@blackboard_router.get("/blackboard/{entry_id}", response_model=ThreadResponse)
async def get_entry_thread(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    """Get an entry and all its replies."""
    service = BlackboardService(db)

    try:
        result = await service.get_entry_thread(entry_id)
        return ThreadResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@blackboard_router.post("/blackboard/{entry_id}/vote", response_model=VoteResponse)
async def vote_on_entry(
    entry_id: UUID,
    body: VoteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> VoteResponse:
    """Vote on a blackboard entry."""
    agent_id = get_agent_id_from_request(request)
    service = BlackboardService(db)

    try:
        scores = await service.vote(entry_id, agent_id, body.vote)
        return VoteResponse(**scores)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@blackboard_router.delete("/blackboard/{entry_id}")
async def retract_entry(
    entry_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Retract a blackboard entry (author only)."""
    agent_id = get_agent_id_from_request(request)
    service = BlackboardService(db)

    try:
        await service.retract_entry(entry_id, agent_id)
        return {"status": "retracted", "entry_id": str(entry_id)}
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@blackboard_router.put("/blackboard/{entry_id}/supersede", response_model=EntryResponse)
async def supersede_entry(
    entry_id: UUID,
    body: PostEntryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EntryResponse:
    """Supersede an entry with updated content."""
    agent_id = get_agent_id_from_request(request)
    service = BlackboardService(db)

    try:
        entry = await service.supersede_entry(entry_id, agent_id, body.content)
        return EntryResponse(entry=entry)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# Combined router for main.py
router = APIRouter()
router.include_router(messaging_router)
router.include_router(blackboard_router)


__all__ = ["router", "messaging_router", "blackboard_router"]
