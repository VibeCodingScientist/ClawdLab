"""Research session manager for tracking agent work."""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from platform.orchestration.base import (
    ResearchSession,
    ResearchWorkflow,
)
from platform.orchestration.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class SessionManager:
    """
    Manage research sessions for agents.

    Features:
    - Session creation and tracking
    - Checkpointing for recovery
    - Session expiration
    - Context management
    """

    def __init__(self):
        """Initialize session manager."""
        self._sessions: dict[str, ResearchSession] = {}
        self._agent_sessions: dict[str, list[str]] = {}

    async def create_session(
        self,
        agent_id: str,
        context: dict[str, Any] | None = None,
        ttl_hours: int | None = None,
    ) -> ResearchSession:
        """
        Create a new research session.

        Args:
            agent_id: ID of the agent
            context: Initial session context
            ttl_hours: Session time-to-live

        Returns:
            Created session
        """
        # Check session limit
        agent_session_count = len(self._agent_sessions.get(agent_id, []))
        if agent_session_count >= settings.max_sessions_per_agent:
            raise ValueError(
                f"Agent {agent_id} has reached maximum sessions ({settings.max_sessions_per_agent})"
            )

        ttl = ttl_hours or settings.session_ttl_hours
        expires_at = datetime.utcnow() + timedelta(hours=ttl)

        session = ResearchSession(
            session_id=str(uuid4()),
            agent_id=agent_id,
            context=context or {},
            expires_at=expires_at,
        )

        self._sessions[session.session_id] = session

        if agent_id not in self._agent_sessions:
            self._agent_sessions[agent_id] = []
        self._agent_sessions[agent_id].append(session.session_id)

        logger.info(
            "session_created",
            session_id=session.session_id,
            agent_id=agent_id,
            expires_at=expires_at.isoformat(),
        )

        return session

    async def get_session(self, session_id: str) -> ResearchSession | None:
        """
        Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session or None if not found/expired
        """
        session = self._sessions.get(session_id)

        if session and session.is_expired:
            await self.close_session(session_id)
            return None

        if session:
            session.last_active_at = datetime.utcnow()

        return session

    async def get_agent_sessions(self, agent_id: str) -> list[ResearchSession]:
        """
        Get all active sessions for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of active sessions
        """
        session_ids = self._agent_sessions.get(agent_id, [])
        sessions = []

        for session_id in session_ids:
            session = await self.get_session(session_id)
            if session:
                sessions.append(session)

        return sessions

    async def update_session(
        self,
        session_id: str,
        context: dict[str, Any] | None = None,
        workflow_ids: list[str] | None = None,
        task_ids: list[str] | None = None,
    ) -> ResearchSession | None:
        """
        Update session state.

        Args:
            session_id: Session ID
            context: Updated context (merged with existing)
            workflow_ids: Workflow IDs to add
            task_ids: Active task IDs

        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            return None

        if context:
            session.context.update(context)

        if workflow_ids:
            for wf_id in workflow_ids:
                if wf_id not in session.workflow_ids:
                    session.workflow_ids.append(wf_id)

        if task_ids is not None:
            session.active_task_ids = task_ids

        session.last_active_at = datetime.utcnow()

        logger.debug("session_updated", session_id=session_id)

        return session

    async def create_checkpoint(
        self,
        session_id: str,
        checkpoint_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a checkpoint for session recovery.

        Args:
            session_id: Session ID
            checkpoint_data: Additional checkpoint data

        Returns:
            Checkpoint info
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        checkpoint = {
            "checkpoint_id": str(uuid4()),
            "created_at": datetime.utcnow().isoformat(),
            "context": session.context.copy(),
            "workflow_ids": session.workflow_ids.copy(),
            "active_task_ids": session.active_task_ids.copy(),
            "data": checkpoint_data or {},
        }

        session.checkpoints.append(checkpoint)

        # Limit checkpoint history
        if len(session.checkpoints) > 100:
            session.checkpoints = session.checkpoints[-100:]

        logger.info(
            "checkpoint_created",
            session_id=session_id,
            checkpoint_id=checkpoint["checkpoint_id"],
        )

        return checkpoint

    async def restore_from_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str | None = None,
    ) -> ResearchSession | None:
        """
        Restore session from a checkpoint.

        Args:
            session_id: Session ID
            checkpoint_id: Specific checkpoint (default: latest)

        Returns:
            Restored session
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        if not session.checkpoints:
            return session

        # Find checkpoint
        if checkpoint_id:
            checkpoint = next(
                (cp for cp in session.checkpoints if cp["checkpoint_id"] == checkpoint_id),
                None,
            )
        else:
            checkpoint = session.checkpoints[-1]

        if not checkpoint:
            return session

        # Restore state
        session.context = checkpoint["context"].copy()
        session.workflow_ids = checkpoint["workflow_ids"].copy()
        session.active_task_ids = checkpoint["active_task_ids"].copy()
        session.last_active_at = datetime.utcnow()

        logger.info(
            "session_restored",
            session_id=session_id,
            checkpoint_id=checkpoint["checkpoint_id"],
        )

        return session

    async def close_session(self, session_id: str) -> bool:
        """
        Close a session.

        Args:
            session_id: Session ID

        Returns:
            True if closed
        """
        session = self._sessions.pop(session_id, None)
        if not session:
            return False

        # Remove from agent's session list
        if session.agent_id in self._agent_sessions:
            if session_id in self._agent_sessions[session.agent_id]:
                self._agent_sessions[session.agent_id].remove(session_id)

        logger.info(
            "session_closed",
            session_id=session_id,
            agent_id=session.agent_id,
            duration_seconds=(datetime.utcnow() - session.created_at).total_seconds(),
        )

        return True

    async def extend_session(
        self,
        session_id: str,
        hours: int | None = None,
    ) -> ResearchSession | None:
        """
        Extend session expiration.

        Args:
            session_id: Session ID
            hours: Hours to extend (default: session_ttl_hours)

        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            return None

        extension = timedelta(hours=hours or settings.session_ttl_hours)
        session.expires_at = datetime.utcnow() + extension

        logger.info(
            "session_extended",
            session_id=session_id,
            new_expiry=session.expires_at.isoformat(),
        )

        return session

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        expired = []
        now = datetime.utcnow()

        for session_id, session in self._sessions.items():
            if session.expires_at and now > session.expires_at:
                expired.append(session_id)

        for session_id in expired:
            await self.close_session(session_id)

        if expired:
            logger.info("expired_sessions_cleaned", count=len(expired))

        return len(expired)

    def get_session_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        now = datetime.utcnow()
        active = 0
        expiring_soon = 0

        for session in self._sessions.values():
            if not session.is_expired:
                active += 1
                if session.expires_at and session.expires_at < now + timedelta(hours=1):
                    expiring_soon += 1

        return {
            "total_sessions": len(self._sessions),
            "active_sessions": active,
            "expiring_soon": expiring_soon,
            "agents_with_sessions": len(self._agent_sessions),
        }

    def get_all_sessions(self) -> list[ResearchSession]:
        """Get all active sessions."""
        return [s for s in self._sessions.values() if not s.is_expired]


class DistributedSessionManager(SessionManager):
    """
    Distributed session manager using Redis.

    Extends SessionManager for multi-instance deployments.
    """

    def __init__(self, redis_url: str | None = None):
        """Initialize distributed session manager."""
        super().__init__()
        self._redis_url = redis_url or settings.redis_url
        self._redis_client = None

    async def _get_redis(self):
        """Get Redis client."""
        if self._redis_client is None:
            import redis.asyncio as redis
            self._redis_client = redis.from_url(self._redis_url)
        return self._redis_client

    async def create_session(
        self,
        agent_id: str,
        context: dict[str, Any] | None = None,
        ttl_hours: int | None = None,
    ) -> ResearchSession:
        """Create session with Redis storage."""
        # For now, use local implementation
        # Production would store in Redis
        return await super().create_session(agent_id, context, ttl_hours)


# Singleton instance
_manager_instance: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get singleton SessionManager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = SessionManager()
    return _manager_instance
