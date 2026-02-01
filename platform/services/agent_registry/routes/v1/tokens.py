"""Token management endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.session import get_db
from platform.services.agent_registry.dependencies import CurrentAgent
from platform.services.agent_registry.exceptions import (
    TokenNotFoundError,
    raise_http_exception,
)
from platform.services.agent_registry.schemas import (
    ErrorResponse,
    TokenCreateRequest,
    TokenCreateResponse,
    TokenListResponse,
    TokenResponse,
)
from platform.services.agent_registry.service import TokenService
from platform.shared.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ===========================================
# TOKEN MANAGEMENT ENDPOINTS
# ===========================================


@router.get(
    "/me/tokens",
    response_model=TokenListResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def list_tokens(
    agent: CurrentAgent,
    db: AsyncSession = Depends(get_db),
):
    """
    List all tokens for the current agent.

    Returns both active and revoked tokens, sorted by creation date.
    Token values are never returned - only metadata for identification.
    """
    service = TokenService(db)
    tokens = await service.list_tokens(agent["agent_id"])

    return TokenListResponse(
        tokens=[TokenResponse(**t) for t in tokens],
        total=len(tokens),
    )


@router.post(
    "/me/tokens",
    response_model=TokenCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def create_token(
    request: TokenCreateRequest,
    agent: CurrentAgent,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new API token.

    The full token value is only returned once in this response.
    Store it securely as it cannot be retrieved again.

    **Example Request:**
    ```json
    {
        "name": "ci-deployment-token",
        "scopes": ["read", "write"],
        "expires_in_days": 90
    }
    ```
    """
    service = TokenService(db)

    token, token_data = await service.create_token(
        agent_id=agent["agent_id"],
        name=request.name,
        scopes=request.scopes,
        expires_in_days=request.expires_in_days,
    )

    await db.commit()

    logger.info(
        "token_created",
        agent_id=agent["agent_id"],
        token_name=request.name,
        scopes=request.scopes,
    )

    return TokenCreateResponse(
        token=token,
        token_id=token_data["token_id"],
        token_prefix=token_data["token_prefix"],
        name=token_data["name"],
        scopes=token_data["scopes"],
        expires_at=token_data["expires_at"],
    )


@router.delete(
    "/me/tokens/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Token not found"},
    },
)
async def revoke_token(
    token_id: str,
    agent: CurrentAgent,
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke a specific token.

    Revoked tokens cannot be used for authentication.
    This action cannot be undone.
    """
    service = TokenService(db)

    try:
        await service.revoke_token(
            agent_id=agent["agent_id"],
            token_id=token_id,
        )
        logger.info(
            "token_revoked",
            agent_id=agent["agent_id"],
            token_id=token_id,
        )
    except TokenNotFoundError as e:
        raise_http_exception(e)


@router.post(
    "/me/tokens/revoke-all",
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def revoke_all_tokens(
    agent: CurrentAgent,
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke all tokens for the current agent.

    This is a destructive action that will invalidate all existing tokens.
    The agent will need to re-register to obtain a new token.

    Use with caution - primarily for security incidents.
    """
    from platform.services.agent_registry.repository import TokenRepository

    repo = TokenRepository(db)
    count = await repo.revoke_all(agent["agent_id"])
    await db.commit()

    logger.warning(
        "all_tokens_revoked",
        agent_id=agent["agent_id"],
        count=count,
    )

    return {
        "message": f"Revoked {count} token(s)",
        "revoked_count": count,
    }


@router.get(
    "/me/tokens/{token_id}",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Token not found"},
    },
)
async def get_token(
    token_id: str,
    agent: CurrentAgent,
    db: AsyncSession = Depends(get_db),
):
    """
    Get details about a specific token.

    Returns metadata about the token, not the token value itself.
    """
    from platform.services.agent_registry.repository import TokenRepository

    repo = TokenRepository(db)
    token = await repo.get_by_id(token_id)

    if not token or str(token.agent_id) != str(agent["agent_id"]):
        raise_http_exception(TokenNotFoundError(token_id))

    return TokenResponse(
        token_id=str(token.id),
        token_prefix=token.token_prefix,
        name=token.name,
        scopes=token.scopes,
        created_at=token.created_at,
        expires_at=token.expires_at,
        last_used_at=token.last_used_at,
        is_revoked=token.revoked_at is not None,
    )


@router.post(
    "/me/tokens/{token_id}/rotate",
    response_model=TokenCreateResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Token not found"},
    },
)
async def rotate_token(
    token_id: str,
    agent: CurrentAgent,
    db: AsyncSession = Depends(get_db),
):
    """
    Rotate a token (revoke old, create new with same config).

    This atomically revokes the existing token and creates a new one
    with the same name and scopes. Use this for regular security rotation.

    Returns the new token - store it securely as this is the only time
    the full token value is returned.
    """
    from platform.services.agent_registry.repository import TokenRepository

    repo = TokenRepository(db)
    old_token = await repo.get_by_id(token_id)

    if not old_token or str(old_token.agent_id) != str(agent["agent_id"]):
        raise_http_exception(TokenNotFoundError(token_id))

    if old_token.revoked_at is not None:
        raise_http_exception(TokenNotFoundError(token_id))

    # Revoke old token
    await repo.revoke(token_id)

    # Create new token with same configuration
    service = TokenService(db)
    new_token, token_data = await service.create_token(
        agent_id=agent["agent_id"],
        name=old_token.name or "rotated",
        scopes=old_token.scopes,
        expires_in_days=365,  # Default expiry for rotated tokens
    )

    await db.commit()

    logger.info(
        "token_rotated",
        agent_id=agent["agent_id"],
        old_token_id=token_id,
        new_token_id=token_data["token_id"],
    )

    return TokenCreateResponse(
        token=new_token,
        token_id=token_data["token_id"],
        token_prefix=token_data["token_prefix"],
        name=token_data["name"],
        scopes=token_data["scopes"],
        expires_at=token_data["expires_at"],
    )
