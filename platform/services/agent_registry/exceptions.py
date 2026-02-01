"""Custom exceptions for Agent Registry service."""

from fastapi import HTTPException, status


class AgentRegistryError(Exception):
    """Base exception for Agent Registry errors."""

    def __init__(self, message: str, error_type: str = "agent_registry_error"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)


class AgentAlreadyExistsError(AgentRegistryError):
    """Raised when attempting to register an agent that already exists."""

    def __init__(self, agent_id: str):
        super().__init__(
            f"Agent with ID {agent_id} already exists",
            "agent_already_exists",
        )
        self.agent_id = agent_id


class AgentNotFoundError(AgentRegistryError):
    """Raised when an agent is not found."""

    def __init__(self, agent_id: str):
        super().__init__(
            f"Agent with ID {agent_id} not found",
            "agent_not_found",
        )
        self.agent_id = agent_id


class InvalidPublicKeyError(AgentRegistryError):
    """Raised when public key is invalid."""

    def __init__(self, message: str = "Invalid public key"):
        super().__init__(message, "invalid_public_key")


class InvalidSignatureError(AgentRegistryError):
    """Raised when signature verification fails."""

    def __init__(self, message: str = "Invalid signature"):
        super().__init__(message, "invalid_signature")


class ChallengeExpiredError(AgentRegistryError):
    """Raised when registration challenge has expired."""

    def __init__(self, message: str = "Challenge expired"):
        super().__init__(message, "challenge_expired")


class TokenNotFoundError(AgentRegistryError):
    """Raised when a token is not found."""

    def __init__(self, token_id: str):
        super().__init__(
            f"Token with ID {token_id} not found",
            "token_not_found",
        )
        self.token_id = token_id


class InsufficientScopesError(AgentRegistryError):
    """Raised when token doesn't have required scopes."""

    def __init__(self, required_scopes: list[str], actual_scopes: list[str]):
        super().__init__(
            f"Insufficient scopes. Required: {required_scopes}, has: {actual_scopes}",
            "insufficient_scopes",
        )
        self.required_scopes = required_scopes
        self.actual_scopes = actual_scopes


def raise_http_exception(error: AgentRegistryError) -> None:
    """Convert AgentRegistryError to HTTPException."""
    status_map = {
        "agent_already_exists": status.HTTP_409_CONFLICT,
        "agent_not_found": status.HTTP_404_NOT_FOUND,
        "invalid_public_key": status.HTTP_400_BAD_REQUEST,
        "invalid_signature": status.HTTP_401_UNAUTHORIZED,
        "challenge_expired": status.HTTP_410_GONE,
        "token_not_found": status.HTTP_404_NOT_FOUND,
        "insufficient_scopes": status.HTTP_403_FORBIDDEN,
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
