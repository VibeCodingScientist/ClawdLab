"""Unit tests for challenge state machine transitions."""

import pytest

from platform.challenges.state_machine import (
    ChallengeStateError,
    can_transition,
    validate_transition,
)


class TestChallengeCanTransition:
    def test_draft_to_review(self):
        assert can_transition("draft", "review") is True

    def test_draft_to_cancelled(self):
        assert can_transition("draft", "cancelled") is True

    def test_draft_to_active_invalid(self):
        assert can_transition("draft", "active") is False

    def test_review_to_open(self):
        assert can_transition("review", "open") is True

    def test_open_to_active(self):
        assert can_transition("open", "active") is True

    def test_active_to_evaluation(self):
        assert can_transition("active", "evaluation") is True

    def test_evaluation_to_completed(self):
        assert can_transition("evaluation", "completed") is True

    def test_full_lifecycle(self):
        """Test complete happy-path lifecycle."""
        states = ["draft", "review", "open", "active", "evaluation", "completed"]
        for i in range(len(states) - 1):
            assert can_transition(states[i], states[i + 1]) is True

    def test_any_to_cancelled(self):
        """All non-terminal states can transition to cancelled."""
        for state in ["draft", "review", "open", "active", "evaluation"]:
            assert can_transition(state, "cancelled") is True

    def test_completed_is_terminal(self):
        for target in ["draft", "review", "open", "active", "evaluation", "cancelled"]:
            assert can_transition("completed", target) is False

    def test_cancelled_is_terminal(self):
        for target in ["draft", "review", "open", "active", "evaluation", "completed"]:
            assert can_transition("cancelled", target) is False

    def test_no_backward_transitions(self):
        assert can_transition("open", "review") is False
        assert can_transition("active", "open") is False
        assert can_transition("evaluation", "active") is False


class TestChallengeValidateTransition:
    def test_valid_passes(self):
        validate_transition("draft", "review")

    def test_invalid_raises(self):
        with pytest.raises(ChallengeStateError, match="Cannot transition"):
            validate_transition("draft", "active")

    def test_terminal_raises(self):
        with pytest.raises(ChallengeStateError):
            validate_transition("completed", "review")
