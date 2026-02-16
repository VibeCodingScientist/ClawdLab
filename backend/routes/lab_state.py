"""Composite lab-state endpoint: tasks enriched with activity evidence and signature chains."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Agent, Lab, LabActivityLog, SignatureChain, Task, TaskVote
from backend.schemas import (
    EvidenceEntryResponse,
    LabStateItemResponse,
    SignatureEntryResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/labs/{slug}", tags=["lab-state"])

# Task status → frontend LabStateStatus
_STATUS_MAP = {
    "accepted": "established",
    "in_progress": "under_investigation",
    "completed": "under_investigation",
    "critique_period": "contested",
    "voting": "contested",
    "proposed": "proposed",
}

# Activity type → EvidenceEntry type
_EVIDENCE_TYPE_MAP = {
    "task_proposed": "hypothesis",
    "task_picked_up": "experiment",
    "task_completed": "result",
    "critique_filed": "challenge",
    "voting_started": "roundtable",
    "vote_cast": "decision",
    "vote_resolved": "decision",
    "task_verified": "verification",
}

# Status sort order
_STATUS_ORDER = {
    "established": 0,
    "under_investigation": 1,
    "contested": 2,
    "proposed": 3,
}


def _evidence_outcome(activity_type: str, task: Task) -> str | None:
    """Derive outcome for certain evidence types."""
    if activity_type == "vote_resolved":
        return "confirmed" if task.status == "accepted" else "rejected"
    if activity_type == "task_verified" and task.verification_score is not None:
        score = float(task.verification_score)
        if score >= 0.85:
            return "confirmed"
        if score >= 0.5:
            return "inconclusive"
        return "rejected"
    return None


@router.get("/lab-state", response_model=list[LabStateItemResponse])
async def get_lab_state(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Return tasks enriched with activity evidence and signature chains."""
    # 1. Resolve lab
    result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    # 2. Fetch tasks (exclude rejected/superseded)
    task_result = await db.execute(
        select(Task)
        .where(Task.lab_id == lab.id, Task.status.notin_(["rejected", "superseded"]))
        .order_by(Task.created_at)
    )
    tasks = list(task_result.scalars().all())
    if not tasks:
        return []

    task_ids = [t.id for t in tasks]
    task_by_id = {t.id: t for t in tasks}

    # 3. Batch-fetch activity log entries for these tasks
    activity_result = await db.execute(
        select(LabActivityLog)
        .where(LabActivityLog.task_id.in_(task_ids))
        .order_by(LabActivityLog.created_at)
    )
    activities = list(activity_result.scalars().all())

    # Group activities by task_id
    activities_by_task: dict[UUID, list[LabActivityLog]] = {}
    for act in activities:
        if act.task_id:
            activities_by_task.setdefault(act.task_id, []).append(act)

    # 4. Batch-fetch signature chain for accepted tasks
    accepted_ids = [t.id for t in tasks if t.status == "accepted"]
    sig_entries: dict[UUID, list[SignatureChain]] = {}
    if accepted_ids:
        sig_result = await db.execute(
            select(SignatureChain)
            .where(
                SignatureChain.entity_type == "task",
                SignatureChain.entity_id.in_(accepted_ids),
            )
            .order_by(SignatureChain.created_at)
        )
        for sig in sig_result.scalars().all():
            sig_entries.setdefault(sig.entity_id, []).append(sig)

    # 5. Batch-load agent display names
    agent_ids: set[UUID] = set()
    for t in tasks:
        agent_ids.add(t.proposed_by)
    for act in activities:
        if act.agent_id:
            agent_ids.add(act.agent_id)
    for sigs in sig_entries.values():
        for sig in sigs:
            agent_ids.add(sig.agent_id)

    agent_names: dict[UUID, str] = {}
    if agent_ids:
        agent_result = await db.execute(
            select(Agent.id, Agent.display_name).where(Agent.id.in_(agent_ids))
        )
        for row in agent_result.all():
            agent_names[row.id] = row.display_name

    # 6. Count votes per task as reference_count proxy
    vote_result = await db.execute(
        select(TaskVote.task_id, TaskVote.id)
        .where(TaskVote.task_id.in_(task_ids))
    )
    vote_counts: dict[UUID, int] = {}
    for row in vote_result.all():
        vote_counts[row.task_id] = vote_counts.get(row.task_id, 0) + 1

    # 7. Build response items
    items: list[LabStateItemResponse] = []
    for task in tasks:
        status = _STATUS_MAP.get(task.status)
        if status is None:
            continue

        # Map activities → evidence entries
        evidence: list[EvidenceEntryResponse] = []
        for act in activities_by_task.get(task.id, []):
            ev_type = _EVIDENCE_TYPE_MAP.get(act.activity_type)
            if ev_type is None:
                continue

            # Day label: days since task creation + 1
            days = (act.created_at - task.created_at).days + 1
            day_label = f"Day {days}" if days > 0 else "Day 1"

            evidence.append(
                EvidenceEntryResponse(
                    type=ev_type,
                    description=act.message,
                    agent=agent_names.get(act.agent_id, str(act.agent_id)) if act.agent_id else "system",
                    day_label=day_label,
                    outcome=_evidence_outcome(act.activity_type, task),
                )
            )

        # Map signature chain
        signature_chain: list[SignatureEntryResponse] = []
        for sig in sig_entries.get(task.id, []):
            signature_chain.append(
                SignatureEntryResponse(
                    action=sig.action,
                    agent_id=str(sig.agent_id),
                    signature_hash=sig.signature[:16],
                    timestamp=sig.created_at.isoformat(),
                )
            )

        items.append(
            LabStateItemResponse(
                id=task.id,
                title=task.title,
                status=status,
                verification_score=float(task.verification_score) if task.verification_score is not None else None,
                reference_count=vote_counts.get(task.id, 0),
                domain=task.domain,
                proposed_by=agent_names.get(task.proposed_by, str(task.proposed_by)),
                current_summary=task.description,
                signature_chain=signature_chain,
                evidence=evidence,
            )
        )

    # 8. Sort: established first, then under_investigation, contested, proposed
    items.sort(key=lambda i: _STATUS_ORDER.get(i.status, 99))

    return items
