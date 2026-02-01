"""Challenge lifecycle state machine.

States: draft → review → open → active → evaluation → completed
Any non-terminal state can also → cancelled.
"""


class ChallengeStateError(Exception):
    """Raised when an invalid challenge state transition is attempted."""


VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["review", "cancelled"],
    "review": ["open", "cancelled"],
    "open": ["active", "cancelled"],
    "active": ["evaluation", "cancelled"],
    "evaluation": ["completed", "cancelled"],
    "completed": [],    # terminal
    "cancelled": [],    # terminal
}


def can_transition(current: str, target: str) -> bool:
    """Check if a challenge state transition is valid."""
    return target in VALID_TRANSITIONS.get(current, [])


def validate_transition(current: str, target: str) -> None:
    """Validate a challenge state transition, raising ChallengeStateError if invalid."""
    if not can_transition(current, target):
        allowed = VALID_TRANSITIONS.get(current, [])
        raise ChallengeStateError(
            f"Cannot transition challenge from '{current}' to '{target}'. "
            f"Allowed from '{current}': {allowed}"
        )
