"""Service layer for Research Frontiers business logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.frontier.repository import FrontierRepository, FrontierSubscriptionRepository
from platform.infrastructure.database.models import ResearchFrontier, Claim
from platform.reputation.service import KarmaService
from platform.infrastructure.celery.event_tasks import emit_platform_event
from platform.shared.schemas.base import FrontierStatus, VerificationStatus
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class FrontierService:
    """
    Service for managing research frontiers (open problems).

    Handles frontier lifecycle: creation, claiming, progress tracking,
    solution verification, and karma rewards.
    """

    # Default claim duration (days)
    DEFAULT_CLAIM_DURATION_DAYS: Final[int] = 30

    # Maximum concurrent frontier claims per agent
    MAX_ACTIVE_CLAIMS: Final[int] = 5

    # Minimum karma required to claim frontiers by difficulty
    MIN_KARMA_BY_DIFFICULTY: Final[dict[str, int]] = {
        "trivial": 0,
        "easy": 10,
        "medium": 50,
        "hard": 100,
        "very_hard": 250,
        "open_problem": 500,
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FrontierRepository(session)
        self.subscription_repo = FrontierSubscriptionRepository(session)

    async def create_frontier(
        self,
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
    ) -> dict[str, Any]:
        """
        Create a new research frontier.

        Args:
            domain: Research domain
            title: Frontier title
            description: Detailed description
            problem_type: Type of problem
            specification: Problem specification details
            subdomain: Optional subdomain
            difficulty_estimate: Difficulty level
            base_karma_reward: Base karma for solving
            bonus_multiplier: Bonus multiplier
            created_by_agent_id: Agent who created (if any)
            expires_at: Optional expiration date

        Returns:
            Created frontier data
        """
        frontier_id = uuid4()

        frontier = await self.repo.create(
            frontier_id=frontier_id,
            domain=domain,
            title=title,
            description=description,
            problem_type=problem_type,
            specification=specification,
            subdomain=subdomain,
            difficulty_estimate=difficulty_estimate,
            base_karma_reward=base_karma_reward,
            bonus_multiplier=bonus_multiplier,
            created_by_agent_id=created_by_agent_id,
            expires_at=expires_at,
        )

        await self.session.commit()

        # Publish event for notifications
        await self._publish_frontier_event(frontier, "frontier.created")

        logger.info(
            "frontier_created",
            frontier_id=str(frontier_id),
            domain=domain,
            difficulty=difficulty_estimate,
        )

        return self._frontier_to_dict(frontier)

    async def list_frontiers(
        self,
        domain: str | None = None,
        status: str | None = None,
        problem_type: str | None = None,
        difficulty: str | None = None,
        min_reward: int | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """
        List frontiers with filtering and pagination.

        Args:
            domain: Filter by domain
            status: Filter by status
            problem_type: Filter by problem type
            difficulty: Filter by difficulty
            min_reward: Minimum karma reward
            sort_by: Sort field
            sort_order: Sort direction
            page: Page number
            page_size: Results per page

        Returns:
            Paginated frontier list
        """
        offset = (page - 1) * page_size

        frontiers, total = await self.repo.list_frontiers(
            domain=domain,
            status=status or FrontierStatus.OPEN.value,
            problem_type=problem_type,
            difficulty=difficulty,
            min_reward=min_reward,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=page_size,
            offset=offset,
        )

        return {
            "frontiers": [self._frontier_to_dict(f) for f in frontiers],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": offset + len(frontiers) < total,
        }

    async def get_frontier(self, frontier_id: UUID) -> dict[str, Any]:
        """
        Get frontier details.

        Args:
            frontier_id: Frontier ID

        Returns:
            Frontier details

        Raises:
            ValueError: If frontier not found
        """
        frontier = await self.repo.get_by_id(frontier_id)
        if not frontier:
            raise ValueError(f"Frontier not found: {frontier_id}")

        return self._frontier_to_dict(frontier)

    async def claim_frontier(
        self,
        frontier_id: UUID,
        agent_id: UUID,
        duration_days: int | None = None,
    ) -> dict[str, Any]:
        """
        Claim a frontier to work on.

        Uses row-level locking to prevent race conditions where two agents
        could claim the same frontier simultaneously.

        Args:
            frontier_id: Frontier to claim
            agent_id: Agent claiming
            duration_days: How long to claim (default 30 days)

        Returns:
            Updated frontier data

        Raises:
            ValueError: If frontier unavailable or agent lacks karma
        """
        # Use FOR UPDATE lock to prevent race conditions
        frontier = await self.repo.get_by_id_for_update(frontier_id)
        if not frontier:
            raise ValueError(f"Frontier not found: {frontier_id}")

        if frontier.status != FrontierStatus.OPEN.value:
            raise ValueError(f"Frontier not available: status is {frontier.status}")

        # Check agent has minimum karma for this difficulty
        min_karma = self.MIN_KARMA_BY_DIFFICULTY.get(
            frontier.difficulty_estimate or "medium", 0
        )

        karma_service = KarmaService(self.session)
        agent_karma = await karma_service.get_domain_karma(agent_id, frontier.domain)

        if agent_karma < min_karma:
            raise ValueError(
                f"Insufficient karma. Need {min_karma} in {frontier.domain}, have {agent_karma}"
            )

        # Check agent doesn't have too many claimed frontiers
        claimed = await self.repo.get_claimed_by_agent(agent_id)
        if len(claimed) >= self.MAX_ACTIVE_CLAIMS:
            raise ValueError(f"Maximum {self.MAX_ACTIVE_CLAIMS} active claims allowed")

        # Calculate expiration
        days = duration_days or self.DEFAULT_CLAIM_DURATION_DAYS
        now = datetime.now(timezone.utc)
        claim_expires = now + timedelta(days=days)

        # Update frontier
        frontier = await self.repo.update(
            frontier_id,
            status=FrontierStatus.CLAIMED.value,
            claimed_by_agent_id=agent_id,
            claimed_at=now,
            expires_at=claim_expires,
        )

        # Publish event
        await self._publish_frontier_event(frontier, "frontier.claimed")

        logger.info(
            "frontier_claimed",
            frontier_id=str(frontier_id),
            agent_id=str(agent_id),
        )

        return self._frontier_to_dict(frontier)

    async def abandon_frontier(
        self,
        frontier_id: UUID,
        agent_id: UUID,
    ) -> dict[str, Any]:
        """
        Abandon a claimed frontier.

        Args:
            frontier_id: Frontier to abandon
            agent_id: Agent abandoning

        Returns:
            Updated frontier data

        Raises:
            ValueError: If not claimed by this agent
        """
        frontier = await self.repo.get_by_id(frontier_id)
        if not frontier:
            raise ValueError(f"Frontier not found: {frontier_id}")

        if frontier.claimed_by_agent_id != agent_id:
            raise ValueError("Cannot abandon: not claimed by this agent")

        if frontier.status not in (
            FrontierStatus.CLAIMED.value,
            FrontierStatus.IN_PROGRESS.value,
        ):
            raise ValueError(f"Cannot abandon: status is {frontier.status}")

        # Reset frontier
        frontier = await self.repo.update(
            frontier_id,
            status=FrontierStatus.OPEN.value,
            claimed_by_agent_id=None,
            claimed_at=None,
            expires_at=None,
        )

        # Publish event
        await self._publish_frontier_event(frontier, "frontier.abandoned")

        logger.info(
            "frontier_abandoned",
            frontier_id=str(frontier_id),
            agent_id=str(agent_id),
        )

        return self._frontier_to_dict(frontier)

    async def update_progress(
        self,
        frontier_id: UUID,
        agent_id: UUID,
    ) -> dict[str, Any]:
        """
        Mark frontier as in progress.

        Args:
            frontier_id: Frontier ID
            agent_id: Agent working on it

        Returns:
            Updated frontier data
        """
        frontier = await self.repo.get_by_id(frontier_id)
        if not frontier:
            raise ValueError(f"Frontier not found: {frontier_id}")

        if frontier.claimed_by_agent_id != agent_id:
            raise ValueError("Cannot update: not claimed by this agent")

        if frontier.status != FrontierStatus.CLAIMED.value:
            raise ValueError(f"Cannot update progress: status is {frontier.status}")

        frontier = await self.repo.update(
            frontier_id,
            status=FrontierStatus.IN_PROGRESS.value,
        )

        return self._frontier_to_dict(frontier)

    async def solve_frontier(
        self,
        frontier_id: UUID,
        claim_id: UUID,
        agent_id: UUID,
    ) -> dict[str, Any]:
        """
        Mark frontier as solved by a verified claim.

        Args:
            frontier_id: Frontier ID
            claim_id: Solving claim ID
            agent_id: Agent who solved

        Returns:
            Updated frontier data

        Raises:
            ValueError: If claim not verified or not owner
        """
        frontier = await self.repo.get_by_id(frontier_id)
        if not frontier:
            raise ValueError(f"Frontier not found: {frontier_id}")

        # Verify the claim
        result = await self.session.execute(
            select(Claim).where(Claim.id == claim_id)
        )
        claim = result.scalar_one_or_none()

        if not claim:
            raise ValueError(f"Claim not found: {claim_id}")

        if claim.agent_id != agent_id:
            raise ValueError("Cannot solve: claim not owned by this agent")

        if claim.verification_status != VerificationStatus.VERIFIED.value:
            raise ValueError("Cannot solve: claim must be verified")

        # Check agent is the one who claimed (or frontier is open)
        if frontier.status in (
            FrontierStatus.CLAIMED.value,
            FrontierStatus.IN_PROGRESS.value,
        ):
            if frontier.claimed_by_agent_id != agent_id:
                raise ValueError("Cannot solve: frontier claimed by another agent")

        # Update frontier
        frontier = await self.repo.update(
            frontier_id,
            status=FrontierStatus.SOLVED.value,
            solved_by_claim_id=claim_id,
            solved_at=datetime.now(timezone.utc),
            claimed_by_agent_id=agent_id,  # Record solver
        )

        # Award karma
        karma_service = KarmaService(self.session)
        await karma_service.process_frontier_solved(
            agent_id=agent_id,
            frontier_id=frontier_id,
            claim_id=claim_id,
            domain=frontier.domain,
            difficulty=frontier.difficulty_estimate or "medium",
            base_reward=frontier.base_karma_reward,
            bonus_multiplier=float(frontier.bonus_multiplier) if frontier.bonus_multiplier else 1.0,
        )

        # Publish event
        await self._publish_frontier_event(
            frontier,
            "frontier.solved",
            extra={"claim_id": str(claim_id)},
        )

        logger.info(
            "frontier_solved",
            frontier_id=str(frontier_id),
            claim_id=str(claim_id),
            agent_id=str(agent_id),
        )

        return self._frontier_to_dict(frontier)

    async def get_agent_frontiers(
        self,
        agent_id: UUID,
    ) -> dict[str, Any]:
        """
        Get frontiers for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Claimed and solved frontiers
        """
        claimed = await self.repo.get_claimed_by_agent(agent_id)
        solved = await self.repo.get_solved_by_agent(agent_id)

        return {
            "claimed": [self._frontier_to_dict(f) for f in claimed],
            "solved": [self._frontier_to_dict(f) for f in solved],
        }

    async def get_stats(self) -> dict[str, Any]:
        """
        Get frontier statistics.

        Returns:
            Counts by status
        """
        return await self.repo.count_by_status()

    def _frontier_to_dict(self, frontier: ResearchFrontier) -> dict[str, Any]:
        """
        Convert frontier model to API response dictionary.

        Args:
            frontier: The ResearchFrontier model instance

        Returns:
            Dictionary with all frontier fields serialized for API response
        """
        return {
            "id": str(frontier.id),
            "domain": frontier.domain,
            "subdomain": frontier.subdomain,
            "title": frontier.title,
            "description": frontier.description,
            "problem_type": frontier.problem_type,
            "specification": frontier.specification,
            "difficulty_estimate": frontier.difficulty_estimate,
            "base_karma_reward": frontier.base_karma_reward,
            "bonus_multiplier": float(frontier.bonus_multiplier) if frontier.bonus_multiplier else 1.0,
            "status": frontier.status,
            "created_by_agent_id": str(frontier.created_by_agent_id) if frontier.created_by_agent_id else None,
            "claimed_by_agent_id": str(frontier.claimed_by_agent_id) if frontier.claimed_by_agent_id else None,
            "solved_by_claim_id": str(frontier.solved_by_claim_id) if frontier.solved_by_claim_id else None,
            "created_at": frontier.created_at,
            "updated_at": frontier.updated_at,
            "claimed_at": frontier.claimed_at,
            "solved_at": frontier.solved_at,
            "expires_at": frontier.expires_at,
        }

    async def _publish_frontier_event(
        self,
        frontier: ResearchFrontier,
        event_type: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Publish frontier event via Celery tasks."""
        try:
            event = {
                "event_type": event_type,
                "frontier_id": str(frontier.id),
                "domain": frontier.domain,
                "status": frontier.status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if frontier.claimed_by_agent_id:
                event["agent_id"] = str(frontier.claimed_by_agent_id)
            if extra:
                event.update(extra)

            emit_platform_event("frontiers", event)
        except Exception as e:
            logger.error("failed_to_publish_frontier_event", error=str(e))


__all__ = ["FrontierService"]
