"""Main Security Service."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from platform.security.audit import AuditService, get_audit_service
from platform.security.auth import AuthenticationService, get_auth_service
from platform.security.authorization import AuthorizationService, get_authorization_service
from platform.security.base import (
    APIKey,
    AuditAction,
    AuditEntry,
    AuditResult,
    AuthorizationResult,
    Policy,
    Role,
    Session,
    Token,
    User,
    UserStatus,
)
from platform.security.config import get_settings


@dataclass
class SecurityStats:
    """Statistics about security service."""

    total_users: int = 0
    active_users: int = 0
    total_roles: int = 0
    total_policies: int = 0
    active_tokens: int = 0
    active_sessions: int = 0
    active_api_keys: int = 0
    total_audit_entries: int = 0
    failed_logins_24h: int = 0
    security_events_24h: int = 0


class SecurityService:
    """Main service for security and access control."""

    def __init__(
        self,
        auth_service: AuthenticationService | None = None,
        authz_service: AuthorizationService | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self._settings = get_settings()
        self._auth = auth_service or get_auth_service()
        self._authz = authz_service or get_authorization_service()
        self._audit = audit_service or get_audit_service()

    # ===========================================
    # USER MANAGEMENT
    # ===========================================

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: list[str] | None = None,
        created_by: str = "system",
        ip_address: str = "",
    ) -> User:
        """Create a new user."""
        user = await self._auth.create_user(username, email, password, roles)

        await self._audit.log(
            event_type="user.created",
            action=AuditAction.CREATE,
            result=AuditResult.SUCCESS,
            user_id=created_by,
            resource_type="user",
            resource_id=user.user_id,
            ip_address=ip_address,
            details={"username": username, "roles": roles},
        )

        return user

    async def get_user(self, user_id: str) -> User | None:
        """Get a user by ID."""
        return await self._auth.get_user(user_id)

    async def get_user_by_username(self, username: str) -> User | None:
        """Get a user by username."""
        return await self._auth.get_user_by_username(username)

    async def update_user(
        self,
        user_id: str,
        updated_by: str = "system",
        ip_address: str = "",
        **updates: Any,
    ) -> User | None:
        """Update a user."""
        user = await self._auth.update_user(user_id, **updates)

        if user:
            await self._audit.log(
                event_type="user.updated",
                action=AuditAction.UPDATE,
                result=AuditResult.SUCCESS,
                user_id=updated_by,
                resource_type="user",
                resource_id=user_id,
                ip_address=ip_address,
                details=updates,
            )

        return user

    async def delete_user(
        self,
        user_id: str,
        deleted_by: str = "system",
        ip_address: str = "",
    ) -> bool:
        """Delete a user."""
        result = await self._auth.delete_user(user_id)

        if result:
            await self._audit.log(
                event_type="user.deleted",
                action=AuditAction.DELETE,
                result=AuditResult.SUCCESS,
                user_id=deleted_by,
                resource_type="user",
                resource_id=user_id,
                ip_address=ip_address,
            )

        return result

    async def list_users(
        self,
        status: UserStatus | None = None,
        role: str | None = None,
    ) -> list[User]:
        """List users."""
        return await self._auth.list_users(status, role)

    async def assign_role(
        self,
        user_id: str,
        role: str,
        assigned_by: str = "system",
        ip_address: str = "",
    ) -> User | None:
        """Assign a role to a user."""
        user = await self._auth.get_user(user_id)
        if not user:
            return None

        if role not in user.roles:
            user.roles.append(role)
            user.updated_at = datetime.utcnow()

            await self._audit.log(
                event_type="role.assigned",
                action=AuditAction.GRANT,
                result=AuditResult.SUCCESS,
                user_id=assigned_by,
                resource_type="user",
                resource_id=user_id,
                ip_address=ip_address,
                details={"role": role},
            )

        return user

    async def revoke_role(
        self,
        user_id: str,
        role: str,
        revoked_by: str = "system",
        ip_address: str = "",
    ) -> User | None:
        """Revoke a role from a user."""
        user = await self._auth.get_user(user_id)
        if not user:
            return None

        if role in user.roles:
            user.roles.remove(role)
            user.updated_at = datetime.utcnow()

            await self._audit.log(
                event_type="role.revoked",
                action=AuditAction.REVOKE,
                result=AuditResult.SUCCESS,
                user_id=revoked_by,
                resource_type="user",
                resource_id=user_id,
                ip_address=ip_address,
                details={"role": role},
            )

        return user

    # ===========================================
    # AUTHENTICATION
    # ===========================================

    async def login(
        self,
        username: str,
        password: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> tuple[User | None, Token | None, str]:
        """Login a user and create tokens."""
        user, message = await self._auth.authenticate(username, password)

        if not user:
            await self._audit.log_auth_event(
                event_type="auth.login_failed",
                result=AuditResult.FAILURE,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                details={"reason": message},
            )
            return None, None, message

        # Create tokens
        access_token = await self._auth.create_access_token(user)
        refresh_token = await self._auth.create_refresh_token(user)

        # Create session
        session = await self._auth.create_session(
            user, access_token, ip_address, user_agent
        )

        await self._audit.log_auth_event(
            event_type="auth.login",
            result=AuditResult.SUCCESS,
            user_id=user.user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"session_id": session.session_id},
        )

        return user, access_token, "Success"

    async def logout(
        self,
        user_id: str,
        token_id: str = "",
        session_id: str = "",
        ip_address: str = "",
    ) -> bool:
        """Logout a user."""
        # Revoke token if provided
        if token_id:
            await self._auth.revoke_token(token_id)

        # Invalidate session if provided
        if session_id:
            await self._auth.invalidate_session(session_id)

        user = await self._auth.get_user(user_id)
        await self._audit.log_auth_event(
            event_type="auth.logout",
            result=AuditResult.SUCCESS,
            user_id=user_id,
            username=user.username if user else "",
            ip_address=ip_address,
        )

        return True

    async def authenticate_request(
        self,
        token_value: str = "",
        api_key: str = "",
        ip_address: str = "",
    ) -> tuple[User | None, str]:
        """Authenticate a request using token or API key."""
        if token_value:
            user, token, message = await self._auth.authenticate_token(token_value)
            return user, message
        elif api_key:
            user, key, message = await self._auth.authenticate_api_key(api_key)
            return user, message
        else:
            return None, "No credentials provided"

    async def refresh_token(
        self,
        refresh_token_value: str,
        ip_address: str = "",
    ) -> tuple[Token | None, str]:
        """Refresh an access token."""
        token, message = await self._auth.refresh_access_token(refresh_token_value)

        if token:
            await self._audit.log(
                event_type="auth.token_created",
                action=AuditAction.CREATE,
                result=AuditResult.SUCCESS,
                user_id=token.user_id,
                ip_address=ip_address,
                details={"token_type": "access", "method": "refresh"},
            )

        return token, message

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        ip_address: str = "",
    ) -> bool:
        """Change a user's password."""
        result = await self._auth.change_password(user_id, current_password, new_password)

        user = await self._auth.get_user(user_id)
        await self._audit.log_auth_event(
            event_type="auth.password_changed",
            result=AuditResult.SUCCESS if result else AuditResult.FAILURE,
            user_id=user_id,
            username=user.username if user else "",
            ip_address=ip_address,
        )

        return result

    # ===========================================
    # API KEY MANAGEMENT
    # ===========================================

    async def create_api_key(
        self,
        user_id: str,
        name: str,
        scopes: list[str] | None = None,
        expires_days: int | None = None,
        ip_address: str = "",
    ) -> tuple[APIKey, str]:
        """Create an API key."""
        api_key, key_value = await self._auth.create_api_key(
            user_id, name, scopes, expires_days
        )

        await self._audit.log(
            event_type="auth.token_created",
            action=AuditAction.CREATE,
            result=AuditResult.SUCCESS,
            user_id=user_id,
            ip_address=ip_address,
            details={"token_type": "api_key", "name": name, "scopes": scopes},
        )

        return api_key, key_value

    async def revoke_api_key(
        self,
        key_id: str,
        revoked_by: str = "system",
        ip_address: str = "",
    ) -> bool:
        """Revoke an API key."""
        result = await self._auth.revoke_api_key(key_id)

        if result:
            await self._audit.log(
                event_type="auth.token_revoked",
                action=AuditAction.REVOKE,
                result=AuditResult.SUCCESS,
                user_id=revoked_by,
                ip_address=ip_address,
                details={"key_id": key_id},
            )

        return result

    async def get_user_api_keys(self, user_id: str) -> list[APIKey]:
        """Get API keys for a user."""
        return await self._auth.get_user_api_keys(user_id)

    # ===========================================
    # AUTHORIZATION
    # ===========================================

    async def authorize(
        self,
        user: User,
        resource: str,
        action: str,
        resource_id: str = "",
        context: dict[str, Any] | None = None,
        ip_address: str = "",
    ) -> AuthorizationResult:
        """Check if user is authorized for an action."""
        result = await self._authz.authorize(
            user, resource, action, resource_id, context
        )

        # Log the authorization check
        await self._audit.log_permission_event(
            event_type="permission.granted" if result.allowed else "permission.denied",
            user_id=user.user_id,
            username=user.username,
            resource=f"{resource}:{resource_id}" if resource_id else resource,
            action_performed=action,
            result=AuditResult.SUCCESS if result.allowed else AuditResult.DENIED,
            ip_address=ip_address,
            details={"reason": result.reason},
        )

        return result

    async def check_permission(
        self,
        user: User,
        permission: str,
    ) -> bool:
        """Quick permission check."""
        return await self._authz.check_permission(user, permission)

    async def get_user_permissions(self, user: User) -> list[str]:
        """Get all permissions for a user."""
        return await self._authz.get_user_permissions(user)

    # ===========================================
    # ROLE MANAGEMENT
    # ===========================================

    async def create_role(
        self,
        name: str,
        description: str = "",
        permissions: list[str] | None = None,
        created_by: str = "system",
        ip_address: str = "",
    ) -> Role:
        """Create a new role."""
        role = await self._authz.create_role(name, description, permissions)

        await self._audit.log(
            event_type="resource.created",
            action=AuditAction.CREATE,
            result=AuditResult.SUCCESS,
            user_id=created_by,
            resource_type="role",
            resource_id=role.role_id,
            ip_address=ip_address,
            details={"name": name, "permissions": permissions},
        )

        return role

    async def get_role(self, role_id: str) -> Role | None:
        """Get a role by ID."""
        return await self._authz.get_role(role_id)

    async def get_role_by_name(self, name: str) -> Role | None:
        """Get a role by name."""
        return await self._authz.get_role_by_name(name)

    async def list_roles(self) -> list[Role]:
        """List all roles."""
        return await self._authz.list_roles()

    async def update_role(
        self,
        role_id: str,
        updated_by: str = "system",
        ip_address: str = "",
        **updates: Any,
    ) -> Role | None:
        """Update a role."""
        role = await self._authz.update_role(role_id, **updates)

        if role:
            await self._audit.log(
                event_type="resource.updated",
                action=AuditAction.UPDATE,
                result=AuditResult.SUCCESS,
                user_id=updated_by,
                resource_type="role",
                resource_id=role_id,
                ip_address=ip_address,
                details=updates,
            )

        return role

    async def delete_role(
        self,
        role_id: str,
        deleted_by: str = "system",
        ip_address: str = "",
    ) -> bool:
        """Delete a role."""
        result = await self._authz.delete_role(role_id)

        if result:
            await self._audit.log(
                event_type="resource.deleted",
                action=AuditAction.DELETE,
                result=AuditResult.SUCCESS,
                user_id=deleted_by,
                resource_type="role",
                resource_id=role_id,
                ip_address=ip_address,
            )

        return result

    # ===========================================
    # POLICY MANAGEMENT
    # ===========================================

    async def create_policy(
        self,
        name: str,
        effect: str,
        principals: list[str],
        resources: list[str],
        actions: list[str],
        description: str = "",
        conditions: dict[str, Any] | None = None,
        created_by: str = "system",
        ip_address: str = "",
    ) -> Policy:
        """Create a new policy."""
        policy = await self._authz.create_policy(
            name, effect, principals, resources, actions, description, conditions
        )

        await self._audit.log(
            event_type="resource.created",
            action=AuditAction.CREATE,
            result=AuditResult.SUCCESS,
            user_id=created_by,
            resource_type="policy",
            resource_id=policy.policy_id,
            ip_address=ip_address,
            details={"name": name, "effect": effect},
        )

        return policy

    async def get_policy(self, policy_id: str) -> Policy | None:
        """Get a policy by ID."""
        return await self._authz.get_policy(policy_id)

    async def list_policies(self) -> list[Policy]:
        """List all policies."""
        return await self._authz.list_policies()

    async def delete_policy(
        self,
        policy_id: str,
        deleted_by: str = "system",
        ip_address: str = "",
    ) -> bool:
        """Delete a policy."""
        result = await self._authz.delete_policy(policy_id)

        if result:
            await self._audit.log(
                event_type="resource.deleted",
                action=AuditAction.DELETE,
                result=AuditResult.SUCCESS,
                user_id=deleted_by,
                resource_type="policy",
                resource_id=policy_id,
                ip_address=ip_address,
            )

        return result

    # ===========================================
    # AUDIT
    # ===========================================

    async def get_audit_entries(
        self,
        user_id: str | None = None,
        event_type: str | None = None,
        resource_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Get audit entries."""
        return await self._audit.get_entries(
            user_id=user_id,
            event_type=event_type,
            resource_type=resource_type,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    async def get_user_activity(
        self,
        user_id: str,
        days: int = 7,
    ) -> list[AuditEntry]:
        """Get user activity."""
        return await self._audit.get_user_activity(user_id, days)

    async def get_security_events(
        self,
        days: int = 7,
    ) -> list[AuditEntry]:
        """Get security events."""
        return await self._audit.get_security_events(days)

    async def get_audit_stats(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get audit statistics."""
        return await self._audit.get_stats(start_time, end_time)

    # ===========================================
    # STATISTICS
    # ===========================================

    async def get_stats(self) -> SecurityStats:
        """Get security statistics."""
        users = await self._auth.list_users()
        roles = await self._authz.list_roles()
        policies = await self._authz.list_policies()

        # Count active items
        active_users = sum(1 for u in users if u.status == UserStatus.ACTIVE)

        # Get audit stats
        from datetime import timedelta
        start_24h = datetime.utcnow() - timedelta(hours=24)
        failed_logins = await self._audit.get_failed_logins(days=1)
        security_events = await self._audit.get_security_events(days=1)
        audit_stats = await self._audit.get_stats()

        return SecurityStats(
            total_users=len(users),
            active_users=active_users,
            total_roles=len(roles),
            total_policies=len(policies),
            active_tokens=len([t for t in self._auth._tokens.values() if t.is_valid()]),
            active_sessions=len([s for s in self._auth._sessions.values() if s.active]),
            active_api_keys=len([k for k in self._auth._api_keys.values() if k.active]),
            total_audit_entries=audit_stats["total_entries"],
            failed_logins_24h=len(failed_logins),
            security_events_24h=len(security_events),
        )


# Singleton instance
_service: SecurityService | None = None


def get_security_service() -> SecurityService:
    """Get or create security service singleton."""
    global _service
    if _service is None:
        _service = SecurityService()
    return _service


__all__ = [
    "SecurityStats",
    "SecurityService",
    "get_security_service",
]
