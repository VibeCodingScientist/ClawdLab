"""Base classes and data structures for Agent Communication."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable
from uuid import uuid4


class AgentStatus(Enum):
    """Status of an agent."""

    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    PAUSED = "paused"
    UNHEALTHY = "unhealthy"
    TERMINATED = "terminated"


class MessageType(Enum):
    """Types of messages."""

    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    COMMAND = "command"
    BROADCAST = "broadcast"
    HEARTBEAT = "heartbeat"


class MessagePriority(Enum):
    """Message priority levels."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class ChannelType(Enum):
    """Types of communication channels."""

    DIRECT = "direct"
    TOPIC = "topic"
    BROADCAST = "broadcast"
    QUEUE = "queue"


class DeliveryStatus(Enum):
    """Message delivery status."""

    PENDING = "pending"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    EXPIRED = "expired"
    DEAD_LETTERED = "dead_lettered"


# ===========================================
# AGENT DATA CLASSES
# ===========================================


@dataclass
class AgentCapability:
    """A capability that an agent provides."""

    name: str
    description: str = ""
    version: str = "1.0"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInfo:
    """Information about a registered agent."""

    agent_id: str = field(default_factory=lambda: str(uuid4()))
    agent_type: str = ""
    name: str = ""
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    status: AgentStatus = AgentStatus.INITIALIZING
    metadata: dict[str, Any] = field(default_factory=dict)
    endpoint: str = ""  # Communication endpoint
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "metadata": self.metadata,
            "endpoint": self.endpoint,
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentInfo":
        return cls(
            agent_id=data.get("agent_id", str(uuid4())),
            agent_type=data.get("agent_type", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            capabilities=data.get("capabilities", []),
            status=AgentStatus(data.get("status", "initializing")),
            metadata=data.get("metadata", {}),
            endpoint=data.get("endpoint", ""),
            registered_at=(
                datetime.fromisoformat(data["registered_at"])
                if data.get("registered_at")
                else datetime.utcnow()
            ),
            last_heartbeat=(
                datetime.fromisoformat(data["last_heartbeat"])
                if data.get("last_heartbeat")
                else datetime.utcnow()
            ),
            version=data.get("version", "1.0"),
        )


@dataclass
class AgentMetrics:
    """Metrics for an agent."""

    agent_id: str
    messages_sent: int = 0
    messages_received: int = 0
    requests_handled: int = 0
    errors_count: int = 0
    avg_response_time_ms: float = 0.0
    uptime_seconds: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "requests_handled": self.requests_handled,
            "errors_count": self.errors_count,
            "avg_response_time_ms": self.avg_response_time_ms,
            "uptime_seconds": self.uptime_seconds,
            "last_updated": self.last_updated.isoformat(),
        }


# ===========================================
# MESSAGE DATA CLASSES
# ===========================================


@dataclass
class MessageHeader:
    """Header information for a message."""

    message_id: str = field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None  # For request-response tracking
    reply_to: str | None = None  # Channel for responses
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    priority: MessagePriority = MessagePriority.NORMAL
    retry_count: int = 0
    trace_id: str | None = None  # For distributed tracing

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "priority": self.priority.value,
            "retry_count": self.retry_count,
            "trace_id": self.trace_id,
        }


