"""Pytest fixtures for Agent Registry tests."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from platform.shared.utils.crypto import generate_agent_keypair


def _utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@pytest.fixture
def agent_keypair():
    """Generate a test agent keypair."""
    private_key, identity = generate_agent_keypair()
    return {
        "private_key": private_key,
        "identity": identity,
        "agent_id": identity.agent_id,
        "public_key_pem": identity.get_public_key_pem(),
    }


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_redis_cache():
    """Create a mock Redis cache."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.setex = AsyncMock()
    cache.delete = AsyncMock()
    return cache


@pytest.fixture
def registration_challenge_data(agent_keypair):
    """Create mock registration challenge data."""
    import secrets
    from datetime import datetime, timedelta

    nonce = secrets.token_urlsafe(64)
    return {
        "challenge_nonce": nonce,
        "agent_id": agent_keypair["agent_id"],
        "public_key": agent_keypair["public_key_pem"],
        "display_name": "TestAgent",
        "agent_type": "openclaw",
        "capabilities": ["mathematics"],
        "metadata": {},
    }


@pytest.fixture
def valid_signature(agent_keypair, registration_challenge_data):
    """Create a valid signature for registration."""
    import base64

    message = f"register:{registration_challenge_data['challenge_nonce']}".encode()
    signature = agent_keypair["private_key"].sign(message)
    return base64.b64encode(signature).decode()


@pytest.fixture
def mock_agent_data(agent_keypair):
    """Create mock agent data."""
    return {
        "agent_id": agent_keypair["agent_id"],
        "display_name": "TestAgent",
        "agent_type": "openclaw",
        "status": "active",
        "capabilities": [
            {"domain": "mathematics", "capability_level": "basic", "verified_at": None}
        ],
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    }


@pytest.fixture
def mock_token_data():
    """Create mock token data."""
    return {
        "token_id": "test-token-id",
        "token_prefix": "srp_abcd1234",
        "name": "default",
        "scopes": ["read", "write"],
        "expires_at": _utcnow() + timedelta(days=365),
    }
