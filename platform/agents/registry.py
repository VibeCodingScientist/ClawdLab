"""Agent Registry Service for agent registration and discovery."""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from platform.agents.base import (
    AgentEvent,
    AgentInfo,
    AgentMetrics,
    AgentStatus,
)
from platform.agents.config import AGENT_TYPES, get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class AgentRegistry:
    """
    Registry for agent registration, discovery, and health tracking.

    Manages the lifecycle of agents in the system including:
    - Registration and deregistration
    - Health monitoring via heartbeats
    - Capability-based discovery
    - Agent metrics tracking
    """

    def __init__(self):
        """Initialize agent registry."""
        self._agents: dict[str, AgentInfo] = {}
        self._metrics: dict[str, AgentMetrics] = {}
        self._by_type: dict[str, set[str]] = defaultdict(set)
        self._by_capability: dict[str, set[str]] = defaultdict(set)
        self._events: list[AgentEvent] = []
        self._health_check_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the registry and health monitoring."""
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("agent_registry_started")

    async def stop(self) -> None:
        """Stop the registry."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("agent_registry_stopped")

    async def register(
        self,
        agent_type: str,
        name: str,
        capabilities: list[str],
        endpoint: str = "",
        description: str = "",
        metadata: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> AgentInfo:
        """
        Register a new agent.

        Args:
            agent_type: Type of agent (from AGENT_TYPES)
            name: Agent name
            capabilities: List of capabilities
            endpoint: Communication endpoint
            description: Agent description
            metadata: Additional metadata
            agent_id: Optional specific agent ID

        Returns:
            Registered agent info

        Raises:
            ValueError: If max agents reached or invalid type
        """
        if len(self._agents) >= settings.max_agents:
            raise ValueError(f"Maximum agents ({settings.max_agents}) reached")

        if agent_type not in AGENT_TYPES:
            logger.warning("unknown_agent_type", agent_type=agent_type)

        agent = AgentInfo(
            agent_type=agent_type,
            name=name,
            description=description or AGENT_TYPES.get(agent_type, {}).get("description", ""),
            capabilities=capabilities,
            status=AgentStatus.INITIALIZING,
            endpoint=endpoint,
            metadata=metadata or {},
        )

        if agent_id:
            agent.agent_id = agent_id

        # Store agent
        self._agents[agent.agent_id] = agent

        # Index by type
        self._by_type[agent_type].add(agent.agent_id)

        # Index by capabilities
        for cap in capabilities:
            self._by_capability[cap].add(agent.agent_id)

        # Initialize metrics
        self._metrics[agent.agent_id] = AgentMetrics(agent_id=agent.agent_id)

        # Record event
        await self._record_event(
            "registered",
            agent.agent_id,
            {"agent_type": agent_type, "name": name},
        )

        logger.info(
            "agent_registered",
            agent_id=agent.agent_id,
            agent_type=agent_type,
            name=name,
        )

        return agent

    async def unregister(self, agent_id: str) -> bool:
        """
        Unregister an agent.

        Args:
            agent_id: Agent ID to unregister

        Returns:
            True if unregistered successfully
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        # Remove from type index
        self._by_type[agent.agent_type].discard(agent_id)

        # Remove from capability index
        for cap in agent.capabilities:
            self._by_capability[cap].discard(agent_id)

        # Update status
        agent.status = AgentStatus.TERMINATED

        # Record event
        await self._record_event("unregistered", agent_id)

        # Remove agent
        del self._agents[agent_id]

        # Keep metrics for a while for historical purposes
        # Could add cleanup logic here

        logger.info("agent_unregistered", agent_id=agent_id)

        return True

    async def update_status(
        self,
        agent_id: str,
        status: AgentStatus,
        metadata: dict[str, Any] | None = None,
    ) -> AgentInfo | None:
        """
        Update agent status.

        Args:
            agent_id: Agent ID
            status: New status
            metadata: Optional metadata to update

        Returns:
            Updated agent info or None
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return None

        old_status = agent.status
        agent.status = status

        if metadata:
            agent.metadata.update(metadata)

        # Record status change
        if old_status != status:
            await self._record_event(
                "status_changed",
                agent_id,
                {"old_status": old_status.value, "new_status": status.value},
            )

        logger.info(
            "agent_status_updated",
            agent_id=agent_id,
            old_status=old_status.value,
            new_status=status.value,
        )

        return agent

    async def heartbeat(
        self,
        agent_id: str,
        metrics: dict[str, Any] | None = None,
    ) -> bool:
        """
        Record agent heartbeat.

        Args:
            agent_id: Agent ID
            metrics: Optional metrics to update

        Returns:
            True if heartbeat recorded
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        agent.last_heartbeat = datetime.utcnow()

        # Update to ready if was unhealthy
        if agent.status == AgentStatus.UNHEALTHY:
            agent.status = AgentStatus.READY
            await self._record_event(
                "recovered",
                agent_id,
                {"previous_status": "unhealthy"},
            )

        # Update metrics if provided
        if metrics and agent_id in self._metrics:
            agent_metrics = self._metrics[agent_id]
            agent_metrics.messages_sent = metrics.get(
                "messages_sent", agent_metrics.messages_sent
            )
            agent_metrics.messages_received = metrics.get(
                "messages_received", agent_metrics.messages_received
            )
            agent_metrics.requests_handled = metrics.get(
                "requests_handled", agent_metrics.requests_handled
            )
            agent_metrics.errors_count = metrics.get(
                "errors_count", agent_metrics.errors_count
            )
            agent_metrics.avg_response_time_ms = metrics.get(
                "avg_response_time_ms", agent_metrics.avg_response_time_ms
            )
            agent_metrics.last_updated = datetime.utcnow()

        return True

    async def get_agent(self, agent_id: str) -> AgentInfo | None:
        """Get agent info by ID."""
        return self._agents.get(agent_id)

    async def get_agents_by_type(
        self,
        agent_type: str,
        status: AgentStatus | None = None,
    ) -> list[AgentInfo]:
        """
        Get agents by type.

        Args:
            agent_type: Agent type to filter
            status: Optional status filter

        Returns:
            List of matching agents
        """
        agent_ids = self._by_type.get(agent_type, set())
        agents = [self._agents[aid] for aid in agent_ids if aid in self._agents]

        if status:
            agents = [a for a in agents if a.status == status]

        return agents

    async def get_agents_by_capability(
        self,
        capability: str,
        status: AgentStatus | None = None,
    ) -> list[AgentInfo]:
        """
        Get agents by capability.

        Args:
            capability: Required capability
            status: Optional status filter

        Returns:
            List of agents with the capability
        """
        agent_ids = self._by_capability.get(capability, set())
        agents = [self._agents[aid] for aid in agent_ids if aid in self._agents]

        if status:
            agents = [a for a in agents if a.status == status]

        return agents

    async def find_agents(
        self,
        capabilities: list[str] | None = None,
        agent_type: str | None = None,
        status: AgentStatus | None = None,
        limit: int = 100,
    ) -> list[AgentInfo]:
        """
        Find agents matching criteria.

        Args:
            capabilities: Required capabilities (all must match)
            agent_type: Required agent type
            status: Required status
            limit: Maximum results

        Returns:
            List of matching agents
        """
        # Start with all agents
        candidates = set(self._agents.keys())

        # Filter by type
        if agent_type:
            type_agents = self._by_type.get(agent_type, set())
            candidates = candidates.intersection(type_agents)

        # Filter by capabilities
        if capabilities:
            for cap in capabilities:
                cap_agents = self._by_capability.get(cap, set())
                candidates = candidates.intersection(cap_agents)

        # Get agent objects and filter by status
        agents = []
        for agent_id in candidates:
            agent = self._agents.get(agent_id)
            if agent:
                if status is None or agent.status == status:
                    agents.append(agent)

        # Sort by last heartbeat (most recent first) and limit
        agents.sort(key=lambda a: a.last_heartbeat, reverse=True)
        return agents[:limit]

    async def get_ready_agent(
        self,
        capability: str | None = None,
        agent_type: str | None = None,
    ) -> AgentInfo | None:
        """
        Get a ready agent for processing.

        Uses round-robin selection among ready agents.

        Args:
            capability: Required capability
            agent_type: Required agent type

        Returns:
            A ready agent or None
        """
        agents = await self.find_agents(
            capabilities=[capability] if capability else None,
            agent_type=agent_type,
            status=AgentStatus.READY,
        )

        if not agents:
            return None

        # Simple round-robin: pick the agent with oldest heartbeat
        agents.sort(key=lambda a: a.last_heartbeat)
        return agents[0]

    async def get_metrics(self, agent_id: str) -> AgentMetrics | None:
        """Get metrics for an agent."""
        return self._metrics.get(agent_id)

    async def get_all_metrics(self) -> list[AgentMetrics]:
        """Get metrics for all agents."""
        return list(self._metrics.values())

    async def list_agents(
        self,
        include_terminated: bool = False,
    ) -> list[AgentInfo]:
        """
        List all agents.

        Args:
            include_terminated: Include terminated agents

        Returns:
            List of all agents
        """
        agents = list(self._agents.values())

        if not include_terminated:
            agents = [a for a in agents if a.status != AgentStatus.TERMINATED]

        return agents

    async def get_events(
        self,
        agent_id: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AgentEvent]:
        """
        Get agent events.

        Args:
            agent_id: Filter by agent ID
            event_type: Filter by event type
            since: Filter events after this time
            limit: Maximum events

        Returns:
            List of matching events
        """
        events = self._events

        if agent_id:
            events = [e for e in events if e.agent_id == agent_id]

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if since:
            events = [e for e in events if e.timestamp >= since]

        # Most recent first
        events.sort(key=lambda e: e.timestamp, reverse=True)

        return events[:limit]

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        status_counts: dict[str, int] = defaultdict(int)
        type_counts: dict[str, int] = defaultdict(int)

        for agent in self._agents.values():
            status_counts[agent.status.value] += 1
            type_counts[agent.agent_type] += 1

        return {
            "total_agents": len(self._agents),
            "by_status": dict(status_counts),
            "by_type": dict(type_counts),
            "total_events": len(self._events),
        }

    async def _health_check_loop(self) -> None:
        """Background task to check agent health."""
        while True:
            try:
                await asyncio.sleep(settings.heartbeat_interval_seconds)
                await self._check_agent_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("health_check_error", error=str(e))

    async def _check_agent_health(self) -> None:
        """Check health of all agents based on heartbeat."""
        timeout = timedelta(seconds=settings.agent_timeout_seconds)
        now = datetime.utcnow()

        for agent_id, agent in self._agents.items():
            if agent.status == AgentStatus.TERMINATED:
                continue

            time_since_heartbeat = now - agent.last_heartbeat

            if time_since_heartbeat > timeout:
                if agent.status != AgentStatus.UNHEALTHY:
                    agent.status = AgentStatus.UNHEALTHY
                    await self._record_event(
                        "unhealthy",
                        agent_id,
                        {"seconds_since_heartbeat": time_since_heartbeat.total_seconds()},
                    )
                    logger.warning(
                        "agent_unhealthy",
                        agent_id=agent_id,
                        seconds_since_heartbeat=time_since_heartbeat.total_seconds(),
                    )

    async def _record_event(
        self,
        event_type: str,
        agent_id: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Record an agent event."""
        event = AgentEvent(
            event_type=event_type,
            agent_id=agent_id,
            data=data or {},
        )
        self._events.append(event)

        # Trim old events (keep last 10000)
        if len(self._events) > 10000:
            self._events = self._events[-10000:]


# Singleton instance
_registry_instance: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    """Get singleton AgentRegistry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AgentRegistry()
    return _registry_instance
