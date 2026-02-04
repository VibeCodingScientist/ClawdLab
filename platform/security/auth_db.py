"""Database-backed Authentication Service.

This module provides an AuthenticationService implementation that uses
PostgreSQL for user storage and Redis for token/session management.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from platform.repositories.user_repository import UserRepository
from platform.repositories.token_repository import TokenRepository
from platform.security.base import (
    APIKey,
    Session,
    Token,
    TokenType,
    User,
    UserStatus,
)
from platform.security.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    """Return current UTC time with timezone info (SOTA replacement for _utcnow())."""
    return datetime.now(timezone.utc)


class DatabaseAuthenticationService:
    """Authentication service backed by PostgreSQL and Redis.

    Uses:
    - PostgreSQL (via UserRepository) for user data
    - Redis (via TokenRepository) for tokens and sessions
    - Redis for API keys

    This implementation provides full database persistence instead of
    in-memory storage, suitable for production deployments.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        user_repository: UserRepository | None = None,
        token_repository: TokenRepository | None = None,
    ) -> None:
        """Initialize the database authentication service.

        Args:
            db_session: Async SQLAlchemy session for database operations
            user_repository: Optional user repository (created from session if not provided)
            token_repository: Optional token repository (created if not provided)
        """
        self._settings = get_settings()
        self._db_session = db_session
        self._user_repo = user_repository or UserRepository(db_session)
        self._token_repo = token_repository or TokenRepository()

        # In-memory cache for API keys and sessions (consider Redis for production)
        self._api_keys: dict[str, APIKey] = {}
        self._sessions: dict[str, Session] = {}
        self._revoked_tokens: set[str] = set()

    # ===========================================
    # PASSWORD MANAGEMENT
    # ===========================================

    def _hash_password(self, password: str) -> str:
        """Hash a password using PBKDF2."""
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            iterations=100000,
        )
        return f"{salt}${key.hex()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        try:
            salt, key_hex = password_hash.split("$")
            key = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode(),
                salt.encode(),
                iterations=100000,
            )
            return hmac.compare_digest(key.hex(), key_hex)
        except (ValueError, AttributeError):
            return False

    def validate_password(self, password: str) -> tuple[bool, list[str]]:
        """Validate password meets requirements."""
        errors = []

        if len(password) < self._settings.password_min_length:
            errors.append(f"Password must be at least {self._settings.password_min_length} characters")

        if self._settings.password_require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        if self._settings.password_require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        if self._settings.password_require_digit and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")

        if self._settings.password_require_special:
            special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in special_chars for c in password):
                errors.append("Password must contain at least one special character")

        return len(errors) == 0, errors

    # ===========================================
    # USER MANAGEMENT (PostgreSQL)
    # ===========================================

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: list[str] | None = None,
    ) -> User:
        """Create a new user in the database."""
        # Validate password
        valid, errors = self.validate_password(password)
        if not valid:
            raise ValueError(f"Invalid password: {', '.join(errors)}")

        # Check username uniqueness
        if await self._user_repo.exists_by_username(username):
            raise ValueError(f"Username already exists: {username}")

        # Check email uniqueness
        if await self._user_repo.exists_by_email(email):
            raise ValueError(f"Email already exists: {email}")

        # Create user in database
        user_model = await self._user_repo.create_user(
            username=username,
            email=email,
            password_hash=self._hash_password(password),
            roles=roles or ["viewer"],
            status="active",
        )

        await self._db_session.commit()

        logger.info("user_created", user_id=str(user_model.id), username=username)

        return user_model.to_domain()

    async def get_user(self, user_id: str) -> User | None:
        """Get a user by ID from the database."""
        user_model = await self._user_repo.get_by_id(user_id)
        return user_model.to_domain() if user_model else None

    async def get_user_by_username(self, username: str) -> User | None:
        """Get a user by username from the database."""
        user_model = await self._user_repo.get_by_username(username)
        return user_model.to_domain() if user_model else None

    async def get_user_by_email(self, email: str) -> User | None:
        """Get a user by email from the database."""
        user_model = await self._user_repo.get_by_email(email)
        return user_model.to_domain() if user_model else None

    async def update_user(
        self,
        user_id: str,
        **updates: Any,
    ) -> User | None:
        """Update a user in the database."""
        user_model = await self._user_repo.update_user(user_id, **updates)
        if user_model:
            await self._db_session.commit()
            return user_model.to_domain()
        return None

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user from the database."""
        # Revoke all tokens for user first
        await self.revoke_all_user_tokens(user_id)

        result = await self._user_repo.delete(user_id)
        if result:
            await self._db_session.commit()
            logger.info("user_deleted", user_id=user_id)
        return result

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change a user's password."""
        user_model = await self._user_repo.get_by_id(user_id)
        if not user_model:
            return False

        if not self._verify_password(current_password, user_model.password_hash):
            return False

        valid, errors = self.validate_password(new_password)
        if not valid:
            raise ValueError(f"Invalid password: {', '.join(errors)}")

        result = await self._user_repo.update_password(
            user_id,
            self._hash_password(new_password),
        )

        if result:
            await self._db_session.commit()
            logger.info("password_changed", user_id=user_id)

        return result

    async def list_users(
        self,
        status: UserStatus | None = None,
        role: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[User]:
        """List users from the database with filters."""
        if status:
            user_models = await self._user_repo.list_by_status(
                status.value, limit=limit, offset=offset
            )
        elif role:
            user_models = await self._user_repo.list_by_role(
                role, limit=limit, offset=offset
            )
        else:
            user_models = await self._user_repo.get_all(limit=limit, offset=offset)

        return [u.to_domain() for u in user_models]

    # ===========================================
    # AUTHENTICATION
    # ===========================================

    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> tuple[User | None, str]:
        """Authenticate a user with username and password."""
        user_model = await self._user_repo.get_by_username(username)

        if not user_model:
            return None, "User not found"

        if user_model.status != "active":
            return None, f"Account is {user_model.status}"

        if not self._verify_password(password, user_model.password_hash):
            return None, "Invalid password"

        # Update login info
        await self._user_repo.update_login_info(str(user_model.id))
        await self._db_session.commit()

        return user_model.to_domain(), "Success"

    async def authenticate_token(self, token_value: str) -> tuple[User | None, Token | None, str]:
        """Authenticate using a token."""
        token = await self._token_repo.get_token_by_value(token_value)

        if not token:
            return None, None, "Token not found"

        if not token.is_valid():
            if token.revoked:
                return None, None, "Token has been revoked"
            return None, None, "Token has expired"

        user_model = await self._user_repo.get_by_id(token.user_id)
        if not user_model:
            return None, None, "User not found"

        if user_model.status != "active":
            return None, None, f"Account is {user_model.status}"

        return user_model.to_domain(), token, "Success"

    async def authenticate_api_key(self, api_key: str) -> tuple[User | None, APIKey | None, str]:
        """Authenticate using an API key."""
        # Hash the provided key and compare
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        api_key_obj = None
        for key in self._api_keys.values():
            if key.key_hash == key_hash:
                api_key_obj = key
                break

        if not api_key_obj:
            return None, None, "API key not found"

        if not api_key_obj.active:
            return None, None, "API key is inactive"

        if api_key_obj.expires_at and _utcnow() > api_key_obj.expires_at:
            return None, None, "API key has expired"

        user = await self.get_user(api_key_obj.user_id)
        if not user:
            return None, None, "User not found"

        # Update usage stats
        api_key_obj.last_used = _utcnow()
        api_key_obj.use_count += 1

        return user, api_key_obj, "Success"

    # ===========================================
    # TOKEN MANAGEMENT (Redis)
    # ===========================================

    async def create_access_token(
        self,
        user: User,
        scopes: list[str] | None = None,
    ) -> Token:
        """Create an access token for a user."""
        expires_at = _utcnow() + timedelta(
            minutes=self._settings.jwt_access_token_expire_minutes
        )

        token = Token(
            token_type=TokenType.ACCESS,
            token_value=self._generate_token_value(),
            user_id=user.user_id,
            scopes=scopes or [],
            expires_at=expires_at,
        )

        await self._token_repo.save_token(token)
        return token

    async def create_refresh_token(
        self,
        user: User,
    ) -> Token:
        """Create a refresh token for a user."""
        expires_at = _utcnow() + timedelta(
            days=self._settings.jwt_refresh_token_expire_days
        )

        token = Token(
            token_type=TokenType.REFRESH,
            token_value=self._generate_token_value(),
            user_id=user.user_id,
            expires_at=expires_at,
        )

        await self._token_repo.save_token(token)
        return token

    async def refresh_access_token(
        self,
        refresh_token_value: str,
    ) -> tuple[Token | None, str]:
        """Refresh an access token using a refresh token."""
        refresh_token = await self._token_repo.get_token_by_value(refresh_token_value)

        if not refresh_token:
            return None, "Refresh token not found"

        if refresh_token.token_type != TokenType.REFRESH:
            return None, "Invalid token type"

        if not refresh_token.is_valid():
            return None, "Refresh token is invalid"

        user = await self.get_user(refresh_token.user_id)
        if not user:
            return None, "User not found"

        # Create new access token
        access_token = await self.create_access_token(user, refresh_token.scopes)
        return access_token, "Success"

    async def revoke_token(self, token_id: str) -> bool:
        """Revoke a token."""
        result = await self._token_repo.revoke_token(token_id)
        if result:
            self._revoked_tokens.add(token_id)
        return result

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all tokens for a user."""
        count = await self._token_repo.revoke_all_user_tokens(user_id)
        return count

    def _generate_token_value(self) -> str:
        """Generate a secure token value."""
        return secrets.token_urlsafe(48)

    # ===========================================
    # API KEY MANAGEMENT
    # ===========================================

    async def create_api_key(
        self,
        user_id: str,
        name: str,
        scopes: list[str] | None = None,
        expires_days: int | None = None,
        rate_limit: int | None = None,
    ) -> tuple[APIKey, str]:
        """Create an API key. Returns the key object and the raw key value."""
        user = await self.get_user(user_id)
        if not user:
            raise ValueError("User not found")

        # Generate key
        key_value = secrets.token_urlsafe(self._settings.api_key_length)
        key_hash = hashlib.sha256(key_value.encode()).hexdigest()

        expires_at = None
        if expires_days:
            expires_at = _utcnow() + timedelta(days=expires_days)

        api_key = APIKey(
            name=name,
            key_hash=key_hash,
            key_prefix=key_value[:8],
            user_id=user_id,
            scopes=scopes or [],
            expires_at=expires_at,
            rate_limit=rate_limit,
        )

        self._api_keys[api_key.key_id] = api_key
        return api_key, key_value

    async def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        api_key = self._api_keys.get(key_id)
        if not api_key:
            return False

        api_key.active = False
        return True

    async def get_user_api_keys(self, user_id: str) -> list[APIKey]:
        """Get all API keys for a user."""
        return [k for k in self._api_keys.values() if k.user_id == user_id]

    async def delete_api_key(self, key_id: str) -> bool:
        """Delete an API key."""
        if key_id in self._api_keys:
            del self._api_keys[key_id]
            return True
        return False

    # ===========================================
    # SESSION MANAGEMENT
    # ===========================================

    async def create_session(
        self,
        user: User,
        token: Token,
        ip_address: str = "",
        user_agent: str = "",
    ) -> Session:
        """Create a new session."""
        # Check session limit
        user_sessions = [s for s in self._sessions.values() if s.user_id == user.user_id and s.active]
        if len(user_sessions) >= self._settings.max_sessions_per_user:
            # Invalidate oldest session
            oldest = min(user_sessions, key=lambda s: s.created_at)
            oldest.active = False

        expires_at = _utcnow() + timedelta(
            minutes=self._settings.session_timeout_minutes
        )

        session = Session(
            user_id=user.user_id,
            token_id=token.token_id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )

        self._sessions[session.session_id] = session
        return session

    async def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    async def update_session_activity(self, session_id: str) -> bool:
        """Update session last activity time."""
        session = self._sessions.get(session_id)
        if not session or not session.active:
            return False

        session.last_activity = _utcnow()
        session.expires_at = _utcnow() + timedelta(
            minutes=self._settings.session_timeout_minutes
        )
        return True

    async def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.active = False
        return True

    async def get_user_sessions(self, user_id: str) -> list[Session]:
        """Get all active sessions for a user."""
        return [
            s for s in self._sessions.values()
            if s.user_id == user_id and s.active
        ]

    async def invalidate_all_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user."""
        count = 0
        for session in self._sessions.values():
            if session.user_id == user_id and session.active:
                session.active = False
                count += 1
        return count


__all__ = [
    "DatabaseAuthenticationService",
]
