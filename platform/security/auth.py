"""Authentication Service."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Any

from platform.security.base import (
    APIKey,
    Session,
    Token,
    TokenType,
    User,
    UserStatus,
)
from platform.security.config import get_settings


class AuthenticationService:
    """Service for authentication and token management."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._users: dict[str, User] = {}
        self._tokens: dict[str, Token] = {}
        self._sessions: dict[str, Session] = {}
        self._api_keys: dict[str, APIKey] = {}
        self._revoked_tokens: set[str] = set()

        self._init_default_users()

    def _init_default_users(self) -> None:
        """Initialize default system users."""
        # System admin user
        admin = User(
            user_id="system-admin",
            username="admin",
            email="admin@system.local",
            password_hash=self._hash_password("admin"),  # Change in production!
            status=UserStatus.ACTIVE,
            roles=["admin"],
        )
        self._users[admin.user_id] = admin

        # Service account
        service = User(
            user_id="system-service",
            username="service",
            email="service@system.local",
            password_hash="",
            status=UserStatus.ACTIVE,
            roles=["service"],
        )
        self._users[service.user_id] = service

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
    # USER MANAGEMENT
    # ===========================================

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: list[str] | None = None,
    ) -> User:
        """Create a new user."""
        # Validate password
        valid, errors = self.validate_password(password)
        if not valid:
            raise ValueError(f"Invalid password: {', '.join(errors)}")

        # Check username uniqueness
        if any(u.username == username for u in self._users.values()):
            raise ValueError(f"Username already exists: {username}")

        # Check email uniqueness
        if any(u.email == email for u in self._users.values()):
            raise ValueError(f"Email already exists: {email}")

        user = User(
            username=username,
            email=email,
            password_hash=self._hash_password(password),
            status=UserStatus.ACTIVE,
            roles=roles or ["viewer"],
        )

        self._users[user.user_id] = user
        return user

    async def get_user(self, user_id: str) -> User | None:
        """Get a user by ID."""
        return self._users.get(user_id)

    async def get_user_by_username(self, username: str) -> User | None:
        """Get a user by username."""
        for user in self._users.values():
            if user.username == username:
                return user
        return None

    async def get_user_by_email(self, email: str) -> User | None:
        """Get a user by email."""
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    async def update_user(
        self,
        user_id: str,
        **updates: Any,
    ) -> User | None:
        """Update a user."""
        user = self._users.get(user_id)
        if not user:
            return None

        if "username" in updates:
            user.username = updates["username"]
        if "email" in updates:
            user.email = updates["email"]
        if "status" in updates:
            user.status = UserStatus(updates["status"])
        if "roles" in updates:
            user.roles = updates["roles"]
        if "permissions" in updates:
            user.permissions = updates["permissions"]
        if "metadata" in updates:
            user.metadata.update(updates["metadata"])

        user.updated_at = datetime.utcnow()
        return user

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        if user_id in self._users:
            del self._users[user_id]
            # Revoke all tokens for user
            for token in list(self._tokens.values()):
                if token.user_id == user_id:
                    token.revoked = True
                    token.revoked_at = datetime.utcnow()
            return True
        return False

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change a user's password."""
        user = self._users.get(user_id)
        if not user:
            return False

        if not self._verify_password(current_password, user.password_hash):
            return False

        valid, errors = self.validate_password(new_password)
        if not valid:
            raise ValueError(f"Invalid password: {', '.join(errors)}")

        user.password_hash = self._hash_password(new_password)
        user.updated_at = datetime.utcnow()
        return True

    async def list_users(
        self,
        status: UserStatus | None = None,
        role: str | None = None,
    ) -> list[User]:
        """List users with filters."""
        users = list(self._users.values())

        if status:
            users = [u for u in users if u.status == status]

        if role:
            users = [u for u in users if role in u.roles]

        return users

    # ===========================================
    # AUTHENTICATION
    # ===========================================

    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> tuple[User | None, str]:
        """Authenticate a user with username and password."""
        user = await self.get_user_by_username(username)

        if not user:
            return None, "User not found"

        if user.status != UserStatus.ACTIVE:
            return None, f"Account is {user.status.value}"

        if not self._verify_password(password, user.password_hash):
            return None, "Invalid password"

        # Update login info
        user.last_login = datetime.utcnow()
        user.login_count += 1

        return user, "Success"

    async def authenticate_token(self, token_value: str) -> tuple[User | None, Token | None, str]:
        """Authenticate using a token."""
        # Find token
        token = None
        for t in self._tokens.values():
            if t.token_value == token_value:
                token = t
                break

        if not token:
            return None, None, "Token not found"

        if not token.is_valid():
            if token.revoked:
                return None, None, "Token has been revoked"
            return None, None, "Token has expired"

        user = self._users.get(token.user_id)
        if not user:
            return None, None, "User not found"

        if user.status != UserStatus.ACTIVE:
            return None, None, f"Account is {user.status.value}"

        return user, token, "Success"

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

        if api_key_obj.expires_at and datetime.utcnow() > api_key_obj.expires_at:
            return None, None, "API key has expired"

        user = self._users.get(api_key_obj.user_id)
        if not user:
            return None, None, "User not found"

        # Update usage stats
        api_key_obj.last_used = datetime.utcnow()
        api_key_obj.use_count += 1

        return user, api_key_obj, "Success"

    # ===========================================
    # TOKEN MANAGEMENT
    # ===========================================

    async def create_access_token(
        self,
        user: User,
        scopes: list[str] | None = None,
    ) -> Token:
        """Create an access token for a user."""
        expires_at = datetime.utcnow() + timedelta(
            minutes=self._settings.jwt_access_token_expire_minutes
        )

        token = Token(
            token_type=TokenType.ACCESS,
            token_value=self._generate_token_value(),
            user_id=user.user_id,
            scopes=scopes or [],
            expires_at=expires_at,
        )

        self._tokens[token.token_id] = token
        return token

    async def create_refresh_token(
        self,
        user: User,
    ) -> Token:
        """Create a refresh token for a user."""
        expires_at = datetime.utcnow() + timedelta(
            days=self._settings.jwt_refresh_token_expire_days
        )

        token = Token(
            token_type=TokenType.REFRESH,
            token_value=self._generate_token_value(),
            user_id=user.user_id,
            expires_at=expires_at,
        )

        self._tokens[token.token_id] = token
        return token

    async def refresh_access_token(
        self,
        refresh_token_value: str,
    ) -> tuple[Token | None, str]:
        """Refresh an access token using a refresh token."""
        # Find refresh token
        refresh_token = None
        for t in self._tokens.values():
            if t.token_value == refresh_token_value and t.token_type == TokenType.REFRESH:
                refresh_token = t
                break

        if not refresh_token:
            return None, "Refresh token not found"

        if not refresh_token.is_valid():
            return None, "Refresh token is invalid"

        user = self._users.get(refresh_token.user_id)
        if not user:
            return None, "User not found"

        # Create new access token
        access_token = await self.create_access_token(user, refresh_token.scopes)
        return access_token, "Success"

    async def revoke_token(self, token_id: str) -> bool:
        """Revoke a token."""
        token = self._tokens.get(token_id)
        if not token:
            return False

        token.revoked = True
        token.revoked_at = datetime.utcnow()
        self._revoked_tokens.add(token.token_id)
        return True

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all tokens for a user."""
        count = 0
        for token in self._tokens.values():
            if token.user_id == user_id and not token.revoked:
                token.revoked = True
                token.revoked_at = datetime.utcnow()
                self._revoked_tokens.add(token.token_id)
                count += 1
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
        user = self._users.get(user_id)
        if not user:
            raise ValueError("User not found")

        # Generate key
        key_value = secrets.token_urlsafe(self._settings.api_key_length)
        key_hash = hashlib.sha256(key_value.encode()).hexdigest()

        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

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

        expires_at = datetime.utcnow() + timedelta(
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

        session.last_activity = datetime.utcnow()
        session.expires_at = datetime.utcnow() + timedelta(
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


# Singleton instance
_auth_service: AuthenticationService | None = None


def get_auth_service() -> AuthenticationService:
    """Get or create authentication service singleton."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthenticationService()
    return _auth_service


__all__ = [
    "AuthenticationService",
    "get_auth_service",
]
