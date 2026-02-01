"""Integration tests for Experience API endpoints and schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ===========================================
# SCHEMA VALIDATION TESTS
# ===========================================


class TestLeaderboardEntrySchema:
    """Test that LeaderboardEntryResponse schema validates correctly."""

    def test_global_leaderboard_entry(self):
        from platform.experience.schemas import LeaderboardEntryResponse

        entry = LeaderboardEntryResponse(
            rank=1,
            agent_id=uuid4(),
            display_name="alpha-agent",
            global_level=42,
            tier="expert",
            total_xp=125000,
            domain_level=None,
        )
        assert entry.rank == 1
        assert entry.global_level == 42
        assert entry.domain_level is None

    def test_domain_leaderboard_entry_includes_domain_level(self):
        from platform.experience.schemas import LeaderboardEntryResponse

        entry = LeaderboardEntryResponse(
            rank=3,
            agent_id=uuid4(),
            display_name="math-wizard",
            global_level=30,
            tier="specialist",
            total_xp=85000,
            domain_level=28,
        )
        assert entry.domain_level == 28

    def test_leaderboard_entry_serialization(self):
        from platform.experience.schemas import LeaderboardEntryResponse

        agent_id = uuid4()
        entry = LeaderboardEntryResponse(
            rank=1,
            agent_id=agent_id,
            display_name=None,
            global_level=50,
            tier="master",
            total_xp=500000,
        )
        data = entry.model_dump()
        assert data["rank"] == 1
        assert data["agent_id"] == agent_id
        assert data["display_name"] is None
        assert data["domain_level"] is None


class TestPrestigeRequestSchema:
    """Test PrestigeRequest validation."""

    def test_valid_prestige_request(self):
        from platform.experience.schemas import PrestigeRequest

        req = PrestigeRequest(domain="mathematics")
        assert req.domain == "mathematics"

    def test_prestige_request_stores_domain(self):
        from platform.experience.schemas import PrestigeRequest

        for domain in ["mathematics", "ml_ai", "computational_biology", "materials_science", "bioinformatics"]:
            req = PrestigeRequest(domain=domain)
            assert req.domain == domain


class TestXPEventResponseSchema:
    """Test XPEventResponse schema structure."""

    def test_xp_event_response_fields(self):
        from platform.experience.schemas import XPEventResponse

        event_id = uuid4()
        agent_id = uuid4()
        source_id = uuid4()

        event = XPEventResponse(
            id=event_id,
            agent_id=agent_id,
            xp_amount=150,
            domain="ml_ai",
            role_category="execution",
            source_type="claim_verified",
            source_id=source_id,
            lab_slug="deep-learning-lab",
            multiplier=1.05,
            created_at=_utc_now(),
        )
        assert event.xp_amount == 150
        assert event.domain == "ml_ai"
        assert event.multiplier == 1.05
        assert event.source_id == source_id

    def test_xp_event_response_optional_fields(self):
        from platform.experience.schemas import XPEventResponse

        event = XPEventResponse(
            id=uuid4(),
            agent_id=uuid4(),
            xp_amount=50,
            domain=None,
            role_category=None,
            source_type="challenge_won",
            source_id=None,
            lab_slug=None,
            multiplier=1.0,
            created_at=_utc_now(),
        )
        assert event.domain is None
        assert event.source_id is None
        assert event.lab_slug is None


class TestAgentExperienceResponseSchema:
    """Test AgentExperienceResponse schema structure."""

    def test_full_experience_response(self):
        from platform.experience.schemas import AgentExperienceResponse, DomainXPDetail

        exp = AgentExperienceResponse(
            agent_id=uuid4(),
            total_xp=50000,
            global_level=25,
            tier="specialist",
            prestige_count=1,
            prestige_bonus=1.05,
            domains=[
                DomainXPDetail(domain="ml_ai", xp=30000, level=20, xp_to_next_level=2500),
                DomainXPDetail(domain="mathematics", xp=15000, level=12, xp_to_next_level=1800),
            ],
            role_xp={"theory": 10000, "execution": 30000, "review": 5000, "scouting": 3000, "coordination": 2000},
            last_xp_event_at=_utc_now(),
        )
        assert exp.global_level == 25
        assert len(exp.domains) == 2
        assert exp.domains[0].domain == "ml_ai"
        assert exp.prestige_bonus == 1.05

    def test_empty_experience_response(self):
        from platform.experience.schemas import AgentExperienceResponse

        exp = AgentExperienceResponse(
            agent_id=uuid4(),
            total_xp=0,
            global_level=1,
            tier="novice",
            prestige_count=0,
            prestige_bonus=1.0,
            domains=[],
            role_xp={},
            last_xp_event_at=None,
        )
        assert exp.total_xp == 0
        assert exp.last_xp_event_at is None
        assert exp.domains == []


class TestDeployerPortfolioResponseSchema:
    """Test DeployerPortfolioResponse schema."""

    def test_portfolio_response(self):
        from platform.experience.schemas import (
            AgentExperienceResponse,
            DeployerPortfolioResponse,
        )

        deployer_id = uuid4()
        agent_exp = AgentExperienceResponse(
            agent_id=uuid4(),
            total_xp=10000,
            global_level=10,
            tier="contributor",
            prestige_count=0,
            prestige_bonus=1.0,
            domains=[],
            role_xp={},
            last_xp_event_at=None,
        )
        portfolio = DeployerPortfolioResponse(
            deployer_id=deployer_id,
            display_name="Research Corp",
            portfolio_karma=5000,
            agent_count=3,
            tier="specialist",
            agents=[agent_exp],
        )
        assert portfolio.deployer_id == deployer_id
        assert portfolio.agent_count == 3
        assert len(portfolio.agents) == 1


# ===========================================
# MILESTONE SCHEMA TESTS
# ===========================================


class TestMilestoneResponseSchema:
    """Test MilestoneResponse schema."""

    def test_milestone_response_fields(self):
        from platform.experience.schemas import MilestoneResponse

        milestone = MilestoneResponse(
            milestone_slug="first_verified_claim",
            name="First Blood",
            description="Submit a claim that passes verification",
            category="verification",
            unlocked_at=_utc_now(),
            metadata={"claim_id": str(uuid4())},
        )
        assert milestone.milestone_slug == "first_verified_claim"
        assert milestone.name == "First Blood"
        assert milestone.category == "verification"

    def test_milestone_response_empty_metadata(self):
        from platform.experience.schemas import MilestoneResponse

        milestone = MilestoneResponse(
            milestone_slug="domain_10",
            name="Domain Journeyman",
            description="Reach level 10 in any domain",
            category="domain",
            unlocked_at=_utc_now(),
        )
        assert milestone.metadata == {}


# ===========================================
# API ENDPOINT TESTS
# ===========================================


class TestExperienceAPIEndpoints:
    """Integration tests for experience router endpoints."""

    @pytest.mark.asyncio
    async def test_get_agent_experience_returns_profile(self):
        """GET /experience/agents/{id}/experience should return experience profile."""
        from platform.experience.api import get_agent_experience

        mock_session = AsyncMock()
        agent_id = uuid4()

        exp_response = AgentExperienceResponse(
            agent_id=agent_id,
            total_xp=25000,
            global_level=15,
            tier="contributor",
            prestige_count=0,
            prestige_bonus=1.0,
            domains=[],
            role_xp={},
            last_xp_event_at=None,
        )

        with patch("platform.experience.api.ExperienceService") as MockService:
            mock_svc = MagicMock()
            mock_svc.get_experience = AsyncMock(return_value=exp_response)
            MockService.return_value = mock_svc

            result = await get_agent_experience(agent_id=agent_id, db=mock_session)

        assert result.agent_id == agent_id
        assert result.global_level == 15

    @pytest.mark.asyncio
    async def test_get_global_leaderboard_returns_entries(self):
        """GET /experience/leaderboard/global should return ranked entries."""
        from platform.experience.api import get_global_leaderboard

        mock_session = AsyncMock()

        entries = [
            LeaderboardEntryResponse(
                rank=1,
                agent_id=uuid4(),
                display_name="top-agent",
                global_level=50,
                tier="master",
                total_xp=500000,
            ),
            LeaderboardEntryResponse(
                rank=2,
                agent_id=uuid4(),
                display_name="second-agent",
                global_level=45,
                tier="expert",
                total_xp=400000,
            ),
        ]

        with patch("platform.experience.api.LeaderboardService") as MockService:
            mock_svc = MagicMock()
            mock_svc.get_global_leaderboard = AsyncMock(return_value=entries)
            MockService.return_value = mock_svc

            result = await get_global_leaderboard(limit=20, db=mock_session)

        assert len(result) == 2
        assert result[0].rank == 1
        assert result[0].global_level == 50

    @pytest.mark.asyncio
    async def test_get_domain_leaderboard_validates_domain(self):
        """GET /experience/leaderboard/domain/{domain} should reject invalid domains."""
        from platform.experience.api import get_domain_leaderboard
        from fastapi import HTTPException

        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_domain_leaderboard(domain="invalid_domain", limit=20, db=mock_session)

        assert exc_info.value.status_code == 400
        assert "Invalid domain" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_prestige_validates_domain(self):
        """POST /experience/agents/{id}/prestige should reject invalid domains."""
        from platform.experience.api import prestige_agent
        from platform.experience.schemas import PrestigeRequest
        from fastapi import HTTPException

        mock_session = AsyncMock()
        agent_id = uuid4()
        body = PrestigeRequest(domain="invalid_domain")

        with pytest.raises(HTTPException) as exc_info:
            await prestige_agent(agent_id=agent_id, body=body, db=mock_session)

        assert exc_info.value.status_code == 400
        assert "Invalid domain" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_prestige_with_valid_domain(self):
        """POST /experience/agents/{id}/prestige should call service for valid domain."""
        from platform.experience.api import prestige_agent
        from platform.experience.schemas import PrestigeRequest

        mock_session = AsyncMock()
        agent_id = uuid4()
        body = PrestigeRequest(domain="mathematics")

        prestige_response = {
            "agent_id": str(agent_id),
            "domain": "mathematics",
            "prestige_count": 1,
            "prestige_bonus": 1.05,
        }

        with patch("platform.experience.api.ExperienceService") as MockService:
            mock_svc = MagicMock()
            mock_svc.prestige = AsyncMock(return_value=prestige_response)
            MockService.return_value = mock_svc

            result = await prestige_agent(agent_id=agent_id, body=body, db=mock_session)

        assert result["prestige_count"] == 1
        assert result["prestige_bonus"] == 1.05


# ===========================================
# XP WORKER STRUCTURAL TESTS
# ===========================================


class TestXPWorkerStructure:
    """Test XP worker configuration and structure."""

    def test_xp_worker_has_correct_topics(self):
        """XPWorker should subscribe to the expected Kafka topics."""
        from platform.workers.xp_worker import XPWorker

        expected_topics = [
            "verification.results",
            "claims",
            "frontiers",
            "roundtable.proposals",
            "roundtable.reviews",
            "challenges",
        ]
        assert XPWorker.TOPICS == expected_topics

    def test_xp_worker_initial_state(self):
        """XPWorker should initialize with correct defaults."""
        with patch("platform.workers.xp_worker.KafkaConsumer"):
            from platform.workers.xp_worker import XPWorker
            worker = XPWorker()

            assert worker.running is False
            assert worker._messages_processed == 0
            assert worker._errors_count == 0
            assert worker._started_at is None

    def test_xp_worker_health_status(self):
        """get_health_status should return monitoring data."""
        with patch("platform.workers.xp_worker.KafkaConsumer"):
            from platform.workers.xp_worker import XPWorker
            worker = XPWorker()

            status = worker.get_health_status()

            assert status["healthy"] is False
            assert status["messages_processed"] == 0
            assert status["errors_count"] == 0
            assert status["started_at"] is None
            assert "topics" in status


# Need to import these for use in test methods above
from platform.experience.schemas import (
    AgentExperienceResponse,
    LeaderboardEntryResponse,
)
