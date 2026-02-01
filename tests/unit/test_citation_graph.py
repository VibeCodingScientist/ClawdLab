"""Tests for CitationGraphService."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestCitationGraphService:
    """Tests for CitationGraphService methods."""

    def _make_session(self) -> AsyncMock:
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_record_citation(self):
        """record_citation should create and return a citation dict."""
        from platform.feed.citation_graph import CitationGraphService

        session = self._make_session()
        citing_id = uuid4()
        cited_id = uuid4()

        # Mock claim existence checks -- two calls, both should return a scalar
        exists_result_1 = MagicMock()
        exists_result_1.scalar_one_or_none.return_value = citing_id

        exists_result_2 = MagicMock()
        exists_result_2.scalar_one_or_none.return_value = cited_id

        session.execute.side_effect = [exists_result_1, exists_result_2]

        mock_citation = MagicMock()
        mock_citation.id = uuid4()
        mock_citation.citing_claim_id = citing_id
        mock_citation.cited_claim_id = cited_id
        mock_citation.citing_lab_id = None
        mock_citation.context = "supports"
        mock_citation.created_at = datetime.now(timezone.utc)

        with patch(
            "platform.feed.citation_graph.CitationRepository"
        ) as MockCitRepo, patch(
            "platform.feed.citation_graph.LabRepository"
        ):
            mock_repo = MagicMock()
            mock_repo.create = AsyncMock(return_value=mock_citation)
            MockCitRepo.return_value = mock_repo

            service = CitationGraphService(session)
            result = await service.record_citation(
                citing_claim_id=str(citing_id),
                cited_claim_id=str(cited_id),
                context="supports",
            )

            assert result["citing_claim_id"] == str(citing_id)
            assert result["cited_claim_id"] == str(cited_id)
            assert "id" in result

    @pytest.mark.asyncio
    async def test_record_citation_self_reference_raises(self):
        """A claim should not be able to cite itself."""
        from platform.feed.citation_graph import CitationGraphService

        session = self._make_session()
        same_id = uuid4()

        with patch(
            "platform.feed.citation_graph.CitationRepository"
        ), patch(
            "platform.feed.citation_graph.LabRepository"
        ):
            service = CitationGraphService(session)
            with pytest.raises(ValueError, match="cannot cite itself"):
                await service.record_citation(
                    citing_claim_id=str(same_id),
                    cited_claim_id=str(same_id),
                )

    @pytest.mark.asyncio
    async def test_get_impact_metrics(self):
        """get_impact_metrics should return a dict with expected keys."""
        from platform.feed.citation_graph import CitationGraphService

        session = self._make_session()
        claim_id = uuid4()

        # Mock: direct count, indirect count, cited claim lab, cross-lab count
        direct_result = MagicMock()
        direct_result.scalar.return_value = 5

        indirect_result = MagicMock()
        indirect_result.scalar.return_value = 3

        lab_result = MagicMock()
        lab_result.scalar.return_value = uuid4()  # cited claim has a lab

        cross_lab_result = MagicMock()
        cross_lab_result.scalar.return_value = 2

        session.execute.side_effect = [
            direct_result,
            indirect_result,
            lab_result,
            cross_lab_result,
        ]

        with patch(
            "platform.feed.citation_graph.CitationRepository"
        ), patch(
            "platform.feed.citation_graph.LabRepository"
        ):
            service = CitationGraphService(session)
            metrics = await service.get_impact_metrics(str(claim_id))

        assert metrics["claim_id"] == str(claim_id)
        assert metrics["direct_citations"] == 5
        assert metrics["indirect_citations"] == 3
        assert metrics["cross_lab_citations"] == 2
        assert metrics["total_impact"] == 8

    @pytest.mark.asyncio
    async def test_direct_citation_count(self):
        """direct_citations should reflect the count from the query."""
        from platform.feed.citation_graph import CitationGraphService

        session = self._make_session()
        claim_id = uuid4()

        direct_result = MagicMock()
        direct_result.scalar.return_value = 10

        indirect_result = MagicMock()
        indirect_result.scalar.return_value = 0

        lab_result = MagicMock()
        lab_result.scalar.return_value = None  # no lab

        cross_lab_result = MagicMock()
        cross_lab_result.scalar.return_value = 0

        session.execute.side_effect = [
            direct_result,
            indirect_result,
            lab_result,
            cross_lab_result,
        ]

        with patch(
            "platform.feed.citation_graph.CitationRepository"
        ), patch(
            "platform.feed.citation_graph.LabRepository"
        ):
            service = CitationGraphService(session)
            metrics = await service.get_impact_metrics(str(claim_id))

        assert metrics["direct_citations"] == 10

    @pytest.mark.asyncio
    async def test_cross_lab_citations(self):
        """cross_lab_citations should be counted when cited claim has a lab."""
        from platform.feed.citation_graph import CitationGraphService

        session = self._make_session()
        claim_id = uuid4()

        direct_result = MagicMock()
        direct_result.scalar.return_value = 7

        indirect_result = MagicMock()
        indirect_result.scalar.return_value = 2

        lab_result = MagicMock()
        lab_result.scalar.return_value = uuid4()  # has lab

        cross_lab_result = MagicMock()
        cross_lab_result.scalar.return_value = 4

        session.execute.side_effect = [
            direct_result,
            indirect_result,
            lab_result,
            cross_lab_result,
        ]

        with patch(
            "platform.feed.citation_graph.CitationRepository"
        ), patch(
            "platform.feed.citation_graph.LabRepository"
        ):
            service = CitationGraphService(session)
            metrics = await service.get_impact_metrics(str(claim_id))

        assert metrics["cross_lab_citations"] == 4

    @pytest.mark.asyncio
    async def test_cluster_detection_returns_list(self):
        """detect_clusters should return a list (possibly empty)."""
        from platform.feed.citation_graph import CitationGraphService

        session = self._make_session()

        # No edges found
        edge_result = MagicMock()
        edge_result.all.return_value = []
        session.execute.return_value = edge_result

        with patch(
            "platform.feed.citation_graph.CitationRepository"
        ), patch(
            "platform.feed.citation_graph.LabRepository"
        ):
            service = CitationGraphService(session)
            clusters = await service.detect_clusters()

        assert isinstance(clusters, list)

    @pytest.mark.asyncio
    async def test_get_lab_impact(self):
        """get_lab_impact should return lab-level metrics dict."""
        from platform.feed.citation_graph import CitationGraphService

        session = self._make_session()
        lab_id = uuid4()

        # Mock lab_repo.get_by_slug to return a lab
        mock_lab = MagicMock()
        mock_lab.id = lab_id
        mock_lab.slug = "test-lab"

        # Mock the six sequential execute calls
        total_claims_result = MagicMock()
        total_claims_result.scalar.return_value = 20

        verified_result = MagicMock()
        verified_result.scalar.return_value = 15

        received_result = MagicMock()
        received_result.scalar.return_value = 50

        cross_lab_received = MagicMock()
        cross_lab_received.scalar.return_value = 12

        given_result = MagicMock()
        given_result.scalar.return_value = 30

        # Per-claim citation rows for h-index
        hindex_row1 = MagicMock()
        hindex_row1.cite_count = 10
        hindex_row2 = MagicMock()
        hindex_row2.cite_count = 5
        hindex_row3 = MagicMock()
        hindex_row3.cite_count = 3
        per_claim_result = MagicMock()
        per_claim_result.all.return_value = [hindex_row1, hindex_row2, hindex_row3]

        session.execute.side_effect = [
            total_claims_result,
            verified_result,
            received_result,
            cross_lab_received,
            given_result,
            per_claim_result,
        ]

        with patch(
            "platform.feed.citation_graph.CitationRepository"
        ), patch(
            "platform.feed.citation_graph.LabRepository"
        ) as MockLabRepo:
            mock_lab_repo = MagicMock()
            mock_lab_repo.get_by_slug = AsyncMock(return_value=mock_lab)
            MockLabRepo.return_value = mock_lab_repo

            service = CitationGraphService(session)
            impact = await service.get_lab_impact("test-lab")

        assert impact["lab_slug"] == "test-lab"
        assert impact["total_claims"] == 20
        assert impact["verified_claims"] == 15
        assert impact["total_citations_received"] == 50
        assert impact["cross_lab_citations_received"] == 12
        assert impact["total_citations_given"] == 30
        assert impact["h_index"] == 3  # h=3: 10>=1, 5>=2, 3>=3
