"""FastAPI endpoints for Research Orchestration."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from platform.orchestration.base import (
    Claim,
    Priority,
    ResearchRequest,
)
from platform.orchestration.service import get_orchestration_service
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/orchestration", tags=["orchestration"])


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class ClaimModel(BaseModel):
    """Claim input model."""

    claim_type: str = Field(default="", description="Type of claim")
    content: str = Field(..., description="Claim content")
    domain: str | None = Field(default=None, description="Research domain")
    source: str = Field(default="", description="Source of claim")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchRequestModel(BaseModel):
    """Research request input model."""

    request_type: str = Field(
        default="claim_verification",
        description="Type of research request",
    )
    title: str = Field(default="", description="Request title")
    description: str = Field(default="", description="Request description")
    claims: list[ClaimModel] = Field(default_factory=list, description="Claims to verify")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    files: list[str] = Field(default_factory=list, description="File paths")
    priority: int = Field(default=3, ge=1, le=5, description="Priority (1=highest)")


class WorkflowStatusResponse(BaseModel):
    """Workflow status response."""

    workflow_id: str
    status: str
    progress_percent: float
    current_step: str | None
    total_steps: int
    completed_steps: int
    total_claims: int
    verified_claims: int
    execution_time_seconds: float


class ClaimRoutingRequest(BaseModel):
    """Claim routing request."""

    claim_type: str = Field(default="", description="Type of claim")
    content: str = Field(..., description="Claim content")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimExtractionRequest(BaseModel):
    """Claim extraction request."""

    text: str = Field(..., description="Text to extract claims from")
    source: str = Field(default="", description="Source of text")


# ===========================================
# RESEARCH ENDPOINTS
# ===========================================


@router.post("/research", response_model=dict[str, Any])
async def submit_research_request(request: ResearchRequestModel):
    """
    Submit a new research request.

    Creates a workflow to process the research request and verify claims.
    """
    service = get_orchestration_service()

    # Convert to internal model
    claims = [
        Claim(
            claim_type=c.claim_type,
            content=c.content,
            domain=c.domain,
            source=c.source,
            metadata=c.metadata,
        )
        for c in request.claims
    ]

    research_request = ResearchRequest(
        request_type=request.request_type,
        title=request.title,
        description=request.description,
        claims=claims,
        context=request.context,
        files=request.files,
        priority=Priority(request.priority),
    )

    try:
        response = await service.submit_research_request(research_request)
        return response.to_dict()
    except Exception as e:
        logger.exception("research_request_error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/research/{workflow_id}", response_model=dict[str, Any])
async def get_research_results(workflow_id: str):
    """
    Get research results for a workflow.

    Returns the current state and results of the research workflow.
    """
    service = get_orchestration_service()

    response = await service.get_workflow_results(workflow_id)
    if not response:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")

    return response.to_dict()


@router.get("/research/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str):
    """
    Get workflow status.

    Returns a summary of the workflow's current state.
    """
    service = get_orchestration_service()

    try:
        status = await service.get_workflow_status(workflow_id)
        return WorkflowStatusResponse(**status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/research/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel a running workflow."""
    service = get_orchestration_service()

    cancelled = await service.cancel_workflow(workflow_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Unable to cancel workflow")

    return {"message": "Workflow cancelled", "workflow_id": workflow_id}


@router.post("/research/{workflow_id}/pause")
async def pause_workflow(workflow_id: str):
    """Pause a running workflow."""
    service = get_orchestration_service()

    paused = await service.pause_workflow(workflow_id)
    if not paused:
        raise HTTPException(status_code=400, detail="Unable to pause workflow")

    return {"message": "Workflow paused", "workflow_id": workflow_id}


@router.post("/research/{workflow_id}/resume")
async def resume_workflow(workflow_id: str):
    """Resume a paused workflow."""
    service = get_orchestration_service()

    resumed = await service.resume_workflow(workflow_id)
    if not resumed:
        raise HTTPException(status_code=400, detail="Unable to resume workflow")

    return {"message": "Workflow resumed", "workflow_id": workflow_id}


# ===========================================
# CLAIM ENDPOINTS
# ===========================================


@router.post("/claims/route", response_model=dict[str, Any])
async def route_claim(request: ClaimRoutingRequest):
    """
    Route a claim to the appropriate verification engine.

    Analyzes the claim and determines which verification engine should handle it.
    """
    from platform.orchestration.claim_router import get_claim_router

    router = get_claim_router()

    claim = Claim(
        claim_type=request.claim_type,
        content=request.content,
        metadata=request.metadata,
    )

    decision = await router.route_claim(claim)
    return decision.to_dict()


@router.post("/claims/extract", response_model=list[dict[str, Any]])
async def extract_claims(request: ClaimExtractionRequest):
    """
    Extract verifiable claims from text.

    Analyzes the text and extracts claims that can be verified.
    """
    from platform.orchestration.claim_router import get_claim_router

    router = get_claim_router()

    claims = await router.extract_claims(request.text, request.source)
    return [c.to_dict() for c in claims]


@router.post("/claims/verify", response_model=dict[str, Any])
async def verify_claim(request: ClaimModel):
    """
    Submit a single claim for verification.

    Routes and verifies a single claim without creating a full workflow.
    """
    service = get_orchestration_service()

    claim = Claim(
        claim_type=request.claim_type,
        content=request.content,
        domain=request.domain,
        source=request.source,
        metadata=request.metadata,
    )

    result = await service.process_claim(claim)
    return result.to_dict()


# ===========================================
# SESSION ENDPOINTS
# ===========================================


@router.post("/sessions", response_model=dict[str, Any])
async def create_session(
    agent_id: str,
    ttl_hours: int = Query(default=72, ge=1, le=168),
):
    """
    Create a new research session.

    Sessions track agent's ongoing work and enable checkpointing.
    """
    from platform.orchestration.session_manager import get_session_manager

    manager = get_session_manager()

    try:
        session = await manager.create_session(agent_id, ttl_hours=ttl_hours)
        return session.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}", response_model=dict[str, Any])
