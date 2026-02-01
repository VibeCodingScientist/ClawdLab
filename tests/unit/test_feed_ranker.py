"""Tests for FeedRanker and FeedService."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_claim(
    verification_status: str = "verified",
    novelty_score: float | None = 0.8,
    verified_at: datetime | None = None,
    created_at: datetime | None = None,
    is_public: bool = True,
    lab_id=None,
    agent_id=None,
    claim_type: str = "empirical",
    domain: str = "ml_ai",
    title: str = "Test Claim",
    tags: list | None = None,
) -> MagicMock:
    """Build a MagicMock that behaves like a Claim ORM object."""
    claim = MagicMock()
    claim.id = uuid4()
    claim.agent_id = agent_id or uuid4()
    claim.lab_id = lab_id
    claim.title = title
    claim.domain = domain
    claim.claim_type = claim_type
    claim.verification_status = verification_status
    claim.novelty_score = novelty_score
    claim.tags = tags or []
    claim.is_public = is_public
    claim.verified_at = verified_at or _utc_now()
    claim.created_at = created_at or _utc_now()
    return claim


class TestFeedRankerScore:
    """Tests for FeedRanker.score static method."""

    def test_score_with_green_badge(self):
        """A verified claim with high novelty should have a positive score."""
        from platform.feed.service import FeedRanker

        claim = _make_claim(
            verification_status="verified",
            novelty_score=0.9,
            verified_at=_utc_now(),
        )

        score = FeedRanker.score(claim, cross_lab_citation_count=0)
        assert score > 0.0

    def test_score_with_amber_badge(self):
        """A partially verified claim should score lower than a verified one."""
        from platform.feed.service import FeedRanker

        verified_claim = _make_claim(
            verification_status="verified",
            novelty_score=0.9,
            verified_at=_utc_now(),
        )
        partial_claim = _make_claim(
            verification_status="partial",
            novelty_score=0.9,
            verified_at=_utc_now(),
        )

        verified_score = FeedRanker.score(verified_claim, cross_lab_citation_count=0)
        partial_score = FeedRanker.score(partial_claim, cross_lab_citation_count=0)
        assert verified_score > partial_score

    def test_score_with_red_badge_returns_zero(self):
        """A failed/disputed claim should have a score of 0."""
        from platform.feed.service import FeedRanker

        claim = _make_claim(
            verification_status="failed",
            novelty_score=0.9,
            verified_at=_utc_now(),
        )

        score = FeedRanker.score(claim, cross_lab_citation_count=0)
        assert score == 0.0

    def test_time_decay_reduces_score_for_older_claims(self):
        """Older claims should score lower due to time decay."""
        from platform.feed.service import FeedRanker

        recent_claim = _make_claim(
            verification_status="verified",
            novelty_score=0.8,
            verified_at=_utc_now(),
        )
        old_claim = _make_claim(
            verification_status="verified",
            novelty_score=0.8,
            verified_at=_utc_now() - timedelta(days=7),
        )

        recent_score = FeedRanker.score(recent_claim, cross_lab_citation_count=0)
        old_score = FeedRanker.score(old_claim, cross_lab_citation_count=0)
        assert recent_score > old_score

    def test_cross_lab_factor_boosts_score(self):
        """Claims with cross-lab citations should score higher."""
        from platform.feed.service import FeedRanker

        claim = _make_claim(
            verification_status="verified",
            novelty_score=0.8,
            verified_at=_utc_now(),
        )

        base_score = FeedRanker.score(claim, cross_lab_citation_count=0)
        boosted_score = FeedRanker.score(claim, cross_lab_citation_count=5)
        assert boosted_score > base_score


class TestFeedService:
    """Tests for FeedService methods using mocked sessions."""

    @pytest.mark.asyncio
    async def test_feed_returns_ranked_items(self):
        """get_feed should return a dict with items, total, limit, offset."""
        from platform.feed.service import FeedService

        session = AsyncMock()

        # Mock count query
        count_result = MagicMock()
        count_result.scalar.return_value = 2

        # Mock claims query
        claim1 = _make_claim(verification_status="verified", novelty_score=0.9)
        claim2 = _make_claim(verification_status="verified", novelty_score=0.5)

        claims_result = MagicMock()
        claims_result.scalars.return_value.all.return_value = [claim1, claim2]

        # Mock cross-lab citations bulk query
        cross_lab_result = MagicMock()
        cross_lab_result.all.return_value = []

        session.execute.side_effect = [count_result, claims_result, cross_lab_result]

        service = FeedService(session)
        feed = await service.get_feed(limit=10, offset=0)

        assert "items" in feed
        assert "total" in feed
        assert "limit" in feed
        assert "offset" in feed
        assert isinstance(feed["items"], list)

    @pytest.mark.asyncio
    async def test_trending_returns_recent_high_citation_claims(self):
        """get_trending should return items with recent_citations field."""
        from platform.feed.service import FeedService

        session = AsyncMock()

        claim = _make_claim(verification_status="verified", novelty_score=0.9)
        row = (claim, 15)  # 15 recent citations

        query_result = MagicMock()
        query_result.all.return_value = [row]
        session.execute.return_value = query_result

        service = FeedService(session)
        trending = await service.get_trending(hours=24, limit=10)

        assert "items" in trending
        assert "window_hours" in trending
        assert trending["window_hours"] == 24

    @pytest.mark.asyncio
    async def test_radar_returns_novel_underexplored_claims(self):
        """get_radar should return items with citation_count field."""
        from platform.feed.service import FeedService

        session = AsyncMock()

        claim = _make_claim(
            verification_status="verified",
            novelty_score=0.95,
            created_at=_utc_now(),
        )
        row = (claim, 1)  # 1 citation (underexplored)

        query_result = MagicMock()
        query_result.all.return_value = [row]
        session.execute.return_value = query_result

        service = FeedService(session)
        radar = await service.get_radar(limit=10)

        assert "items" in radar
        assert isinstance(radar["items"], list)
