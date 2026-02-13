"""Forum endpoints — idea submission by humans, comments by humans and agents."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_current_agent_optional
from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import Agent, ForumComment, ForumPost, Lab
from backend.schemas import (
    ForumCommentCreate,
    ForumCommentResponse,
    ForumPostCreate,
    ForumPostListResponse,
    ForumPostResponse,
    PaginatedResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/forum", tags=["forum"])


@router.get("", response_model=PaginatedResponse)
async def list_forum_posts(
    status: str | None = Query(None, pattern=r"^(open|claimed|in_progress|completed|closed)$"),
    domain: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List forum posts with optional filters."""
    query = select(ForumPost)

    if status:
        query = query.where(ForumPost.status == status)
    if domain:
        query = query.where(ForumPost.domain == domain)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate with lab slug join
    query = query.order_by(ForumPost.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    # Join lab to resolve slug
    list_query = (
        select(ForumPost, Lab.slug.label("lab_slug"))
        .outerjoin(Lab, ForumPost.claimed_by_lab == Lab.id)
        .where(ForumPost.id.in_(select(ForumPost.id).select_from(query.subquery())))
        .order_by(ForumPost.created_at.desc())
        .options(selectinload(ForumPost.comments))
    )
    result = await db.execute(list_query)
    rows = result.all()

    items = [
        ForumPostListResponse(
            id=p.id,
            author_name=p.author_name,
            title=p.title,
            body=p.body,
            domain=p.domain,
            status=p.status,
            claimed_by_lab=p.claimed_by_lab,
            lab_slug=lab_slug,
            upvotes=p.upvotes,
            created_at=p.created_at,
            updated_at=p.updated_at,
            comment_count=len(p.comments),
        )
        for p, lab_slug in rows
    ]

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

    post = ForumPost(
        author_name=agent.display_name if agent else body.author_name,
        title=body.title,
        body=body.body,
        domain=body.domain,
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
    result = await db.execute(
        select(ForumPost, Lab.slug.label("lab_slug"))
        .outerjoin(Lab, ForumPost.claimed_by_lab == Lab.id)
        .where(ForumPost.id == post_id)
        .options(selectinload(ForumPost.comments))
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Forum post not found")

    post, lab_slug = row
    return ForumPostResponse(
        id=post.id,
        author_name=post.author_name,
        title=post.title,
        body=post.body,
        domain=post.domain,
        status=post.status,
        claimed_by_lab=post.claimed_by_lab,
        lab_slug=lab_slug,
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
    db: AsyncSession = Depends(get_db),
):
    """Upvote a forum post (no auth, simple increment)."""
    result = await db.execute(
        select(ForumPost).where(ForumPost.id == post_id)
    )
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Forum post not found")

    post.upvotes += 1
    await db.commit()
    await db.refresh(post)
    return post
