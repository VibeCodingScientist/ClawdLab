"""Unit tests for sprint service — validates business rules and async operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# 1. Business-rule / constant tests (no DB)
# ---------------------------------------------------------------------------


class TestSprintServiceRules:
    """Test sprint service business rules without DB (logic validation)."""

    def test_default_sprint_days_by_domain(self):
        from platform.agents.sprint_service import DEFAULT_SPRINT_DAYS

        assert DEFAULT_SPRINT_DAYS["mathematics"] == 28
        assert DEFAULT_SPRINT_DAYS["ml_ai"] == 14
        assert DEFAULT_SPRINT_DAYS["computational_biology"] == 21
        assert DEFAULT_SPRINT_DAYS["materials_science"] == 21
        assert DEFAULT_SPRINT_DAYS["bioinformatics"] == 14

    def test_all_domains_have_defaults(self):
        from platform.agents.sprint_service import DEFAULT_SPRINT_DAYS

        expected_domains = {
            "mathematics",
            "ml_ai",
            "computational_biology",
            "materials_science",
            "bioinformatics",
        }
        assert set(DEFAULT_SPRINT_DAYS.keys()) == expected_domains


# ---------------------------------------------------------------------------
# 2. start_sprint
# ---------------------------------------------------------------------------


class TestSprintServiceStartSprint:
    """Tests for SprintService.start_sprint using AsyncMock DB session."""

    @pytest.mark.asyncio
    async def test_start_sprint_creates_planning_sprint(self):
        """A new sprint should be created with status 'planning'."""
        from platform.agents.sprint_service import SprintService

        session = AsyncMock()
        service = SprintService(session)

        agent_id = uuid4()
        lab_id = uuid4()

        # No active sprint exists
        no_active_result = MagicMock()
        no_active_result.scalar_one_or_none.return_value = None

        # Next sprint number query returns 0 (no previous sprints)
        seq_result = MagicMock()
        seq_result.scalar.return_value = 0

        session.execute = AsyncMock(side_effect=[no_active_result, seq_result])
        session.flush = AsyncMock()

        sprint = await service.start_sprint(
            agent_id=agent_id,
            lab_id=lab_id,
            goal="Investigate transformer architectures",
            approach="Systematic ablation study",
            duration_days=7,
        )

        assert sprint.status == "planning"
        assert sprint.goal == "Investigate transformer architectures"
        assert sprint.approach == "Systematic ablation study"
        assert sprint.agent_id == agent_id
        assert sprint.lab_id == lab_id
        assert sprint.sprint_number == 1
        session.add.assert_called_once_with(sprint)
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_sprint_fails_with_active_sprint(self):
        """Should raise ValueError when agent already has an active sprint."""
        from platform.agents.sprint_service import SprintService

        session = AsyncMock()
        service = SprintService(session)

        agent_id = uuid4()
        lab_id = uuid4()

        # An active sprint already exists
        existing_sprint = MagicMock()
        existing_sprint.status = "active"
        active_result = MagicMock()
        active_result.scalar_one_or_none.return_value = existing_sprint

        session.execute = AsyncMock(return_value=active_result)

        with pytest.raises(ValueError, match="already has an active sprint"):
            await service.start_sprint(
                agent_id=agent_id,
                lab_id=lab_id,
                goal="New goal",
            )

        # Ensure no sprint was added
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_sprint_uses_default_duration_for_domain(self):
        """When duration_days is None, should use domain default from DEFAULT_SPRINT_DAYS."""
        from platform.agents.sprint_service import DEFAULT_SPRINT_DAYS, SprintService

        session = AsyncMock()
        service = SprintService(session)

        agent_id = uuid4()
        lab_id = uuid4()

        # No active sprint
        no_active_result = MagicMock()
        no_active_result.scalar_one_or_none.return_value = None

        # Previous sprint number = 2
        seq_result = MagicMock()
        seq_result.scalar.return_value = 2

        session.execute = AsyncMock(side_effect=[no_active_result, seq_result])
        session.flush = AsyncMock()

        sprint = await service.start_sprint(
            agent_id=agent_id,
            lab_id=lab_id,
            goal="Study protein folding dynamics",
            domain="mathematics",
            # duration_days is intentionally omitted
        )

        expected_days = DEFAULT_SPRINT_DAYS["mathematics"]  # 28
        expected_end = sprint.started_at + timedelta(days=expected_days)

        assert sprint.target_end_at == expected_end
        assert sprint.sprint_number == 3


# ---------------------------------------------------------------------------
# 3. pause / resume
# ---------------------------------------------------------------------------


class TestSprintServicePauseResume:
    """Tests for pausing and resuming sprints."""

    @pytest.mark.asyncio
    async def test_pause_sprint_transitions_to_paused(self):
        """Pausing an active sprint should set status to 'paused'."""
        from platform.agents.sprint_service import SprintService

        session = AsyncMock()
        service = SprintService(session)

        sprint_id = uuid4()

        mock_sprint = MagicMock()
        mock_sprint.id = sprint_id
        mock_sprint.status = "active"

        execute_result = MagicMock()
        execute_result.scalar_one.return_value = mock_sprint

        session.execute = AsyncMock(return_value=execute_result)
        session.flush = AsyncMock()

        result = await service.pause_sprint(sprint_id)

        assert result.status == "paused"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_resume_sprint_transitions_to_active(self):
        """Resuming a paused sprint should set status to 'active'."""
        from platform.agents.sprint_service import SprintService

        session = AsyncMock()
        service = SprintService(session)

        sprint_id = uuid4()

        mock_sprint = MagicMock()
        mock_sprint.id = sprint_id
        mock_sprint.status = "paused"

        execute_result = MagicMock()
        execute_result.scalar_one.return_value = mock_sprint

        session.execute = AsyncMock(return_value=execute_result)
        session.flush = AsyncMock()

        result = await service.resume_sprint(sprint_id)

        assert result.status == "active"
        session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. end_sprint
# ---------------------------------------------------------------------------


class TestSprintServiceEndSprint:
    """Tests for ending sprints with outcomes."""

    @pytest.mark.asyncio
    async def test_end_sprint_records_outcome(self):
        """Ending a sprint should record outcome_type and outcome_summary."""
        from platform.agents.sprint_service import SprintService

        session = AsyncMock()
        service = SprintService(session)

        sprint_id = uuid4()

        mock_sprint = MagicMock()
        mock_sprint.id = sprint_id
        mock_sprint.status = "active"

        execute_result = MagicMock()
        execute_result.scalar_one.return_value = mock_sprint

        session.execute = AsyncMock(return_value=execute_result)
        session.flush = AsyncMock()

        result = await service.end_sprint(
            sprint_id=sprint_id,
            outcome_type="positive",
            outcome_summary="Successfully replicated the main finding with p<0.01",
        )

        assert result.status == "completed"
        assert result.outcome_type == "positive"
        assert result.outcome_summary == "Successfully replicated the main finding with p<0.01"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_end_sprint_sets_actual_end_at(self):
        """Ending a sprint should set actual_end_at to approximately now (UTC)."""
        from platform.agents.sprint_service import SprintService

        session = AsyncMock()
        service = SprintService(session)

        sprint_id = uuid4()

        mock_sprint = MagicMock()
        mock_sprint.id = sprint_id
        mock_sprint.status = "active"
        mock_sprint.actual_end_at = None  # not yet set

        execute_result = MagicMock()
        execute_result.scalar_one.return_value = mock_sprint

        session.execute = AsyncMock(return_value=execute_result)
        session.flush = AsyncMock()

        before = datetime.now(timezone.utc)

        result = await service.end_sprint(
            sprint_id=sprint_id,
            outcome_type="inconclusive",
            outcome_summary="Results were mixed, further investigation needed",
        )

        after = datetime.now(timezone.utc)

        assert result.actual_end_at is not None
        assert before <= result.actual_end_at <= after
