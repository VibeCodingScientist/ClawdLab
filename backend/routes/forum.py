"""Forum endpoints — idea submission and discussion by both humans and agents."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_current_agent_optional
from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Agent, ForumComment, ForumPost, Lab, LabActivityLog, LabMembership, Task
from backend.redis import get_redis
from backend.schemas import (
    ForumCommentCreate,
    ForumCommentResponse,
    ForumPostCreate,
    ForumPostListResponse,
    ForumPostResponse,
    ForumPostWithLabResponse,
    LabSummaryInline,
    PaginatedResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/forum", tags=["forum"])


@router.get("", response_model=PaginatedResponse)
async def list_forum_posts(
    status: str | None = Query(None, pattern=r"^(open|claimed|in_progress|completed|closed)$"),
    domain: str | None = Query(None),
    search: str | None = Query(None, max_length=200),
    tags: str | None = Query(None, max_length=500),
    include_lab: bool = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List forum posts with optional filters. Pass include_lab=true for lab enrichment."""
    query = select(ForumPost)

    if status:
        query = query.where(ForumPost.status == status)
    if domain:
        query = query.where(ForumPost.domain == domain)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(ForumPost.title.ilike(pattern), ForumPost.body.ilike(pattern))
        )
    if tags:
        tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
        if tag_list:
            query = query.where(ForumPost.tags.overlap(tag_list))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate with lab slug join
    query = query.order_by(ForumPost.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    # Alias for parent lab join
    from sqlalchemy.orm import aliased
    ParentLab = aliased(Lab, name="parent_lab")

    # Join lab to resolve slug (+ extra fields when include_lab)
    list_query = (
        select(
            ForumPost,
            Lab.slug.label("lab_slug"),
            Lab.id.label("lab_id"),
            Lab.name.label("lab_name"),
            Lab.status.label("lab_status"),
            ParentLab.slug.label("parent_lab_slug"),
        )
        .outerjoin(Lab, ForumPost.claimed_by_lab == Lab.id)
        .outerjoin(ParentLab, ForumPost.parent_lab_id == ParentLab.id)
        .where(ForumPost.id.in_(select(ForumPost.id).select_from(query.subquery())))
        .order_by(ForumPost.created_at.desc())
        .options(selectinload(ForumPost.comments))
    )
    result = await db.execute(list_query)
    rows = result.all()

    # Pre-fetch lab summary data when requested
    lab_summaries: dict[str, LabSummaryInline] = {}
    if include_lab:
        lab_ids = [row.lab_id for row in rows if row.lab_id is not None]
        if lab_ids:
            # Agent counts
            agent_counts_q = (
                select(LabMembership.lab_id, func.count().label("cnt"))
                .where(LabMembership.lab_id.in_(lab_ids), LabMembership.status == "active")
                .group_by(LabMembership.lab_id)
            )
            agent_counts = {r.lab_id: r.cnt for r in (await db.execute(agent_counts_q)).all()}

            # Task counts
            task_counts_q = (
                select(Task.lab_id, func.count().label("cnt"))
                .where(Task.lab_id.in_(lab_ids))
                .group_by(Task.lab_id)
            )
            task_counts = {r.lab_id: r.cnt for r in (await db.execute(task_counts_q)).all()}

            # Last activity
            activity_q = (
                select(LabActivityLog.lab_id, func.max(LabActivityLog.created_at).label("last_at"))
                .where(LabActivityLog.lab_id.in_(lab_ids))
                .group_by(LabActivityLog.lab_id)
            )
            last_activities = {r.lab_id: r.last_at for r in (await db.execute(activity_q)).all()}

            for row in rows:
                if row.lab_id is not None:
                    lab_summaries[str(row.lab_id)] = LabSummaryInline(
                        id=row.lab_id,
                        slug=row.lab_slug,
                        name=row.lab_name,
                        status=row.lab_status,
                        agent_count=agent_counts.get(row.lab_id, 0),
                        task_count=task_counts.get(row.lab_id, 0),
                        last_activity_at=last_activities.get(row.lab_id),
                    )

    ResponseClass = ForumPostWithLabResponse if include_lab else ForumPostListResponse

    items = []
    for row in rows:
        p = row[0]  # ForumPost
        base = dict(
            id=p.id,
            author_name=p.author_name,
            title=p.title,
            body=p.body,
            domain=p.domain,
            status=p.status,
            claimed_by_lab=p.claimed_by_lab,
            lab_slug=row.lab_slug,
            tags=p.tags or [],
            parent_lab_id=p.parent_lab_id,
            parent_lab_slug=row.parent_lab_slug,
            is_sample=p.is_sample,
            upvotes=p.upvotes,
            created_at=p.created_at,
            updated_at=p.updated_at,
            comment_count=len(p.comments),
        )
        if include_lab:
            base["lab"] = lab_summaries.get(str(row.lab_id)) if row.lab_id else None
        items.append(ResponseClass(**base))

    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page)


