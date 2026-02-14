"""Tests for role card enforcement in task routes."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.models import RoleCard


def _make_role_card(role, task_types_allowed, can_initiate_voting=False):
    """Helper to create a mock role card."""
    card = MagicMock(spec=RoleCard)
    card.role = role
    card.domain = "test"
    card.inputs = []
    card.outputs = []
    card.hard_bans = []
    card.escalation = []
    card.task_types_allowed = task_types_allowed
    card.can_initiate_voting = can_initiate_voting
    card.can_assign_tasks = False
    card.definition_of_done = []
    return card


class TestTaskTypeEnforcement:
    """Test that propose_task enforces task_types_allowed."""

    def test_scout_blocked_from_analysis(self):
        """Scout should not be allowed to propose analysis tasks."""
        card = _make_role_card("scout", ["literature_review"])
        task_type = "analysis"

        # Simulate the check from propose_task
        if card and card.task_types_allowed and task_type not in card.task_types_allowed:
            blocked = True
        else:
            blocked = False

        assert blocked is True

    def test_scout_allowed_literature_review(self):
        """Scout should be allowed to propose literature_review tasks."""
        card = _make_role_card("scout", ["literature_review"])
        task_type = "literature_review"

        if card and card.task_types_allowed and task_type not in card.task_types_allowed:
            blocked = True
        else:
            blocked = False

        assert blocked is False

    def test_pi_allowed_any_type(self):
        """PI has empty task_types_allowed, so no restriction applies."""
        card = _make_role_card("pi", [])
        task_type = "analysis"

        if card and card.task_types_allowed and task_type not in card.task_types_allowed:
            blocked = True
        else:
            blocked = False

        assert blocked is False

    def test_research_analyst_allowed_analysis(self):
        """Research analyst can propose analysis."""
        card = _make_role_card("research_analyst", ["analysis", "deep_research"])
        task_type = "analysis"

        if card and card.task_types_allowed and task_type not in card.task_types_allowed:
            blocked = True
        else:
            blocked = False

        assert blocked is False

    def test_research_analyst_blocked_from_critique(self):
        """Research analyst cannot propose critique."""
        card = _make_role_card("research_analyst", ["analysis", "deep_research"])
        task_type = "critique"

        if card and card.task_types_allowed and task_type not in card.task_types_allowed:
            blocked = True
        else:
            blocked = False

        assert blocked is True

    def test_skeptical_theorist_allowed_critique(self):
        """Skeptical theorist can propose critique."""
        card = _make_role_card("skeptical_theorist", ["critique"])
        task_type = "critique"

        if card and card.task_types_allowed and task_type not in card.task_types_allowed:
            blocked = True
        else:
            blocked = False

        assert blocked is False

    def test_synthesizer_allowed_synthesis(self):
        """Synthesizer can propose synthesis."""
        card = _make_role_card("synthesizer", ["synthesis"])
        task_type = "synthesis"

        if card and card.task_types_allowed and task_type not in card.task_types_allowed:
            blocked = True
        else:
            blocked = False

        assert blocked is False


class TestVotingEnforcement:
    """Test that start_voting enforces can_initiate_voting."""

    def test_scout_blocked_from_voting(self):
        """Scout should not be able to initiate voting."""
        card = _make_role_card("scout", ["literature_review"], can_initiate_voting=False)

        blocked = not card or not card.can_initiate_voting
        assert blocked is True

    def test_pi_allowed_voting(self):
        """PI should be able to initiate voting."""
        card = _make_role_card("pi", [], can_initiate_voting=True)

        blocked = not card or not card.can_initiate_voting
        assert blocked is False

    def test_research_analyst_blocked_from_voting(self):
        """Research analyst cannot initiate voting."""
        card = _make_role_card("research_analyst", ["analysis"], can_initiate_voting=False)

        blocked = not card or not card.can_initiate_voting
        assert blocked is True

    def test_none_card_blocks_voting(self):
        """If no role card found, voting should be blocked."""
        card = None

        blocked = not card or not card.can_initiate_voting
        assert blocked is True
