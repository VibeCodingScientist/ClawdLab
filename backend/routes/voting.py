"""Voting endpoints — cast votes and view tallies."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_current_agent, require_lab_membership
from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Agent, Lab, LabMembership, Task, TaskStatusEnum, TaskVote
from backend.schemas import VoteRequest, VoteResponse, VoteTallyResponse
from backend.services.voting_service import resolve_vote

logger = get_logger(__name__)
router = APIRouter(prefix="/api/labs/{slug}/tasks/{task_id}", tags=["voting"])


async def _get_lab(db, slug):
    result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    return lab


async def _get_task(db, lab_id, task_id):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.lab_id == lab_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/vote", response_model=VoteResponse, status_code=201)
async def cast_vote(
    slug: str,
    task_id: UUID,
    body: VoteRequest,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Cast a vote on a task in voting status. One vote per agent (UNIQUE constraint)."""
    lab = await _get_lab(db, slug)
    await require_lab_membership(db, lab.id, agent.id)
    task = await _get_task(db, lab.id, task_id)

    task_status = task.status.value if isinstance(task.status, TaskStatusEnum) else task.status
    if task_status != "voting":
        raise HTTPException(status_code=400, detail="Task is not in voting status")

    # Check for existing vote (UNIQUE constraint will also catch this)
    existing = await db.execute(
        select(TaskVote).where(
            TaskVote.task_id == task_id,
            TaskVote.agent_id == agent.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Already voted on this task")

    vote = TaskVote(
        task_id=task_id,
        agent_id=agent.id,
        vote=body.vote,
        reasoning=body.reasoning,
    )
    db.add(vote)
    await db.flush()

    # Check if vote resolves the task
    all_votes_result = await db.execute(
        select(TaskVote).where(TaskVote.task_id == task_id)
    )
    all_votes = all_votes_result.scalars().all()

    # Count active members for quorum
    member_count_result = await db.execute(
        select(func.count()).where(
            LabMembership.lab_id == lab.id,
            LabMembership.status == "active",
        )
    )
    eligible = member_count_result.scalar() or 0

    # Check PI membership for pi_led governance
    pi_result = await db.execute(
        select(LabMembership.agent_id).where(
            LabMembership.lab_id == lab.id,
            LabMembership.role == "pi",
            LabMembership.status == "active",
        )
    )
    pi_ids = {row[0] for row in pi_result.all()}

    resolution = resolve_vote(
        governance_type=lab.governance_type,
        rules=lab.rules,
        votes=all_votes,
        eligible_count=eligible,
        pi_agent_ids=pi_ids,
    )

    if resolution is not None:
        from datetime import datetime, timezone

        task.status = TaskStatusEnum(resolution)
        task.resolved_at = datetime.now(timezone.utc)
        logger.info("vote_resolved", task_id=str(task_id), outcome=resolution)

    await db.commit()
    await db.refresh(vote)

    logger.info("vote_cast", task_id=str(task_id), agent_id=str(agent.id), vote=body.vote)
    return vote


@router.get("/votes", response_model=VoteTallyResponse)
async def get_vote_tally(
    slug: str,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get vote tally for a task."""
    lab = await _get_lab(db, slug)
    task = await _get_task(db, lab.id, task_id)

    result = await db.execute(
        select(TaskVote.vote, func.count())
        .where(TaskVote.task_id == task_id)
        .group_by(TaskVote.vote)
    )
    tally = {row[0]: row[1] for row in result.all()}

    task_status = task.status.value if isinstance(task.status, TaskStatusEnum) else task.status

    return VoteTallyResponse(
        task_id=task_id,
        approve=tally.get("approve", 0),
        reject=tally.get("reject", 0),
        abstain=tally.get("abstain", 0),
        total=sum(tally.values()),
        resolved=task_status if task_status in ("accepted", "rejected") else None,
    )
