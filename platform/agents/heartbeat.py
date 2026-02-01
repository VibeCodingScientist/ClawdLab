"""HeartbeatProcessor — processes three-probe heartbeats and updates agent state."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

from .lifecycle import AgentOperationalState, AgentResearchState
from .lifecycle_schemas import HeartbeatRequest

logger = get_logger(__name__)

# Thresholds
LIVENESS_FAILURE_LIMIT = 3
READINESS_STALE_MINUTES = 5
PROGRESS_WARNING_MINUTES = 30
PROGRESS_STUCK_MINUTES = 60
PROGRESS_CRITICAL_MINUTES = 120


class HeartbeatProcessor:
    """Processes three-probe heartbeats from agents."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def process_heartbeat(
        self,
        agent_id: UUID,
        heartbeat: HeartbeatRequest,
    ) -> dict:
        """Process a heartbeat and update agent state.

        Returns a dict with evaluation results.
        """
        from platform.infrastructure.database.models import Agent

        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id).with_for_update()
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")

        now = datetime.now(timezone.utc)

        # Evaluate each probe
        liveness_ok = heartbeat.liveness.alive and heartbeat.liveness.error_count < LIVENESS_FAILURE_LIMIT
        readiness_ok = heartbeat.readiness.ready and heartbeat.readiness.queue_depth < heartbeat.readiness.max_load
        progress_ok = heartbeat.progress.stale_minutes < PROGRESS_WARNING_MINUTES

        warnings: list[str] = []

        # Liveness warnings
        if not heartbeat.liveness.alive:
            warnings.append("Agent reports not alive")
        if heartbeat.liveness.error_count >= LIVENESS_FAILURE_LIMIT:
            warnings.append(f"High error count: {heartbeat.liveness.error_count}")
        if heartbeat.liveness.memory_mb > 4096:
            warnings.append(f"High memory usage: {heartbeat.liveness.memory_mb}MB")

        # Readiness warnings
        if not heartbeat.readiness.ready:
            warnings.append("Agent reports not ready")
        if heartbeat.readiness.queue_depth >= heartbeat.readiness.max_load:
            warnings.append(f"Queue at capacity: {heartbeat.readiness.queue_depth}/{heartbeat.readiness.max_load}")

        # Progress warnings
        stale = heartbeat.progress.stale_minutes
        if stale >= PROGRESS_CRITICAL_MINUTES:
            warnings.append(f"Critical: no progress for {stale} minutes")
        elif stale >= PROGRESS_STUCK_MINUTES:
            warnings.append(f"Stuck: no progress for {stale} minutes")
        elif stale >= PROGRESS_WARNING_MINUTES:
            warnings.append(f"Slow progress: {stale} minutes since last finding")

        # Determine recommendation
        recommendation = "continue"
        if not liveness_ok:
            recommendation = "restart"
        elif stale >= PROGRESS_CRITICAL_MINUTES:
            recommendation = "park"
        elif stale >= PROGRESS_STUCK_MINUTES:
            recommendation = "investigate"

        # Update agent's last heartbeat (if field exists)
        agent.last_heartbeat_at = now

        await self.session.flush()

        logger.info(
            "Heartbeat processed for agent %s (liveness=%s, readiness=%s, progress=%s, recommendation=%s)",
            agent_id,
            liveness_ok,
            readiness_ok,
            progress_ok,
            recommendation,
        )

        return {
            "agent_id": str(agent_id),
            "operational_state": AgentOperationalState.ONLINE.value if liveness_ok else AgentOperationalState.CRASHED.value,
            "research_state": heartbeat.progress.research_state,
            "liveness_ok": liveness_ok,
            "readiness_ok": readiness_ok,
            "progress_ok": progress_ok,
            "warnings": warnings,
            "recommendation": recommendation,
        }
