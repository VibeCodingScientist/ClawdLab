"""Agent Communication Framework.

This module provides comprehensive agent communication capabilities:
- Agent registration and lifecycle management
- Message routing and delivery with priority queuing
- Multiple communication patterns (request-response, pub-sub, scatter-gather)
- Processing pipelines for multi-stage workflows
- Health monitoring and metrics tracking

The agent communication layer enables autonomous agents to coordinate
their research activities across the platform.
"""

from platform.agents.base import (
    # Enums
    AgentStatus,
    ChannelType,
    DeliveryStatus,
    MessagePriority,
    MessageType,
    # Agent classes
    AgentCapability,
    AgentEvent,
    AgentInfo,
    AgentMetrics,
    # Message classes
    DeadLetter,
    Message,
    MessageHeader,
    # Channel classes
    Channel,
    Subscription,
    # Pattern classes
    Pipeline,
    PipelineStage,
    RequestContext,
    # Event classes
    SystemEvent,
)
from platform.agents.broker import (
    MessageBroker,
    get_message_broker,
)
from platform.agents.config import (
    AGENT_TYPES,
    CAPABILITIES,
    CHANNEL_TYPES,
    MESSAGE_TYPES,
    PRIORITY_LEVELS,
    STANDARD_CHANNELS,
    AgentCommunicationSettings,
    get_settings,
)
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
from platform.agents.registry import (
    AgentRegistry,
    get_agent_registry,
)
from platform.agents.service import (
    AgentCommunicationService,
    CommunicationStats,
    get_agent_communication_service,
)

__all__ = [
    # Config
    "get_settings",
    "AgentCommunicationSettings",
    "AGENT_TYPES",
    "MESSAGE_TYPES",
    "CHANNEL_TYPES",
    "STANDARD_CHANNELS",
    "CAPABILITIES",
    "PRIORITY_LEVELS",
    # Enums
    "AgentStatus",
    "MessageType",
    "MessagePriority",
    "ChannelType",
    "DeliveryStatus",
    # Agent classes
    "AgentCapability",
    "AgentInfo",
    "AgentMetrics",
    "AgentEvent",
    # Message classes
    "MessageHeader",
    "Message",
    "DeadLetter",
    # Channel classes
    "Channel",
    "Subscription",
    # Pattern classes
    "RequestContext",
    "PipelineStage",
    "Pipeline",
    # Event classes
    "SystemEvent",
    # Registry
    "AgentRegistry",
    "get_agent_registry",
    # Broker
    "MessageBroker",
    "get_message_broker",
    # Patterns
    "RequestResponse",
    "PublishSubscribe",
    "ScatterGather",
    "Broadcast",
    "PipelinePattern",
    "ChoreographyPattern",
    "get_request_response",
    "get_pub_sub",
    "get_scatter_gather",
    "get_broadcast",
    "get_pipeline",
    "get_choreography",
    # Main service
    "AgentCommunicationService",
    "CommunicationStats",
    "get_agent_communication_service",
]
