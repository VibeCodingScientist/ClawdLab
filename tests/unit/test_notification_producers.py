"""Tests for NotificationProducer."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def producer(mock_session):
    """Create a NotificationProducer with a mocked service."""
    from platform.notifications.producers import NotificationProducer

    p = NotificationProducer(mock_session)
    # Replace the internal NotificationService with a mock
    p.service = MagicMock()
    p.service.create_notification = AsyncMock(return_value={
        "id": str(uuid4()),
        "agent_id": str(uuid4()),
        "notification_type": "roundtable",
        "priority": "high",
        "title": "Test",
        "body": None,
        "data": None,
        "action_url": None,
        "read_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRoundtableVoteCalled:
    """Tests for roundtable.vote_called event."""

    @pytest.mark.asyncio
    async def test_creates_notification_for_lab_members(self, producer, mock_session):
        """vote_called should create notifications for all active lab members."""
        lab_id = uuid4()
        member1 = uuid4()
        member2 = uuid4()
        originator = uuid4()

        # Mock _get_lab_member_ids to return lab members
        producer._get_lab_member_ids = AsyncMock(
            return_value=[str(member1), str(member2), str(originator)]
        )

        await producer.handle_event(
            "roundtable.vote_called",
            {
                "lab_id": str(lab_id),
                "lab_name": "Quantum Lab",
                "title": "Prove quantum speedup",
                "agent_id": str(originator),
            },
        )

        # Originator is excluded, so 2 notifications should be created
        assert producer.service.create_notification.await_count == 2

        # Verify the title was formatted correctly
        first_call = producer.service.create_notification.call_args_list[0]
        assert "Quantum Lab" in first_call.kwargs.get("title", "") or "Quantum Lab" in str(first_call)

    @pytest.mark.asyncio
    async def test_vote_called_no_members_produces_nothing(self, producer, mock_session):
        """If no lab members found, no notifications should be created."""
        producer._get_lab_member_ids = AsyncMock(return_value=[])

        await producer.handle_event(
            "roundtable.vote_called",
            {
                "lab_id": str(uuid4()),
                "lab_name": "Empty Lab",
                "title": "Test item",
            },
        )

        producer.service.create_notification.assert_not_awaited()


class TestRoundtableResultVerified:
    """Tests for roundtable.result_verified event."""

    @pytest.mark.asyncio
    async def test_creates_notification_for_claim_owner(self, producer, mock_session):
        """result_verified should notify the claim owner (executor)."""
        claim_id = uuid4()
        executor_id = uuid4()

        # Mock _get_claim_owner
        producer._get_claim_owner = AsyncMock(return_value=str(executor_id))

        await producer.handle_event(
            "roundtable.result_verified",
            {
                "claim_id": str(claim_id),
                "karma": 50,
            },
        )

        producer.service.create_notification.assert_awaited_once()
        call_kwargs = producer.service.create_notification.call_args.kwargs
        assert call_kwargs["agent_id"] == str(executor_id)
        assert call_kwargs["notification_type"] == "verification"

    @pytest.mark.asyncio
    async def test_result_verified_fallback_to_target_agent(self, producer, mock_session):
        """If claim_id is missing, fall back to target_agent_id."""
        target_id = uuid4()

        # No claim_id in data, so _get_claim_owner should not be called
        producer._get_claim_owner = AsyncMock(return_value=None)

        await producer.handle_event(
            "roundtable.result_verified",
            {
                "target_agent_id": str(target_id),
                "karma": 25,
            },
        )

        producer.service.create_notification.assert_awaited_once()
        call_kwargs = producer.service.create_notification.call_args.kwargs
        assert call_kwargs["agent_id"] == str(target_id)


class TestMemberJoined:
    """Tests for member.joined event."""

    @pytest.mark.asyncio
    async def test_creates_notification_for_existing_members(self, producer, mock_session):
        """member.joined should notify existing lab members."""
        lab_id = uuid4()
        joiner_id = uuid4()
        existing_member = uuid4()

        producer._get_lab_member_ids = AsyncMock(
            return_value=[str(existing_member), str(joiner_id)]
        )

        await producer.handle_event(
            "member.joined",
            {
                "lab_id": str(lab_id),
                "lab_name": "Research Lab",
                "agent_id": str(joiner_id),
            },
        )

        # Joiner (originator) is excluded
        assert producer.service.create_notification.await_count == 1
        call_kwargs = producer.service.create_notification.call_args.kwargs
        assert call_kwargs["agent_id"] == str(existing_member)
        assert call_kwargs["notification_type"] == "membership"
        assert call_kwargs["priority"] == "low"


class TestUnknownEventType:
    """Tests for unknown/unregistered event types."""

    @pytest.mark.asyncio
    async def test_unknown_event_handled_gracefully(self, producer, mock_session):
        """An unknown event type should not raise or create notifications."""
        await producer.handle_event(
            "some.unknown.event",
            {"data": "irrelevant"},
        )

        producer.service.create_notification.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_event_type_handled_gracefully(self, producer, mock_session):
        """An empty string event type should not raise or create notifications."""
        await producer.handle_event("", {})

        producer.service.create_notification.assert_not_awaited()


class TestOriginatorExclusion:
    """Verify that the originator is excluded from notifications."""

    @pytest.mark.asyncio
    async def test_originator_excluded_from_lab_notification(self, producer, mock_session):
        """The agent who triggered the event should not be notified."""
        lab_id = uuid4()
        originator = uuid4()
        other_member = uuid4()

        producer._get_lab_member_ids = AsyncMock(
            return_value=[str(originator), str(other_member)]
        )

        await producer.handle_event(
            "research.proposed",
            {
                "lab_id": str(lab_id),
                "lab_name": "Test Lab",
                "title": "New research idea",
                "agent_id": str(originator),
            },
        )

        # Only other_member should be notified
        assert producer.service.create_notification.await_count == 1
        call_kwargs = producer.service.create_notification.call_args.kwargs
        assert call_kwargs["agent_id"] == str(other_member)


class TestSafeFormatDict:
    """Tests for the _SafeFormatDict used in title formatting."""

    def test_missing_key_returns_braced_key(self):
        """Missing keys should return {key} instead of raising KeyError."""
        from platform.notifications.producers import _SafeFormatDict

        d = _SafeFormatDict({"name": "Test"})
        result = "{missing}".format_map(d)

        assert result == "{missing}"

    def test_present_key_returns_value(self):
        """Present keys should return their value normally."""
        from platform.notifications.producers import _SafeFormatDict

        d = _SafeFormatDict({"lab_name": "Quantum Lab"})
        result = "Lab {lab_name}: event".format_map(d)

        assert result == "Lab Quantum Lab: event"
