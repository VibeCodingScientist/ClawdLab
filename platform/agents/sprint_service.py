"""SprintService — manages agent research sprints."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

from .sprint_state_machine import validate_transition

logger = get_logger(__name__)

DEFAULT_SPRINT_DAYS: dict[str, int] = {
    "mathematics": 28,
    "ml_ai": 14,
    "computational_biology": 21,
    "materials_science": 21,
    "bioinformatics": 14,
}


class SprintService:
    """Manages agent research sprints."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def start_sprint(
        self,
        agent_id: UUID,
        lab_id: UUID,
        goal: str,
        approach: str | None = None,
        duration_days: int | None = None,
        domain: str | None = None,
    ) -> "ResearchSprint":
        """Start a new research sprint."""
        from platform.infrastructure.database.models import ResearchSprint

        # Verify no active sprint exists
        active = await self.get_active_sprint(agent_id, lab_id)
        if active is not None:
            raise ValueError(
                f"Agent {agent_id} already has an active sprint in lab {lab_id}"
            )

        # Determine duration
        if duration_days is None:
            duration_days = DEFAULT_SPRINT_DAYS.get(domain or "ml_ai", 14)

        # Get next sprint number
        seq_result = await self.session.execute(
            select(func.coalesce(func.max(ResearchSprint.sprint_number), 0))
            .where(
                ResearchSprint.agent_id == agent_id,
                ResearchSprint.lab_id == lab_id,
            )
        )
        next_number = seq_result.scalar() + 1

        now = datetime.now(timezone.utc)
        sprint = ResearchSprint(
            agent_id=agent_id,
            lab_id=lab_id,
            sprint_number=next_number,
            goal=goal,
            approach=approach,
            started_at=now,
            target_end_at=now + timedelta(days=duration_days),
            status="planning",
        )
        self.session.add(sprint)
        await self.session.flush()

        logger.info(
            "Started sprint #%d for agent %s in lab %s (goal=%s, days=%d)",
            next_number,
            agent_id,
            lab_id,
            goal[:80],
            duration_days,
        )
        return sprint

    async def end_sprint(
        self,
        sprint_id: UUID,
        outcome_type: str,
        outcome_summary: str,
    ) -> "ResearchSprint":
        """End a sprint with an outcome."""
        from platform.infrastructure.database.models import ResearchSprint

        result = await self.session.execute(
            select(ResearchSprint)
            .where(ResearchSprint.id == sprint_id)
            .with_for_update()
        )
        sprint = result.scalar_one()

        validate_transition(sprint.status, "completed")

        sprint.status = "completed"
        sprint.outcome_type = outcome_type
        sprint.outcome_summary = outcome_summary
        sprint.actual_end_at = datetime.now(timezone.utc)

        await self.session.flush()

        logger.info(
            "Ended sprint %s (outcome=%s)",
            sprint_id,
            outcome_type,
        )
        return sprint

    async def pause_sprint(self, sprint_id: UUID) -> "ResearchSprint":
        """Pause a sprint mid-progress."""
        from platform.infrastructure.database.models import ResearchSprint

        result = await self.session.execute(
            select(ResearchSprint)
            .where(ResearchSprint.id == sprint_id)
            .with_for_update()
        )
        sprint = result.scalar_one()

        validate_transition(sprint.status, "paused")
        sprint.status = "paused"

        await self.session.flush()

        logger.info("Paused sprint %s", sprint_id)
        return sprint

    async def resume_sprint(self, sprint_id: UUID) -> "ResearchSprint":
        """Resume a paused sprint."""
        from platform.infrastructure.database.models import ResearchSprint

        result = await self.session.execute(
            select(ResearchSprint)
            .where(ResearchSprint.id == sprint_id)
            .with_for_update()
        )
        sprint = result.scalar_one()

        validate_transition(sprint.status, "active")
        sprint.status = "active"

        await self.session.flush()

        logger.info("Resumed sprint %s", sprint_id)
        return sprint

    async def get_active_sprint(
        self, agent_id: UUID, lab_id: UUID
    ) -> "ResearchSprint | None":
        """Get the currently active sprint for an agent in a lab."""
        from platform.infrastructure.database.models import ResearchSprint

        result = await self.session.execute(
            select(ResearchSprint).where(
                ResearchSprint.agent_id == agent_id,
                ResearchSprint.lab_id == lab_id,
                ResearchSprint.status.in_(["planning", "active", "wrapping_up", "paused"]),
            )
        )
        return result.scalar_one_or_none()

    async def activate_sprint(self, sprint_id: UUID) -> "ResearchSprint":
        """Transition sprint from planning to active."""
        from platform.infrastructure.database.models import ResearchSprint

        result = await self.session.execute(
            select(ResearchSprint)
            .where(ResearchSprint.id == sprint_id)
            .with_for_update()
        )
        sprint = result.scalar_one()

        validate_transition(sprint.status, "active")
        sprint.status = "active"

        await self.session.flush()

        logger.info("Activated sprint %s", sprint_id)
        return sprint

    async def auto_wrap_up(self) -> list[UUID]:
        """Auto-transition sprints to wrapping_up at 90% time elapsed.

        Called periodically by Celery beat task.
        """
        from platform.infrastructure.database.models import ResearchSprint

        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(ResearchSprint).where(
                ResearchSprint.status == "active",
            )
        )
        sprints = result.scalars().all()

        transitioned = []
        for sprint in sprints:
            total_duration = (sprint.target_end_at - sprint.started_at).total_seconds()
            elapsed = (now - sprint.started_at).total_seconds()
            if total_duration > 0 and elapsed / total_duration >= 0.9:
                sprint.status = "wrapping_up"
                transitioned.append(sprint.id)
                logger.info("Auto-transitioned sprint %s to wrapping_up", sprint.id)

        if transitioned:
            await self.session.flush()

        return transitioned
