"""Tests for personalized /skill.md discovery endpoint."""

from unittest.mock import MagicMock

import pytest

from backend.routes.discovery import SKILL_MD, _build_role_section


def _make_role_card(role, hard_bans=None, escalation=None, definition_of_done=None):
    """Helper to create a mock role card."""
    card = MagicMock()
    card.role = role
    card.domain = f"Domain for {role}"
    card.hard_bans = hard_bans or []
    card.escalation = escalation or []
    card.definition_of_done = definition_of_done or []
    return card


def _make_membership(custom_bans=None):
    """Helper to create a mock membership."""
    m = MagicMock()
    m.custom_bans = custom_bans or []
    return m


class TestBuildRoleSection:
    """Test the _build_role_section helper."""

    def test_basic_section(self):
        """Should include role name and domain."""
        card = _make_role_card("scout")
        membership = _make_membership()

        section = _build_role_section(card, membership)

        assert "Your Role: Scout" in section
        assert "Domain for scout" in section

    def test_hard_bans_included(self):
        """Hard bans should appear as MUST NOT list."""
        card = _make_role_card(
            "scout",
            hard_bans=["No fabricating citations.", "No proposing analysis tasks."],
        )
        membership = _make_membership()

        section = _build_role_section(card, membership)

        assert "You MUST NOT" in section
        assert "No fabricating citations." in section
        assert "No proposing analysis tasks." in section

    def test_escalation_included(self):
        """Escalation items should appear."""
        card = _make_role_card(
            "scout",
            escalation=["Contradictory findings across sources"],
        )
        membership = _make_membership()

        section = _build_role_section(card, membership)

        assert "Escalate to PI when" in section
        assert "Contradictory findings across sources" in section

    def test_definition_of_done_included(self):
        """Definition of done items should appear."""
        card = _make_role_card(
            "scout",
            definition_of_done=["Papers list includes title, authors, year."],
        )
        membership = _make_membership()

        section = _build_role_section(card, membership)

        assert "Definition of Done" in section
        assert "Papers list includes title, authors, year." in section

    def test_custom_bans_from_membership(self):
        """Custom bans from lab membership should appear."""
        card = _make_role_card("scout")
        membership = _make_membership(
            custom_bans=["No protein design claims in this math lab."],
        )

        section = _build_role_section(card, membership)

        assert "Lab-specific rules" in section
        assert "No protein design claims in this math lab." in section

    def test_empty_bans_no_section(self):
        """When no hard bans, the MUST NOT section should not appear."""
        card = _make_role_card("pi")
        membership = _make_membership()

        section = _build_role_section(card, membership)

        assert "MUST NOT" not in section

    def test_role_name_formatting(self):
        """Role names with underscores should be title-cased."""
        card = _make_role_card("skeptical_theorist")
        membership = _make_membership()

        section = _build_role_section(card, membership)

        assert "Skeptical Theorist" in section


class TestSkillMdContent:
    """Test the static SKILL_MD content."""

    def test_contains_registration(self):
        assert "Registration" in SKILL_MD

    def test_contains_task_lifecycle(self):
        # Task lifecycle is now embedded in role cron loops (pick-up, complete, vote)
        assert "pick-up" in SKILL_MD
        assert "complete" in SKILL_MD
        assert "vote" in SKILL_MD

    def test_contains_all_roles(self):
        assert "scout" in SKILL_MD
        assert "pi" in SKILL_MD
        assert "research_analyst" in SKILL_MD
        assert "skeptical_theorist" in SKILL_MD
        assert "synthesizer" in SKILL_MD
