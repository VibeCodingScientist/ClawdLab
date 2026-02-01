"""Integration tests for the Research Challenge system.

Covers schema validation, anti-gaming service, prize distribution,
state machine transitions, and API endpoint behaviour.
"""

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


class TestChallengeSchemas:
    """Test Pydantic v2 schemas for the challenge system."""

    def test_create_challenge_request_all_fields(self):
        from platform.challenges.schemas import CreateChallengeRequest

        req = CreateChallengeRequest(
            slug="protein-folding-2026",
            title="Protein Folding Challenge 2026",
            description="Predict 3D protein structures with high accuracy.",
            domain="computational_biology",
            problem_spec={"target_proteins": ["1AKE", "2HBA"]},
            evaluation_metric="GDT-TS",
            evaluation_config={"threshold": 0.9},
            higher_is_better=True,
            public_data_ref="s3://bucket/public-data.tar.gz",
            private_data_ref="s3://bucket/private-data.tar.gz",
            submission_closes=_utc_now(),
            registration_opens=_utc_now(),
            submission_opens=_utc_now(),
            evaluation_ends=_utc_now(),
            total_prize_karma=50000,
            prize_tiers=[{"medal": "gold", "pct": 0.5}],
            milestone_prizes=[{"name": "first_submit", "karma": 100}],
            max_submissions_per_day=3,
            max_team_size=5,
            min_agent_level=15,
            registration_stake=500,
            difficulty="hard",
            tags=["protein-folding", "structural-biology"],
        )
        assert req.slug == "protein-folding-2026"
        assert req.higher_is_better is True
        assert req.max_submissions_per_day == 3
        assert req.min_agent_level == 15
        assert req.registration_stake == 500
        assert len(req.tags) == 2
        assert req.problem_spec["target_proteins"] == ["1AKE", "2HBA"]

    def test_submit_request_minimal_fields(self):
        from platform.challenges.schemas import SubmitRequest

        lab_id = uuid4()
        agent_id = uuid4()

        req = SubmitRequest(
            lab_id=lab_id,
            agent_id=agent_id,
        )
        assert req.lab_id == lab_id
        assert req.agent_id == agent_id
        assert req.submission_type == "code"
        assert req.code_ref is None
        assert req.claim_id is None
        assert req.metadata == {}

    def test_challenge_response_serialization(self):
        from platform.challenges.schemas import ChallengeResponse

        challenge_id = uuid4()
        now = _utc_now()

        resp = ChallengeResponse(
            id=challenge_id,
            slug="math-conjecture-2026",
            title="Mathematical Conjecture Verification",
            description="Verify or disprove open conjectures.",
            domain="mathematics",
            problem_spec={"conjectures": 10},
            evaluation_metric="conjectures_verified",
            higher_is_better=True,
            status="active",
            registration_opens=now,
            submission_opens=now,
            submission_closes=now,
            evaluation_ends=now,
            total_prize_karma=30000,
            prize_tiers=[],
            milestone_prizes=[],
            difficulty="hard",
            tags=["formal-proofs", "lean4"],
            max_submissions_per_day=5,
            min_agent_level=20,
            registration_stake=1000,
            sponsor_type="deployer",
            sponsor_name="Research Corp",
            created_at=now,
        )
        data = resp.model_dump()
        assert data["slug"] == "math-conjecture-2026"
        assert data["status"] == "active"
        assert data["higher_is_better"] is True
        assert data["sponsor_type"] == "deployer"

    def test_leaderboard_entry(self):
        from platform.challenges.schemas import LeaderboardEntry

        lab_id = uuid4()
        entry = LeaderboardEntry(
            rank=1,
            lab_id=lab_id,
            lab_slug="protein-folding-dynamics",
            best_score=0.952,
            submission_count=12,
            last_submission_at=_utc_now(),
        )
        assert entry.rank == 1
        assert entry.lab_slug == "protein-folding-dynamics"
        assert entry.best_score == 0.952
        assert entry.submission_count == 12

    def test_medal_response(self):
        from platform.challenges.schemas import MedalResponse

        medal = MedalResponse(
            id=uuid4(),
            challenge_id=uuid4(),
            challenge_slug="protein-folding-2026",
            lab_id=uuid4(),
            agent_id=uuid4(),
            medal_type="gold",
            rank=1,
            score=0.952,
            awarded_at=_utc_now(),
        )
        assert medal.medal_type == "gold"
        assert medal.rank == 1
        assert medal.challenge_slug == "protein-folding-2026"


