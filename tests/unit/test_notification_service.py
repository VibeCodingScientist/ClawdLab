"""Tests for NotificationService."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_notification(
    agent_id=None,
    notification_type="roundtable",
    priority="normal",
    title="Test notification",
    read_at=None,
):
    """Create a mock Notification ORM object."""
    n = MagicMock()
    n.id = uuid4()
    n.agent_id = agent_id or uuid4()
    n.notification_type = notification_type
    n.priority = priority
    n.title = title
    n.body = "Test body"
    n.data = {"key": "value"}
    n.action_url = "/api/v1/test"
    n.read_at = read_at
    n.created_at = datetime.now(timezone.utc)
    return n


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
def service(mock_session):
    """Create a NotificationService with the mock session."""
    from platform.notifications.service import NotificationService

    return NotificationService(mock_session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateNotification:
    """Tests for NotificationService.create_notification."""

    @pytest.mark.asyncio
    async def test_create_notification(self, service, mock_session):
        """create_notification should add a row and return a serialised dict."""
        agent_id = uuid4()

        # After flush+refresh, the mock session provides the Notification
        # via session.refresh which populates the object. We simulate by
        # making refresh set attributes on the object that was added.
        created_notification = _make_notification(agent_id=agent_id, title="Vote called")

        # Capture the Notification object passed to session.add
        added_objects = []
        mock_session.add.side_effect = lambda obj: added_objects.append(obj)

        # After refresh, the object should have the right attributes.
        async def fake_refresh(obj):
            obj.id = created_notification.id
            obj.agent_id = created_notification.agent_id
            obj.notification_type = created_notification.notification_type
            obj.priority = created_notification.priority
            obj.title = created_notification.title
            obj.body = created_notification.body
            obj.data = created_notification.data
            obj.action_url = created_notification.action_url
            obj.read_at = created_notification.read_at
            obj.created_at = created_notification.created_at

        mock_session.refresh.side_effect = fake_refresh

        with patch("platform.notifications.service.Notification") as MockNotif:
            mock_obj = MagicMock()
            MockNotif.return_value = mock_obj

            # Wire up refresh to populate mock_obj
            async def fake_refresh2(obj):
                obj.id = created_notification.id
                obj.agent_id = agent_id
                obj.notification_type = "roundtable"
                obj.priority = "high"
                obj.title = "Vote called"
                obj.body = None
                obj.data = None
                obj.action_url = None
                obj.read_at = None
                obj.created_at = datetime.now(timezone.utc)

            mock_session.refresh.side_effect = fake_refresh2

            result = await service.create_notification(
                agent_id=agent_id,
                notification_type="roundtable",
                priority="high",
                title="Vote called",
            )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()
        assert result["title"] == "Vote called"


class TestGetNotifications:
    """Tests for NotificationService.get_notifications."""

    @pytest.mark.asyncio
    async def test_get_notifications_returns_list_and_count(self, service, mock_session):
        """get_notifications should return (list, total_count) tuple."""
        agent_id = uuid4()
        notif1 = _make_notification(agent_id)
        notif2 = _make_notification(agent_id)

        # First call returns count, second returns rows
        count_result = MagicMock()
        count_result.scalar.return_value = 2

        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = [notif1, notif2]

        mock_session.execute.side_effect = [count_result, rows_result]

        notifications, total = await service.get_notifications(agent_id)

        assert total == 2
        assert len(notifications) == 2
        assert notifications[0]["title"] == notif1.title

    @pytest.mark.asyncio
    async def test_get_notifications_unread_only(self, service, mock_session):
        """Passing unread_only=True should filter appropriately."""
        agent_id = uuid4()

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [count_result, rows_result]

        notifications, total = await service.get_notifications(
            agent_id, unread_only=True
        )

        assert total == 0
        assert len(notifications) == 0
        # Verify execute was called twice (count + rows)
        assert mock_session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_get_notifications_with_type_filter(self, service, mock_session):
        """Passing notification_type should filter by type."""
        agent_id = uuid4()

        count_result = MagicMock()
        count_result.scalar.return_value = 1

        notif = _make_notification(agent_id, notification_type="membership")
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = [notif]

        mock_session.execute.side_effect = [count_result, rows_result]

        notifications, total = await service.get_notifications(
            agent_id, notification_type="membership"
        )

        assert total == 1
        assert notifications[0]["notification_type"] == "membership"


class TestMarkRead:
    """Tests for NotificationService.mark_read."""

    @pytest.mark.asyncio
    async def test_mark_read_returns_true_on_success(self, service, mock_session):
        """mark_read should return True when a row is updated."""
        agent_id = uuid4()
        notification_id = uuid4()

        result = MagicMock()
        result.rowcount = 1
        mock_session.execute.return_value = result

        updated = await service.mark_read(agent_id, notification_id)

        assert updated is True
        mock_session.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_mark_read_returns_false_when_not_found(self, service, mock_session):
        """mark_read should return False when no row matches."""
        agent_id = uuid4()
        notification_id = uuid4()

        result = MagicMock()
        result.rowcount = 0
        mock_session.execute.return_value = result

        updated = await service.mark_read(agent_id, notification_id)

        assert updated is False


class TestMarkAllRead:
    """Tests for NotificationService.mark_all_read."""

    @pytest.mark.asyncio
    async def test_mark_all_read_returns_count(self, service, mock_session):
        """mark_all_read should return the number of rows updated."""
        agent_id = uuid4()

        result = MagicMock()
        result.rowcount = 5
        mock_session.execute.return_value = result

        count = await service.mark_all_read(agent_id)

        assert count == 5
        mock_session.flush.assert_awaited()


class TestDeleteNotification:
    """Tests for NotificationService.delete_notification."""

    @pytest.mark.asyncio
    async def test_delete_notification_returns_true(self, service, mock_session):
        """delete_notification should return True when the row is removed."""
        agent_id = uuid4()
        notification_id = uuid4()

        result = MagicMock()
        result.rowcount = 1
        mock_session.execute.return_value = result

        deleted = await service.delete_notification(agent_id, notification_id)

        assert deleted is True

    @pytest.mark.asyncio
    async def test_delete_notification_returns_false_not_found(self, service, mock_session):
        """delete_notification should return False when no row matches."""
        agent_id = uuid4()
        notification_id = uuid4()

        result = MagicMock()
        result.rowcount = 0
        mock_session.execute.return_value = result

        deleted = await service.delete_notification(agent_id, notification_id)

        assert deleted is False


class TestGetUnreadCount:
    """Tests for NotificationService.get_unread_count."""

    @pytest.mark.asyncio
    async def test_get_unread_count(self, service, mock_session):
        """get_unread_count should return the scalar count."""
        agent_id = uuid4()

        result = MagicMock()
        result.scalar.return_value = 7
        mock_session.execute.return_value = result

        count = await service.get_unread_count(agent_id)

        assert count == 7

    @pytest.mark.asyncio
    async def test_get_unread_count_returns_zero_when_none(self, service, mock_session):
        """get_unread_count should return 0 when scalar returns None."""
        agent_id = uuid4()

        result = MagicMock()
        result.scalar.return_value = None
        mock_session.execute.return_value = result

        count = await service.get_unread_count(agent_id)

        assert count == 0


class TestGetRoleFiltered:
    """Tests for NotificationService.get_role_filtered."""

    @pytest.mark.asyncio
    async def test_role_filtered_for_theorist(self, service, mock_session):
        """Theorist should get roundtable/research/verification/challenge types."""
        agent_id = uuid4()
        notif = _make_notification(agent_id, notification_type="roundtable")

        result = MagicMock()
        result.scalars.return_value.all.return_value = [notif]
        mock_session.execute.return_value = result

        notifications = await service.get_role_filtered(agent_id, "theorist")

        assert len(notifications) == 1
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_role_filtered_generalist_gets_all(self, service, mock_session):
        """Generalist should receive all notification types (no type filter)."""
        agent_id = uuid4()
        notif = _make_notification(agent_id, notification_type="governance")

        result = MagicMock()
        result.scalars.return_value.all.return_value = [notif]
        mock_session.execute.return_value = result

        notifications = await service.get_role_filtered(agent_id, "generalist")

        assert len(notifications) == 1
