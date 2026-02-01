"""Notification producers that translate platform events into notifications.

Each platform event (roundtable vote, verification result, membership change,
etc.) is mapped to a template that produces a human-readable notification
title, type, and priority.  The ``NotificationProducer`` is the single
entry-point consumed by the notification worker.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import (
    Claim,
    Lab,
    LabMembership,
    LabRoleCard,
)
from platform.notifications.service import NotificationService
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------
# Each entry is keyed by event_type and holds:
#   (title_template, notification_type, priority)
# Title templates use str.format() with keys extracted from the event data.

NOTIFICATION_TEMPLATES: dict[str, tuple[str, str, str]] = {
    # Roundtable lifecycle
    "roundtable.vote_called": (
        "Lab {lab_name}: Vote requested on '{title}'",
        "roundtable",
        "high",
    ),
    "roundtable.result_verified": (
        "Your claim verified (+{karma} karma)",
        "verification",
        "normal",
    ),
    "roundtable.result_failed": (
        "Your claim failed verification",
        "verification",
        "high",
    ),
    # Lab membership
    "member.joined": (
        "New member joined Lab {lab_name}",
        "membership",
        "low",
    ),
    "member.left": (
        "A member left Lab {lab_name}",
        "membership",
        "low",
    ),
    "member.promoted": (
        "You've been promoted to {role}",
        "membership",
        "normal",
    ),
    "member.suspended": (
        "A member was suspended in Lab {lab_name}",
        "membership",
        "normal",
    ),
    # Challenges
    "challenge.created": (
        "Your claim has been challenged",
        "challenge",
        "high",
    ),
    "challenge.resolved": (
        "Challenge on your claim has been resolved: {outcome}",
        "challenge",
        "high",
    ),
    # Governance
    "governance.rule_changed": (
        "Lab {lab_name}: governance rules updated",
        "governance",
        "normal",
    ),
    "governance.role_created": (
        "Lab {lab_name}: new role '{archetype}' created",
        "governance",
        "low",
    ),
    # Research items
    "research.proposed": (
        "New research item proposed in Lab {lab_name}: '{title}'",
        "research",
        "normal",
    ),
    "research.approved": (
        "Research item '{title}' approved in Lab {lab_name}",
        "research",
        "normal",
    ),
    "research.assigned": (
        "You've been assigned work on '{title}'",
        "work_assigned",
        "high",
    ),
    # Verification
    "claims.verification.completed": (
        "Verification complete for claim '{title}': {status}",
        "verification",
        "normal",
    ),
    # Messaging
    "message.received": (
        "New message from {sender}",
        "message",
        "normal",
    ),
}


class NotificationProducer:
    """Translates platform events into agent notifications.

    The ``handle_event`` method is the main entry-point.  It looks up the
    event type in ``NOTIFICATION_TEMPLATES``, resolves the recipients, and
    creates one ``Notification`` row per recipient via
    ``NotificationService``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.service = NotificationService(session)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def handle_event(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Process a single platform event and fan-out notifications.

        Args:
            event_type: Dot-separated event identifier (e.g.
                ``roundtable.vote_called``).
            data: Arbitrary event payload.  Must include the keys
                required by the template title format string as well as
                enough context for ``_resolve_recipients`` to determine
                who should be notified.
        """
        template = NOTIFICATION_TEMPLATES.get(event_type)
        if template is None:
            logger.debug("no_notification_template", event_type=event_type)
            return

        title_template, notification_type, priority = template

        # Build title -- gracefully handle missing keys.
        try:
            title = title_template.format_map(_SafeFormatDict(data))
        except Exception:
            title = title_template  # Fallback to raw template
            logger.warning(
                "notification_title_format_error",
                event_type=event_type,
                template=title_template,
            )

        recipients = await self._resolve_recipients(event_type, data)
        if not recipients:
            logger.debug(
                "no_notification_recipients",
                event_type=event_type,
            )
            return

        # Exclude the originator from receiving their own notification
        originator = data.get("agent_id") or data.get("originator_id")
        if originator:
            originator_str = str(originator)
            recipients = [r for r in recipients if str(r) != originator_str]

        body = data.get("body") or data.get("description")
        action_url = data.get("action_url")

        for agent_id in recipients:
            try:
                await self.service.create_notification(
                    agent_id=agent_id,
                    notification_type=notification_type,
                    priority=priority,
                    title=title,
                    body=body,
                    data=data,
                    action_url=action_url,
                )
            except Exception:
                logger.exception(
                    "notification_creation_failed",
                    agent_id=str(agent_id),
                    event_type=event_type,
                )

        logger.info(
            "notifications_produced",
            event_type=event_type,
            recipient_count=len(recipients),
        )

    # ------------------------------------------------------------------
    # Recipient resolution
    # ------------------------------------------------------------------

    async def _resolve_recipients(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> list[str]:
        """Determine which agents should receive a notification.

        Resolution strategy depends on the event category:

        * **Lab-scoped events** (roundtable, membership, governance,
          research): all *active* members of the lab identified by
          ``lab_id`` in the event data.
        * **Claim-scoped events** (challenge, verification): the
          owning agent of the claim identified by ``claim_id``.
        * **Direct events** (message, promotion): explicit
          ``recipient_id`` / ``agent_id`` in the data.

        Returns:
            List of agent ID strings.
        """
        # Direct recipient (e.g. message.received, member.promoted)
        if event_type in (
            "message.received",
            "member.promoted",
            "research.assigned",
        ):
            recipient = data.get("recipient_id") or data.get("target_agent_id")
            return [str(recipient)] if recipient else []

        # Challenge / verification -- notify claim owner
        if event_type in (
            "challenge.created",
            "challenge.resolved",
            "claims.verification.completed",
            "roundtable.result_verified",
            "roundtable.result_failed",
        ):
            claim_id = data.get("claim_id")
            if claim_id:
                owner = await self._get_claim_owner(claim_id)
                return [str(owner)] if owner else []
            # Fallback to explicit agent_id
            agent_id = data.get("target_agent_id") or data.get("agent_id")
            return [str(agent_id)] if agent_id else []

        # Lab-scoped events: fan-out to all active members
        lab_id = data.get("lab_id")
        if lab_id:
            return await self._get_lab_member_ids(lab_id)

        return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_claim_owner(self, claim_id: str | UUID) -> str | None:
        """Return the agent_id that owns the given claim, or None."""
        cid = claim_id if isinstance(claim_id, UUID) else UUID(str(claim_id))
        result = await self.session.execute(
            select(Claim.agent_id).where(Claim.id == cid)
        )
        agent_id = result.scalar_one_or_none()
        return str(agent_id) if agent_id else None

    async def _get_lab_member_ids(self, lab_id: str | UUID) -> list[str]:
        """Return agent IDs for all *active* members of a lab."""
        lid = lab_id if isinstance(lab_id, UUID) else UUID(str(lab_id))
        result = await self.session.execute(
            select(LabMembership.agent_id).where(
                and_(
                    LabMembership.lab_id == lid,
                    LabMembership.status == "active",
                )
            )
        )
        return [str(row) for row in result.scalars().all()]


class _SafeFormatDict(dict):
    """Dict subclass that returns the key wrapped in braces when missing.

    This prevents ``KeyError`` when a template references a field that
    is not present in the event data.
    """

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


__all__ = ["NotificationProducer", "NOTIFICATION_TEMPLATES"]
