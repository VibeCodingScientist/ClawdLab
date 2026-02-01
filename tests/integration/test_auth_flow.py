"""Integration tests for authentication flow.

Tests the complete authentication lifecycle:
- User registration and login
- Token creation and refresh
- Session management
- Logout and token revocation
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from platform.security.auth import AuthenticationService
from platform.security.base import UserStatus, TokenType


def utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture
def auth_service():
    """Create fresh AuthenticationService for each test."""
    with patch("platform.security.auth.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            password_min_length=8,
            password_require_uppercase=True,
            password_require_lowercase=True,
            password_require_digit=True,
            password_require_special=False,
            jwt_access_token_expire_minutes=30,
            jwt_refresh_token_expire_days=7,
            api_key_length=32,
            session_timeout_minutes=60,
            max_sessions_per_user=5,
        )
        return AuthenticationService()


# ===========================================
# USER REGISTRATION FLOW
# ===========================================


class TestUserRegistrationFlow:
    """Tests for user registration."""

    @pytest.mark.asyncio
    async def test_register_new_user(self, auth_service):
        """Test complete user registration flow."""
        # Register new user
        user = await auth_service.create_user(
            username="newuser",
            email="newuser@example.com",
            password="SecurePass123",
            roles=["researcher"],
        )

        # Verify user created
        assert user is not None
        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.status == UserStatus.ACTIVE
        assert "researcher" in user.roles

        # Verify user can be retrieved
        retrieved = await auth_service.get_user(user.user_id)
        assert retrieved is not None
        assert retrieved.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_register_duplicate_username_fails(self, auth_service):
        """Test registration fails with duplicate username."""
        await auth_service.create_user(
            username="testuser",
            email="test1@example.com",
            password="SecurePass123",
        )

        with pytest.raises(ValueError, match="Username already exists"):
            await auth_service.create_user(
                username="testuser",
                email="test2@example.com",
                password="SecurePass123",
            )

    @pytest.mark.asyncio
    async def test_register_duplicate_email_fails(self, auth_service):
        """Test registration fails with duplicate email."""
        await auth_service.create_user(
            username="user1",
            email="shared@example.com",
            password="SecurePass123",
        )

        with pytest.raises(ValueError, match="Email already exists"):
            await auth_service.create_user(
                username="user2",
                email="shared@example.com",
                password="SecurePass123",
            )

    @pytest.mark.asyncio
    async def test_register_weak_password_fails(self, auth_service):
        """Test registration fails with weak password."""
        with pytest.raises(ValueError, match="Invalid password"):
            await auth_service.create_user(
                username="user",
                email="user@example.com",
                password="weak",  # Too short, no uppercase, no digit
            )


# ===========================================
# LOGIN FLOW
# ===========================================


class TestLoginFlow:
    """Tests for user login."""

    @pytest.mark.asyncio
    async def test_successful_login(self, auth_service):
        """Test successful login flow."""
        # Create user
        await auth_service.create_user(
            username="loginuser",
            email="login@example.com",
            password="SecurePass123",
        )

        # Login
        user, message = await auth_service.authenticate(
            username="loginuser",
            password="SecurePass123",
        )

        assert user is not None
        assert message == "Success"
        assert user.username == "loginuser"
        assert user.login_count == 1
        assert user.last_login is not None

    @pytest.mark.asyncio
    async def test_login_updates_count(self, auth_service):
        """Test login count increments."""
        await auth_service.create_user(
            username="countuser",
            email="count@example.com",
            password="SecurePass123",
        )

        # First login
        user1, _ = await auth_service.authenticate("countuser", "SecurePass123")
        assert user1.login_count == 1

        # Second login
        user2, _ = await auth_service.authenticate("countuser", "SecurePass123")
        assert user2.login_count == 2

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, auth_service):
        """Test login with wrong password."""
        await auth_service.create_user(
            username="wrongpass",
            email="wrongpass@example.com",
            password="SecurePass123",
        )

        user, message = await auth_service.authenticate(
            username="wrongpass",
            password="WrongPassword",
        )

        assert user is None
        assert message == "Invalid password"

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, auth_service):
        """Test login with nonexistent username."""
        user, message = await auth_service.authenticate(
            username="nonexistent",
            password="AnyPassword123",
        )

        assert user is None
        assert message == "User not found"

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, auth_service):
        """Test login with inactive user."""
        user = await auth_service.create_user(
            username="inactive",
            email="inactive@example.com",
            password="SecurePass123",
        )

        # Deactivate user
        await auth_service.update_user(user.user_id, status="suspended")

        result, message = await auth_service.authenticate(
            username="inactive",
            password="SecurePass123",
        )

        assert result is None
        assert "suspended" in message.lower()


# ===========================================
# TOKEN FLOW
# ===========================================


class TestTokenFlow:
    """Tests for token management."""

    @pytest.mark.asyncio
    async def test_create_access_token(self, auth_service):
        """Test access token creation."""
        user = await auth_service.create_user(
            username="tokenuser",
            email="token@example.com",
            password="SecurePass123",
        )

        token = await auth_service.create_access_token(user)

        assert token is not None
        assert token.token_type == TokenType.ACCESS
        assert token.user_id == user.user_id
        assert token.expires_at > utcnow()

    @pytest.mark.asyncio
    async def test_create_refresh_token(self, auth_service):
        """Test refresh token creation."""
        user = await auth_service.create_user(
            username="refreshuser",
            email="refresh@example.com",
            password="SecurePass123",
        )

        token = await auth_service.create_refresh_token(user)

        assert token is not None
        assert token.token_type == TokenType.REFRESH
        assert token.expires_at > utcnow() + timedelta(days=6)

    @pytest.mark.asyncio
    async def test_authenticate_with_token(self, auth_service):
        """Test authentication using token."""
        user = await auth_service.create_user(
            username="authtoken",
            email="authtoken@example.com",
            password="SecurePass123",
        )

        token = await auth_service.create_access_token(user)

        auth_user, auth_token, message = await auth_service.authenticate_token(
            token.token_value
        )

        assert auth_user is not None
        assert auth_user.user_id == user.user_id
        assert auth_token is not None
        assert message == "Success"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_token(self, auth_service):
        """Test authentication with invalid token."""
        user, token, message = await auth_service.authenticate_token("invalid-token")

        assert user is None
        assert token is None
        assert "not found" in message.lower()

    @pytest.mark.asyncio
    async def test_refresh_access_token(self, auth_service):
        """Test refreshing access token."""
        user = await auth_service.create_user(
            username="refreshflow",
            email="refreshflow@example.com",
            password="SecurePass123",
        )

        refresh_token = await auth_service.create_refresh_token(user)

        new_access_token, message = await auth_service.refresh_access_token(
            refresh_token.token_value
        )

        assert new_access_token is not None
        assert new_access_token.token_type == TokenType.ACCESS
        assert message == "Success"

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token(self, auth_service):
        """Test refresh fails with invalid token."""
        token, message = await auth_service.refresh_access_token("invalid-refresh")

        assert token is None
        assert "not found" in message.lower()

    @pytest.mark.asyncio
    async def test_revoke_token(self, auth_service):
        """Test token revocation."""
        user = await auth_service.create_user(
            username="revokeuser",
            email="revoke@example.com",
            password="SecurePass123",
        )

        token = await auth_service.create_access_token(user)

        # Revoke token
        result = await auth_service.revoke_token(token.token_id)
        assert result is True

        # Try to authenticate with revoked token
        auth_user, auth_token, message = await auth_service.authenticate_token(
            token.token_value
        )
        assert auth_user is None
        assert "revoked" in message.lower()

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, auth_service):
        """Test revoking all user tokens."""
        user = await auth_service.create_user(
            username="revokeall",
            email="revokeall@example.com",
            password="SecurePass123",
        )

        # Create multiple tokens
        token1 = await auth_service.create_access_token(user)
        token2 = await auth_service.create_access_token(user)
        token3 = await auth_service.create_refresh_token(user)

        # Revoke all
        count = await auth_service.revoke_all_user_tokens(user.user_id)
        assert count == 3

        # All tokens should be revoked
        for token in [token1, token2, token3]:
            _, _, message = await auth_service.authenticate_token(token.token_value)
            assert "revoked" in message.lower() or "invalid" in message.lower()


# ===========================================
# API KEY FLOW
# ===========================================


class TestAPIKeyFlow:
    """Tests for API key management."""

    @pytest.mark.asyncio
    async def test_create_api_key(self, auth_service):
        """Test API key creation."""
        user = await auth_service.create_user(
            username="apikeyuser",
            email="apikey@example.com",
            password="SecurePass123",
        )

        api_key, raw_key = await auth_service.create_api_key(
            user_id=user.user_id,
            name="Test API Key",
            scopes=["read", "write"],
        )

        assert api_key is not None
        assert raw_key is not None
        assert api_key.name == "Test API Key"
        assert "read" in api_key.scopes

    @pytest.mark.asyncio
    async def test_authenticate_with_api_key(self, auth_service):
        """Test authentication using API key."""
        user = await auth_service.create_user(
            username="apiauthuser",
            email="apiauth@example.com",
            password="SecurePass123",
        )

        api_key, raw_key = await auth_service.create_api_key(
            user_id=user.user_id,
            name="Auth Key",
        )

        auth_user, auth_key, message = await auth_service.authenticate_api_key(raw_key)

        assert auth_user is not None
        assert auth_user.user_id == user.user_id
        assert auth_key is not None
        assert message == "Success"
        assert auth_key.use_count == 1

    @pytest.mark.asyncio
    async def test_api_key_usage_tracking(self, auth_service):
        """Test API key usage is tracked."""
        user = await auth_service.create_user(
            username="apistats",
            email="apistats@example.com",
            password="SecurePass123",
        )

        api_key, raw_key = await auth_service.create_api_key(
            user_id=user.user_id,
            name="Stats Key",
        )

        # Use key multiple times
        await auth_service.authenticate_api_key(raw_key)
        await auth_service.authenticate_api_key(raw_key)
        _, key, _ = await auth_service.authenticate_api_key(raw_key)

        assert key.use_count == 3
        assert key.last_used is not None

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, auth_service):
        """Test API key revocation."""
        user = await auth_service.create_user(
            username="apirevokeuser",
            email="apirevoke@example.com",
            password="SecurePass123",
        )

        api_key, raw_key = await auth_service.create_api_key(
            user_id=user.user_id,
            name="Revoke Key",
        )

        # Revoke
        result = await auth_service.revoke_api_key(api_key.key_id)
        assert result is True

        # Try to use revoked key
        user, key, message = await auth_service.authenticate_api_key(raw_key)
        assert user is None
        assert "inactive" in message.lower()


# ===========================================
# SESSION FLOW
# ===========================================


class TestSessionFlow:
    """Tests for session management."""

    @pytest.mark.asyncio
    async def test_create_session(self, auth_service):
        """Test session creation."""
        user = await auth_service.create_user(
            username="sessionuser",
            email="session@example.com",
            password="SecurePass123",
        )
        token = await auth_service.create_access_token(user)

        session = await auth_service.create_session(
            user=user,
            token=token,
            ip_address="127.0.0.1",
            user_agent="TestClient/1.0",
        )

        assert session is not None
        assert session.user_id == user.user_id
        assert session.ip_address == "127.0.0.1"
        assert session.active is True

    @pytest.mark.asyncio
    async def test_session_activity_update(self, auth_service):
        """Test session activity updates."""
        user = await auth_service.create_user(
            username="activityuser",
            email="activity@example.com",
            password="SecurePass123",
        )
        token = await auth_service.create_access_token(user)

        session = await auth_service.create_session(user, token)
        original_activity = session.last_activity

        # Update activity
        result = await auth_service.update_session_activity(session.session_id)
        assert result is True

        # Verify activity updated
        updated_session = await auth_service.get_session(session.session_id)
        assert updated_session.last_activity >= original_activity

    @pytest.mark.asyncio
    async def test_invalidate_session(self, auth_service):
        """Test session invalidation."""
        user = await auth_service.create_user(
            username="invalidatesession",
            email="invalidate@example.com",
            password="SecurePass123",
        )
        token = await auth_service.create_access_token(user)

        session = await auth_service.create_session(user, token)

        # Invalidate
        result = await auth_service.invalidate_session(session.session_id)
        assert result is True

        # Verify inactive
        invalid_session = await auth_service.get_session(session.session_id)
        assert invalid_session.active is False

    @pytest.mark.asyncio
    async def test_session_limit_enforcement(self, auth_service):
        """Test maximum session limit."""
        user = await auth_service.create_user(
            username="sessionlimit",
            email="limit@example.com",
            password="SecurePass123",
        )

        # Create sessions up to limit (5)
        sessions = []
        for i in range(6):
            token = await auth_service.create_access_token(user)
            session = await auth_service.create_session(user, token)
            sessions.append(session)

        # Get active sessions
        active_sessions = await auth_service.get_user_sessions(user.user_id)

        # Should be at most max_sessions_per_user (5)
        assert len(active_sessions) <= 5

    @pytest.mark.asyncio
    async def test_invalidate_all_user_sessions(self, auth_service):
        """Test invalidating all user sessions."""
        user = await auth_service.create_user(
            username="invalidateall",
            email="invalidateall@example.com",
            password="SecurePass123",
        )

        # Create multiple sessions
        for _ in range(3):
            token = await auth_service.create_access_token(user)
            await auth_service.create_session(user, token)

        # Invalidate all
        count = await auth_service.invalidate_all_user_sessions(user.user_id)
        assert count == 3

        # Verify no active sessions
        active = await auth_service.get_user_sessions(user.user_id)
        assert len(active) == 0


# ===========================================
# COMPLETE LOGIN/LOGOUT FLOW
# ===========================================


class TestCompleteAuthFlow:
    """Tests for complete authentication flows."""

    @pytest.mark.asyncio
    async def test_complete_login_to_logout_flow(self, auth_service):
        """Test complete flow from login to logout."""
        # 1. Register
        user = await auth_service.create_user(
            username="fullflow",
            email="fullflow@example.com",
            password="SecurePass123",
        )

        # 2. Login
        auth_user, message = await auth_service.authenticate(
            "fullflow", "SecurePass123"
        )
        assert auth_user is not None

        # 3. Create tokens
        access_token = await auth_service.create_access_token(auth_user)
        refresh_token = await auth_service.create_refresh_token(auth_user)

        # 4. Create session
        session = await auth_service.create_session(
            auth_user, access_token, "127.0.0.1", "Browser/1.0"
        )

        # 5. Use access token
        token_user, _, _ = await auth_service.authenticate_token(access_token.token_value)
        assert token_user is not None

        # 6. Refresh token
        new_access, _ = await auth_service.refresh_access_token(refresh_token.token_value)
        assert new_access is not None

        # 7. Logout (invalidate session and revoke tokens)
        await auth_service.invalidate_session(session.session_id)
        await auth_service.revoke_token(access_token.token_id)
        await auth_service.revoke_token(new_access.token_id)

        # 8. Verify logged out
        _, _, message = await auth_service.authenticate_token(access_token.token_value)
        assert "revoked" in message.lower()

        session = await auth_service.get_session(session.session_id)
        assert session.active is False

    @pytest.mark.asyncio
    async def test_password_change_invalidates_tokens(self, auth_service):
        """Test password change invalidates all tokens."""
        # Create and login
        user = await auth_service.create_user(
            username="passchange",
            email="passchange@example.com",
            password="SecurePass123",
        )

        # Create tokens
        access_token = await auth_service.create_access_token(user)
        refresh_token = await auth_service.create_refresh_token(user)

        # Change password
        result = await auth_service.change_password(
            user.user_id,
            current_password="SecurePass123",
            new_password="NewSecurePass456",
        )
        assert result is True

        # Revoke all tokens after password change
        await auth_service.revoke_all_user_tokens(user.user_id)

        # Old tokens should be invalid
        _, _, msg1 = await auth_service.authenticate_token(access_token.token_value)
        assert "revoked" in msg1.lower()

        _, _, msg2 = await auth_service.authenticate_token(refresh_token.token_value)
        assert "revoked" in msg2.lower()

        # New login should work
        auth_user, _ = await auth_service.authenticate(
            "passchange", "NewSecurePass456"
        )
        assert auth_user is not None

    @pytest.mark.asyncio
    async def test_user_deletion_cleanup(self, auth_service):
        """Test user deletion cleans up tokens and sessions."""
        # Create user with tokens
        user = await auth_service.create_user(
            username="deleteuser",
            email="delete@example.com",
            password="SecurePass123",
        )

        access_token = await auth_service.create_access_token(user)
        await auth_service.create_session(user, access_token)

        # Delete user
        result = await auth_service.delete_user(user.user_id)
        assert result is True

        # User should not exist
        retrieved = await auth_service.get_user(user.user_id)
        assert retrieved is None

        # Token should be revoked
        _, _, message = await auth_service.authenticate_token(access_token.token_value)
        assert "revoked" in message.lower() or "not found" in message.lower()
