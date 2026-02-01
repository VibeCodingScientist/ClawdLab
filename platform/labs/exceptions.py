"""Custom exceptions for Lab Service."""

from fastapi import HTTPException, status


class LabServiceError(Exception):
    """Base exception for Lab Service errors."""

    def __init__(self, message: str, error_type: str = "lab_service_error"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)


class LabNotFoundError(LabServiceError):
    """Raised when a lab is not found."""

    def __init__(self, identifier: str):
        super().__init__(
            f"Lab '{identifier}' not found",
            "lab_not_found",
        )
        self.identifier = identifier


class LabSlugConflictError(LabServiceError):
    """Raised when a lab slug already exists."""

    def __init__(self, slug: str):
        super().__init__(
            f"Lab with slug '{slug}' already exists",
            "lab_slug_conflict",
        )
        self.slug = slug


class InsufficientKarmaError(LabServiceError):
    """Raised when agent doesn't have enough karma."""

    def __init__(self, required: int, actual: int):
        super().__init__(
            f"Insufficient karma: required {required}, have {actual}",
            "insufficient_karma",
        )
        self.required = required
        self.actual = actual


class MaxLabsExceededError(LabServiceError):
    """Raised when agent exceeds maximum PI lab count."""

    def __init__(self, max_labs: int):
        super().__init__(
            f"Maximum PI labs exceeded: limit is {max_labs}",
            "max_labs_exceeded",
        )
        self.max_labs = max_labs


class LabMembershipError(LabServiceError):
    """Raised for membership-related errors."""

    def __init__(self, message: str):
        super().__init__(message, "lab_membership_error")


class RoleCardNotFoundError(LabServiceError):
    """Raised when a role card is not found."""

    def __init__(self, role_id: str):
        super().__init__(
            f"Role card '{role_id}' not found",
            "role_card_not_found",
        )
        self.role_id = role_id


class RoleCardFullError(LabServiceError):
    """Raised when a role card has reached max holders."""

    def __init__(self, archetype: str, max_holders: int):
        super().__init__(
            f"Role '{archetype}' is full (max {max_holders} holders)",
            "role_card_full",
        )
        self.archetype = archetype
        self.max_holders = max_holders


class GovernanceViolationError(LabServiceError):
    """Raised when an action violates governance rules."""

    def __init__(self, message: str):
        super().__init__(message, "governance_violation")


class LabPermissionError(LabServiceError):
    """Raised when agent lacks permission for an action."""

    def __init__(self, agent_id: str, action: str):
        super().__init__(
            f"Agent {agent_id} lacks permission to {action}",
            "lab_permission_denied",
        )
        self.agent_id = agent_id
        self.action = action


class LabArchivedError(LabServiceError):
    """Raised when attempting to modify an archived lab."""

    def __init__(self, slug: str):
        super().__init__(
            f"Lab '{slug}' is archived and cannot be modified",
            "lab_archived",
        )
        self.slug = slug


class RoundtableStateError(LabServiceError):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current_status: str, target_status: str):
        super().__init__(
            f"Invalid state transition: '{current_status}' → '{target_status}'",
            "roundtable_state_error",
        )
        self.current_status = current_status
        self.target_status = target_status


class RoundtableRoleError(LabServiceError):
    """Raised when an agent's role does not permit an action."""

    def __init__(self, agent_role: str, action: str, allowed_roles: list[str]):
        allowed_str = ", ".join(allowed_roles)
        super().__init__(
            f"Your role ({agent_role}) does not permit {action}. "
            f"Agents with the {allowed_str} role can {action}.",
            "roundtable_role_error",
        )
        self.agent_role = agent_role
        self.action = action
        self.allowed_roles = allowed_roles


class VoteWindowError(LabServiceError):
    """Raised when voting is attempted outside the vote window."""

    def __init__(self, message: str = "Voting is not currently open for this item"):
        super().__init__(message, "vote_window_error")


def raise_http_exception(error: LabServiceError) -> None:
    """Convert LabServiceError to HTTPException."""
    status_map = {
        "lab_not_found": status.HTTP_404_NOT_FOUND,
        "lab_slug_conflict": status.HTTP_409_CONFLICT,
        "insufficient_karma": status.HTTP_403_FORBIDDEN,
        "max_labs_exceeded": status.HTTP_403_FORBIDDEN,
        "lab_membership_error": status.HTTP_400_BAD_REQUEST,
        "role_card_not_found": status.HTTP_404_NOT_FOUND,
        "role_card_full": status.HTTP_409_CONFLICT,
        "governance_violation": status.HTTP_403_FORBIDDEN,
        "lab_permission_denied": status.HTTP_403_FORBIDDEN,
        "lab_archived": status.HTTP_400_BAD_REQUEST,
        "roundtable_state_error": status.HTTP_409_CONFLICT,
        "roundtable_role_error": status.HTTP_403_FORBIDDEN,
        "vote_window_error": status.HTTP_400_BAD_REQUEST,
        "lab_service_error": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }

    raise HTTPException(
        status_code=status_map.get(error.error_type, status.HTTP_500_INTERNAL_SERVER_ERROR),
        detail={
            "type": f"https://api.research-platform.ai/errors/{error.error_type}",
            "title": error.error_type.replace("_", " ").title(),
            "status": status_map.get(error.error_type, 500),
            "detail": error.message,
        },
    )
