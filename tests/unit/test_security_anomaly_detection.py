"""Tests for security anomaly detection in SecurityEventRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from platform.security.security_event_repository import SecurityEventRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> SecurityEventRepository:
    """Create a SecurityEventRepository with a mock session."""
    return SecurityEventRepository(mock_session)


def _make_scalar_result(value):
    """Create a mock execute result that returns a scalar."""
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _make_all_result(rows):
    """Create a mock execute result that returns .all() rows."""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows
    result.scalars.return_value = scalars_mock
    return result


class TestGetEventsByAgent:
    """Tests for SecurityEventRepository.get_events_by_agent."""

    @pytest.mark.asyncio
    async def test_get_events_by_agent_returns_events(self, repo, mock_session):
        """get_events_by_agent should return a list of security events for the agent."""
        agent_id = uuid4()
        mock_event = MagicMock()
        mock_event.event_type = "canary_leak"
        mock_event.severity = "critical"
        mock_event.agent_id = agent_id

        mock_session.execute.return_value = _make_all_result([mock_event])

        with patch("platform.security.security_event_repository.logger"):
            events = await repo.get_events_by_agent(agent_id)

        assert len(events) == 1
        assert events[0].event_type == "canary_leak"

    @pytest.mark.asyncio
    async def test_get_events_by_agent_with_since_filter(self, repo, mock_session):
        """get_events_by_agent should accept a since parameter to filter by time."""
        agent_id = uuid4()
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)

        mock_session.execute.return_value = _make_all_result([])

        with patch("platform.security.security_event_repository.logger"):
            events = await repo.get_events_by_agent(agent_id, since=since)

        assert events == []
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_events_by_agent_empty(self, repo, mock_session):
        """get_events_by_agent should return an empty list when no events exist."""
        agent_id = uuid4()
        mock_session.execute.return_value = _make_all_result([])

        with patch("platform.security.security_event_repository.logger"):
            events = await repo.get_events_by_agent(agent_id)

        assert events == []


class TestDetectAnomalies:
    """Tests for SecurityEventRepository.detect_anomalies."""

    @pytest.mark.asyncio
    async def test_detect_anomalies_returns_anomaly_report(self, repo, mock_session):
        """detect_anomalies should return a dict with anomaly flags and risk_score."""
        agent_id = uuid4()

        # Mock all the DB queries in the order they are called:
        # 1. submission_count (>50 triggers anomaly)
        # 2. domain_count (>=3 triggers anomaly)
        # 3. vote_count (>100 triggers anomaly)
        # 4. canary_count (via count_by_agent -> >0 triggers anomaly)
        # 5. severe_events count (>10 triggers anomaly)
        mock_session.execute.side_effect = [
            _make_scalar_result(60),   # submission_count > 50
            _make_scalar_result(4),    # domain_count >= 3
            _make_scalar_result(5),    # vote_count (not > 100, not > 10 so no bias check)
            _make_scalar_result(1),    # canary_count > 0
            _make_scalar_result(15),   # severe_events > 10
        ]

        with patch("platform.security.security_event_repository.logger"):
            report = await repo.detect_anomalies(agent_id, window_hours=24)

        assert report["agent_id"] == str(agent_id)
        assert report["window_hours"] == 24
        assert isinstance(report["anomalies"], list)
        assert report["risk_score"] >= 0.0
        assert report["risk_score"] <= 1.0
        assert isinstance(report["is_anomalous"], bool)

        # We expect anomalies from: submission freq, domain switching, canary leak, event spike
        anomaly_types = [a["type"] for a in report["anomalies"]]
        assert "unusual_submission_frequency" in anomaly_types
        assert "domain_switching" in anomaly_types
        assert "canary_leak" in anomaly_types
        assert "security_event_spike" in anomaly_types

    @pytest.mark.asyncio
    async def test_detect_anomalies_empty_events_returns_no_anomalies(self, repo, mock_session):
        """detect_anomalies should return no anomalies when all counters are below thresholds."""
        agent_id = uuid4()

        # All counts below thresholds
        mock_session.execute.side_effect = [
            _make_scalar_result(5),    # submission_count < 50
            _make_scalar_result(1),    # domain_count < 3
            _make_scalar_result(2),    # vote_count < 100 and < 10 (no bias check)
            _make_scalar_result(0),    # canary_count == 0
            _make_scalar_result(0),    # severe_events == 0
        ]

        with patch("platform.security.security_event_repository.logger"):
            report = await repo.detect_anomalies(agent_id, window_hours=24)

        assert report["anomalies"] == []
        assert report["risk_score"] == 0.0
        assert report["is_anomalous"] is False

    @pytest.mark.asyncio
    async def test_detect_anomalies_excessive_voting(self, repo, mock_session):
        """detect_anomalies should flag excessive voting (>100 votes)."""
        agent_id = uuid4()

        # Create mock vote distribution result
        vote_dist_row_approve = MagicMock()
        vote_dist_row_approve.vote = "approve"
        vote_dist_row_approve.cnt = 95
        vote_dist_row_reject = MagicMock()
        vote_dist_row_reject.vote = "reject"
        vote_dist_row_reject.cnt = 6

        vote_dist_result = MagicMock()
        vote_dist_result.all.return_value = [vote_dist_row_approve, vote_dist_row_reject]

        mock_session.execute.side_effect = [
            _make_scalar_result(10),   # submission_count < 50
            _make_scalar_result(1),    # domain_count < 3
            _make_scalar_result(150),  # vote_count > 100
            vote_dist_result,          # vote distribution query
            _make_scalar_result(0),    # canary_count == 0
            _make_scalar_result(0),    # severe_events == 0
        ]

        with patch("platform.security.security_event_repository.logger"):
            report = await repo.detect_anomalies(agent_id, window_hours=24)

        anomaly_types = [a["type"] for a in report["anomalies"]]
        assert "excessive_voting" in anomaly_types

    @pytest.mark.asyncio
    async def test_detect_anomalies_vote_bias(self, repo, mock_session):
        """detect_anomalies should flag vote pattern bias (>95% same direction)."""
        agent_id = uuid4()

        # Create mock vote distribution with extreme bias
        vote_dist_row = MagicMock()
        vote_dist_row.vote = "approve"
        vote_dist_row.cnt = 50

        vote_dist_result = MagicMock()
        vote_dist_result.all.return_value = [vote_dist_row]  # 100% approve

        mock_session.execute.side_effect = [
            _make_scalar_result(10),   # submission_count < 50
            _make_scalar_result(1),    # domain_count < 3
            _make_scalar_result(50),   # vote_count > 10 (triggers bias check) but not > 100
            vote_dist_result,          # vote distribution query
            _make_scalar_result(0),    # canary_count == 0
            _make_scalar_result(0),    # severe_events == 0
        ]

        with patch("platform.security.security_event_repository.logger"):
            report = await repo.detect_anomalies(agent_id, window_hours=24)

        anomaly_types = [a["type"] for a in report["anomalies"]]
        assert "vote_pattern_bias" in anomaly_types

    @pytest.mark.asyncio
    async def test_detect_anomalies_risk_score_capped_at_1(self, repo, mock_session):
        """risk_score should never exceed 1.0 even with many anomalies."""
        agent_id = uuid4()

        # Trigger all anomalies
        vote_dist_row = MagicMock()
        vote_dist_row.vote = "approve"
        vote_dist_row.cnt = 200

        vote_dist_result = MagicMock()
        vote_dist_result.all.return_value = [vote_dist_row]

        mock_session.execute.side_effect = [
            _make_scalar_result(100),  # unusual_submission_frequency: high (0.6)
            _make_scalar_result(5),    # domain_switching: medium (0.3)
            _make_scalar_result(200),  # excessive_voting: high (0.6), vote_count > 10
            vote_dist_result,          # vote_pattern_bias: medium (0.3) -- 100% approve
            _make_scalar_result(3),    # canary_leak: critical (1.0)
            _make_scalar_result(20),   # security_event_spike: high (0.6)
        ]

        with patch("platform.security.security_event_repository.logger"):
            report = await repo.detect_anomalies(agent_id)

        assert report["risk_score"] <= 1.0
        assert report["is_anomalous"] is True

    @pytest.mark.asyncio
    async def test_detect_anomalies_custom_window_hours(self, repo, mock_session):
        """detect_anomalies should respect a custom window_hours value."""
        agent_id = uuid4()

        mock_session.execute.side_effect = [
            _make_scalar_result(0),
            _make_scalar_result(0),
            _make_scalar_result(0),
            _make_scalar_result(0),
            _make_scalar_result(0),
        ]

        with patch("platform.security.security_event_repository.logger"):
            report = await repo.detect_anomalies(agent_id, window_hours=1)

        assert report["window_hours"] == 1
