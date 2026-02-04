"""User repository for PostgreSQL operations.

Provides data access for User entities stored in PostgreSQL.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, select, update
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from platform.infrastructure.database.models import Base
from platform.repositories.base import BaseRepository
from platform.repositories.exceptions import DuplicateEntityError, EntityNotFoundError
from platform.shared.utils.datetime_utils import utcnow
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# ===========================================
# USER ORM MODEL
# ===========================================


class UserModel(Base):
    """User ORM model for PostgreSQL storage."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    roles: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    permissions: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def to_domain(self) -> "User":
        """Convert ORM model to domain User dataclass."""
        from platform.security.base import User, UserStatus

        return User(
            user_id=str(self.id),
            username=self.username,
            email=self.email,
            password_hash=self.password_hash,
            status=UserStatus(self.status),
            roles=list(self.roles) if self.roles else [],
            permissions=list(self.permissions) if self.permissions else [],
            metadata=dict(self.metadata_) if self.metadata_ else {},
            created_at=self.created_at,
            updated_at=self.updated_at,
            last_login=self.last_login,
            login_count=self.login_count,
        )

    @classmethod
    def from_domain(cls, user: "User") -> "UserModel":
        """Create ORM model from domain User dataclass."""
        return cls(
            id=user.user_id if isinstance(user.user_id, UUID) else UUID(user.user_id),
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            status=user.status.value,
            roles=user.roles,
            permissions=user.permissions,
            metadata_=user.metadata,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login=user.last_login,
            login_count=user.login_count,
        )


# ===========================================
# USER REPOSITORY
# ===========================================


class UserRepository(BaseRepository[UserModel]):
    """Repository for User database operations.

    Provides CRUD operations and queries for users stored in PostgreSQL.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the user repository.

        Args:
            session: Async SQLAlchemy session
        """
        super().__init__(session)

    @property
    def model_class(self) -> type[UserModel]:
        """Return the UserModel class."""
        return UserModel

    async def get_by_id(self, user_id: str | UUID) -> UserModel | None:
        """Get a user by ID.

        Args:
            user_id: The user's unique identifier

        Returns:
            UserModel if found, None otherwise
        """
        if isinstance(user_id, str):
            try:
                user_id = UUID(user_id)
            except ValueError:
                return None

        return await super().get_by_id(user_id)

    async def get_by_username(self, username: str) -> UserModel | None:
        """Get a user by username.

        Args:
            username: The username to search for

        Returns:
            UserModel if found, None otherwise
        """
        query = select(UserModel).where(UserModel.username == username)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> UserModel | None:
        """Get a user by email.

        Args:
            email: The email to search for

        Returns:
            UserModel if found, None otherwise
        """
        query = select(UserModel).where(UserModel.email == email)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def exists_by_username(self, username: str) -> bool:
        """Check if a username exists.

        Args:
            username: The username to check

        Returns:
            True if exists, False otherwise
        """
        query = select(UserModel.id).where(UserModel.username == username)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def exists_by_email(self, email: str) -> bool:
        """Check if an email exists.

        Args:
            email: The email to check

        Returns:
            True if exists, False otherwise
        """
        query = select(UserModel.id).where(UserModel.email == email)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def create_user(
        self,
        username: str,
        email: str,
        password_hash: str,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        status: str = "active",
        metadata: dict[str, Any] | None = None,
    ) -> UserModel:
        """Create a new user.

        Args:
            username: Unique username
            email: Unique email address
            password_hash: Hashed password
            roles: List of role names
            permissions: List of direct permissions
            status: User status (active, inactive, suspended, etc.)
            metadata: Additional user metadata

        Returns:
            The created UserModel
        """
        user = UserModel(
            username=username,
            email=email,
            password_hash=password_hash,
            status=status,
            roles=roles or [],
            permissions=permissions or [],
            metadata_=metadata or {},
        )

        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)

        logger.info("user_created", user_id=str(user.id), username=username)
        return user

    async def update_user(
        self,
        user_id: str | UUID,
        **kwargs: Any,
    ) -> UserModel | None:
        """Update a user's fields.

        Args:
            user_id: The user ID to update
            **kwargs: Fields to update (username, email, status, roles, permissions, metadata)

        Returns:
            Updated UserModel if found, None otherwise
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        # Map metadata to metadata_ for ORM
        if "metadata" in kwargs:
            kwargs["metadata_"] = kwargs.pop("metadata")

        return await super().update(user_id, **kwargs)

    async def update_password(
        self,
        user_id: str | UUID,
        password_hash: str,
    ) -> bool:
        """Update a user's password hash.

        Args:
            user_id: The user ID
            password_hash: The new password hash

        Returns:
            True if updated, False if user not found
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        result = await self.session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(password_hash=password_hash, updated_at=utcnow())
        )
        return result.rowcount > 0

    async def update_login_info(self, user_id: str | UUID) -> bool:
        """Update user's login timestamp and count.

        Args:
            user_id: The user ID

        Returns:
            True if updated, False if user not found
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        result = await self.session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(
                last_login=utcnow(),
                login_count=UserModel.login_count + 1,
            )
        )
        return result.rowcount > 0

    async def update_status(self, user_id: str | UUID, status: str) -> bool:
        """Update a user's status.

        Args:
            user_id: The user ID
            status: New status value

        Returns:
            True if updated, False if user not found
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        result = await self.session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(status=status, updated_at=utcnow())
        )

        if result.rowcount > 0:
            logger.info("user_status_updated", user_id=str(user_id), status=status)

        return result.rowcount > 0

    async def add_role(self, user_id: str | UUID, role: str) -> bool:
        """Add a role to a user.

        Args:
            user_id: The user ID
            role: Role name to add

        Returns:
            True if role added, False if user not found or role already exists
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False

        if role in user.roles:
            return True

        new_roles = list(user.roles) + [role]
        await self.session.execute(
            update(UserModel)
            .where(UserModel.id == user.id)
            .values(roles=new_roles, updated_at=utcnow())
        )

        return True

    async def remove_role(self, user_id: str | UUID, role: str) -> bool:
        """Remove a role from a user.

        Args:
            user_id: The user ID
            role: Role name to remove

        Returns:
            True if role removed, False if user not found
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False

        if role not in user.roles:
            return True

        new_roles = [r for r in user.roles if r != role]
        await self.session.execute(
            update(UserModel)
            .where(UserModel.id == user.id)
            .values(roles=new_roles, updated_at=utcnow())
        )

        return True

    async def list_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UserModel]:
        """List users by status.

        Args:
            status: Status to filter by
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching users
        """
        query = (
            select(UserModel)
            .where(UserModel.status == status)
            .limit(limit)
            .offset(offset)
            .order_by(UserModel.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_role(
        self,
        role: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UserModel]:
        """List users who have a specific role.

        Args:
            role: Role to filter by
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching users
        """
        query = (
            select(UserModel)
            .where(UserModel.roles.any(role))
            .limit(limit)
            .offset(offset)
            .order_by(UserModel.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search(
        self,
        query_text: str,
        limit: int = 20,
    ) -> list[UserModel]:
        """Search users by username or email.

        Args:
            query_text: Text to search for
            limit: Maximum number to return

        Returns:
            List of matching users
        """
        pattern = f"%{query_text}%"
        query = (
            select(UserModel)
            .where(
                (UserModel.username.ilike(pattern)) |
                (UserModel.email.ilike(pattern))
            )
            .limit(limit)
            .order_by(UserModel.username)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
