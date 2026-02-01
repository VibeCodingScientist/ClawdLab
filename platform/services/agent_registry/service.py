"""Service layer for Agent Registry business logic."""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from platform.services.agent_registry.config import get_settings
from platform.services.agent_registry.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
    ChallengeExpiredError,
    InvalidPublicKeyError,
    InvalidSignatureError,
    TokenNotFoundError,
)
from platform.services.agent_registry.repository import AgentRepository, TokenRepository
from platform.shared.clients.redis_client import RedisCache
from platform.shared.utils.crypto import AgentIdentity
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RegistrationService:
    """Handles agent registration flow."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.agent_repo = AgentRepository(session)
        self.token_repo = TokenRepository(session)
        self.cache = RedisCache("registration")

    async def initiate_registration(
        self,
        public_key: str,
        display_name: str | None,
        agent_type: str,
        capabilities: list[str],
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Start the registration process.

        Args:
            public_key: PEM-encoded Ed25519 public key
            display_name: Optional human-readable name
            agent_type: Type of agent
            capabilities: List of domain capabilities
            metadata: Additional agent metadata

        Returns:
            Challenge data for signing

        Raises:
            InvalidPublicKeyError: If public key is invalid
            AgentAlreadyExistsError: If agent already exists
        """
        # Parse and validate public key
        try:
            identity = AgentIdentity.from_public_key_pem(public_key)
        except Exception as e:
            raise InvalidPublicKeyError(f"Invalid public key format: {e}")

        # Check if agent already exists
        if await self.agent_repo.exists_by_public_key(public_key):
            raise AgentAlreadyExistsError(identity.agent_id)

        # Generate challenge
        challenge_id = secrets.token_urlsafe(32)
        challenge_nonce = secrets.token_urlsafe(64)
        expires_at = datetime.utcnow() + timedelta(
            seconds=settings.challenge_expiry_seconds
        )

        # Store challenge data in cache
        challenge_data = {
            "challenge_nonce": challenge_nonce,
            "agent_id": identity.agent_id,
            "public_key": public_key,
            "display_name": display_name,
            "agent_type": agent_type,
            "capabilities": capabilities,
            "metadata": metadata or {},
        }
        await self.cache.setex(
            f"challenge:{challenge_id}",
            settings.challenge_expiry_seconds,
            challenge_data,
        )

        logger.info(
            "registration_initiated",
            agent_id=identity.agent_id,
            challenge_id=challenge_id,
        )

        return {
            "challenge_id": challenge_id,
            "challenge_nonce": challenge_nonce,
            "message_to_sign": f"register:{challenge_nonce}",
            "expires_at": expires_at,
        }

    async def complete_registration(
        self,
        challenge_id: str,
        signature_b64: str,
    ) -> dict[str, Any]:
        """
        Complete registration with signed challenge.

        Args:
            challenge_id: Challenge ID from initiate step
            signature_b64: Base64-encoded signature

        Returns:
            Agent data with API token

        Raises:
            ChallengeExpiredError: If challenge expired or not found
            InvalidSignatureError: If signature verification fails
        """
        # Retrieve challenge data
        challenge_data = await self.cache.get(f"challenge:{challenge_id}")
        if not challenge_data:
            raise ChallengeExpiredError("Challenge expired or not found")

        # Decode signature
        try:
            signature = base64.b64decode(signature_b64)
        except Exception:
            raise InvalidSignatureError("Invalid signature encoding")

        # Reconstruct identity and verify signature
        identity = AgentIdentity.from_public_key_pem(challenge_data["public_key"])
        message = f"register:{challenge_data['challenge_nonce']}".encode()

        if not identity.verify_signature(message, signature):
            raise InvalidSignatureError("Signature verification failed")

        # Create agent
        agent = await self.agent_repo.create(
            agent_id=identity.agent_id,
            public_key=challenge_data["public_key"],
            display_name=challenge_data["display_name"],
            agent_type=challenge_data["agent_type"],
            capabilities=challenge_data["capabilities"],
            metadata=challenge_data["metadata"],
        )

        # Generate API token
        token_service = TokenService(self.session)
        token, token_data = await token_service.create_token(
            agent_id=identity.agent_id,
            name="default",
            scopes=["read", "write"],
            expires_in_days=settings.token_expiry_days,
        )

        # Commit transaction
        await self.session.commit()

        # Clean up challenge
        await self.cache.delete(f"challenge:{challenge_id}")

        logger.info("registration_completed", agent_id=identity.agent_id)

        return {
            "agent_id": identity.agent_id,
            "display_name": agent.display_name,
            "agent_type": agent.agent_type,
            "capabilities": [c.domain for c in agent.capabilities],
            "status": agent.status,
            "created_at": agent.created_at,
            "token": token,
            "token_expires_at": token_data["expires_at"],
        }


