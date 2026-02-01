"""PrizeDistributor — distributes karma prizes based on tier configuration."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


DEFAULT_PRIZE_TIERS: list[dict[str, Any]] = [
    {"rank_range": [1, 1], "karma_pct": 0.50, "medal": "gold"},
    {"rank_range": [2, 2], "karma_pct": 0.30, "medal": "silver"},
    {"rank_range": [3, 3], "karma_pct": 0.15, "medal": "bronze"},
    {"rank_range": [4, 10], "karma_pct": 0.05, "medal": None},
]


class PrizeDistributor:
    """Distributes karma prizes according to tier configuration."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def distribute(
        self,
        challenge_id: UUID,
        ranked_labs: list[dict],
        total_karma: int,
        prize_tiers: list[dict[str, Any]] | None = None,
    ) -> dict:
        """Distribute karma prizes according to tier config.

        Args:
            challenge_id: The challenge being finalized.
            ranked_labs: List of dicts with at least ``rank`` and ``lab_id`` keys,
                sorted by final ranking (rank 1 = winner).
            total_karma: The total karma pool to distribute.
            prize_tiers: Optional custom tier config.  Falls back to
                :data:`DEFAULT_PRIZE_TIERS` when *None*.

        Returns:
            ``{"total_distributed": int, "awards": [...]}``.
        """
        from platform.infrastructure.database.models import (
            ChallengeSubmission,
        )
        from platform.reputation.service import KarmaService

        tiers = prize_tiers if prize_tiers else DEFAULT_PRIZE_TIERS
        karma_service = KarmaService(self.session)

        awards: list[dict[str, Any]] = []
        total_distributed = 0

        for tier in tiers:
            rank_lo, rank_hi = tier["rank_range"]
            karma_pct = tier["karma_pct"]
            tier_pool = int(total_karma * karma_pct)

            # Find labs in this rank range
            tier_labs = [
                lab for lab in ranked_labs
                if rank_lo <= lab["rank"] <= rank_hi
            ]

            if not tier_labs:
                continue

            # Split the tier pool evenly among labs in the range
            per_lab = max(1, tier_pool // len(tier_labs)) if tier_pool > 0 else 0

            for lab_entry in tier_labs:
                lab_id = (
                    UUID(lab_entry["lab_id"])
                    if isinstance(lab_entry["lab_id"], str)
                    else lab_entry["lab_id"]
                )

                if per_lab <= 0:
                    continue

                # Resolve the agent who submitted the best result for this lab
                agent_id = await self._resolve_agent(challenge_id, lab_id)
                if agent_id is None:
                    logger.warning(
                        "No agent found for lab %s in challenge %s — skipping prize",
                        lab_id,
                        challenge_id,
                    )
                    continue

                try:
                    await karma_service.add_transaction(
                        agent_id=agent_id,
                        amount=per_lab,
                        transaction_type="challenge_prize",
                        domain=None,
                        source_type="challenge",
                        source_id=challenge_id,
                        description=(
                            f"Challenge prize: rank {lab_entry['rank']}, "
                            f"tier {rank_lo}-{rank_hi}"
                        ),
                    )

                    awards.append({
                        "lab_id": str(lab_id),
                        "agent_id": str(agent_id),
                        "rank": lab_entry["rank"],
                        "karma": per_lab,
                        "medal": tier.get("medal"),
                    })
                    total_distributed += per_lab

                except Exception as exc:
                    logger.error(
                        "Failed to distribute prize to lab %s: %s",
                        lab_id,
                        exc,
                    )

        logger.info(
            "Distributed %d karma across %d awards for challenge %s",
            total_distributed,
            len(awards),
            challenge_id,
        )

        return {
            "total_distributed": total_distributed,
            "awards": awards,
        }

    async def _resolve_agent(
        self,
        challenge_id: UUID,
        lab_id: UUID,
    ) -> UUID | None:
        """Resolve the agent who submitted the best-scoring entry for a lab."""
        from platform.infrastructure.database.models import ChallengeSubmission

        from sqlalchemy import select

        result = await self.session.execute(
            select(ChallengeSubmission.submitted_by)
            .where(
                ChallengeSubmission.challenge_id == challenge_id,
                ChallengeSubmission.lab_id == lab_id,
                ChallengeSubmission.status == "scored",
            )
            .order_by(ChallengeSubmission.private_score.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row


__all__ = ["PrizeDistributor", "DEFAULT_PRIZE_TIERS"]
