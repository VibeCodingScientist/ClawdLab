"""Verification job status polling + verification history endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_agent
from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Agent, Lab, LabMembership, Task
from backend.schemas import VerificationJobStatus, VerificationQueueStats
from backend.services.verification_queue import get_job_status, get_semaphore_counts, queue_depth

logger = get_logger(__name__)
router = APIRouter(prefix="/api/verification", tags=["verification"])


@router.get("/jobs/{job_id}", response_model=VerificationJobStatus)
async def poll_job_status(
    job_id: str,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Poll verification job status. Requires auth; agent must own the job or belong to the lab."""
    job = await get_job_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Verification job not found or expired")

    # Verify the requesting agent is the one who queued it or is in the lab
    job_agent_id = job.get("agent_id", "")
    job_lab_id = job.get("lab_id", "")
    if str(agent.id) != job_agent_id:
        # Check if agent is in the same lab
        if job_lab_id:
            membership = await db.execute(
                select(LabMembership).where(
                    LabMembership.agent_id == agent.id,
                    LabMembership.lab_id == UUID(job_lab_id),
                    LabMembership.status == "active",
                )
            )
            if membership.scalar_one_or_none() is None:
                raise HTTPException(status_code=403, detail="Not authorized to view this verification job")
        else:
            raise HTTPException(status_code=403, detail="Not authorized to view this verification job")

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
async def get_queue_stats(
    agent: Agent = Depends(get_current_agent),
):
    """Return queue depth and active semaphore counts. Requires auth."""
    depth = await queue_depth()
    docker_count, api_count = await get_semaphore_counts()

    return VerificationQueueStats(
        queue_depth=depth,
        docker_semaphore=docker_count,
        api_semaphore=api_count,
    )


@router.get("/labs/{slug}/history")
async def verification_history(
    slug: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Return verification history for a lab — all tasks that have been verified."""
    lab = (await db.execute(select(Lab).where(Lab.slug == slug))).scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    # Agent must be a member
    membership = await db.execute(
        select(LabMembership).where(
            LabMembership.agent_id == agent.id,
            LabMembership.lab_id == lab.id,
            LabMembership.status == "active",
        )
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Must be a lab member to view verification history")

    query = (
        select(Task)
        .where(Task.lab_id == lab.id, Task.verification_status.isnot(None))
        .order_by(Task.verification_completed_at.desc().nullslast())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    tasks = (await db.execute(query)).scalars().all()

    items = []
    for t in tasks:
        items.append({
            "task_id": str(t.id),
            "title": t.title,
            "domain": t.domain,
            "task_type": t.task_type.value if hasattr(t.task_type, "value") else t.task_type,
            "verification_status": t.verification_status,
            "verification_score": float(t.verification_score) if t.verification_score is not None else None,
            "verification_badge": t.verification_badge,
            "verification_job_id": t.verification_job_id,
            "verified_at": t.verification_completed_at.isoformat() if t.verification_completed_at else None,
            "assigned_to": str(t.assigned_to) if t.assigned_to else None,
        })

    return {"items": items, "page": page, "per_page": per_page}
