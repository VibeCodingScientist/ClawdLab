"""Tests for ConsistencyChecker."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestConsistencyChecker:
    """Tests for ConsistencyChecker.check_consistency."""

    def _make_mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession for ConsistencyChecker."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_returns_consistency_result_dataclass(self):
        """check_consistency should return a ConsistencyResult instance."""
        from platform.services.verification_orchestrator.consistency import (
            ConsistencyChecker,
            ConsistencyResult,
        )

        session = self._make_mock_session()

        # Patch the CitationRepository and DB queries to return no related claims
        with patch(
            "platform.services.verification_orchestrator.consistency.CitationRepository"
        ) as MockCitRepo:
            mock_cite_repo = MagicMock()
            mock_cite_repo.get_citations_for = AsyncMock(return_value=[])
            mock_cite_repo.get_cited_by = AsyncMock(return_value=[])
            MockCitRepo.return_value = mock_cite_repo

            # Mock the DB execute call for tag-based query to return empty
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            session.execute.return_value = mock_result

            checker = ConsistencyChecker(session)
            result = await checker.check_consistency(
                claim_id=str(uuid4()),
                domain="mathematics",
                payload={"conclusion": "true"},
            )

            assert isinstance(result, ConsistencyResult)

    @pytest.mark.asyncio
    async def test_consistent_result_when_no_contradictions(self):
        """When no related claims exist the result should be consistent
        with confidence 1.0."""
        from platform.services.verification_orchestrator.consistency import (
            ConsistencyChecker,
        )

        session = self._make_mock_session()

        with patch(
            "platform.services.verification_orchestrator.consistency.CitationRepository"
        ) as MockCitRepo:
            mock_cite_repo = MagicMock()
            mock_cite_repo.get_citations_for = AsyncMock(return_value=[])
            mock_cite_repo.get_cited_by = AsyncMock(return_value=[])
            MockCitRepo.return_value = mock_cite_repo

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            session.execute.return_value = mock_result

            checker = ConsistencyChecker(session)
            result = await checker.check_consistency(
                claim_id=str(uuid4()),
                domain="mathematics",
                payload={"conclusion": "convergent"},
            )

            assert result.consistent is True
            assert result.contradictions == []
            assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_contradictions_detected(self):
        """When related claims contain contradictory conclusions the
        result should report contradictions."""
        from platform.services.verification_orchestrator.consistency import (
            ConsistencyChecker,
        )

        claim_id = str(uuid4())
        related_claim_id = str(uuid4())

        session = self._make_mock_session()

        # Build a mock related claim object for the tag query
        mock_related = MagicMock()
        mock_related.id = uuid4()
        mock_related.title = "Contradictory claim"
        mock_related.domain = "mathematics"
        mock_related.claim_type = "proof"
        mock_related.verification_status = "verified"
        mock_related.content = {"conclusion": "divergent"}
        mock_related.tags = ["analysis"]

        with patch(
            "platform.services.verification_orchestrator.consistency.CitationRepository"
        ) as MockCitRepo:
            mock_cite_repo = MagicMock()
            mock_cite_repo.get_citations_for = AsyncMock(return_value=[])
            mock_cite_repo.get_cited_by = AsyncMock(return_value=[])
            MockCitRepo.return_value = mock_cite_repo

            # First execute call: tag query returns our contradictory claim
            # Second execute call: fetch full rows
            tag_result = MagicMock()
            tag_result.scalars.return_value.all.return_value = [mock_related]

            full_result = MagicMock()
            full_result.scalars.return_value.all.return_value = [mock_related]

            session.execute.side_effect = [tag_result, full_result]

            checker = ConsistencyChecker(session)
            result = await checker.check_consistency(
                claim_id=claim_id,
                domain="mathematics",
                payload={"conclusion": "convergent", "tags": ["analysis"]},
            )

            assert len(result.contradictions) > 0
            assert result.contradictions[0]["relationship"] == "contradictory_conclusion"

    @pytest.mark.asyncio
    async def test_confidence_score_range(self):
        """Confidence score should be between 0.0 and 1.0."""
        from platform.services.verification_orchestrator.consistency import (
            ConsistencyChecker,
        )

        session = self._make_mock_session()

        with patch(
            "platform.services.verification_orchestrator.consistency.CitationRepository"
        ) as MockCitRepo:
            mock_cite_repo = MagicMock()
            mock_cite_repo.get_citations_for = AsyncMock(return_value=[])
            mock_cite_repo.get_cited_by = AsyncMock(return_value=[])
            MockCitRepo.return_value = mock_cite_repo

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            session.execute.return_value = mock_result

            checker = ConsistencyChecker(session)
            result = await checker.check_consistency(
                claim_id=str(uuid4()),
                domain="ml_ai",
                payload={"dataset": "imagenet", "metrics": {"accuracy": 0.99}},
            )

            assert 0.0 <= result.confidence <= 1.0