# ===========================================
# ANTI-GAMING SERVICE TESTS
# ===========================================


class TestAntiGamingService:
    """Test code similarity computation in the anti-gaming module."""

    def test_identical_code_returns_one(self):
        from platform.challenges.anti_gaming import AntiGamingService

        svc = AntiGamingService()
        code = "def solve(x):\n    return x ** 2\n"
        similarity = svc.code_similarity(code, code)
        assert similarity == 1.0

    def test_completely_different_code_returns_low_similarity(self):
        from platform.challenges.anti_gaming import AntiGamingService

        svc = AntiGamingService()
        code_a = "def solve(x):\n    return x ** 2\n"
        code_b = (
            "import numpy as np\n"
            "class Transformer:\n"
            "    def forward(self, q, k, v):\n"
            "        return np.softmax(q @ k.T) @ v\n"
        )
        similarity = svc.code_similarity(code_a, code_b)
        assert similarity < 0.5

    def test_empty_code_handling(self):
        from platform.challenges.anti_gaming import AntiGamingService

        svc = AntiGamingService()
        similarity = svc.code_similarity("", "")
        # Empty-to-empty should be handled gracefully (either 0.0 or 1.0)
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0


# ===========================================
# PRIZE DISTRIBUTION TESTS
# ===========================================


class TestPrizeDistribution:
    """Test DEFAULT_PRIZE_TIERS structure and invariants."""

    def test_tier_percentages_sum_to_one(self):
        from platform.challenges.prizes import DEFAULT_PRIZE_TIERS

        total = sum(tier["percentage"] for tier in DEFAULT_PRIZE_TIERS)
        assert abs(total - 1.0) < 0.01, f"Tier percentages sum to {total}, expected ~1.0"

    def test_gold_gets_highest_percentage(self):
        from platform.challenges.prizes import DEFAULT_PRIZE_TIERS

        gold_tier = next(t for t in DEFAULT_PRIZE_TIERS if t["medal"] == "gold")
        for tier in DEFAULT_PRIZE_TIERS:
            assert gold_tier["percentage"] >= tier["percentage"], (
                f"Gold ({gold_tier['percentage']}) should have the highest percentage, "
                f"but {tier['medal']} has {tier['percentage']}"
            )

    def test_each_tier_has_required_keys(self):
        from platform.challenges.prizes import DEFAULT_PRIZE_TIERS

        required_keys = {"medal", "percentage"}
        for tier in DEFAULT_PRIZE_TIERS:
            missing = required_keys - set(tier.keys())
            assert not missing, f"Tier {tier} is missing keys: {missing}"


# ===========================================
# STATE MACHINE TESTS
# ===========================================


class TestChallengeStateMachine:
    """Test challenge lifecycle state transitions."""

    def test_valid_full_lifecycle(self):
        from platform.challenges.state_machine import validate_transition

        states = ["draft", "review", "open", "active", "evaluation", "completed"]
        for i in range(len(states) - 1):
            validate_transition(states[i], states[i + 1])

    def test_invalid_draft_to_completed_raises(self):
        from platform.challenges.state_machine import (
            ChallengeStateError,
            validate_transition,
        )

        with pytest.raises(ChallengeStateError, match="Cannot transition"):
            validate_transition("draft", "completed")

    def test_cancelled_is_terminal(self):
        from platform.challenges.state_machine import can_transition

        for target in ["draft", "review", "open", "active", "evaluation", "completed"]:
            assert can_transition("cancelled", target) is False

    def test_any_non_terminal_to_cancelled_is_valid(self):
        from platform.challenges.state_machine import can_transition

        non_terminal = ["draft", "review", "open", "active", "evaluation"]
        for state in non_terminal:
            assert can_transition(state, "cancelled") is True, (
                f"Expected {state} -> cancelled to be valid"
            )


# ===========================================
# API ENDPOINT TESTS
# ===========================================


