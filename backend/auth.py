"""Authentication and cryptographic utilities for agent identity + human JWT auth."""

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# JWT Configuration (human auth)
# ---------------------------------------------------------------------------

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET_KEY environment variable is required")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30


def create_access_token(user_id: str) -> str:
    """Create a JWT access token for a human user."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a JWT refresh token for a human user."""
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "exp": expire, "type": "refresh", "jti": secrets.token_urlsafe(16)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and validate a JWT token. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ---------------------------------------------------------------------------
# Cryptographic Identity
# ---------------------------------------------------------------------------


@dataclass
class AgentIdentity:
    """Represents an agent's cryptographic identity."""

    public_key: Ed25519PublicKey
    agent_id: str  # Derived from public key hash

    @classmethod
    def from_public_key_bytes(cls, public_key_bytes: bytes) -> "AgentIdentity":
        """Create identity from raw public key bytes (32 bytes)."""
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        agent_id = hashlib.sha256(public_key_bytes).hexdigest()[:32]
        return cls(public_key=public_key, agent_id=agent_id)

    @classmethod
    def from_public_key_base64(cls, b64: str) -> "AgentIdentity":
        """Create identity from base64-encoded public key."""
        public_key_bytes = base64.b64decode(b64)
        return cls.from_public_key_bytes(public_key_bytes)

    def verify_signature(self, message: bytes, signature: bytes) -> bool:
        """Verify a signature from this agent."""
        try:
            self.public_key.verify(signature, message)
            return True
        except Exception:
            return False

    def get_public_key_base64(self) -> str:
        """Get base64-encoded raw public key."""
        raw_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(raw_bytes).decode()


def generate_agent_keypair() -> tuple[Ed25519PrivateKey, AgentIdentity]:
    """Generate a new agent keypair."""
    private_key = Ed25519PrivateKey.generate()
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    identity = AgentIdentity.from_public_key_bytes(public_key_bytes)
    return private_key, identity


def generate_api_token(prefix: str = "clab_") -> str:
    """Generate a secure API token with the clab_ prefix."""
    return f"{prefix}{secrets.token_urlsafe(48)}"


def hash_token(token: str) -> str:
    """Hash a token for secure storage using SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return secrets.compare_digest(a.encode(), b.encode())


# ---------------------------------------------------------------------------
# FastAPI Auth Dependencies
# ---------------------------------------------------------------------------


async def get_current_agent(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    FastAPI dependency: extract and validate Bearer token.

    Returns the Agent ORM object or raises 401.
    """
    from backend.models import Agent, AgentToken

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty token",
        )

    # Look up by prefix (first 8 chars) then verify hash
    token_prefix = token[:8]
    token_hash_value = hash_token(token)

    result = await db.execute(
        select(AgentToken).where(
            AgentToken.token_prefix == token_prefix,
            AgentToken.revoked_at.is_(None),
        )
    )
    db_token = result.scalar_one_or_none()

    if db_token is None or not constant_time_compare(db_token.token_hash, token_hash_value):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked token",
        )

    # Check expiry
    if db_token.expires_at is not None:
        from datetime import datetime, timezone

        if datetime.now(timezone.utc) > db_token.expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            )

    # Load the agent
    agent_result = await db.execute(
        select(Agent).where(Agent.id == db_token.agent_id)
    )
    agent = agent_result.scalar_one_or_none()

    if agent is None or agent.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent not found or suspended",
        )

    return agent


async def get_current_agent_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    FastAPI dependency: optional agent auth.

    Returns Agent or None (no exception if missing).
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    try:
        return await get_current_agent(request, db)
    except HTTPException:
        return None


# ---------------------------------------------------------------------------
# Lab Role Helpers
# ---------------------------------------------------------------------------


async def require_lab_membership(
    db: AsyncSession,
    lab_id: UUID,
    agent_id: UUID,
):
    """Verify agent is an active member of the lab. Raises 403 if not."""
    from backend.models import LabMembership

    result = await db.execute(
        select(LabMembership).where(
            LabMembership.lab_id == lab_id,
            LabMembership.agent_id == agent_id,
            LabMembership.status == "active",
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent is not an active member of this lab",
        )
    return membership


async def require_lab_role(
    db: AsyncSession,
    lab_id: UUID,
    agent_id: UUID,
    role: str,
):
    """Verify agent has a specific role in the lab. Raises 403 if not."""
    membership = await require_lab_membership(db, lab_id, agent_id)
    if membership.role != role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires the '{role}' role",
        )
    return membership


# ---------------------------------------------------------------------------
# Human User Auth Dependencies
# ---------------------------------------------------------------------------


async def _authenticate_user_api_key(token: str, db: AsyncSession):
    """Authenticate a user via a clab_user_ API key. Returns User or raises 401."""
    from backend.models import User, UserApiKey

    token_prefix = token[:12]
    token_hash_value = hash_token(token)

    result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.token_prefix == token_prefix,
            UserApiKey.revoked_at.is_(None),
        )
    )
    db_key = result.scalar_one_or_none()

    if db_key is None or not constant_time_compare(db_key.token_hash, token_hash_value):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    # Check expiry
    if db_key.expires_at is not None:
        if datetime.now(timezone.utc) > db_key.expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key expired",
            )

    # Update last_used_at (debounce: only if >5 min since last update)
    now = datetime.now(timezone.utc)
    if db_key.last_used_at is None or (now - db_key.last_used_at).total_seconds() > 300:
        db_key.last_used_at = now
        await db.commit()

    # Load the user
    user_result = await db.execute(
        select(User).where(User.id == db_key.user_id)
    )
    user = user_result.scalar_one_or_none()

    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found or suspended",
        )

    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    FastAPI dependency: extract and validate Bearer token for human users.

    Accepts both JWT access tokens and clab_user_ API keys.
    Returns the User ORM object or raises 401.
    """
    from backend.models import User

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty token",
        )

    # Route to API key auth if token has the clab_user_ prefix
    if token.startswith("clab_user_"):
        return await _authenticate_user_api_key(token, db)

    # Otherwise, treat as JWT
    payload = decode_jwt(token)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found or suspended",
        )

    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Optional human user auth — returns User or None."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None
