"""Custom exceptions for Claim Service."""

from fastapi import HTTPException, status


class ClaimServiceError(Exception):
    """Base exception for Claim Service errors."""

    def __init__(self, message: str, error_type: str = "claim_service_error"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)


class ClaimNotFoundError(ClaimServiceError):
    """Raised when a claim is not found."""

    def __init__(self, claim_id: str):
        super().__init__(
            f"Claim with ID {claim_id} not found",
            "claim_not_found",
        )
        self.claim_id = claim_id


class ClaimAlreadyExistsError(ClaimServiceError):
    """Raised when attempting to create a duplicate claim."""

    def __init__(self, claim_hash: str):
        super().__init__(
            f"Claim with hash {claim_hash} already exists",
            "claim_already_exists",
        )
        self.claim_hash = claim_hash


class InvalidClaimError(ClaimServiceError):
    """Raised when claim validation fails."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message, "invalid_claim")
        self.field = field


class DependencyNotFoundError(ClaimServiceError):
    """Raised when a claim dependency is not found."""

    def __init__(self, dependency_id: str):
        super().__init__(
            f"Dependency claim {dependency_id} not found",
            "dependency_not_found",
        )
        self.dependency_id = dependency_id


class DependencyNotVerifiedError(ClaimServiceError):
    """Raised when a claim dependency is not verified."""

    def __init__(self, dependency_id: str):
        super().__init__(
            f"Dependency claim {dependency_id} is not verified",
            "dependency_not_verified",
        )
        self.dependency_id = dependency_id


class CyclicDependencyError(ClaimServiceError):
    """Raised when claim dependencies form a cycle."""

    def __init__(self, cycle: list[str]):
        super().__init__(
            f"Cyclic dependency detected: {' -> '.join(cycle)}",
            "cyclic_dependency",
        )
        self.cycle = cycle


class ChallengeNotFoundError(ClaimServiceError):
    """Raised when a challenge is not found."""

    def __init__(self, challenge_id: str):
        super().__init__(
            f"Challenge with ID {challenge_id} not found",
            "challenge_not_found",
        )
        self.challenge_id = challenge_id


class ChallengeAlreadyExistsError(ClaimServiceError):
    """Raised when agent already has an active challenge on a claim."""

    def __init__(self, claim_id: str, agent_id: str):
        super().__init__(
            f"Agent {agent_id} already has an active challenge on claim {claim_id}",
            "challenge_already_exists",
        )
        self.claim_id = claim_id
        self.agent_id = agent_id


class ClaimNotChallengableError(ClaimServiceError):
    """Raised when a claim cannot be challenged."""

    def __init__(self, claim_id: str, reason: str):
        super().__init__(
            f"Claim {claim_id} cannot be challenged: {reason}",
            "claim_not_challengable",
        )
        self.claim_id = claim_id
        self.reason = reason


class ClaimNotRetractableError(ClaimServiceError):
    """Raised when a claim cannot be retracted."""

    def __init__(self, claim_id: str, reason: str):
        super().__init__(
            f"Claim {claim_id} cannot be retracted: {reason}",
            "claim_not_retractable",
        )
        self.claim_id = claim_id
        self.reason = reason


class UnauthorizedClaimAccessError(ClaimServiceError):
    """Raised when agent doesn't own the claim."""

    def __init__(self, claim_id: str, agent_id: str):
        super().__init__(
            f"Agent {agent_id} is not authorized to modify claim {claim_id}",
            "unauthorized_claim_access",
        )
        self.claim_id = claim_id
        self.agent_id = agent_id


class RateLimitExceededError(ClaimServiceError):
    """Raised when rate limit is exceeded."""

    def __init__(self, limit_type: str, retry_after: int):
        super().__init__(
            f"Rate limit exceeded for {limit_type}. Retry after {retry_after} seconds.",
            "rate_limit_exceeded",
        )
        self.limit_type = limit_type
        self.retry_after = retry_after


class VerificationInProgressError(ClaimServiceError):
    """Raised when claim is being verified."""

    def __init__(self, claim_id: str):
        super().__init__(
            f"Claim {claim_id} is currently being verified",
            "verification_in_progress",
        )
        self.claim_id = claim_id


def raise_http_exception(error: ClaimServiceError) -> None:
    """Convert ClaimServiceError to HTTPException."""
    status_map = {
        "claim_not_found": status.HTTP_404_NOT_FOUND,
        "claim_already_exists": status.HTTP_409_CONFLICT,
        "invalid_claim": status.HTTP_400_BAD_REQUEST,
        "dependency_not_found": status.HTTP_400_BAD_REQUEST,
        "dependency_not_verified": status.HTTP_400_BAD_REQUEST,
        "cyclic_dependency": status.HTTP_400_BAD_REQUEST,
        "challenge_not_found": status.HTTP_404_NOT_FOUND,
        "challenge_already_exists": status.HTTP_409_CONFLICT,
        "claim_not_challengable": status.HTTP_400_BAD_REQUEST,
        "claim_not_retractable": status.HTTP_400_BAD_REQUEST,
        "unauthorized_claim_access": status.HTTP_403_FORBIDDEN,
        "rate_limit_exceeded": status.HTTP_429_TOO_MANY_REQUESTS,
        "verification_in_progress": status.HTTP_409_CONFLICT,
    }

    headers = {}
    if error.error_type == "rate_limit_exceeded" and hasattr(error, "retry_after"):
        headers["Retry-After"] = str(error.retry_after)

    raise HTTPException(
        status_code=status_map.get(error.error_type, status.HTTP_500_INTERNAL_SERVER_ERROR),
        detail={
            "type": f"https://api.research-platform.ai/errors/{error.error_type}",
            "title": error.error_type.replace("_", " ").title(),
            "status": status_map.get(error.error_type, 500),
            "detail": error.message,
        },
        headers=headers if headers else None,
    )
