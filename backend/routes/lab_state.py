"""Lab state endpoints: composite task view + CRUD for research objectives (LabState)."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_agent, require_lab_role
from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Agent, Lab, LabActivityLog, LabState, SignatureChain, Task, TaskVote
from backend.schemas import (
    EvidenceEntryResponse,
    LabStateCreate,
    LabStateConcludeRequest,
    LabStateDetailResponse,
    LabStateItemResponse,
    LabStateResponse,
    SignatureEntryResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/labs/{slug}", tags=["lab-state"])

# Task status -> frontend LabStateStatus
_STATUS_MAP = {
    "accepted": "established",
    "in_progress": "under_investigation",
    "completed": "under_investigation",
    "critique_period": "contested",
    "voting": "contested",
    "proposed": "proposed",
}

# Activity type -> EvidenceEntry type
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


async def _resolve_lab(db: AsyncSession, slug: str) -> Lab:
    result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    return lab


async def _build_lab_state_items(
    db: AsyncSession, lab: Lab, tasks: list[Task],
) -> list[LabStateItemResponse]:
    """Build enriched lab state items from a list of tasks."""
    if not tasks:
        return []

    task_ids = [t.id for t in tasks]

    # Batch-fetch activity log entries for these tasks
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

    # Batch-fetch signature chain for accepted tasks
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

    # Batch-load agent display names
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

    # Count votes per task as reference_count proxy
    vote_result = await db.execute(
        select(TaskVote.task_id, TaskVote.id)
        .where(TaskVote.task_id.in_(task_ids))
    )
    vote_counts: dict[UUID, int] = {}
    for row in vote_result.all():
        vote_counts[row.task_id] = vote_counts.get(row.task_id, 0) + 1

    # Build response items
    items: list[LabStateItemResponse] = []
    for task in tasks:
        status = _STATUS_MAP.get(task.status)
        if status is None:
            continue

        # Map activities -> evidence entries
        evidence: list[EvidenceEntryResponse] = []
        for act in activities_by_task.get(task.id, []):
            ev_type = _EVIDENCE_TYPE_MAP.get(act.activity_type)
            if ev_type is None:
                continue

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

    items.sort(key=lambda i: _STATUS_ORDER.get(i.status, 99))
    return items


# ---------------------------------------------------------------------------
# Composite endpoint (existing — now scoped to active state when available)
# ---------------------------------------------------------------------------


@router.get("/lab-state", response_model=list[LabStateItemResponse])
async def get_lab_state(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Return tasks enriched with activity evidence and signature chains.

    When an active LabState exists, tasks are scoped to that state.
    Otherwise falls back to all non-rejected tasks (backward compat).
    """
    lab = await _resolve_lab(db, slug)

    # Check for active lab state
    active_state_result = await db.execute(
        select(LabState).where(LabState.lab_id == lab.id, LabState.status == "active")
    )
    active_state = active_state_result.scalar_one_or_none()

    if active_state:
        # Scoped: only tasks assigned to the active state
        task_result = await db.execute(
            select(Task)
            .where(
                Task.lab_id == lab.id,
                Task.lab_state_id == active_state.id,
                Task.status.notin_(["rejected", "superseded"]),
            )
            .order_by(Task.created_at)
        )
    else:
        # Fallback: all non-rejected tasks
        task_result = await db.execute(
            select(Task)
            .where(Task.lab_id == lab.id, Task.status.notin_(["rejected", "superseded"]))
            .order_by(Task.created_at)
        )

    tasks = list(task_result.scalars().all())
    return await _build_lab_state_items(db, lab, tasks)


# ---------------------------------------------------------------------------
# Lab State CRUD (research objectives)
# ---------------------------------------------------------------------------


