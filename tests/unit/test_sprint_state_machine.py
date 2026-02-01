"""Unit tests for sprint state machine transitions."""

import pytest

from platform.agents.sprint_state_machine import (
    SprintStateError,
    can_transition,
    validate_transition,
)


class TestCanTransition:
    def test_planning_to_active(self):
        assert can_transition("planning", "active") is True

    def test_planning_to_abandoned(self):
        assert can_transition("planning", "abandoned") is True

    def test_planning_to_completed_invalid(self):
        assert can_transition("planning", "completed") is False

    def test_active_to_wrapping_up(self):
        assert can_transition("active", "wrapping_up") is True

    def test_active_to_paused(self):
        assert can_transition("active", "paused") is True

    def test_active_to_completed(self):
        assert can_transition("active", "completed") is True

    def test_active_to_planning_invalid(self):
        assert can_transition("active", "planning") is False

    def test_wrapping_up_to_completed(self):
        assert can_transition("wrapping_up", "completed") is True

    def test_wrapping_up_to_active_invalid(self):
        assert can_transition("wrapping_up", "active") is False

    def test_paused_to_active(self):
        assert can_transition("paused", "active") is True

    def test_paused_to_abandoned(self):
        assert can_transition("paused", "abandoned") is True

    def test_paused_to_completed_invalid(self):
        assert can_transition("paused", "completed") is False

    def test_completed_is_terminal(self):
        for target in ["planning", "active", "paused", "abandoned", "wrapping_up"]:
            assert can_transition("completed", target) is False

    def test_abandoned_is_terminal(self):
        for target in ["planning", "active", "paused", "completed", "wrapping_up"]:
            assert can_transition("abandoned", target) is False

    def test_unknown_state(self):
        assert can_transition("unknown", "active") is False


class TestValidateTransition:
    def test_valid_transition_passes(self):
        validate_transition("planning", "active", "sprint_started")

    def test_invalid_transition_raises(self):
        with pytest.raises(SprintStateError, match="Cannot transition"):
            validate_transition("planning", "completed")

    def test_terminal_state_raises(self):
        with pytest.raises(SprintStateError):
            validate_transition("completed", "active")
