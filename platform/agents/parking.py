"""AgentParkingService — park and resume agents with checkpoint preservation."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

from .checkpoint import AgentCheckpointData
from .checkpoint_service import CheckpointService
from .lifecycle import AgentOperationalState, AgentResearchState

logger = get_logger(__name__)


class AgentParkingService:
    """Manages parking (suspending) and resuming agents."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.checkpoint_service = CheckpointService(session)

    async def park(
        self,
        agent_id: UUID,
        reason: str = "manual",
    ) -> dict:
        """Park an agent — save checkpoint and mark as suspended.

        Returns the checkpoint ID for later resumption.
        """
        from platform.infrastructure.database.models import Agent

        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id).with_for_update()
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")

        # Load existing latest checkpoint data, or create minimal one
        existing_data = await self.checkpoint_service.load_latest(agent_id)

        if existing_data is None:
            existing_data = AgentCheckpointData(
                agent_id=str(agent_id),
                research_state=AgentResearchState.PARKED.value,
            )
        else:
            existing_data.research_state = AgentResearchState.PARKED.value

        # Save parking checkpoint
        checkpoint_id = await self.checkpoint_service.save_checkpoint(
            agent_id=agent_id,
            data=existing_data,
            checkpoint_type="pre_park",
        )

        # Update agent status
        agent.status = "suspended"

        await self.session.flush()

        logger.info(
            "Parked agent %s (reason=%s, checkpoint=%s)",
            agent_id,
            reason,
            checkpoint_id,
        )

        return {
            "agent_id": str(agent_id),
            "checkpoint_id": str(checkpoint_id),
            "reason": reason,
            "parked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def resume(self, agent_id: UUID) -> dict:
        """Resume a parked agent from its latest checkpoint.

        Returns the checkpoint data for context restoration.
        """
        from platform.infrastructure.database.models import Agent

        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id).with_for_update()
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")

        if agent.status != "suspended":
            raise ValueError(f"Agent {agent_id} is not parked (status={agent.status})")

        # Load latest checkpoint
        checkpoint_data = await self.checkpoint_service.load_latest(agent_id)
        if checkpoint_data is None:
            raise ValueError(f"No checkpoint found for agent {agent_id}")

        # Restore to online
        agent.status = "active"

        await self.session.flush()

        logger.info("Resumed agent %s from checkpoint", agent_id)

        return {
            "agent_id": str(agent_id),
            "restored_state": checkpoint_data.research_state,
            "checkpoint_sequence": checkpoint_data.sequence_number,
            "resumed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def estimate_resume_cost(self, agent_id: UUID) -> dict:
        """Estimate the cost/time to resume a parked agent."""
        from platform.infrastructure.database.models import Agent, AgentCheckpoint

        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")

        # Load latest checkpoint
        from sqlalchemy import func
        cp_result = await self.session.execute(
            select(AgentCheckpoint)
            .where(AgentCheckpoint.agent_id == agent_id, AgentCheckpoint.is_latest == True)  # noqa: E712
            .limit(1)
        )
        checkpoint = cp_result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        checkpoint_id = None
        checkpoint_age_hours = 0.0
        tokens_estimate = 500  # Base context restoration cost

        if checkpoint:
            checkpoint_id = checkpoint.id
            if checkpoint.created_at:
                checkpoint_age_hours = (now - checkpoint.created_at).total_seconds() / 3600

            # More stale = more drift = more tokens to catch up
            tokens_estimate += int(checkpoint_age_hours * 100)

            # Factor in checkpoint complexity
            if checkpoint.tokens_consumed:
                tokens_estimate += checkpoint.tokens_consumed // 10

        # Count state drift: new claims/findings since checkpoint
        state_drift_items = 0
        if checkpoint and checkpoint.created_at:
            from platform.infrastructure.database.models import Claim
            drift_result = await self.session.execute(
                select(func.count()).where(
                    Claim.created_at > checkpoint.created_at,
                )
            )
            state_drift_items = drift_result.scalar() or 0

        estimated_minutes = tokens_estimate / 1000 * 2  # Rough: 1000 tokens ~2 min

        return {
            "agent_id": str(agent_id),
            "checkpoint_id": str(checkpoint_id) if checkpoint_id else None,
            "estimated_tokens": tokens_estimate,
            "estimated_minutes": round(estimated_minutes, 1),
            "state_drift_items": state_drift_items,
            "checkpoint_age_hours": round(checkpoint_age_hours, 1),
        }
