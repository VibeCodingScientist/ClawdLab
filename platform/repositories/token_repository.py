"""Token repository for Redis operations.

Provides data access for tokens and sessions stored in Redis
with TTL-based expiration.
"""

import json
from datetime import timedelta
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from platform.repositories.exceptions import ValidationError
from platform.shared.utils.datetime_utils import utcnow
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# Validation constants
MIN_TOKEN_EXPIRY_SECONDS = 60  # 1 minute
MAX_TOKEN_EXPIRY_SECONDS = 365 * 24 * 60 * 60  # 1 year
MAX_SCAN_ITERATIONS = 100  # Limit scan iterations to prevent DoS


@runtime_checkable
class RedisClientProtocol(Protocol):
    """Protocol for Redis client interface."""

    async def get(self, key: str) -> bytes | str | None: ...
    async def set(self, key: str, value: str) -> bool: ...
    async def setex(self, key: str, seconds: int, value: str) -> bool: ...
    async def delete(self, *keys: str) -> int: ...
    async def exists(self, *keys: str) -> int: ...
    async def ttl(self, key: str) -> int: ...
    async def sadd(self, key: str, *members: str) -> int: ...
    async def srem(self, key: str, *members: str) -> int: ...
    async def smembers(self, key: str) -> set[bytes | str]: ...
    async def scan(self, cursor: int, match: str | None = None, count: int | None = None) -> tuple[int, list[bytes]]: ...
    async def mget(self, *keys: str) -> list[bytes | str | None]: ...


def _validate_token_params(
    token_id: str,
    user_id: str,
    token_value: str,
    expires_in_seconds: int,
) -> None:
    """Validate token parameters.

    Raises:
        ValidationError: If any parameter is invalid
    """
    if not token_id or not token_id.strip():
        raise ValidationError("Token ID cannot be empty", field="token_id")
    if not user_id or not user_id.strip():
        raise ValidationError("User ID cannot be empty", field="user_id")
    if not token_value or not token_value.strip():
        raise ValidationError("Token value cannot be empty", field="token_value")
    if expires_in_seconds < MIN_TOKEN_EXPIRY_SECONDS:
        raise ValidationError(
            f"Token expiry must be at least {MIN_TOKEN_EXPIRY_SECONDS} seconds",
            field="expires_in_seconds",
        )
    if expires_in_seconds > MAX_TOKEN_EXPIRY_SECONDS:
        raise ValidationError(
            f"Token expiry cannot exceed {MAX_TOKEN_EXPIRY_SECONDS} seconds",
            field="expires_in_seconds",
        )