class AgentService:
    """Handles agent profile operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.agent_repo = AgentRepository(session)

    async def get_agent(self, agent_id: str | UUID) -> dict[str, Any]:
        """Get agent by ID."""
        agent = await self.agent_repo.get_by_id(agent_id)
        if not agent:
            raise AgentNotFoundError(str(agent_id))

        return {
            "agent_id": str(agent.id),
            "display_name": agent.display_name,
            "agent_type": agent.agent_type,
            "status": agent.status,
            "capabilities": [
                {
                    "domain": c.domain,
                    "capability_level": c.capability_level,
                    "verified_at": c.verified_at,
                }
                for c in agent.capabilities
            ],
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        }

    async def update_agent(
        self,
        agent_id: str | UUID,
        display_name: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """Update agent profile."""
        updates = {}
        if display_name is not None:
            updates["display_name"] = display_name
        if metadata is not None:
            updates["metadata_"] = metadata

        agent = await self.agent_repo.update(agent_id, **updates)
        if not agent:
            raise AgentNotFoundError(str(agent_id))

        await self.session.commit()
        return await self.get_agent(agent_id)

    async def update_capabilities(
        self,
        agent_id: str | UUID,
        add: list[str],
        remove: list[str],
    ) -> dict[str, Any]:
        """Update agent capabilities."""
        # Remove capabilities
        for domain in remove:
            await self.agent_repo.remove_capability(agent_id, domain)

        # Add capabilities
        for domain in add:
            try:
                await self.agent_repo.add_capability(agent_id, domain)
            except Exception:
                # Capability may already exist
                pass

        await self.session.commit()
        return await self.get_agent(agent_id)


class TokenService:
    """Handles token operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.token_repo = TokenRepository(session)

    async def create_token(
        self,
        agent_id: str | UUID,
        name: str,
        scopes: list[str],
        expires_in_days: int = 365,
    ) -> tuple[str, dict[str, Any]]:
        """
        Create a new API token.

        Returns:
            Tuple of (token_string, token_metadata)
        """
        # Generate token
        token = f"{settings.token_prefix}{secrets.token_urlsafe(48)}"
        token_prefix = token[:12]

        # Hash for storage
        token_hash = bcrypt.hashpw(token.encode(), bcrypt.gensalt(rounds=12)).decode()

        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Store token
        token_record = await self.token_repo.create(
            agent_id=agent_id,
            token_hash=token_hash,
            token_prefix=token_prefix,
            name=name,
            scopes=scopes,
            expires_at=expires_at,
        )

        return token, {
            "token_id": str(token_record.id),
            "token_prefix": token_prefix,
            "name": name,
            "scopes": scopes,
            "expires_at": expires_at,
        }

    async def list_tokens(self, agent_id: str | UUID) -> list[dict[str, Any]]:
        """List all tokens for an agent."""
        tokens = await self.token_repo.get_agent_tokens(agent_id)
        return [
            {
                "token_id": str(t.id),
                "token_prefix": t.token_prefix,
                "name": t.name,
                "scopes": t.scopes,
                "created_at": t.created_at,
                "expires_at": t.expires_at,
                "last_used_at": t.last_used_at,
                "is_revoked": t.revoked_at is not None,
            }
            for t in tokens
        ]

    async def revoke_token(self, agent_id: str | UUID, token_id: str | UUID) -> bool:
        """Revoke a specific token."""
        # Verify token belongs to agent
        token = await self.token_repo.get_by_id(token_id)
        if not token or str(token.agent_id) != str(agent_id):
            raise TokenNotFoundError(str(token_id))

        result = await self.token_repo.revoke(token_id)
        if result:
            await self.session.commit()
        return result


class AuthenticationService:
    """Handles token authentication."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.token_repo = TokenRepository(session)
        self.agent_repo = AgentRepository(session)
        self.cache = RedisCache("auth")

    async def authenticate_token(self, token: str) -> dict[str, Any] | None:
        """
        Authenticate an API token.

        Returns:
            Agent info if valid, None if invalid
        """
        # Quick format check
        if not token or not token.startswith(settings.token_prefix):
            return None

        token_prefix = token[:12]

        # Check cache first
        cached = await self.cache.get(f"token:{token_prefix}")
        if cached:
            # Update last used asynchronously
            if "token_id" in cached:
                await self.token_repo.update_last_used(cached["token_id"])
            return cached

        # Find potential matches by prefix
        tokens = await self.token_repo.get_by_prefix(token_prefix)

        for token_record in tokens:
            # Check expiration
            if token_record.expires_at and token_record.expires_at < datetime.utcnow():
                continue

            # Verify token hash
            if bcrypt.checkpw(token.encode(), token_record.token_hash.encode()):
                # Get agent info
                agent = await self.agent_repo.get_by_id(token_record.agent_id)
                if not agent or agent.status != "active":
                    return None

                result = {
                    "token_id": str(token_record.id),
                    "agent_id": str(agent.id),
                    "display_name": agent.display_name,
                    "agent_type": agent.agent_type,
                    "scopes": token_record.scopes,
                    "capabilities": [c.domain for c in agent.capabilities],
                }

                # Cache for 5 minutes
                await self.cache.setex(f"token:{token_prefix}", 300, result)

                # Update last used
                await self.token_repo.update_last_used(token_record.id)

                return result

        return None
