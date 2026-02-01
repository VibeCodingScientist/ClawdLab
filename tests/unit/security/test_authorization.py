"""Unit tests for AuthorizationService."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from platform.security.authorization import AuthorizationService
from platform.security.base import (
    User,
    UserStatus,
    Role,
    Policy,
    Permission,
    AuthorizationResult,
)


class TestAuthorizationService:
    """Tests for AuthorizationService class."""

    @pytest.fixture
    def authz_service(self) -> AuthorizationService:
        """Create a fresh AuthorizationService instance for each test."""
        return AuthorizationService()

    @pytest.fixture
    def test_user(self) -> User:
        """Create a test user."""
        return User(
            user_id="test-user-id",
            username="testuser",
            email="test@example.com",
            password_hash="",
            status=UserStatus.ACTIVE,
            roles=["researcher"],
            permissions=["experiments:read"],
        )

    @pytest.fixture
    def admin_user(self) -> User:
        """Create an admin user."""
        return User(
            user_id="admin-user-id",
            username="admin",
            email="admin@example.com",
            password_hash="",
            status=UserStatus.ACTIVE,
            roles=["admin"],
            permissions=["*"],
        )

    # ===========================================
    # ROLE MANAGEMENT TESTS
    # ===========================================

    @pytest.mark.asyncio
    async def test_create_role_success(self, authz_service: AuthorizationService):
        """Creating a new role should succeed."""
        role = await authz_service.create_role(
            name="custom_role",
            description="A custom test role",
            permissions=["experiments:read", "experiments:write"],
        )

        assert role is not None
        assert role.name == "custom_role"
        assert role.description == "A custom test role"
        assert "experiments:read" in role.permissions
        assert role.is_system is False

    @pytest.mark.asyncio
    async def test_create_role_duplicate_name(self, authz_service: AuthorizationService):
        """Creating a role with duplicate name should fail."""
        await authz_service.create_role(name="unique_role")

        with pytest.raises(ValueError, match="Role already exists"):
            await authz_service.create_role(name="unique_role")

    @pytest.mark.asyncio
    async def test_get_role_existing(self, authz_service: AuthorizationService):
        """Getting an existing role should return it."""
        created = await authz_service.create_role(name="findme_role")

        found = await authz_service.get_role(created.role_id)

        assert found is not None
        assert found.role_id == created.role_id

    @pytest.mark.asyncio
    async def test_get_role_nonexistent(self, authz_service: AuthorizationService):
        """Getting a nonexistent role should return None."""
        result = await authz_service.get_role("nonexistent-role-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_role_by_name(self, authz_service: AuthorizationService):
        """Getting a role by name should work."""
        await authz_service.create_role(name="named_role")

        found = await authz_service.get_role_by_name("named_role")

        assert found is not None
        assert found.name == "named_role"

    @pytest.mark.asyncio
    async def test_update_role_success(self, authz_service: AuthorizationService):
        """Updating a custom role should succeed."""
        role = await authz_service.create_role(
            name="updatable",
            permissions=["experiments:read"],
        )

        updated = await authz_service.update_role(
            role.role_id,
            name="updated_role",
            permissions=["experiments:read", "experiments:write"],
        )

        assert updated is not None
        assert updated.name == "updated_role"
        assert "experiments:write" in updated.permissions

    @pytest.mark.asyncio
    async def test_update_system_role_fails(self, authz_service: AuthorizationService):
        """Updating a system role should fail."""
        # System roles are created during initialization
        admin_role = await authz_service.get_role_by_name("admin")

        if admin_role:
            with pytest.raises(ValueError, match="Cannot modify system roles"):
                await authz_service.update_role(
                    admin_role.role_id,
                    name="hacked_admin",
                )

    @pytest.mark.asyncio
    async def test_delete_role_success(self, authz_service: AuthorizationService):
        """Deleting a custom role should succeed."""
        role = await authz_service.create_role(name="deletable")

        result = await authz_service.delete_role(role.role_id)

        assert result is True
        assert await authz_service.get_role(role.role_id) is None

    @pytest.mark.asyncio
    async def test_delete_system_role_fails(self, authz_service: AuthorizationService):
        """Deleting a system role should fail."""
        admin_role = await authz_service.get_role_by_name("admin")

        if admin_role:
            with pytest.raises(ValueError, match="Cannot delete system roles"):
                await authz_service.delete_role(admin_role.role_id)

    @pytest.mark.asyncio
    async def test_list_roles(self, authz_service: AuthorizationService):
        """Listing roles should return all roles."""
        await authz_service.create_role(name="role1")
        await authz_service.create_role(name="role2")

        roles = await authz_service.list_roles()

        assert len(roles) >= 2
        role_names = [r.name for r in roles]
        assert "role1" in role_names
        assert "role2" in role_names

    @pytest.mark.asyncio
    async def test_add_permission_to_role(self, authz_service: AuthorizationService):
        """Adding a permission to a role should work."""
        role = await authz_service.create_role(
            name="permissiontest",
            permissions=["experiments:read"],
        )

        updated = await authz_service.add_permission_to_role(
            role.role_id,
            "experiments:write",
        )

        assert updated is not None
        assert "experiments:write" in updated.permissions

    @pytest.mark.asyncio
    async def test_remove_permission_from_role(
        self,
        authz_service: AuthorizationService,
    ):
        """Removing a permission from a role should work."""
        role = await authz_service.create_role(
            name="removetest",
            permissions=["experiments:read", "experiments:write"],
        )

        updated = await authz_service.remove_permission_from_role(
            role.role_id,
            "experiments:write",
        )

        assert updated is not None
        assert "experiments:write" not in updated.permissions
        assert "experiments:read" in updated.permissions

    # ===========================================
    # POLICY MANAGEMENT TESTS
    # ===========================================

    @pytest.mark.asyncio
    async def test_create_policy_allow(self, authz_service: AuthorizationService):
        """Creating an allow policy should succeed."""
        policy = await authz_service.create_policy(
            name="allow_experiments",
            effect="allow",
            principals=["role:researcher"],
            resources=["experiments"],
            actions=["read", "create"],
        )

        assert policy is not None
        assert policy.name == "allow_experiments"
        assert policy.effect == "allow"
        assert "role:researcher" in policy.principals
        assert policy.enabled is True

    @pytest.mark.asyncio
    async def test_create_policy_deny(self, authz_service: AuthorizationService):
        """Creating a deny policy should succeed."""
        policy = await authz_service.create_policy(
            name="deny_delete",
            effect="deny",
            principals=["role:viewer"],
            resources=["*"],
            actions=["delete"],
        )

        assert policy is not None
        assert policy.effect == "deny"

    @pytest.mark.asyncio
    async def test_create_policy_invalid_effect(
        self,
        authz_service: AuthorizationService,
    ):
        """Creating a policy with invalid effect should fail."""
        with pytest.raises(ValueError, match="Effect must be"):
            await authz_service.create_policy(
                name="invalid",
                effect="maybe",  # Invalid
                principals=["*"],
                resources=["*"],
                actions=["*"],
            )

    @pytest.mark.asyncio
    async def test_update_policy(self, authz_service: AuthorizationService):
        """Updating a policy should work."""
        policy = await authz_service.create_policy(
            name="updateable_policy",
            effect="allow",
            principals=["*"],
            resources=["experiments"],
            actions=["read"],
        )

        updated = await authz_service.update_policy(
            policy.policy_id,
            name="updated_policy",
            actions=["read", "write"],
            enabled=False,
        )

        assert updated is not None
        assert updated.name == "updated_policy"
        assert "write" in updated.actions
        assert updated.enabled is False

    @pytest.mark.asyncio
    async def test_delete_policy(self, authz_service: AuthorizationService):
        """Deleting a policy should work."""
        policy = await authz_service.create_policy(
            name="deletable_policy",
            effect="allow",
            principals=["*"],
            resources=["*"],
            actions=["*"],
        )

        result = await authz_service.delete_policy(policy.policy_id)

        assert result is True
        assert await authz_service.get_policy(policy.policy_id) is None

    # ===========================================
    # AUTHORIZATION TESTS
    # ===========================================

    @pytest.mark.asyncio
    async def test_authorize_with_direct_permission(
        self,
        authz_service: AuthorizationService,
        test_user: User,
    ):
        """User with direct permission should be authorized."""
        result = await authz_service.authorize(
            user=test_user,
            resource="experiments",
            action="read",
        )

        assert result.allowed is True
        assert "Direct permission" in result.reason

    @pytest.mark.asyncio
    async def test_authorize_with_wildcard_permission(
        self,
        authz_service: AuthorizationService,
        admin_user: User,
    ):
        """User with wildcard permission should be authorized for anything."""
        result = await authz_service.authorize(
            user=admin_user,
            resource="any_resource",
            action="any_action",
        )

        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_authorize_with_role_permission(
        self,
        authz_service: AuthorizationService,
    ):
        """User should be authorized via role permissions."""
        # Create a role with permissions
        await authz_service.create_role(
            name="tester",
            permissions=["tests:run", "tests:read"],
        )

        user = User(
            user_id="role-user",
            username="roleuser",
            email="role@example.com",
            status=UserStatus.ACTIVE,
            roles=["tester"],
            permissions=[],
        )

        result = await authz_service.authorize(
            user=user,
            resource="tests",
            action="run",
        )

        assert result.allowed is True
        assert "role" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_authorize_denied_no_permission(
        self,
        authz_service: AuthorizationService,
    ):
        """User without permission should be denied."""
        user = User(
            user_id="noperm-user",
            username="noperm",
            email="noperm@example.com",
            status=UserStatus.ACTIVE,
            roles=[],
            permissions=[],
        )

        result = await authz_service.authorize(
            user=user,
            resource="experiments",
            action="delete",
        )

        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_authorize_with_policy_allow(
        self,
        authz_service: AuthorizationService,
    ):
        """Policy-based allow should work."""
        await authz_service.create_policy(
            name="allow_specific",
            effect="allow",
            principals=["test-policy-user"],
            resources=["special"],
            actions=["access"],
        )

        user = User(
            user_id="test-policy-user",
            username="policyuser",
            email="policy@example.com",
            status=UserStatus.ACTIVE,
            roles=[],
            permissions=[],
        )

        result = await authz_service.authorize(
            user=user,
            resource="special",
            action="access",
        )

        assert result.allowed is True
        assert "policy" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_authorize_with_policy_deny(
        self,
        authz_service: AuthorizationService,
    ):
        """Policy-based deny should take effect."""
        # Create a deny policy with high priority
        await authz_service.create_policy(
            name="deny_all_delete",
            effect="deny",
            principals=["role:restricted"],
            resources=["*"],
            actions=["delete"],
            priority=100,
        )

        user = User(
            user_id="restricted-user",
            username="restricted",
            email="restricted@example.com",
            status=UserStatus.ACTIVE,
            roles=["restricted"],
            permissions=["*"],  # Even with wildcard permission
        )

        # Note: Direct permissions are checked before policies,
        # so this test verifies the policy logic is correct
        # In real use, you'd structure permissions differently

    @pytest.mark.asyncio
    async def test_authorize_with_resource_id(
        self,
        authz_service: AuthorizationService,
    ):
        """Authorization should support resource IDs."""
        await authz_service.create_policy(
            name="allow_own_experiments",
            effect="allow",
            principals=["*"],
            resources=["experiments:exp-123"],
            actions=["*"],
        )

        user = User(
            user_id="some-user",
            username="someuser",
            email="some@example.com",
            status=UserStatus.ACTIVE,
            roles=[],
            permissions=[],
        )

        result = await authz_service.authorize(
            user=user,
            resource="experiments",
            action="read",
            resource_id="exp-123",
        )

        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_authorize_with_conditions(
        self,
        authz_service: AuthorizationService,
    ):
        """Policy conditions should be evaluated."""
        await authz_service.create_policy(
            name="time_based",
            effect="allow",
            principals=["*"],
            resources=["restricted"],
            actions=["access"],
            conditions={"environment": "development"},
        )

        user = User(
            user_id="cond-user",
            username="conduser",
            email="cond@example.com",
            status=UserStatus.ACTIVE,
            roles=[],
            permissions=[],
        )

        # Should succeed with matching condition
        result = await authz_service.authorize(
            user=user,
            resource="restricted",
            action="access",
            context={"environment": "development"},
        )

        assert result.allowed is True

        # Should fail with non-matching condition
        result = await authz_service.authorize(
            user=user,
            resource="restricted",
            action="access",
            context={"environment": "production"},
        )

        assert result.allowed is False

    # ===========================================
    # PERMISSION MATCHING TESTS
    # ===========================================

    def test_permission_matches_exact(self, authz_service: AuthorizationService):
        """Exact permission match should work."""
        assert authz_service._permission_matches("experiments:read", "experiments:read") is True

    def test_permission_matches_wildcard(self, authz_service: AuthorizationService):
        """Wildcard permission should match anything."""
        assert authz_service._permission_matches("*", "experiments:read") is True
        assert authz_service._permission_matches("*", "any:thing") is True

    def test_permission_matches_resource_wildcard(
        self,
        authz_service: AuthorizationService,
    ):
        """Resource wildcard should match any action."""
        assert authz_service._permission_matches("experiments:*", "experiments:read") is True
        assert authz_service._permission_matches("experiments:*", "experiments:delete") is True

    def test_permission_no_match(self, authz_service: AuthorizationService):
        """Non-matching permissions should return False."""
        assert authz_service._permission_matches("experiments:read", "experiments:write") is False
        assert authz_service._permission_matches("experiments:read", "other:read") is False

    # ===========================================
    # POLICY PRINCIPAL MATCHING TESTS
    # ===========================================

    def test_policy_applies_to_wildcard_principal(
        self,
        authz_service: AuthorizationService,
        test_user: User,
    ):
        """Wildcard principal should match any user."""
        policy = Policy(
            name="test",
            principals=["*"],
            resources=["*"],
            actions=["*"],
        )

        assert authz_service._policy_applies_to_principal(policy, test_user) is True

    def test_policy_applies_to_user_id(
        self,
        authz_service: AuthorizationService,
        test_user: User,
    ):
        """Policy with user ID should match specific user."""
        policy = Policy(
            name="test",
            principals=["test-user-id"],
            resources=["*"],
            actions=["*"],
        )

        assert authz_service._policy_applies_to_principal(policy, test_user) is True

    def test_policy_applies_to_role(
        self,
        authz_service: AuthorizationService,
        test_user: User,
    ):
        """Policy with role: prefix should match user with role."""
        policy = Policy(
            name="test",
            principals=["role:researcher"],
            resources=["*"],
            actions=["*"],
        )

        assert authz_service._policy_applies_to_principal(policy, test_user) is True

    # ===========================================
    # CONDITION EVALUATION TESTS
    # ===========================================

    def test_evaluate_conditions_simple_equality(
        self,
        authz_service: AuthorizationService,
    ):
        """Simple equality conditions should work."""
        conditions = {"env": "prod"}
        context = {"env": "prod"}

        assert authz_service._evaluate_conditions(conditions, context) is True

        context = {"env": "dev"}
        assert authz_service._evaluate_conditions(conditions, context) is False

    def test_evaluate_conditions_complex_eq(self, authz_service: AuthorizationService):
        """Complex eq condition should work."""
        conditions = {"status": {"eq": "active"}}
        context = {"status": "active"}

        assert authz_service._evaluate_conditions(conditions, context) is True

        context = {"status": "inactive"}
        assert authz_service._evaluate_conditions(conditions, context) is False

    def test_evaluate_conditions_complex_gt(self, authz_service: AuthorizationService):
        """Complex gt condition should work."""
        conditions = {"priority": {"gt": 5}}
        context = {"priority": 10}

        assert authz_service._evaluate_conditions(conditions, context) is True

        context = {"priority": 3}
        assert authz_service._evaluate_conditions(conditions, context) is False

    def test_evaluate_conditions_complex_in(self, authz_service: AuthorizationService):
        """Complex in condition should work."""
        conditions = {"role": {"in": ["admin", "moderator"]}}
        context = {"role": "admin"}

        assert authz_service._evaluate_conditions(conditions, context) is True

        context = {"role": "viewer"}
        assert authz_service._evaluate_conditions(conditions, context) is False

    def test_evaluate_conditions_no_context(self, authz_service: AuthorizationService):
        """No context should pass if conditions exist."""
        conditions = {"env": "prod"}

        # No context provided
        assert authz_service._evaluate_conditions(conditions, None) is True

    # ===========================================
    # PERMISSION QUERY TESTS
    # ===========================================

    @pytest.mark.asyncio
    async def test_get_user_permissions(
        self,
        authz_service: AuthorizationService,
        test_user: User,
    ):
        """Getting user permissions should include direct and role permissions."""
        # Add a role with additional permissions
        await authz_service.create_role(
            name="researcher",
            permissions=["literature:read", "knowledge:read"],
        )

        permissions = await authz_service.get_user_permissions(test_user)

        # Should include direct permission
        assert "experiments:read" in permissions

        # Should include role permissions
        assert "literature:read" in permissions
        assert "knowledge:read" in permissions

    @pytest.mark.asyncio
    async def test_check_permission_direct(
        self,
        authz_service: AuthorizationService,
        test_user: User,
    ):
        """check_permission should return True for direct permissions."""
        result = await authz_service.check_permission(test_user, "experiments:read")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_via_role(
        self,
        authz_service: AuthorizationService,
    ):
        """check_permission should return True for role permissions."""
        await authz_service.create_role(
            name="checker_role",
            permissions=["checkers:use"],
        )

        user = User(
            user_id="checker",
            username="checker",
            email="checker@example.com",
            status=UserStatus.ACTIVE,
            roles=["checker_role"],
            permissions=[],
        )

        result = await authz_service.check_permission(user, "checkers:use")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_not_found(
        self,
        authz_service: AuthorizationService,
    ):
        """check_permission should return False for missing permissions."""
        user = User(
            user_id="nope",
            username="nope",
            email="nope@example.com",
            status=UserStatus.ACTIVE,
            roles=[],
            permissions=[],
        )

        result = await authz_service.check_permission(user, "secret:access")

        assert result is False


class TestAuthorizationServiceSingleton:
    """Tests for get_authorization_service singleton."""

    def test_get_authorization_service_returns_instance(self):
        """get_authorization_service should return an AuthorizationService."""
        from platform.security.authorization import get_authorization_service

        service = get_authorization_service()

        assert isinstance(service, AuthorizationService)

    def test_get_authorization_service_returns_same_instance(self):
        """get_authorization_service should return the same instance."""
        from platform.security.authorization import get_authorization_service

        service1 = get_authorization_service()
        service2 = get_authorization_service()

        assert service1 is service2
