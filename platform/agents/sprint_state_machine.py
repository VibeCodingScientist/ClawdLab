"""Sprint lifecycle state machine.

Sprint states: planning → active → wrapping_up → completed
               also: paused ↔ active, any → abandoned
"""


class SprintStateError(Exception):
    """Raised when an invalid sprint state transition is attempted."""


VALID_TRANSITIONS: dict[str, list[tuple[str, str]]] = {
    "planning": [
        ("active", "sprint_started"),
        ("abandoned", "deployer_cancelled"),
    ],
    "active": [
        ("wrapping_up", "time_threshold_reached"),
        ("paused", "deployer_paused"),
        ("abandoned", "deployer_cancelled"),
        ("completed", "sprint_completed"),
    ],
    "wrapping_up": [
        ("completed", "sprint_completed"),
        ("abandoned", "deployer_cancelled"),
    ],
    "paused": [
        ("active", "deployer_resumed"),
        ("abandoned", "deployer_cancelled"),
    ],
    "completed": [],  # terminal
    "abandoned": [],   # terminal
}


def can_transition(current: str, target: str) -> bool:
    """Check if a sprint state transition is valid."""
    transitions = VALID_TRANSITIONS.get(current, [])
    return any(t == target for t, _ in transitions)


def validate_transition(current: str, target: str, reason: str = "") -> None:
    """Validate a sprint state transition, raising SprintStateError if invalid."""
    if not can_transition(current, target):
        allowed = [t for t, _ in VALID_TRANSITIONS.get(current, [])]
        raise SprintStateError(
            f"Cannot transition sprint from '{current}' to '{target}'. "
            f"Allowed transitions from '{current}': {allowed}"
        )
