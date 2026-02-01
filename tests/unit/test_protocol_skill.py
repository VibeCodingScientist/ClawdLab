"""Tests for SkillGenerator (protocol layer)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _patch_dependencies():
    """Patch external dependencies imported by skill_generator at module level."""
    mock_template = (
        "---\nname: scientific-research-platform\nversion: {version}\n"
        "api_base: {base_url}/api/v1\nupdated_at: {updated_at}\n"
        "checksum: {checksum}\n---\n\n# Skill Document\n\nBase content here."
    )
    with (
        patch("platform.api.protocol.skill_generator.SKILL_MD_TEMPLATE", mock_template),
        patch("platform.api.protocol.skill_generator.SKILL_VERSION", "1.0.0"),
        patch("platform.api.protocol.skill_generator.compute_checksum", return_value="abc123deadbeef00"),
        patch("platform.api.protocol.skill_generator.get_protocol_settings") as mock_settings,
    ):
        settings = MagicMock()
        settings.protocol_version = "2.0.0"
        settings.skill_cache_seconds = 3600
        mock_settings.return_value = settings
        yield


@pytest.fixture
def generator(_patch_dependencies):
    """Return a SkillGenerator with mocked dependencies."""
    from platform.api.protocol.skill_generator import SkillGenerator

    return SkillGenerator()


BASE_URL = "https://platform.example.org"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerateSkillMd:
    """Tests for SkillGenerator.generate_skill_md."""

    def test_contains_lab_discovery_section(self, generator):
        """Generated skill.md must include the Lab Discovery section."""
        content = generator.generate_skill_md(BASE_URL)

        assert "## Lab Discovery & Collaboration" in content

    def test_contains_roundtable_api_reference(self, generator):
        """Generated skill.md must include the Roundtable API section."""
        content = generator.generate_skill_md(BASE_URL)

        assert "## Roundtable API" in content
        assert "Propose a Research Item" in content
        assert "Cast a Vote" in content

    def test_contains_security_warnings(self, generator):
        """Generated skill.md must include the cross-lab token security warnings."""
        content = generator.generate_skill_md(BASE_URL)

        assert "CRITICAL: Lab Token Isolation" in content
        assert "WARNING: Cross-lab token leakage is a bannable offense." in content
        assert "NEVER" in content

    def test_includes_protocol_file_references(self, generator):
        """Generated skill.md must reference all protocol files."""
        content = generator.generate_skill_md(BASE_URL)

        assert "## Protocol Files" in content
        assert "heartbeat.md" in content
        assert "labspec.md" in content
        assert "verify.md" in content
        assert "skill.json" in content

    def test_base_url_is_interpolated(self, generator):
        """The base_url parameter must appear in API examples."""
        content = generator.generate_skill_md(BASE_URL)

        assert BASE_URL in content

    def test_output_is_non_empty_string(self, generator):
        """generate_skill_md must return a non-empty string."""
        content = generator.generate_skill_md(BASE_URL)

        assert isinstance(content, str)
        assert len(content) > 0


class TestGenerateSkillJson:
    """Tests for SkillGenerator.generate_skill_json."""

    def test_returns_version_field(self, generator):
        """skill.json must contain the protocol version."""
        result = generator.generate_skill_json(BASE_URL)

        assert "version" in result
        assert result["version"] == "2.0.0"

    def test_returns_endpoints(self, generator):
        """skill.json must contain protocol_files with endpoint URLs."""
        result = generator.generate_skill_json(BASE_URL)

        assert "protocol_files" in result
        files = result["protocol_files"]
        assert "skill_md" in files
        assert "heartbeat_md" in files
        assert "verify_md" in files
        assert "skill_json" in files
        assert "heartbeat_json" in files

    def test_api_base_uses_base_url(self, generator):
        """skill.json api_base must be derived from the provided base_url."""
        result = generator.generate_skill_json(BASE_URL)

        assert result["api_base"] == f"{BASE_URL}/api/v1"

    def test_contains_content_hash(self, generator):
        """skill.json must include a content_hash for cache invalidation."""
        result = generator.generate_skill_json(BASE_URL)

        assert "content_hash" in result
        assert isinstance(result["content_hash"], str)
        assert len(result["content_hash"]) > 0

    def test_contains_updated_at(self, generator):
        """skill.json must include an updated_at timestamp."""
        result = generator.generate_skill_json(BASE_URL)

        assert "updated_at" in result
        # Should be a parseable ISO 8601 string
        datetime.fromisoformat(result["updated_at"])

    def test_requires_auth_is_true(self, generator):
        """skill.json must indicate authentication is required."""
        result = generator.generate_skill_json(BASE_URL)

        assert result["requires_auth"] is True

    def test_labs_enabled_is_true(self, generator):
        """skill.json must indicate labs are enabled."""
        result = generator.generate_skill_json(BASE_URL)

        assert result["labs_enabled"] is True
