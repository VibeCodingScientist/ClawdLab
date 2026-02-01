"""Main Agent Communication Service coordinating all agent operations."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine

from platform.agents.base import (
    AgentEvent,
    AgentInfo,
    AgentMetrics,
    AgentStatus,
    Channel,
    DeadLetter,
    Message,
    MessagePriority,
    Pipeline,
    Subscription,
)
from platform.agents.broker import MessageBroker, get_message_broker
from platform.agents.config import AGENT_TYPES, get_settings
from platform.agents.patterns import (
    Broadcast,
    ChoreographyPattern,
    PipelinePattern,
    PublishSubscribe,
    RequestResponse,
    ScatterGather,
    get_broadcast,
    get_choreography,
    get_pipeline,
    get_pub_sub,
    get_request_response,
    get_scatter_gather,
)
from platform.agents.registry import AgentRegistry, get_agent_registry
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Type alias
MessageHandler = Callable[[Message], Coroutine[Any, Any, None]]


@dataclass
class CommunicationStats:
    """Overall communication statistics."""

    total_agents: int
    agents_by_status: dict[str, int]
    agents_by_type: dict[str, int]
    total_channels: int
    total_subscriptions: int
    total_messages: int
    dead_letters: int
    pending_responses: int


class AgentCommunicationService:
    """
    Main service for agent communication.

    Coordinates agent registry, message broker, and communication patterns
    to provide a unified interface for agent interactions.
    """

    def __init__(self):
        """Initialize agent communication service."""
        self._registry = get_agent_registry()
        self._broker = get_message_broker()
        self._request_response = get_request_response()
        self._pub_sub = get_pub_sub()
        self._scatter_gather = get_scatter_gather()
        self._broadcast_pattern = get_broadcast()
        self._pipeline = get_pipeline()
        self._choreography = get_choreography()
        self._running = False

    async def start(self) -> None:
        """Start the agent communication service."""
        await self._registry.start()
        await self._broker.start()
        self._running = True
        logger.info("agent_communication_service_started")

    async def stop(self) -> None:
        """Stop the agent communication service."""
        self._running = False
        await self._broker.stop()
        await self._registry.stop()
        logger.info("agent_communication_service_stopped")

    # ===========================================
    # AGENT LIFECYCLE OPERATIONS
    # ===========================================

    async def register_agent(
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
            agent_type: Type of agent
            name: Agent name
            capabilities: List of capabilities
            endpoint: Communication endpoint
            description: Agent description
            metadata: Additional metadata
            agent_id: Optional specific agent ID

        Returns:
            Registered agent info
        """
        agent = await self._registry.register(
            agent_type=agent_type,
            name=name,
            capabilities=capabilities,
            endpoint=endpoint,
            description=description,
            metadata=metadata,
            agent_id=agent_id,
        )

        # Create agent's inbox channel
        await self._broker.create_channel(
            name=f"agent.{agent.agent_id}.inbox",
            channel_type=ChannelType.DIRECT,
            description=f"Inbox for {name}",
            created_by=agent.agent_id,
        )

        # Announce registration
        await self._broadcast_pattern.announce(
            sender_id="system",
            announcement_type="agent_registered",
            data={"agent_id": agent.agent_id, "agent_type": agent_type, "name": name},
        )

        return agent

    async def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent.

        Args:
            agent_id: Agent ID

        Returns:
            True if unregistered
        """
        # Get agent info before unregistering
        agent = await self._registry.get_agent(agent_id)
        if not agent:
            return False

        # Unsubscribe from all channels
        subscriptions = await self._broker.get_subscriptions(agent_id)
        for sub in subscriptions:
            await self._broker.unsubscribe(agent_id, sub.channel)

        # Unregister from registry
        result = await self._registry.unregister(agent_id)

        if result:
            # Announce unregistration
            await self._broadcast_pattern.announce(
                sender_id="system",
                announcement_type="agent_unregistered",
                data={"agent_id": agent_id, "agent_type": agent.agent_type},
            )

        return result

    async def set_agent_ready(self, agent_id: str) -> AgentInfo | None:
        """Mark agent as ready to receive messages."""
        return await self._registry.update_status(agent_id, AgentStatus.READY)

    async def set_agent_busy(self, agent_id: str) -> AgentInfo | None:
        """Mark agent as busy processing."""
        return await self._registry.update_status(agent_id, AgentStatus.BUSY)

    async def set_agent_paused(self, agent_id: str) -> AgentInfo | None:
        """Mark agent as paused."""
        return await self._registry.update_status(agent_id, AgentStatus.PAUSED)

    async def heartbeat(
        self,
        agent_id: str,
        metrics: dict[str, Any] | None = None,
    ) -> bool:
        """Record agent heartbeat."""
        return await self._registry.heartbeat(agent_id, metrics)

    async def get_agent(self, agent_id: str) -> AgentInfo | None:
        """Get agent info."""
        return await self._registry.get_agent(agent_id)

    async def list_agents(
        self,
        agent_type: str | None = None,
        capability: str | None = None,
        status: AgentStatus | None = None,
    ) -> list[AgentInfo]:
        """
        List agents with optional filters.

        Args:
            agent_type: Filter by agent type
            capability: Filter by capability
            status: Filter by status

        Returns:
            List of matching agents
        """
        if capability:
            return await self._registry.get_agents_by_capability(capability, status)
        elif agent_type:
            return await self._registry.get_agents_by_type(agent_type, status)
        else:
            agents = await self._registry.list_agents()
            if status:
                agents = [a for a in agents if a.status == status]
            return agents

    # ===========================================
    # MESSAGE OPERATIONS
    # ===========================================

    async def send_request(
        self,
        sender_id: str,
        recipient_id: str,
        subject: str,
        payload: dict[str, Any],
        timeout: float | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> Message:
        """
        Send a request and wait for response.

        Args:
            sender_id: Sender agent ID
            recipient_id: Recipient agent ID
            subject: Request subject
            payload: Request payload
            timeout: Response timeout
            priority: Message priority

        Returns:
            Response message
        """
        return await self._request_response.request(
            sender_id=sender_id,
            recipient_id=recipient_id,
            subject=subject,
            payload=payload,
            timeout=timeout,
            priority=priority,
        )

    async def send_request_by_capability(
        self,
        sender_id: str,
        capability: str,
        subject: str,
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> Message:
        """Send request to an agent with specific capability."""
        return await self._request_response.request_by_capability(
            sender_id=sender_id,
            capability=capability,
            subject=subject,
            payload=payload,
            timeout=timeout,
        )

    async def send_request_by_type(
        self,
        sender_id: str,
        agent_type: str,
        subject: str,
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> Message:
        """Send request to an agent of specific type."""
        return await self._request_response.request_by_type(
            sender_id=sender_id,
            agent_type=agent_type,
            subject=subject,
            payload=payload,
            timeout=timeout,
        )

    async def send_response(
        self,
        request: Message,
        sender_id: str,
        payload: dict[str, Any],
        success: bool = True,
    ) -> str:
        """Send response to a request."""
        return await self._broker.send_response(request, sender_id, payload, success)

    async def broadcast(
        self,
        sender_id: str,
        subject: str,
        payload: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """Broadcast message to all agents."""
        return await self._broadcast_pattern.broadcast(
            sender_id=sender_id,
            subject=subject,
            payload=payload,
            priority=priority,
        )

    async def scatter(
        self,
        sender_id: str,
        recipient_ids: list[str],
        subject: str,
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> list[Message]:
        """Send requests to multiple agents and gather responses."""
        return await self._scatter_gather.scatter(
            sender_id=sender_id,
            recipient_ids=recipient_ids,
            subject=subject,
            payload=payload,
            timeout=timeout,
        )

    # ===========================================
    # SUBSCRIPTION OPERATIONS
    # ===========================================

    async def subscribe(
        self,
        agent_id: str,
        channel: str,
        handler: MessageHandler | None = None,
    ) -> Subscription:
        """
        Subscribe agent to a channel.

        Args:
            agent_id: Subscribing agent ID
            channel: Channel name
            handler: Optional message handler

        Returns:
            Subscription info
        """
        return await self._broker.subscribe(
            agent_id=agent_id,
            channel=channel,
            handler=handler,
        )

    async def unsubscribe(self, agent_id: str, channel: str) -> bool:
        """Unsubscribe agent from a channel."""
        return await self._broker.unsubscribe(agent_id, channel)

    async def publish_event(
        self,
        sender_id: str,
        topic: str,
        subject: str,
        payload: dict[str, Any],
    ) -> str:
        """Publish event to a topic."""
        return await self._pub_sub.publish(
            sender_id=sender_id,
            topic=topic,
            subject=subject,
            payload=payload,
        )

    async def get_subscriptions(self, agent_id: str) -> list[Subscription]:
        """Get all subscriptions for an agent."""
        return await self._broker.get_subscriptions(agent_id)

    # ===========================================
    # CHANNEL OPERATIONS
    # ===========================================

    async def create_channel(
        self,
        name: str,
        channel_type: str,
        description: str = "",
        created_by: str = "",
    ) -> Channel:
        """Create a communication channel."""
        from platform.agents.base import ChannelType as CT

        return await self._broker.create_channel(
            name=name,
            channel_type=CT(channel_type),
            description=description,
            created_by=created_by,
        )

    async def get_channel(self, name: str) -> Channel | None:
        """Get channel info."""
        return await self._broker.get_channel(name)

    async def list_channels(self) -> list[Channel]:
        """List all channels."""
        return await self._broker.list_channels()

    # ===========================================
    # PIPELINE OPERATIONS
    # ===========================================

    async def create_pipeline(
        self,
        name: str,
        stages: list[dict[str, Any]],
        description: str = "",
        created_by: str = "",
    ) -> Pipeline:
        """Create a processing pipeline."""
        return await self._pipeline.create_pipeline(
            name=name,
            stages=stages,
            description=description,
            created_by=created_by,
        )

    async def submit_to_pipeline(
        self,
        pipeline_id: str,
        sender_id: str,
        payload: dict[str, Any],
    ) -> str:
        """Submit data to a pipeline."""
        return await self._pipeline.submit(
            pipeline_id=pipeline_id,
            sender_id=sender_id,
            payload=payload,
        )

    async def advance_pipeline_stage(
        self,
        pipeline_id: str,
        execution_id: str,
        current_stage: int,
        sender_id: str,
        result: dict[str, Any],
    ) -> bool:
        """Advance to next pipeline stage."""
        return await self._pipeline.advance_stage(
            pipeline_id=pipeline_id,
            execution_id=execution_id,
            current_stage=current_stage,
            sender_id=sender_id,
            result=result,
        )

    def get_pipeline(self, pipeline_id: str) -> Pipeline | None:
        """Get pipeline info."""
        return self._pipeline.get_pipeline(pipeline_id)

    def list_pipelines(self) -> list[Pipeline]:
        """List all pipelines."""
        return self._pipeline.list_pipelines()

    # ===========================================
    # MONITORING OPERATIONS
    # ===========================================

    async def get_agent_metrics(self, agent_id: str) -> AgentMetrics | None:
        """Get metrics for an agent."""
        return await self._registry.get_metrics(agent_id)

    async def get_all_metrics(self) -> list[AgentMetrics]:
        """Get metrics for all agents."""
        return await self._registry.get_all_metrics()

    async def get_agent_events(
        self,
        agent_id: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AgentEvent]:
        """Get agent events."""
        return await self._registry.get_events(
            agent_id=agent_id,
            event_type=event_type,
            since=since,
            limit=limit,
        )

    async def get_dead_letters(
        self,
        limit: int = 100,
        since: datetime | None = None,
    ) -> list[DeadLetter]:
        """Get dead-lettered messages."""
        return await self._broker.get_dead_letters(limit=limit, since=since)

    async def retry_dead_letter(self, message_id: str) -> bool:
        """Retry a dead-lettered message."""
        return await self._broker.retry_dead_letter(message_id)

    def get_stats(self) -> CommunicationStats:
        """Get overall communication statistics."""
        registry_stats = self._registry.get_stats()
        broker_stats = self._broker.get_stats()

        return CommunicationStats(
            total_agents=registry_stats["total_agents"],
            agents_by_status=registry_stats["by_status"],
            agents_by_type=registry_stats["by_type"],
            total_channels=broker_stats["total_channels"],
            total_subscriptions=broker_stats["total_subscriptions"],
            total_messages=broker_stats["total_messages"],
            dead_letters=broker_stats["dead_letters"],
            pending_responses=broker_stats["pending_responses"],
        )

    # ===========================================
    # HELPER OPERATIONS
    # ===========================================

    async def find_agent_for_task(
        self,
        capabilities: list[str] | None = None,
        agent_type: str | None = None,
    ) -> AgentInfo | None:
        """
        Find a ready agent for a task.

        Args:
            capabilities: Required capabilities
            agent_type: Required agent type

        Returns:
            Available agent or None
        """
        if capabilities:
            for cap in capabilities:
                agent = await self._registry.get_ready_agent(capability=cap)
                if agent:
                    return agent
        elif agent_type:
            return await self._registry.get_ready_agent(agent_type=agent_type)
        else:
            agents = await self._registry.find_agents(status=AgentStatus.READY, limit=1)
            return agents[0] if agents else None

        return None

    def get_agent_types(self) -> dict[str, Any]:
        """Get available agent types."""
        return AGENT_TYPES


# Import ChannelType for create_channel
from platform.agents.base import ChannelType

# Singleton instance
_service_instance: AgentCommunicationService | None = None


def get_agent_communication_service() -> AgentCommunicationService:
    """Get singleton AgentCommunicationService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = AgentCommunicationService()
    return _service_instance