class TokenRepository:
    """Repository for Token operations using Redis.

    Stores access tokens, refresh tokens, and sessions in Redis
    with automatic expiration via TTL.
    """

    # Key prefixes for different token types
    ACCESS_TOKEN_PREFIX = "token:access:"
    REFRESH_TOKEN_PREFIX = "token:refresh:"
    SESSION_PREFIX = "session:"
    USER_TOKENS_PREFIX = "user:tokens:"
    USER_SESSIONS_PREFIX = "user:sessions:"
    REVOKED_PREFIX = "revoked:"
    API_KEY_PREFIX = "apikey:"

    def __init__(self, redis_client: Any) -> None:
        """Initialize the token repository.

        Args:
            redis_client: Async Redis client instance
        """
        self.redis = redis_client

    # ===========================================
    # ACCESS TOKEN OPERATIONS
    # ===========================================

    async def store_access_token(
        self,
        token_id: str,
        user_id: str,
        token_value: str,
        scopes: list[str],
        expires_in_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Store an access token.

        Args:
            token_id: Unique token identifier
            user_id: User ID this token belongs to
            token_value: The actual token value
            scopes: List of permission scopes
            expires_in_seconds: TTL in seconds
            metadata: Additional token metadata

        Returns:
            True if stored successfully
        """
        key = f"{self.ACCESS_TOKEN_PREFIX}{token_id}"

        token_data = {
            "token_id": token_id,
            "user_id": user_id,
            "token_value": token_value,
            "scopes": scopes,
            "created_at": utcnow().isoformat(),
            "expires_at": (utcnow() + timedelta(seconds=expires_in_seconds)).isoformat(),
            "metadata": metadata or {},
        }

        # Store token with TTL
        await self.redis.setex(
            key,
            expires_in_seconds,
            json.dumps(token_data),
        )

        # Add to user's token set
        user_tokens_key = f"{self.USER_TOKENS_PREFIX}{user_id}"
        await self.redis.sadd(user_tokens_key, token_id)

        logger.debug("access_token_stored", token_id=token_id, user_id=user_id)
        return True

    async def get_access_token(self, token_id: str) -> dict[str, Any] | None:
        """Get an access token by ID.

        Args:
            token_id: The token ID to retrieve

        Returns:
            Token data dict if found and not expired, None otherwise
        """
        key = f"{self.ACCESS_TOKEN_PREFIX}{token_id}"
        data = await self.redis.get(key)

        if not data:
            return None

        return json.loads(data)

    async def get_access_token_by_value(self, token_value: str) -> dict[str, Any] | None:
        """Get an access token by its value.

        Note: This requires scanning, prefer using token_id when possible.

        Args:
            token_value: The token value to search for

        Returns:
            Token data dict if found, None otherwise
        """
        # This is a simplified implementation
        # In production, consider using a secondary index
        pattern = f"{self.ACCESS_TOKEN_PREFIX}*"
        cursor = 0

        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)

            for key in keys:
                data = await self.redis.get(key)
                if data:
                    token_data = json.loads(data)
                    if token_data.get("token_value") == token_value:
                        return token_data

            if cursor == 0:
                break

        return None

    async def revoke_access_token(self, token_id: str) -> bool:
        """Revoke an access token.

        Args:
            token_id: The token ID to revoke

        Returns:
            True if revoked, False if not found
        """
        key = f"{self.ACCESS_TOKEN_PREFIX}{token_id}"

        # Get token data first to find user_id
        data = await self.redis.get(key)
        if not data:
            return False

        token_data = json.loads(data)
        user_id = token_data.get("user_id")

        # Delete the token
        await self.redis.delete(key)

        # Remove from user's token set
        if user_id:
            user_tokens_key = f"{self.USER_TOKENS_PREFIX}{user_id}"
            await self.redis.srem(user_tokens_key, token_id)

        # Mark as revoked (optional, for audit)
        revoked_key = f"{self.REVOKED_PREFIX}{token_id}"
        await self.redis.setex(revoked_key, 86400 * 7, "1")  # Keep for 7 days

        logger.info("access_token_revoked", token_id=token_id)
        return True

    async def is_token_revoked(self, token_id: str) -> bool:
        """Check if a token has been revoked.

        Args:
            token_id: The token ID to check

        Returns:
            True if revoked, False otherwise
        """
        revoked_key = f"{self.REVOKED_PREFIX}{token_id}"
        return await self.redis.exists(revoked_key) > 0

    # ===========================================
    # REFRESH TOKEN OPERATIONS
    # ===========================================

    async def store_refresh_token(
        self,
        token_id: str,
        user_id: str,
        token_value: str,
        scopes: list[str],
        expires_in_seconds: int,
        access_token_id: str | None = None,
    ) -> bool:
        """Store a refresh token.

        Args:
            token_id: Unique token identifier
            user_id: User ID this token belongs to
            token_value: The actual token value
            scopes: List of permission scopes
            expires_in_seconds: TTL in seconds
            access_token_id: Associated access token ID (optional)

        Returns:
            True if stored successfully
        """
        key = f"{self.REFRESH_TOKEN_PREFIX}{token_id}"

        token_data = {
            "token_id": token_id,
            "user_id": user_id,
            "token_value": token_value,
            "scopes": scopes,
            "access_token_id": access_token_id,
            "created_at": utcnow().isoformat(),
            "expires_at": (utcnow() + timedelta(seconds=expires_in_seconds)).isoformat(),
        }

        await self.redis.setex(
            key,
            expires_in_seconds,
            json.dumps(token_data),
        )

        logger.debug("refresh_token_stored", token_id=token_id, user_id=user_id)
        return True

    async def get_refresh_token(self, token_id: str) -> dict[str, Any] | None:
        """Get a refresh token by ID.

        Args:
            token_id: The token ID to retrieve

        Returns:
            Token data dict if found, None otherwise
        """
        key = f"{self.REFRESH_TOKEN_PREFIX}{token_id}"
        data = await self.redis.get(key)

        if not data:
            return None

        return json.loads(data)

    async def get_refresh_token_by_value(self, token_value: str) -> dict[str, Any] | None:
        """Get a refresh token by its value.

        Args:
            token_value: The token value to search for

        Returns:
            Token data dict if found, None otherwise
        """
        pattern = f"{self.REFRESH_TOKEN_PREFIX}*"
        cursor = 0

        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)

            for key in keys:
                data = await self.redis.get(key)
                if data:
                    token_data = json.loads(data)
                    if token_data.get("token_value") == token_value:
                        return token_data

            if cursor == 0:
                break

        return None

    async def revoke_refresh_token(self, token_id: str) -> bool:
        """Revoke a refresh token.

        Args:
            token_id: The token ID to revoke

        Returns:
            True if revoked, False if not found
        """
        key = f"{self.REFRESH_TOKEN_PREFIX}{token_id}"

        existed = await self.redis.delete(key) > 0

        if existed:
            revoked_key = f"{self.REVOKED_PREFIX}{token_id}"
            await self.redis.setex(revoked_key, 86400 * 7, "1")
            logger.info("refresh_token_revoked", token_id=token_id)

        return existed

    # ===========================================
    # SESSION OPERATIONS
    # ===========================================

    async def store_session(
        self,
        session_id: str,
        user_id: str,
        token_id: str,
        ip_address: str,
        user_agent: str,
        expires_in_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Store a user session.

        Args:
            session_id: Unique session identifier
            user_id: User ID this session belongs to
            token_id: Associated token ID
            ip_address: Client IP address
            user_agent: Client user agent
            expires_in_seconds: TTL in seconds
            metadata: Additional session metadata

        Returns:
            True if stored successfully
        """
        key = f"{self.SESSION_PREFIX}{session_id}"

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "token_id": token_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "active": True,
            "created_at": utcnow().isoformat(),
            "last_activity": utcnow().isoformat(),
            "expires_at": (utcnow() + timedelta(seconds=expires_in_seconds)).isoformat(),
            "metadata": metadata or {},
        }

        await self.redis.setex(
            key,
            expires_in_seconds,
            json.dumps(session_data),
        )

        # Add to user's session set
        user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
        await self.redis.sadd(user_sessions_key, session_id)

        logger.debug("session_stored", session_id=session_id, user_id=user_id)
        return True

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get a session by ID.

        Args:
            session_id: The session ID to retrieve

        Returns:
            Session data dict if found, None otherwise
        """
        key = f"{self.SESSION_PREFIX}{session_id}"
        data = await self.redis.get(key)

        if not data:
            return None

        return json.loads(data)

    async def update_session_activity(
        self,
        session_id: str,
        expires_in_seconds: int,
    ) -> bool:
        """Update session last activity and extend expiration.

        Args:
            session_id: The session ID to update
            expires_in_seconds: New TTL in seconds

        Returns:
            True if updated, False if not found
        """
        key = f"{self.SESSION_PREFIX}{session_id}"
        data = await self.redis.get(key)

        if not data:
            return False

        session_data = json.loads(data)
        session_data["last_activity"] = utcnow().isoformat()
        session_data["expires_at"] = (utcnow() + timedelta(seconds=expires_in_seconds)).isoformat()

        await self.redis.setex(
            key,
            expires_in_seconds,
            json.dumps(session_data),
        )

        return True

    async def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session.

        Args:
            session_id: The session ID to invalidate

        Returns:
            True if invalidated, False if not found
        """
        key = f"{self.SESSION_PREFIX}{session_id}"

        # Get session data first to find user_id
        data = await self.redis.get(key)
        if not data:
            return False

        session_data = json.loads(data)
        user_id = session_data.get("user_id")

        # Delete the session
        await self.redis.delete(key)

        # Remove from user's session set
        if user_id:
            user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
            await self.redis.srem(user_sessions_key, session_id)

        logger.info("session_invalidated", session_id=session_id)
        return True

    async def get_user_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """Get all active sessions for a user.

        Uses batch operations (mget) for efficient retrieval.

        Args:
            user_id: The user ID

        Returns:
            List of session data dicts
        """
        user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
        session_ids_raw = await self.redis.smembers(user_sessions_key)

        if not session_ids_raw:
            return []

        # Decode session IDs
        session_ids = [
            sid.decode() if isinstance(sid, bytes) else sid
            for sid in session_ids_raw
        ]

        # Build keys for batch fetch
        keys = [f"{self.SESSION_PREFIX}{sid}" for sid in session_ids]

        # Batch fetch all sessions at once (N+1 -> 1 query)
        try:
            results = await self.redis.mget(*keys)
        except AttributeError:
            # Fallback for Redis clients without mget
            logger.warning("Redis client does not support mget, falling back to individual gets")
            results = [await self.redis.get(key) for key in keys]

        sessions = []
        stale_ids = []

        for session_id, data in zip(session_ids, results):
            if data:
                try:
                    session_data = json.loads(data if isinstance(data, str) else data.decode())
                    if session_data.get("active"):
                        sessions.append(session_data)
                except (json.JSONDecodeError, AttributeError):
                    logger.warning("invalid_session_data", session_id=session_id)
                    stale_ids.append(session_id)
            else:
                stale_ids.append(session_id)

        # Batch cleanup of stale references
        if stale_ids:
            for stale_id in stale_ids:
                await self.redis.srem(user_sessions_key, stale_id)

        return sessions

    async def invalidate_all_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user.

        Args:
            user_id: The user ID

        Returns:
            Number of sessions invalidated
        """
        user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
        session_ids = await self.redis.smembers(user_sessions_key)

        count = 0
        for session_id in session_ids:
            if isinstance(session_id, bytes):
                session_id = session_id.decode()

            key = f"{self.SESSION_PREFIX}{session_id}"
            if await self.redis.delete(key) > 0:
                count += 1

        # Clear the user's session set
        await self.redis.delete(user_sessions_key)

        logger.info("all_sessions_invalidated", user_id=user_id, count=count)
        return count

    # ===========================================
    # API KEY OPERATIONS
    # ===========================================

    async def store_api_key_hash(
        self,
        key_id: str,
        key_hash: str,
        key_prefix: str,
        user_id: str,
        name: str,
        scopes: list[str],
        rate_limit: int | None = None,
        expires_in_seconds: int | None = None,
    ) -> bool:
        """Store an API key hash for authentication.

        Args:
            key_id: Unique key identifier
            key_hash: SHA256 hash of the key value
            key_prefix: First few characters for identification
            user_id: User ID this key belongs to
            name: Human-readable key name
            scopes: List of permission scopes
            rate_limit: Requests per minute limit (optional)
            expires_in_seconds: TTL in seconds (optional, None for no expiry)

        Returns:
            True if stored successfully
        """
        key = f"{self.API_KEY_PREFIX}{key_id}"

        key_data = {
            "key_id": key_id,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "user_id": user_id,
            "name": name,
            "scopes": scopes,
            "rate_limit": rate_limit,
            "active": True,
            "created_at": utcnow().isoformat(),
            "last_used": None,
            "use_count": 0,
        }

        if expires_in_seconds:
            key_data["expires_at"] = (
                utcnow() + timedelta(seconds=expires_in_seconds)
            ).isoformat()
            await self.redis.setex(key, expires_in_seconds, json.dumps(key_data))
        else:
            await self.redis.set(key, json.dumps(key_data))

        # Store hash-to-id mapping for authentication lookup
        hash_key = f"{self.API_KEY_PREFIX}hash:{key_hash}"
        await self.redis.set(hash_key, key_id)

        logger.debug("api_key_stored", key_id=key_id, user_id=user_id)
        return True

    async def get_api_key_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        """Get an API key by its hash.

        Args:
            key_hash: SHA256 hash of the key value

        Returns:
            API key data dict if found and active, None otherwise
        """
        # Look up key_id from hash
        hash_key = f"{self.API_KEY_PREFIX}hash:{key_hash}"
        key_id = await self.redis.get(hash_key)

        if not key_id:
            return None

        if isinstance(key_id, bytes):
            key_id = key_id.decode()

        key = f"{self.API_KEY_PREFIX}{key_id}"
        data = await self.redis.get(key)

        if not data:
            return None

        key_data = json.loads(data)

        if not key_data.get("active"):
            return None

        return key_data

    async def update_api_key_usage(self, key_id: str) -> bool:
        """Update API key last used timestamp and count.

        Note: This operation uses atomic updates where possible to prevent
        race conditions when multiple requests use the same API key concurrently.

        Args:
            key_id: The key ID to update

        Returns:
            True if updated, False if not found
        """
        key = f"{self.API_KEY_PREFIX}{key_id}"

        # Try to use WATCH for optimistic locking (handles concurrent updates)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Get current data
                data = await self.redis.get(key)
                if not data:
                    return False

                key_data = json.loads(data if isinstance(data, str) else data.decode())
                current_count = key_data.get("use_count", 0)

                # Update fields
                key_data["last_used"] = utcnow().isoformat()
                key_data["use_count"] = current_count + 1

                # Preserve TTL if it exists
                ttl = await self.redis.ttl(key)
                new_data = json.dumps(key_data)

                # Attempt atomic update
                # Note: For true atomicity in high-concurrency scenarios,
                # consider using a Lua script or Redis Streams
                if ttl > 0:
                    await self.redis.setex(key, ttl, new_data)
                else:
                    await self.redis.set(key, new_data)

                return True

            except Exception as e:
                if attempt == max_retries - 1:
                    # Log generic error without sensitive details
                    logger.warning(
                        "api_key_usage_update_failed",
                        key_id=key_id,
                        attempt=attempt + 1,
                    )
                    raise
                # Brief backoff before retry
                import asyncio
                await asyncio.sleep(0.01 * (attempt + 1))

        return False

    async def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key.

        Args:
            key_id: The key ID to revoke

        Returns:
            True if revoked, False if not found
        """
        key = f"{self.API_KEY_PREFIX}{key_id}"
        data = await self.redis.get(key)

        if not data:
            return False

        key_data = json.loads(data)
        key_data["active"] = False

        # Preserve TTL if it exists
        ttl = await self.redis.ttl(key)
        if ttl > 0:
            await self.redis.setex(key, ttl, json.dumps(key_data))
        else:
            await self.redis.set(key, json.dumps(key_data))

        logger.info("api_key_revoked", key_id=key_id)
        return True

    # ===========================================
    # BULK OPERATIONS
    # ===========================================

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all tokens for a user.

        Args:
            user_id: The user ID

        Returns:
            Number of tokens revoked
        """
        user_tokens_key = f"{self.USER_TOKENS_PREFIX}{user_id}"
        token_ids = await self.redis.smembers(user_tokens_key)

        count = 0
        for token_id in token_ids:
            if isinstance(token_id, bytes):
                token_id = token_id.decode()

            if await self.revoke_access_token(token_id):
                count += 1

        # Clear the user's token set
        await self.redis.delete(user_tokens_key)

        logger.info("all_tokens_revoked", user_id=user_id, count=count)
        return count

    async def cleanup_expired(self) -> int:
        """Clean up expired token references.

        This is a maintenance operation to clean up stale references
        in user token/session sets.

        Returns:
            Number of stale references cleaned
        """
        count = 0

        # Clean up user token sets
        pattern = f"{self.USER_TOKENS_PREFIX}*"
        cursor = 0

        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)

            for key in keys:
                if isinstance(key, bytes):
                    key = key.decode()

                token_ids = await self.redis.smembers(key)
                for token_id in token_ids:
                    if isinstance(token_id, bytes):
                        token_id = token_id.decode()

                    token_key = f"{self.ACCESS_TOKEN_PREFIX}{token_id}"
                    if not await self.redis.exists(token_key):
                        await self.redis.srem(key, token_id)
                        count += 1

            if cursor == 0:
                break

        logger.info("cleanup_completed", stale_refs_removed=count)
        return count
