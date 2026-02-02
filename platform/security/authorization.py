"""Authorization and Access Control Service."""

import fnmatch
from datetime import datetime
from typing import Any

from platform.security.base import (
    AuthorizationContext,
    AuthorizationResult,
    Permission,
    Policy,
    Role,
    User,
)
from platform.security.config import DEFAULT_ROLES, RESOURCE_PERMISSIONS, get_settings


class AuthorizationService:
    """Service for authorization and access control."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._roles: dict[str, Role] = {}
        self._policies: dict[str, Policy] = {}
        self._permissions: dict[str, Permission] = {}

        self._init_default_roles()
        self._init_permissions()

    def _init_default_roles(self) -> None:
        """Initialize default system roles."""
        for role_name, role_info in DEFAULT_ROLES.items():
            role = Role(
                role_id=f"system-{role_name}",
                name=role_name,
                description=role_info["description"],
                permissions=role_info["permissions"],
                is_system=True,
            )
            self._roles[role.role_id] = role

    def _init_permissions(self) -> None:
        """Initialize permissions from resource definitions."""
        for resource, actions in RESOURCE_PERMISSIONS.items():
            for action in actions:
                perm_name = f"{resource}:{action}"
                permission = Permission(
                    name=perm_name,
                    resource=resource,
                    action=action,
                    description=f"{action.title()} {resource}",
                )
                self._permissions[perm_name] = permission

    # ===========================================
    # ROLE MANAGEMENT
    # ===========================================

    async def create_role(
        self,
        name: str,
        description: str = "",
        permissions: list[str] | None = None,
    ) -> Role:
        """Create a new role."""
        # Check name uniqueness
        for role in self._roles.values():
            if role.name == name:
                raise ValueError(f"Role already exists: {name}")

        role = Role(
            name=name,
            description=description,
            permissions=permissions or [],
        )

        self._roles[role.role_id] = role
        return role

    async def get_role(self, role_id: str) -> Role | None:
        """Get a role by ID."""
        return self._roles.get(role_id)

    async def get_role_by_name(self, name: str) -> Role | None:
        """Get a role by name."""
        for role in self._roles.values():
            if role.name == name:
                return role
        return None

    async def update_role(
        self,
        role_id: str,
        **updates: Any,
    ) -> Role | None:
        """Update a role."""
        role = self._roles.get(role_id)
        if not role:
            return None

        if role.is_system:
            raise ValueError("Cannot modify system roles")

        if "name" in updates:
            role.name = updates["name"]
        if "description" in updates:
            role.description = updates["description"]
        if "permissions" in updates:
            role.permissions = updates["permissions"]

        role.updated_at = datetime.utcnow()
        return role

    async def delete_role(self, role_id: str) -> bool:
        """Delete a role."""
        role = self._roles.get(role_id)
        if not role:
            return False

        if role.is_system:
            raise ValueError("Cannot delete system roles")

        del self._roles[role_id]
        return True

    async def list_roles(self) -> list[Role]:
        """List all roles."""
        return list(self._roles.values())

    async def add_permission_to_role(
        self,
        role_id: str,
        permission: str,
    ) -> Role | None:
        """Add a permission to a role."""
        role = self._roles.get(role_id)
        if not role:
            return None

        if permission not in role.permissions:
            role.permissions.append(permission)
            role.updated_at = datetime.utcnow()

        return role

    async def remove_permission_from_role(
        self,
        role_id: str,
        permission: str,
    ) -> Role | None:
        """Remove a permission from a role."""
        role = self._roles.get(role_id)
        if not role:
            return None

        if permission in role.permissions:
            role.permissions.remove(permission)
            role.updated_at = datetime.utcnow()

        return role

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
        priority: int = 0,
    ) -> Policy:
        """Create a new policy."""
        if effect not in ["allow", "deny"]:
            raise ValueError("Effect must be 'allow' or 'deny'")

        policy = Policy(
            name=name,
            description=description,
            effect=effect,
            principals=principals,
            resources=resources,
            actions=actions,
            conditions=conditions or {},
            priority=priority,
        )

        self._policies[policy.policy_id] = policy
        return policy

    async def get_policy(self, policy_id: str) -> Policy | None:
        """Get a policy by ID."""
        return self._policies.get(policy_id)

    async def update_policy(
        self,
        policy_id: str,
        **updates: Any,
    ) -> Policy | None:
        """Update a policy."""
        policy = self._policies.get(policy_id)
        if not policy:
            return None

        if "name" in updates:
            policy.name = updates["name"]
        if "description" in updates:
            policy.description = updates["description"]
        if "effect" in updates:
            policy.effect = updates["effect"]
        if "principals" in updates:
            policy.principals = updates["principals"]
        if "resources" in updates:
            policy.resources = updates["resources"]
        if "actions" in updates:
            policy.actions = updates["actions"]
        if "conditions" in updates:
            policy.conditions = updates["conditions"]
        if "priority" in updates:
            policy.priority = updates["priority"]
        if "enabled" in updates:
            policy.enabled = updates["enabled"]

        return policy

    async def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    async def list_policies(self) -> list[Policy]:
        """List all policies."""
        return list(self._policies.values())

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
    ) -> AuthorizationResult:
        """Check if a user is authorized to perform an action."""
        auth_context = AuthorizationContext(
            user_id=user.user_id,
            username=user.username,
            roles=user.roles,
            permissions=user.permissions,
            resource=resource,
            action=action,
            resource_id=resource_id,
            metadata=context or {},
        )

        # Check direct permissions first
        result = await self._check_direct_permissions(user, resource, action)
        if result.allowed:
            result.context = auth_context
            return result

        # Check role-based permissions
        result = await self._check_role_permissions(user, resource, action)
        if result.allowed:
            result.context = auth_context
            return result

        # Check policies
        result = await self._evaluate_policies(user, resource, action, resource_id, context)
        result.context = auth_context

        return result

    async def _check_direct_permissions(
        self,
        user: User,
        resource: str,
        action: str,
    ) -> AuthorizationResult:
        """Check user's direct permissions."""
        required_perm = f"{resource}:{action}"

        for perm in user.permissions:
            if self._permission_matches(perm, required_perm):
                return AuthorizationResult(
                    allowed=True,
                    reason="Direct permission granted",
                    matched_permission=perm,
                )

        return AuthorizationResult(
            allowed=False,
            reason="No matching direct permission",
        )

    async def _check_role_permissions(
        self,
        user: User,
        resource: str,
        action: str,
    ) -> AuthorizationResult:
        """Check permissions from user's roles."""
        required_perm = f"{resource}:{action}"

        for role_name in user.roles:
            role = await self.get_role_by_name(role_name)
            if not role:
                continue

            for perm in role.permissions:
                if self._permission_matches(perm, required_perm):
                    return AuthorizationResult(
                        allowed=True,
                        reason=f"Permission granted via role: {role_name}",
                        matched_permission=perm,
                    )

        return AuthorizationResult(
            allowed=False,
            reason="No matching role permission",
        )

    async def _evaluate_policies(
        self,
        user: User,
        resource: str,
        action: str,
        resource_id: str,
        context: dict[str, Any] | None,
    ) -> AuthorizationResult:
        """Evaluate policies for authorization."""
        # Get applicable policies sorted by priority
        applicable_policies = []

        for policy in self._policies.values():
            if not policy.enabled:
                continue

            # Check if policy applies to this user
            if not self._policy_applies_to_principal(policy, user):
                continue

            # Check if policy applies to this resource
            if not self._policy_applies_to_resource(policy, resource, resource_id):
                continue

            # Check if policy applies to this action
            if not self._policy_applies_to_action(policy, action):
                continue

            applicable_policies.append(policy)

        # Sort by priority (higher first)
        applicable_policies.sort(key=lambda p: p.priority, reverse=True)

        # Evaluate policies - explicit deny takes precedence
        for policy in applicable_policies:
            # Check conditions
            if policy.conditions and not self._evaluate_conditions(policy.conditions, context):
                continue

            if policy.effect == "deny":
                return AuthorizationResult(
                    allowed=False,
                    reason=f"Denied by policy: {policy.name}",
                    matched_policy=policy.policy_id,
                )
            elif policy.effect == "allow":
                return AuthorizationResult(
                    allowed=True,
                    reason=f"Allowed by policy: {policy.name}",
                    matched_policy=policy.policy_id,
                )

        return AuthorizationResult(
            allowed=False,
            reason="No matching policy found",
        )

    def _permission_matches(self, granted: str, required: str) -> bool:
        """Check if a granted permission matches a required permission."""
        # Wildcard permission
        if granted == "*":
            return True

        # Exact match
        if granted == required:
            return True

        # Resource wildcard (e.g., "experiments:*" matches "experiments:read")
        granted_parts = granted.split(":")
        required_parts = required.split(":")

        if len(granted_parts) == 2 and len(required_parts) == 2:
            if granted_parts[0] == required_parts[0] and granted_parts[1] == "*":
                return True

        return False

    def _policy_applies_to_principal(self, policy: Policy, user: User) -> bool:
        """Check if policy applies to user."""
        for principal in policy.principals:
            # Wildcard
            if principal == "*":
                return True

            # Direct user match
            if principal == user.user_id or principal == user.username:
                return True

            # Role match (prefixed with "role:")
            if principal.startswith("role:"):
                role_name = principal[5:]
                if role_name in user.roles:
                    return True

        return False

    def _policy_applies_to_resource(
        self,
        policy: Policy,
        resource: str,
        resource_id: str,
    ) -> bool:
        """Check if policy applies to resource."""
        for res_pattern in policy.resources:
            # Wildcard
            if res_pattern == "*":
                return True

            # Full resource path (resource:id)
            full_resource = f"{resource}:{resource_id}" if resource_id else resource

            # Pattern matching
            if fnmatch.fnmatch(full_resource, res_pattern):
                return True

            if fnmatch.fnmatch(resource, res_pattern):
                return True

        return False

    def _policy_applies_to_action(self, policy: Policy, action: str) -> bool:
        """Check if policy applies to action."""
        for act_pattern in policy.actions:
            if act_pattern == "*":
                return True
            if fnmatch.fnmatch(action, act_pattern):
                return True
        return False

    def _evaluate_conditions(
        self,
        conditions: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> bool:
        """Evaluate policy conditions."""
        if not context:
            return True

        for key, expected in conditions.items():
            actual = context.get(key)

            # Handle different condition types
            if isinstance(expected, dict):
                # Complex condition
                if "eq" in expected and actual != expected["eq"]:
                    return False
                if "ne" in expected and actual == expected["ne"]:
                    return False
                if "gt" in expected and (actual is None or actual <= expected["gt"]):
                    return False
                if "lt" in expected and (actual is None or actual >= expected["lt"]):
                    return False
                if "in" in expected and actual not in expected["in"]:
                    return False
            else:
                # Simple equality
                if actual != expected:
                    return False

        return True

    # ===========================================
    # PERMISSION QUERIES
    # ===========================================

    async def get_user_permissions(self, user: User) -> list[str]:
        """Get all effective permissions for a user."""
        permissions = set(user.permissions)

        for role_name in user.roles:
            role = await self.get_role_by_name(role_name)
            if role:
                permissions.update(role.permissions)

        return sorted(list(permissions))

    async def check_permission(
        self,
        user: User,
        permission: str,
    ) -> bool:
        """Quick check if user has a specific permission."""
        # Check direct permissions
        for perm in user.permissions:
            if self._permission_matches(perm, permission):
                return True

        # Check role permissions
        for role_name in user.roles:
            role = await self.get_role_by_name(role_name)
            if role:
                for perm in role.permissions:
                    if self._permission_matches(perm, permission):
                        return True

        return False

    async def get_all_permissions(self) -> list[Permission]:
        """Get all defined permissions."""
        return list(self._permissions.values())


# Singleton instance
_authz_service: AuthorizationService | None = None


def get_authorization_service() -> AuthorizationService:
    """Get or create authorization service singleton."""
    global _authz_service
    if _authz_service is None:
        _authz_service = AuthorizationService()
    return _authz_service


__all__ = [
    "AuthorizationService",
    "get_authorization_service",
]
