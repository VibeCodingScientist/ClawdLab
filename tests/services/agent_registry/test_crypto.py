"""Tests for cryptographic identity utilities."""

import pytest
from platform.shared.utils.crypto import AgentIdentity, generate_agent_keypair


class TestAgentIdentity:
    """Tests for AgentIdentity class."""

    def test_generate_keypair(self):
        """Test generating a new keypair."""
        private_key, identity = generate_agent_keypair()

        assert private_key is not None
        assert identity is not None
        assert len(identity.agent_id) == 32
        assert identity.public_key is not None

    def test_agent_id_deterministic(self):
        """Test that agent_id is deterministic from public key."""
        private_key, identity1 = generate_agent_keypair()

        # Create identity from same public key
        pem = identity1.get_public_key_pem()
        identity2 = AgentIdentity.from_public_key_pem(pem)

        assert identity1.agent_id == identity2.agent_id

    def test_unique_agent_ids(self):
        """Test that different keys produce different IDs."""
        _, identity1 = generate_agent_keypair()
        _, identity2 = generate_agent_keypair()

        assert identity1.agent_id != identity2.agent_id

    def test_sign_and_verify(self):
        """Test signing and verification."""
        private_key, identity = generate_agent_keypair()

        message = b"test message"
        signature = private_key.sign(message)

        assert identity.verify_signature(message, signature)

    def test_verify_wrong_message(self):
        """Test verification fails with wrong message."""
        private_key, identity = generate_agent_keypair()

        message = b"test message"
        wrong_message = b"wrong message"
        signature = private_key.sign(message)

        assert not identity.verify_signature(wrong_message, signature)

    def test_verify_wrong_key(self):
        """Test verification fails with wrong key."""
        private_key1, identity1 = generate_agent_keypair()
        _, identity2 = generate_agent_keypair()

        message = b"test message"
        signature = private_key1.sign(message)

        # Signature from key1 should not verify with identity2
        assert not identity2.verify_signature(message, signature)

    def test_pem_roundtrip(self):
        """Test PEM encoding roundtrip."""
        _, identity = generate_agent_keypair()

        pem = identity.get_public_key_pem()
        restored = AgentIdentity.from_public_key_pem(pem)

        assert identity.agent_id == restored.agent_id

    def test_base64_roundtrip(self):
        """Test Base64 encoding roundtrip."""
        _, identity = generate_agent_keypair()

        b64 = identity.get_public_key_base64()
        restored = AgentIdentity.from_public_key_base64(b64)

        assert identity.agent_id == restored.agent_id

    def test_to_dict(self):
        """Test serialization to dict."""
        _, identity = generate_agent_keypair()

        data = identity.to_dict()

        assert "agent_id" in data
        assert "public_key" in data
        assert "public_key_base64" in data
        assert data["agent_id"] == identity.agent_id