@dataclass
class Message:
    """A message in the agent communication system."""

    header: MessageHeader = field(default_factory=MessageHeader)
    message_type: MessageType = MessageType.EVENT
    sender_id: str = ""
    recipient_id: str | None = None  # None for broadcasts/topics
    channel: str = ""
    subject: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "header": self.header.to_dict(),
            "message_type": self.message_type.value,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "channel": self.channel,
            "subject": self.subject,
            "payload": self.payload,
            "delivery_status": self.delivery_status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        header_data = data.get("header", {})
        header = MessageHeader(
            message_id=header_data.get("message_id", str(uuid4())),
            correlation_id=header_data.get("correlation_id"),
            reply_to=header_data.get("reply_to"),
            timestamp=(
                datetime.fromisoformat(header_data["timestamp"])
                if header_data.get("timestamp")
                else datetime.utcnow()
            ),
            expires_at=(
                datetime.fromisoformat(header_data["expires_at"])
                if header_data.get("expires_at")
                else None
            ),
            priority=MessagePriority(header_data.get("priority", 2)),
            retry_count=header_data.get("retry_count", 0),
            trace_id=header_data.get("trace_id"),
        )

        return cls(
            header=header,
            message_type=MessageType(data.get("message_type", "event")),
            sender_id=data.get("sender_id", ""),
            recipient_id=data.get("recipient_id"),
            channel=data.get("channel", ""),
            subject=data.get("subject", ""),
            payload=data.get("payload", {}),
            delivery_status=DeliveryStatus(data.get("delivery_status", "pending")),
        )

    def create_response(
        self,
        sender_id: str,
        payload: dict[str, Any],
        success: bool = True,
    ) -> "Message":
        """Create a response message for this request."""
        return Message(
            header=MessageHeader(
                correlation_id=self.header.message_id,
                priority=self.header.priority,
                trace_id=self.header.trace_id,
            ),
            message_type=MessageType.RESPONSE,
            sender_id=sender_id,
            recipient_id=self.sender_id,
            channel=self.header.reply_to or f"agent.{self.sender_id}.inbox",
            subject=f"response.{self.subject}",
            payload={
                "success": success,
                "request_id": self.header.message_id,
                **payload,
            },
        )


@dataclass
class DeadLetter:
    """A message that failed delivery."""

    message: Message
    reason: str
    failed_at: datetime = field(default_factory=datetime.utcnow)
    original_channel: str = ""
    retry_attempts: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message.to_dict(),
            "reason": self.reason,
            "failed_at": self.failed_at.isoformat(),
            "original_channel": self.original_channel,
            "retry_attempts": self.retry_attempts,
        }


# ===========================================
# CHANNEL DATA CLASSES
# ===========================================


@dataclass
class Subscription:
    """A subscription to a channel."""

    subscription_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    channel: str = ""
    filter_pattern: str | None = None  # Optional message filter
    created_at: datetime = field(default_factory=datetime.utcnow)
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "agent_id": self.agent_id,
            "channel": self.channel,
            "filter_pattern": self.filter_pattern,
            "created_at": self.created_at.isoformat(),
            "active": self.active,
        }


@dataclass
class Channel:
    """A communication channel."""

    channel_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    channel_type: ChannelType = ChannelType.TOPIC
    description: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)
    subscriber_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "name": self.name,
            "channel_type": self.channel_type.value,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "subscriber_count": self.subscriber_count,
        }


# ===========================================
# PATTERN DATA CLASSES
# ===========================================


@dataclass
class RequestContext:
    """Context for a request-response interaction."""

    request_id: str
    sender_id: str
    recipient_id: str
    sent_at: datetime
    timeout_seconds: float
    callback: Callable[[Message], None] | None = None


@dataclass
class PipelineStage:
    """A stage in a processing pipeline."""

    stage_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    agent_type: str = ""  # Type of agent to handle this stage
    input_channel: str = ""
    output_channel: str = ""
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "name": self.name,
            "agent_type": self.agent_type,
            "input_channel": self.input_channel,
            "output_channel": self.output_channel,
            "config": self.config,
        }


@dataclass
class Pipeline:
    """A multi-stage processing pipeline."""

    pipeline_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    stages: list[PipelineStage] = field(default_factory=list)
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "name": self.name,
            "description": self.description,
            "stages": [s.to_dict() for s in self.stages],
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }


# ===========================================
# EVENT DATA CLASSES
# ===========================================


@dataclass
class AgentEvent:
    """An event related to agent lifecycle."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: str = ""  # registered, unregistered, status_changed, etc.
    agent_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


@dataclass
class SystemEvent:
    """A system-wide event."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: str = ""
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"  # info, warning, error, critical

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "severity": self.severity,
        }


__all__ = [
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
    # Message classes
    "MessageHeader",
    "Message",
    "DeadLetter",
    # Channel classes
    "Subscription",
    "Channel",
    # Pattern classes
    "RequestContext",
    "PipelineStage",
    "Pipeline",
    # Event classes
    "AgentEvent",
    "SystemEvent",
]
