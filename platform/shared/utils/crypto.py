"""Cryptographic utilities for agent identity and authentication."""

import base64
import hashlib
import secrets
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


@dataclass
class AgentIdentity:
    """
    Represents an agent's cryptographic identity.

    The agent's ID is derived from their public key, ensuring
    that identity cannot be forged without the private key.
    """

    public_key: Ed25519PublicKey
    agent_id: str  # Derived from public key hash

    @classmethod
    def from_public_key_bytes(cls, public_key_bytes: bytes) -> "AgentIdentity":
        """Create identity from raw public key bytes (32 bytes)."""
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)

        # Agent ID is first 32 chars of SHA-256 hash of public key
        agent_id = hashlib.sha256(public_key_bytes).hexdigest()[:32]

        return cls(public_key=public_key, agent_id=agent_id)

    @classmethod
    def from_public_key_pem(cls, pem: str) -> "AgentIdentity":
        """Create identity from PEM-encoded public key."""
        public_key = serialization.load_pem_public_key(pem.encode())
        if not isinstance(public_key, Ed25519PublicKey):
            raise ValueError("Public key must be Ed25519")

        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return cls.from_public_key_bytes(public_key_bytes)

    @classmethod
    def from_public_key_base64(cls, b64: str) -> "AgentIdentity":
        """Create identity from base64-encoded public key."""
        public_key_bytes = base64.b64decode(b64)
        return cls.from_public_key_bytes(public_key_bytes)

    def verify_signature(self, message: bytes, signature: bytes) -> bool:
        """
        Verify a signature from this agent.

        Args:
            message: The original message that was signed
            signature: The 64-byte Ed25519 signature

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            self.public_key.verify(signature, message)
            return True
        except Exception:
            return False

    def get_public_key_pem(self) -> str:
        """Get PEM-encoded public key."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def get_public_key_base64(self) -> str:
        """Get base64-encoded raw public key."""
        raw_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(raw_bytes).decode()

    def to_dict(self) -> dict:
        """Serialize identity for API responses."""
        return {
            "agent_id": self.agent_id,
            "public_key": self.get_public_key_pem(),
            "public_key_base64": self.get_public_key_base64(),
        }


def generate_agent_keypair() -> tuple[Ed25519PrivateKey, AgentIdentity]:
    """
    Generate a new agent keypair.

    This is a utility function for agents to generate their identity.
    The private key should be kept secret by the agent.

    Returns:
        Tuple of (private_key, agent_identity)
    """
    private_key = Ed25519PrivateKey.generate()
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    identity = AgentIdentity.from_public_key_bytes(public_key_bytes)

    return private_key, identity


def generate_api_token(prefix: str = "srp_") -> str:
    """
    Generate a secure API token.

    Args:
        prefix: Token prefix for identification

    Returns:
        Token string in format: prefix + 48 random bytes (base64)
    """
    return f"{prefix}{secrets.token_urlsafe(48)}"


def generate_challenge_nonce() -> str:
    """Generate a random nonce for registration challenges."""
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    """
    Hash a token for secure storage.

    Uses SHA-256 for fast lookups. For additional security,
    consider using bcrypt for primary authentication tokens.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return secrets.compare_digest(a.encode(), b.encode())
