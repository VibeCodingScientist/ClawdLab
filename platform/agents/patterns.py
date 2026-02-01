"""Communication patterns for agent coordination."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine
from uuid import uuid4

from platform.agents.base import (
    AgentInfo,
    AgentStatus,
    ChannelType,
    Message,
    MessageHeader,
    MessagePriority,
    MessageType,
    Pipeline,
    PipelineStage,
)
from platform.agents.broker import MessageBroker, get_message_broker
from platform.agents.config import get_settings
from platform.agents.registry import AgentRegistry, get_agent_registry
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Type aliases
ResponseCallback = Callable[[Message], Coroutine[Any, Any, None]]
AggregatorFunc = Callable[[list[Message]], dict[str, Any]]


@dataclass
class RequestResponse:
    """Request-response pattern for synchronous agent communication."""

    broker: MessageBroker = field(default_factory=get_message_broker)
    registry: AgentRegistry = field(default_factory=get_agent_registry)
    default_timeout: float = field(default_factory=lambda: settings.request_timeout_seconds)

    async def request(
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
        return await self.broker.send_request(
            sender_id=sender_id,
            recipient_id=recipient_id,
            subject=subject,
            payload=payload,
            timeout=timeout or self.default_timeout,
            priority=priority,
        )

    async def request_by_capability(
        self,
        sender_id: str,
        capability: str,
        subject: str,
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> Message:
        """
        Send request to an agent with specific capability.

        Args:
            sender_id: Sender agent ID
            capability: Required capability
            subject: Request subject
            payload: Request payload
            timeout: Response timeout

        Returns:
            Response message

        Raises:
            ValueError: If no agent with capability is available
        """
        agent = await self.registry.get_ready_agent(capability=capability)
        if not agent:
            raise ValueError(f"No ready agent with capability: {capability}")

        return await self.request(
            sender_id=sender_id,
            recipient_id=agent.agent_id,
            subject=subject,
            payload=payload,
            timeout=timeout,
        )

    async def request_by_type(
        self,
        sender_id: str,
        agent_type: str,
        subject: str,
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> Message:
        """
        Send request to an agent of specific type.

        Args:
            sender_id: Sender agent ID
            agent_type: Required agent type
            subject: Request subject
            payload: Request payload
            timeout: Response timeout

        Returns:
            Response message
        """
        agent = await self.registry.get_ready_agent(agent_type=agent_type)
        if not agent:
            raise ValueError(f"No ready agent of type: {agent_type}")

        return await self.request(
            sender_id=sender_id,
            recipient_id=agent.agent_id,
            subject=subject,
            payload=payload,
            timeout=timeout,
        )


@dataclass
class PublishSubscribe:
    """Publish-subscribe pattern for event-driven communication."""

    broker: MessageBroker = field(default_factory=get_message_broker)

    async def create_topic(
        self,
        topic: str,
        description: str = "",
        created_by: str = "",
    ) -> None:
        """Create a topic channel."""
        await self.broker.create_channel(
            name=topic,
            channel_type=ChannelType.TOPIC,
            description=description,
            created_by=created_by,
        )

    async def subscribe(
        self,
        agent_id: str,
        topic: str,
        handler: Callable[[Message], Coroutine[Any, Any, None]],
        filter_pattern: str | None = None,
    ) -> str:
        """
        Subscribe to a topic.

        Args:
            agent_id: Subscribing agent ID
            topic: Topic name
            handler: Message handler
            filter_pattern: Optional message filter

        Returns:
            Subscription ID
        """
        subscription = await self.broker.subscribe(
            agent_id=agent_id,
            channel=topic,
            handler=handler,
            filter_pattern=filter_pattern,
        )
        return subscription.subscription_id

    async def unsubscribe(self, agent_id: str, topic: str) -> bool:
        """Unsubscribe from a topic."""
        return await self.broker.unsubscribe(agent_id, topic)

    async def publish(
        self,
        sender_id: str,
        topic: str,
        subject: str,
        payload: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """
        Publish an event to a topic.

        Args:
            sender_id: Publisher agent ID
            topic: Topic name
            subject: Event subject
            payload: Event payload
            priority: Message priority

        Returns:
            Message ID
        """
        message = Message(
            header=MessageHeader(priority=priority),
            message_type=MessageType.EVENT,
            sender_id=sender_id,
            channel=topic,
            subject=subject,
            payload=payload,
        )

        return await self.broker.publish(message)


@dataclass
class ScatterGather:
    """Scatter-gather pattern for parallel requests to multiple agents."""

    broker: MessageBroker = field(default_factory=get_message_broker)
    registry: AgentRegistry = field(default_factory=get_agent_registry)
    default_timeout: float = field(default_factory=lambda: settings.broadcast_timeout_seconds)

    async def scatter(
        self,
        sender_id: str,
        recipient_ids: list[str],
        subject: str,
        payload: dict[str, Any],
        timeout: float | None = None,
        require_all: bool = False,
    ) -> list[Message]:
        """
        Send requests to multiple agents and gather responses.

        Args:
            sender_id: Sender agent ID
            recipient_ids: List of recipient agent IDs
            subject: Request subject
            payload: Request payload
            timeout: Response timeout
            require_all: Fail if not all respond

        Returns:
            List of response messages
        """
        timeout = timeout or self.default_timeout

        # Send all requests concurrently
        tasks = [
            self.broker.send_request(
                sender_id=sender_id,
                recipient_id=recipient_id,
                subject=subject,
                payload=payload,
                timeout=timeout,
            )
            for recipient_id in recipient_ids
        ]

        # Gather responses
        if require_all:
            responses = await asyncio.gather(*tasks)
        else:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            # Filter out exceptions
            responses = [r for r in responses if isinstance(r, Message)]

        return responses

    async def scatter_by_capability(
        self,
        sender_id: str,
        capability: str,
        subject: str,
        payload: dict[str, Any],
        timeout: float | None = None,
        max_agents: int = 10,
    ) -> list[Message]:
        """
        Scatter to all agents with a capability.

        Args:
            sender_id: Sender agent ID
            capability: Required capability
            subject: Request subject
            payload: Request payload
            timeout: Response timeout
            max_agents: Maximum agents to query

        Returns:
            List of response messages
        """
        agents = await self.registry.get_agents_by_capability(
            capability=capability,
            status=AgentStatus.READY,
        )

        recipient_ids = [a.agent_id for a in agents[:max_agents]]

        return await self.scatter(
            sender_id=sender_id,
            recipient_ids=recipient_ids,
            subject=subject,
            payload=payload,
            timeout=timeout,
        )

    async def scatter_aggregate(
        self,
        sender_id: str,
        recipient_ids: list[str],
        subject: str,
        payload: dict[str, Any],
        aggregator: AggregatorFunc,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        Scatter requests and aggregate responses.

        Args:
            sender_id: Sender agent ID
            recipient_ids: List of recipient agent IDs
            subject: Request subject
            payload: Request payload
            aggregator: Function to aggregate responses
            timeout: Response timeout

        Returns:
            Aggregated result
        """
        responses = await self.scatter(
            sender_id=sender_id,
            recipient_ids=recipient_ids,
            subject=subject,
            payload=payload,
            timeout=timeout,
        )

        return aggregator(responses)


