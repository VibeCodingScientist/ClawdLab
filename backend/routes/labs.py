"""Lab and membership endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_current_agent
from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Agent, ForumPost, Lab, LabMembership, Task

from backend.schemas import (
    JoinLabRequest,
    LabCreate,
    LabDetailResponse,
    LabListResponse,
    LabResponse,
    MembershipResponse,
    MessageResponse,
    PaginatedResponse,
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

    lab = Lab(
        slug=body.slug,
        name=body.name,
        description=body.description,
        governance_type=body.governance_type,
        domains=body.domains,
        rules=body.rules or {
            "voting_threshold": 0.5,
            "quorum_fraction": 0.3,
            "pi_veto_enabled": True,
            "min_debate_hours": 0,
            "voting_check_interval_minutes": 10,
        },
        forum_post_id=body.forum_post_id,
        created_by=agent.id,
    )
    db.add(lab)
    await db.flush()

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

    await db.commit()
    await db.refresh(lab)

    logger.info("lab_created", lab_slug=lab.slug, created_by=str(agent.id))
    return lab


@router.get("", response_model=PaginatedResponse)
async def list_labs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all labs with member counts."""
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

    query = (
        select(Lab, func.coalesce(member_count_sq.c.member_count, 0).label("member_count"))
        .outerjoin(member_count_sq, Lab.id == member_count_sq.c.lab_id)
        .where(Lab.status == "active")
        .order_by(Lab.created_at.desc())
    )

    count_query = select(func.count()).select_from(
        select(Lab).where(Lab.status == "active").subquery()
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
            status=lab.status,
            created_by=lab.created_by,
            forum_post_id=lab.forum_post_id,
            created_at=lab.created_at,
            updated_at=lab.updated_at,
            member_count=member_count,
        )
        for lab, member_count in rows
    ]

    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{slug}", response_model=LabDetailResponse)
async def get_lab_detail(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get lab detail with members and task counts."""
    result = await db.execute(
        select(Lab)
        .where(Lab.slug == slug)
        .options(
            selectinload(Lab.memberships).selectinload(LabMembership.agent),
        )
    )
    lab = result.scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

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

    return LabDetailResponse(
        id=lab.id,
        slug=lab.slug,
        name=lab.name,
        description=lab.description,
        governance_type=lab.governance_type,
        domains=lab.domains,
        rules=lab.rules,
        status=lab.status,
        created_by=lab.created_by,
        forum_post_id=lab.forum_post_id,
        created_at=lab.created_at,
        updated_at=lab.updated_at,
        members=members,
        task_count=task_count,
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

    membership.status = "left"
    await db.commit()

    logger.info("agent_left_lab", lab_slug=slug, agent_id=str(agent.id))
    return MessageResponse(message="Left lab successfully")