async def get_session(session_id: str):
    """Get session details."""
    from platform.orchestration.session_manager import get_session_manager

    manager = get_session_manager()

    session = await manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return session.to_dict()


@router.post("/sessions/{session_id}/checkpoint", response_model=dict[str, Any])
async def create_checkpoint(session_id: str, data: dict[str, Any] | None = None):
    """Create a session checkpoint."""
    from platform.orchestration.session_manager import get_session_manager

    manager = get_session_manager()

    try:
        checkpoint = await manager.create_checkpoint(session_id, data)
        return checkpoint
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/sessions/{session_id}/restore", response_model=dict[str, Any])
async def restore_session(session_id: str, checkpoint_id: str | None = None):
    """Restore session from checkpoint."""
    from platform.orchestration.session_manager import get_session_manager

    manager = get_session_manager()

    session = await manager.restore_from_checkpoint(session_id, checkpoint_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return session.to_dict()


@router.delete("/sessions/{session_id}")
async def close_session(session_id: str):
    """Close a session."""
    from platform.orchestration.session_manager import get_session_manager

    manager = get_session_manager()

    closed = await manager.close_session(session_id)
    if not closed:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return {"message": "Session closed", "session_id": session_id}


# ===========================================
# METADATA ENDPOINTS
# ===========================================


@router.get("/templates", response_model=list[dict[str, Any]])
async def get_workflow_templates():
    """Get available workflow templates."""
    service = get_orchestration_service()
    return service.get_available_templates()


@router.get("/domains", response_model=list[dict[str, Any]])
async def get_research_domains():
    """Get available research domains."""
    service = get_orchestration_service()
    return service.get_available_domains()


@router.get("/stats", response_model=dict[str, Any])
async def get_orchestration_stats():
    """Get orchestration statistics."""
    from platform.orchestration.session_manager import get_session_manager
    from platform.orchestration.task_scheduler import get_task_scheduler

    scheduler = get_task_scheduler()
    session_manager = get_session_manager()

    return {
        "queues": scheduler.get_queue_stats(),
        "sessions": session_manager.get_session_stats(),
    }
