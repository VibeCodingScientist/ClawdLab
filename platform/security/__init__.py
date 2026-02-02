"""Security and Access Control Module.

This module provides comprehensive security features including:
- Authentication (password, token, API key)
- Authorization (RBAC, policies)
- Audit logging
- Session management
"""

from platform.security.api import router
from platform.security.audit import AuditService, get_audit_service
from platform.security.auth import AuthenticationService, get_auth_service
from platform.security.authorization import AuthorizationService, get_authorization_service
from platform.security.base import (
    APIKey,
    AuditAction,
    AuditEntry,
    AuditResult,
    AuthorizationContext,
    AuthorizationResult,
    Permission,
    Policy,
    Role,
    Session,
    Token,
    TokenType,
    User,
    UserProfile,
    UserStatus,
)
from platform.security.config import (
    AUDIT_EVENT_TYPES,
    DEFAULT_ROLES,
    RESOURCE_PERMISSIONS,
    SecuritySettings,
    get_settings,
)
from platform.security.service import SecurityService, get_security_service

__all__ = [
    # API
    "router",
    # Services
    "SecurityService",
    "get_security_service",
    "AuthenticationService",
    "get_auth_service",
    "AuthorizationService",
    "get_authorization_service",
    "AuditService",
    "get_audit_service",
    # Config
    "SecuritySettings",
    "get_settings",
    "DEFAULT_ROLES",
    "RESOURCE_PERMISSIONS",
    "AUDIT_EVENT_TYPES",
    # Base classes - Enums
    "UserStatus",
    "TokenType",
    "AuditAction",
    "AuditResult",
    # Base classes - User
    "User",
    "UserProfile",
    # Base classes - Role and Permission
    "Permission",
    "Role",
    "Policy",
    # Base classes - Token
    "Token",
    "Session",
    "APIKey",
    # Base classes - Audit
    "AuditEntry",
    # Base classes - Authorization
    "AuthorizationContext",
    "AuthorizationResult",
]
