"""FastAPI dependencies for Agent Registry service."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.session import get_db
from platform.services.agent_registry.service import AuthenticationService
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

# HTTP Bearer scheme for token authentication
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_agent(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Authenticate request and return agent context.

    This dependency validates the Bearer token and returns the agent
    information if valid. Use this for endpoints that require authentication.

    Args:
        request: FastAPI request object
        credentials: Bearer token credentials
        db: Database session

    Returns:
        Agent context dictionary with agent_id, scopes, etc.

    Raises:
        HTTPException: 401 if not authenticated
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = AuthenticationService(db)
    agent_context = await auth_service.authenticate_token(credentials.credentials)

    if not agent_context:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Store in request state for use by other components
    request.state.agent = agent_context

    logger.debug(
        "request_authenticated",
        agent_id=agent_context["agent_id"],
        scopes=agent_context["scopes"],
    )

    return agent_context


async def get_optional_agent(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | None:
    """
    Optionally authenticate request.

    Use this for endpoints that work both authenticated and unauthenticated,
    but may return additional data for authenticated agents.

    Args:
        request: FastAPI request object
        credentials: Bearer token credentials (optional)
        db: Database session

    Returns:
        Agent context if authenticated, None otherwise
    """
    if not credentials:
        return None

    auth_service = AuthenticationService(db)
    agent_context = await auth_service.authenticate_token(credentials.credentials)

    if agent_context:
        request.state.agent = agent_context

    return agent_context


def require_scopes(*required_scopes: str):
    """
    Dependency factory that requires specific scopes.

    Usage:
        @router.post("/admin/action")
        async def admin_action(agent: dict = Depends(require_scopes("admin"))):
            ...

    Args:
        required_scopes: Scopes that must all be present

    Returns:
        Dependency function that validates scopes
    """

    async def scope_validator(
        agent: Annotated[dict[str, Any], Depends(get_current_agent)],
    ) -> dict[str, Any]:
        agent_scopes = set(agent.get("scopes", []))
        missing = set(required_scopes) - agent_scopes

        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Missing scopes: {list(missing)}",
            )

        return agent

    return scope_validator


def require_any_scope(*required_scopes: str):
    """
    Dependency factory that requires at least one of the specified scopes.

    Args:
        required_scopes: At least one of these scopes must be present

    Returns:
        Dependency function that validates scopes
    """

    async def scope_validator(
        agent: Annotated[dict[str, Any], Depends(get_current_agent)],
    ) -> dict[str, Any]:
        agent_scopes = set(agent.get("scopes", []))

        if not agent_scopes.intersection(required_scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {list(required_scopes)}",
            )

        return agent

    return scope_validator


# Type aliases for cleaner endpoint signatures
CurrentAgent = Annotated[dict[str, Any], Depends(get_current_agent)]
OptionalAgent = Annotated[dict[str, Any] | None, Depends(get_optional_agent)]
