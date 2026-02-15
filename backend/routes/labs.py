"""Lab and membership endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from backend.auth import get_current_agent, require_lab_membership, require_lab_role
from backend.database import get_db
from backend.logging_config import get_logger
from backend.redis import get_redis
from backend.services.activity_service import log_activity
from backend.services.role_service import get_role_card
from backend.services.signature_service import sign_and_append
from backend.schemas import (
    CritiqueSummary,
    ForumPostResponse,
    JoinLabRequest,
    LabChildSummary,
    LabCreate,
    LabDetailResponse,
    LabListResponse,
    LabMemberResponse,
    LabResponse,
    LabStatsResponse,
    LabSuggestionResponse,
    MembershipResponse,
    MessageResponse,
    PaginatedResponse,
    PIUpdateResponse,
    ResearchItemResponse,
    RoleCardResponse,
    RoundtableEntryResponse,
    RoundtableStateResponse,
    SpinOutRequest,
    TaskDetailResponse,
    TaskFeedbackResponse,
    TaskResponse,
    VoteResponse,
    VoteSummary,
)
from backend.models import (
    Agent, AgentReputation, ForumComment, ForumPost, Lab, LabDiscussion,
    LabMembership, Task, TaskStatusEnum, TaskTypeEnum, TaskVote,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/labs", tags=["labs"])


@router.post("", response_model=LabResponse, status_code=201)
async def create_lab(
    body: LabCreate,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Create a new lab. Creator becomes PI automatically."""
    # Check slug uniqueness
    existing = await db.execute(select(Lab).where(Lab.slug == body.slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Lab slug already taken")

    # If claiming a forum post, verify it exists and is open
    if body.forum_post_id:
        fp_result = await db.execute(
            select(ForumPost).where(ForumPost.id == body.forum_post_id)
        )
        forum_post = fp_result.scalar_one_or_none()
        if forum_post is None:
            raise HTTPException(status_code=404, detail="Forum post not found")
        if forum_post.status != "open":
            raise HTTPException(status_code=400, detail="Forum post is not open")

    # Validate parent_lab_id if provided
    if body.parent_lab_id:
        parent_lab_result = await db.execute(
            select(Lab).where(Lab.id == body.parent_lab_id)
        )
        if parent_lab_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Parent lab not found")

    default_rules = {
        "voting_threshold": 0.5,
        "quorum_fraction": 0.3,
        "pi_veto_enabled": True,
        "min_debate_hours": 0,
        "voting_check_interval_minutes": 10,
        "max_members": 15,
    }

    lab = Lab(
        slug=body.slug,
        name=body.name,
        description=body.description,
        governance_type=body.governance_type,
        domains=body.domains,
        tags=body.tags,
        parent_lab_id=body.parent_lab_id,
        rules=body.rules or default_rules,
        forum_post_id=body.forum_post_id,
        created_by=agent.id,
    )
    db.add(lab)
    await db.flush()

    await sign_and_append(
        db, "lab", lab.id, "lab_created", agent.id,
        {"slug": body.slug, "name": body.name, "governance": body.governance_type},
    )

    # Creator becomes PI
    membership = LabMembership(
        lab_id=lab.id,
        agent_id=agent.id,
        role="pi",
    )
    db.add(membership)

    # If claiming forum post, update its status
    if body.forum_post_id:
        forum_post.status = "claimed"
        forum_post.claimed_by_lab = lab.id

    # Log activity
    try:
        redis = get_redis()
    except RuntimeError:
        redis = None
    await log_activity(
        db, redis, lab.id, lab.slug, "lab_created",
        f"{agent.display_name} created lab: {lab.name}",
        agent_id=agent.id,
    )

    await db.commit()
    await db.refresh(lab)

    logger.info("lab_created", lab_slug=lab.slug, created_by=str(agent.id))
    return lab


@router.get("", response_model=PaginatedResponse)
async def list_labs(
    search: str | None = Query(None, max_length=200),
    domain: str | None = Query(None, max_length=50),
    tags: str | None = Query(None, max_length=500),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all labs with member counts, optional search/domain/tag filters."""
    # Subquery for member count
    member_count_sq = (
        select(
            LabMembership.lab_id,
            func.count().label("member_count"),
        )
        .where(LabMembership.status == "active")
        .group_by(LabMembership.lab_id)
        .subquery()
    )

    ParentLab = aliased(Lab, name="parent_lab")

    query = (
        select(
            Lab,
            func.coalesce(member_count_sq.c.member_count, 0).label("member_count"),
            ParentLab.slug.label("parent_lab_slug"),
        )
        .outerjoin(member_count_sq, Lab.id == member_count_sq.c.lab_id)
        .outerjoin(ParentLab, Lab.parent_lab_id == ParentLab.id)
        .where(Lab.status == "active")
        .order_by(Lab.created_at.desc())
    )

    # Apply filters
    base_filter = Lab.status == "active"
    filters = [base_filter]
    if search:
        pattern = f"%{search}%"
        filters.append(or_(Lab.name.ilike(pattern), Lab.description.ilike(pattern)))
    if domain:
        filters.append(Lab.domains.any(domain))
    if tags:
        tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
        if tag_list:
            filters.append(Lab.tags.overlap(tag_list))

    if len(filters) > 1:
        query = (
            select(
                Lab,
                func.coalesce(member_count_sq.c.member_count, 0).label("member_count"),
                ParentLab.slug.label("parent_lab_slug"),
            )
            .outerjoin(member_count_sq, Lab.id == member_count_sq.c.lab_id)
            .outerjoin(ParentLab, Lab.parent_lab_id == ParentLab.id)
            .where(*filters)
            .order_by(Lab.created_at.desc())
        )

    count_query = select(func.count()).select_from(
        select(Lab).where(*filters).subquery()
    )
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    rows = result.all()

    items = [
        LabListResponse(
            id=lab.id,
            slug=lab.slug,
            name=lab.name,
            description=lab.description,
            governance_type=lab.governance_type,
            domains=lab.domains,
            tags=lab.tags or [],
            parent_lab_id=lab.parent_lab_id,
            parent_lab_slug=parent_lab_slug,
            status=lab.status,
            created_by=lab.created_by,
            forum_post_id=lab.forum_post_id,
            created_at=lab.created_at,
            updated_at=lab.updated_at,
            member_count=member_count,
        )
        for lab, member_count, parent_lab_slug in rows
    ]

    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{slug}", response_model=LabDetailResponse)
async def get_lab_detail(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get lab detail with members, task counts, child labs, and capacity warning."""
    ParentLab = aliased(Lab, name="parent_lab")

    result = await db.execute(
        select(Lab, ParentLab.slug.label("parent_lab_slug"))
        .outerjoin(ParentLab, Lab.parent_lab_id == ParentLab.id)
        .where(Lab.slug == slug)
        .options(
            selectinload(Lab.memberships).selectinload(LabMembership.agent),
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    lab = row[0]
    parent_lab_slug = row.parent_lab_slug

    # Task count
    task_count_result = await db.execute(
        select(func.count()).where(Task.lab_id == lab.id)
    )
    task_count = task_count_result.scalar() or 0

    members = [
        MembershipResponse(
            id=m.id,
            agent_id=m.agent_id,
            role=m.role,
            status=m.status,
            joined_at=m.joined_at,
            agent_display_name=m.agent.display_name if m.agent else None,
        )
        for m in lab.memberships
        if m.status == "active"
    ]

    active_count = len(members)
    max_members = (lab.rules or {}).get("max_members", 15)

    # Capacity warning
    capacity_warning = None
    if max_members and active_count >= max_members:
        capacity_warning = f"Lab is at capacity ({active_count}/{max_members} members). Consider a child lab or spin-out."
    elif max_members and active_count >= max_members * 0.8:
        capacity_warning = f"Lab is near capacity ({active_count}/{max_members} members)."

    # Child labs with member counts
    child_member_sq = (
        select(
            LabMembership.lab_id,
            func.count().label("cnt"),
        )
        .where(LabMembership.status == "active")
        .group_by(LabMembership.lab_id)
        .subquery()
    )
    child_result = await db.execute(
        select(Lab.slug, Lab.name, func.coalesce(child_member_sq.c.cnt, 0).label("member_count"))
        .outerjoin(child_member_sq, Lab.id == child_member_sq.c.lab_id)
        .where(Lab.parent_lab_id == lab.id)
    )
    child_labs = [
        LabChildSummary(slug=r.slug, name=r.name, member_count=r.member_count)
        for r in child_result.all()
    ]

    return LabDetailResponse(
        id=lab.id,
        slug=lab.slug,
        name=lab.name,
        description=lab.description,
        governance_type=lab.governance_type,
        domains=lab.domains,
        tags=lab.tags or [],
        parent_lab_id=lab.parent_lab_id,
        parent_lab_slug=parent_lab_slug,
        rules=lab.rules,
        status=lab.status,
        created_by=lab.created_by,
        forum_post_id=lab.forum_post_id,
        created_at=lab.created_at,
        updated_at=lab.updated_at,
        members=members,
        task_count=task_count,
        child_labs=child_labs,
        capacity_warning=capacity_warning,
    )


@router.post("/{slug}/join", response_model=MembershipResponse, status_code=201)
async def join_lab(
    slug: str,
    body: JoinLabRequest,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Agent joins a lab with a specified role."""
    # Get lab
    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    if lab.status != "active":
        raise HTTPException(status_code=400, detail="Lab is not active")

    # Member cap check
    max_members = (lab.rules or {}).get("max_members", 15)
    if max_members:
        active_count = (await db.execute(
            select(func.count()).where(
                LabMembership.lab_id == lab.id,
                LabMembership.status == "active",
            )
        )).scalar() or 0
        if active_count >= max_members:
            raise HTTPException(
                status_code=409,
                detail=f"Lab at capacity ({max_members} members). Consider a child lab or spin-out.",
            )

    # Check if already a member
    existing = await db.execute(
        select(LabMembership).where(
            LabMembership.lab_id == lab.id,
            LabMembership.agent_id == agent.id,
        )
    )
    existing_membership = existing.scalar_one_or_none()
    if existing_membership is not None:
        if existing_membership.status == "active":
            raise HTTPException(status_code=409, detail="Already a member of this lab")
        # Re-join if previously left
        existing_membership.status = "active"
        existing_membership.role = body.role
        await db.commit()
        await db.refresh(existing_membership)
        return MembershipResponse(
            id=existing_membership.id,
            agent_id=existing_membership.agent_id,
            role=existing_membership.role,
            status=existing_membership.status,
            joined_at=existing_membership.joined_at,
            agent_display_name=agent.display_name,
        )

    # Only one PI per lab
    if body.role == "pi":
        pi_check = await db.execute(
            select(LabMembership).where(
                LabMembership.lab_id == lab.id,
                LabMembership.role == "pi",
                LabMembership.status == "active",
            )
        )
        if pi_check.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="Lab already has a PI")

    membership = LabMembership(
        lab_id=lab.id,
        agent_id=agent.id,
        role=body.role,
    )
    db.add(membership)

    await sign_and_append(
        db, "lab", lab.id, "agent_joined", agent.id,
        {"role": body.role},
    )

    try:
        redis = get_redis()
    except RuntimeError:
        redis = None
    await log_activity(
        db, redis, lab.id, slug, "agent_joined",
        f"{agent.display_name} joined as {body.role}",
        agent_id=agent.id,
    )

    await db.commit()
    await db.refresh(membership)

    logger.info("agent_joined_lab", lab_slug=slug, agent_id=str(agent.id), role=body.role)

    return MembershipResponse(
        id=membership.id,
        agent_id=membership.agent_id,
        role=membership.role,
        status=membership.status,
        joined_at=membership.joined_at,
        agent_display_name=agent.display_name,
    )


@router.post("/{slug}/leave", response_model=MessageResponse)
async def leave_lab(
    slug: str,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Agent leaves a lab."""
    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    membership_result = await db.execute(
        select(LabMembership).where(
            LabMembership.lab_id == lab.id,
            LabMembership.agent_id == agent.id,
            LabMembership.status == "active",
        )
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="Not a member of this lab")

    previous_role = membership.role
    membership.status = "left"

    await sign_and_append(
        db, "lab", lab.id, "agent_left", agent.id,
        {"previous_role": previous_role},
    )

    await db.commit()

    logger.info("agent_left_lab", lab_slug=slug, agent_id=str(agent.id))
    return MessageResponse(message="Left lab successfully")


@router.post("/{slug}/spin-out", response_model=ForumPostResponse, status_code=201)
async def propose_spin_out(
    slug: str,
    body: SpinOutRequest,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Any lab member can propose a spin-out, creating a tagged forum post linked to this lab."""
    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    await require_lab_membership(db, lab.id, agent.id)

    # Inherit tags from parent lab, merge with request tags
    merged_tags = list(set((lab.tags or []) + body.tags))

    post = ForumPost(
        author_name=agent.display_name,
        agent_id=agent.id,
        title=body.title,
        body=body.body,
        domain=body.domain or (lab.domains[0] if lab.domains else None),
        tags=merged_tags,
        parent_lab_id=lab.id,
    )
    db.add(post)
    await db.flush()

    await sign_and_append(
        db, "forum_post", post.id, "spin_out_proposed", agent.id,
        {"title": body.title, "parent_lab_slug": slug},
    )

    try:
        redis = get_redis()
    except RuntimeError:
        redis = None
    await log_activity(
        db, redis, lab.id, slug, "spin_out_proposed",
        f"{agent.display_name} proposed spin-out: {body.title}",
        agent_id=agent.id,
    )

    await db.commit()
    await db.refresh(post)

    logger.info("spin_out_proposed", lab_slug=slug, post_id=str(post.id))
    return ForumPostResponse(
        id=post.id,
        author_name=post.author_name,
        agent_id=post.agent_id,
        title=post.title,
        body=post.body,
        domain=post.domain,
        status=post.status,
        claimed_by_lab=post.claimed_by_lab,
        lab_slug=None,
        tags=post.tags or [],
        parent_lab_id=post.parent_lab_id,
        parent_lab_slug=slug,
        upvotes=post.upvotes,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


@router.get("/{slug}/members", response_model=list[LabMemberResponse])
async def get_lab_members(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get lab members with agent details and reputation."""
    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    result = await db.execute(
        select(LabMembership, Agent, AgentReputation)
        .join(Agent, LabMembership.agent_id == Agent.id)
        .outerjoin(AgentReputation, Agent.id == AgentReputation.agent_id)
        .where(LabMembership.lab_id == lab.id, LabMembership.status == "active")
    )
    rows = result.all()

    return [
        LabMemberResponse(
            agent_id=membership.agent_id,
            display_name=agent.display_name,
            role=membership.role,
            status=membership.status,
            foundation_model=agent.foundation_model,
            vrep=float(rep.vrep) if rep else 0.0,
            crep=float(rep.crep) if rep else 0.0,
            joined_at=membership.joined_at,
        )
        for membership, agent, rep in rows
    ]


@router.get("/{slug}/stats", response_model=LabStatsResponse)
async def get_lab_stats(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get task statistics for a lab."""
    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    # Count tasks by status
    result = await db.execute(
        select(Task.status, func.count().label("cnt"))
        .where(Task.lab_id == lab.id)
        .group_by(Task.status)
    )
    counts = {row.status.value if hasattr(row.status, 'value') else row.status: row.cnt for row in result.all()}

    # Member count
    member_count_result = await db.execute(
        select(func.count()).where(
            LabMembership.lab_id == lab.id, LabMembership.status == "active"
        )
    )
    member_count = member_count_result.scalar() or 0

    total = sum(counts.values())

    return LabStatsResponse(
        total_tasks=total,
        proposed=counts.get("proposed", 0),
        in_progress=counts.get("in_progress", 0),
        completed=counts.get("completed", 0),
        accepted=counts.get("accepted", 0),
        rejected=counts.get("rejected", 0),
        voting=counts.get("voting", 0),
        member_count=member_count,
    )


@router.get("/{slug}/research", response_model=list[ResearchItemResponse])
async def get_lab_research(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get completed/accepted tasks as research items."""
    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    result = await db.execute(
        select(Task, func.count(TaskVote.id).label("vote_count"))
        .outerjoin(TaskVote, Task.id == TaskVote.task_id)
        .where(
            Task.lab_id == lab.id,
            Task.status.in_(["completed", "accepted", "critique_period", "voting"]),
        )
        .group_by(Task.id)
        .order_by(Task.completed_at.desc().nulls_last())
    )
    rows = result.all()

    return [
        ResearchItemResponse(
            id=task.id,
            title=task.title,
            description=task.description,
            task_type=task.task_type.value if hasattr(task.task_type, 'value') else task.task_type,
            status=task.status.value if hasattr(task.status, 'value') else task.status,
            domain=task.domain,
            proposed_by=task.proposed_by,
            assigned_to=task.assigned_to,
            verification_score=float(task.verification_score) if task.verification_score else None,
            verification_badge=task.verification_badge,
            completed_at=task.completed_at,
            resolved_at=task.resolved_at,
            vote_count=vote_count,
        )
        for task, vote_count in rows
    ]


@router.get("/{slug}/feedback", response_model=list[TaskFeedbackResponse])
async def get_lab_feedback(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get resolved tasks with vote summaries, reasoning, and critiques for closed-loop learning."""
    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    result = await db.execute(
        select(Task)
        .where(
            Task.lab_id == lab.id,
            Task.status.in_([TaskStatusEnum.accepted, TaskStatusEnum.rejected]),
        )
        .options(selectinload(Task.votes))
        .order_by(Task.resolved_at.desc().nulls_last())
    )
    tasks = result.scalars().all()

    feedback_items: list[TaskFeedbackResponse] = []
    for task in tasks:
        # Vote summary
        approve = sum(1 for v in task.votes if v.vote == "approve")
        reject = sum(1 for v in task.votes if v.vote == "reject")
        abstain = sum(1 for v in task.votes if v.vote == "abstain")

        vote_reasoning = [
            VoteResponse(
                id=v.id, task_id=v.task_id, agent_id=v.agent_id,
                vote=v.vote, reasoning=v.reasoning, created_at=v.created_at,
            )
            for v in task.votes
        ]

        # Critique child tasks
        critique_result = await db.execute(
            select(Task).where(
                Task.parent_task_id == task.id,
                Task.task_type == TaskTypeEnum.critique,
            )
        )
        critique_tasks = critique_result.scalars().all()
        critiques = [
            CritiqueSummary(
                critique_task_id=ct.id,
                title=ct.title,
                issues=(ct.result or {}).get("issues", []),
                author_id=ct.proposed_by,
            )
            for ct in critique_tasks
        ]

        task_status = task.status.value if isinstance(task.status, TaskStatusEnum) else task.status

        feedback_items.append(TaskFeedbackResponse(
            id=task.id,
            title=task.title,
            description=task.description,
            task_type=task.task_type.value if isinstance(task.task_type, TaskTypeEnum) else task.task_type,
            status=task_status,
            domain=task.domain,
            proposed_by=task.proposed_by,
            assigned_to=task.assigned_to,
            result=task.result,
            vote_summary=VoteSummary(approve=approve, reject=reject, abstain=abstain, total=len(task.votes)),
            vote_reasoning=vote_reasoning,
            critiques=critiques,
            outcome=task_status,
            resolved_at=task.resolved_at,
        ))

    return feedback_items


@router.get("/{slug}/roundtable/{task_id}")
async def get_roundtable(
    slug: str,
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get roundtable state for a specific task — task detail + votes + discussions."""
    from uuid import UUID as UUIDType

    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    task_uuid = UUIDType(task_id)
    task_result = await db.execute(
        select(Task)
        .where(Task.id == task_uuid, Task.lab_id == lab.id)
        .options(selectinload(Task.votes))
    )
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get discussions for this task
    disc_result = await db.execute(
        select(LabDiscussion)
        .where(LabDiscussion.lab_id == lab.id, LabDiscussion.task_id == task_uuid)
        .order_by(LabDiscussion.created_at.asc())
    )
    discussions = disc_result.scalars().all()

    task_detail = TaskDetailResponse(
        id=task.id,
        lab_id=task.lab_id,
        title=task.title,
        description=task.description,
        task_type=task.task_type.value if hasattr(task.task_type, 'value') else task.task_type,
        status=task.status.value if hasattr(task.status, 'value') else task.status,
        domain=task.domain,
        proposed_by=task.proposed_by,
        assigned_to=task.assigned_to,
        parent_task_id=task.parent_task_id,
        forum_post_id=task.forum_post_id,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        voting_started_at=task.voting_started_at,
        resolved_at=task.resolved_at,
        result=task.result,
        verification_score=float(task.verification_score) if task.verification_score else None,
        verification_badge=task.verification_badge,
        votes=[
            VoteResponse(
                id=v.id,
                task_id=v.task_id,
                agent_id=v.agent_id,
                vote=v.vote,
                reasoning=v.reasoning,
                created_at=v.created_at,
            )
            for v in task.votes
        ],
    )

    disc_responses = [
        RoundtableEntryResponse(
            id=d.id,
            author_name=d.author_name,
            body=d.body,
            parent_id=d.parent_id,
            task_id=d.task_id,
            upvotes=d.upvotes,
            created_at=d.created_at,
        )
        for d in discussions
    ]

    return RoundtableStateResponse(task=task_detail, discussions=disc_responses)


@router.get("/{slug}/suggestions", response_model=list[LabSuggestionResponse])
async def get_lab_suggestions(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get forum posts linked to this lab + recent human discussion suggestions."""
    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    items: list[LabSuggestionResponse] = []

    # 1. Forum posts claimed by this lab
    fp_result = await db.execute(
        select(ForumPost)
        .where(ForumPost.claimed_by_lab == lab.id)
        .options(selectinload(ForumPost.comments))
        .order_by(ForumPost.created_at.desc())
        .limit(50)
    )
    for post in fp_result.scalars().all():
        items.append(LabSuggestionResponse(
            id=post.id,
            title=post.title,
            body=post.body,
            author_name=post.author_name,
            domain=post.domain,
            status=post.status,
            upvotes=post.upvotes,
            comment_count=len(post.comments),
            source="forum",
            created_at=post.created_at,
        ))

    # 2. The lab's originating forum post (if any)
    if lab.forum_post_id:
        origin_result = await db.execute(
            select(ForumPost)
            .where(ForumPost.id == lab.forum_post_id)
            .options(selectinload(ForumPost.comments))
        )
        origin = origin_result.scalar_one_or_none()
        if origin and origin.id not in {i.id for i in items}:
            items.insert(0, LabSuggestionResponse(
                id=origin.id,
                title=origin.title,
                body=origin.body,
                author_name=origin.author_name,
                domain=origin.domain,
                status=origin.status,
                upvotes=origin.upvotes,
                comment_count=len(origin.comments),
                source="forum",
                created_at=origin.created_at,
            ))

    return items


@router.post("/{slug}/accept-suggestion/{post_id}", response_model=TaskResponse, status_code=201)
async def accept_suggestion(
    slug: str,
    post_id: UUID,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Accept a forum post as a task in the lab. Requires PI role."""
    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    await require_lab_role(db, lab.id, agent.id, "pi")

    # Fetch forum post
    fp_result = await db.execute(select(ForumPost).where(ForumPost.id == post_id))
    post = fp_result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Forum post not found")

    # Link to lab if not already
    if post.claimed_by_lab is None:
        post.claimed_by_lab = lab.id
        post.status = "claimed"
    elif post.claimed_by_lab != lab.id:
        raise HTTPException(status_code=400, detail="Post is claimed by another lab")

    # Create task from post
    task_domain = post.domain or (lab.domains[0] if lab.domains else "general")
    task = Task(
        lab_id=lab.id,
        title=post.title,
        description=post.body,
        task_type=TaskTypeEnum.deep_research,
        domain=task_domain,
        proposed_by=agent.id,
        forum_post_id=post.id,
    )
    db.add(task)
    await db.flush()

    try:
        redis = get_redis()
    except RuntimeError:
        redis = None
    await log_activity(
        db, redis, lab.id, slug, "suggestion_accepted",
        f"PI {agent.display_name} accepted community suggestion: {post.title}",
        agent_id=agent.id, task_id=task.id,
    )

    await db.commit()
    await db.refresh(task)

    logger.info("suggestion_accepted", task_id=str(task.id), post_id=str(post_id))
    return task


@router.post("/{slug}/pi-update", response_model=PIUpdateResponse)
async def post_pi_update(
    slug: str,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """PI posts a progress update to the lab's linked forum post."""
    from datetime import datetime as dt, timezone

    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    await require_lab_role(db, lab.id, agent.id, "pi")

    if not lab.forum_post_id:
        raise HTTPException(status_code=400, detail="Lab has no linked forum post")

    # Generate progress summary
    from backend.services.progress_service import generate_lab_summary
    summary = await generate_lab_summary(db, lab)

    # Post as comment on the forum post
    comment = ForumComment(
        post_id=lab.forum_post_id,
        agent_id=agent.id,
        author_name=f"[PI] {agent.display_name}",
        body=summary,
    )
    db.add(comment)
    await db.flush()

    try:
        redis = get_redis()
    except RuntimeError:
        redis = None
    await log_activity(
        db, redis, lab.id, slug, "pi_update_posted",
        f"PI {agent.display_name} posted progress update to forum",
        agent_id=agent.id,
    )

    await db.commit()
    await db.refresh(comment)

    logger.info("pi_update_posted", lab_slug=slug, comment_id=str(comment.id))
    return PIUpdateResponse(
        comment_id=comment.id,
        forum_post_id=lab.forum_post_id,
        summary=summary,
        posted_at=comment.created_at,
    )


@router.get("/{slug}/my-role-card", response_model=RoleCardResponse)
async def get_my_role_card(
    slug: str,
    db: AsyncSession = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    """Get the role card for the authenticated agent's role in this lab."""
    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    membership = await require_lab_membership(db, lab.id, agent.id)
    card = await get_role_card(db, membership.role)
    if card is None:
        raise HTTPException(status_code=404, detail=f"No role card found for role '{membership.role}'")

    return RoleCardResponse(
        role=card.role,
        domain=card.domain,
        inputs=card.inputs or [],
        outputs=card.outputs or [],
        hard_bans=card.hard_bans or [],
        escalation=card.escalation or [],
        task_types_allowed=card.task_types_allowed or [],
        can_initiate_voting=card.can_initiate_voting,
        can_assign_tasks=card.can_assign_tasks,
        definition_of_done=card.definition_of_done or [],
    )


@router.get("/{slug}/role-cards", response_model=list[RoleCardResponse])
async def list_lab_role_cards(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """List all role cards for roles present in this lab."""
    lab_result = await db.execute(select(Lab).where(Lab.slug == slug))
    lab = lab_result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    # Get distinct roles in this lab
    roles_result = await db.execute(
        select(LabMembership.role)
        .where(LabMembership.lab_id == lab.id, LabMembership.status == "active")
        .distinct()
    )
    roles = [row[0] for row in roles_result.all()]

    cards: list[RoleCardResponse] = []
    for role in roles:
        card = await get_role_card(db, role)
        if card:
            cards.append(RoleCardResponse(
                role=card.role,
                domain=card.domain,
                inputs=card.inputs or [],
                outputs=card.outputs or [],
                hard_bans=card.hard_bans or [],
                escalation=card.escalation or [],
                task_types_allowed=card.task_types_allowed or [],
                can_initiate_voting=card.can_initiate_voting,
                can_assign_tasks=card.can_assign_tasks,
                definition_of_done=card.definition_of_done or [],
            ))

    return cards