@dataclass
class Broadcast:
    """Broadcast pattern for system-wide notifications."""

    broker: MessageBroker = field(default_factory=get_message_broker)

    async def broadcast(
        self,
        sender_id: str,
        subject: str,
        payload: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """
        Broadcast message to all agents.

        Args:
            sender_id: Sender agent ID
            subject: Message subject
            payload: Message payload
            priority: Message priority

        Returns:
            Message ID
        """
        return await self.broker.broadcast(
            sender_id=sender_id,
            subject=subject,
            payload=payload,
            priority=priority,
        )

    async def announce(
        self,
        sender_id: str,
        announcement_type: str,
        data: dict[str, Any],
    ) -> str:
        """
        Make a system announcement.

        Args:
            sender_id: Announcer agent ID
            announcement_type: Type of announcement
            data: Announcement data

        Returns:
            Message ID
        """
        return await self.broadcast(
            sender_id=sender_id,
            subject=f"system.announcement.{announcement_type}",
            payload={
                "type": announcement_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
            },
            priority=MessagePriority.HIGH,
        )


@dataclass
class PipelinePattern:
    """Pipeline pattern for multi-stage processing."""

    broker: MessageBroker = field(default_factory=get_message_broker)
    registry: AgentRegistry = field(default_factory=get_agent_registry)
    _pipelines: dict[str, Pipeline] = field(default_factory=dict)

    async def create_pipeline(
        self,
        name: str,
        stages: list[dict[str, Any]],
        description: str = "",
        created_by: str = "",
    ) -> Pipeline:
        """
        Create a processing pipeline.

        Args:
            name: Pipeline name
            stages: List of stage configurations
            description: Pipeline description
            created_by: Creator ID

        Returns:
            Created pipeline
        """
        pipeline_stages = []

        for i, stage_config in enumerate(stages):
            stage = PipelineStage(
                name=stage_config.get("name", f"stage_{i}"),
                agent_type=stage_config.get("agent_type", ""),
                input_channel=stage_config.get("input_channel", f"{name}.stage.{i}.input"),
                output_channel=stage_config.get("output_channel", f"{name}.stage.{i}.output"),
                config=stage_config.get("config", {}),
            )
            pipeline_stages.append(stage)

            # Create channels for stage
            await self.broker.create_channel(
                name=stage.input_channel,
                channel_type=ChannelType.QUEUE,
                description=f"Input for {name} stage {i}",
            )

        pipeline = Pipeline(
            name=name,
            description=description,
            stages=pipeline_stages,
            created_by=created_by,
        )

        self._pipelines[pipeline.pipeline_id] = pipeline

        logger.info(
            "pipeline_created",
            pipeline_id=pipeline.pipeline_id,
            name=name,
            stages=len(stages),
        )

        return pipeline

    async def submit(
        self,
        pipeline_id: str,
        sender_id: str,
        payload: dict[str, Any],
    ) -> str:
        """
        Submit data to a pipeline.

        Args:
            pipeline_id: Pipeline ID
            sender_id: Submitter agent ID
            payload: Initial payload

        Returns:
            Pipeline execution ID
        """
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline or not pipeline.stages:
            raise ValueError(f"Pipeline not found: {pipeline_id}")

        execution_id = str(uuid4())

        # Send to first stage
        first_stage = pipeline.stages[0]
        message = Message(
            header=MessageHeader(
                trace_id=execution_id,
            ),
            message_type=MessageType.COMMAND,
            sender_id=sender_id,
            channel=first_stage.input_channel,
            subject=f"pipeline.{pipeline.name}.execute",
            payload={
                "pipeline_id": pipeline_id,
                "execution_id": execution_id,
                "stage_index": 0,
                "data": payload,
            },
        )

        await self.broker.publish(message)

        logger.info(
            "pipeline_submitted",
            pipeline_id=pipeline_id,
            execution_id=execution_id,
        )

        return execution_id

    async def advance_stage(
        self,
        pipeline_id: str,
        execution_id: str,
        current_stage: int,
        sender_id: str,
        result: dict[str, Any],
    ) -> bool:
        """
        Advance to next pipeline stage.

        Args:
            pipeline_id: Pipeline ID
            execution_id: Execution ID
            current_stage: Current stage index
            sender_id: Sender agent ID
            result: Result from current stage

        Returns:
            True if advanced to next stage, False if completed
        """
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return False

        next_stage_idx = current_stage + 1

        if next_stage_idx >= len(pipeline.stages):
            # Pipeline complete
            logger.info(
                "pipeline_completed",
                pipeline_id=pipeline_id,
                execution_id=execution_id,
            )
            return False

        # Send to next stage
        next_stage = pipeline.stages[next_stage_idx]
        message = Message(
            header=MessageHeader(
                trace_id=execution_id,
            ),
            message_type=MessageType.COMMAND,
            sender_id=sender_id,
            channel=next_stage.input_channel,
            subject=f"pipeline.{pipeline.name}.execute",
            payload={
                "pipeline_id": pipeline_id,
                "execution_id": execution_id,
                "stage_index": next_stage_idx,
                "data": result,
            },
        )

        await self.broker.publish(message)
        return True

    def get_pipeline(self, pipeline_id: str) -> Pipeline | None:
        """Get pipeline by ID."""
        return self._pipelines.get(pipeline_id)

    def list_pipelines(self) -> list[Pipeline]:
        """List all pipelines."""
        return list(self._pipelines.values())


@dataclass
class ChoreographyPattern:
    """Choreography pattern for event-driven coordination."""

    broker: MessageBroker = field(default_factory=get_message_broker)
    _workflows: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def define_workflow(
        self,
        name: str,
        triggers: dict[str, list[str]],
        description: str = "",
    ) -> str:
        """
        Define a choreographed workflow.

        Args:
            name: Workflow name
            triggers: Map of event -> list of actions to trigger
            description: Workflow description

        Returns:
            Workflow ID
        """
        workflow_id = str(uuid4())

        self._workflows[workflow_id] = {
            "name": name,
            "triggers": triggers,
            "description": description,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Set up event subscriptions
        for event_topic in triggers.keys():
            await self.broker.create_channel(
                name=event_topic,
                channel_type=ChannelType.TOPIC,
                description=f"Event topic for {name}",
            )

        logger.info(
            "choreography_defined",
            workflow_id=workflow_id,
            name=name,
            trigger_count=len(triggers),
        )

        return workflow_id

    async def emit_event(
        self,
        sender_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> str:
        """
        Emit an event that may trigger choreography.

        Args:
            sender_id: Event emitter ID
            event_type: Event type/topic
            data: Event data

        Returns:
            Message ID
        """
        message = Message(
            header=MessageHeader(),
            message_type=MessageType.EVENT,
            sender_id=sender_id,
            channel=event_type,
            subject=event_type,
            payload={
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        return await self.broker.publish(message)


# Singleton instances
_request_response: RequestResponse | None = None
_pub_sub: PublishSubscribe | None = None
_scatter_gather: ScatterGather | None = None
_broadcast: Broadcast | None = None
_pipeline: PipelinePattern | None = None
_choreography: ChoreographyPattern | None = None


def get_request_response() -> RequestResponse:
    """Get RequestResponse pattern instance."""
    global _request_response
    if _request_response is None:
        _request_response = RequestResponse()
    return _request_response


def get_pub_sub() -> PublishSubscribe:
    """Get PublishSubscribe pattern instance."""
    global _pub_sub
    if _pub_sub is None:
        _pub_sub = PublishSubscribe()
    return _pub_sub


def get_scatter_gather() -> ScatterGather:
    """Get ScatterGather pattern instance."""
    global _scatter_gather
    if _scatter_gather is None:
        _scatter_gather = ScatterGather()
    return _scatter_gather


def get_broadcast() -> Broadcast:
    """Get Broadcast pattern instance."""
    global _broadcast
    if _broadcast is None:
        _broadcast = Broadcast()
    return _broadcast


def get_pipeline() -> PipelinePattern:
    """Get Pipeline pattern instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = PipelinePattern()
    return _pipeline


def get_choreography() -> ChoreographyPattern:
    """Get Choreography pattern instance."""
    global _choreography
    if _choreography is None:
        _choreography = ChoreographyPattern()
    return _choreography
