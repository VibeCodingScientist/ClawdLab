"""Kafka client for event streaming."""

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine
from uuid import UUID, uuid4

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


def get_kafka_config() -> dict[str, Any]:
    """Get Kafka configuration from environment."""
    return {
        "bootstrap_servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "consumer_group": os.getenv("KAFKA_CONSUMER_GROUP", "asrp-services"),
    }


class UUIDEncoder(json.JSONEncoder):
    """JSON encoder that handles UUID objects."""

    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


@dataclass
class KafkaMessage:
    """Represents a Kafka message."""

    topic: str
    key: str | None
    value: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)
    partition: int | None = None
    offset: int | None = None
    timestamp: datetime | None = None


class KafkaProducer:
    """Async Kafka producer with retry logic."""

    def __init__(self, client_id: str = "asrp-producer"):
        self.client_id = client_id
        self._producer: AIOKafkaProducer | None = None
        self._config = get_kafka_config()

    async def start(self) -> None:
        """Start the producer."""
        if self._producer is None:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._config["bootstrap_servers"],
                client_id=self.client_id,
                value_serializer=lambda v: json.dumps(v, cls=UUIDEncoder).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=3,
                retry_backoff_ms=100,
            )
            await self._producer.start()
            logger.info("kafka_producer_started", client_id=self.client_id)

    async def stop(self) -> None:
        """Stop the producer."""
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
            logger.info("kafka_producer_stopped", client_id=self.client_id)

    async def send(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send a message to a topic."""
        if self._producer is None:
            await self.start()

        kafka_headers = [(k, v.encode("utf-8")) for k, v in (headers or {}).items()]

        await self._producer.send_and_wait(
            topic=topic,
            value=value,
            key=key,
            headers=kafka_headers,
        )
        logger.debug("kafka_message_sent", topic=topic, key=key)

    async def send_event(
        self,
        topic: str,
        event_type: str,
        data: dict[str, Any],
        source_service: str,
        correlation_id: UUID | None = None,
    ) -> None:
        """Send a standardized event message."""
        event = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "source_service": source_service,
            "correlation_id": str(correlation_id) if correlation_id else None,
            "data": data,
        }
        await self.send(topic, event, key=event_type)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()


class KafkaConsumer:
    """Async Kafka consumer with message handling."""

    def __init__(
        self,
        topics: list[str],
        group_id: str | None = None,
        client_id: str = "asrp-consumer",
    ):
        self.topics = topics
        self.client_id = client_id
        self._config = get_kafka_config()
        self.group_id = group_id or self._config["consumer_group"]
        self._consumer: AIOKafkaConsumer | None = None
        self._handlers: dict[str, Callable[[KafkaMessage], Coroutine[Any, Any, None]]] = {}
        self._running = False

    def register_handler(
        self,
        topic: str,
        handler: Callable[[KafkaMessage], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a handler for a specific topic."""
        self._handlers[topic] = handler
        logger.info("kafka_handler_registered", topic=topic)

    async def start(self) -> None:
        """Start the consumer."""
        if self._consumer is None:
            self._consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self._config["bootstrap_servers"],
                group_id=self.group_id,
                client_id=self.client_id,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                auto_offset_reset="earliest",
                enable_auto_commit=False,
            )
            await self._consumer.start()
            logger.info(
                "kafka_consumer_started",
                topics=self.topics,
                group_id=self.group_id,
            )

    async def stop(self) -> None:
        """Stop the consumer."""
        self._running = False
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None
            logger.info("kafka_consumer_stopped")

    async def consume(self) -> None:
        """Start consuming messages."""
        if self._consumer is None:
            await self.start()

        self._running = True
        try:
            async for msg in self._consumer:
                if not self._running:
                    break

                message = KafkaMessage(
                    topic=msg.topic,
                    key=msg.key,
                    value=msg.value,
                    headers={k: v.decode("utf-8") for k, v in msg.headers},
                    partition=msg.partition,
                    offset=msg.offset,
                    timestamp=datetime.fromtimestamp(msg.timestamp / 1000) if msg.timestamp else None,
                )

                handler = self._handlers.get(msg.topic)
                if handler:
                    try:
                        await handler(message)
                        await self._consumer.commit()
                    except Exception as e:
                        logger.error(
                            "kafka_message_handler_error",
                            topic=msg.topic,
                            error=str(e),
                        )
                else:
                    logger.warning("kafka_no_handler", topic=msg.topic)
                    await self._consumer.commit()
        except asyncio.CancelledError:
            logger.info("kafka_consumer_cancelled")
        finally:
            await self.stop()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()


