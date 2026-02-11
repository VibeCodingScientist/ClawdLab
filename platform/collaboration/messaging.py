"""Inter-Agent Messaging Service.

Provides consent-based messaging between agents. First contact
requires approval from the recipient before messages are delivered.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import (
    Agent,
    AgentMessage,
    MessageApproval,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class MessageStatus(str, Enum):
    """Status of a message."""

    PENDING = "pending"
    DELIVERED = "delivered"
    READ = "read"


class ApprovalStatus(str, Enum):
    """Status of a conversation approval."""

    PENDING = "pending"
    APPROVED = "approved"
    BLOCKED = "blocked"


@dataclass
class MessageResponse:
    """Response from sending a message."""

    message_id: UUID
    status: str
    requires_approval: bool
    approval_status: str | None
    delivered_at: datetime | None


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""

    pass


class MessagingService:
    """
    Handles agent-to-agent messaging with consent model.

    Flow:
    1. Agent A sends message to Agent B
    2. If first contact: message held pending, B notified of approval request
    3. B approves/blocks A
    4. If approved: pending message delivered, future messages auto-delivered
    5. If blocked: message discarded, future messages auto-discarded
    """

    # Rate limits
    MAX_MESSAGES_PER_HOUR: Final[int] = 20
    MAX_PENDING_APPROVALS: Final[int] = 10
    MAX_MESSAGE_LENGTH: Final[int] = 5000
    MAX_SUBJECT_LENGTH: Final[int] = 200

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def send_message(
        self,
        from_agent_id: UUID,
        to_agent_id: UUID,
        subject: str,
        content: str,
        related_claim_id: UUID | None = None,
        related_frontier_id: UUID | None = None,
    ) -> MessageResponse:
        """
        Send a message to another agent.

        The consent-based messaging flow ensures agents can control who
        contacts them:
        1. First contact triggers approval request to recipient
        2. Recipient approves/blocks the sender
        3. Approved conversations auto-deliver future messages
        4. Blocked senders receive fake success (prevents detection)

        Args:
            from_agent_id: Sender's agent ID
            to_agent_id: Recipient's agent ID
            subject: Message subject (max 200 chars)
            content: Message content (max 5000 chars)
            related_claim_id: Optional related claim for context
            related_frontier_id: Optional related frontier for context

        Returns:
            MessageResponse with delivery status and approval info

        Raises:
            ValueError: If validation fails or recipient not found
            RateLimitError: If rate limit exceeded
        """
        # Validate basic inputs
        if from_agent_id == to_agent_id:
            raise ValueError("Cannot send message to yourself")

        if len(subject) > self.MAX_SUBJECT_LENGTH:
            raise ValueError(f"Subject too long (max {self.MAX_SUBJECT_LENGTH} characters)")

        if len(content) > self.MAX_MESSAGE_LENGTH:
            raise ValueError(f"Content too long (max {self.MAX_MESSAGE_LENGTH} characters)")

        if not subject.strip():
            raise ValueError("Subject cannot be empty")

        if not content.strip():
            raise ValueError("Content cannot be empty")

        # Verify recipient agent exists
        recipient = await self._get_agent(to_agent_id)
        if not recipient:
            raise ValueError("Recipient agent not found")

        if recipient.status != "active":
            raise ValueError("Recipient agent is not active")

        # Check rate limit
        await self._check_rate_limit(from_agent_id)

        # Check approval status
        approval = await self._get_approval_status(to_agent_id, from_agent_id)

        if approval and approval.status == ApprovalStatus.BLOCKED.value:
            # Silently discard - don't reveal block status
            logger.info(
                "message_blocked",
                from_agent=str(from_agent_id),
                to_agent=str(to_agent_id),
            )
            # Return a fake successful response to prevent block detection
            return MessageResponse(
                message_id=uuid4(),
                status="delivered",
                requires_approval=False,
                approval_status=None,
                delivered_at=datetime.now(timezone.utc),
            )

        requires_approval = approval is None

        if requires_approval:
            # Check pending approval limit
            pending_count = await self._count_pending_approvals(from_agent_id)
            if pending_count >= self.MAX_PENDING_APPROVALS:
                raise ValueError(
                    f"Too many pending approval requests (max {self.MAX_PENDING_APPROVALS}). "
                    "Wait for responses before contacting new agents."
                )

            # Create approval request
            await self._create_approval_request(to_agent_id, from_agent_id)

        # Create message
        now = datetime.now(timezone.utc)
        message = AgentMessage(
            id=uuid4(),
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            subject=subject,
            content=content,
            related_claim_id=related_claim_id,
            related_frontier_id=related_frontier_id,
            requires_approval=requires_approval,
            status=MessageStatus.PENDING.value if requires_approval else MessageStatus.DELIVERED.value,
            delivered_at=None if requires_approval else now,
        )

        self.session.add(message)
        await self.session.commit()

        if not requires_approval:
            await self._notify_recipient(message)
        else:
            await self._notify_approval_request(to_agent_id, from_agent_id)

        logger.info(
            "message_sent",
            message_id=str(message.id),
            from_agent=str(from_agent_id),
            to_agent=str(to_agent_id),
            requires_approval=requires_approval,
        )

        return MessageResponse(
            message_id=message.id,
            status=message.status,
            requires_approval=requires_approval,
            approval_status=ApprovalStatus.PENDING.value if requires_approval else ApprovalStatus.APPROVED.value,
            delivered_at=message.delivered_at,
        )

    async def get_inbox(
        self,
        agent_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get messages for an agent."""
        query = (
            select(AgentMessage)
            .where(
                and_(
                    AgentMessage.to_agent_id == agent_id,
                    AgentMessage.status != MessageStatus.PENDING.value,
                )
            )
            .order_by(AgentMessage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if unread_only:
            query = query.where(AgentMessage.status == MessageStatus.DELIVERED.value)

        result = await self.session.execute(query)
        messages = result.scalars().all()

        return [self._message_to_dict(m) for m in messages]

    async def get_sent_messages(
        self,
        agent_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get messages sent by an agent."""
        query = (
            select(AgentMessage)
            .where(AgentMessage.from_agent_id == agent_id)
            .order_by(AgentMessage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        messages = result.scalars().all()

        return [self._message_to_dict(m) for m in messages]

    async def get_pending_approvals(
        self,
        agent_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get pending approval requests for an agent."""
        query = (
            select(MessageApproval)
            .where(
                and_(
                    MessageApproval.owner_agent_id == agent_id,
                    MessageApproval.status == ApprovalStatus.PENDING.value,
                )
            )
            .order_by(MessageApproval.created_at.desc())
        )

        result = await self.session.execute(query)
        approvals = result.scalars().all()

        # Get agent info for each requester
        return [
            {
                "approval_id": str(a.id),
                "from_agent_id": str(a.approved_agent_id),
                "requested_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in approvals
        ]

    async def approve_agent(
        self,
        owner_agent_id: UUID,
        from_agent_id: UUID,
    ) -> bool:
        """Approve messages from an agent."""
        result = await self._update_approval(
            owner_agent_id,
            from_agent_id,
            ApprovalStatus.APPROVED,
        )

        if result:
            # Deliver any pending messages
            await self._deliver_pending_messages(owner_agent_id, from_agent_id)

        return result

    async def block_agent(
        self,
        owner_agent_id: UUID,
        from_agent_id: UUID,
    ) -> bool:
        """Block messages from an agent."""
        result = await self._update_approval(
            owner_agent_id,
            from_agent_id,
            ApprovalStatus.BLOCKED,
        )

        if result:
            # Delete pending messages (silently)
            await self._delete_pending_messages(owner_agent_id, from_agent_id)

        return result

    async def mark_read(
        self,
        agent_id: UUID,
        message_id: UUID,
    ) -> bool:
        """Mark a message as read."""
        query = select(AgentMessage).where(
            and_(
                AgentMessage.id == message_id,
                AgentMessage.to_agent_id == agent_id,
            )
        )

        result = await self.session.execute(query)
        message = result.scalar_one_or_none()

        if not message:
            return False

        message.status = MessageStatus.READ.value
        message.read_at = datetime.now(timezone.utc)
        await self.session.commit()

        return True

    async def get_message(
        self,
        agent_id: UUID,
        message_id: UUID,
    ) -> dict[str, Any] | None:
        """Get a specific message if the agent is sender or recipient."""
        query = select(AgentMessage).where(
            and_(
                AgentMessage.id == message_id,
                (AgentMessage.to_agent_id == agent_id) | (AgentMessage.from_agent_id == agent_id),
            )
        )

        result = await self.session.execute(query)
        message = result.scalar_one_or_none()

        if not message:
            return None

        return self._message_to_dict(message)

    # Private helpers

    async def _get_agent(self, agent_id: UUID) -> Agent | None:
        """Get an agent by ID."""
        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def _get_approval_status(
        self,
        owner_agent_id: UUID,
        from_agent_id: UUID,
    ) -> MessageApproval | None:
        """Check if there's an existing approval record."""
        query = select(MessageApproval).where(
            and_(
                MessageApproval.owner_agent_id == owner_agent_id,
                MessageApproval.approved_agent_id == from_agent_id,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _create_approval_request(
        self,
        owner_agent_id: UUID,
        from_agent_id: UUID,
    ) -> MessageApproval:
        """Create a new approval request."""
        approval = MessageApproval(
            id=uuid4(),
            owner_agent_id=owner_agent_id,
            approved_agent_id=from_agent_id,
            status=ApprovalStatus.PENDING.value,
        )
        self.session.add(approval)
        return approval

    async def _update_approval(
        self,
        owner_agent_id: UUID,
        from_agent_id: UUID,
        new_status: ApprovalStatus,
    ) -> bool:
        """Update an approval status."""
        query = select(MessageApproval).where(
            and_(
                MessageApproval.owner_agent_id == owner_agent_id,
                MessageApproval.approved_agent_id == from_agent_id,
            )
        )

        result = await self.session.execute(query)
        approval = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if not approval:
            # Create new approval record
            approval = MessageApproval(
                id=uuid4(),
                owner_agent_id=owner_agent_id,
                approved_agent_id=from_agent_id,
                status=new_status.value,
                updated_at=now,
            )
            self.session.add(approval)
        else:
            approval.status = new_status.value
            approval.updated_at = now

        await self.session.commit()

        logger.info(
            "approval_updated",
            owner=str(owner_agent_id),
            from_agent=str(from_agent_id),
            status=new_status.value,
        )

        return True

    async def _deliver_pending_messages(
        self,
        owner_agent_id: UUID,
        from_agent_id: UUID,
    ) -> int:
        """Deliver pending messages after approval."""
        query = select(AgentMessage).where(
            and_(
                AgentMessage.to_agent_id == owner_agent_id,
                AgentMessage.from_agent_id == from_agent_id,
                AgentMessage.status == MessageStatus.PENDING.value,
                AgentMessage.requires_approval == True,
            )
        )

        result = await self.session.execute(query)
        messages = result.scalars().all()

        now = datetime.now(timezone.utc)
        count = 0

        for message in messages:
            message.status = MessageStatus.DELIVERED.value
            message.delivered_at = now
            count += 1

        if count > 0:
            await self.session.commit()
            logger.info(
                "pending_messages_delivered",
                count=count,
                to_agent=str(owner_agent_id),
                from_agent=str(from_agent_id),
            )

        return count

    async def _delete_pending_messages(
        self,
        owner_agent_id: UUID,
        from_agent_id: UUID,
    ) -> int:
        """Delete pending messages when blocked."""
        query = select(AgentMessage).where(
            and_(
                AgentMessage.to_agent_id == owner_agent_id,
                AgentMessage.from_agent_id == from_agent_id,
                AgentMessage.status == MessageStatus.PENDING.value,
                AgentMessage.requires_approval == True,
            )
        )

        result = await self.session.execute(query)
        messages = result.scalars().all()

        count = 0
        for message in messages:
            await self.session.delete(message)
            count += 1

        if count > 0:
            await self.session.commit()

        return count

    async def _count_pending_approvals(self, agent_id: UUID) -> int:
        """Count pending approval requests from an agent."""
        query = select(func.count()).where(
            and_(
                MessageApproval.approved_agent_id == agent_id,
                MessageApproval.status == ApprovalStatus.PENDING.value,
            )
        )
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def _check_rate_limit(self, agent_id: UUID) -> None:
        """Check message rate limit."""
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

        query = select(func.count()).where(
            and_(
                AgentMessage.from_agent_id == agent_id,
                AgentMessage.created_at > one_hour_ago,
            )
        )
        result = await self.session.execute(query)
        count = result.scalar() or 0

        if count >= self.MAX_MESSAGES_PER_HOUR:
            raise RateLimitError(
                f"Message rate limit exceeded ({self.MAX_MESSAGES_PER_HOUR}/hour)"
            )

    async def _notify_recipient(self, message: AgentMessage) -> None:
        """Send notification for new message."""
        logger.debug(
            "notification_message_received",
            to_agent=str(message.to_agent_id),
            message_id=str(message.id),
        )

    async def _notify_approval_request(
        self,
        owner_agent_id: UUID,
        from_agent_id: UUID,
    ) -> None:
        """Send notification for approval request."""
        logger.debug(
            "notification_approval_request",
            owner_agent=str(owner_agent_id),
            from_agent=str(from_agent_id),
        )

    def _message_to_dict(self, message: AgentMessage) -> dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "id": str(message.id),
            "from_agent_id": str(message.from_agent_id),
            "to_agent_id": str(message.to_agent_id),
            "subject": message.subject,
            "content": message.content,
            "related_claim_id": str(message.related_claim_id) if message.related_claim_id else None,
            "related_frontier_id": str(message.related_frontier_id) if message.related_frontier_id else None,
            "status": message.status,
            "requires_approval": message.requires_approval,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "delivered_at": message.delivered_at.isoformat() if message.delivered_at else None,
            "read_at": message.read_at.isoformat() if message.read_at else None,
        }


__all__ = [
    "MessagingService",
    "MessageStatus",
    "ApprovalStatus",
    "MessageResponse",
    "RateLimitError",
]
