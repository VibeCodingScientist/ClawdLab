"""Message Broker Service for agent communication."""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Coroutine

from platform.agents.base import (
    Channel,
    ChannelType,
    DeadLetter,
    DeliveryStatus,
    Message,
    MessageHeader,
    MessagePriority,
    MessageType,
    Subscription,
)
from platform.agents.config import STANDARD_CHANNELS, get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Type for message handlers
MessageHandler = Callable[[Message], Coroutine[Any, Any, None]]


class PriorityQueue:
    """Priority queue for messages."""

    def __init__(self, max_size: int = 10000):
        """Initialize priority queue."""
        self._queues: dict[int, asyncio.Queue] = {
            p.value: asyncio.Queue(maxsize=max_size // 5) for p in MessagePriority
        }
        self._size = 0
        self._max_size = max_size

    async def put(self, message: Message) -> None:
        """Add message to queue."""
        if self._size >= self._max_size:
            raise asyncio.QueueFull("Message queue is full")

        priority = message.header.priority.value
        await self._queues[priority].put(message)
        self._size += 1

    async def get(self, timeout: float | None = None) -> Message | None:
        """Get highest priority message."""
        # Try queues in priority order
        for priority in sorted(self._queues.keys()):
            queue = self._queues[priority]
            if not queue.empty():
                message = await queue.get()
                self._size -= 1
                return message

        # If all empty, wait on any
        if timeout:
            try:
                # Wait for any message with timeout
                for priority in sorted(self._queues.keys()):
                    try:
                        message = await asyncio.wait_for(
                            self._queues[priority].get(),
                            timeout=timeout / len(self._queues),
                        )
                        self._size -= 1
                        return message
                    except asyncio.TimeoutError:
                        continue
            except asyncio.TimeoutError:
                pass

        return None

    def size(self) -> int:
        """Get queue size."""
        return self._size

    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._size == 0


class MessageBroker:
    """
    Message broker for agent communication.

    Handles message routing, queuing, delivery, and dead letter management.
    Supports multiple channel types: direct, topic, broadcast, and queue.
    """

    def __init__(self):
        """Initialize message broker."""
        self._channels: dict[str, Channel] = {}
        self._subscriptions: dict[str, list[Subscription]] = defaultdict(list)
        self._agent_subscriptions: dict[str, list[str]] = defaultdict(list)
        self._handlers: dict[str, list[MessageHandler]] = defaultdict(list)
        self._queues: dict[str, PriorityQueue] = {}
        self._dead_letters: list[DeadLetter] = []
        self._pending_responses: dict[str, asyncio.Future] = {}
        self._message_history: list[Message] = []
        self._running = False
        self._worker_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the message broker."""
        self._running = True

        # Create standard channels
        for channel_name, config in STANDARD_CHANNELS.items():
            await self.create_channel(
                name=channel_name,
                channel_type=ChannelType(config["type"]),
                description=config["description"],
            )

        # Start worker task for queue processing
        self._worker_task = asyncio.create_task(self._process_queues())

        logger.info("message_broker_started")

    async def stop(self) -> None:
        """Stop the message broker."""
        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        # Cancel pending responses
        for future in self._pending_responses.values():
            if not future.done():
                future.cancel()

        logger.info("message_broker_stopped")

    async def create_channel(
        self,
        name: str,
        channel_type: ChannelType,
        description: str = "",
        created_by: str = "",
    ) -> Channel:
        """
        Create a communication channel.

        Args:
            name: Channel name
            channel_type: Type of channel
            description: Channel description
            created_by: Creator ID

        Returns:
            Created channel
        """
        if name in self._channels:
            return self._channels[name]

        if len(self._channels) >= settings.max_channels:
            raise ValueError(f"Maximum channels ({settings.max_channels}) reached")

        channel = Channel(
            name=name,
            channel_type=channel_type,
            description=description,
            created_by=created_by,
        )

        self._channels[name] = channel

        # Create queue for queue-type channels
        if channel_type == ChannelType.QUEUE:
            self._queues[name] = PriorityQueue(settings.default_queue_size)

        logger.info(
            "channel_created",
            channel=name,
            type=channel_type.value,
        )

        return channel

    async def delete_channel(self, name: str) -> bool:
        """Delete a channel."""
        if name not in self._channels:
            return False

        # Remove all subscriptions
        self._subscriptions.pop(name, None)
        self._handlers.pop(name, None)
        self._queues.pop(name, None)

        del self._channels[name]

        logger.info("channel_deleted", channel=name)
        return True

    async def subscribe(
        self,
        agent_id: str,
        channel: str,
        handler: MessageHandler | None = None,
        filter_pattern: str | None = None,
    ) -> Subscription:
        """
        Subscribe an agent to a channel.

        Args:
            agent_id: Subscribing agent ID
            channel: Channel name
            handler: Message handler callback
            filter_pattern: Optional message filter

        Returns:
            Subscription info
        """
        # Check channel exists
        if channel not in self._channels:
            # Auto-create topic channel
            await self.create_channel(channel, ChannelType.TOPIC)

        # Check subscription limit
        if len(self._agent_subscriptions[agent_id]) >= settings.max_subscriptions_per_agent:
            raise ValueError(
                f"Maximum subscriptions ({settings.max_subscriptions_per_agent}) reached"
            )

        subscription = Subscription(
            agent_id=agent_id,
            channel=channel,
            filter_pattern=filter_pattern,
        )

        self._subscriptions[channel].append(subscription)
        self._agent_subscriptions[agent_id].append(channel)

        if handler:
            self._handlers[channel].append(handler)

        # Update subscriber count
        self._channels[channel].subscriber_count = len(self._subscriptions[channel])

        logger.info(
            "agent_subscribed",
            agent_id=agent_id,
            channel=channel,
        )

        return subscription

    async def unsubscribe(
        self,
        agent_id: str,
        channel: str,
    ) -> bool:
        """
        Unsubscribe an agent from a channel.

        Args:
            agent_id: Agent ID
            channel: Channel name

        Returns:
            True if unsubscribed
        """
        subs = self._subscriptions.get(channel, [])
        self._subscriptions[channel] = [s for s in subs if s.agent_id != agent_id]

        if channel in self._agent_subscriptions[agent_id]:
            self._agent_subscriptions[agent_id].remove(channel)

        # Update subscriber count
        if channel in self._channels:
            self._channels[channel].subscriber_count = len(self._subscriptions[channel])

        logger.info(
            "agent_unsubscribed",
            agent_id=agent_id,
            channel=channel,
        )

        return True

    async def publish(
        self,
        message: Message,
    ) -> str:
        """
        Publish a message to a channel.

        Args:
            message: Message to publish

        Returns:
            Message ID
        """
        # Set message defaults
        if not message.header.message_id:
            message.header.message_id = str(MessageHeader().message_id)

        if not message.header.timestamp:
            message.header.timestamp = datetime.utcnow()

        # Set expiry if not set
        if not message.header.expires_at:
            message.header.expires_at = datetime.utcnow() + timedelta(
                seconds=settings.message_ttl_seconds
            )

        # Record message
        self._message_history.append(message)
        if len(self._message_history) > 10000:
            self._message_history = self._message_history[-10000:]

        # Route based on channel type
        channel = self._channels.get(message.channel)

        if not channel:
            # Create implicit topic channel
            channel = await self.create_channel(
                message.channel, ChannelType.TOPIC
            )

        if channel.channel_type == ChannelType.DIRECT:
            await self._deliver_direct(message)
        elif channel.channel_type == ChannelType.TOPIC:
            await self._deliver_topic(message)
        elif channel.channel_type == ChannelType.BROADCAST:
            await self._deliver_broadcast(message)
        elif channel.channel_type == ChannelType.QUEUE:
            await self._enqueue(message)

        logger.debug(
            "message_published",
            message_id=message.header.message_id,
            channel=message.channel,
            type=message.message_type.value,
        )

        return message.header.message_id

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
            subject: Message subject
            payload: Message payload
            timeout: Response timeout in seconds
            priority: Message priority

        Returns:
            Response message

        Raises:
            asyncio.TimeoutError: If no response within timeout
        """
        timeout = timeout or settings.request_timeout_seconds

        # Create request message
        reply_channel = f"agent.{sender_id}.inbox"
        message = Message(
            header=MessageHeader(
                reply_to=reply_channel,
                priority=priority,
            ),
            message_type=MessageType.REQUEST,
            sender_id=sender_id,
            recipient_id=recipient_id,
            channel=f"agent.{recipient_id}.inbox",
            subject=subject,
            payload=payload,
        )

        # Create future for response
        future: asyncio.Future[Message] = asyncio.Future()
        self._pending_responses[message.header.message_id] = future

        try:
            # Publish request
            await self.publish(message)

            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)
            return response

        finally:
            self._pending_responses.pop(message.header.message_id, None)

    async def send_response(
        self,
        request: Message,
        sender_id: str,
        payload: dict[str, Any],
        success: bool = True,
    ) -> str:
        """
        Send a response to a request.

        Args:
            request: Original request message
            sender_id: Responder agent ID
            payload: Response payload
            success: Whether request was successful

        Returns:
            Response message ID
        """
        response = request.create_response(sender_id, payload, success)
        return await self.publish(response)

    async def broadcast(
        self,
        sender_id: str,
        subject: str,
        payload: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """
        Broadcast a message to all agents.

        Args:
            sender_id: Sender agent ID
            subject: Message subject
            payload: Message payload
            priority: Message priority

        Returns:
            Message ID
        """
        message = Message(
            header=MessageHeader(priority=priority),
            message_type=MessageType.BROADCAST,
            sender_id=sender_id,
            channel="system.broadcast",
            subject=subject,
            payload=payload,
        )

        # Ensure broadcast channel exists
        if "system.broadcast" not in self._channels:
            await self.create_channel(
                "system.broadcast",
                ChannelType.BROADCAST,
                "System-wide broadcast channel",
            )

        return await self.publish(message)

    async def get_channel(self, name: str) -> Channel | None:
        """Get channel info."""
        return self._channels.get(name)

    async def list_channels(self) -> list[Channel]:
        """List all channels."""
        return list(self._channels.values())

    async def get_subscriptions(self, agent_id: str) -> list[Subscription]:
        """Get all subscriptions for an agent."""
        channels = self._agent_subscriptions.get(agent_id, [])
        subscriptions = []

        for channel in channels:
            for sub in self._subscriptions.get(channel, []):
                if sub.agent_id == agent_id:
                    subscriptions.append(sub)

        return subscriptions

    async def get_dead_letters(
        self,
        limit: int = 100,
        since: datetime | None = None,
    ) -> list[DeadLetter]:
        """Get dead letters."""
        letters = self._dead_letters

        if since:
            letters = [dl for dl in letters if dl.failed_at >= since]

        return letters[-limit:]

    async def retry_dead_letter(self, message_id: str) -> bool:
        """Retry a dead-lettered message."""
        for i, dl in enumerate(self._dead_letters):
            if dl.message.header.message_id == message_id:
                message = dl.message
                message.header.retry_count += 1
                message.delivery_status = DeliveryStatus.PENDING

                # Remove from dead letters
                self._dead_letters.pop(i)

                # Re-publish
                await self.publish(message)
                return True

        return False

    def get_stats(self) -> dict[str, Any]:
        """Get broker statistics."""
        return {
            "total_channels": len(self._channels),
            "total_subscriptions": sum(
                len(subs) for subs in self._subscriptions.values()
            ),
            "total_messages": len(self._message_history),
            "dead_letters": len(self._dead_letters),
            "pending_responses": len(self._pending_responses),
            "queue_sizes": {
                name: queue.size() for name, queue in self._queues.items()
            },
        }

    async def _deliver_direct(self, message: Message) -> None:
        """Deliver message directly to recipient."""
        if not message.recipient_id:
            await self._dead_letter(message, "No recipient specified for direct message")
            return

        # Get handlers for recipient's inbox
        inbox_channel = f"agent.{message.recipient_id}.inbox"
        handlers = self._handlers.get(inbox_channel, [])

        if not handlers:
            # Check if it's a response to a pending request
            if message.message_type == MessageType.RESPONSE:
                correlation_id = message.header.correlation_id
                if correlation_id and correlation_id in self._pending_responses:
                    future = self._pending_responses[correlation_id]
                    if not future.done():
                        future.set_result(message)
                        message.delivery_status = DeliveryStatus.DELIVERED
                        return

            await self._dead_letter(message, f"No handlers for {inbox_channel}")
            return

        await self._invoke_handlers(handlers, message)

    async def _deliver_topic(self, message: Message) -> None:
        """Deliver message to all topic subscribers."""
        subscriptions = self._subscriptions.get(message.channel, [])

        if not subscriptions:
            # No subscribers - might be normal for some topics
            message.delivery_status = DeliveryStatus.DELIVERED
            return

        handlers = self._handlers.get(message.channel, [])
        await self._invoke_handlers(handlers, message)

    async def _deliver_broadcast(self, message: Message) -> None:
        """Deliver message to all subscribers of broadcast channel."""
        # Broadcast channels deliver to all registered handlers
        for channel, handlers in self._handlers.items():
            if handlers:
                await self._invoke_handlers(handlers, message)

        message.delivery_status = DeliveryStatus.DELIVERED

    async def _enqueue(self, message: Message) -> None:
        """Add message to queue for load-balanced delivery."""
        queue = self._queues.get(message.channel)
        if not queue:
            await self._dead_letter(message, f"Queue not found: {message.channel}")
            return

        try:
            await queue.put(message)
        except asyncio.QueueFull:
            await self._dead_letter(message, "Queue full")

    async def _process_queues(self) -> None:
        """Background task to process queued messages."""
        while self._running:
            try:
                for channel, queue in self._queues.items():
                    if queue.empty():
                        continue

                    message = await queue.get(timeout=0.1)
                    if message:
                        handlers = self._handlers.get(channel, [])
                        if handlers:
                            # Pick one handler (round-robin through handlers)
                            handler = handlers[0]
                            try:
                                await handler(message)
                                message.delivery_status = DeliveryStatus.DELIVERED
                            except Exception as e:
                                await self._handle_delivery_failure(message, str(e))
                        else:
                            await self._dead_letter(message, "No handlers available")

                await asyncio.sleep(0.01)  # Small delay between processing

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("queue_processing_error", error=str(e))

    async def _invoke_handlers(
        self,
        handlers: list[MessageHandler],
        message: Message,
    ) -> None:
        """Invoke message handlers."""
        for handler in handlers:
            try:
                await handler(message)
                message.delivery_status = DeliveryStatus.DELIVERED
            except Exception as e:
                logger.exception(
                    "handler_error",
                    message_id=message.header.message_id,
                    error=str(e),
                )
                await self._handle_delivery_failure(message, str(e))

    async def _handle_delivery_failure(
        self,
        message: Message,
        error: str,
    ) -> None:
        """Handle message delivery failure."""
        message.header.retry_count += 1

        if message.header.retry_count < settings.max_retries:
            # Retry after delay
            await asyncio.sleep(settings.retry_delay_seconds)
            await self.publish(message)
        else:
            await self._dead_letter(message, f"Max retries exceeded: {error}")

    async def _dead_letter(self, message: Message, reason: str) -> None:
        """Move message to dead letter queue."""
        if not settings.enable_dead_letter:
            return

        message.delivery_status = DeliveryStatus.DEAD_LETTERED

        dead_letter = DeadLetter(
            message=message,
            reason=reason,
            original_channel=message.channel,
            retry_attempts=message.header.retry_count,
        )

        self._dead_letters.append(dead_letter)

        # Trim old dead letters
        cutoff = datetime.utcnow() - timedelta(hours=settings.dead_letter_retention_hours)
        self._dead_letters = [dl for dl in self._dead_letters if dl.failed_at >= cutoff]

        logger.warning(
            "message_dead_lettered",
            message_id=message.header.message_id,
            reason=reason,
        )


# Singleton instance
_broker_instance: MessageBroker | None = None


def get_message_broker() -> MessageBroker:
    """Get singleton MessageBroker instance."""
    global _broker_instance
    if _broker_instance is None:
        _broker_instance = MessageBroker()
    return _broker_instance
