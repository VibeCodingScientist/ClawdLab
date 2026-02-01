"""Integration tests for protocol API endpoints."""

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


@pytest.fixture
def _patch_all_protocol_deps():
    """Patch all external dependencies used by the protocol API module.

    This patches generators, signers, database, and discovery functions
    so the router can be exercised without real infrastructure.
    """
    mock_settings = MagicMock()
    mock_settings.protocol_version = "2.0.0"
    mock_settings.skill_cache_seconds = 3600
    mock_settings.heartbeat_cache_seconds = 60
    mock_settings.labspec_cache_seconds = 300
    mock_settings.heartbeat_lab_scan_interval = 4

    patches = [
        patch("platform.api.protocol.config.get_protocol_settings", return_value=mock_settings),
        patch("platform.api.protocol.api.get_protocol_settings", return_value=mock_settings),
    ]

    # Patch SkillGenerator
    mock_skill_gen = MagicMock()
    mock_skill_gen.generate_skill_md.return_value = (
        "---\nversion: 2.0.0\n---\n# Skill Document\n\nContent here."
    )
    mock_skill_gen.generate_skill_json.return_value = {
        "version": "2.0.0",
        "platform": "autonomous-scientific-research-platform",
        "protocol_files": {
            "skill_md": "http://test/protocol/skill.md",
            "heartbeat_md": "http://test/protocol/heartbeat.md",
        },
    }

    # Patch HeartbeatGenerator
    mock_heartbeat_gen = MagicMock()
    mock_heartbeat_gen.generate_heartbeat_md = AsyncMock(
        return_value="# Heartbeat\n\nStep 1...\nStep 5..."
    )

    # Patch VerifyGenerator
    mock_verify_gen = MagicMock()
    mock_verify_gen.generate_verify_md.return_value = (
        "# Verification Reference\n\nDomain details here."
    )

    # Patch ProtocolSigner to pass-through content
    mock_signer = MagicMock()
    mock_signer.sign_content.side_effect = lambda content, version: (content, "checksum123")

    patches.extend([
        patch("platform.api.protocol.api._skill_gen", mock_skill_gen),
        patch("platform.api.protocol.api._heartbeat_gen", mock_heartbeat_gen),
        patch("platform.api.protocol.api._verify_gen", mock_verify_gen),
        patch("platform.api.protocol.api._signer", mock_signer),
    ])

    # Patch database dependency
    mock_db = AsyncMock()
    patches.append(
        patch("platform.api.protocol.api.get_db", return_value=mock_db),
    )

    # Patch discovery functions (used by heartbeat.json endpoint)
    patches.extend([
        patch("platform.api.protocol.api._get_queue_depths", new_callable=AsyncMock, return_value={"mathematics": 5}),
        patch("platform.api.protocol.api._get_recent_stats", new_callable=AsyncMock, return_value={"claims_verified": 3}),
        patch("platform.api.protocol.api._get_system_stats", new_callable=AsyncMock, return_value=(10, 2)),
        patch("platform.api.protocol.api._get_open_frontiers", new_callable=AsyncMock, return_value=[]),
    ])

    started = [p.start() for p in patches]
    yield
    for p in patches:
        p.stop()


@pytest.fixture
def client(_patch_all_protocol_deps):
    """Create a FastAPI test client with the protocol router mounted."""
    from platform.api.protocol.api import router

    app = FastAPI()
    app.include_router(router, prefix="/protocol")

    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSkillMdEndpoint:
    """Tests for GET /protocol/skill.md."""

    def test_returns_text_markdown_content_type(self, client):
        """Response content-type must be text/markdown."""
        response = client.get("/protocol/skill.md")

        assert response.status_code == 200
        content_type = response.headers["content-type"]
        assert "text/markdown" in content_type

    def test_has_cache_headers(self, client):
        """Response must include Cache-Control and X-Skill-Version headers."""
        response = client.get("/protocol/skill.md")

        assert response.status_code == 200
        assert "Cache-Control" in response.headers
        assert "max-age=" in response.headers["Cache-Control"]
        assert "X-Skill-Version" in response.headers

    def test_has_checksum_header(self, client):
        """Response must include X-Content-Checksum header."""
        response = client.get("/protocol/skill.md")

        assert response.status_code == 200
        assert "X-Content-Checksum" in response.headers

    def test_has_nosniff_header(self, client):
        """Response must include X-Content-Type-Options: nosniff."""
        response = client.get("/protocol/skill.md")

        assert response.status_code == 200
        assert response.headers.get("X-Content-Type-Options") == "nosniff"


class TestSkillJsonEndpoint:
    """Tests for GET /protocol/skill.json."""

    def test_returns_json_with_version(self, client):
        """Response must be JSON containing a version field."""
        response = client.get("/protocol/skill.json")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data["version"] == "2.0.0"

    def test_returns_protocol_files(self, client):
        """Response must contain protocol_files mapping."""
        response = client.get("/protocol/skill.json")

        assert response.status_code == 200
        data = response.json()
        assert "protocol_files" in data


class TestHeartbeatMdEndpoint:
    """Tests for GET /protocol/heartbeat.md."""

    def test_returns_markdown(self, client):
        """Response must be markdown text."""
        response = client.get("/protocol/heartbeat.md")

        assert response.status_code == 200
        content_type = response.headers["content-type"]
        assert "text/markdown" in content_type

    def test_has_heartbeat_timestamp_header(self, client):
        """Response must include X-Heartbeat-Timestamp header."""
        response = client.get("/protocol/heartbeat.md")

        assert response.status_code == 200
        assert "X-Heartbeat-Timestamp" in response.headers

    def test_accepts_heartbeat_count_param(self, client):
        """Endpoint should accept heartbeat_count query parameter."""
        response = client.get("/protocol/heartbeat.md?heartbeat_count=5")

        assert response.status_code == 200


class TestVerifyMdEndpoint:
    """Tests for GET /protocol/verify.md."""

    def test_returns_markdown(self, client):
        """Response must be markdown text."""
        response = client.get("/protocol/verify.md")

        assert response.status_code == 200
        content_type = response.headers["content-type"]
        assert "text/markdown" in content_type

    def test_has_cache_headers(self, client):
        """Response must include Cache-Control header."""
        response = client.get("/protocol/verify.md")

        assert response.status_code == 200
        assert "Cache-Control" in response.headers

    def test_has_checksum_header(self, client):
        """Response must include X-Content-Checksum header."""
        response = client.get("/protocol/verify.md")

        assert response.status_code == 200
        assert "X-Content-Checksum" in response.headers

    def test_body_contains_verification_content(self, client):
        """Response body should contain verification reference text."""
        response = client.get("/protocol/verify.md")

        assert response.status_code == 200
        assert "Verification Reference" in response.text