class KafkaAdmin:
    """Kafka admin client for topic management."""

    def __init__(self):
        self._config = get_kafka_config()
        self._admin: AIOKafkaAdminClient | None = None

    async def start(self) -> None:
        """Start admin client."""
        if self._admin is None:
            self._admin = AIOKafkaAdminClient(
                bootstrap_servers=self._config["bootstrap_servers"],
            )
            await self._admin.start()
            logger.info("kafka_admin_started")

    async def stop(self) -> None:
        """Stop admin client."""
        if self._admin is not None:
            await self._admin.close()
            self._admin = None
            logger.info("kafka_admin_stopped")

    async def create_topics(self, topics: list[dict[str, Any]]) -> None:
        """Create multiple topics."""
        if self._admin is None:
            await self.start()

        new_topics = [
            NewTopic(
                name=t["name"],
                num_partitions=t.get("partitions", 6),
                replication_factor=t.get("replication_factor", 1),
            )
            for t in topics
        ]

        try:
            await self._admin.create_topics(new_topics)
            logger.info("kafka_topics_created", count=len(topics))
        except Exception as e:
            # Topics may already exist
            logger.warning("kafka_topic_creation_warning", error=str(e))

    async def list_topics(self) -> list[str]:
        """List all topics."""
        if self._admin is None:
            await self.start()

        metadata = await self._admin.list_topics()
        return list(metadata)

    async def delete_topics(self, topic_names: list[str]) -> None:
        """Delete topics."""
        if self._admin is None:
            await self.start()

        await self._admin.delete_topics(topic_names)
        logger.info("kafka_topics_deleted", topics=topic_names)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()


# Topic definitions for the platform
PLATFORM_TOPICS = [
    # Claim lifecycle events
    {"name": "claims.submitted", "partitions": 12},
    {"name": "claims.verification.requested", "partitions": 24},
    {"name": "claims.verification.completed", "partitions": 12},
    {"name": "claims.status.changed", "partitions": 6},
    # Domain-specific verification queues
    {"name": "verification.math", "partitions": 6},
    {"name": "verification.ml", "partitions": 12},
    {"name": "verification.compbio", "partitions": 12},
    {"name": "verification.materials", "partitions": 6},
    {"name": "verification.bioinfo", "partitions": 6},
    # Reputation events
    {"name": "reputation.transactions", "partitions": 6},
    {"name": "reputation.milestones", "partitions": 3},
    # Challenge events
    {"name": "challenges.created", "partitions": 3},
    {"name": "challenges.votes", "partitions": 3},
    {"name": "challenges.resolved", "partitions": 3},
    # Frontier events
    {"name": "frontiers.created", "partitions": 3},
    {"name": "frontiers.claimed", "partitions": 3},
    {"name": "frontiers.solved", "partitions": 3},
    # Notifications
    {"name": "notifications.outbound", "partitions": 12},
    # Knowledge graph
    {"name": "knowledge.entities.created", "partitions": 6},
    {"name": "knowledge.entities.updated", "partitions": 6},
    {"name": "knowledge.relationships.created", "partitions": 6},
    # Audit and provenance
    {"name": "audit.events", "partitions": 12},
    {"name": "provenance.records", "partitions": 6},
    # Compute jobs
    {"name": "compute.jobs.submitted", "partitions": 12},
    {"name": "compute.jobs.started", "partitions": 6},
    {"name": "compute.jobs.completed", "partitions": 12},
    {"name": "compute.jobs.failed", "partitions": 6},
]


async def initialize_topics() -> None:
    """Initialize all platform topics."""
    async with KafkaAdmin() as admin:
        await admin.create_topics(PLATFORM_TOPICS)


async def health_check() -> bool:
    """Check Kafka connectivity."""
    try:
        async with KafkaAdmin() as admin:
            await admin.list_topics()
        return True
    except Exception as e:
        logger.error("kafka_health_check_failed", error=str(e))
        return False
