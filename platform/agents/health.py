"""AgentHealthEvaluator — evaluates agent health and detects stuck agents."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

from .lifecycle import AgentOperationalState

logger = get_logger(__name__)

# Thresholds
LIVENESS_FAILURE_THRESHOLD = 3
HEARTBEAT_STALE_MINUTES = 5
PROGRESS_WARNING_MINUTES = 30
PROGRESS_STUCK_MINUTES = 60
PROGRESS_CRITICAL_MINUTES = 120


class AgentHealthEvaluator:
    """Evaluates agent health from heartbeat data and detects stuck agents."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def evaluate(self, agent_id: UUID) -> dict:
        """Full health assessment for a single agent."""
        from platform.infrastructure.database.models import Agent, AgentCheckpoint

        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")

        now = datetime.now(timezone.utc)
        warnings: list[str] = []

        # Check heartbeat freshness
        liveness_ok = True
        if hasattr(agent, "last_heartbeat_at") and agent.last_heartbeat_at:
            stale_minutes = (now - agent.last_heartbeat_at).total_seconds() / 60
            if stale_minutes > HEARTBEAT_STALE_MINUTES:
                liveness_ok = False
                warnings.append(f"No heartbeat for {stale_minutes:.0f} minutes")
        else:
            warnings.append("No heartbeat data available")

        # Check latest checkpoint for progress
        cp_result = await self.session.execute(
            select(AgentCheckpoint)
            .where(AgentCheckpoint.agent_id == agent_id, AgentCheckpoint.is_latest == True)  # noqa: E712
            .limit(1)
        )
        checkpoint = cp_result.scalar_one_or_none()

        progress_ok = True
        readiness_ok = True

        if checkpoint and checkpoint.created_at:
            cp_age_minutes = (now - checkpoint.created_at).total_seconds() / 60
            if cp_age_minutes > PROGRESS_CRITICAL_MINUTES:
                progress_ok = False
                warnings.append(f"Last checkpoint {cp_age_minutes:.0f} minutes old (critical)")
            elif cp_age_minutes > PROGRESS_STUCK_MINUTES:
                progress_ok = False
                warnings.append(f"Last checkpoint {cp_age_minutes:.0f} minutes old (stuck)")
            elif cp_age_minutes > PROGRESS_WARNING_MINUTES:
                warnings.append(f"Last checkpoint {cp_age_minutes:.0f} minutes old (slow)")

        # Determine recommendation
        recommendation = "continue"
        if not liveness_ok:
            recommendation = "restart"
        elif not progress_ok:
            recommendation = "investigate"

        op_state = AgentOperationalState.ONLINE.value if liveness_ok else AgentOperationalState.CRASHED.value
        research_state = checkpoint.research_state if checkpoint else "idle"

        return {
            "agent_id": str(agent_id),
            "operational_state": op_state,
            "research_state": research_state,
            "liveness_ok": liveness_ok,
            "readiness_ok": readiness_ok,
            "progress_ok": progress_ok,
            "warnings": warnings,
            "recommendation": recommendation,
        }

    async def detect_stuck_agents(self) -> list[dict]:
        """Find all agents that appear stuck (for Celery beat task).

        Returns list of agent health assessments for agents with warnings.
        """
        from platform.infrastructure.database.models import Agent

        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(minutes=HEARTBEAT_STALE_MINUTES)

        # Find agents with stale heartbeats or no heartbeats
        result = await self.session.execute(
            select(Agent).where(
                Agent.status == "active",
            )
        )
        agents = result.scalars().all()

        stuck = []
        for agent in agents:
            try:
                assessment = await self.evaluate(agent.id)
                if assessment["warnings"]:
                    stuck.append(assessment)
            except Exception:
                logger.exception("Error evaluating health for agent %s", agent.id)

        if stuck:
            logger.warning("Detected %d stuck/unhealthy agents", len(stuck))

        return stuck
