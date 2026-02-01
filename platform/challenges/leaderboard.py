"""ChallengeLeaderboard — manages challenge rankings.

During active phase: ranked by best public_score per lab.
After evaluation: ranked by private_score (the real ranking).
"""

from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

from .schemas import LeaderboardEntry

logger = get_logger(__name__)


class ChallengeLeaderboard:
    """Manages challenge rankings with public/private score split."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_leaderboard(
        self,
        challenge_id: UUID,
        phase: str = "active",
        limit: int = 50,
    ) -> list[LeaderboardEntry]:
        """Get the challenge leaderboard.

        Active phase: public_score only.
        Completed phase: private_score (final ranking).
        """
        from platform.infrastructure.database.models import (
            ChallengeSubmission,
            Lab,
            ResearchChallenge,
        )

        # Determine which score to use
        score_col = (
            ChallengeSubmission.public_score
            if phase == "active"
            else ChallengeSubmission.private_score
        )

        # Load challenge to check higher_is_better
        ch_result = await self.session.execute(
            select(ResearchChallenge).where(ResearchChallenge.id == challenge_id)
        )
        challenge = ch_result.scalar_one()

        order = desc(func.max(score_col)) if challenge.higher_is_better else func.min(score_col)

        # Best score per lab
        query = (
            select(
                ChallengeSubmission.lab_id,
                func.max(score_col).label("best_score") if challenge.higher_is_better
                else func.min(score_col).label("best_score"),
                func.count().label("submission_count"),
                func.max(ChallengeSubmission.created_at).label("last_submission_at"),
            )
            .where(
                ChallengeSubmission.challenge_id == challenge_id,
                score_col.is_not(None),
            )
            .group_by(ChallengeSubmission.lab_id)
            .order_by(order)
            .limit(limit)
        )

        result = await self.session.execute(query)
        rows = result.all()

        entries = []
        for rank, row in enumerate(rows, 1):
            entries.append(
                LeaderboardEntry(
                    rank=rank,
                    lab_id=row.lab_id,
                    best_score=float(row.best_score),
                    submission_count=row.submission_count,
                    last_submission_at=row.last_submission_at,
                )
            )

        return entries
