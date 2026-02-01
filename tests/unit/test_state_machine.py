"""Tests for the research item state machine."""

import pytest

from platform.labs.exceptions import RoundtableStateError
from platform.labs.state_machine import VALID_TRANSITIONS, can_transition, validate_transition


class TestCanTransition:
    """Test can_transition function."""

    def test_proposed_to_under_debate(self):
        assert can_transition("proposed", "under_debate") is True

    def test_proposed_to_withdrawn(self):
        assert can_transition("proposed", "withdrawn") is True

    def test_proposed_to_approved_invalid(self):
        assert can_transition("proposed", "approved") is False

    def test_under_debate_to_approved(self):
        assert can_transition("under_debate", "approved") is True

    def test_under_debate_to_rejected(self):
        assert can_transition("under_debate", "rejected") is True

    def test_under_debate_to_under_debate(self):
        assert can_transition("under_debate", "under_debate") is True

    def test_approved_to_in_progress(self):
        assert can_transition("approved", "in_progress") is True

    def test_in_progress_to_submitted(self):
        assert can_transition("in_progress", "submitted") is True

    def test_submitted_to_under_review(self):
        assert can_transition("submitted", "under_review") is True

    def test_under_review_to_verified(self):
        assert can_transition("under_review", "verified") is True

    def test_under_review_to_under_debate(self):
        assert can_transition("under_review", "under_debate") is True

    def test_verified_to_archived(self):
        assert can_transition("verified", "archived") is True

    def test_invalid_backward_transition(self):
        assert can_transition("approved", "proposed") is False

    def test_verified_to_proposed_invalid(self):
        assert can_transition("verified", "proposed") is False

    def test_unknown_status(self):
        assert can_transition("nonexistent", "proposed") is False

    def test_in_progress_to_approved_invalid(self):
        assert can_transition("in_progress", "approved") is False


class TestValidateTransition:
    """Test validate_transition raises on invalid transitions."""

    def test_valid_transition_no_error(self):
        validate_transition("proposed", "under_debate")

    def test_invalid_transition_raises(self):
        with pytest.raises(RoundtableStateError) as exc_info:
            validate_transition("proposed", "verified")
        assert "proposed" in str(exc_info.value.message)
        assert "verified" in str(exc_info.value.message)

    def test_error_contains_statuses(self):
        with pytest.raises(RoundtableStateError) as exc_info:
            validate_transition("approved", "rejected")
        assert exc_info.value.current_status == "approved"
        assert exc_info.value.target_status == "rejected"


class TestTransitionCoverage:
    """Ensure all defined transitions are valid."""

    def test_all_transitions_defined(self):
        """Every entry in VALID_TRANSITIONS should be testable."""
        for current, targets in VALID_TRANSITIONS.items():
            for target, trigger in targets:
                assert can_transition(current, target), (
                    f"Transition {current} → {target} (trigger: {trigger}) should be valid"
                )

    def test_no_self_transition_except_under_debate(self):
        """Only under_debate should allow self-transition."""
        for current, targets in VALID_TRANSITIONS.items():
            for target, _ in targets:
                if current == target:
                    assert current == "under_debate", (
                        f"Self-transition only allowed for under_debate, not {current}"
                    )
