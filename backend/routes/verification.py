"""Verification job status polling endpoints."""

from fastapi import APIRouter, HTTPException

from backend.logging_config import get_logger
from backend.schemas import VerificationJobStatus, VerificationQueueStats
from backend.services.verification_queue import get_job_status, get_semaphore_counts, queue_depth

logger = get_logger(__name__)
router = APIRouter(prefix="/api/verification", tags=["verification"])


@router.get("/jobs/{job_id}", response_model=VerificationJobStatus)
async def poll_job_status(job_id: str):
    """Poll verification job status by job_id."""
    job = await get_job_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Verification job not found or expired")

    return VerificationJobStatus(
        job_id=job.get("job_id", job_id),
        status=job.get("status", "unknown"),
        domain=job.get("domain"),
        task_id=job.get("task_id"),
        score=float(job["score"]) if job.get("score") not in ("", None) else None,
        badge=job.get("badge") or None,
        passed=job.get("passed") if job.get("passed") not in ("", None) else None,
        errors=job.get("errors", []),
        queued_at=job.get("queued_at") or None,
        started_at=job.get("started_at") or None,
        completed_at=job.get("completed_at") or None,
    )


@router.get("/queue-stats", response_model=VerificationQueueStats)
async def get_queue_stats():
    """Return queue depth and active semaphore counts."""
    depth = await queue_depth()
    docker_count, api_count = await get_semaphore_counts()

    return VerificationQueueStats(
        queue_depth=depth,
        docker_semaphore=docker_count,
        api_semaphore=api_count,
    )
