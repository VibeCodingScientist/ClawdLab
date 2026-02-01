"""AntiGamingService — submission integrity and anti-collusion checks."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

# Thresholds
CODE_SIMILARITY_THRESHOLD = 0.85
BEHAVIORAL_CORRELATION_THRESHOLD = 0.90


class AntiGamingService:
    """Detects collusion, plagiarism, and rate-limit violations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def check_submission(self, submission_id: UUID) -> dict:
        """Run all anti-gaming checks on a single submission.

        Returns:
            {
                "passed": bool,
                "flags": list[str],
                "similarity_score": float,
            }
        """
        from platform.infrastructure.database.models import ChallengeSubmission

        result = await self.session.execute(
            select(ChallengeSubmission).where(
                ChallengeSubmission.id == submission_id
            )
        )
        submission = result.scalar_one()

        flags: list[str] = []
        max_similarity = 0.0

        # 1. Code similarity against other submissions in the same challenge
        similarity_score = await self._check_code_similarity(submission)
        if similarity_score > CODE_SIMILARITY_THRESHOLD:
            flags.append(
                f"code_similarity_high ({similarity_score:.2f} > {CODE_SIMILARITY_THRESHOLD})"
            )
        max_similarity = max(max_similarity, similarity_score)

        # 2. Behavioral correlation
        correlation = await self.check_behavioral_correlation(
            submission.challenge_id,
            submission.lab_id,
        )
        if correlation["correlation_score"] > BEHAVIORAL_CORRELATION_THRESHOLD:
            flags.append(
                f"behavioral_correlation ({correlation['correlation_score']:.2f})"
            )

        # 3. Rate violations
        rate_flags = await self.check_rate_violations(
            submission.challenge_id,
            submission.lab_id,
        )
        flags.extend(rate_flags)

        passed = len(flags) == 0

        if not passed:
            logger.warning(
                "Anti-gaming flags for submission %s: %s",
                submission_id,
                flags,
            )

        return {
            "passed": passed,
            "flags": flags,
            "similarity_score": max_similarity,
        }

    async def _check_code_similarity(
        self,
        submission: object,
    ) -> float:
        """Compare submission code against other labs' submissions.

        Returns the highest Jaccard similarity found.
        """
        from platform.infrastructure.database.models import ChallengeSubmission

        if not getattr(submission, "code_ref", None):
            return 0.0

        # Get other labs' submissions for the same challenge
        others_result = await self.session.execute(
            select(ChallengeSubmission).where(
                ChallengeSubmission.challenge_id == submission.challenge_id,
                ChallengeSubmission.lab_id != submission.lab_id,
                ChallengeSubmission.code_ref.is_not(None),
            )
        )
        other_subs = others_result.scalars().all()

        if not other_subs:
            return 0.0

        max_sim = 0.0
        source_code = submission.code_ref or ""

        for other in other_subs:
            other_code = other.code_ref or ""
            if not other_code:
                continue
            sim = self.compute_code_similarity(source_code, other_code)
            max_sim = max(max_sim, sim)

        return max_sim

    @staticmethod
    def compute_code_similarity(code_a: str, code_b: str) -> float:
        """Compute AST-based Jaccard similarity between two code snippets.

        Parses both snippets with ``ast.parse``, extracts a multiset of
        AST node type names, and returns the Jaccard index (intersection /
        union).  Falls back to token-level comparison if either snippet
        fails to parse.

        Returns:
            float between 0.0 (completely different) and 1.0 (identical structure).
        """
        def _extract_node_types(source: str) -> list[str]:
            try:
                tree = ast.parse(source)
            except SyntaxError:
                # Fallback: split on whitespace as pseudo-tokens
                return source.split()
            return [type(node).__name__ for node in ast.walk(tree)]

        types_a = _extract_node_types(code_a)
        types_b = _extract_node_types(code_b)

        if not types_a and not types_b:
            return 1.0
        if not types_a or not types_b:
            return 0.0

        set_a = set(enumerate(types_a))
        set_b = set(enumerate(types_b))

        # Use multiset (bag) approach for more accurate similarity
        bag_a: dict[str, int] = {}
        for t in types_a:
            bag_a[t] = bag_a.get(t, 0) + 1
        bag_b: dict[str, int] = {}
        for t in types_b:
            bag_b[t] = bag_b.get(t, 0) + 1

        all_keys = set(bag_a) | set(bag_b)
        intersection = sum(min(bag_a.get(k, 0), bag_b.get(k, 0)) for k in all_keys)
        union = sum(max(bag_a.get(k, 0), bag_b.get(k, 0)) for k in all_keys)

        if union == 0:
            return 1.0

        return intersection / union

    async def check_behavioral_correlation(
        self,
        challenge_id: UUID,
        lab_id: UUID,
    ) -> dict:
        """Check if a lab's submission scores are suspiciously correlated with another lab's.

        Compares the sequence of public_score values between this lab and
        every other lab in the challenge.  A high Pearson-like correlation
        suggests collusion or shared evaluation leaks.

        Returns:
            {
                "correlated_with": UUID | None,
                "correlation_score": float,
            }
        """
        from platform.infrastructure.database.models import ChallengeSubmission

        # Get this lab's scored submissions
        own_result = await self.session.execute(
            select(ChallengeSubmission.public_score)
            .where(
                ChallengeSubmission.challenge_id == challenge_id,
                ChallengeSubmission.lab_id == lab_id,
                ChallengeSubmission.status == "scored",
            )
            .order_by(ChallengeSubmission.sequence_number)
        )
        own_scores = [float(r[0]) for r in own_result.all() if r[0] is not None]

        if len(own_scores) < 3:
            return {"correlated_with": None, "correlation_score": 0.0}

        # Get distinct other labs
        labs_result = await self.session.execute(
            select(ChallengeSubmission.lab_id)
            .where(
                ChallengeSubmission.challenge_id == challenge_id,
                ChallengeSubmission.lab_id != lab_id,
                ChallengeSubmission.status == "scored",
            )
            .distinct()
        )
        other_labs = [r[0] for r in labs_result.all()]

        max_corr = 0.0
        correlated_lab: UUID | None = None

        for other_lab_id in other_labs:
            other_result = await self.session.execute(
                select(ChallengeSubmission.public_score)
                .where(
                    ChallengeSubmission.challenge_id == challenge_id,
                    ChallengeSubmission.lab_id == other_lab_id,
                    ChallengeSubmission.status == "scored",
                )
                .order_by(ChallengeSubmission.sequence_number)
            )
            other_scores = [float(r[0]) for r in other_result.all() if r[0] is not None]

            if len(other_scores) < 3:
                continue

            corr = self._pearson(own_scores, other_scores)
            if corr > max_corr:
                max_corr = corr
                correlated_lab = other_lab_id

        return {
            "correlated_with": correlated_lab,
            "correlation_score": max_corr,
        }

    async def check_rate_violations(
        self,
        challenge_id: UUID,
        lab_id: UUID,
    ) -> list[str]:
        """Check for rate limit violations (double-check beyond service.py enforcement).

        Returns a list of flag descriptions (empty if clean).
        """
        from platform.infrastructure.database.models import (
            ChallengeSubmission,
            ResearchChallenge,
        )

        ch_result = await self.session.execute(
            select(ResearchChallenge).where(ResearchChallenge.id == challenge_id)
        )
        challenge = ch_result.scalar_one()

        flags: list[str] = []

        # Check submissions per 24-hour window
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        count_result = await self.session.execute(
            select(func.count()).where(
                ChallengeSubmission.challenge_id == challenge_id,
                ChallengeSubmission.lab_id == lab_id,
                ChallengeSubmission.created_at >= cutoff,
            )
        )
        recent_count = count_result.scalar() or 0

        if recent_count > challenge.max_submissions_per_day:
            flags.append(
                f"rate_exceeded_24h ({recent_count} > {challenge.max_submissions_per_day})"
            )

        # Check rapid-fire submissions (more than 5 in 10 minutes)
        rapid_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        rapid_result = await self.session.execute(
            select(func.count()).where(
                ChallengeSubmission.challenge_id == challenge_id,
                ChallengeSubmission.lab_id == lab_id,
                ChallengeSubmission.created_at >= rapid_cutoff,
            )
        )
        rapid_count = rapid_result.scalar() or 0

        if rapid_count > 5:
            flags.append(f"rapid_fire_submissions ({rapid_count} in 10min)")

        return flags

    @staticmethod
    def _pearson(x: list[float], y: list[float]) -> float:
        """Compute Pearson correlation between two equal-length score sequences.

        If lengths differ, truncate to the shorter length.
        Returns 0.0 on degenerate inputs.
        """
        n = min(len(x), len(y))
        if n < 2:
            return 0.0

        x = x[:n]
        y = y[:n]

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        den_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
        den_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5

        if den_x == 0 or den_y == 0:
            return 0.0

        return abs(num / (den_x * den_y))


__all__ = ["AntiGamingService"]
