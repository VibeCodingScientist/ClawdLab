"""User test data factory."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from platform.security.base import User, UserStatus, Token, TokenType, APIKey, Session


def _utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass
class UserFactory:
    """Factory for creating User test instances."""

    # Default values that can be overridden
    user_id: str | None = None
    username: str | None = None
    email: str | None = None
    password_hash: str = "hashed_password_placeholder"
    status: UserStatus = UserStatus.ACTIVE
    roles: list[str] | None = None
    permissions: list[str] | None = None
    metadata: dict[str, Any] | None = None

    _counter: int = field(default=0, repr=False)

    @classmethod
    def create(
        cls,
        user_id: str | None = None,
        username: str | None = None,
        email: str | None = None,
        password_hash: str = "hashed_password_placeholder",
        status: UserStatus = UserStatus.ACTIVE,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> User:
        """Create a User instance with sensible defaults."""
        cls._counter = getattr(cls, "_counter", 0) + 1

        return User(
            user_id=user_id or str(uuid4()),
            username=username or f"testuser_{cls._counter}",
            email=email or f"testuser_{cls._counter}@example.com",
            password_hash=password_hash,
            status=status,
            roles=roles or ["researcher"],
            permissions=permissions or ["experiments:read"],
            metadata=metadata or {},
            created_at=_utcnow(),
            updated_at=_utcnow(),
            last_login=None,
            login_count=0,
        )

    @classmethod
    def create_admin(cls, **kwargs: Any) -> User:
        """Create an admin User instance."""
        return cls.create(
            username=kwargs.pop("username", "admin"),
            email=kwargs.pop("email", "admin@example.com"),
            roles=kwargs.pop("roles", ["admin"]),
            permissions=kwargs.pop("permissions", ["*"]),
            **kwargs,
        )

    @classmethod
    def create_service_account(cls, **kwargs: Any) -> User:
        """Create a service account User instance."""
        return cls.create(
            username=kwargs.pop("username", "service"),
            email=kwargs.pop("email", "service@system.local"),
            roles=kwargs.pop("roles", ["service"]),
            permissions=kwargs.pop("permissions", ["service:*"]),
            password_hash="",  # Service accounts don't have passwords
            **kwargs,
        )

    @classmethod
    def create_batch(cls, count: int, **kwargs: Any) -> list[User]:
        """Create multiple User instances."""
        return [cls.create(**kwargs) for _ in range(count)]


@dataclass
class TokenFactory:
    """Factory for creating Token test instances."""

    _counter: int = field(default=0, repr=False)

    @classmethod
    def create(
        cls,
        token_id: str | None = None,
        token_type: TokenType = TokenType.ACCESS,
        token_value: str | None = None,
        user_id: str | None = None,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
        revoked: bool = False,
        **kwargs: Any,
    ) -> Token:
        """Create a Token instance with sensible defaults."""
        import secrets
        from datetime import timedelta

        cls._counter = getattr(cls, "_counter", 0) + 1

        return Token(
            token_id=token_id or str(uuid4()),
            token_type=token_type,
            token_value=token_value or secrets.token_urlsafe(48),
            user_id=user_id or str(uuid4()),
            scopes=scopes or ["read", "write"],
            issued_at=_utcnow(),
            expires_at=expires_at or _utcnow() + timedelta(hours=1),
            revoked=revoked,
            revoked_at=None,
            metadata={},
        )

    @classmethod
    def create_access_token(cls, user: User | None = None, **kwargs: Any) -> Token:
        """Create an access Token for a user."""
        return cls.create(
            token_type=TokenType.ACCESS,
            user_id=user.user_id if user else kwargs.pop("user_id", None),
            **kwargs,
        )

    @classmethod
    def create_refresh_token(cls, user: User | None = None, **kwargs: Any) -> Token:
        """Create a refresh Token for a user."""
        from datetime import timedelta

        return cls.create(
            token_type=TokenType.REFRESH,
            user_id=user.user_id if user else kwargs.pop("user_id", None),
            expires_at=kwargs.pop("expires_at", _utcnow() + timedelta(days=7)),
            **kwargs,
        )

    @classmethod
    def create_expired_token(cls, **kwargs: Any) -> Token:
        """Create an expired Token."""
        from datetime import timedelta

        return cls.create(
            expires_at=_utcnow() - timedelta(hours=1),
            **kwargs,
        )

    @classmethod
    def create_revoked_token(cls, **kwargs: Any) -> Token:
        """Create a revoked Token."""
        token = cls.create(revoked=True, **kwargs)
        token.revoked_at = _utcnow()
        return token


@dataclass
class APIKeyFactory:
    """Factory for creating APIKey test instances."""

    _counter: int = field(default=0, repr=False)

    @classmethod
    def create(
        cls,
        key_id: str | None = None,
        name: str | None = None,
        key_hash: str | None = None,
        key_prefix: str | None = None,
        user_id: str | None = None,
        scopes: list[str] | None = None,
        rate_limit: int | None = None,
        expires_at: datetime | None = None,
        active: bool = True,
        **kwargs: Any,
    ) -> APIKey:
        """Create an APIKey instance with sensible defaults."""
        import hashlib
        import secrets
        from datetime import timedelta

        cls._counter = getattr(cls, "_counter", 0) + 1

        raw_key = secrets.token_urlsafe(32)

        return APIKey(
            key_id=key_id or str(uuid4()),
            name=name or f"test_api_key_{cls._counter}",
            key_hash=key_hash or hashlib.sha256(raw_key.encode()).hexdigest(),
            key_prefix=key_prefix or f"srp_{raw_key[:8]}",
            user_id=user_id or str(uuid4()),
            scopes=scopes or ["read", "write"],
            rate_limit=rate_limit or 1000,
            created_at=_utcnow(),
            expires_at=expires_at or _utcnow() + timedelta(days=365),
            last_used=None,
            use_count=0,
            active=active,
        )

    @classmethod
    def create_with_raw_key(cls, **kwargs: Any) -> tuple[APIKey, str]:
        """Create an APIKey and return both the key object and raw key value."""
        import hashlib
        import secrets

        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        api_key = cls.create(
            key_hash=key_hash,
            key_prefix=f"srp_{raw_key[:8]}",
            **kwargs,
        )

        return api_key, raw_key


@dataclass
class SessionFactory:
    """Factory for creating Session test instances."""

    _counter: int = field(default=0, repr=False)

    @classmethod
    def create(
        cls,
        session_id: str | None = None,
        user_id: str | None = None,
        token_id: str | None = None,
        ip_address: str = "127.0.0.1",
        user_agent: str = "TestClient/1.0",
        expires_at: datetime | None = None,
        active: bool = True,
        **kwargs: Any,
    ) -> Session:
        """Create a Session instance with sensible defaults."""
        from datetime import timedelta

        cls._counter = getattr(cls, "_counter", 0) + 1

        return Session(
            session_id=session_id or str(uuid4()),
            user_id=user_id or str(uuid4()),
            token_id=token_id or str(uuid4()),
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=_utcnow(),
            last_activity=_utcnow(),
            expires_at=expires_at or _utcnow() + timedelta(hours=24),
            active=active,
        )
