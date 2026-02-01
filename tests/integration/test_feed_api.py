"""Integration tests for feed API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_mock_claim(**overrides) -> MagicMock:
    """Build a minimal mock Claim for feed serialization."""
    claim = MagicMock()
    claim.id = overrides.get("id", uuid4())
    claim.agent_id = overrides.get("agent_id", uuid4())
    claim.lab_id = overrides.get("lab_id", None)
    claim.title = overrides.get("title", "Test Claim")
    claim.domain = overrides.get("domain", "ml_ai")
    claim.claim_type = overrides.get("claim_type", "empirical")
    claim.verification_status = overrides.get("verification_status", "verified")
    claim.novelty_score = overrides.get("novelty_score", 0.8)
    claim.tags = overrides.get("tags", [])
    claim.is_public = overrides.get("is_public", True)
    claim.verified_at = overrides.get("verified_at", _utc_now())
    claim.created_at = overrides.get("created_at", _utc_now())
    return claim


class TestFeedAPIEndpoints:
    """Integration tests for the feed router endpoints."""

    @pytest.mark.asyncio
    async def test_get_feed_returns_feed_items(self):
        """GET /feed should return a dict with items list."""
        from platform.feed.api import get_feed

        mock_session = AsyncMock()

        # Mock FeedService.get_feed
        feed_response = {
            "items": [
                {
                    "claim_id": str(uuid4()),
                    "agent_id": str(uuid4()),
                    "lab_id": None,
                    "title": "Test",
                    "domain": "ml_ai",
                    "claim_type": "empirical",
                    "verification_status": "verified",
                    "novelty_score": 0.8,
                    "tags": [],
                    "created_at": _utc_now().isoformat(),
                    "verified_at": _utc_now().isoformat(),
                    "feed_score": 0.72,
                }
            ],
            "total": 1,
            "limit": 50,
            "offset": 0,
        }

        with patch("platform.feed.api.FeedService") as MockFeedService:
            mock_svc = MagicMock()
            mock_svc.get_feed = AsyncMock(return_value=feed_response)
            MockFeedService.return_value = mock_svc

            result = await get_feed(domain=None, offset=0, limit=50, db=mock_session)

        assert "items" in result
        assert "total" in result
        assert len(result["items"]) == 1

    @pytest.mark.asyncio
    async def test_get_trending_returns_trending(self):
        """GET /feed/trending should return trending items."""
        from platform.feed.api import get_trending

        mock_session = AsyncMock()

        trending_response = {
            "items": [
                {
                    "claim_id": str(uuid4()),
                    "agent_id": str(uuid4()),
                    "lab_id": None,
                    "title": "Trending Claim",
                    "domain": "ml_ai",
                    "claim_type": "benchmark",
                    "verification_status": "verified",
                    "novelty_score": 0.9,
                    "tags": [],
                    "created_at": _utc_now().isoformat(),
                    "verified_at": _utc_now().isoformat(),
                    "feed_score": 15.0,
                    "recent_citations": 15,
                }
            ],
            "window_hours": 24,
        }

        with patch("platform.feed.api.FeedService") as MockFeedService:
            mock_svc = MagicMock()
            mock_svc.get_trending = AsyncMock(return_value=trending_response)
            MockFeedService.return_value = mock_svc

            result = await get_trending(hours=24, limit=20, db=mock_session)

        assert "items" in result
        assert "window_hours" in result
        assert result["window_hours"] == 24

    @pytest.mark.asyncio
    async def test_get_radar_returns_radar_items(self):
        """GET /feed/radar should return novel underexplored items."""
        from platform.feed.api import get_radar

        mock_session = AsyncMock()

        radar_response = {
            "items": [
                {
                    "claim_id": str(uuid4()),
                    "agent_id": str(uuid4()),
                    "lab_id": None,
                    "title": "Novel Claim",
                    "domain": "mathematics",
                    "claim_type": "proof",
                    "verification_status": "verified",
                    "novelty_score": 0.95,
                    "tags": [],
                    "created_at": _utc_now().isoformat(),
                    "verified_at": _utc_now().isoformat(),
                    "feed_score": 0.95,
                    "citation_count": 1,
                }
            ],
        }

        with patch("platform.feed.api.FeedService") as MockFeedService:
            mock_svc = MagicMock()
            mock_svc.get_radar = AsyncMock(return_value=radar_response)
            MockFeedService.return_value = mock_svc

            result = await get_radar(limit=20, db=mock_session)

        assert "items" in result
        assert len(result["items"]) == 1

    @pytest.mark.asyncio
    async def test_get_radar_clusters_returns_clusters(self):
        """GET /feed/radar/clusters should return a list of cluster dicts."""
        from platform.feed.api import get_research_clusters

        mock_session = AsyncMock()

        clusters_response = [
            {
                "cluster_id": 0,
                "lab_ids": [str(uuid4()), str(uuid4())],
                "lab_slugs": ["lab-a", "lab-b"],
                "lab_count": 2,
                "edge_count": 5,
            }
        ]

        with patch("platform.feed.api.CitationGraphService") as MockCGS:
            mock_svc = MagicMock()
            mock_svc.detect_clusters = AsyncMock(return_value=clusters_response)
            MockCGS.return_value = mock_svc

            result = await get_research_clusters(db=mock_session)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["cluster_id"] == 0
        assert result[0]["lab_count"] == 2

    @pytest.mark.asyncio
    async def test_get_claim_citations_returns_metrics(self):
        """GET /feed/claims/{id}/citations should return impact metrics."""
        from platform.feed.api import get_claim_citations

        mock_session = AsyncMock()
        claim_id = uuid4()

        metrics_response = {
            "claim_id": str(claim_id),
            "direct_citations": 10,
            "indirect_citations": 4,
            "cross_lab_citations": 3,
            "total_impact": 14,
        }

        with patch("platform.feed.api.CitationGraphService") as MockCGS:
            mock_svc = MagicMock()
            mock_svc.get_impact_metrics = AsyncMock(return_value=metrics_response)
            MockCGS.return_value = mock_svc

            result = await get_claim_citations(claim_id=claim_id, db=mock_session)

        assert result["claim_id"] == str(claim_id)
        assert result["direct_citations"] == 10
        assert result["total_impact"] == 14

    @pytest.mark.asyncio
    async def test_get_lab_impact_returns_impact(self):
        """GET /feed/labs/{slug}/impact should return lab-level impact."""
        from platform.feed.api import get_lab_impact

        mock_session = AsyncMock()

        impact_response = {
            "lab_slug": "deep-learning-lab",
            "lab_id": str(uuid4()),
            "total_claims": 42,
            "verified_claims": 35,
            "total_citations_received": 120,
            "cross_lab_citations_received": 30,
            "total_citations_given": 80,
            "h_index": 7,
        }

        with patch("platform.feed.api.CitationGraphService") as MockCGS:
            mock_svc = MagicMock()
            mock_svc.get_lab_impact = AsyncMock(return_value=impact_response)
            MockCGS.return_value = mock_svc

            result = await get_lab_impact(slug="deep-learning-lab", db=mock_session)

        assert result["lab_slug"] == "deep-learning-lab"
        assert result["total_claims"] == 42
        assert result["h_index"] == 7
