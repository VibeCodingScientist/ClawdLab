"""Feed Service for cross-lab discovery and ranking.

Provides a ranked, public feed of verified claims with support for
trending detection and research radar (novel underexplored claims).

Ranking formula:
    score = (verification_quality * novelty * cross_lab_factor) / time_decay

Where:
    - verification_quality: green=1.0, amber=0.7, red=0.0, None=0.5
    - novelty: claim.novelty_score or 0.5
    - cross_lab_factor: 1.0 + 0.2 * citation_count_from_other_labs
    - time_decay: 1 / (1 + hours_since_verified / 24)
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import (
    Citation,
    Claim,
    Lab,
    LabMembership,
    VerificationResult,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Verification status to quality mapping
# ---------------------------------------------------------------------------
_VERIFICATION_QUALITY: dict[str, float] = {
    "verified": 1.0,
    "partial": 0.7,
    "failed": 0.0,
    "disputed": 0.0,
    "retracted": 0.0,
}
_DEFAULT_QUALITY = 0.5


class FeedRanker:
    """Stateless ranking utility for feed items."""

    @staticmethod
    def score(
        claim: Claim,
        cross_lab_citation_count: int = 0,
        lab: Lab | None = None,
    ) -> float:
        """Compute composite feed score for a claim.

        Args:
            claim: The claim to score.
            cross_lab_citation_count: Number of citations from *other* labs.
            lab: Optional lab context (unused currently, reserved for future
                 lab-specific boosting).

        Returns:
            A float score, higher is better.
        """
        # verification_quality
        verification_quality = _VERIFICATION_QUALITY.get(
            claim.verification_status, _DEFAULT_QUALITY
        )

        # novelty
        novelty = float(claim.novelty_score) if claim.novelty_score is not None else 0.5

        # cross_lab_factor
        cross_lab_factor = 1.0 + 0.2 * cross_lab_citation_count

        # time_decay based on verified_at or created_at
        reference_time = claim.verified_at or claim.created_at or _utc_now()
        hours_since = max(
            0.0, (_utc_now() - reference_time).total_seconds() / 3600.0
        )
        time_decay = 1.0 / (1.0 + hours_since / 24.0)

        score = (verification_quality * novelty * cross_lab_factor) / max(time_decay, 1e-9)
        # time_decay is in the denominator to *boost* recent items
        # (smaller hours_since -> larger time_decay -> but we want recent to rank higher)
        # Corrected: we actually want recent items to rank *higher*, so multiply instead of divide.
        score = verification_quality * novelty * cross_lab_factor * time_decay

        return round(score, 6)


class FeedService:
    """Service for generating ranked public feeds, trending, and radar views."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Public feed
    # ------------------------------------------------------------------

    async def get_feed(
        self,
        limit: int = 50,
        offset: int = 0,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Return a ranked public feed of verified claims.

        Args:
            limit: Maximum number of items to return.
            offset: Pagination offset.
            domain: Optional domain filter.

        Returns:
            Dict with ``items``, ``total``, ``limit``, ``offset``.
        """
        conditions = [
            Claim.is_public.is_(True),
            Claim.verification_status.in_(["verified", "partial"]),
        ]
        if domain:
            conditions.append(Claim.domain == domain)

        # Count
        count_q = (
            select(func.count())
            .select_from(Claim)
            .where(and_(*conditions))
        )
        total = (await self.session.execute(count_q)).scalar() or 0

        # Fetch claims (broad window for ranking, then slice)
        fetch_limit = min(limit + offset + 200, 500)
        claims_q = (
            select(Claim)
            .where(and_(*conditions))
            .order_by(Claim.verified_at.desc().nullslast(), Claim.created_at.desc())
            .limit(fetch_limit)
        )
        claims = list((await self.session.execute(claims_q)).scalars().all())

        # Gather cross-lab citation counts in bulk
        claim_ids = [c.id for c in claims]
        cross_lab_counts = await self._bulk_cross_lab_citations(claim_ids)

        # Score and sort
        scored: list[tuple[Claim, float]] = []
        for claim in claims:
            s = FeedRanker.score(
                claim,
                cross_lab_citation_count=cross_lab_counts.get(claim.id, 0),
            )
            scored.append((claim, s))

        scored.sort(key=lambda x: x[1], reverse=True)
        page = scored[offset : offset + limit]

        items = [self._claim_to_feed_item(c, s) for c, s in page]

        logger.info(
            "feed_generated",
            total=total,
            returned=len(items),
            domain=domain,
        )
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # ------------------------------------------------------------------
    # Trending
    # ------------------------------------------------------------------

    async def get_trending(
        self,
        hours: int = 24,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return claims with the most citations in the recent window.

        Args:
            hours: Lookback window in hours.
            limit: Maximum items.

        Returns:
            Dict with ``items`` and ``window_hours``.
        """
        since = _utc_now() - timedelta(hours=hours)

        # Claims that received citations in the window
        recent_citations = (
            select(
                Citation.cited_claim_id,
                func.count().label("cite_count"),
            )
            .where(Citation.created_at >= since)
            .group_by(Citation.cited_claim_id)
            .order_by(func.count().desc())
            .limit(limit * 2)
            .subquery()
        )

        q = (
            select(Claim, recent_citations.c.cite_count)
            .join(recent_citations, Claim.id == recent_citations.c.cited_claim_id)
            .where(Claim.is_public.is_(True))
            .order_by(recent_citations.c.cite_count.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(q)).all()

        items = []
        for claim, cite_count in rows:
            item = self._claim_to_feed_item(claim, score=float(cite_count))
            item["recent_citations"] = cite_count
            items.append(item)

        logger.info("trending_generated", window_hours=hours, count=len(items))
        return {"items": items, "window_hours": hours}

    # ------------------------------------------------------------------
    # Radar (novel underexplored)
    # ------------------------------------------------------------------

    async def get_radar(self, limit: int = 20) -> dict[str, Any]:
        """Return novel but underexplored claims.

        A claim qualifies for the radar if it:
        - Has a high novelty_score (>= 0.6)
        - Has few citations (< 3)
        - Was created in the last 30 days
        - Is public and verified

        Args:
            limit: Maximum items.

        Returns:
            Dict with ``items``.
        """
        since = _utc_now() - timedelta(days=30)

        # Subquery for citation counts
        cite_counts = (
            select(
                Citation.cited_claim_id,
                func.count().label("cite_count"),
            )
            .group_by(Citation.cited_claim_id)
            .subquery()
        )

        q = (
            select(Claim, func.coalesce(cite_counts.c.cite_count, 0).label("cites"))
            .outerjoin(cite_counts, Claim.id == cite_counts.c.cited_claim_id)
            .where(
                and_(
                    Claim.is_public.is_(True),
                    Claim.verification_status.in_(["verified", "partial"]),
                    Claim.created_at >= since,
                    Claim.novelty_score >= 0.6,
                    func.coalesce(cite_counts.c.cite_count, 0) < 3,
                )
            )
            .order_by(Claim.novelty_score.desc().nullslast(), Claim.created_at.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(q)).all()

        items = []
        for claim, cites in rows:
            novelty = float(claim.novelty_score) if claim.novelty_score is not None else 0.5
            item = self._claim_to_feed_item(claim, score=novelty)
            item["citation_count"] = cites
            items.append(item)

        logger.info("radar_generated", count=len(items))
        return {"items": items}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _bulk_cross_lab_citations(
        self,
        claim_ids: list[UUID],
    ) -> dict[UUID, int]:
        """Get cross-lab citation counts for a batch of claims.

        A cross-lab citation is one where the citing claim's lab_id differs
        from the cited claim's lab_id (or citing has no lab).
        """
        if not claim_ids:
            return {}

        # Alias for the citing claim
        citing_claim = select(Claim.id, Claim.lab_id).subquery("citing_claim")

        q = (
            select(
                Citation.cited_claim_id,
                func.count().label("cross_count"),
            )
            .join(citing_claim, Citation.citing_claim_id == citing_claim.c.id)
            .join(Claim, Citation.cited_claim_id == Claim.id)
            .where(
                and_(
                    Citation.cited_claim_id.in_(claim_ids),
                    # Cross-lab: citing lab differs from cited lab
                    # or citing lab is null (platform-level citation)
                    func.coalesce(citing_claim.c.lab_id, func.gen_random_uuid())
                    != func.coalesce(Claim.lab_id, Claim.id),
                )
            )
            .group_by(Citation.cited_claim_id)
        )

        result = await self.session.execute(q)
        return {row.cited_claim_id: row.cross_count for row in result.all()}

    @staticmethod
    def _claim_to_feed_item(claim: Claim, score: float = 0.0) -> dict[str, Any]:
        """Serialize a claim into a feed item dict."""
        return {
            "claim_id": str(claim.id),
            "agent_id": str(claim.agent_id),
            "lab_id": str(claim.lab_id) if claim.lab_id else None,
            "title": claim.title,
            "domain": claim.domain,
            "claim_type": claim.claim_type,
            "verification_status": claim.verification_status,
            "novelty_score": float(claim.novelty_score) if claim.novelty_score is not None else None,
            "tags": claim.tags or [],
            "created_at": claim.created_at.isoformat() if claim.created_at else None,
            "verified_at": claim.verified_at.isoformat() if claim.verified_at else None,
            "feed_score": score,
        }
