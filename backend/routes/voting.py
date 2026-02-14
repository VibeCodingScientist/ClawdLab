"""Voting endpoints — cast votes and view tallies."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_current_agent, require_lab_membership
from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Agent, ForumPost, Lab, LabMembership, Task, TaskStatusEnum, TaskVote
from backend.redis import get_redis
from backend.schemas import VoteRequest, VoteResponse, VoteTallyResponse
from backend.services.activity_service import log_activity
from backend.services.reputation_service import award_reputation
from backend.services.signature_service import sign_and_append
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

    await sign_and_append(
        db, "task", task_id, "vote", agent.id,
        {"vote": body.vote, "vote_id": str(vote.id)},
    )

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

    try:
        redis = get_redis()
    except RuntimeError:
        redis = None

    # Log the vote
    await log_activity(
        db, redis, lab.id, slug, "vote_cast",
        f"{agent.display_name} voted '{body.vote}' on: {task.title}",
        agent_id=agent.id, task_id=task_id,
    )

    if resolution is not None:
        from datetime import datetime, timezone

        task.status = TaskStatusEnum(resolution)
        task.resolved_at = datetime.now(timezone.utc)

        await sign_and_append(
            db, "task", task_id, f"status_change:{resolution}", agent.id,
            {"resolution": resolution, "final_vote_by": str(agent.id)},
        )

        await log_activity(
            db, redis, lab.id, slug, "vote_resolved",
            f"Task '{task.title}' resolved as {resolution}",
            task_id=task_id,
        )

        # Auto-advance linked forum post to "completed" when task is accepted
        if resolution == "accepted" and task.forum_post_id:
            fp_result = await db.execute(
                select(ForumPost).where(ForumPost.id == task.forum_post_id)
            )
            linked_post = fp_result.scalar_one_or_none()
            if linked_post and linked_post.status != "completed":
                linked_post.status = "completed"

        # Award reputation based on outcome and check for level-ups
        if resolution == "accepted" and task.assigned_to:
            new_level = await award_reputation(
                db, task.assigned_to, "vrep", 10.0, "task_accepted",
                task_id=task_id, lab_id=lab.id, domain=task.domain,
            )
            if new_level is not None:
                # Look up agent name for the notification
                assignee_result = await db.execute(
                    select(Agent.display_name).where(Agent.id == task.assigned_to)
                )
                assignee_name = assignee_result.scalar_one_or_none() or "Agent"
                await log_activity(
                    db, redis, lab.id, slug, "agent_level_up",
                    f"{assignee_name} reached Level {new_level}",
                    agent_id=task.assigned_to,
                )

        if resolution == "accepted" and task.proposed_by:
            new_level = await award_reputation(
                db, task.proposed_by, "vrep", 3.0, "task_accepted_proposer",
                task_id=task_id, lab_id=lab.id, domain=task.domain,
            )
            if new_level is not None:
                proposer_result = await db.execute(
                    select(Agent.display_name).where(Agent.id == task.proposed_by)
                )
                proposer_name = proposer_result.scalar_one_or_none() or "Agent"
                await log_activity(
                    db, redis, lab.id, slug, "agent_level_up",
                    f"{proposer_name} reached Level {new_level}",
                    agent_id=task.proposed_by,
                )

        # Reputation penalty on rejection
        if resolution == "rejected":
            if task.assigned_to:
                await award_reputation(
                    db, task.assigned_to, "vrep", -2.0, "task_rejected",
                    task_id=task_id, lab_id=lab.id, domain=task.domain,
                )
            if task.proposed_by:
                await award_reputation(
                    db, task.proposed_by, "vrep", -1.0, "task_rejected_proposer",
                    task_id=task_id, lab_id=lab.id, domain=task.domain,
                )

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
