"""Tests for HeartbeatGenerator (protocol layer)."""

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
    """Patch external dependencies imported by heartbeat_generator at module level."""
    with (
        patch("platform.api.protocol.heartbeat_generator._get_queue_depths", new_callable=AsyncMock) as mock_qd,
        patch("platform.api.protocol.heartbeat_generator._get_recent_stats", new_callable=AsyncMock) as mock_rs,
        patch("platform.api.protocol.heartbeat_generator._get_system_stats", new_callable=AsyncMock) as mock_ss,
        patch("platform.api.protocol.heartbeat_generator._get_open_frontiers", new_callable=AsyncMock) as mock_of,
        patch("platform.api.protocol.heartbeat_generator.get_protocol_settings") as mock_settings,
    ):
        mock_qd.return_value = {"mathematics": 5, "ml_ai": 3}
        mock_rs.return_value = {
            "claims_verified": 10,
            "claims_failed": 2,
            "challenges_resolved": 1,
            "frontiers_solved": 0,
        }
        mock_ss.return_value = (42, 7)  # active_agents, active_jobs
        mock_of.return_value = []  # no open frontiers

        settings = MagicMock()
        settings.protocol_version = "2.0.0"
        settings.heartbeat_cache_seconds = 60
        settings.heartbeat_lab_scan_interval = 4
        mock_settings.return_value = settings

        yield


@pytest.fixture
def generator(_patch_dependencies):
    """Return a HeartbeatGenerator with mocked dependencies."""
    from platform.api.protocol.heartbeat_generator import HeartbeatGenerator

    return HeartbeatGenerator()


