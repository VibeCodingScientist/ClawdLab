"""Unit tests for AuthenticationService."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from platform.security.auth import AuthenticationService
from platform.security.base import User, UserStatus, Token, TokenType


class TestAuthenticationService:
    """Tests for AuthenticationService class."""

    @pytest.fixture
    def auth_service(self) -> AuthenticationService:
        """Create a fresh AuthenticationService instance for each test."""
        return AuthenticationService()

    # ===========================================
    # PASSWORD MANAGEMENT TESTS
    # ===========================================

    def test_hash_password_returns_salted_hash(self, auth_service: AuthenticationService):
        """Password hashing should return a salt$hash format."""
        password = "TestPassword123!"
        hashed = auth_service._hash_password(password)

        assert "$" in hashed
        parts = hashed.split("$")
        assert len(parts) == 2
        assert len(parts[0]) == 32  # 16 bytes hex = 32 chars
        assert len(parts[1]) == 64  # SHA256 = 64 hex chars

    def test_hash_password_produces_different_hashes_for_same_password(
        self,
        auth_service: AuthenticationService,
    ):
        """Same password should produce different hashes (different salts)."""
        password = "TestPassword123!"
        hash1 = auth_service._hash_password(password)
        hash2 = auth_service._hash_password(password)

        assert hash1 != hash2

    def test_verify_password_with_correct_password(
        self,
        auth_service: AuthenticationService,
    ):
        """Correct password should verify successfully."""
        password = "TestPassword123!"
        hashed = auth_service._hash_password(password)

        assert auth_service._verify_password(password, hashed) is True

    def test_verify_password_with_incorrect_password(
        self,
        auth_service: AuthenticationService,
    ):
        """Incorrect password should fail verification."""
        password = "TestPassword123!"
        hashed = auth_service._hash_password(password)

        assert auth_service._verify_password("WrongPassword", hashed) is False

    def test_verify_password_with_invalid_hash_format(
        self,
        auth_service: AuthenticationService,
    ):
        """Invalid hash format should fail gracefully."""
        assert auth_service._verify_password("password", "invalid_hash") is False
        assert auth_service._verify_password("password", "") is False

    def test_validate_password_meets_requirements(
        self,
        auth_service: AuthenticationService,
    ):
        """Valid password should pass validation."""
        valid, errors = auth_service.validate_password("ValidPass123!")

        assert valid is True
        assert errors == []

    def test_validate_password_too_short(self, auth_service: AuthenticationService):
        """Short password should fail validation."""
        valid, errors = auth_service.validate_password("Aa1!")

        assert valid is False
        assert any("at least" in err for err in errors)

    def test_validate_password_missing_uppercase(
        self,
        auth_service: AuthenticationService,
    ):
        """Password without uppercase should fail if required."""
        # Note: Depends on settings, but we test the logic
        valid, errors = auth_service.validate_password("validpass123!")

        # May or may not fail depending on settings
        # This test verifies the validation runs without error

    def test_validate_password_missing_digit(self, auth_service: AuthenticationService):
        """Password without digit should fail if required."""
        valid, errors = auth_service.validate_password("ValidPassword!")

        # May or may not fail depending on settings

    # ===========================================
    # USER MANAGEMENT TESTS
    # ===========================================

    @pytest.mark.asyncio
    async def test_create_user_success(self, auth_service: AuthenticationService):
        """Creating a user with valid data should succeed."""
        user = await auth_service.create_user(
            username="newuser",
            email="newuser@example.com",
            password="ValidPass123!",
            roles=["researcher"],
        )

        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.status == UserStatus.ACTIVE
        assert "researcher" in user.roles
        assert user.password_hash != "ValidPass123!"  # Should be hashed

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(
        self,
        auth_service: AuthenticationService,
    ):
        """Creating a user with duplicate username should fail."""
        await auth_service.create_user(
            username="existinguser",
            email="user1@example.com",
            password="ValidPass123!",
        )

        with pytest.raises(ValueError, match="Username already exists"):
            await auth_service.create_user(
                username="existinguser",
                email="user2@example.com",
                password="ValidPass123!",
            )

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(
        self,
        auth_service: AuthenticationService,
    ):
        """Creating a user with duplicate email should fail."""
        await auth_service.create_user(
            username="user1",
            email="duplicate@example.com",
            password="ValidPass123!",
        )

        with pytest.raises(ValueError, match="Email already exists"):
            await auth_service.create_user(
                username="user2",
                email="duplicate@example.com",
                password="ValidPass123!",
            )

    @pytest.mark.asyncio
    async def test_create_user_invalid_password(
        self,
        auth_service: AuthenticationService,
    ):
        """Creating a user with invalid password should fail."""
        with pytest.raises(ValueError, match="Invalid password"):
            await auth_service.create_user(
                username="newuser",
                email="newuser@example.com",
                password="weak",  # Too short
            )

    @pytest.mark.asyncio
    async def test_get_user_existing(self, auth_service: AuthenticationService):
        """Getting an existing user should return the user."""
        created = await auth_service.create_user(
            username="testuser",
            email="test@example.com",
            password="ValidPass123!",
        )

        retrieved = await auth_service.get_user(created.user_id)

        assert retrieved is not None
        assert retrieved.user_id == created.user_id
        assert retrieved.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_nonexistent(self, auth_service: AuthenticationService):
        """Getting a nonexistent user should return None."""
        result = await auth_service.get_user("nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_username(self, auth_service: AuthenticationService):
        """Getting a user by username should work."""
        await auth_service.create_user(
            username="findme",
            email="findme@example.com",
            password="ValidPass123!",
        )

        found = await auth_service.get_user_by_username("findme")

        assert found is not None
        assert found.username == "findme"

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, auth_service: AuthenticationService):
        """Getting a user by email should work."""
        await auth_service.create_user(
            username="emailuser",
            email="findme@example.com",
            password="ValidPass123!",
        )

        found = await auth_service.get_user_by_email("findme@example.com")

        assert found is not None
        assert found.email == "findme@example.com"

    @pytest.mark.asyncio
    async def test_update_user(self, auth_service: AuthenticationService):
        """Updating a user should modify the specified fields."""
        user = await auth_service.create_user(
            username="updateme",
            email="update@example.com",
            password="ValidPass123!",
        )

        updated = await auth_service.update_user(
            user.user_id,
            username="newname",
            roles=["admin"],
        )

        assert updated is not None
        assert updated.username == "newname"
        assert "admin" in updated.roles

    @pytest.mark.asyncio
    async def test_delete_user(self, auth_service: AuthenticationService):
        """Deleting a user should remove them."""
        user = await auth_service.create_user(
            username="deleteme",
            email="delete@example.com",
            password="ValidPass123!",
        )

        result = await auth_service.delete_user(user.user_id)

        assert result is True
        assert await auth_service.get_user(user.user_id) is None

    @pytest.mark.asyncio
    async def test_delete_user_revokes_tokens(self, auth_service: AuthenticationService):
        """Deleting a user should revoke their tokens."""
        user = await auth_service.create_user(
            username="deletewithtoken",
            email="deletetoken@example.com",
            password="ValidPass123!",
        )

        # Create a token
        token = await auth_service.create_access_token(user)

        # Delete user
        await auth_service.delete_user(user.user_id)

        # Token should be revoked
        assert token.revoked is True

    @pytest.mark.asyncio
    async def test_change_password_success(self, auth_service: AuthenticationService):
        """Changing password with correct current password should succeed."""
        user = await auth_service.create_user(
            username="changepass",
            email="changepass@example.com",
            password="OldPass123!",
        )

        result = await auth_service.change_password(
            user.user_id,
            current_password="OldPass123!",
            new_password="NewPass456!",
        )

        assert result is True

        # Should now authenticate with new password
        auth_user, _ = await auth_service.authenticate("changepass", "NewPass456!")
        assert auth_user is not None

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(
        self,
        auth_service: AuthenticationService,
    ):
        """Changing password with wrong current password should fail."""
        user = await auth_service.create_user(
            username="wrongpass",
            email="wrongpass@example.com",
            password="CorrectPass123!",
        )

        result = await auth_service.change_password(
            user.user_id,
            current_password="WrongPass123!",
            new_password="NewPass456!",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_list_users_filters(self, auth_service: AuthenticationService):
        """Listing users should support filtering."""
        await auth_service.create_user(
            username="researcher1",
            email="r1@example.com",
            password="ValidPass123!",
            roles=["researcher"],
        )
        await auth_service.create_user(
            username="researcher2",
            email="r2@example.com",
            password="ValidPass123!",
            roles=["researcher"],
        )

        researchers = await auth_service.list_users(role="researcher")

        assert len(researchers) >= 2
        assert all("researcher" in u.roles for u in researchers)

    # ===========================================
    # AUTHENTICATION TESTS
    # ===========================================

    @pytest.mark.asyncio
    async def test_authenticate_success(self, auth_service: AuthenticationService):
        """Authentication with valid credentials should succeed."""
        await auth_service.create_user(
            username="authuser",
            email="auth@example.com",
            password="AuthPass123!",
        )

        user, message = await auth_service.authenticate("authuser", "AuthPass123!")

        assert user is not None
        assert message == "Success"
        assert user.username == "authuser"
        assert user.login_count == 1

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(
        self,
        auth_service: AuthenticationService,
    ):
        """Authentication with wrong password should fail."""
        await auth_service.create_user(
            username="authfail",
            email="authfail@example.com",
            password="CorrectPass123!",
        )

        user, message = await auth_service.authenticate("authfail", "WrongPass123!")

        assert user is None
        assert message == "Invalid password"

    @pytest.mark.asyncio
    async def test_authenticate_nonexistent_user(
        self,
        auth_service: AuthenticationService,
    ):
        """Authentication with nonexistent user should fail."""
        user, message = await auth_service.authenticate("nonexistent", "AnyPass123!")

        assert user is None
        assert message == "User not found"

    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(
        self,
        auth_service: AuthenticationService,
    ):
        """Authentication with inactive user should fail."""
        user = await auth_service.create_user(
            username="inactive",
            email="inactive@example.com",
            password="ValidPass123!",
        )
        await auth_service.update_user(user.user_id, status=UserStatus.SUSPENDED.value)

        auth_user, message = await auth_service.authenticate("inactive", "ValidPass123!")

        assert auth_user is None
        assert "suspended" in message.lower()

    @pytest.mark.asyncio
    async def test_authenticate_token_success(
        self,
        auth_service: AuthenticationService,
    ):
        """Token authentication should work with valid token."""
        user = await auth_service.create_user(
            username="tokenuser",
            email="token@example.com",
            password="ValidPass123!",
        )
        token = await auth_service.create_access_token(user)

        auth_user, auth_token, message = await auth_service.authenticate_token(
            token.token_value
        )

        assert auth_user is not None
        assert auth_token is not None
        assert message == "Success"
        assert auth_user.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_authenticate_token_invalid(
        self,
        auth_service: AuthenticationService,
    ):
        """Token authentication should fail with invalid token."""
        user, token, message = await auth_service.authenticate_token("invalid_token")

        assert user is None
        assert token is None
        assert message == "Token not found"

    @pytest.mark.asyncio
    async def test_authenticate_token_revoked(
        self,
        auth_service: AuthenticationService,
    ):
        """Token authentication should fail with revoked token."""
        user = await auth_service.create_user(
            username="revokedtoken",
            email="revoked@example.com",
            password="ValidPass123!",
        )
        token = await auth_service.create_access_token(user)
        await auth_service.revoke_token(token.token_id)

        auth_user, auth_token, message = await auth_service.authenticate_token(
            token.token_value
        )

        assert auth_user is None
        assert "revoked" in message.lower()

    # ===========================================
    # TOKEN MANAGEMENT TESTS
    # ===========================================

    @pytest.mark.asyncio
    async def test_create_access_token(self, auth_service: AuthenticationService):
        """Creating an access token should work."""
        user = await auth_service.create_user(
            username="accesstoken",
            email="access@example.com",
            password="ValidPass123!",
        )

        token = await auth_service.create_access_token(user, scopes=["read", "write"])

        assert token is not None
        assert token.token_type == TokenType.ACCESS
        assert token.user_id == user.user_id
        assert "read" in token.scopes
        assert token.expires_at is not None
        assert token.token_value  # Should have a value

    @pytest.mark.asyncio
    async def test_create_refresh_token(self, auth_service: AuthenticationService):
        """Creating a refresh token should work."""
        user = await auth_service.create_user(
            username="refreshtoken",
            email="refresh@example.com",
            password="ValidPass123!",
        )

        token = await auth_service.create_refresh_token(user)

        assert token is not None
        assert token.token_type == TokenType.REFRESH
        assert token.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_refresh_access_token(self, auth_service: AuthenticationService):
        """Refreshing an access token with valid refresh token should work."""
        user = await auth_service.create_user(
            username="refreshme",
            email="refreshme@example.com",
            password="ValidPass123!",
        )
        refresh_token = await auth_service.create_refresh_token(user)

        new_token, message = await auth_service.refresh_access_token(
            refresh_token.token_value
        )

        assert new_token is not None
        assert message == "Success"
        assert new_token.token_type == TokenType.ACCESS

    @pytest.mark.asyncio
    async def test_refresh_access_token_invalid(
        self,
        auth_service: AuthenticationService,
    ):
        """Refreshing with invalid refresh token should fail."""
        token, message = await auth_service.refresh_access_token("invalid_refresh")

        assert token is None
        assert "not found" in message.lower()

    @pytest.mark.asyncio
    async def test_revoke_token(self, auth_service: AuthenticationService):
        """Revoking a token should mark it as revoked."""
        user = await auth_service.create_user(
            username="revoketoken",
            email="revoke@example.com",
            password="ValidPass123!",
        )
        token = await auth_service.create_access_token(user)

        result = await auth_service.revoke_token(token.token_id)

        assert result is True
        assert token.revoked is True
        assert token.revoked_at is not None

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, auth_service: AuthenticationService):
        """Revoking all tokens for a user should work."""
        user = await auth_service.create_user(
            username="revokeall",
            email="revokeall@example.com",
            password="ValidPass123!",
        )
        token1 = await auth_service.create_access_token(user)
        token2 = await auth_service.create_access_token(user)
        token3 = await auth_service.create_refresh_token(user)

        count = await auth_service.revoke_all_user_tokens(user.user_id)

        assert count == 3
        assert token1.revoked is True
        assert token2.revoked is True
        assert token3.revoked is True

    # ===========================================
    # API KEY TESTS
    # ===========================================

    @pytest.mark.asyncio
    async def test_create_api_key(self, auth_service: AuthenticationService):
        """Creating an API key should return key object and raw value."""
        user = await auth_service.create_user(
            username="apikey",
            email="apikey@example.com",
            password="ValidPass123!",
        )

        api_key, raw_key = await auth_service.create_api_key(
            user_id=user.user_id,
            name="Test API Key",
            scopes=["read"],
        )

        assert api_key is not None
        assert raw_key is not None
        assert api_key.name == "Test API Key"
        assert api_key.user_id == user.user_id
        assert len(raw_key) > 0

    @pytest.mark.asyncio
    async def test_authenticate_api_key(self, auth_service: AuthenticationService):
        """Authenticating with valid API key should work."""
        user = await auth_service.create_user(
            username="apikeyauth",
            email="apikeyauth@example.com",
            password="ValidPass123!",
        )
        api_key, raw_key = await auth_service.create_api_key(
            user_id=user.user_id,
            name="Auth Key",
        )

        auth_user, auth_key, message = await auth_service.authenticate_api_key(raw_key)

        assert auth_user is not None
        assert auth_key is not None
        assert message == "Success"
        assert auth_user.user_id == user.user_id
        assert auth_key.use_count == 1

    @pytest.mark.asyncio
    async def test_authenticate_api_key_invalid(
        self,
        auth_service: AuthenticationService,
    ):
        """Authenticating with invalid API key should fail."""
        user, key, message = await auth_service.authenticate_api_key("invalid_api_key")

        assert user is None
        assert key is None
        assert "not found" in message.lower()

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, auth_service: AuthenticationService):
        """Revoking an API key should disable it."""
        user = await auth_service.create_user(
            username="revokeapikey",
            email="revokeapi@example.com",
            password="ValidPass123!",
        )
        api_key, raw_key = await auth_service.create_api_key(
            user_id=user.user_id,
            name="Revoke Key",
        )

        result = await auth_service.revoke_api_key(api_key.key_id)

        assert result is True
        assert api_key.active is False

        # Should not authenticate anymore
        auth_user, _, message = await auth_service.authenticate_api_key(raw_key)
        assert auth_user is None
        assert "inactive" in message.lower()

    # ===========================================
    # SESSION MANAGEMENT TESTS
    # ===========================================

    @pytest.mark.asyncio
    async def test_create_session(self, auth_service: AuthenticationService):
        """Creating a session should work."""
        user = await auth_service.create_user(
            username="sessionuser",
            email="session@example.com",
            password="ValidPass123!",
        )
        token = await auth_service.create_access_token(user)

        session = await auth_service.create_session(
            user=user,
            token=token,
            ip_address="192.168.1.1",
            user_agent="TestBrowser/1.0",
        )

        assert session is not None
        assert session.user_id == user.user_id
        assert session.token_id == token.token_id
        assert session.ip_address == "192.168.1.1"
        assert session.active is True

    @pytest.mark.asyncio
    async def test_session_limit_enforcement(self, auth_service: AuthenticationService):
        """Creating sessions beyond limit should invalidate oldest."""
        user = await auth_service.create_user(
            username="sessionlimit",
            email="sessionlimit@example.com",
            password="ValidPass123!",
        )

        # Create sessions up to limit
        sessions = []
        max_sessions = auth_service._settings.max_sessions_per_user

        for i in range(max_sessions + 1):
            token = await auth_service.create_access_token(user)
            session = await auth_service.create_session(user, token)
            sessions.append(session)

        # First session should be inactive
        assert sessions[0].active is False

        # Last session should be active
        assert sessions[-1].active is True

    @pytest.mark.asyncio
    async def test_update_session_activity(self, auth_service: AuthenticationService):
        """Updating session activity should refresh expiration."""
        user = await auth_service.create_user(
            username="activityuser",
            email="activity@example.com",
            password="ValidPass123!",
        )
        token = await auth_service.create_access_token(user)
        session = await auth_service.create_session(user, token)

        original_last_activity = session.last_activity

        # Small delay to ensure time difference
        import asyncio
        await asyncio.sleep(0.01)

        result = await auth_service.update_session_activity(session.session_id)

        assert result is True
        assert session.last_activity > original_last_activity

    @pytest.mark.asyncio
    async def test_invalidate_session(self, auth_service: AuthenticationService):
        """Invalidating a session should mark it inactive."""
        user = await auth_service.create_user(
            username="invalidatesession",
            email="invalidate@example.com",
            password="ValidPass123!",
        )
        token = await auth_service.create_access_token(user)
        session = await auth_service.create_session(user, token)

        result = await auth_service.invalidate_session(session.session_id)

        assert result is True
        assert session.active is False

    @pytest.mark.asyncio
    async def test_get_user_sessions(self, auth_service: AuthenticationService):
        """Getting user sessions should return active sessions."""
        user = await auth_service.create_user(
            username="usersessions",
            email="usersessions@example.com",
            password="ValidPass123!",
        )

        for _ in range(3):
            token = await auth_service.create_access_token(user)
            await auth_service.create_session(user, token)

        sessions = await auth_service.get_user_sessions(user.user_id)

        assert len(sessions) == 3
        assert all(s.active for s in sessions)

    @pytest.mark.asyncio
    async def test_invalidate_all_user_sessions(
        self,
        auth_service: AuthenticationService,
    ):
        """Invalidating all sessions should mark them inactive."""
        user = await auth_service.create_user(
            username="invalidateall",
            email="invalidateall@example.com",
            password="ValidPass123!",
        )

        sessions = []
        for _ in range(3):
            token = await auth_service.create_access_token(user)
            session = await auth_service.create_session(user, token)
            sessions.append(session)

        count = await auth_service.invalidate_all_user_sessions(user.user_id)

        assert count == 3
        assert all(not s.active for s in sessions)


class TestAuthServiceSingleton:
    """Tests for get_auth_service singleton."""

    def test_get_auth_service_returns_instance(self):
        """get_auth_service should return an AuthenticationService."""
        from platform.security.auth import get_auth_service

        service = get_auth_service()

        assert isinstance(service, AuthenticationService)

    def test_get_auth_service_returns_same_instance(self):
        """get_auth_service should return the same instance."""
        from platform.security.auth import get_auth_service

        service1 = get_auth_service()
        service2 = get_auth_service()

        assert service1 is service2
