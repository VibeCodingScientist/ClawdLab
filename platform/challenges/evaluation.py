"""ChallengeEvaluator — scoring, finalization, medals, and prize distribution."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class ChallengeEvaluator:
    """Evaluates submissions and finalizes completed challenges."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def evaluate_submission(self, submission_id: UUID) -> dict:
        """Evaluate a single submission.

        Sets public_score (visible during active phase) and private_score
        (used for final ranking after evaluation closes).

        Scoring uses a deterministic hash-based approach seeded by the
        submission metadata and the challenge evaluation_config.  In a real
        deployment this would call out to a sandboxed evaluation service.
        """
        from platform.infrastructure.database.models import (
            ChallengeSubmission,
            ResearchChallenge,
        )

        result = await self.session.execute(
            select(ChallengeSubmission)
            .where(ChallengeSubmission.id == submission_id)
            .with_for_update()
        )
        submission = result.scalar_one()

        ch_result = await self.session.execute(
            select(ResearchChallenge).where(
                ResearchChallenge.id == submission.challenge_id
            )
        )
        challenge = ch_result.scalar_one()

        # Deterministic scoring based on submission hash + evaluation config
        seed_material = (
            f"{submission.submission_hash}"
            f":{challenge.evaluation_metric}"
            f":{submission.sequence_number}"
        )
        digest = hashlib.sha256(seed_material.encode()).hexdigest()

        # Map the first 8 hex chars to a 0-1 float
        public_raw = int(digest[:8], 16) / 0xFFFFFFFF
        private_raw = int(digest[8:16], 16) / 0xFFFFFFFF

        # Scale to a reasonable metric range (e.g. 0-100)
        scale = challenge.evaluation_config.get("score_scale", 100.0)
        public_score = round(public_raw * float(scale), 6)
        private_score = round(private_raw * float(scale), 6)

        submission.public_score = Decimal(str(public_score))
        submission.private_score = Decimal(str(private_score))
        submission.status = "scored"
        submission.evaluated_at = datetime.now(timezone.utc)
        submission.evaluation_log = {
            "metric": challenge.evaluation_metric,
            "public_score": public_score,
            "private_score": private_score,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.session.flush()

        logger.info(
            "Evaluated submission %s (public=%.4f, private=%.4f)",
            submission_id,
            public_score,
            private_score,
        )

        return {
            "submission_id": str(submission_id),
            "public_score": public_score,
            "private_score": private_score,
            "status": "scored",
        }

    async def finalize_challenge(self, challenge_slug: str) -> dict:
        """Finalize a completed challenge.

        1. Verify status == 'evaluation'
        2. Rank evaluated submissions by private_score
        3. Run anti-gaming checks
        4. Build final_leaderboard JSONB
        5. Award medals to top 3
        6. Distribute karma prizes
        7. Award XP to winners
        8. Return stakes to non-disqualified labs
        9. Transition challenge to 'completed'
        """
        from platform.infrastructure.database.models import (
            ChallengeRegistration,
            ChallengeSubmission,
            ResearchChallenge,
        )

        from .anti_gaming import AntiGamingService
        from .prizes import PrizeDistributor
        from .state_machine import validate_transition

        # 1. Load challenge and verify status
        ch_result = await self.session.execute(
            select(ResearchChallenge)
            .where(ResearchChallenge.slug == challenge_slug)
            .with_for_update()
        )
        challenge = ch_result.scalar_one()

        validate_transition(challenge.status, "completed")

        # 2. Get best private_score per lab (ranked)
        score_agg = (
            func.max(ChallengeSubmission.private_score)
            if challenge.higher_is_better
            else func.min(ChallengeSubmission.private_score)
        )
        order = (
            desc(score_agg)
            if challenge.higher_is_better
            else score_agg
        )

        ranked_query = (
            select(
                ChallengeSubmission.lab_id,
                score_agg.label("best_score"),
                func.count().label("submission_count"),
            )
            .where(
                ChallengeSubmission.challenge_id == challenge.id,
                ChallengeSubmission.status == "scored",
                ChallengeSubmission.private_score.is_not(None),
            )
            .group_by(ChallengeSubmission.lab_id)
            .order_by(order)
        )
        ranked_result = await self.session.execute(ranked_query)
        ranked_rows = ranked_result.all()

        # 3. Anti-gaming checks — flag suspicious submissions
        anti_gaming = AntiGamingService(self.session)
        disqualified_labs: set[UUID] = set()

        for row in ranked_rows:
            # Get one submission per lab for checking
            sub_result = await self.session.execute(
                select(ChallengeSubmission)
                .where(
                    ChallengeSubmission.challenge_id == challenge.id,
                    ChallengeSubmission.lab_id == row.lab_id,
                    ChallengeSubmission.status == "scored",
                )
                .order_by(ChallengeSubmission.private_score.desc())
                .limit(1)
            )
            best_sub = sub_result.scalar_one_or_none()
            if best_sub:
                check = await anti_gaming.check_submission(best_sub.id)
                if not check["passed"]:
                    disqualified_labs.add(row.lab_id)
                    logger.warning(
                        "Lab %s disqualified from challenge '%s': %s",
                        row.lab_id,
                        challenge_slug,
                        check["flags"],
                    )

        # Filter out disqualified labs
        eligible = [r for r in ranked_rows if r.lab_id not in disqualified_labs]

        # 4. Build ranked submissions dicts and final leaderboard
        ranked_submissions: list[dict] = []
        for rank, row in enumerate(eligible, 1):
            ranked_submissions.append({
                "rank": rank,
                "lab_id": str(row.lab_id),
                "best_score": float(row.best_score),
                "submission_count": row.submission_count,
            })

        final_leaderboard = {
            "finalized_at": datetime.now(timezone.utc).isoformat(),
            "total_participants": len(ranked_rows),
            "disqualified": len(disqualified_labs),
            "rankings": ranked_submissions,
        }
        challenge.final_leaderboard = final_leaderboard

        if eligible:
            challenge.winner_lab_id = eligible[0]["lab_id"] if isinstance(eligible[0], dict) else eligible[0].lab_id

        # 5. Award medals
        medals_awarded = await self._award_medals(challenge.id, ranked_submissions)

        # 6. Distribute karma prizes
        karma_distributed = 0
        if challenge.total_prize_karma > 0 and ranked_submissions:
            distributor = PrizeDistributor(self.session)
            prize_result = await distributor.distribute(
                challenge_id=challenge.id,
                ranked_labs=ranked_submissions,
                total_karma=challenge.total_prize_karma,
                prize_tiers=challenge.prize_tiers if challenge.prize_tiers else None,
            )
            karma_distributed = prize_result["total_distributed"]

        # 7. Award XP to top-placing agents
        await self._award_winner_xp(challenge, ranked_submissions)

        # 8. Return stakes to non-disqualified labs
        await self._return_stakes(challenge.id, disqualified_labs)

        # 9. Transition to completed
        challenge.status = "completed"
        challenge.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

        logger.info(
            "Finalized challenge '%s': %d participants, %d disqualified, %d medals",
            challenge_slug,
            len(ranked_rows),
            len(disqualified_labs),
            len(medals_awarded),
        )

        return {
            "challenge_slug": challenge_slug,
            "final_leaderboard": final_leaderboard,
            "medals_awarded": medals_awarded,
            "karma_distributed": karma_distributed,
        }

    async def _award_medals(
        self,
        challenge_id: UUID,
        ranked_submissions: list[dict],
    ) -> list[dict]:
        """Award gold/silver/bronze medals based on rank."""
        from platform.infrastructure.database.models import (
            ChallengeMedal,
            ChallengeSubmission,
        )

        medal_map = {1: "gold", 2: "silver", 3: "bronze"}
        medals_created: list[dict] = []

        for entry in ranked_submissions[:3]:
            rank = entry["rank"]
            lab_id = UUID(entry["lab_id"]) if isinstance(entry["lab_id"], str) else entry["lab_id"]
            medal_type = medal_map.get(rank)
            if medal_type is None:
                continue

            # Find the agent who submitted the best submission
            sub_result = await self.session.execute(
                select(ChallengeSubmission)
                .where(
                    ChallengeSubmission.challenge_id == challenge_id,
                    ChallengeSubmission.lab_id == lab_id,
                    ChallengeSubmission.status == "scored",
                )
                .order_by(ChallengeSubmission.private_score.desc())
                .limit(1)
            )
            best_sub = sub_result.scalar_one_or_none()
            if best_sub is None:
                continue

            medal = ChallengeMedal(
                challenge_id=challenge_id,
                lab_id=lab_id,
                agent_id=best_sub.submitted_by,
                medal_type=medal_type,
                rank=rank,
                score=best_sub.private_score,
            )
            self.session.add(medal)

            medals_created.append({
                "medal_type": medal_type,
                "rank": rank,
                "lab_id": str(lab_id),
                "agent_id": str(best_sub.submitted_by),
                "score": float(best_sub.private_score) if best_sub.private_score else None,
            })

        await self.session.flush()
        return medals_created

    async def _award_winner_xp(
        self,
        challenge: object,
        ranked_submissions: list[dict],
    ) -> None:
        """Award XP to top-placing agents via ExperienceService."""
        from platform.infrastructure.database.models import ChallengeSubmission

        from platform.experience.service import ExperienceService
        from platform.experience.calculator import XPSource

        xp_service = ExperienceService(self.session)

        xp_amounts = {1: 500, 2: 300, 3: 150}

        for entry in ranked_submissions[:3]:
            rank = entry["rank"]
            lab_id = UUID(entry["lab_id"]) if isinstance(entry["lab_id"], str) else entry["lab_id"]

            sub_result = await self.session.execute(
                select(ChallengeSubmission)
                .where(
                    ChallengeSubmission.challenge_id == challenge.id,
                    ChallengeSubmission.lab_id == lab_id,
                    ChallengeSubmission.status == "scored",
                )
                .order_by(ChallengeSubmission.private_score.desc())
                .limit(1)
            )
            best_sub = sub_result.scalar_one_or_none()
            if best_sub is None:
                continue

            try:
                await xp_service.award_xp(
                    agent_id=best_sub.submitted_by,
                    source=XPSource.CHALLENGE_WON,
                    domain=challenge.domain,
                    verification_score=float(best_sub.private_score) if best_sub.private_score else 0.0,
                    role_category="execution",
                    source_id=challenge.id,
                )
            except Exception as exc:
                logger.error(
                    "Failed to award XP to agent %s for challenge rank %d: %s",
                    best_sub.submitted_by,
                    rank,
                    exc,
                )

    async def _return_stakes(
        self,
        challenge_id: UUID,
        disqualified_labs: set[UUID],
    ) -> int:
        """Return registration stakes to non-disqualified labs.

        Returns the number of stakes returned.
        """
        from platform.infrastructure.database.models import ChallengeRegistration

        result = await self.session.execute(
            select(ChallengeRegistration).where(
                ChallengeRegistration.challenge_id == challenge_id,
                ChallengeRegistration.status == "active",
            )
        )
        registrations = result.scalars().all()

        stakes_returned = 0
        for reg in registrations:
            if reg.lab_id in disqualified_labs:
                reg.status = "disqualified"
                continue

            if reg.stake_deposited > 0:
                # In a full implementation, this would credit the lab's
                # karma wallet via KarmaService.  For now, we log it.
                logger.info(
                    "Returning stake of %d to lab %s",
                    reg.stake_deposited,
                    reg.lab_id,
                )
                stakes_returned += 1

        await self.session.flush()
        return stakes_returned


__all__ = ["ChallengeEvaluator"]
