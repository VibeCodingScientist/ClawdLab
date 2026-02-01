"""Kafka event handler for XP events.

Consumes verification.results, claims, and frontiers topics
and calls ExperienceService.award_xp() for eligible events.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

from .calculator import ROLE_CATEGORY_MAP, XPSource
from .service import ExperienceService

logger = get_logger(__name__)


class XPEventHandler:
    """Routes Kafka events to XP awards."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.service = ExperienceService(session)

    async def handle_event(self, event_type: str, data: dict) -> None:
        """Route incoming event to appropriate handler."""
        handlers = {
            "verification.completed": self._handle_verification_completed,
            "claim.verified": self._handle_claim_verified,
            "claim.cited": self._handle_claim_cited,
            "challenge.resolved": self._handle_challenge_resolved,
            "frontier.solved": self._handle_frontier_solved,
            "roundtable.proposal_approved": self._handle_proposal_approved,
            "roundtable.review_accepted": self._handle_review_accepted,
        }

        handler = handlers.get(event_type)
        if handler:
            try:
                await handler(data)
            except Exception:
                logger.exception("Error handling XP event %s", event_type)
        else:
            logger.debug("Ignoring unhandled event type: %s", event_type)

    async def _handle_verification_completed(self, data: dict) -> None:
        status = data.get("status")
        if status != "verified":
            return

        agent_id = UUID(data["agent_id"])
        claim_id = UUID(data["claim_id"])
        domain = data.get("domain")
        score = float(data.get("verification_score", 0.0))

        # Look up agent's archetype for role category
        role_category = await self._get_role_category(agent_id)

        await self.service.award_xp(
            agent_id=agent_id,
            source=XPSource.CLAIM_VERIFIED,
            domain=domain,
            verification_score=score,
            role_category=role_category,
            source_id=claim_id,
            lab_slug=data.get("lab_slug"),
        )

    async def _handle_claim_verified(self, data: dict) -> None:
        agent_id = UUID(data["agent_id"])
        claim_id = UUID(data["claim_id"])
        domain = data.get("domain")
        score = float(data.get("verification_score", 0.0))
        role_category = await self._get_role_category(agent_id)

        await self.service.award_xp(
            agent_id=agent_id,
            source=XPSource.CLAIM_VERIFIED,
            domain=domain,
            verification_score=score,
            role_category=role_category,
            source_id=claim_id,
            lab_slug=data.get("lab_slug"),
        )

    async def _handle_claim_cited(self, data: dict) -> None:
        cited_agent_id = UUID(data["cited_agent_id"])
        claim_id = UUID(data["claim_id"]) if "claim_id" in data else None
        domain = data.get("domain")
        role_category = await self._get_role_category(cited_agent_id)

        await self.service.award_xp(
            agent_id=cited_agent_id,
            source=XPSource.CLAIM_CITED,
            domain=domain,
            verification_score=0.0,
            role_category=role_category,
            source_id=claim_id,
        )

    async def _handle_challenge_resolved(self, data: dict) -> None:
        winner_agent_id = data.get("winner_agent_id")
        if not winner_agent_id:
            return

        agent_id = UUID(winner_agent_id)
        domain = data.get("domain")
        role_category = await self._get_role_category(agent_id)
        challenge_id = UUID(data["challenge_id"]) if "challenge_id" in data else None

        await self.service.award_xp(
            agent_id=agent_id,
            source=XPSource.CHALLENGE_WON,
            domain=domain,
            verification_score=0.0,
            role_category=role_category,
            source_id=challenge_id,
        )

    async def _handle_frontier_solved(self, data: dict) -> None:
        agent_id = UUID(data["agent_id"])
        domain = data.get("domain")
        frontier_id = UUID(data["frontier_id"]) if "frontier_id" in data else None
        role_category = await self._get_role_category(agent_id)

        await self.service.award_xp(
            agent_id=agent_id,
            source=XPSource.FRONTIER_CONTRIBUTED,
            domain=domain,
            verification_score=0.0,
            role_category=role_category,
            source_id=frontier_id,
        )

    async def _handle_proposal_approved(self, data: dict) -> None:
        agent_id = UUID(data["proposer_agent_id"])
        domain = data.get("domain")
        role_category = await self._get_role_category(agent_id)

        await self.service.award_xp(
            agent_id=agent_id,
            source=XPSource.PROPOSAL_APPROVED,
            domain=domain,
            verification_score=0.0,
            role_category=role_category,
        )

    async def _handle_review_accepted(self, data: dict) -> None:
        agent_id = UUID(data["reviewer_agent_id"])
        domain = data.get("domain")
        role_category = await self._get_role_category(agent_id)

        await self.service.award_xp(
            agent_id=agent_id,
            source=XPSource.REVIEW_ACCEPTED,
            domain=domain,
            verification_score=0.0,
            role_category=role_category,
        )

    async def _get_role_category(self, agent_id: UUID) -> str:
        """Look up agent's primary archetype and map to role category."""
        from platform.infrastructure.database.models import LabMembership

        result = await self.session.execute(
            select(LabMembership)
            .where(
                LabMembership.agent_id == agent_id,
                LabMembership.status == "active",
            )
            .limit(1)
        )
        membership = result.scalar_one_or_none()

        if membership and membership.role_card:
            archetype = membership.role_card.archetype
            return ROLE_CATEGORY_MAP.get(archetype, "execution")

        return "execution"
