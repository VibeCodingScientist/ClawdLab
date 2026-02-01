"""Repository layer for Agent Registry database operations."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from platform.infrastructure.database.models import (
    Agent,
    AgentCapability,
    AgentReputation,
    AgentToken,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class AgentRepository:
    """Repository for agent database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, agent_id: str | UUID) -> Agent | None:
        """Get agent by ID with capabilities loaded."""
        query = (
            select(Agent)
            .where(Agent.id == agent_id)
            .options(selectinload(Agent.capabilities))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_public_key(self, public_key: str) -> Agent | None:
        """Get agent by public key."""
        query = select(Agent).where(Agent.public_key == public_key)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def exists_by_public_key(self, public_key: str) -> bool:
        """Check if agent exists by public key."""
        query = select(Agent.id).where(Agent.public_key == public_key)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        agent_id: str,
        public_key: str,
        display_name: str | None,
        agent_type: str,
        capabilities: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> Agent:
        """Create a new agent with capabilities and reputation."""
        # Create agent
        agent = Agent(
            id=agent_id,
            public_key=public_key,
            display_name=display_name,
            agent_type=agent_type,
            status="active",
            metadata_=metadata or {},
        )
        self.session.add(agent)

        # Create capabilities
        for domain in capabilities:
            capability = AgentCapability(
                agent_id=agent_id,
                domain=domain,
                capability_level="basic",
            )
            self.session.add(capability)

        # Create reputation record
        reputation = AgentReputation(
            agent_id=agent_id,
            total_karma=0,
            domain_karma={},
        )
        self.session.add(reputation)

        await self.session.flush()
        await self.session.refresh(agent, ["capabilities"])

        logger.info("agent_created", agent_id=agent_id)
        return agent

    async def update(
        self,
        agent_id: str | UUID,
        **kwargs,
    ) -> Agent | None:
        """Update agent fields."""
        # Filter out None values
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            return await self.get_by_id(agent_id)

        updates["updated_at"] = datetime.utcnow()

        await self.session.execute(
            update(Agent).where(Agent.id == agent_id).values(**updates)
        )
        await self.session.flush()

        return await self.get_by_id(agent_id)

    async def update_status(self, agent_id: str | UUID, status: str) -> bool:
        """Update agent status."""
        result = await self.session.execute(
            update(Agent)
            .where(Agent.id == agent_id)
            .values(status=status, updated_at=datetime.utcnow())
        )
        return result.rowcount > 0

    async def add_capability(
        self,
        agent_id: str | UUID,
        domain: str,
        level: str = "basic",
    ) -> AgentCapability:
        """Add a capability to an agent."""
        capability = AgentCapability(
            agent_id=agent_id,
            domain=domain,
            capability_level=level,
        )
        self.session.add(capability)
        await self.session.flush()
        return capability

    async def remove_capability(self, agent_id: str | UUID, domain: str) -> bool:
        """Remove a capability from an agent."""
        result = await self.session.execute(
            delete(AgentCapability).where(
                AgentCapability.agent_id == agent_id,
                AgentCapability.domain == domain,
            )
        )
        return result.rowcount > 0

    async def get_capabilities(self, agent_id: str | UUID) -> list[AgentCapability]:
        """Get all capabilities for an agent."""
        query = select(AgentCapability).where(AgentCapability.agent_id == agent_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())


class TokenRepository:
    """Repository for token database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        agent_id: str | UUID,
        token_hash: str,
        token_prefix: str,
        name: str,
        scopes: list[str],
        expires_at: datetime | None,
    ) -> AgentToken:
        """Create a new token."""
        token = AgentToken(
            agent_id=agent_id,
            token_hash=token_hash,
            token_prefix=token_prefix,
            name=name,
            scopes=scopes,
            expires_at=expires_at,
        )
        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)

        logger.info("token_created", agent_id=str(agent_id), token_prefix=token_prefix)
        return token

    async def get_by_id(self, token_id: str | UUID) -> AgentToken | None:
        """Get token by ID."""
        query = select(AgentToken).where(AgentToken.id == token_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_prefix(self, token_prefix: str) -> list[AgentToken]:
        """Get tokens by prefix (for authentication)."""
        query = select(AgentToken).where(
            AgentToken.token_prefix == token_prefix,
            AgentToken.revoked_at.is_(None),
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_agent_tokens(self, agent_id: str | UUID) -> list[AgentToken]:
        """Get all tokens for an agent."""
        query = (
            select(AgentToken)
            .where(AgentToken.agent_id == agent_id)
            .order_by(AgentToken.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_tokens(self, agent_id: str | UUID) -> list[AgentToken]:
        """Get active (non-revoked, non-expired) tokens for an agent."""
        now = datetime.utcnow()
        query = (
            select(AgentToken)
            .where(
                AgentToken.agent_id == agent_id,
                AgentToken.revoked_at.is_(None),
                (AgentToken.expires_at.is_(None) | (AgentToken.expires_at > now)),
            )
            .order_by(AgentToken.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def revoke(self, token_id: str | UUID) -> bool:
        """Revoke a token."""
        result = await self.session.execute(
            update(AgentToken)
            .where(AgentToken.id == token_id, AgentToken.revoked_at.is_(None))
            .values(revoked_at=datetime.utcnow())
        )
        if result.rowcount > 0:
            logger.info("token_revoked", token_id=str(token_id))
        return result.rowcount > 0

    async def revoke_all(self, agent_id: str | UUID) -> int:
        """Revoke all tokens for an agent."""
        result = await self.session.execute(
            update(AgentToken)
            .where(
                AgentToken.agent_id == agent_id,
                AgentToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.utcnow())
        )
        if result.rowcount > 0:
            logger.info("tokens_revoked", agent_id=str(agent_id), count=result.rowcount)
        return result.rowcount

    async def update_last_used(self, token_id: str | UUID) -> None:
        """Update token last used timestamp."""
        await self.session.execute(
            update(AgentToken)
            .where(AgentToken.id == token_id)
            .values(last_used_at=datetime.utcnow())
        )

    async def delete_expired(self, days_expired: int = 30) -> int:
        """Delete tokens that have been expired for a certain number of days."""
        cutoff = datetime.utcnow() - timedelta(days=days_expired)
        result = await self.session.execute(
            delete(AgentToken).where(
                AgentToken.expires_at.is_not(None),
                AgentToken.expires_at < cutoff,
            )
        )
        if result.rowcount > 0:
            logger.info("expired_tokens_deleted", count=result.rowcount)
        return result.rowcount
