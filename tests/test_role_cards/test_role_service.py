"""Tests for role_service — compute_level, compute_tier, get_role_card."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.role_service import compute_level, compute_tier, get_role_card


class TestComputeLevel:
    """Test log2 level calculation at boundary values."""

    def test_zero_rep(self):
        assert compute_level(0) == 1

    def test_one_rep(self):
        assert compute_level(1) == 2

    def test_three_rep(self):
        assert compute_level(3) == 3

    def test_fifteen_rep(self):
        assert compute_level(15) == 5

    def test_sixtythree_rep(self):
        assert compute_level(63) == 7

    def test_fiveeleven_rep(self):
        assert compute_level(511) == 10

    def test_max_level_cap(self):
        assert compute_level(16383) == 15

    def test_above_max_cap(self):
        assert compute_level(100000) == 15

    def test_negative_rep(self):
        assert compute_level(-10) == 1

    def test_fractional_rep(self):
        assert compute_level(0.5) == 1


class TestComputeTier:
    """Test tier boundaries."""

    def test_junior_zero(self):
        assert compute_tier(0) == "junior"

    def test_junior_twentynine(self):
        assert compute_tier(29) == "junior"

    def test_established_thirty(self):
        assert compute_tier(30) == "established"

    def test_established_ninetynine(self):
        assert compute_tier(99) == "established"

    def test_senior_hundred(self):
        assert compute_tier(100) == "senior"

    def test_senior_high(self):
        assert compute_tier(5000) == "senior"


class TestGetRoleCard:
    """Test role card lookup with mocked Redis and DB."""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """When Redis has the card cached, should return it without DB query."""
        cached_data = json.dumps({
            "role": "scout",
            "domain": "Literature discovery",
            "inputs": [],
            "outputs": [],
            "hard_bans": ["No fabricating citations."],
            "escalation": [],
            "task_types_allowed": ["literature_review"],
            "can_initiate_voting": False,
            "can_assign_tasks": False,
            "definition_of_done": [],
        })

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=cached_data)

        mock_db = AsyncMock()

        with patch("backend.services.role_service.get_redis", return_value=mock_redis):
            card = await get_role_card(mock_db, "scout")

        assert card is not None
        assert card.role == "scout"
        assert card.task_types_allowed == ["literature_review"]
        assert card.can_initiate_voting is False
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_db_hit(self):
        """When Redis misses but DB has the card, should fetch and cache."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        mock_card = MagicMock()
        mock_card.role = "pi"
        mock_card.domain = "Lab governance"
        mock_card.inputs = []
        mock_card.outputs = []
        mock_card.hard_bans = []
        mock_card.escalation = []
        mock_card.task_types_allowed = []
        mock_card.can_initiate_voting = True
        mock_card.can_assign_tasks = True
        mock_card.definition_of_done = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_card
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("backend.services.role_service.get_redis", return_value=mock_redis):
            card = await get_role_card(mock_db, "pi")

        assert card is not None
        assert card.role == "pi"
        assert card.can_initiate_voting is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_role(self):
        """Unknown role should return None."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("backend.services.role_service.get_redis", return_value=mock_redis):
            card = await get_role_card(mock_db, "nonexistent")

        assert card is None

    @pytest.mark.asyncio
    async def test_redis_unavailable_falls_back_to_db(self):
        """When Redis is unavailable, should fall back to DB."""
        mock_card = MagicMock()
        mock_card.role = "scout"
        mock_card.domain = "Literature"
        mock_card.inputs = []
        mock_card.outputs = []
        mock_card.hard_bans = []
        mock_card.escalation = []
        mock_card.task_types_allowed = ["literature_review"]
        mock_card.can_initiate_voting = False
        mock_card.can_assign_tasks = False
        mock_card.definition_of_done = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_card
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("backend.services.role_service.get_redis", side_effect=RuntimeError("Redis not initialized")):
            card = await get_role_card(mock_db, "scout")

        assert card is not None
        assert card.role == "scout"
