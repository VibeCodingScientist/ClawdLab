"""Tests for Agent Registry schemas."""

import pytest
from pydantic import ValidationError

from platform.services.agent_registry.schemas import (
    RegistrationInitiateRequest,
    RegistrationCompleteRequest,
    AgentUpdateRequest,
    CapabilityUpdateRequest,
    TokenCreateRequest,
)


class TestRegistrationInitiateRequest:
    """Tests for registration initiate request schema."""

    def test_valid_request(self):
        """Test valid registration request."""
        data = {
            "public_key": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAtest\n-----END PUBLIC KEY-----",
            "display_name": "TestAgent",
            "agent_type": "openclaw",
            "capabilities": ["mathematics", "ml_ai"],
        }
        request = RegistrationInitiateRequest(**data)
        assert request.public_key.startswith("-----BEGIN PUBLIC KEY-----")
        assert request.display_name == "TestAgent"
        assert request.agent_type == "openclaw"
        assert "mathematics" in request.capabilities

    def test_invalid_public_key_format(self):
        """Test that invalid public key format is rejected."""
        data = {
            "public_key": "not-a-valid-key",
            "agent_type": "openclaw",
        }
        with pytest.raises(ValidationError) as exc_info:
            RegistrationInitiateRequest(**data)
        assert "Public key must be PEM-encoded" in str(exc_info.value)

    def test_invalid_capability(self):
        """Test that invalid capabilities are rejected."""
        data = {
            "public_key": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAtest\n-----END PUBLIC KEY-----",
            "agent_type": "openclaw",
            "capabilities": ["invalid_domain"],
        }
        with pytest.raises(ValidationError) as exc_info:
            RegistrationInitiateRequest(**data)
        assert "Invalid capabilities" in str(exc_info.value)

    def test_default_values(self):
        """Test default values are set correctly."""
        data = {
            "public_key": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAtest\n-----END PUBLIC KEY-----",
        }
        request = RegistrationInitiateRequest(**data)
        assert request.agent_type == "openclaw"
        assert request.capabilities == []
        assert request.display_name is None


class TestRegistrationCompleteRequest:
    """Tests for registration complete request schema."""

    def test_valid_request(self):
        """Test valid completion request."""
        data = {
            "challenge_id": "test-challenge-id",
            "signature": "base64-encoded-signature",
        }
        request = RegistrationCompleteRequest(**data)
        assert request.challenge_id == "test-challenge-id"
        assert request.signature == "base64-encoded-signature"

    def test_missing_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            RegistrationCompleteRequest(challenge_id="test")


class TestTokenCreateRequest:
    """Tests for token create request schema."""

    def test_valid_request(self):
        """Test valid token creation request."""
        data = {
            "name": "my-token",
            "scopes": ["read", "write"],
            "expires_in_days": 90,
        }
        request = TokenCreateRequest(**data)
        assert request.name == "my-token"
        assert request.scopes == ["read", "write"]
        assert request.expires_in_days == 90

    def test_invalid_scopes(self):
        """Test that invalid scopes are rejected."""
        data = {
            "name": "my-token",
            "scopes": ["invalid_scope"],
        }
        with pytest.raises(ValidationError) as exc_info:
            TokenCreateRequest(**data)
        assert "Invalid scopes" in str(exc_info.value)

    def test_default_scopes(self):
        """Test default scopes."""
        data = {"name": "my-token"}
        request = TokenCreateRequest(**data)
        assert request.scopes == ["read", "write"]

    def test_expiry_bounds(self):
        """Test expiry day bounds."""
        # Too short
        with pytest.raises(ValidationError):
            TokenCreateRequest(name="test", expires_in_days=0)

        # Too long
        with pytest.raises(ValidationError):
            TokenCreateRequest(name="test", expires_in_days=1000)


class TestCapabilityUpdateRequest:
    """Tests for capability update request schema."""

    def test_valid_request(self):
        """Test valid capability update request."""
        data = {
            "add_capabilities": ["mathematics"],
            "remove_capabilities": ["ml_ai"],
        }
        request = CapabilityUpdateRequest(**data)
        assert "mathematics" in request.add_capabilities
        assert "ml_ai" in request.remove_capabilities

    def test_invalid_capabilities_rejected(self):
        """Test that invalid capabilities in add/remove are rejected."""
        with pytest.raises(ValidationError):
            CapabilityUpdateRequest(add_capabilities=["fake_domain"])

        with pytest.raises(ValidationError):
            CapabilityUpdateRequest(remove_capabilities=["fake_domain"])
