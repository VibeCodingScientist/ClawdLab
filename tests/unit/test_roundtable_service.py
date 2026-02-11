"""Tests for RoundtableService."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform.labs.exceptions import (
    LabMembershipError,
    RoundtableRoleError,
    RoundtableStateError,
    VoteWindowError,
)
from platform.labs.roundtable_service import RoundtableService


def _make_lab(governance_type="democratic", created_by=None):
    lab = MagicMock()
    lab.id = uuid4()
    lab.slug = "test-lab"
    lab.governance_type = governance_type
    lab.rules = {"voting_threshold": 0.5, "quorum_fraction": 0.3}
    lab.created_by = created_by or uuid4()
    lab.archived_at = None
    lab.domains = ["mathematics"]
    return lab


def _make_membership(agent_id=None, role_card_id=None, status="active"):
    m = MagicMock()
    m.id = uuid4()
    m.agent_id = agent_id or uuid4()
    m.role_card_id = role_card_id
    m.status = status
    m.lab_karma = 10
    m.vote_weight = 1.0
    return m


def _make_role_card(archetype="theorist", permissions=None):
    rc = MagicMock()
    rc.id = uuid4()
    rc.archetype = archetype
    rc.permissions = permissions or {
        "can_propose": True,
        "can_critique": True,
        "can_cast_vote": True,
    }
    return rc


def _make_item(status="proposed", lab_id=None, proposed_by=None, assigned_to=None):
    item = MagicMock()
    item.id = uuid4()
    item.lab_id = lab_id or uuid4()
    item.status = status
    item.proposed_by = proposed_by or uuid4()
    item.assigned_to = assigned_to
    item.resulting_claim_id = None
    item.title = "Test Item"
    item.description = "Test description"
    item.domain = "mathematics"
    item.claim_type = "theorem"
    item.created_at = datetime.now(timezone.utc)
    item.updated_at = datetime.now(timezone.utc)
    return item


def _make_entry(entry_type="argument", author_id=None, vote_value=None):
    e = MagicMock()
    e.id = uuid4()
    e.research_item_id = uuid4()
    e.author_id = author_id or uuid4()
    e.parent_entry_id = None
    e.entry_type = entry_type
    e.content = "Test content"
    e.vote_value = vote_value
    e.created_at = datetime.now(timezone.utc)
    return e


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    return session


class TestPropose:
    @pytest.mark.asyncio
    async def test_propose_with_valid_role(self, mock_session):
        agent_id = uuid4()
        lab = _make_lab()
        role_card = _make_role_card("theorist", {"can_propose": True})
        membership = _make_membership(agent_id, role_card.id)

        service = RoundtableService(mock_session)
        service.lab_repo.get_by_slug = AsyncMock(return_value=lab)
        service.membership_repo.get = AsyncMock(return_value=membership)
        service.role_card_repo.get_by_id = AsyncMock(return_value=role_card)

        item = _make_item(lab_id=lab.id, proposed_by=agent_id)
        service.research_repo.create = AsyncMock(return_value=item)

        entry = _make_entry("proposal", agent_id)
        service.roundtable_repo.create = AsyncMock(return_value=entry)

        result = await service.propose("test-lab", agent_id, "Test Title", "Desc", "mathematics")

        assert result["title"] == "Test Item"
        service.research_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_propose_with_denied_role(self, mock_session):
        agent_id = uuid4()
        lab = _make_lab()
        role_card = _make_role_card("technician", {"can_propose": False, "can_submit_results": True})
        membership = _make_membership(agent_id, role_card.id)

        service = RoundtableService(mock_session)
        service.lab_repo.get_by_slug = AsyncMock(return_value=lab)
        service.membership_repo.get = AsyncMock(return_value=membership)
        service.role_card_repo.get_by_id = AsyncMock(return_value=role_card)

        with pytest.raises(RoundtableRoleError) as exc_info:
            await service.propose("test-lab", agent_id, "Test", "Desc", "mathematics")
        assert "technician" in str(exc_info.value.message)


class TestContribute:
    @pytest.mark.asyncio
    async def test_auto_transition_proposed_to_under_debate(self, mock_session):
        agent_id = uuid4()
        lab = _make_lab()
        item = _make_item("proposed", lab.id)
        role_card = _make_role_card("critic", {"can_critique": True})
        membership = _make_membership(agent_id, role_card.id)

        service = RoundtableService(mock_session)
        service.lab_repo.get_by_slug = AsyncMock(return_value=lab)
        service.research_repo.get_by_id = AsyncMock(return_value=item)
        service.membership_repo.get = AsyncMock(return_value=membership)
        service.role_card_repo.get_by_id = AsyncMock(return_value=role_card)
        service.research_repo.update = AsyncMock(return_value=item)

        entry = _make_entry("argument", agent_id)
        service.roundtable_repo.create = AsyncMock(return_value=entry)
        service.roundtable_repo.list_by_item = AsyncMock(return_value=([], 0))

        result = await service.contribute("test-lab", item.id, agent_id, "argument", "Good point")

        service.research_repo.update.assert_called_once_with(item.id, status="under_debate")

    @pytest.mark.asyncio
    async def test_contribute_to_approved_item_raises(self, mock_session):
        agent_id = uuid4()
        lab = _make_lab()
        item = _make_item("approved", lab.id)
        role_card = _make_role_card("critic", {"can_critique": True})
        membership = _make_membership(agent_id, role_card.id)

        service = RoundtableService(mock_session)
        service.lab_repo.get_by_slug = AsyncMock(return_value=lab)
        service.research_repo.get_by_id = AsyncMock(return_value=item)
        service.membership_repo.get = AsyncMock(return_value=membership)
        service.role_card_repo.get_by_id = AsyncMock(return_value=role_card)

        with pytest.raises(RoundtableStateError):
            await service.contribute("test-lab", item.id, agent_id, "argument", "Content")


class TestCastVote:
    @pytest.mark.asyncio
    async def test_cast_vote_valid(self, mock_session):
        agent_id = uuid4()
        lab = _make_lab()
        item = _make_item("under_debate", lab.id)
        role_card = _make_role_card("theorist", {"can_cast_vote": True})
        membership = _make_membership(agent_id, role_card.id)

        service = RoundtableService(mock_session)
        service.lab_repo.get_by_slug = AsyncMock(return_value=lab)
        service.research_repo.get_by_id = AsyncMock(return_value=item)
        service.membership_repo.get = AsyncMock(return_value=membership)
        service.role_card_repo.get_by_id = AsyncMock(return_value=role_card)

        entry = _make_entry("vote", agent_id, vote_value=1)
        service.roundtable_repo.create = AsyncMock(return_value=entry)

        result = await service.cast_vote("test-lab", item.id, agent_id, 1)

        assert result["vote_value"] == 1

    @pytest.mark.asyncio
    async def test_cast_vote_on_approved_item_raises(self, mock_session):
        agent_id = uuid4()
        lab = _make_lab()
        item = _make_item("approved", lab.id)
        role_card = _make_role_card("theorist", {"can_cast_vote": True})
        membership = _make_membership(agent_id, role_card.id)

        service = RoundtableService(mock_session)
        service.lab_repo.get_by_slug = AsyncMock(return_value=lab)
        service.research_repo.get_by_id = AsyncMock(return_value=item)
        service.membership_repo.get = AsyncMock(return_value=membership)
        service.role_card_repo.get_by_id = AsyncMock(return_value=role_card)

        with pytest.raises(VoteWindowError):
            await service.cast_vote("test-lab", item.id, agent_id, 1)


class TestResolveVote:
    @pytest.mark.asyncio
    async def test_resolve_approves(self, mock_session):
        lab = _make_lab()
        item = _make_item("under_debate", lab.id)

        service = RoundtableService(mock_session)
        service.lab_repo.get_by_slug = AsyncMock(return_value=lab)
        service.research_repo.get_by_id = AsyncMock(return_value=item)
        service.roundtable_repo.count_votes = AsyncMock(return_value={"approve": 3, "reject": 0, "abstain": 0})
        service.membership_repo.list_by_lab = AsyncMock(return_value=([MagicMock()] * 5, 5))
        service.roundtable_repo.list_by_item = AsyncMock(return_value=([], 0))
        service.research_repo.update = AsyncMock(return_value=item)

        result = await service.resolve_vote("test-lab", item.id)

        assert result["approved"] is True
        assert result["new_status"] == "approved"


class TestAssignWork:
    @pytest.mark.asyncio
    async def test_assign_work_valid(self, mock_session):
        agent_id = uuid4()
        lab = _make_lab()
        item = _make_item("approved", lab.id)
        role_card = _make_role_card("experimentalist", {"can_claim_work": True})
        membership = _make_membership(agent_id, role_card.id)

        service = RoundtableService(mock_session)
        service.lab_repo.get_by_slug = AsyncMock(return_value=lab)
        service.research_repo.get_by_id = AsyncMock(return_value=item)
        service.membership_repo.get = AsyncMock(return_value=membership)
        service.role_card_repo.get_by_id = AsyncMock(return_value=role_card)
        service.research_repo.assign = AsyncMock(return_value=True)
        service.research_repo.update = AsyncMock(return_value=item)
        service.workspace_repo.upsert = AsyncMock()

        result = await service.assign_work("test-lab", item.id, agent_id)

        service.research_repo.assign.assert_called_once()

    @pytest.mark.asyncio
    async def test_assign_work_wrong_status_raises(self, mock_session):
        agent_id = uuid4()
        lab = _make_lab()
        item = _make_item("proposed", lab.id)
        role_card = _make_role_card("experimentalist", {"can_claim_work": True})
        membership = _make_membership(agent_id, role_card.id)

        service = RoundtableService(mock_session)
        service.lab_repo.get_by_slug = AsyncMock(return_value=lab)
        service.research_repo.get_by_id = AsyncMock(return_value=item)
        service.membership_repo.get = AsyncMock(return_value=membership)
        service.role_card_repo.get_by_id = AsyncMock(return_value=role_card)

        with pytest.raises(RoundtableStateError):
            await service.assign_work("test-lab", item.id, agent_id)


class TestSubmitResult:
    @pytest.mark.asyncio
    async def test_submit_result_valid(self, mock_session):
        agent_id = uuid4()
        lab = _make_lab()
        item = _make_item("in_progress", lab.id, assigned_to=agent_id)
        role_card = _make_role_card("experimentalist", {"can_submit_results": True})
        membership = _make_membership(agent_id, role_card.id)

        service = RoundtableService(mock_session)
        service.lab_repo.get_by_slug = AsyncMock(return_value=lab)
        service.research_repo.get_by_id = AsyncMock(return_value=item)
        service.membership_repo.get = AsyncMock(return_value=membership)
        service.role_card_repo.get_by_id = AsyncMock(return_value=role_card)
        service.research_repo.update = AsyncMock(return_value=item)

        result = await service.submit_result(
            "test-lab", item.id, agent_id, {"proof": "data"}, "theorem",
        )

        service.research_repo.update.assert_called()

    @pytest.mark.asyncio
    async def test_submit_result_wrong_agent_raises(self, mock_session):
        agent_id = uuid4()
        other_agent = uuid4()
        lab = _make_lab()
        item = _make_item("in_progress", lab.id, assigned_to=other_agent)
        role_card = _make_role_card("experimentalist", {"can_submit_results": True})
        membership = _make_membership(agent_id, role_card.id)

        service = RoundtableService(mock_session)
        service.lab_repo.get_by_slug = AsyncMock(return_value=lab)
        service.research_repo.get_by_id = AsyncMock(return_value=item)
        service.membership_repo.get = AsyncMock(return_value=membership)
        service.role_card_repo.get_by_id = AsyncMock(return_value=role_card)

        with pytest.raises(LabMembershipError):
            await service.submit_result("test-lab", item.id, agent_id, {}, "theorem")


class TestKarmaDistribution:
    @pytest.mark.asyncio
    async def test_karma_distribution_all_roles(self, mock_session):
        lab = _make_lab()
        proposer_id = uuid4()
        executor_id = uuid4()
        critic_id = uuid4()
        voter_id = uuid4()

        item = _make_item("verified", lab.id, proposed_by=proposer_id, assigned_to=executor_id)

        service = RoundtableService(mock_session)
        service.research_repo.get_by_id = AsyncMock(return_value=item)
        service.lab_repo.get_by_id = AsyncMock(return_value=lab)

        entries = [
            _make_entry("argument", critic_id),
            _make_entry("vote", voter_id, vote_value=1),
        ]
        service.roundtable_repo.list_by_item = AsyncMock(return_value=(entries, len(entries)))

        # Create memberships for each participant
        memberships = {}
        for aid in [executor_id, proposer_id, critic_id, voter_id, lab.created_by]:
            m = _make_membership(aid)
            memberships[str(aid)] = m

        async def mock_get(lab_id, agent_id):
            return memberships.get(str(agent_id))

        service.membership_repo.get = mock_get
        service.membership_repo.update_karma = AsyncMock(return_value=True)

        awarded = await service._distribute_karma(lab.id, item.id, 100)

        assert len(awarded) > 0
        assert str(executor_id) in awarded
        assert str(proposer_id) in awarded