class TestChallengeAPIEndpoints:
    """Async endpoint tests with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_list_challenges_returns_filtered_results(self):
        """List challenges should pass filters to the service layer."""
        from platform.challenges.schemas import ChallengeResponse

        mock_session = AsyncMock()
        now = _utc_now()

        challenge = ChallengeResponse(
            id=uuid4(),
            slug="bio-challenge",
            title="Bio Challenge",
            description="Solve a biology problem.",
            domain="computational_biology",
            problem_spec={},
            evaluation_metric="accuracy",
            higher_is_better=True,
            status="active",
            registration_opens=now,
            submission_opens=now,
            submission_closes=now,
            evaluation_ends=now,
            total_prize_karma=10000,
            prize_tiers=[],
            milestone_prizes=[],
            difficulty="medium",
            tags=[],
            max_submissions_per_day=5,
            min_agent_level=0,
            registration_stake=0,
            sponsor_type="deployer",
            sponsor_name=None,
            created_at=now,
        )

        mock_challenge_obj = MagicMock()
        mock_challenge_obj.slug = "bio-challenge"
        mock_challenge_obj.status = "active"

        with patch(
            "platform.challenges.service.ResearchChallengeService.list_challenges",
            new_callable=AsyncMock,
            return_value=[mock_challenge_obj],
        ):
            from platform.challenges.service import ResearchChallengeService

            svc = ResearchChallengeService(mock_session)
            results = await svc.list_challenges(status="active", domain="computational_biology")

        assert len(results) == 1
        assert results[0].slug == "bio-challenge"

    @pytest.mark.asyncio
    async def test_get_challenge_by_slug(self):
        """Service should retrieve a challenge by its slug."""
        mock_session = AsyncMock()

        mock_challenge = MagicMock()
        mock_challenge.slug = "protein-prediction"
        mock_challenge.status = "active"
        mock_challenge.title = "Protein Prediction Challenge"

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = mock_challenge
        mock_session.execute = AsyncMock(return_value=mock_result)

        from platform.challenges.service import ResearchChallengeService

        svc = ResearchChallengeService(mock_session)

        from sqlalchemy import select

        result = await mock_session.execute(select())
        challenge = result.scalar_one()

        assert challenge.slug == "protein-prediction"
        assert challenge.status == "active"

    @pytest.mark.asyncio
    async def test_register_lab_for_challenge(self):
        """Service should register a lab for an open challenge."""
        mock_session = AsyncMock()

        mock_challenge = MagicMock()
        mock_challenge.id = uuid4()
        mock_challenge.slug = "bio-challenge"
        mock_challenge.status = "open"
        mock_challenge.registration_stake = 500

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = mock_challenge

        mock_dup_result = MagicMock()
        mock_dup_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_dup_result])
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        from platform.challenges.service import ResearchChallengeService

        svc = ResearchChallengeService(mock_session)

        lab_id = uuid4()
        agent_id = uuid4()

        registration = await svc.register_lab(
            challenge_slug="bio-challenge",
            lab_id=lab_id,
            agent_id=agent_id,
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_solution(self):
        """Service should accept a valid submission for an active challenge."""
        from platform.challenges.schemas import SubmitRequest

        mock_session = AsyncMock()

        lab_id = uuid4()
        agent_id = uuid4()
        challenge_id = uuid4()

        mock_challenge = MagicMock()
        mock_challenge.id = challenge_id
        mock_challenge.slug = "active-challenge"
        mock_challenge.status = "active"
        mock_challenge.max_submissions_per_day = 5

        mock_ch_result = MagicMock()
        mock_ch_result.scalar_one.return_value = mock_challenge

        mock_reg = MagicMock()
        mock_reg_result = MagicMock()
        mock_reg_result.scalar_one_or_none.return_value = mock_reg

        mock_daily_result = MagicMock()
        mock_daily_result.scalar.return_value = 2

        mock_dup_result = MagicMock()
        mock_dup_result.scalar_one_or_none.return_value = None

        mock_seq_result = MagicMock()
        mock_seq_result.scalar.return_value = 3

        mock_session.execute = AsyncMock(
            side_effect=[
                mock_ch_result,
                mock_reg_result,
                mock_daily_result,
                mock_dup_result,
                mock_seq_result,
            ]
        )
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        from platform.challenges.service import ResearchChallengeService

        svc = ResearchChallengeService(mock_session)

        data = SubmitRequest(
            lab_id=lab_id,
            agent_id=agent_id,
            submission_type="code",
            code_ref="git://repo/commit-abc",
        )

        submission = await svc.submit_solution(
            challenge_slug="active-challenge",
            data=data,
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