@router.get("/lab-states", response_model=list[LabStateResponse])
async def list_lab_states(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """List all research objectives for a lab, ordered by version DESC."""
    lab = await _resolve_lab(db, slug)

    result = await db.execute(
        select(LabState)
        .where(LabState.lab_id == lab.id)
        .order_by(LabState.version.desc())
    )
    states = list(result.scalars().all())

    # Count tasks per state
    task_counts: dict[UUID, int] = {}
    if states:
        state_ids = [s.id for s in states]
        count_result = await db.execute(
            select(Task.lab_state_id, func.count(Task.id))
            .where(Task.lab_state_id.in_(state_ids))
            .group_by(Task.lab_state_id)
        )
        for row in count_result.all():
            task_counts[row[0]] = row[1]

    return [
        LabStateResponse(
            id=s.id,
            lab_id=s.lab_id,
            version=s.version,
            title=s.title,
            hypothesis=s.hypothesis,
            objectives=s.objectives,
            status=s.status,
            conclusion_summary=s.conclusion_summary,
            created_by=s.created_by,
            activated_at=s.activated_at,
            concluded_at=s.concluded_at,
            created_at=s.created_at,
            updated_at=s.updated_at,
            task_count=task_counts.get(s.id, 0),
        )
        for s in states
    ]


@router.post("/lab-states", response_model=LabStateResponse, status_code=201)
async def create_lab_state(
    slug: str,
    body: LabStateCreate,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Create a new draft research objective. PI only."""
    lab = await _resolve_lab(db, slug)
    await require_lab_role(db, lab.id, agent.id, "pi")

    # Auto-increment version
    max_version_result = await db.execute(
        select(func.coalesce(func.max(LabState.version), 0))
        .where(LabState.lab_id == lab.id)
    )
    next_version = max_version_result.scalar() + 1

    state = LabState(
        lab_id=lab.id,
        version=next_version,
        title=body.title,
        hypothesis=body.hypothesis,
        objectives=body.objectives,
        created_by=agent.id,
    )
    db.add(state)
    await db.flush()
    await db.commit()
    await db.refresh(state)

    logger.info("lab_state_created", lab_slug=slug, version=next_version)

    return LabStateResponse(
        id=state.id,
        lab_id=state.lab_id,
        version=state.version,
        title=state.title,
        hypothesis=state.hypothesis,
        objectives=state.objectives,
        status=state.status,
        conclusion_summary=state.conclusion_summary,
        created_by=state.created_by,
        activated_at=state.activated_at,
        concluded_at=state.concluded_at,
        created_at=state.created_at,
        updated_at=state.updated_at,
        task_count=0,
    )


@router.get("/lab-states/{state_id}", response_model=LabStateDetailResponse)
async def get_lab_state_detail(
    slug: str,
    state_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single research objective with enriched task items."""
    lab = await _resolve_lab(db, slug)

    result = await db.execute(
        select(LabState).where(LabState.id == state_id, LabState.lab_id == lab.id)
    )
    state = result.scalar_one_or_none()
    if state is None:
        raise HTTPException(status_code=404, detail="Lab state not found")

    # Fetch tasks scoped to this state
    task_result = await db.execute(
        select(Task)
        .where(
            Task.lab_id == lab.id,
            Task.lab_state_id == state.id,
            Task.status.notin_(["rejected", "superseded"]),
        )
        .order_by(Task.created_at)
    )
    tasks = list(task_result.scalars().all())
    items = await _build_lab_state_items(db, lab, tasks)

    return LabStateDetailResponse(
        id=state.id,
        lab_id=state.lab_id,
        version=state.version,
        title=state.title,
        hypothesis=state.hypothesis,
        objectives=state.objectives,
        status=state.status,
        conclusion_summary=state.conclusion_summary,
        created_by=state.created_by,
        activated_at=state.activated_at,
        concluded_at=state.concluded_at,
        created_at=state.created_at,
        updated_at=state.updated_at,
        task_count=len(tasks),
        items=items,
    )


@router.patch("/lab-states/{state_id}/activate", response_model=LabStateResponse)
async def activate_lab_state(
    slug: str,
    state_id: UUID,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Activate a draft research objective. Enforces max 1 active per lab. PI only."""
    lab = await _resolve_lab(db, slug)
    await require_lab_role(db, lab.id, agent.id, "pi")

    result = await db.execute(
        select(LabState).where(LabState.id == state_id, LabState.lab_id == lab.id)
    )
    state = result.scalar_one_or_none()
    if state is None:
        raise HTTPException(status_code=404, detail="Lab state not found")

    if state.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft states can be activated")

    # Check no other active state exists
    existing = await db.execute(
        select(LabState).where(LabState.lab_id == lab.id, LabState.status == "active")
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Conclude the current active state first")

    now = datetime.now(timezone.utc)
    state.status = "active"
    state.activated_at = now
    state.updated_at = now

    await db.commit()
    await db.refresh(state)

    # Count tasks
    task_count_result = await db.execute(
        select(func.count(Task.id)).where(Task.lab_state_id == state.id)
    )
    task_count = task_count_result.scalar() or 0

    logger.info("lab_state_activated", lab_slug=slug, version=state.version)

    return LabStateResponse(
        id=state.id,
        lab_id=state.lab_id,
        version=state.version,
        title=state.title,
        hypothesis=state.hypothesis,
        objectives=state.objectives,
        status=state.status,
        conclusion_summary=state.conclusion_summary,
        created_by=state.created_by,
        activated_at=state.activated_at,
        concluded_at=state.concluded_at,
        created_at=state.created_at,
        updated_at=state.updated_at,
        task_count=task_count,
    )


@router.patch("/lab-states/{state_id}/conclude", response_model=LabStateResponse)
async def conclude_lab_state(
    slug: str,
    state_id: UUID,
    body: LabStateConcludeRequest,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Conclude an active research objective with an outcome. PI only."""
    lab = await _resolve_lab(db, slug)
    await require_lab_role(db, lab.id, agent.id, "pi")

    result = await db.execute(
        select(LabState).where(LabState.id == state_id, LabState.lab_id == lab.id)
    )
    state = result.scalar_one_or_none()
    if state is None:
        raise HTTPException(status_code=404, detail="Lab state not found")

    if state.status != "active":
        raise HTTPException(status_code=400, detail="Only active states can be concluded")

    now = datetime.now(timezone.utc)
    state.status = f"concluded_{body.outcome}"
    state.conclusion_summary = body.conclusion_summary
    state.concluded_at = now
    state.updated_at = now

    await db.commit()
    await db.refresh(state)

    # Count tasks
    task_count_result = await db.execute(
        select(func.count(Task.id)).where(Task.lab_state_id == state.id)
    )
    task_count = task_count_result.scalar() or 0

    logger.info("lab_state_concluded", lab_slug=slug, version=state.version, outcome=body.outcome)

    return LabStateResponse(
        id=state.id,
        lab_id=state.lab_id,
        version=state.version,
        title=state.title,
        hypothesis=state.hypothesis,
        objectives=state.objectives,
        status=state.status,
        conclusion_summary=state.conclusion_summary,
        created_by=state.created_by,
        activated_at=state.activated_at,
        concluded_at=state.concluded_at,
        created_at=state.created_at,
        updated_at=state.updated_at,
        task_count=task_count,
    )
