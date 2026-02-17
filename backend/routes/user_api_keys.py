"""CRUD endpoints for user API keys (long-lived programmatic access)."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import (
    generate_api_token,
    get_current_user,
    hash_token,
)
from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import User, UserApiKey
from backend.schemas import (
    UserApiKeyCreateRequest,
    UserApiKeyCreateResponse,
    UserApiKeyListResponse,
    UserApiKeyResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/user/api-keys", tags=["user-api-keys"])

MAX_KEYS_PER_USER = 10


@router.get("", response_model=UserApiKeyListResponse)
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all active (non-revoked) API keys for the current user."""
    result = await db.execute(
        select(UserApiKey)
        .where(
            UserApiKey.user_id == user.id,
            UserApiKey.revoked_at.is_(None),
        )
        .order_by(UserApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return UserApiKeyListResponse(
        items=[UserApiKeyResponse.model_validate(k) for k in keys],
        total=len(keys),
    )


@router.post("", response_model=UserApiKeyCreateResponse, status_code=201)
async def create_api_key(
    body: UserApiKeyCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new API key. The raw token is returned only once."""
    # Enforce per-user limit
    count_result = await db.execute(
        select(func.count()).where(
            UserApiKey.user_id == user.id,
            UserApiKey.revoked_at.is_(None),
        )
    )
    active_count = count_result.scalar() or 0
    if active_count >= MAX_KEYS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_KEYS_PER_USER} active API keys allowed. Revoke an existing key first.",
        )

    # Generate token
    raw_token = generate_api_token(prefix="clab_user_")
    token_hash_value = hash_token(raw_token)
    token_prefix = raw_token[:12]

    expires_at = None
    if body.expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)

    api_key = UserApiKey(
        user_id=user.id,
        name=body.name,
        token_hash=token_hash_value,
        token_prefix=token_prefix,
        scopes=body.scopes,
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    logger.info(
        "user_api_key_created",
        user_id=str(user.id),
        key_id=str(api_key.id),
        name=body.name,
    )

    return UserApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        token=raw_token,
        prefix=token_prefix,
        scopes=api_key.scopes,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Soft-revoke an API key (sets revoked_at timestamp)."""
    from uuid import UUID as PyUUID

    try:
        key_uuid = PyUUID(key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key ID")

    result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.id == key_uuid,
            UserApiKey.user_id == user.id,
            UserApiKey.revoked_at.is_(None),
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.revoked_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(
        "user_api_key_revoked",
        user_id=str(user.id),
        key_id=str(api_key.id),
    )
