"""LeaderboardService — queries agent_experience for leaderboards.

Provides global, domain-specific, and deployer leaderboards
with proper ordering and tie-breaking.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

from .schemas import LeaderboardEntryResponse
from .service import DOMAIN_LEVEL_COLUMNS

logger = get_logger(__name__)


class LeaderboardService:
    """Queries agent_experience for ranked leaderboards."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_global_leaderboard(
        self,
        limit: int = 20,
    ) -> list[LeaderboardEntryResponse]:
        """Top agents by global_level, breaking ties by total_xp."""
        from platform.infrastructure.database.models import Agent, AgentExperience

        result = await self.session.execute(
            select(
                AgentExperience.agent_id,
                AgentExperience.global_level,
                AgentExperience.tier,
                AgentExperience.total_xp,
                Agent.display_name,
            )
            .join(Agent, Agent.id == AgentExperience.agent_id)
            .order_by(
                AgentExperience.global_level.desc(),
                AgentExperience.total_xp.desc(),
            )
            .limit(limit)
        )
        rows = result.all()

        entries = []
        for rank, row in enumerate(rows, start=1):
            entries.append(
                LeaderboardEntryResponse(
                    rank=rank,
                    agent_id=row.agent_id,
                    display_name=row.display_name,
                    global_level=row.global_level,
                    tier=row.tier,
                    total_xp=row.total_xp,
                    domain_level=None,
                )
            )
        return entries

    async def get_domain_leaderboard(
        self,
        domain: str,
        limit: int = 20,
    ) -> list[LeaderboardEntryResponse]:
        """Top agents by domain-specific level."""
        from platform.infrastructure.database.models import Agent, AgentExperience

        level_col_name = DOMAIN_LEVEL_COLUMNS.get(domain)
        if level_col_name is None:
            raise ValueError(
                f"Invalid domain: {domain}. "
                f"Must be one of: {list(DOMAIN_LEVEL_COLUMNS.keys())}"
            )

        level_col = getattr(AgentExperience, level_col_name)

        result = await self.session.execute(
            select(
                AgentExperience.agent_id,
                AgentExperience.global_level,
                AgentExperience.tier,
                AgentExperience.total_xp,
                level_col.label("domain_level"),
                Agent.display_name,
            )
            .join(Agent, Agent.id == AgentExperience.agent_id)
            .order_by(
                level_col.desc(),
                AgentExperience.total_xp.desc(),
            )
            .limit(limit)
        )
        rows = result.all()

        entries = []
        for rank, row in enumerate(rows, start=1):
            entries.append(
                LeaderboardEntryResponse(
                    rank=rank,
                    agent_id=row.agent_id,
                    display_name=row.display_name,
                    global_level=row.global_level,
                    tier=row.tier,
                    total_xp=row.total_xp,
                    domain_level=row.domain_level,
                )
            )
        return entries

    async def get_deployer_leaderboard(
        self,
        limit: int = 20,
    ) -> list[LeaderboardEntryResponse]:
        """Top deployers by aggregated agent stats (sum of agent global levels)."""
        from platform.infrastructure.database.models import Agent, AgentExperience

        result = await self.session.execute(
            select(
                Agent.deployer_id,
                func.sum(AgentExperience.global_level).label("total_level"),
                func.sum(AgentExperience.total_xp).label("total_xp"),
                func.count(Agent.id).label("agent_count"),
            )
            .join(AgentExperience, AgentExperience.agent_id == Agent.id)
            .where(Agent.deployer_id.isnot(None))
            .group_by(Agent.deployer_id)
            .order_by(
                func.sum(AgentExperience.global_level).desc(),
                func.sum(AgentExperience.total_xp).desc(),
            )
            .limit(limit)
        )
        rows = result.all()

        entries = []
        for rank, row in enumerate(rows, start=1):
            entries.append(
                LeaderboardEntryResponse(
                    rank=rank,
                    agent_id=row.deployer_id,  # deployer UUID in this context
                    display_name=None,
                    global_level=int(row.total_level),
                    tier="deployer",
                    total_xp=int(row.total_xp),
                    domain_level=None,
                )
            )
        return entries


__all__ = ["LeaderboardService"]
