"""Notification service — creates notifications for forum/lab events."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.models import ForumComment, ForumPost, Lab, Notification, User

logger = get_logger(__name__)


async def resolve_user_id_by_username(db: AsyncSession, username: str) -> UUID | None:
    """Look up a user ID by username. Returns None if not found."""
    result = await db.execute(select(User.id).where(User.username == username))
    row = result.scalar_one_or_none()
    return row


async def create_notification(
    db: AsyncSession,
    user_id: UUID,
    notification_type: str,
    title: str,
    body: str,
    link: str | None = None,
    metadata: dict | None = None,
) -> Notification:
    """Insert a single notification."""
    notif = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        link=link,
        metadata_=metadata or {},
    )
    db.add(notif)
    return notif


async def notify_post_author(
    db: AsyncSession,
    post: ForumPost,
    notification_type: str,
    title: str,
    body: str,
    link: str | None = None,
    metadata: dict | None = None,
) -> Notification | None:
    """Resolve the post's author_name to a user and create a notification."""
    user_id = await resolve_user_id_by_username(db, post.author_name)
    if user_id is None:
        return None
    return await create_notification(db, user_id, notification_type, title, body, link, metadata)


async def notify_comment_parent_author(
    db: AsyncSession,
    comment: ForumComment,
    post: ForumPost,
) -> None:
    """Handle notifications for a new comment: reply notification + post-comment notification."""
    # If this is a reply, notify the parent comment author
    if comment.parent_id:
        parent_result = await db.execute(
            select(ForumComment).where(ForumComment.id == comment.parent_id)
        )
        parent_comment = parent_result.scalar_one_or_none()
        if parent_comment and parent_comment.author_name:
            user_id = await resolve_user_id_by_username(db, parent_comment.author_name)
            if user_id:
                commenter = comment.author_name or "Someone"
                await create_notification(
                    db,
                    user_id=user_id,
                    notification_type="comment_reply",
                    title="Reply to your comment",
                    body=f"{commenter} replied to your comment on \"{post.title}\"",
                    link=f"/forum/{post.id}",
                    metadata={"post_id": str(post.id), "comment_id": str(comment.id)},
                )

    # Notify the post author about the new comment (skip if commenter is the author)
    if comment.author_name != post.author_name:
        commenter = comment.author_name or "Someone"
        await notify_post_author(
            db,
            post,
            notification_type="post_comment",
            title="New comment on your idea",
            body=f"{commenter} commented on \"{post.title}\"",
            link=f"/forum/{post.id}",
            metadata={"post_id": str(post.id), "comment_id": str(comment.id)},
        )


async def notify_lab_created_from_post(
    db: AsyncSession,
    lab: Lab,
    post: ForumPost,
) -> None:
    """Notify the post author that a lab was created from their idea."""
    await notify_post_author(
        db,
        post,
        notification_type="lab_created_from_post",
        title="Lab created from your idea",
        body=f"A lab was created from your idea: \"{post.title}\"",
        link=f"/labs/{lab.slug}",
        metadata={"post_id": str(post.id), "lab_slug": lab.slug},
    )


async def notify_agent_level_up(
    db: AsyncSession,
    agent_name: str,
    lab: Lab,
    new_level: int,
) -> None:
    """Notify the originating post author when an agent levels up in a lab."""
    if not lab.forum_post_id:
        return
    post_result = await db.execute(
        select(ForumPost).where(ForumPost.id == lab.forum_post_id)
    )
    post = post_result.scalar_one_or_none()
    if post is None:
        return
    await notify_post_author(
        db,
        post,
        notification_type="agent_level_up",
        title="Agent leveled up",
        body=f"{agent_name} reached level {new_level} in {lab.name}",
        link=f"/labs/{lab.slug}",
        metadata={"lab_slug": lab.slug, "new_level": new_level},
    )


async def notify_task_completed(
    db: AsyncSession,
    task_title: str,
    lab: Lab,
) -> None:
    """Notify the originating post author when a task is completed."""
    if not lab.forum_post_id:
        return
    post_result = await db.execute(
        select(ForumPost).where(ForumPost.id == lab.forum_post_id)
    )
    post = post_result.scalar_one_or_none()
    if post is None:
        return
    await notify_post_author(
        db,
        post,
        notification_type="task_completed",
        title="Research completed",
        body=f"Research completed: \"{task_title}\"",
        link=f"/labs/{lab.slug}",
        metadata={"lab_slug": lab.slug, "task_title": task_title},
    )
