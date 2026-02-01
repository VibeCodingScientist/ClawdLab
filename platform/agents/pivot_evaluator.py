"""PivotEvaluator — decides whether an agent should continue, wrap up, pivot, or park."""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class PivotDecision(str, Enum):
    """Possible decisions from pivot evaluation."""

    CONTINUE = "continue"
    WRAP_UP = "wrap_up"
    PIVOT_NOW = "pivot_now"
    PARK = "park"


class PivotEvaluator:
    """Evaluates whether an agent's current sprint should continue or pivot."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def should_pivot(
        self,
        agent_id: UUID,
        lab_id: UUID,
    ) -> dict:
        """Evaluate whether the agent should pivot.

        Considers:
        1. Sprint progress vs. time elapsed
        2. Findings velocity (findings per day)
        3. Confidence trend
        4. Resource consumption rate
        5. External events (new literature, competing claims)

        Returns decision and reasoning.
        """
        from platform.infrastructure.database.models import (
            ResearchSprint,
            AgentProgressPost,
            AgentCheckpoint,
        )

        # Get active sprint
        sprint_result = await self.session.execute(
            select(ResearchSprint).where(
                ResearchSprint.agent_id == agent_id,
                ResearchSprint.lab_id == lab_id,
                ResearchSprint.status.in_(["active", "wrapping_up"]),
            )
        )
        sprint = sprint_result.scalar_one_or_none()

        if sprint is None:
            return {
                "decision": PivotDecision.PARK.value,
                "reason": "No active sprint found",
                "confidence": 1.0,
                "signals": {},
            }

        now = datetime.now(timezone.utc)
        total_duration = (sprint.target_end_at - sprint.started_at).total_seconds()
        elapsed = (now - sprint.started_at).total_seconds()
        time_pct = elapsed / total_duration if total_duration > 0 else 1.0

        # Count progress posts (findings)
        post_count_result = await self.session.execute(
            select(func.count()).where(
                AgentProgressPost.sprint_id == sprint.id,
            )
        )
        findings_count = post_count_result.scalar() or 0

        # Get latest checkpoint for token consumption
        cp_result = await self.session.execute(
            select(AgentCheckpoint)
            .where(AgentCheckpoint.agent_id == agent_id, AgentCheckpoint.is_latest == True)  # noqa: E712
            .limit(1)
        )
        checkpoint = cp_result.scalar_one_or_none()
        tokens_consumed = checkpoint.tokens_consumed if checkpoint else 0

        # Calculate velocity
        days_elapsed = max(elapsed / 86400, 0.1)
        findings_per_day = findings_count / days_elapsed

        # Signals
        signals = {
            "time_pct": round(time_pct, 2),
            "findings_count": findings_count,
            "findings_per_day": round(findings_per_day, 2),
            "tokens_consumed": tokens_consumed,
            "sprint_status": sprint.status,
        }

        # Decision logic
        decision = PivotDecision.CONTINUE
        reason = "Sprint progressing normally"
        confidence = 0.7

        if sprint.status == "wrapping_up":
            decision = PivotDecision.WRAP_UP
            reason = "Sprint is in wrapping_up phase"
            confidence = 0.9

        elif time_pct > 0.9:
            decision = PivotDecision.WRAP_UP
            reason = f"Sprint at {time_pct:.0%} of allocated time"
            confidence = 0.85

        elif time_pct > 0.5 and findings_count == 0:
            decision = PivotDecision.PIVOT_NOW
            reason = f"No findings after {time_pct:.0%} of time elapsed"
            confidence = 0.75

        elif time_pct > 0.7 and findings_per_day < 0.5:
            decision = PivotDecision.WRAP_UP
            reason = f"Low velocity ({findings_per_day:.1f}/day) late in sprint"
            confidence = 0.7

        elif tokens_consumed > 100_000 and findings_count == 0:
            decision = PivotDecision.PARK
            reason = f"High token consumption ({tokens_consumed}) with no findings"
            confidence = 0.8

        logger.info(
            "Pivot evaluation for agent %s: %s (reason=%s, confidence=%.2f)",
            agent_id,
            decision.value,
            reason,
            confidence,
        )

        return {
            "decision": decision.value,
            "reason": reason,
            "confidence": confidence,
            "signals": signals,
        }
