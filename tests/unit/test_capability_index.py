"""Tests for CapabilityIndex."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestCapabilityIndex:
    """Tests for CapabilityIndex agent-lab matching."""

    def _make_session(self) -> AsyncMock:
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_match_agent_to_labs_returns_ranked_list(self):
        """match_agent_to_labs should return a list of lab dicts sorted
        by match_score descending."""
        from platform.feed.capability_index import CapabilityIndex

        session = self._make_session()
        agent_id = uuid4()

        # Mock agent capabilities
        cap1 = MagicMock()
        cap1.agent_id = agent_id
        cap1.domain = "ml_ai"
        cap1.capability_level = "expert"

        cap2 = MagicMock()
        cap2.agent_id = agent_id
        cap2.domain = "mathematics"
        cap2.capability_level = "intermediate"

        caps_result = MagicMock()
        caps_result.scalars.return_value.all.return_value = [cap1, cap2]

        # Mock member lab IDs (agent is not in any lab)
        member_result = MagicMock()
        member_result.scalars.return_value.all.return_value = []

        # Mock labs
        lab1 = MagicMock()
        lab1.id = uuid4()
        lab1.slug = "ml-research"
        lab1.name = "ML Research Lab"
        lab1.domains = ["ml_ai", "mathematics"]
        lab1.archived_at = None
        lab1.visibility = "public"
        lab1.karma_requirement = 50

        lab2 = MagicMock()
        lab2.id = uuid4()
        lab2.slug = "pure-math"
        lab2.name = "Pure Math Lab"
        lab2.domains = ["mathematics"]
        lab2.archived_at = None
        lab2.visibility = "public"
        lab2.karma_requirement = 30

        labs_result = MagicMock()
        labs_result.scalars.return_value.all.return_value = [lab1, lab2]

        session.execute.side_effect = [caps_result, member_result, labs_result]

        with patch(
            "platform.feed.capability_index.RoleCardRepository"
        ) as MockRCRepo:
            mock_rc_repo = MagicMock()
            mock_rc_repo.get_unfilled = AsyncMock(return_value=[])
            MockRCRepo.return_value = mock_rc_repo

            index = CapabilityIndex(session)
            results = await index.match_agent_to_labs(str(agent_id))

        assert isinstance(results, list)
        assert len(results) == 2
        # Lab1 matches both ml_ai (expert=4) + mathematics (intermediate=2) = 6
        # Lab2 matches only mathematics (intermediate=2) = 2
        assert results[0]["lab_slug"] == "ml-research"
        assert results[0]["match_score"] >= results[1]["match_score"]

    @pytest.mark.asyncio
    async def test_match_lab_to_agents_returns_ranked_list(self):
        """match_lab_to_agents should return a list of agent dicts
        sorted by match_score descending."""
        from platform.feed.capability_index import CapabilityIndex

        session = self._make_session()
        lab_id = uuid4()
        role_card_id = uuid4()

        # Mock role card
        mock_role_card = MagicMock()
        mock_role_card.lab_id = lab_id
        mock_role_card.skill_tags = {"domains": ["ml_ai"]}
        mock_role_card.archetype = "researcher"
        mock_role_card.min_karma = 0

        # Mock current members (none)
        member_result = MagicMock()
        member_result.scalars.return_value.all.return_value = []

        # Mock agents
        agent1 = MagicMock()
        agent1.id = uuid4()
        agent1.display_name = "AgentAlpha"
        agent1.agent_type = "openclaw"
        agent1.status = "active"

        agent2 = MagicMock()
        agent2.id = uuid4()
        agent2.display_name = "AgentBeta"
        agent2.agent_type = "openclaw"
        agent2.status = "active"

        agents_result = MagicMock()
        agents_result.scalars.return_value.all.return_value = [agent1, agent2]

        # Capabilities for agent1 -- expert in ml_ai
        cap1 = MagicMock()
        cap1.domain = "ml_ai"
        cap1.capability_level = "expert"
        agent1_caps_result = MagicMock()
        agent1_caps_result.scalars.return_value.all.return_value = [cap1]

        # Capabilities for agent2 -- basic in ml_ai
        cap2 = MagicMock()
        cap2.domain = "ml_ai"
        cap2.capability_level = "basic"
        agent2_caps_result = MagicMock()
        agent2_caps_result.scalars.return_value.all.return_value = [cap2]

        session.execute.side_effect = [
            member_result,
            agents_result,
            agent1_caps_result,
            agent2_caps_result,
        ]

        with patch(
            "platform.feed.capability_index.RoleCardRepository"
        ) as MockRCRepo:
            mock_rc_repo = MagicMock()
            mock_rc_repo.get_by_id = AsyncMock(return_value=mock_role_card)
            mock_rc_repo.get_unfilled = AsyncMock(return_value=[])
            MockRCRepo.return_value = mock_rc_repo

            index = CapabilityIndex(session)
            results = await index.match_lab_to_agents(
                lab_id=str(lab_id),
                role_card_id=str(role_card_id),
            )

        assert isinstance(results, list)
        assert len(results) == 2
        # Agent1 is expert (4.0) > Agent2 basic (1.0)
        assert results[0]["display_name"] == "AgentAlpha"
        assert results[0]["match_score"] >= results[1]["match_score"]

    @pytest.mark.asyncio
    async def test_empty_results_when_no_match(self):
        """match_agent_to_labs should return an empty list when the
        agent has no capabilities."""
        from platform.feed.capability_index import CapabilityIndex

        session = self._make_session()
        agent_id = uuid4()

        # No capabilities
        caps_result = MagicMock()
        caps_result.scalars.return_value.all.return_value = []
        session.execute.return_value = caps_result

        with patch(
            "platform.feed.capability_index.RoleCardRepository"
        ):
            index = CapabilityIndex(session)
            results = await index.match_agent_to_labs(str(agent_id))

        assert results == []
