"""Global pytest fixtures for the Autonomous Scientific Research Platform.

This module provides shared fixtures for testing including:
- Database sessions (PostgreSQL, Redis)
- Mock clients for unit tests
- Test data factories
- Async test utilities
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


def utcnow() -> datetime:
    """Return current UTC time with timezone info (SOTA replacement for datetime.utcnow())."""
    return datetime.now(timezone.utc)

# ===========================================
# ASYNC EVENT LOOP CONFIGURATION
# ===========================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ===========================================
# DATABASE SESSION FIXTURES
# ===========================================


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncMock, None]:
    """Create a mock async database session for unit tests.

    For integration tests, use `real_db_session` fixture instead.
    """
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    # Mock context manager behavior
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    yield session


@pytest_asyncio.fixture
async def real_db_session() -> AsyncGenerator[Any, None]:
    """Create a real transactional database session for integration tests.

    This fixture creates an actual PostgreSQL connection and wraps
    each test in a transaction that is rolled back after the test.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from platform.infrastructure.database.models import Base

    # Use test database URL
    test_db_url = "postgresql+asyncpg://test:test@localhost:5432/asrp_test"

    engine = create_async_engine(test_db_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        async with session.begin():
            yield session
            # Rollback after each test
            await session.rollback()

    await engine.dispose()


# ===========================================
# REDIS MOCK FIXTURES
# ===========================================


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Create a mock Redis client for unit tests."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    redis.expire = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=-1)
    redis.incr = AsyncMock(return_value=1)
    redis.decr = AsyncMock(return_value=0)
    redis.lpush = AsyncMock(return_value=1)
    redis.rpop = AsyncMock(return_value=None)
    redis.lrange = AsyncMock(return_value=[])
    redis.hset = AsyncMock(return_value=1)
    redis.hget = AsyncMock(return_value=None)
    redis.hgetall = AsyncMock(return_value={})
    redis.hdel = AsyncMock(return_value=1)
    redis.sadd = AsyncMock(return_value=1)
    redis.srem = AsyncMock(return_value=1)
    redis.smembers = AsyncMock(return_value=set())
    redis.sismember = AsyncMock(return_value=False)
    redis.pipeline = MagicMock(return_value=redis)
    redis.execute = AsyncMock(return_value=[])
    redis.close = AsyncMock()
    return redis


@pytest_asyncio.fixture
async def real_redis_client() -> AsyncGenerator[Any, None]:
    """Create a real Redis client for integration tests."""
    import redis.asyncio as redis

    client = redis.Redis(host="localhost", port=6379, db=15)  # Use db=15 for tests

    yield client

    # Clean up test data
    await client.flushdb()
    await client.close()


# ===========================================
# HTTP CLIENT FIXTURES
# ===========================================


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for API testing."""
    from platform.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def authenticated_client(
    async_client: AsyncClient,
    test_user_token: str,
) -> AsyncClient:
    """Create an authenticated async HTTP client."""
    async_client.headers["Authorization"] = f"Bearer {test_user_token}"
    return async_client


# ===========================================
# USER TEST DATA FIXTURES
# ===========================================


@pytest.fixture
def test_user_data() -> dict[str, Any]:
    """Create test user data."""
    return {
        "user_id": str(uuid4()),
        "username": "testuser",
        "email": "test@example.com",
        "password": "TestPass123!",
        "roles": ["researcher"],
        "permissions": ["experiments:read", "experiments:write"],
    }


@pytest.fixture
def test_admin_data() -> dict[str, Any]:
    """Create test admin user data."""
    return {
        "user_id": str(uuid4()),
        "username": "admin",
        "email": "admin@example.com",
        "password": "AdminPass123!",
        "roles": ["admin"],
        "permissions": ["*"],
    }


@pytest.fixture
def test_user(test_user_data: dict[str, Any]) -> Any:
    """Create a test User instance."""
    from platform.security.base import User, UserStatus

    return User(
        user_id=test_user_data["user_id"],
        username=test_user_data["username"],
        email=test_user_data["email"],
        password_hash="hashed_password",
        status=UserStatus.ACTIVE,
        roles=test_user_data["roles"],
        permissions=test_user_data["permissions"],
    )


@pytest.fixture
def test_user_token(test_user: Any) -> str:
    """Create a test access token for the test user."""
    import secrets
    return secrets.token_urlsafe(48)


# ===========================================
# AGENT TEST DATA FIXTURES
# ===========================================


@pytest.fixture
def test_agent_data() -> dict[str, Any]:
    """Create test agent data."""
    agent_id = str(uuid4())
    return {
        "agent_id": agent_id,
        "display_name": "TestAgent",
        "agent_type": "openclaw",
        "status": "active",
        "capabilities": ["mathematics", "ml_ai"],
        "metadata": {
            "version": "1.0.0",
            "description": "A test agent for unit tests",
        },
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }


@pytest.fixture
def test_agent_keypair() -> dict[str, Any]:
    """Generate a test agent keypair."""
    try:
        from platform.shared.utils.crypto import generate_agent_keypair
        private_key, identity = generate_agent_keypair()
        return {
            "private_key": private_key,
            "identity": identity,
            "agent_id": identity.agent_id,
            "public_key_pem": identity.get_public_key_pem(),
        }
    except ImportError:
        # Fallback for when crypto module is not available
        return {
            "agent_id": str(uuid4()),
            "public_key_pem": "-----BEGIN PUBLIC KEY-----\nMOCK_KEY\n-----END PUBLIC KEY-----",
        }


# ===========================================
# EXPERIMENT TEST DATA FIXTURES
# ===========================================


@pytest.fixture
def test_experiment_data(test_user_data: dict[str, Any]) -> dict[str, Any]:
    """Create test experiment data."""
    return {
        "experiment_id": str(uuid4()),
        "name": "Test Experiment",
        "description": "A test experiment for unit testing",
        "hypothesis_id": str(uuid4()),
        "status": "pending",
        "created_by": test_user_data["user_id"],
        "parameters": {
            "learning_rate": 0.001,
            "batch_size": 32,
            "epochs": 100,
        },
        "metrics": {},
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }


@pytest.fixture
def test_experiment_plan(test_experiment_data: dict[str, Any]) -> dict[str, Any]:
    """Create test experiment plan data."""
    return {
        "plan_id": str(uuid4()),
        "experiment_id": test_experiment_data["experiment_id"],
        "steps": [
            {
                "step_id": str(uuid4()),
                "name": "Data Preparation",
                "type": "preprocessing",
                "status": "pending",
            },
            {
                "step_id": str(uuid4()),
                "name": "Model Training",
                "type": "training",
                "status": "pending",
            },
            {
                "step_id": str(uuid4()),
                "name": "Evaluation",
                "type": "evaluation",
                "status": "pending",
            },
        ],
        "resources": {
            "cpu_cores": 4,
            "memory_gb": 16,
            "gpu_count": 1,
        },
        "estimated_duration_minutes": 60,
        "created_at": utcnow(),
    }


# ===========================================
# CLAIM TEST DATA FIXTURES
# ===========================================


@pytest.fixture
def test_claim_data(test_agent_data: dict[str, Any]) -> dict[str, Any]:
    """Create test claim data."""
    return {
        "claim_id": str(uuid4()),
        "agent_id": test_agent_data["agent_id"],
        "claim_type": "theorem",
        "domain": "mathematics",
        "title": "Test Mathematical Claim",
        "description": "A test claim for verifying mathematical theorems",
        "content": {
            "statement": "For all n > 0, sum(1..n) = n*(n+1)/2",
            "proof": "By mathematical induction...",
        },
        "verification_status": "pending",
        "verification_score": None,
        "novelty_score": None,
        "tags": ["arithmetic", "induction", "test"],
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }


# ===========================================
# KNOWLEDGE TEST DATA FIXTURES
# ===========================================


@pytest.fixture
def test_knowledge_entry_data() -> dict[str, Any]:
    """Create test knowledge entry data."""
    return {
        "entry_id": str(uuid4()),
        "entry_type": "concept",
        "title": "Test Concept",
        "content": {
            "definition": "A test concept for unit testing",
            "properties": ["property1", "property2"],
        },
        "source": "test",
        "confidence": 0.95,
        "embedding": [0.1] * 768,  # Mock embedding vector
        "metadata": {
            "created_by": "test",
            "version": "1.0",
        },
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }


@pytest.fixture
def test_knowledge_relationship_data(
    test_knowledge_entry_data: dict[str, Any],
) -> dict[str, Any]:
    """Create test knowledge relationship data."""
    return {
        "relationship_id": str(uuid4()),
        "source_id": test_knowledge_entry_data["entry_id"],
        "target_id": str(uuid4()),
        "relationship_type": "related_to",
        "weight": 0.8,
        "properties": {
            "evidence": "Test evidence",
        },
        "created_at": utcnow(),
    }


# ===========================================
# TOKEN TEST DATA FIXTURES
# ===========================================


@pytest.fixture
def test_token_data(test_user_data: dict[str, Any]) -> dict[str, Any]:
    """Create test token data."""
    return {
        "token_id": str(uuid4()),
        "user_id": test_user_data["user_id"],
        "token_type": "access",
        "scopes": ["read", "write"],
        "expires_at": utcnow() + timedelta(hours=1),
        "created_at": utcnow(),
    }


@pytest.fixture
def test_api_key_data(test_user_data: dict[str, Any]) -> dict[str, Any]:
    """Create test API key data."""
    return {
        "key_id": str(uuid4()),
        "name": "Test API Key",
        "key_prefix": "srp_test1234",
        "user_id": test_user_data["user_id"],
        "scopes": ["read", "write"],
        "rate_limit": 1000,
        "expires_at": utcnow() + timedelta(days=30),
        "created_at": utcnow(),
    }


# ===========================================
# SERVICE MOCK FIXTURES
# ===========================================


@pytest.fixture
def mock_auth_service() -> MagicMock:
    """Create a mock authentication service."""
    service = MagicMock()
    service.authenticate = AsyncMock(return_value=(MagicMock(), "Success"))
    service.authenticate_token = AsyncMock(
        return_value=(MagicMock(), MagicMock(), "Success")
    )
    service.create_access_token = AsyncMock(return_value=MagicMock())
    service.create_refresh_token = AsyncMock(return_value=MagicMock())
    service.revoke_token = AsyncMock(return_value=True)
    service.create_user = AsyncMock(return_value=MagicMock())
    service.get_user = AsyncMock(return_value=MagicMock())
    return service


@pytest.fixture
def mock_authorization_service() -> MagicMock:
    """Create a mock authorization service."""
    from platform.security.base import AuthorizationResult

    service = MagicMock()
    service.check_permission = AsyncMock(
        return_value=AuthorizationResult(allowed=True, reason="Allowed")
    )
    service.get_user_permissions = AsyncMock(return_value=["read", "write"])
    service.has_role = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_monitoring_service() -> MagicMock:
    """Create a mock monitoring service."""
    service = MagicMock()
    service.record_metric = AsyncMock()
    service.get_metrics = AsyncMock(return_value=[])
    service.get_system_status = AsyncMock(
        return_value={"status": "healthy", "checks": {}}
    )
    service.create_alert = AsyncMock(return_value=MagicMock())
    return service


# ===========================================
# UTILITY FIXTURES
# ===========================================


@pytest.fixture
def freeze_time():
    """Fixture to freeze time for testing time-dependent code."""
    frozen_time = datetime(2025, 1, 15, 12, 0, 0)

    with patch("datetime.datetime") as mock_datetime:
        mock_datetime.utcnow.return_value = frozen_time
        mock_datetime.now.return_value = frozen_time
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        yield frozen_time


@pytest.fixture
def random_uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid4())


# ===========================================
# CLEANUP FIXTURES
# ===========================================


@pytest.fixture(autouse=True)
def cleanup_singletons():
    """Clean up singleton instances between tests."""
    yield

    # Reset singleton instances after each test
    # This ensures test isolation
    try:
        from platform.security.auth import _auth_service
        import platform.security.auth as auth_module
        auth_module._auth_service = None
    except (ImportError, AttributeError):
        pass

    try:
        from platform.monitoring.service import _monitoring_service
        import platform.monitoring.service as monitoring_module
        monitoring_module._monitoring_service = None
    except (ImportError, AttributeError):
        pass
