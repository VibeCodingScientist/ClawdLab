"""ProgressPostService — manages agent progress posts (intermediate results)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class ProgressPostService:
    """Manages lightweight intermediate result updates from agents."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_post(
        self,
        agent_id: UUID,
        lab_id: UUID,
        post_type: str,
        title: str,
        content: str,
        sprint_id: UUID | None = None,
        confidence: float | None = None,
        related_research_item: UUID | None = None,
        visibility: str = "lab",
    ) -> "AgentProgressPost":
        """Create a new progress post."""
        from platform.infrastructure.database.models import AgentProgressPost

        post = AgentProgressPost(
            agent_id=agent_id,
            lab_id=lab_id,
            sprint_id=sprint_id,
            post_type=post_type,
            title=title,
            content=content,
            confidence=confidence,
            related_research_item=related_research_item,
            visibility=visibility,
        )
        self.session.add(post)
        await self.session.flush()

        logger.info(
            "Progress post created: agent=%s lab=%s type=%s title=%s",
            agent_id,
            lab_id,
            post_type,
            title[:80],
        )
        return post

    async def list_by_lab(
        self,
        lab_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list["AgentProgressPost"]:
        """List progress posts for a lab."""
        from platform.infrastructure.database.models import AgentProgressPost

        result = await self.session.execute(
            select(AgentProgressPost)
            .where(AgentProgressPost.lab_id == lab_id)
            .order_by(AgentProgressPost.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_sprint(
        self,
        sprint_id: UUID,
        limit: int = 50,
    ) -> list["AgentProgressPost"]:
        """List progress posts for a specific sprint."""
        from platform.infrastructure.database.models import AgentProgressPost

        result = await self.session.execute(
            select(AgentProgressPost)
            .where(AgentProgressPost.sprint_id == sprint_id)
            .order_by(AgentProgressPost.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
