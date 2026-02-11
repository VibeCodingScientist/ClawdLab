"""Verification status and management endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.session import get_db
from platform.services.verification_orchestrator.orchestrator import VerificationOrchestrator
from platform.shared.schemas.base import Domain
from platform.shared.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ===========================================
# SCHEMAS
# ===========================================


class VerificationJobStatus(BaseModel):
    """Verification job status response."""

    job_id: str
    claim_id: str
    domain: str
    status: str
    queued_at: datetime | None = None
    completed_at: datetime | None = None
    attempts: int = 0
    result: dict[str, Any] | None = None
    error: str | None = None


class VerificationDispatchRequest(BaseModel):
    """Request to manually dispatch verification."""

    claim_id: str = Field(..., description="ID of claim to verify")
    priority: int = Field(default=5, ge=1, le=10, description="Priority (1=highest)")


class VerificationDispatchResponse(BaseModel):
    """Response after dispatching verification."""

    job_id: str
    claim_id: str
    status: str
    message: str


class QueueStats(BaseModel):
    """Verification queue statistics."""

    domain: str
    queued: int
    running: int
    completed_today: int
    failed_today: int
    avg_time_seconds: float | None


class VerificationStats(BaseModel):
    """Overall verification statistics."""

    total_pending: int
    total_running: int
    queues: list[QueueStats]


# ===========================================
# ENDPOINTS
# ===========================================


@router.get(
    "/jobs/{job_id}",
    response_model=VerificationJobStatus,
    responses={404: {"description": "Job not found"}},
)
async def get_verification_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get status of a verification job.

    Returns detailed information about a verification job including:
    - Current status (queued, running, completed, failed)
    - Timestamps
    - Result or error details
    """
    orchestrator = VerificationOrchestrator(db)
    job_data = await orchestrator.get_verification_status(job_id)

    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification job {job_id} not found",
        )

    return VerificationJobStatus(
        job_id=job_data["job_id"],
        claim_id=job_data["claim_id"],
        domain=job_data["domain"],
        status=job_data["status"],
        queued_at=job_data.get("queued_at"),
        completed_at=job_data.get("completed_at"),
        attempts=job_data.get("attempts", 0),
        result=job_data.get("result"),
        error=job_data.get("error"),
    )


@router.get(
    "/claims/{claim_id}",
    response_model=VerificationJobStatus,
    responses={404: {"description": "No verification found for claim"}},
)
async def get_claim_verification(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get verification status for a claim.

    Returns the current or most recent verification job for a claim.
    """
    orchestrator = VerificationOrchestrator(db)
    job_data = await orchestrator.get_claim_verification(claim_id)

    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No verification found for claim {claim_id}",
        )

    return VerificationJobStatus(
        job_id=job_data["job_id"],
        claim_id=job_data["claim_id"],
        domain=job_data["domain"],
        status=job_data["status"],
        queued_at=job_data.get("queued_at"),
        completed_at=job_data.get("completed_at"),
        attempts=job_data.get("attempts", 0),
        result=job_data.get("result"),
        error=job_data.get("error"),
    )


@router.post(
    "/dispatch",
    response_model=VerificationDispatchResponse,
    responses={400: {"description": "Invalid request"}},
)
async def dispatch_verification(
    request: VerificationDispatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually dispatch a claim for verification.

    This endpoint is typically used for:
    - Re-verification after challenges
    - Manual retry of failed verifications
    - Testing

    Requires appropriate permissions.
    """
    # Get claim from database
    from platform.infrastructure.database.models import Claim
    from sqlalchemy import select

    result = await db.execute(select(Claim).where(Claim.id == request.claim_id))
    claim = result.scalar_one_or_none()

    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {request.claim_id} not found",
        )

    orchestrator = VerificationOrchestrator(db)

    try:
        job_id = await orchestrator.dispatch_verification(
            claim_id=request.claim_id,
            domain=claim.domain,
            claim_type=claim.claim_type,
            payload=claim.payload,
            priority=request.priority,
        )

        return VerificationDispatchResponse(
            job_id=job_id,
            claim_id=request.claim_id,
            status="dispatched",
            message=f"Verification dispatched to {claim.domain} queue",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/jobs/{job_id}/retry",
    response_model=VerificationDispatchResponse,
    responses={
        404: {"description": "Job not found"},
        400: {"description": "Cannot retry"},
    },
)
async def retry_verification(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retry a failed verification job.

    Only failed or errored jobs can be retried.
    There is a maximum retry limit per job.
    """
    orchestrator = VerificationOrchestrator(db)
    job_data = await orchestrator.get_verification_status(job_id)

    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification job {job_id} not found",
        )

    if job_data["status"] not in ("error", "timeout", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry job with status {job_data['status']}",
        )

    new_job_id = await orchestrator.retry_verification(job_id)

    if not new_job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum retries exceeded",
        )

    return VerificationDispatchResponse(
        job_id=new_job_id,
        claim_id=job_data["claim_id"],
        status="dispatched",
        message="Retry dispatched",
    )


@router.get(
    "/stats",
    response_model=VerificationStats,
)
async def get_verification_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    Get verification queue statistics.

    Returns aggregate statistics for all verification queues.
    """
    # Placeholder - would query Redis for real stats
    queues = []
    for domain in Domain:
        queues.append(
            QueueStats(
                domain=domain.value,
                queued=0,
                running=0,
                completed_today=0,
                failed_today=0,
                avg_time_seconds=None,
            )
        )

    return VerificationStats(
        total_pending=0,
        total_running=0,
        queues=queues,
    )


@router.get(
    "/queues/{domain}",
    response_model=QueueStats,
    responses={404: {"description": "Unknown domain"}},
)
async def get_queue_stats(
    domain: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get statistics for a specific verification queue.
    """
    # Validate domain
    try:
        Domain(domain)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown domain: {domain}",
        )

    # Placeholder stats
    return QueueStats(
        domain=domain,
        queued=0,
        running=0,
        completed_today=0,
        failed_today=0,
        avg_time_seconds=None,
    )
