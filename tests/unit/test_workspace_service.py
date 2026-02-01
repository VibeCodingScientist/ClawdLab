"""Tests for WorkspaceService."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from platform.labs.workspace_service import WorkspaceService


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def service(mock_session: AsyncMock) -> WorkspaceService:
    """Create a WorkspaceService with mocked dependencies."""
    with patch("platform.labs.workspace_service.WorkspaceRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        svc = WorkspaceService(mock_session)
        svc.workspace_repo = mock_repo
        return svc


class TestHandleEventZoneMappings:
    """Tests that handle_event correctly maps events to workspace zones."""

    @pytest.mark.asyncio
    async def test_member_joined_maps_to_ideation_zone(self, service):
        """member.joined should place the agent in the ideation zone."""
        agent_id = uuid4()
        lab_id = uuid4()
        data = {"lab_id": lab_id, "agent_id": agent_id}
        service.workspace_repo.upsert = AsyncMock()

        with patch("platform.labs.workspace_service.logger"):
            result = await service.handle_event("member.joined", data)

        assert result is not None
        assert result["zone"] == "ideation"
        assert result["status"] == "entering"
        assert result["agent_id"] == str(agent_id)
        assert result["lab_id"] == str(lab_id)

    @pytest.mark.asyncio
    async def test_entry_created_maps_to_roundtable_zone(self, service):
        """entry.created should place the agent in the roundtable zone."""
        agent_id = uuid4()
        lab_id = uuid4()
        data = {"lab_id": lab_id, "agent_id": agent_id}
        service.workspace_repo.upsert = AsyncMock()

        with patch("platform.labs.workspace_service.logger"):
            result = await service.handle_event("entry.created", data)

        assert result is not None
        assert result["zone"] == "roundtable"
        assert result["status"] == "contributing"

    @pytest.mark.asyncio
    async def test_work_assigned_maps_to_bench_zone(self, service):
        """roundtable.work_assigned should place the agent in the bench zone."""
        agent_id = uuid4()
        lab_id = uuid4()
        data = {"lab_id": lab_id, "assigned_to": agent_id}
        service.workspace_repo.upsert = AsyncMock()

        with patch("platform.labs.workspace_service.logger"):
            result = await service.handle_event("roundtable.work_assigned", data)

        assert result is not None
        assert result["zone"] == "bench"
        assert result["status"] == "working"

    @pytest.mark.asyncio
    async def test_result_submitted_maps_to_presentation_zone(self, service):
        """roundtable.result_submitted should place the agent in the presentation zone."""
        agent_id = uuid4()
        lab_id = uuid4()
        data = {"lab_id": lab_id, "agent_id": agent_id}
        service.workspace_repo.upsert = AsyncMock()

        with patch("platform.labs.workspace_service.logger"):
            result = await service.handle_event("roundtable.result_submitted", data)

        assert result is not None
        assert result["zone"] == "presentation"
        assert result["status"] == "presenting"

    @pytest.mark.asyncio
    async def test_result_verified_maps_to_whiteboard_zone(self, service):
        """roundtable.result_verified should place the agent in the whiteboard zone."""
        agent_id = uuid4()
        lab_id = uuid4()
        data = {"lab_id": lab_id, "agent_id": agent_id}
        service.workspace_repo.upsert = AsyncMock()

        with patch("platform.labs.workspace_service.logger"):
            result = await service.handle_event("roundtable.result_verified", data)

        assert result is not None
        assert result["zone"] == "whiteboard"
        assert result["status"] == "celebrating"

    @pytest.mark.asyncio
    async def test_vote_cast_maps_to_roundtable_voting(self, service):
        """roundtable.vote_cast should place the agent in the roundtable zone with voting status."""
        agent_id = uuid4()
        lab_id = uuid4()
        data = {"lab_id": lab_id, "agent_id": agent_id}
        service.workspace_repo.upsert = AsyncMock()

        with patch("platform.labs.workspace_service.logger"):
            result = await service.handle_event("roundtable.vote_cast", data)

        assert result is not None
        assert result["zone"] == "roundtable"
        assert result["status"] == "voting"

    @pytest.mark.asyncio
    async def test_item_proposed_maps_to_ideation_proposing(self, service):
        """item.proposed should place the agent in the ideation zone with proposing status."""
        agent_id = uuid4()
        lab_id = uuid4()
        data = {"lab_id": lab_id, "proposed_by": agent_id}
        service.workspace_repo.upsert = AsyncMock()

        with patch("platform.labs.workspace_service.logger"):
            result = await service.handle_event("item.proposed", data)

        assert result is not None
        assert result["zone"] == "ideation"
        assert result["status"] == "proposing"


class TestHandleEventEdgeCases:
    """Tests for edge cases in handle_event."""

    @pytest.mark.asyncio
    async def test_unmapped_event_returns_none(self, service):
        """An event type not in ZONE_MAPPINGS should return None."""
        data = {"lab_id": uuid4(), "agent_id": uuid4()}

        with patch("platform.labs.workspace_service.logger"):
            result = await service.handle_event("unknown.event.type", data)

        assert result is None

    @pytest.mark.asyncio
    async def test_missing_lab_id_returns_none(self, service):
        """handle_event should return None if lab_id is missing from data."""
        data = {"agent_id": uuid4()}

        with patch("platform.labs.workspace_service.logger"):
            result = await service.handle_event("member.joined", data)

        assert result is None

    @pytest.mark.asyncio
    async def test_missing_agent_id_returns_none(self, service):
        """handle_event should return None if agent_id is missing from data."""
        data = {"lab_id": uuid4()}

        with patch("platform.labs.workspace_service.logger"):
            result = await service.handle_event("member.joined", data)

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_data_returns_none(self, service):
        """handle_event should return None if data is empty."""
        with patch("platform.labs.workspace_service.logger"):
            result = await service.handle_event("member.joined", {})

        assert result is None


class TestHandleEventStateUpdate:
    """Tests that handle_event correctly calls workspace_repo.upsert."""

    @pytest.mark.asyncio
    async def test_upsert_called_with_correct_position(self, service):
        """handle_event should call upsert with the zone's default position."""
        agent_id = uuid4()
        lab_id = uuid4()
        data = {"lab_id": lab_id, "agent_id": agent_id}
        service.workspace_repo.upsert = AsyncMock()

        with patch("platform.labs.workspace_service.logger"):
            await service.handle_event("roundtable.work_assigned", data)

        service.workspace_repo.upsert.assert_called_once_with(
            lab_id=lab_id,
            agent_id=agent_id,
            zone="bench",
            position_x=500.0,
            position_y=100.0,
            status="working",
        )

    @pytest.mark.asyncio
    async def test_result_includes_action_and_timestamp(self, service):
        """The returned state dict should include the action (event_type) and a timestamp."""
        agent_id = uuid4()
        lab_id = uuid4()
        data = {"lab_id": lab_id, "agent_id": agent_id}
        service.workspace_repo.upsert = AsyncMock()

        with patch("platform.labs.workspace_service.logger"):
            result = await service.handle_event("entry.created", data)

        assert result["action"] == "entry.created"
        assert "timestamp" in result


