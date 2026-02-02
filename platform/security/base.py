"""Base classes and data structures for Security and Access Control."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class UserStatus(Enum):
    """Status of a user account."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    DELETED = "deleted"


class TokenType(Enum):
    """Type of authentication token."""

    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"
    SERVICE = "service"


class AuditAction(Enum):
    """Type of audit action."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    GRANT = "grant"
    REVOKE = "revoke"
    DENY = "deny"
    EXECUTE = "execute"


class AuditResult(Enum):
    """Result of an audited action."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    ERROR = "error"


# ===========================================
# USER DATA CLASSES
# ===========================================


@dataclass
class User:
    """A user account."""

    user_id: str = field(default_factory=lambda: str(uuid4()))
    username: str = ""
    email: str = ""
    password_hash: str = ""
    status: UserStatus = UserStatus.PENDING
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)  # Direct permissions
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_login: datetime | None = None
    login_count: int = 0

    def to_dict(self, include_sensitive: bool = False) -> dict[str, Any]:
        result = {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "status": self.status.value,
            "roles": self.roles,
            "permissions": self.permissions,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "login_count": self.login_count,
        }
        if include_sensitive:
            result["password_hash"] = self.password_hash
        return result


@dataclass
class UserProfile:
    """User profile information."""

    user_id: str = ""
    display_name: str = ""
    organization: str = ""
    department: str = ""
    title: str = ""
    bio: str = ""
    avatar_url: str = ""
    preferences: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "organization": self.organization,
            "department": self.department,
            "title": self.title,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "preferences": self.preferences,
        }


# ===========================================
# ROLE AND PERMISSION DATA CLASSES
# ===========================================


@dataclass
class Permission:
    """A permission definition."""

    permission_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""  # e.g., "experiments:read"
    resource: str = ""  # e.g., "experiments"
    action: str = ""  # e.g., "read"
    description: str = ""
    conditions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "permission_id": self.permission_id,
            "name": self.name,
            "resource": self.resource,
            "action": self.action,
            "description": self.description,
            "conditions": self.conditions,
        }

    @classmethod
    def from_string(cls, perm_str: str) -> "Permission":
        """Create permission from string like 'experiments:read'."""
        parts = perm_str.split(":", 1)
        resource = parts[0] if parts else ""
        action = parts[1] if len(parts) > 1 else "*"
        return cls(
            name=perm_str,
            resource=resource,
            action=action,
        )


@dataclass
class Role:
    """A role with permissions."""

    role_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    permissions: list[str] = field(default_factory=list)
    is_system: bool = False  # System roles cannot be deleted
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "description": self.description,
            "permissions": self.permissions,
            "is_system": self.is_system,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Policy:
    """An access control policy."""

    policy_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    effect: str = "allow"  # allow or deny
    principals: list[str] = field(default_factory=list)  # user_ids or role names
    resources: list[str] = field(default_factory=list)  # resource patterns
    actions: list[str] = field(default_factory=list)  # action patterns
    conditions: dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Higher priority evaluated first
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "effect": self.effect,
            "principals": self.principals,
            "resources": self.resources,
            "actions": self.actions,
            "conditions": self.conditions,
            "priority": self.priority,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
        }


# ===========================================
# TOKEN DATA CLASSES
# ===========================================


@dataclass
class Token:
    """An authentication token."""

    token_id: str = field(default_factory=lambda: str(uuid4()))
    token_type: TokenType = TokenType.ACCESS
    token_value: str = ""
    user_id: str = ""
    scopes: list[str] = field(default_factory=list)
    issued_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    revoked: bool = False
    revoked_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_value: bool = False) -> dict[str, Any]:
        result = {
            "token_id": self.token_id,
            "token_type": self.token_type.value,
            "user_id": self.user_id,
            "scopes": self.scopes,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked": self.revoked,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "metadata": self.metadata,
        }
        if include_value:
            result["token_value"] = self.token_value
        return result

    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if token is valid."""
        return not self.revoked and not self.is_expired()


@dataclass
class Session:
    """A user session."""

    session_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    token_id: str = ""
    ip_address: str = ""
    user_agent: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "token_id": self.token_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "active": self.active,
        }


@dataclass
class APIKey:
    """An API key for programmatic access."""

    key_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    key_hash: str = ""  # Hashed key value
    key_prefix: str = ""  # First few chars for identification
    user_id: str = ""
    scopes: list[str] = field(default_factory=list)
    rate_limit: int | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    last_used: datetime | None = None
    use_count: int = 0
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "key_id": self.key_id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "user_id": self.user_id,
            "scopes": self.scopes,
            "rate_limit": self.rate_limit,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "use_count": self.use_count,
            "active": self.active,
        }


# ===========================================
# AUDIT DATA CLASSES
# ===========================================


@dataclass
class AuditEntry:
    """An audit log entry."""

    entry_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: str = ""
    action: AuditAction = AuditAction.READ
    result: AuditResult = AuditResult.SUCCESS
    user_id: str = ""
    username: str = ""
    resource_type: str = ""
    resource_id: str = ""
    ip_address: str = ""
    user_agent: str = ""
    request_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    changes: dict[str, Any] = field(default_factory=dict)  # Before/after values
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "event_type": self.event_type,
            "action": self.action.value,
            "result": self.result.value,
            "user_id": self.user_id,
            "username": self.username,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
            "details": self.details,
            "changes": self.changes,
            "timestamp": self.timestamp.isoformat(),
        }


# ===========================================
# AUTHORIZATION DATA CLASSES
# ===========================================


@dataclass
class AuthorizationContext:
    """Context for authorization decisions."""

    user_id: str = ""
    username: str = ""
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    resource: str = ""
    action: str = ""
    resource_id: str = ""
    ip_address: str = ""
    request_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "roles": self.roles,
            "permissions": self.permissions,
            "resource": self.resource,
            "action": self.action,
            "resource_id": self.resource_id,
            "ip_address": self.ip_address,
            "request_id": self.request_id,
            "metadata": self.metadata,
        }


@dataclass
class AuthorizationResult:
    """Result of an authorization check."""

    allowed: bool = False
    reason: str = ""
    matched_policy: str = ""
    matched_permission: str = ""
    context: AuthorizationContext | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "matched_policy": self.matched_policy,
            "matched_permission": self.matched_permission,
            "context": self.context.to_dict() if self.context else None,
        }


__all__ = [
    # Enums
    "UserStatus",
    "TokenType",
    "AuditAction",
    "AuditResult",
    # User classes
    "User",
    "UserProfile",
    # Role and permission classes
    "Permission",
    "Role",
    "Policy",
    # Token classes
    "Token",
    "Session",
    "APIKey",
    # Audit classes
    "AuditEntry",
    # Authorization classes
    "AuthorizationContext",
    "AuthorizationResult",
]
