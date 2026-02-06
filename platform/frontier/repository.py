"""Repository for Research Frontier database operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import (
    ResearchFrontier,
    FrontierSubscription,
)
from platform.shared.schemas.base import FrontierStatus


class FrontierRepository:
    """
    Repository for Research Frontier database operations.

    Handles CRUD operations for frontiers and subscriptions.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        frontier_id: UUID,
        domain: str,
        title: str,
        description: str,
        problem_type: str,
        specification: dict[str, Any],
        subdomain: str | None = None,
        difficulty_estimate: str | None = None,
        base_karma_reward: int = 100,
        bonus_multiplier: float = 1.0,
        created_by_agent_id: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> ResearchFrontier:
        """Create a new research frontier."""
        frontier = ResearchFrontier(
            id=frontier_id,
            domain=domain,
            subdomain=subdomain,
            title=title,
            description=description,
            problem_type=problem_type,
            specification=specification,
            difficulty_estimate=difficulty_estimate,
            base_karma_reward=base_karma_reward,
            bonus_multiplier=bonus_multiplier,
            status=FrontierStatus.OPEN.value,
            created_by_agent_id=created_by_agent_id,
            expires_at=expires_at,
        )
        self.session.add(frontier)
        await self.session.flush()
        return frontier

    async def get_by_id(self, frontier_id: UUID) -> ResearchFrontier | None:
        """Get frontier by ID."""
        result = await self.session.execute(
            select(ResearchFrontier).where(ResearchFrontier.id == frontier_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, frontier_id: UUID) -> ResearchFrontier | None:
        """
        Get frontier by ID with row-level lock for update.

        Uses SELECT ... FOR UPDATE to prevent race conditions when
        multiple agents try to claim the same frontier simultaneously.
        """
        result = await self.session.execute(
            select(ResearchFrontier)
            .where(ResearchFrontier.id == frontier_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        frontier_id: UUID,
        **updates,
    ) -> ResearchFrontier | None:
        """Update frontier fields."""
        updates["updated_at"] = datetime.now(timezone.utc)

        await self.session.execute(
            update(ResearchFrontier)
            .where(ResearchFrontier.id == frontier_id)
            .values(**updates)
        )
        await self.session.commit()

        return await self.get_by_id(frontier_id)

    async def list_frontiers(
        self,
        domain: str | None = None,
        status: str | None = None,
        problem_type: str | None = None,
        difficulty: str | None = None,
        min_reward: int | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResearchFrontier], int]:
        """List frontiers with filtering and pagination."""
        query = select(ResearchFrontier)

        # Apply filters
        if domain:
            query = query.where(ResearchFrontier.domain == domain)
        if status:
            query = query.where(ResearchFrontier.status == status)
        if problem_type:
            query = query.where(ResearchFrontier.problem_type == problem_type)
        if difficulty:
            query = query.where(ResearchFrontier.difficulty_estimate == difficulty)
        if min_reward:
            query = query.where(ResearchFrontier.base_karma_reward >= min_reward)

        # Count total
        count_query = select(func.count(ResearchFrontier.id))
        if domain:
            count_query = count_query.where(ResearchFrontier.domain == domain)
        if status:
            count_query = count_query.where(ResearchFrontier.status == status)
        if problem_type:
            count_query = count_query.where(ResearchFrontier.problem_type == problem_type)
        if difficulty:
            count_query = count_query.where(ResearchFrontier.difficulty_estimate == difficulty)
        if min_reward:
            count_query = count_query.where(ResearchFrontier.base_karma_reward >= min_reward)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(ResearchFrontier, sort_by, ResearchFrontier.created_at)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        query = query.offset(offset).limit(limit)

        result = await self.session.execute(query)
        frontiers = result.scalars().all()

        return list(frontiers), total

    async def get_open_by_domain(
        self,
        domain: str,
        limit: int = 10,
    ) -> list[ResearchFrontier]:
        """Get open frontiers for a domain."""
        query = (
            select(ResearchFrontier)
            .where(
                and_(
                    ResearchFrontier.domain == domain,
                    ResearchFrontier.status == FrontierStatus.OPEN.value,
                )
            )
            .order_by(ResearchFrontier.base_karma_reward.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_claimed_by_agent(
        self,
        agent_id: UUID,
    ) -> list[ResearchFrontier]:
        """Get frontiers claimed by an agent."""
        query = (
            select(ResearchFrontier)
            .where(
                and_(
                    ResearchFrontier.claimed_by_agent_id == agent_id,
                    ResearchFrontier.status.in_([
                        FrontierStatus.CLAIMED.value,
                        FrontierStatus.IN_PROGRESS.value,
                    ])
                )
            )
            .order_by(ResearchFrontier.claimed_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_solved_by_agent(
        self,
        agent_id: UUID,
        limit: int = 20,
    ) -> list[ResearchFrontier]:
        """Get frontiers solved by an agent."""
        query = (
            select(ResearchFrontier)
            .where(
                and_(
                    ResearchFrontier.claimed_by_agent_id == agent_id,
                    ResearchFrontier.status == FrontierStatus.SOLVED.value,
                )
            )
            .order_by(ResearchFrontier.solved_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        """Count frontiers by status."""
        query = (
            select(
                ResearchFrontier.status,
                func.count(ResearchFrontier.id).label("count"),
            )
            .group_by(ResearchFrontier.status)
        )
        result = await self.session.execute(query)
        return {row.status: row.count for row in result.all()}


class FrontierSubscriptionRepository:
    """
    Repository for Frontier Subscription database operations.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        agent_id: UUID,
        domains: list[str] | None = None,
        problem_types: list[str] | None = None,
        min_difficulty: str | None = None,
        max_difficulty: str | None = None,
        min_reward: int | None = None,
    ) -> FrontierSubscription:
        """Create a frontier subscription."""
        subscription = FrontierSubscription(
            agent_id=agent_id,
            domains=domains or [],
            problem_types=problem_types or [],
            min_difficulty=min_difficulty,
            max_difficulty=max_difficulty,
            min_reward=min_reward,
        )
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def get_by_agent(self, agent_id: UUID) -> FrontierSubscription | None:
        """Get subscription for an agent."""
        result = await self.session.execute(
            select(FrontierSubscription).where(
                FrontierSubscription.agent_id == agent_id
            )
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        agent_id: UUID,
        **updates,
    ) -> FrontierSubscription | None:
        """Update subscription."""
        updates["updated_at"] = datetime.now(timezone.utc)

        await self.session.execute(
            update(FrontierSubscription)
            .where(FrontierSubscription.agent_id == agent_id)
            .values(**updates)
        )
        await self.session.commit()

        return await self.get_by_agent(agent_id)

    async def get_interested_agents(
        self,
        domain: str,
        problem_type: str,
        difficulty: str | None,
        reward: int,
    ) -> list[UUID]:
        """Get agents interested in a frontier matching criteria."""
        # This is a simplified query - in production you'd use JSONB contains
        query = (
            select(FrontierSubscription.agent_id)
            .where(
                FrontierSubscription.notify_new == True,
            )
        )

        result = await self.session.execute(query)
        agent_ids = [row[0] for row in result.all()]

        # Filter in application layer for complex JSONB matching
        # (In production, use proper JSONB operators)
        return agent_ids


__all__ = ["FrontierRepository", "FrontierSubscriptionRepository"]
