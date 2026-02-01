"""Configuration for Security and Access Control."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class SecuritySettings(BaseSettings):
    """Settings for security and access control."""

    model_config = {"env_prefix": "SECURITY_", "case_sensitive": False}

    # Authentication Settings
    auth_enabled: bool = Field(
        default=True,
        description="Enable authentication",
    )
    api_key_header: str = Field(
        default="X-API-Key",
        description="Header name for API key",
    )
    api_key_length: int = Field(
        default=32,
        description="Length of generated API keys",
    )

    # JWT Settings
    jwt_secret_key: str = Field(
        default="change-this-secret-key-in-production",
        description="Secret key for JWT signing",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=60,
        description="Access token expiration in minutes",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token expiration in days",
    )

    # Session Settings
    session_enabled: bool = Field(
        default=True,
        description="Enable session management",
    )
    session_timeout_minutes: int = Field(
        default=60,
        description="Session timeout in minutes",
    )
    max_sessions_per_user: int = Field(
        default=5,
        description="Maximum concurrent sessions per user",
    )

    # Password Settings
    password_min_length: int = Field(
        default=8,
        description="Minimum password length",
    )
    password_require_uppercase: bool = Field(
        default=True,
        description="Require uppercase letters in password",
    )
    password_require_lowercase: bool = Field(
        default=True,
        description="Require lowercase letters in password",
    )
    password_require_digit: bool = Field(
        default=True,
        description="Require digits in password",
    )
    password_require_special: bool = Field(
        default=False,
        description="Require special characters in password",
    )
    password_hash_rounds: int = Field(
        default=12,
        description="Bcrypt hash rounds",
    )

    # Rate Limiting
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting",
    )
    rate_limit_requests_per_minute: int = Field(
        default=60,
        description="Maximum requests per minute",
    )
    rate_limit_burst: int = Field(
        default=10,
        description="Burst allowance",
    )

    # Audit Settings
    audit_enabled: bool = Field(
        default=True,
        description="Enable audit logging",
    )
    audit_retention_days: int = Field(
        default=90,
        description="Days to retain audit logs",
    )
    audit_sensitive_fields: list[str] = Field(
        default=["password", "token", "secret", "api_key"],
        description="Fields to mask in audit logs",
    )

    # CORS Settings
    cors_enabled: bool = Field(
        default=True,
        description="Enable CORS",
    )
    cors_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins",
    )


@lru_cache
def get_settings() -> SecuritySettings:
    """Get cached security settings."""
    return SecuritySettings()


# Default Roles
DEFAULT_ROLES = {
    "admin": {
        "name": "Administrator",
        "description": "Full system access",
        "permissions": ["*"],
    },
    "researcher": {
        "name": "Researcher",
        "description": "Can create and run experiments",
        "permissions": [
            "experiments:read",
            "experiments:create",
            "experiments:update",
            "experiments:run",
            "literature:read",
            "literature:search",
            "knowledge:read",
            "knowledge:create",
            "reports:read",
            "reports:create",
        ],
    },
    "reviewer": {
        "name": "Reviewer",
        "description": "Can review and verify results",
        "permissions": [
            "experiments:read",
            "results:read",
            "results:verify",
            "literature:read",
            "knowledge:read",
            "reports:read",
        ],
    },
    "viewer": {
        "name": "Viewer",
        "description": "Read-only access",
        "permissions": [
            "experiments:read",
            "results:read",
            "literature:read",
            "knowledge:read",
            "reports:read",
        ],
    },
    "agent": {
        "name": "Agent",
        "description": "Autonomous agent access",
        "permissions": [
            "experiments:read",
            "experiments:create",
            "experiments:run",
            "literature:read",
            "literature:search",
            "knowledge:read",
            "knowledge:create",
            "knowledge:update",
            "agents:communicate",
        ],
    },
    "service": {
        "name": "Service Account",
        "description": "Internal service access",
        "permissions": [
            "internal:*",
            "metrics:read",
            "health:read",
        ],
    },
}

# Resource Permissions
RESOURCE_PERMISSIONS = {
    "experiments": ["read", "create", "update", "delete", "run", "cancel"],
    "results": ["read", "create", "update", "delete", "verify"],
    "literature": ["read", "search", "import", "export"],
    "knowledge": ["read", "create", "update", "delete", "query"],
    "reports": ["read", "create", "update", "delete", "export"],
    "agents": ["read", "create", "update", "delete", "communicate", "manage"],
    "users": ["read", "create", "update", "delete", "manage"],
    "roles": ["read", "create", "update", "delete", "assign"],
    "settings": ["read", "update"],
    "metrics": ["read"],
    "health": ["read"],
    "audit": ["read"],
    "internal": ["*"],
}

# Audit Event Types
AUDIT_EVENT_TYPES = {
    "auth.login": "User login",
    "auth.logout": "User logout",
    "auth.login_failed": "Failed login attempt",
    "auth.token_created": "Token created",
    "auth.token_revoked": "Token revoked",
    "auth.password_changed": "Password changed",
    "user.created": "User created",
    "user.updated": "User updated",
    "user.deleted": "User deleted",
    "role.assigned": "Role assigned",
    "role.revoked": "Role revoked",
    "permission.granted": "Permission granted",
    "permission.denied": "Permission denied",
    "resource.accessed": "Resource accessed",
    "resource.created": "Resource created",
    "resource.updated": "Resource updated",
    "resource.deleted": "Resource deleted",
    "security.violation": "Security violation detected",
    "security.rate_limited": "Rate limit exceeded",
}

# Token Types
TOKEN_TYPES = {
    "access": {
        "name": "Access Token",
        "description": "Short-lived token for API access",
    },
    "refresh": {
        "name": "Refresh Token",
        "description": "Long-lived token for refreshing access tokens",
    },
    "api_key": {
        "name": "API Key",
        "description": "Permanent key for programmatic access",
    },
    "service": {
        "name": "Service Token",
        "description": "Token for internal service communication",
    },
}

# Security Headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}