@pytest.fixture
def mock_db():
    """Return a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


BASE_URL = "https://platform.example.org"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFiveStepProtocol:
    """Verify that the 5-step protocol sections appear in output."""

    @pytest.mark.asyncio
    async def test_step1_check_updates(self, generator, mock_db):
        """Output must include Step 1: Check for Skill Updates."""
        content = await generator.generate_heartbeat_md(mock_db, base_url=BASE_URL)

        assert "## Step 1: Check for Skill Updates" in content

    @pytest.mark.asyncio
    async def test_step2_check_notifications(self, generator, mock_db):
        """Output must include Step 2: Check Notifications."""
        content = await generator.generate_heartbeat_md(mock_db, base_url=BASE_URL)

        assert "## Step 2: Check Notifications" in content

    @pytest.mark.asyncio
    async def test_step3_check_research(self, generator, mock_db):
        """Output must include Step 3: Check Active Research."""
        content = await generator.generate_heartbeat_md(mock_db, base_url=BASE_URL)

        assert "## Step 3: Check Active Research" in content

    @pytest.mark.asyncio
    async def test_step4_scan_labs(self, generator, mock_db):
        """Output must include Step 4: Scan for New Labs."""
        content = await generator.generate_heartbeat_md(mock_db, base_url=BASE_URL)

        assert "## Step 4: Scan for New Labs" in content

    @pytest.mark.asyncio
    async def test_step5_decision_point(self, generator, mock_db):
        """Output must include Step 5: Decision Point with response codes."""
        content = await generator.generate_heartbeat_md(mock_db, base_url=BASE_URL)

        assert "## Step 5: Decision Point" in content
        assert "HEARTBEAT_OK" in content
        assert "HEARTBEAT_WORKING" in content
        assert "HEARTBEAT_SUBMITTED" in content
        assert "HEARTBEAT_ESCALATE" in content


class TestRolePersonalization:
    """Verify that role-specific actions appear for different archetypes."""

    @pytest.mark.asyncio
    async def test_theorist_gets_propose_and_debate_actions(self, generator, mock_db):
        """A theorist should see propose/debate guidance in step 3."""
        content = await generator.generate_heartbeat_md(
            mock_db,
            agent_id=str(uuid4()),
            base_url=BASE_URL,
            agent_role="theorist",
        )

        assert "Actions for `theorist`" in content
        assert "proposed" in content.lower() or "under_debate" in content.lower()
        assert "Propose new research items" in content

    @pytest.mark.asyncio
    async def test_experimentalist_gets_claim_work_actions(self, generator, mock_db):
        """An experimentalist should see claim work / submit results guidance."""
        content = await generator.generate_heartbeat_md(
            mock_db,
            agent_id=str(uuid4()),
            base_url=BASE_URL,
            agent_role="experimentalist",
        )

        assert "Actions for `experimentalist`" in content
        assert "assign-work" in content
        assert "Submit results" in content

    @pytest.mark.asyncio
    async def test_critic_gets_review_actions(self, generator, mock_db):
        """A critic should see review/challenge guidance."""
        content = await generator.generate_heartbeat_md(
            mock_db,
            agent_id=str(uuid4()),
            base_url=BASE_URL,
            agent_role="critic",
        )

        assert "Actions for `critic`" in content
        assert "challenge" in content.lower()

    @pytest.mark.asyncio
    async def test_unknown_role_falls_back_to_generalist(self, generator, mock_db):
        """An unknown role should fall back to generalist actions."""
        content = await generator.generate_heartbeat_md(
            mock_db,
            agent_id=str(uuid4()),
            base_url=BASE_URL,
            agent_role="unknown_role",
        )

        assert "Actions for `unknown_role`" in content
        # generalist actions contain "Check all active research items"
        assert "Check all active research items" in content


class TestLabScanInterval:
    """Verify the lab scan triggers at the correct heartbeat intervals."""

    @pytest.mark.asyncio
    async def test_lab_scan_triggers_at_interval_zero(self, generator, mock_db):
        """heartbeat_count=0 (modulo interval == 0) triggers scan."""
        content = await generator.generate_heartbeat_md(
            mock_db,
            heartbeat_count=0,
            base_url=BASE_URL,
        )

        assert "lab scan triggered" in content.lower()
        assert "labs/discover" in content

    @pytest.mark.asyncio
    async def test_lab_scan_triggers_at_multiple(self, generator, mock_db):
        """heartbeat_count=4 triggers scan (4 % 4 == 0)."""
        content = await generator.generate_heartbeat_md(
            mock_db,
            heartbeat_count=4,
            base_url=BASE_URL,
        )

        assert "lab scan triggered" in content.lower()

    @pytest.mark.asyncio
    async def test_lab_scan_skipped_between_intervals(self, generator, mock_db):
        """heartbeat_count=1 should skip lab scan (1 % 4 != 0)."""
        content = await generator.generate_heartbeat_md(
            mock_db,
            heartbeat_count=1,
            base_url=BASE_URL,
        )

        assert "Lab scan skipped" in content
        assert "labs/discover" not in content

    @pytest.mark.asyncio
    async def test_lab_scan_skipped_shows_remaining_count(self, generator, mock_db):
        """Skipped lab scan should indicate how many heartbeats until next scan."""
        content = await generator.generate_heartbeat_md(
            mock_db,
            heartbeat_count=2,
            base_url=BASE_URL,
        )

        # 4 - (2 % 4) = 2 heartbeats remaining
        assert "2 heartbeat(s)" in content


class TestRoleCard:
    """Verify the Role Card section is conditionally rendered."""

    @pytest.mark.asyncio
    async def test_role_card_rendered_when_agent_id_provided(self, generator, mock_db):
        """Role Card section appears when agent_id and agent_role are given."""
        agent_id = str(uuid4())
        content = await generator.generate_heartbeat_md(
            mock_db,
            agent_id=agent_id,
            base_url=BASE_URL,
            agent_role="theorist",
        )

        assert "## Your Role Card" in content
        assert agent_id in content
        assert "`theorist`" in content

    @pytest.mark.asyncio
    async def test_role_card_not_rendered_without_agent_id(self, generator, mock_db):
        """Role Card section must NOT appear when agent_id is None."""
        content = await generator.generate_heartbeat_md(
            mock_db,
            agent_id=None,
            base_url=BASE_URL,
            agent_role="theorist",
        )

        assert "## Your Role Card" not in content


class TestLiveStats:
    """Verify that live statistics appear in the output."""

    @pytest.mark.asyncio
    async def test_live_stats_section_included(self, generator, mock_db):
        """Output must include the Live Statistics section with queue data."""
        content = await generator.generate_heartbeat_md(mock_db, base_url=BASE_URL)

        assert "## Live Statistics" in content
        assert "Verification Queue by Domain" in content
        assert "mathematics" in content
        assert "Recent Activity (Last Hour)" in content
