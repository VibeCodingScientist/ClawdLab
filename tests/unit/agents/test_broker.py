"""Unit tests for MessageBroker service."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest


def _utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)

from platform.agents.broker import MessageBroker, PriorityQueue
from platform.agents.base import (
    Channel,
    ChannelType,
    DeliveryStatus,
    Message,
    MessageHeader,
    MessagePriority,
    MessageType,
)


class TestPriorityQueue:
    """Tests for PriorityQueue class."""

    @pytest.fixture
    def queue(self) -> PriorityQueue:
        """Create a priority queue instance."""
        return PriorityQueue(max_size=100)

    @pytest.mark.asyncio
    async def test_put_and_get_single_message(self, queue: PriorityQueue):
        """Test putting and getting a single message."""
        message = Message(
            header=MessageHeader(priority=MessagePriority.NORMAL),
            sender_id="sender-1",
            channel="test",
        )

        await queue.put(message)
        assert queue.size() == 1

        retrieved = await queue.get()
        assert retrieved is not None
        assert retrieved.sender_id == "sender-1"
        assert queue.size() == 0

    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue: PriorityQueue):
        """Test that messages are retrieved in priority order."""
        # Add messages with different priorities
        low = Message(
            header=MessageHeader(priority=MessagePriority.LOW),
            sender_id="low",
            channel="test",
        )
        normal = Message(
            header=MessageHeader(priority=MessagePriority.NORMAL),
            sender_id="normal",
            channel="test",
        )
        critical = Message(
            header=MessageHeader(priority=MessagePriority.CRITICAL),
            sender_id="critical",
            channel="test",
        )

        # Add in reverse priority order
        await queue.put(low)
        await queue.put(normal)
        await queue.put(critical)

        # Should retrieve in priority order (critical first)
        msg1 = await queue.get()
        assert msg1.sender_id == "critical"

        msg2 = await queue.get()
        assert msg2.sender_id == "normal"

        msg3 = await queue.get()
        assert msg3.sender_id == "low"

    @pytest.mark.asyncio
    async def test_queue_full_raises(self, queue: PriorityQueue):
        """Test that putting to a full queue raises QueueFull."""
        queue._max_size = 2  # Override max size for testing

        msg1 = Message(
            header=MessageHeader(priority=MessagePriority.NORMAL),
            sender_id="msg1",
            channel="test",
        )
        msg2 = Message(
            header=MessageHeader(priority=MessagePriority.NORMAL),
            sender_id="msg2",
            channel="test",
        )
        msg3 = Message(
            header=MessageHeader(priority=MessagePriority.NORMAL),
            sender_id="msg3",
            channel="test",
        )

        await queue.put(msg1)
        await queue.put(msg2)

        with pytest.raises(asyncio.QueueFull):
            await queue.put(msg3)

    @pytest.mark.asyncio
    async def test_empty_check(self, queue: PriorityQueue):
        """Test empty check."""
        assert queue.empty() is True

        await queue.put(
            Message(
                header=MessageHeader(priority=MessagePriority.NORMAL),
                sender_id="test",
                channel="test",
            )
        )
        assert queue.empty() is False

        await queue.get()
        assert queue.empty() is True

    @pytest.mark.asyncio
    async def test_get_returns_none_when_empty(self, queue: PriorityQueue):
        """Test that get returns None on empty queue without timeout."""
        result = await queue.get()
        assert result is None


class TestMessageBroker:
    """Tests for MessageBroker class."""

    @pytest.fixture
    def broker(self) -> MessageBroker:
        """Create a message broker instance."""
        return MessageBroker()

    @pytest.fixture
    async def started_broker(self, broker: MessageBroker) -> MessageBroker:
        """Create and start a broker instance."""
        # Start without actually running the queue processor
        with patch.object(broker, '_process_queues', new_callable=AsyncMock):
            await broker.start()
        yield broker
        await broker.stop()

    # ===================================
    # CHANNEL TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_create_channel_success(self, broker: MessageBroker):
        """Test successful channel creation."""
        channel = await broker.create_channel(
            name="test-channel",
            channel_type=ChannelType.TOPIC,
            description="A test channel",
            created_by="admin",
        )

        assert channel is not None
        assert channel.name == "test-channel"
        assert channel.channel_type == ChannelType.TOPIC
        assert channel.description == "A test channel"
        assert channel.created_by == "admin"

    @pytest.mark.asyncio
    async def test_create_channel_returns_existing(self, broker: MessageBroker):
        """Test that creating duplicate channel returns existing one."""
        channel1 = await broker.create_channel(
            name="test-channel",
            channel_type=ChannelType.TOPIC,
        )
        channel2 = await broker.create_channel(
            name="test-channel",
            channel_type=ChannelType.DIRECT,
        )

        # Should return the same channel
        assert channel1.channel_id == channel2.channel_id
        assert channel2.channel_type == ChannelType.TOPIC  # Original type preserved

    @pytest.mark.asyncio
    async def test_create_channel_max_exceeded(self, broker: MessageBroker):
        """Test that max channels limit is enforced."""
        with patch('platform.agents.broker.settings') as mock_settings:
            mock_settings.max_channels = 2
            mock_settings.default_queue_size = 100

            await broker.create_channel("channel-1", ChannelType.TOPIC)
            await broker.create_channel("channel-2", ChannelType.TOPIC)

            with pytest.raises(ValueError, match="Maximum channels"):
                await broker.create_channel("channel-3", ChannelType.TOPIC)

    @pytest.mark.asyncio
    async def test_create_queue_channel_creates_priority_queue(
        self, broker: MessageBroker
    ):
        """Test that creating a queue channel creates a priority queue."""
        channel = await broker.create_channel(
            name="test-queue",
            channel_type=ChannelType.QUEUE,
        )

        assert "test-queue" in broker._queues
        assert isinstance(broker._queues["test-queue"], PriorityQueue)

    @pytest.mark.asyncio
    async def test_delete_channel_success(self, broker: MessageBroker):
        """Test successful channel deletion."""
        await broker.create_channel("test-channel", ChannelType.TOPIC)

        result = await broker.delete_channel("test-channel")
        assert result is True

        channel = await broker.get_channel("test-channel")
        assert channel is None

    @pytest.mark.asyncio
    async def test_delete_channel_not_found(self, broker: MessageBroker):
        """Test deleting non-existent channel."""
        result = await broker.delete_channel("non-existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_channel_removes_subscriptions(self, broker: MessageBroker):
        """Test that deleting channel removes subscriptions."""
        await broker.create_channel("test-channel", ChannelType.TOPIC)
        await broker.subscribe("agent-1", "test-channel")

        await broker.delete_channel("test-channel")

        assert "test-channel" not in broker._subscriptions

    @pytest.mark.asyncio
    async def test_get_channel(self, broker: MessageBroker):
        """Test getting channel info."""
        await broker.create_channel(
            name="test-channel",
            channel_type=ChannelType.TOPIC,
            description="Test",
        )

        channel = await broker.get_channel("test-channel")
        assert channel is not None
        assert channel.name == "test-channel"

    @pytest.mark.asyncio
    async def test_get_channel_not_found(self, broker: MessageBroker):
        """Test getting non-existent channel."""
        channel = await broker.get_channel("non-existent")
        assert channel is None

    @pytest.mark.asyncio
    async def test_list_channels(self, broker: MessageBroker):
        """Test listing all channels."""
        await broker.create_channel("channel-1", ChannelType.TOPIC)
        await broker.create_channel("channel-2", ChannelType.DIRECT)

        channels = await broker.list_channels()
        assert len(channels) == 2

    # ===================================
    # SUBSCRIPTION TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_subscribe_success(self, broker: MessageBroker):
        """Test successful subscription."""
        await broker.create_channel("test-channel", ChannelType.TOPIC)

        subscription = await broker.subscribe("agent-1", "test-channel")

        assert subscription is not None
        assert subscription.agent_id == "agent-1"
        assert subscription.channel == "test-channel"

    @pytest.mark.asyncio
    async def test_subscribe_auto_creates_topic_channel(self, broker: MessageBroker):
        """Test that subscribing to non-existent channel creates topic channel."""
        subscription = await broker.subscribe("agent-1", "new-channel")

        assert subscription is not None
        channel = await broker.get_channel("new-channel")
        assert channel is not None
        assert channel.channel_type == ChannelType.TOPIC

    @pytest.mark.asyncio
    async def test_subscribe_with_handler(self, broker: MessageBroker):
        """Test subscription with message handler."""
        handler = AsyncMock()

        await broker.subscribe("agent-1", "test-channel", handler=handler)

        assert handler in broker._handlers["test-channel"]

    @pytest.mark.asyncio
    async def test_subscribe_with_filter(self, broker: MessageBroker):
        """Test subscription with filter pattern."""
        subscription = await broker.subscribe(
            "agent-1",
            "test-channel",
            filter_pattern="event.*",
        )

        assert subscription.filter_pattern == "event.*"

    @pytest.mark.asyncio
    async def test_subscribe_updates_subscriber_count(self, broker: MessageBroker):
        """Test that subscription updates channel subscriber count."""
        await broker.create_channel("test-channel", ChannelType.TOPIC)

        await broker.subscribe("agent-1", "test-channel")
        await broker.subscribe("agent-2", "test-channel")

        channel = await broker.get_channel("test-channel")
        assert channel.subscriber_count == 2

    @pytest.mark.asyncio
    async def test_subscribe_max_subscriptions_exceeded(self, broker: MessageBroker):
        """Test that max subscriptions per agent is enforced."""
        with patch('platform.agents.broker.settings') as mock_settings:
            mock_settings.max_subscriptions_per_agent = 2

            await broker.subscribe("agent-1", "channel-1")
            await broker.subscribe("agent-1", "channel-2")

            with pytest.raises(ValueError, match="Maximum subscriptions"):
                await broker.subscribe("agent-1", "channel-3")

    @pytest.mark.asyncio
    async def test_unsubscribe_success(self, broker: MessageBroker):
        """Test successful unsubscription."""
        await broker.subscribe("agent-1", "test-channel")

        result = await broker.unsubscribe("agent-1", "test-channel")
        assert result is True

        subscriptions = await broker.get_subscriptions("agent-1")
        assert len(subscriptions) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_updates_subscriber_count(self, broker: MessageBroker):
        """Test that unsubscription updates channel subscriber count."""
        await broker.create_channel("test-channel", ChannelType.TOPIC)
        await broker.subscribe("agent-1", "test-channel")
        await broker.subscribe("agent-2", "test-channel")

        await broker.unsubscribe("agent-1", "test-channel")

        channel = await broker.get_channel("test-channel")
        assert channel.subscriber_count == 1

    @pytest.mark.asyncio
    async def test_get_subscriptions(self, broker: MessageBroker):
        """Test getting subscriptions for an agent."""
        await broker.subscribe("agent-1", "channel-1")
        await broker.subscribe("agent-1", "channel-2")
        await broker.subscribe("agent-2", "channel-1")

        subs = await broker.get_subscriptions("agent-1")
        assert len(subs) == 2

        channels = [s.channel for s in subs]
        assert "channel-1" in channels
        assert "channel-2" in channels

    # ===================================
    # PUBLISH TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_publish_sets_defaults(self, broker: MessageBroker):
        """Test that publish sets message defaults."""
        message = Message(
            message_type=MessageType.EVENT,
            sender_id="sender-1",
            channel="test-channel",
            payload={"data": "test"},
        )

        await broker.publish(message)

        assert message.header.message_id is not None
        assert message.header.timestamp is not None
        assert message.header.expires_at is not None

    @pytest.mark.asyncio
    async def test_publish_records_message_history(self, broker: MessageBroker):
        """Test that publish records message in history."""
        message = Message(
            message_type=MessageType.EVENT,
            sender_id="sender-1",
            channel="test-channel",
        )

        await broker.publish(message)

        assert len(broker._message_history) == 1
        assert broker._message_history[0].sender_id == "sender-1"

    @pytest.mark.asyncio
    async def test_publish_trims_message_history(self, broker: MessageBroker):
        """Test that message history is trimmed at limit."""
        for i in range(10010):
            message = Message(
                message_type=MessageType.EVENT,
                sender_id=f"sender-{i}",
                channel="test-channel",
            )
            await broker.publish(message)

        assert len(broker._message_history) == 10000

    @pytest.mark.asyncio
    async def test_publish_auto_creates_topic_channel(self, broker: MessageBroker):
        """Test that publishing to non-existent channel creates topic channel."""
        message = Message(
            message_type=MessageType.EVENT,
            sender_id="sender-1",
            channel="new-channel",
        )

        await broker.publish(message)

        channel = await broker.get_channel("new-channel")
        assert channel is not None
        assert channel.channel_type == ChannelType.TOPIC

    @pytest.mark.asyncio
    async def test_publish_returns_message_id(self, broker: MessageBroker):
        """Test that publish returns message ID."""
        message = Message(
            message_type=MessageType.EVENT,
            sender_id="sender-1",
            channel="test-channel",
        )

        message_id = await broker.publish(message)

        assert message_id is not None
        assert message_id == message.header.message_id

    # ===================================
    # DIRECT DELIVERY TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_deliver_direct_to_handler(self, broker: MessageBroker):
        """Test direct message delivery to handler."""
        handler = AsyncMock()

        # Set up recipient's inbox
        inbox_channel = "agent.recipient-1.inbox"
        await broker.create_channel(inbox_channel, ChannelType.DIRECT)
        await broker.subscribe("recipient-1", inbox_channel, handler=handler)

        message = Message(
            message_type=MessageType.REQUEST,
            sender_id="sender-1",
            recipient_id="recipient-1",
            channel=inbox_channel,
            payload={"data": "test"},
        )

        await broker._deliver_direct(message)

        handler.assert_called_once()
        call_args = handler.call_args[0]
        assert call_args[0].sender_id == "sender-1"

    @pytest.mark.asyncio
    async def test_deliver_direct_no_recipient_dead_letters(self, broker: MessageBroker):
        """Test that direct message without recipient goes to dead letter."""
        message = Message(
            message_type=MessageType.REQUEST,
            sender_id="sender-1",
            recipient_id=None,  # No recipient
            channel="some-channel",
        )

        await broker._deliver_direct(message)

        assert len(broker._dead_letters) == 1
        assert "No recipient" in broker._dead_letters[0].reason

    @pytest.mark.asyncio
    async def test_deliver_direct_response_resolves_pending(self, broker: MessageBroker):
        """Test that response message resolves pending request."""
        # Set up pending response future
        request_id = "request-123"
        future: asyncio.Future = asyncio.Future()
        broker._pending_responses[request_id] = future

        response = Message(
            header=MessageHeader(correlation_id=request_id),
            message_type=MessageType.RESPONSE,
            sender_id="responder-1",
            recipient_id="requester-1",
            channel="agent.requester-1.inbox",
            payload={"result": "success"},
        )

        await broker._deliver_direct(response)

        assert future.done()
        result = future.result()
        assert result.sender_id == "responder-1"

    # ===================================
    # TOPIC DELIVERY TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_deliver_topic_to_subscribers(self, broker: MessageBroker):
        """Test topic message delivery to subscribers."""
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        await broker.create_channel("test-topic", ChannelType.TOPIC)
        await broker.subscribe("agent-1", "test-topic", handler=handler1)
        await broker.subscribe("agent-2", "test-topic", handler=handler2)

        message = Message(
            message_type=MessageType.EVENT,
            sender_id="publisher-1",
            channel="test-topic",
            payload={"event": "test"},
        )

        await broker._deliver_topic(message)

        handler1.assert_called_once()
        handler2.assert_called_once()

    @pytest.mark.asyncio
    async def test_deliver_topic_no_subscribers_succeeds(self, broker: MessageBroker):
        """Test that topic delivery with no subscribers succeeds."""
        await broker.create_channel("empty-topic", ChannelType.TOPIC)

        message = Message(
            message_type=MessageType.EVENT,
            sender_id="publisher-1",
            channel="empty-topic",
        )

        await broker._deliver_topic(message)

        assert message.delivery_status == DeliveryStatus.DELIVERED

    # ===================================
    # BROADCAST DELIVERY TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_deliver_broadcast_to_all_handlers(self, broker: MessageBroker):
        """Test broadcast delivery to all handlers."""
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        await broker.create_channel("channel-1", ChannelType.TOPIC)
        await broker.create_channel("channel-2", ChannelType.TOPIC)
        await broker.subscribe("agent-1", "channel-1", handler=handler1)
        await broker.subscribe("agent-2", "channel-2", handler=handler2)

        message = Message(
            message_type=MessageType.BROADCAST,
            sender_id="broadcaster-1",
            channel="system.broadcast",
        )

        await broker._deliver_broadcast(message)

        handler1.assert_called()
        handler2.assert_called()
        assert message.delivery_status == DeliveryStatus.DELIVERED

    # ===================================
    # QUEUE DELIVERY TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_enqueue_message(self, broker: MessageBroker):
        """Test enqueueing a message."""
        await broker.create_channel("test-queue", ChannelType.QUEUE)

        message = Message(
            message_type=MessageType.REQUEST,
            sender_id="sender-1",
            channel="test-queue",
        )

        await broker._enqueue(message)

        assert broker._queues["test-queue"].size() == 1

    @pytest.mark.asyncio
    async def test_enqueue_queue_not_found_dead_letters(self, broker: MessageBroker):
        """Test that enqueueing to non-existent queue dead letters message."""
        message = Message(
            message_type=MessageType.REQUEST,
            sender_id="sender-1",
            channel="non-existent-queue",
        )

        await broker._enqueue(message)

        assert len(broker._dead_letters) == 1
        assert "Queue not found" in broker._dead_letters[0].reason

    # ===================================
    # REQUEST-RESPONSE TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_send_request_creates_message(self, broker: MessageBroker):
        """Test that send_request creates proper request message."""
        # Mock the publish to capture the message
        original_publish = broker.publish
        captured_message = None

        async def capture_publish(msg):
            nonlocal captured_message
            captured_message = msg
            return msg.header.message_id

        broker.publish = capture_publish

        # Start the request but don't wait (will timeout)
        with pytest.raises(asyncio.TimeoutError):
            await broker.send_request(
                sender_id="requester-1",
                recipient_id="responder-1",
                subject="test-request",
                payload={"data": "test"},
                timeout=0.01,
            )

        assert captured_message is not None
        assert captured_message.message_type == MessageType.REQUEST
        assert captured_message.sender_id == "requester-1"
        assert captured_message.recipient_id == "responder-1"
        assert captured_message.subject == "test-request"

    @pytest.mark.asyncio
    async def test_send_request_waits_for_response(self, broker: MessageBroker):
        """Test that send_request waits for and returns response."""
        # Mock publish to simulate immediate response
        async def mock_publish(msg):
            if msg.message_type == MessageType.REQUEST:
                # Simulate response
                if msg.header.message_id in broker._pending_responses:
                    response = Message(
                        message_type=MessageType.RESPONSE,
                        sender_id="responder-1",
                        recipient_id="requester-1",
                        payload={"result": "success"},
                    )
                    future = broker._pending_responses[msg.header.message_id]
                    future.set_result(response)
            return msg.header.message_id

        broker.publish = mock_publish

        response = await broker.send_request(
            sender_id="requester-1",
            recipient_id="responder-1",
            subject="test",
            payload={},
            timeout=1.0,
        )

        assert response is not None
        assert response.payload["result"] == "success"

    @pytest.mark.asyncio
    async def test_send_request_timeout(self, broker: MessageBroker):
        """Test that send_request times out properly."""
        async def mock_publish(msg):
            return msg.header.message_id

        broker.publish = mock_publish

        with pytest.raises(asyncio.TimeoutError):
            await broker.send_request(
                sender_id="requester-1",
                recipient_id="responder-1",
                subject="test",
                payload={},
                timeout=0.01,
            )

    @pytest.mark.asyncio
    async def test_send_response(self, broker: MessageBroker):
        """Test sending a response to a request."""
        request = Message(
            header=MessageHeader(reply_to="agent.requester-1.inbox"),
            message_type=MessageType.REQUEST,
            sender_id="requester-1",
            recipient_id="responder-1",
            subject="test-request",
        )

        captured_response = None

        async def capture_publish(msg):
            nonlocal captured_response
            captured_response = msg
            return msg.header.message_id

        broker.publish = capture_publish

        await broker.send_response(
            request=request,
            sender_id="responder-1",
            payload={"result": "done"},
            success=True,
        )

        assert captured_response is not None
        assert captured_response.message_type == MessageType.RESPONSE
        assert captured_response.sender_id == "responder-1"
        assert captured_response.recipient_id == "requester-1"
        assert captured_response.payload["success"] is True
        assert captured_response.payload["result"] == "done"

    # ===================================
    # BROADCAST MESSAGE TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_broadcast_method(self, broker: MessageBroker):
        """Test the broadcast convenience method."""
        captured_message = None

        async def capture_publish(msg):
            nonlocal captured_message
            captured_message = msg
            return msg.header.message_id

        broker.publish = capture_publish

        await broker.broadcast(
            sender_id="broadcaster-1",
            subject="announcement",
            payload={"message": "hello"},
            priority=MessagePriority.HIGH,
        )

        assert captured_message is not None
        assert captured_message.message_type == MessageType.BROADCAST
        assert captured_message.channel == "system.broadcast"
        assert captured_message.header.priority == MessagePriority.HIGH

    @pytest.mark.asyncio
    async def test_broadcast_creates_channel_if_needed(self, broker: MessageBroker):
        """Test that broadcast creates system.broadcast channel if needed."""
        async def mock_publish(msg):
            return msg.header.message_id

        broker.publish = mock_publish

        await broker.broadcast(
            sender_id="broadcaster-1",
            subject="test",
            payload={},
        )

        channel = await broker.get_channel("system.broadcast")
        assert channel is not None
        assert channel.channel_type == ChannelType.BROADCAST

    # ===================================
    # DEAD LETTER TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_dead_letter_records_message(self, broker: MessageBroker):
        """Test that dead letter records the failed message."""
        message = Message(
            message_type=MessageType.REQUEST,
            sender_id="sender-1",
            channel="test",
        )

        await broker._dead_letter(message, "Test failure reason")

        assert len(broker._dead_letters) == 1
        assert broker._dead_letters[0].message.sender_id == "sender-1"
        assert broker._dead_letters[0].reason == "Test failure reason"
        assert message.delivery_status == DeliveryStatus.DEAD_LETTERED

    @pytest.mark.asyncio
    async def test_dead_letter_disabled(self, broker: MessageBroker):
        """Test that dead letter respects disabled setting."""
        with patch('platform.agents.broker.settings') as mock_settings:
            mock_settings.enable_dead_letter = False

            message = Message(
                message_type=MessageType.REQUEST,
                sender_id="sender-1",
                channel="test",
            )

            await broker._dead_letter(message, "Test failure")

            assert len(broker._dead_letters) == 0

    @pytest.mark.asyncio
    async def test_dead_letter_retention(self, broker: MessageBroker):
        """Test that old dead letters are trimmed."""
        with patch('platform.agents.broker.settings') as mock_settings:
            mock_settings.enable_dead_letter = True
            mock_settings.dead_letter_retention_hours = 72

            # Add old dead letter
            old_message = Message(sender_id="old", channel="test")
            broker._dead_letters.append(
                MagicMock(
                    message=old_message,
                    reason="old",
                    failed_at=_utcnow() - timedelta(hours=100),
                )
            )

            # Add new dead letter
            new_message = Message(sender_id="new", channel="test")
            await broker._dead_letter(new_message, "new failure")

            # Old one should be trimmed
            assert len(broker._dead_letters) == 1
            assert broker._dead_letters[0].message.sender_id == "new"

    @pytest.mark.asyncio
    async def test_get_dead_letters(self, broker: MessageBroker):
        """Test getting dead letters."""
        msg1 = Message(sender_id="sender-1", channel="test")
        msg2 = Message(sender_id="sender-2", channel="test")

        await broker._dead_letter(msg1, "reason 1")
        await broker._dead_letter(msg2, "reason 2")

        dead_letters = await broker.get_dead_letters()
        assert len(dead_letters) == 2

    @pytest.mark.asyncio
    async def test_get_dead_letters_with_limit(self, broker: MessageBroker):
        """Test getting dead letters with limit."""
        for i in range(10):
            msg = Message(sender_id=f"sender-{i}", channel="test")
            await broker._dead_letter(msg, f"reason {i}")

        dead_letters = await broker.get_dead_letters(limit=5)
        assert len(dead_letters) == 5

    @pytest.mark.asyncio
    async def test_get_dead_letters_since_time(self, broker: MessageBroker):
        """Test getting dead letters since a specific time."""
        msg1 = Message(sender_id="sender-1", channel="test")
        await broker._dead_letter(msg1, "reason 1")

        cutoff = _utcnow()
        await asyncio.sleep(0.01)

        msg2 = Message(sender_id="sender-2", channel="test")
        await broker._dead_letter(msg2, "reason 2")

        dead_letters = await broker.get_dead_letters(since=cutoff)
        assert len(dead_letters) == 1

    @pytest.mark.asyncio
    async def test_retry_dead_letter_success(self, broker: MessageBroker):
        """Test retrying a dead-lettered message."""
        msg = Message(sender_id="sender-1", channel="test")
        msg.header.retry_count = 2
        await broker._dead_letter(msg, "test failure")

        message_id = msg.header.message_id
        republished = False

        async def mock_publish(message):
            nonlocal republished
            republished = True
            return message.header.message_id

        broker.publish = mock_publish

        result = await broker.retry_dead_letter(message_id)

        assert result is True
        assert republished is True
        assert len(broker._dead_letters) == 0

    @pytest.mark.asyncio
    async def test_retry_dead_letter_not_found(self, broker: MessageBroker):
        """Test retrying non-existent dead letter."""
        result = await broker.retry_dead_letter("non-existent-id")
        assert result is False

    # ===================================
    # HANDLER FAILURE TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_handler_failure_retries(self, broker: MessageBroker):
        """Test that handler failure triggers retry."""
        handler = AsyncMock(side_effect=Exception("Handler error"))

        await broker.create_channel("test-channel", ChannelType.TOPIC)
        await broker.subscribe("agent-1", "test-channel", handler=handler)

        message = Message(
            message_type=MessageType.EVENT,
            sender_id="sender-1",
            channel="test-channel",
        )

        republish_count = 0

        async def mock_publish(msg):
            nonlocal republish_count
            republish_count += 1
            return msg.header.message_id

        broker.publish = mock_publish

        with patch('platform.agents.broker.settings') as mock_settings:
            mock_settings.max_retries = 3
            mock_settings.retry_delay_seconds = 0.01

            await broker._invoke_handlers([handler], message)

            # Should have attempted republish
            assert republish_count >= 1

    @pytest.mark.asyncio
    async def test_handler_failure_max_retries_dead_letters(
        self, broker: MessageBroker
    ):
        """Test that exceeding max retries dead letters message."""
        handler = AsyncMock(side_effect=Exception("Handler error"))

        message = Message(
            message_type=MessageType.EVENT,
            sender_id="sender-1",
            channel="test-channel",
        )
        message.header.retry_count = 5  # Already exceeded

        with patch('platform.agents.broker.settings') as mock_settings:
            mock_settings.max_retries = 3
            mock_settings.enable_dead_letter = True
            mock_settings.dead_letter_retention_hours = 72

            await broker._handle_delivery_failure(message, "error")

            assert len(broker._dead_letters) == 1

    # ===================================
    # STATS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_stats(self, broker: MessageBroker):
        """Test getting broker statistics."""
        await broker.create_channel("channel-1", ChannelType.TOPIC)
        await broker.create_channel("queue-1", ChannelType.QUEUE)
        await broker.subscribe("agent-1", "channel-1")

        msg = Message(sender_id="sender-1", channel="channel-1")
        await broker.publish(msg)

        await broker._dead_letter(
            Message(sender_id="dead", channel="test"),
            "test",
        )

        stats = broker.get_stats()

        assert stats["total_channels"] == 2
        assert stats["total_subscriptions"] == 1
        assert stats["total_messages"] == 1
        assert stats["dead_letters"] == 1
        assert "queue-1" in stats["queue_sizes"]

    # ===================================
    # LIFECYCLE TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_start_creates_standard_channels(self, started_broker: MessageBroker):
        """Test that start creates standard channels."""
        # Check some standard channels exist
        events_channel = await started_broker.get_channel("system.events")
        assert events_channel is not None

        commands_channel = await started_broker.get_channel("system.commands")
        assert commands_channel is not None

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, started_broker: MessageBroker):
        """Test that start sets running flag."""
        assert started_broker._running is True

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self, broker: MessageBroker):
        """Test that stop clears running flag."""
        with patch.object(broker, '_process_queues', new_callable=AsyncMock):
            await broker.start()
            await broker.stop()

        assert broker._running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_pending_responses(self, broker: MessageBroker):
        """Test that stop cancels pending response futures."""
        with patch.object(broker, '_process_queues', new_callable=AsyncMock):
            await broker.start()

            # Add pending response
            future = asyncio.Future()
            broker._pending_responses["test-id"] = future

            await broker.stop()

            assert future.cancelled()