class TestGetLabWorkspace:
    """Tests for WorkspaceService.get_lab_workspace."""

    @pytest.mark.asyncio
    async def test_get_lab_workspace_returns_list_of_states(self, service):
        """get_lab_workspace should return a list of workspace state dicts."""
        lab_id = uuid4()

        mock_state = MagicMock()
        mock_state.agent_id = uuid4()
        mock_state.zone = "bench"
        mock_state.position_x = 500.0
        mock_state.position_y = 100.0
        mock_state.status = "working"
        mock_state.last_action_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        service.workspace_repo.get_by_lab = AsyncMock(return_value=[mock_state])

        states = await service.get_lab_workspace(lab_id)

        assert len(states) == 1
        assert states[0]["zone"] == "bench"
        assert states[0]["status"] == "working"
        assert states[0]["position_x"] == 500.0
        assert states[0]["position_y"] == 100.0
        assert states[0]["agent_id"] == str(mock_state.agent_id)
        assert states[0]["last_action_at"] is not None

    @pytest.mark.asyncio
    async def test_get_lab_workspace_empty_lab(self, service):
        """get_lab_workspace should return an empty list for a lab with no agents."""
        service.workspace_repo.get_by_lab = AsyncMock(return_value=[])

        states = await service.get_lab_workspace("empty-lab")

        assert states == []

    @pytest.mark.asyncio
    async def test_get_lab_workspace_none_last_action_at(self, service):
        """get_lab_workspace should handle None last_action_at."""
        mock_state = MagicMock()
        mock_state.agent_id = uuid4()
        mock_state.zone = "ideation"
        mock_state.position_x = 100.0
        mock_state.position_y = 100.0
        mock_state.status = "entering"
        mock_state.last_action_at = None

        service.workspace_repo.get_by_lab = AsyncMock(return_value=[mock_state])

        states = await service.get_lab_workspace("some-lab")

        assert len(states) == 1
        assert states[0]["last_action_at"] is None
