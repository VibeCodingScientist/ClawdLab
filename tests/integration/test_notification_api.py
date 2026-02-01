"""Integration tests for notification API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_agent_state(agent_id: str) -> dict:
    """Create a dict representing request.state.agent."""
    return {
        "agent_id": agent_id,
        "role": "theorist",
        "labs": [],
    }


@pytest.fixture
def mock_notification_service():
    """Create a mock NotificationService."""
    service = MagicMock()
    service.get_notifications = AsyncMock(return_value=([], 0))
    service.get_unread_count = AsyncMock(return_value=3)
    service.mark_read = AsyncMock(return_value=True)
    service.mark_all_read = AsyncMock(return_value=5)
    service.delete_notification = AsyncMock(return_value=True)
    return service


@pytest.fixture
def app_and_agent_id(mock_notification_service):
    """Create a FastAPI app with the notification router, returning (app, agent_id).

    Includes middleware that injects a mock authenticated agent into
    request.state and patches NotificationService to use the mock.
    """
    agent_id = str(uuid4())

    from platform.notifications.api import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    @app.middleware("http")
    async def inject_agent(request, call_next):
        request.state.agent = _make_agent_state(agent_id)
        response = await call_next(request)
        return response

    return app, agent_id, mock_notification_service


@pytest.fixture
def authenticated_client(app_and_agent_id):
    """Create a TestClient with injected agent state and patched service."""
    app, agent_id, mock_service = app_and_agent_id

    with patch("platform.notifications.api.NotificationService", return_value=mock_service):
        with patch("platform.notifications.api.get_db", return_value=AsyncMock()):
            client = TestClient(app)
            yield client, agent_id, mock_service


@pytest.fixture
def unauthenticated_app():
    """Create a FastAPI app without agent middleware (no auth)."""
    from platform.notifications.api import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def unauthenticated_client(unauthenticated_app):
    """Create a TestClient without authentication."""
    with patch("platform.notifications.api.get_db", return_value=AsyncMock()):
        return TestClient(unauthenticated_app, raise_server_errors=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListNotificationsAuth:
    """Tests for GET /api/v1/notifications requiring auth."""

    def test_list_notifications_requires_auth(self, unauthenticated_client):
        """Listing notifications without auth should return 401."""
        response = unauthenticated_client.get("/api/v1/notifications")

        assert response.status_code == 401

    def test_list_notifications_returns_items(self, authenticated_client):
        """Authenticated request should return items and total."""
        client, agent_id, mock_service = authenticated_client
        mock_service.get_notifications.return_value = (
            [
                {
                    "id": str(uuid4()),
                    "agent_id": agent_id,
                    "notification_type": "roundtable",
                    "priority": "normal",
                    "title": "New discussion",
                    "body": None,
                    "data": None,
                    "action_url": None,
                    "read_at": None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
            1,
        )

        response = client.get("/api/v1/notifications")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 1
        assert len(data["items"]) == 1


class TestGetUnreadCount:
    """Tests for GET /api/v1/notifications/count."""

    def test_get_unread_count(self, authenticated_client):
        """Should return the unread count for the authenticated agent."""
        client, agent_id, mock_service = authenticated_client
        mock_service.get_unread_count.return_value = 7

        response = client.get("/api/v1/notifications/count")

        assert response.status_code == 200
        data = response.json()
        assert data["unread_count"] == 7


class TestMarkRead:
    """Tests for PATCH /api/v1/notifications/{id}/read."""

    def test_mark_read_returns_success(self, authenticated_client):
        """Marking a notification read should return success."""
        client, agent_id, mock_service = authenticated_client
        notification_id = uuid4()
        mock_service.mark_read.return_value = True

        response = client.patch(f"/api/v1/notifications/{notification_id}/read")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["notification_id"] == str(notification_id)

    def test_mark_read_not_found(self, authenticated_client):
        """Marking a non-existent notification should return 404."""
        client, agent_id, mock_service = authenticated_client
        notification_id = uuid4()
        mock_service.mark_read.return_value = False

        response = client.patch(f"/api/v1/notifications/{notification_id}/read")

        assert response.status_code == 404


class TestMarkAllRead:
    """Tests for POST /api/v1/notifications/read-all."""

    def test_mark_all_read(self, authenticated_client):
        """Should mark all unread notifications and return count."""
        client, agent_id, mock_service = authenticated_client
        mock_service.mark_all_read.return_value = 3

        response = client.post("/api/v1/notifications/read-all")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["marked_count"] == 3


class TestDeleteNotification:
    """Tests for DELETE /api/v1/notifications/{id}."""

    def test_delete_notification_success(self, authenticated_client):
        """Deleting an existing notification should return success."""
        client, agent_id, mock_service = authenticated_client
        notification_id = uuid4()
        mock_service.delete_notification.return_value = True

        response = client.delete(f"/api/v1/notifications/{notification_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_delete_notification_not_found(self, authenticated_client):
        """Deleting a non-existent notification should return 404."""
        client, agent_id, mock_service = authenticated_client
        notification_id = uuid4()
        mock_service.delete_notification.return_value = False

        response = client.delete(f"/api/v1/notifications/{notification_id}")

        assert response.status_code == 404
