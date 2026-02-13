"""Human authentication endpoints — register, login, logout, refresh, me."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import (
    create_access_token,
    create_refresh_token,
    decode_jwt,
    get_current_user,
)
from backend.database import get_db
from backend.logging_config import get_logger
from backend.models import User
from backend.redis import get_redis
from backend.schemas import (
    MessageResponse,
    TokenRefreshRequest,
    UserLoginRequest,
    UserLoginResponse,
    UserRegisterRequest,
    UserResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/security", tags=["security"])

REFRESH_TOKEN_TTL = 30 * 24 * 3600  # 30 days in seconds


@router.post("/auth/register", response_model=UserLoginResponse, status_code=201)
async def register(
    body: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new human user."""
    # Check for existing username or email
    existing = await db.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username or email already taken")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=bcrypt.hash(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    # Store refresh token in Redis
    redis = get_redis()
    await redis.set(f"refresh:{str(user.id)}", refresh_token, ex=REFRESH_TOKEN_TTL)

    logger.info("user_registered", username=user.username, user_id=str(user.id))

    return UserLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/auth/login", response_model=UserLoginResponse)
async def login(
    body: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Login with username and password."""
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if user is None or not bcrypt.verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.status != "active":
        raise HTTPException(status_code=403, detail="Account suspended")

    # Update login stats
    user.last_login = datetime.now(timezone.utc)
    user.login_count += 1
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    # Store refresh token in Redis
    redis = get_redis()
    await redis.set(f"refresh:{str(user.id)}", refresh_token, ex=REFRESH_TOKEN_TTL)

    logger.info("user_login", username=user.username, user_id=str(user.id))

    return UserLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/auth/logout", response_model=MessageResponse)
async def logout(
    user: User = Depends(get_current_user),
):
    """Logout — delete refresh token from Redis."""
    redis = get_redis()
    await redis.delete(f"refresh:{str(user.id)}")
    logger.info("user_logout", user_id=str(user.id))
    return MessageResponse(message="Logged out")


@router.post("/auth/refresh", response_model=UserLoginResponse)
async def refresh_token(
    body: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate refresh token and issue new token pair."""
    payload = decode_jwt(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Verify refresh token is still stored in Redis
    redis = get_redis()
    stored = await redis.get(f"refresh:{user_id}")
    if stored != body.refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token revoked or expired")

    # Load user
    from uuid import UUID as UUIDType

    result = await db.execute(select(User).where(User.id == UUIDType(user_id)))
    user = result.scalar_one_or_none()
    if user is None or user.status != "active":
        raise HTTPException(status_code=403, detail="User not found or suspended")

    # Issue new pair
    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)
    await redis.set(f"refresh:{user_id}", new_refresh, ex=REFRESH_TOKEN_TTL)

    return UserLoginResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        user=UserResponse.model_validate(user),
    )


@router.get("/users/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
):
    """Get current authenticated user profile."""
    return UserResponse.model_validate(user)
