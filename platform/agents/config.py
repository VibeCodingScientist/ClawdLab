"""Configuration for Agent Communication Framework."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class AgentCommunicationSettings(BaseSettings):
    """Settings for agent communication."""

    model_config = {"env_prefix": "AGENT_COMM_", "case_sensitive": False}

    # Message Broker Settings
    broker_type: str = Field(
        default="memory",
        description="Message broker type (memory, redis, kafka)",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/2",
        description="Redis URL for message broker",
    )
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers",
    )

    # Queue Settings
    default_queue_size: int = Field(
        default=10000,
        description="Default message queue size",
    )
    message_ttl_seconds: int = Field(
        default=3600,
        description="Message time-to-live in seconds",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum message delivery retries",
    )
    retry_delay_seconds: int = Field(
        default=5,
        description="Delay between retries",
    )

    # Agent Registry Settings
    heartbeat_interval_seconds: int = Field(
        default=30,
        description="Agent heartbeat interval",
    )
    agent_timeout_seconds: int = Field(
        default=90,
        description="Agent timeout before marking unhealthy",
    )
    max_agents: int = Field(
        default=1000,
        description="Maximum registered agents",
    )

    # Communication Settings
    request_timeout_seconds: int = Field(
        default=60,
        description="Request-response timeout",
    )
    broadcast_timeout_seconds: int = Field(
        default=30,
        description="Broadcast timeout",
    )
    max_message_size_bytes: int = Field(
        default=10_000_000,  # 10MB
        description="Maximum message size",
    )

    # Channel Settings
    max_channels: int = Field(
        default=100,
        description="Maximum number of channels",
    )
    max_subscriptions_per_agent: int = Field(
        default=50,
        description="Maximum subscriptions per agent",
    )

    # Dead Letter Settings
    enable_dead_letter: bool = Field(
        default=True,
        description="Enable dead letter queue",
    )
    dead_letter_retention_hours: int = Field(
        default=72,
        description="Dead letter retention period",
    )


@lru_cache
def get_settings() -> AgentCommunicationSettings:
    """Get cached agent communication settings."""
    return AgentCommunicationSettings()


# Agent Types
AGENT_TYPES = {
    "research": {
        "name": "Research Agent",
        "description": "Conducts research and generates hypotheses",
        "capabilities": ["research", "hypothesis_generation", "literature_review"],
    },
    "verification": {
        "name": "Verification Agent",
        "description": "Verifies claims using verification engines",
        "capabilities": ["verification", "proof_checking", "validation"],
    },
    "math": {
        "name": "Mathematics Agent",
        "description": "Specializes in mathematical proofs and analysis",
        "capabilities": ["proof_generation", "theorem_proving", "symbolic_computation"],
    },
    "ml": {
        "name": "ML/AI Agent",
        "description": "Handles machine learning experiments",
        "capabilities": ["experiment_design", "model_training", "benchmark_evaluation"],
    },
    "compbio": {
        "name": "Computational Biology Agent",
        "description": "Specializes in protein and molecular analysis",
        "capabilities": ["protein_analysis", "structure_prediction", "molecular_design"],
    },
    "materials": {
        "name": "Materials Science Agent",
        "description": "Analyzes and designs materials",
        "capabilities": ["crystal_analysis", "stability_prediction", "property_calculation"],
    },
    "bioinfo": {
        "name": "Bioinformatics Agent",
        "description": "Handles genomic and transcriptomic analysis",
        "capabilities": ["sequence_analysis", "pipeline_execution", "statistical_validation"],
    },
    "knowledge": {
        "name": "Knowledge Agent",
        "description": "Manages knowledge base operations",
        "capabilities": ["knowledge_storage", "semantic_search", "citation_tracking"],
    },
    "orchestrator": {
        "name": "Orchestrator Agent",
        "description": "Coordinates multi-agent workflows",
        "capabilities": ["workflow_management", "task_scheduling", "coordination"],
    },
    "reviewer": {
        "name": "Reviewer Agent",
        "description": "Reviews and critiques research outputs",
        "capabilities": ["peer_review", "quality_assessment", "feedback_generation"],
    },
}

# Message Types
MESSAGE_TYPES = {
    "request": {
        "name": "Request",
        "description": "Request expecting a response",
        "requires_response": True,
    },
    "response": {
        "name": "Response",
        "description": "Response to a request",
        "requires_response": False,
    },
    "event": {
        "name": "Event",
        "description": "Event notification",
        "requires_response": False,
    },
    "command": {
        "name": "Command",
        "description": "Command to execute",
        "requires_response": False,
    },
    "broadcast": {
        "name": "Broadcast",
        "description": "Broadcast to all subscribers",
        "requires_response": False,
    },
    "heartbeat": {
        "name": "Heartbeat",
        "description": "Agent health heartbeat",
        "requires_response": False,
    },
}

# Channel Types
CHANNEL_TYPES = {
    "direct": {
        "name": "Direct",
        "description": "Point-to-point communication",
        "max_subscribers": 1,
    },
    "topic": {
        "name": "Topic",
        "description": "Publish-subscribe topic",
        "max_subscribers": 1000,
    },
    "broadcast": {
        "name": "Broadcast",
        "description": "Broadcast to all agents",
        "max_subscribers": -1,  # Unlimited
    },
    "queue": {
        "name": "Queue",
        "description": "Load-balanced queue",
        "max_subscribers": 100,
    },
}

# Standard Channels
STANDARD_CHANNELS = {
    "system.events": {
        "type": "topic",
        "description": "System-wide events",
    },
    "system.commands": {
        "type": "topic",
        "description": "System commands",
    },
    "research.requests": {
        "type": "queue",
        "description": "Research task requests",
    },
    "verification.requests": {
        "type": "queue",
        "description": "Verification requests",
    },
    "verification.results": {
        "type": "topic",
        "description": "Verification results",
    },
    "knowledge.updates": {
        "type": "topic",
        "description": "Knowledge base updates",
    },
    "workflow.events": {
        "type": "topic",
        "description": "Workflow state changes",
    },
}

# Agent Capabilities
CAPABILITIES = [
    "research",
    "hypothesis_generation",
    "literature_review",
    "verification",
    "proof_checking",
    "validation",
    "proof_generation",
    "theorem_proving",
    "symbolic_computation",
    "experiment_design",
    "model_training",
    "benchmark_evaluation",
    "protein_analysis",
    "structure_prediction",
    "molecular_design",
    "crystal_analysis",
    "stability_prediction",
    "property_calculation",
    "sequence_analysis",
    "pipeline_execution",
    "statistical_validation",
    "knowledge_storage",
    "semantic_search",
    "citation_tracking",
    "workflow_management",
    "task_scheduling",
    "coordination",
    "peer_review",
    "quality_assessment",
    "feedback_generation",
]

# Priority Levels
PRIORITY_LEVELS = {
    "critical": {"value": 0, "description": "Critical priority - immediate processing"},
    "high": {"value": 1, "description": "High priority"},
    "normal": {"value": 2, "description": "Normal priority"},
    "low": {"value": 3, "description": "Low priority"},
    "background": {"value": 4, "description": "Background processing"},
}
