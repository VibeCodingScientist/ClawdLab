"""State machine for research item lifecycle.

Defines valid transitions for the roundtable propose → debate → vote →
execute → verify → publish pipeline.
"""

from __future__ import annotations

from platform.labs.exceptions import RoundtableStateError

# Map of current_status → list of (target_status, trigger_reason)
VALID_TRANSITIONS: dict[str, list[tuple[str, str]]] = {
    "proposed": [
        ("under_debate", "contribution_added"),
        ("withdrawn", "proposer_withdraw"),
    ],
    "under_debate": [
        ("under_debate", "contribution_added"),
        ("approved", "vote_resolved_approve"),
        ("rejected", "vote_resolved_reject"),
        ("withdrawn", "proposer_withdraw"),
    ],
    "approved": [
        ("in_progress", "work_assigned"),
        ("withdrawn", "proposer_withdraw"),
    ],
    "in_progress": [
        ("submitted", "result_submitted"),
    ],
    "submitted": [
        ("under_review", "verification_dispatched"),
    ],
    "under_review": [
        ("verified", "verification_passed"),
        ("under_debate", "verification_failed"),
    ],
    "verified": [
        ("archived", "admin_archive"),
    ],
}


def can_transition(current: str, target: str) -> bool:
    """Check whether a transition from current to target is valid."""
    allowed = VALID_TRANSITIONS.get(current, [])
    return any(t == target for t, _ in allowed)


def validate_transition(current: str, target: str) -> None:
    """Validate a state transition, raising RoundtableStateError if invalid."""
    if not can_transition(current, target):
        raise RoundtableStateError(current, target)
