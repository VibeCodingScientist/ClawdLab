"""CheckpointService — save, load, list, and prune agent checkpoints."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

from .checkpoint import AgentCheckpointData

logger = get_logger(__name__)

MAX_CHECKPOINTS_PER_AGENT = 50


class CheckpointService:
    """Manages agent research state checkpoints."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_checkpoint(
        self,
        agent_id: UUID,
        data: AgentCheckpointData,
        checkpoint_type: str = "auto",
        lab_id: UUID | None = None,
    ) -> UUID:
        """Save a new checkpoint, marking it as latest."""
        from platform.infrastructure.database.models import AgentCheckpoint

        # Mark all previous checkpoints as not latest
        await self.session.execute(
            update(AgentCheckpoint)
            .where(AgentCheckpoint.agent_id == agent_id, AgentCheckpoint.is_latest == True)  # noqa: E712
            .values(is_latest=False)
        )

        # Get next sequence number
        seq_result = await self.session.execute(
            select(func.coalesce(func.max(AgentCheckpoint.sequence_number), 0))
            .where(AgentCheckpoint.agent_id == agent_id)
        )
        next_seq = seq_result.scalar() + 1

        data.sequence_number = next_seq
        data.agent_id = str(agent_id)
        if lab_id:
            data.lab_id = str(lab_id)

        checkpoint = AgentCheckpoint(
            agent_id=agent_id,
            lab_id=lab_id,
            sequence_number=next_seq,
            checkpoint_data=data.to_dict(),
            research_state=data.research_state,
            sprint_id=UUID(data.sprint_id) if data.sprint_id else None,
            task_type=data.current_task.task_type if data.current_task else None,
            progress_pct=data.sprint_progress_pct,
            tokens_consumed=data.tokens_consumed,
            checkpoint_type=checkpoint_type,
            is_latest=True,
        )
        self.session.add(checkpoint)
        await self.session.flush()

        # Prune old checkpoints
        await self._prune_old(agent_id)

        logger.info(
            "Saved checkpoint #%d for agent %s (type=%s)",
            next_seq,
            agent_id,
            checkpoint_type,
        )
        return checkpoint.id

    async def load_latest(self, agent_id: UUID) -> AgentCheckpointData | None:
        """Load the most recent checkpoint for an agent."""
        from platform.infrastructure.database.models import AgentCheckpoint

        result = await self.session.execute(
            select(AgentCheckpoint)
            .where(AgentCheckpoint.agent_id == agent_id, AgentCheckpoint.is_latest == True)  # noqa: E712
            .limit(1)
        )
        checkpoint = result.scalar_one_or_none()
        if checkpoint is None:
            return None

        return AgentCheckpointData.from_dict(checkpoint.checkpoint_data)

    async def list_checkpoints(
        self,
        agent_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """List checkpoints for an agent (summary only, not full data)."""
        from platform.infrastructure.database.models import AgentCheckpoint

        result = await self.session.execute(
            select(AgentCheckpoint)
            .where(AgentCheckpoint.agent_id == agent_id)
            .order_by(AgentCheckpoint.sequence_number.desc())
            .limit(limit)
            .offset(offset)
        )
        checkpoints = result.scalars().all()

        return [
            {
                "id": str(cp.id),
                "sequence_number": cp.sequence_number,
                "checkpoint_type": cp.checkpoint_type,
                "research_state": cp.research_state,
                "progress_pct": float(cp.progress_pct) if cp.progress_pct else 0.0,
                "tokens_consumed": cp.tokens_consumed,
                "is_latest": cp.is_latest,
                "created_at": cp.created_at.isoformat() if cp.created_at else None,
            }
            for cp in checkpoints
        ]

    async def _prune_old(self, agent_id: UUID) -> int:
        """Keep only the last N checkpoints per agent."""
        from platform.infrastructure.database.models import AgentCheckpoint

        # Count total
        count_result = await self.session.execute(
            select(func.count()).where(AgentCheckpoint.agent_id == agent_id)
        )
        total = count_result.scalar() or 0

        if total <= MAX_CHECKPOINTS_PER_AGENT:
            return 0

        # Find the cutoff sequence number
        cutoff_result = await self.session.execute(
            select(AgentCheckpoint.sequence_number)
            .where(AgentCheckpoint.agent_id == agent_id)
            .order_by(AgentCheckpoint.sequence_number.desc())
            .offset(MAX_CHECKPOINTS_PER_AGENT)
            .limit(1)
        )
        cutoff_seq = cutoff_result.scalar()
        if cutoff_seq is None:
            return 0

        # Delete older checkpoints
        delete_result = await self.session.execute(
            delete(AgentCheckpoint).where(
                AgentCheckpoint.agent_id == agent_id,
                AgentCheckpoint.sequence_number <= cutoff_seq,
                AgentCheckpoint.is_latest == False,  # noqa: E712
            )
        )
        pruned = delete_result.rowcount
        if pruned:
            logger.info("Pruned %d old checkpoints for agent %s", pruned, agent_id)
        return pruned