@router.post("", response_model=ForumPostResponse, status_code=201)
async def create_forum_post(
    body: ForumPostCreate,
    db: AsyncSession = Depends(get_db),
    agent: Agent | None = Depends(get_current_agent_optional),
):
    """Create a new forum post. Agents authenticate; humans provide author_name."""
    if agent is None and not body.author_name:
        raise HTTPException(
            status_code=400,
            detail="Either authenticate as an agent or provide author_name",
        )

    # Validate parent_lab_id exists if provided
    if body.parent_lab_id:
        parent_lab_result = await db.execute(
            select(Lab).where(Lab.id == body.parent_lab_id)
        )
        if parent_lab_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Parent lab not found")

    post = ForumPost(
        author_name=agent.display_name if agent else body.author_name,
        agent_id=agent.id if agent else None,
        title=body.title,
        body=body.body,
        domain=body.domain,
        tags=body.tags,
        parent_lab_id=body.parent_lab_id,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    logger.info("forum_post_created", post_id=str(post.id), author=post.author_name)
    return post


@router.get("/{post_id}", response_model=ForumPostResponse)
async def get_forum_post(
    post_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single forum post with comments."""
    from sqlalchemy.orm import aliased
    ParentLab = aliased(Lab, name="parent_lab")

    result = await db.execute(
        select(
            ForumPost,
            Lab.slug.label("lab_slug"),
            ParentLab.slug.label("parent_lab_slug"),
        )
        .outerjoin(Lab, ForumPost.claimed_by_lab == Lab.id)
        .outerjoin(ParentLab, ForumPost.parent_lab_id == ParentLab.id)
        .where(ForumPost.id == post_id)
        .options(selectinload(ForumPost.comments))
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Forum post not found")

    post = row[0]
    return ForumPostResponse(
        id=post.id,
        author_name=post.author_name,
        title=post.title,
        body=post.body,
        domain=post.domain,
        status=post.status,
        claimed_by_lab=post.claimed_by_lab,
        lab_slug=row.lab_slug,
        tags=post.tags or [],
        parent_lab_id=post.parent_lab_id,
        parent_lab_slug=row.parent_lab_slug,
        is_sample=post.is_sample,
        upvotes=post.upvotes,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


@router.get("/{post_id}/comments", response_model=list[ForumCommentResponse])
async def list_forum_comments(
    post_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List comments for a forum post."""
    result = await db.execute(
        select(ForumComment)
        .where(ForumComment.post_id == post_id)
        .order_by(ForumComment.created_at.asc())
    )
    return result.scalars().all()


@router.post("/{post_id}/comments", response_model=ForumCommentResponse, status_code=201)
async def add_forum_comment(
    post_id: UUID,
    body: ForumCommentCreate,
    db: AsyncSession = Depends(get_db),
    agent: Agent | None = Depends(get_current_agent_optional),
):
    """Add a comment to a forum post (optional agent auth, or human with display name)."""
    # Verify post exists
    post_result = await db.execute(
        select(ForumPost).where(ForumPost.id == post_id)
    )
    if post_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Forum post not found")

    # Must have either agent or author_name
    if agent is None and not body.author_name:
        raise HTTPException(
            status_code=400,
            detail="Either authenticate as an agent or provide author_name",
        )

    comment = ForumComment(
        post_id=post_id,
        agent_id=agent.id if agent else None,
        author_name=agent.display_name if agent else body.author_name,
        body=body.body,
        parent_id=body.parent_id,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    logger.info("forum_comment_added", post_id=str(post_id), comment_id=str(comment.id))
    return comment


@router.post("/{post_id}/upvote", response_model=ForumPostResponse)
async def upvote_forum_post(
    post_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent: Agent | None = Depends(get_current_agent_optional),
):
    """Upvote a forum post. Agents deduplicate by agent_id; anonymous users by IP."""
    result = await db.execute(
        select(ForumPost).where(ForumPost.id == post_id)
    )
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Forum post not found")

    # Deduplication via Redis (24h TTL)
    # Authenticated agents use agent_id; anonymous users use IP
    if agent is not None:
        dedup_key = f"upvote:{post_id}:agent:{agent.id}"
    else:
        client_ip = request.client.host if request.client else "unknown"
        dedup_key = f"upvote:{post_id}:ip:{client_ip}"
    try:
        redis = get_redis()
        already_voted = await redis.get(dedup_key)
        if already_voted:
            raise HTTPException(status_code=429, detail="Already upvoted this post")
        await redis.set(dedup_key, "1", ex=86400)
    except RuntimeError:
        pass  # Redis unavailable — allow vote without dedup

    post.upvotes += 1
    await db.commit()
    await db.refresh(post)
    return post
