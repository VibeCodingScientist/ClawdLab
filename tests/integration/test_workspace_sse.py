"""Tests for workspace SSE endpoint and event publishing."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from platform.labs.workspace_sse import (
    _workspace_events,
    get_lab_queue,
    publish_workspace_event,
    router,
)


@pytest.fixture(autouse=True)
def clear_workspace_events():
    """Clear the in-memory event bus between tests."""
    _workspace_events.clear()
    yield
    _workspace_events.clear()


class TestWorkspaceStateEndpoint:
    """Tests for GET /labs/{slug}/workspace/state."""

    @pytest.mark.asyncio
    async def test_workspace_state_returns_snapshot(self):
        """GET /labs/{slug}/workspace/state should return a workspace snapshot."""
        mock_states = [
            {
                "agent_id": str(uuid4()),
                "zone": "roundtable",
                "position_x": 100.0,
                "position_y": 300.0,
                "status": "contributing",
                "last_action_at": datetime.now(timezone.utc).isoformat(),
            },
        ]

        mock_service = MagicMock()
        mock_service.get_lab_workspace = AsyncMock(return_value=mock_states)

        with patch("platform.labs.workspace_sse.WorkspaceService", return_value=mock_service):
            # Simulate calling the endpoint handler directly
            mock_db = AsyncMock()
            from platform.labs.workspace_sse import workspace_state

            result = await workspace_state(slug="test-lab", db=mock_db)

        assert result["slug"] == "test-lab"
        assert result["total"] == 1
        assert len(result["agents"]) == 1
        assert result["agents"][0]["zone"] == "roundtable"

    @pytest.mark.asyncio
    async def test_workspace_state_empty_lab(self):
        """GET /labs/{slug}/workspace/state should return empty agents for new lab."""
        mock_service = MagicMock()
        mock_service.get_lab_workspace = AsyncMock(return_value=[])

        with patch("platform.labs.workspace_sse.WorkspaceService", return_value=mock_service):
            mock_db = AsyncMock()
            from platform.labs.workspace_sse import workspace_state

            result = await workspace_state(slug="empty-lab", db=mock_db)

        assert result["slug"] == "empty-lab"
        assert result["total"] == 0
        assert result["agents"] == []


class TestPublishWorkspaceEvent:
    """Tests for publish_workspace_event."""

    @pytest.mark.asyncio
    async def test_publish_workspace_event_adds_to_queue(self):
        """publish_workspace_event should add the event to the lab's queue."""
        slug = "pub-test-lab"
        event = {"zone": "bench", "agent_id": "agent-1", "status": "working"}

        with patch("platform.labs.workspace_sse.logger"):
            await publish_workspace_event(slug, event)

        queue = get_lab_queue(slug)
        assert not queue.empty()
        retrieved = queue.get_nowait()
        assert retrieved == event

    @pytest.mark.asyncio
    async def test_publish_multiple_events(self):
        """Publishing multiple events should queue them in order."""
        slug = "multi-test"
        events = [
            {"zone": "ideation", "agent_id": "a1"},
            {"zone": "roundtable", "agent_id": "a2"},
            {"zone": "bench", "agent_id": "a3"},
        ]

        with patch("platform.labs.workspace_sse.logger"):
            for event in events:
                await publish_workspace_event(slug, event)

        queue = get_lab_queue(slug)
        retrieved = []
        while not queue.empty():
            retrieved.append(queue.get_nowait())

        assert len(retrieved) == 3
        assert retrieved[0]["zone"] == "ideation"
        assert retrieved[1]["zone"] == "roundtable"
        assert retrieved[2]["zone"] == "bench"


class TestGetLabQueue:
    """Tests for get_lab_queue."""

    def test_get_lab_queue_creates_queue_for_new_lab(self):
        """get_lab_queue should create a new queue for a slug not yet seen."""
        slug = "new-lab-queue"
        assert slug not in _workspace_events

        queue = get_lab_queue(slug)

        assert slug in _workspace_events
        assert isinstance(queue, asyncio.Queue)

    def test_get_lab_queue_returns_same_queue_for_same_slug(self):
        """get_lab_queue should return the same queue instance for repeated calls."""
        slug = "same-lab"
        queue1 = get_lab_queue(slug)
        queue2 = get_lab_queue(slug)

        assert queue1 is queue2

    def test_get_lab_queue_different_slugs_get_different_queues(self):
        """Different lab slugs should get independent queues."""
        queue_a = get_lab_queue("lab-alpha")
        queue_b = get_lab_queue("lab-beta")

        assert queue_a is not queue_b


class TestQueueOverflow:
    """Tests for queue overflow behavior (drop oldest when full)."""

    @pytest.mark.asyncio
    async def test_queue_drops_oldest_when_full(self):
        """When the queue is full, publishing should drop the oldest event."""
        slug = "overflow-lab"
        queue = get_lab_queue(slug)

        # Fill the queue to capacity (maxsize=100)
        with patch("platform.labs.workspace_sse.logger"):
            for i in range(100):
                await publish_workspace_event(slug, {"seq": i})

        assert queue.full()

        # Publish one more -- oldest should be dropped
        with patch("platform.labs.workspace_sse.logger"):
            await publish_workspace_event(slug, {"seq": 100})

        assert queue.qsize() == 100

        # The first event (seq=0) should have been dropped; first in queue is seq=1
        first = queue.get_nowait()
        assert first["seq"] == 1

    @pytest.mark.asyncio
    async def test_queue_accepts_events_after_overflow(self):
        """After dropping oldest, the queue should accept new events normally."""
        slug = "post-overflow-lab"

        with patch("platform.labs.workspace_sse.logger"):
            # Fill to capacity
            for i in range(100):
                await publish_workspace_event(slug, {"seq": i})

            # Overflow by 5
            for i in range(100, 105):
                await publish_workspace_event(slug, {"seq": i})

        queue = get_lab_queue(slug)
        assert queue.qsize() == 100

        # The first event should be seq=5 (0-4 were dropped)
        first = queue.get_nowait()
        assert first["seq"] == 5

    @pytest.mark.asyncio
    async def test_different_labs_have_independent_queues(self):
        """Overflow in one lab's queue should not affect another lab's queue."""
        with patch("platform.labs.workspace_sse.logger"):
            # Fill lab-a to capacity
            for i in range(100):
                await publish_workspace_event("lab-a", {"lab": "a", "seq": i})

            # Add one event to lab-b
            await publish_workspace_event("lab-b", {"lab": "b", "seq": 0})

        queue_a = get_lab_queue("lab-a")
        queue_b = get_lab_queue("lab-b")

        assert queue_a.qsize() == 100
        assert queue_b.qsize() == 1
