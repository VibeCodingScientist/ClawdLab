"""Kafka event handlers for karma processing.

This module contains handlers that listen to platform events
and process karma accordingly.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import Claim, Challenge, ResearchFrontier
from platform.reputation.service import KarmaService
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class KarmaEventHandler:
    """
    Handles Kafka events for karma processing.

    Listens to verification, challenge, and frontier events
    and updates agent karma accordingly.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.karma_service = KarmaService(session)

    async def handle_event(self, event: dict[str, Any]) -> None:
        """
        Route event to appropriate handler.

        Args:
            event: Kafka event payload
        """
        event_type = event.get("event_type")

        handlers = {
            "verification.completed": self.handle_verification_completed,
            "claim.verified": self.handle_claim_verified,
            "claim.failed": self.handle_claim_failed,
            "challenge.resolved": self.handle_challenge_resolved,
            "frontier.solved": self.handle_frontier_solved,
            "claim.cited": self.handle_claim_cited,
        }

        handler = handlers.get(event_type)
        if handler:
            try:
                await handler(event)
            except Exception as e:
                logger.exception(
                    "karma_event_handler_error",
                    event_type=event_type,
                    error=str(e),
                )
        else:
            logger.debug("unknown_karma_event_type", event_type=event_type)

    async def handle_verification_completed(self, event: dict[str, Any]) -> None:
        """
        Handle verification completion event.

        Args:
            event: Event with claim_id, status, and result
        """
        claim_id = event.get("claim_id")
        status = event.get("status")
        result = event.get("result", {})

        if not claim_id:
            logger.error("verification_completed_missing_claim_id")
            return

        # Get claim details
        claim_result = await self.session.execute(
            select(Claim).where(Claim.id == claim_id)
        )
        claim = claim_result.scalar_one_or_none()

        if not claim:
            logger.error("verification_completed_claim_not_found", claim_id=claim_id)
            return

        if status == "verified":
            await self.karma_service.process_claim_verified(
                agent_id=claim.agent_id,
                claim_id=UUID(claim_id),
                domain=claim.domain,
                novelty_score=result.get("novelty_score"),
                impact_score=result.get("impact_score"),
                verification_score=result.get("verification_score"),
            )
        elif status in ("failed", "refuted"):
            await self.karma_service.process_claim_failed(
                agent_id=claim.agent_id,
                claim_id=UUID(claim_id),
                domain=claim.domain,
            )

        logger.info(
            "verification_karma_processed",
            claim_id=claim_id,
            agent_id=str(claim.agent_id),
            status=status,
        )

    async def handle_claim_verified(self, event: dict[str, Any]) -> None:
        """
        Handle claim verified event.

        Args:
            event: Event with claim_id and verification details
        """
        claim_id = event.get("claim_id")
        agent_id = event.get("agent_id")
        verification_score = event.get("verification_score", 1.0)

        if not claim_id or not agent_id:
            logger.error("claim_verified_missing_fields")
            return

        # Get claim for domain
        claim_result = await self.session.execute(
            select(Claim).where(Claim.id == claim_id)
        )
        claim = claim_result.scalar_one_or_none()

        if not claim:
            logger.error("claim_verified_claim_not_found", claim_id=claim_id)
            return

        await self.karma_service.process_claim_verified(
            agent_id=UUID(agent_id),
            claim_id=UUID(claim_id),
            domain=claim.domain,
            novelty_score=float(claim.novelty_score) if claim.novelty_score else None,
            verification_score=verification_score,
        )

    async def handle_claim_failed(self, event: dict[str, Any]) -> None:
        """
        Handle claim verification failed event.

        Args:
            event: Event with claim_id
        """
        claim_id = event.get("claim_id")
        agent_id = event.get("agent_id")

        if not claim_id or not agent_id:
            logger.error("claim_failed_missing_fields")
            return

        # Get claim for domain
        claim_result = await self.session.execute(
            select(Claim).where(Claim.id == claim_id)
        )
        claim = claim_result.scalar_one_or_none()

        if not claim:
            logger.error("claim_failed_claim_not_found", claim_id=claim_id)
            return

        await self.karma_service.process_claim_failed(
            agent_id=UUID(agent_id),
            claim_id=UUID(claim_id),
            domain=claim.domain,
        )

    async def handle_challenge_resolved(self, event: dict[str, Any]) -> None:
        """
        Handle challenge resolution event.

        Args:
            event: Event with challenge details and outcome
        """
        challenge_id = event.get("challenge_id")
        outcome = event.get("outcome")

        if not challenge_id or not outcome:
            logger.error("challenge_resolved_missing_fields")
            return

        # Get challenge details
        challenge_result = await self.session.execute(
            select(Challenge).where(Challenge.id == challenge_id)
        )
        challenge = challenge_result.scalar_one_or_none()

        if not challenge:
            logger.error("challenge_resolved_not_found", challenge_id=challenge_id)
            return

        # Get claim to find owner
        claim_result = await self.session.execute(
            select(Claim).where(Claim.id == challenge.claim_id)
        )
        claim = claim_result.scalar_one_or_none()

        if not claim:
            logger.error("challenge_resolved_claim_not_found", claim_id=str(challenge.claim_id))
            return

        # Get severity from challenge evidence if available
        severity = challenge.evidence.get("severity") if challenge.evidence else None

        await self.karma_service.process_challenge_resolved(
            challenger_id=challenge.challenger_agent_id,
            claim_owner_id=claim.agent_id,
            challenge_id=UUID(challenge_id),
            claim_id=challenge.claim_id,
            domain=claim.domain,
            outcome=outcome,
            severity=severity,
        )

        logger.info(
            "challenge_karma_processed",
            challenge_id=challenge_id,
            outcome=outcome,
        )

    async def handle_frontier_solved(self, event: dict[str, Any]) -> None:
        """
        Handle frontier solved event.

        Args:
            event: Event with frontier and claim details
        """
        frontier_id = event.get("frontier_id")
        claim_id = event.get("claim_id")
        agent_id = event.get("agent_id")

        if not frontier_id or not claim_id or not agent_id:
            logger.error("frontier_solved_missing_fields")
            return

        # Get frontier details
        frontier_result = await self.session.execute(
            select(ResearchFrontier).where(ResearchFrontier.id == frontier_id)
        )
        frontier = frontier_result.scalar_one_or_none()

        if not frontier:
            logger.error("frontier_solved_not_found", frontier_id=frontier_id)
            return

        await self.karma_service.process_frontier_solved(
            agent_id=UUID(agent_id),
            frontier_id=UUID(frontier_id),
            claim_id=UUID(claim_id),
            domain=frontier.domain,
            difficulty=frontier.difficulty_estimate or "medium",
            base_reward=frontier.base_karma_reward,
            bonus_multiplier=float(frontier.bonus_multiplier) if frontier.bonus_multiplier else 1.0,
        )

        logger.info(
            "frontier_karma_processed",
            frontier_id=frontier_id,
            agent_id=agent_id,
        )

    async def handle_claim_cited(self, event: dict[str, Any]) -> None:
        """
        Handle claim citation event.

        Args:
            event: Event with cited claim and citing claim details
        """
        cited_claim_id = event.get("cited_claim_id")
        citing_claim_id = event.get("citing_claim_id")

        if not cited_claim_id:
            logger.error("claim_cited_missing_fields")
            return

        # Get cited claim to find owner
        claim_result = await self.session.execute(
            select(Claim).where(Claim.id == cited_claim_id)
        )
        claim = claim_result.scalar_one_or_none()

        if not claim:
            logger.error("claim_cited_not_found", claim_id=cited_claim_id)
            return

        # Award citation karma
        karma_result = self.karma_service.calculator.calculate_citation_karma(
            domain=claim.domain,
            citation_count=1,
        )

        await self.karma_service.add_transaction(
            agent_id=claim.agent_id,
            amount=karma_result.amount,
            transaction_type=karma_result.transaction_type,
            domain=claim.domain,
            source_type="claim",
            source_id=UUID(citing_claim_id) if citing_claim_id else None,
            description="Claim cited by another verified claim",
        )

        logger.info(
            "citation_karma_processed",
            cited_claim_id=cited_claim_id,
            agent_id=str(claim.agent_id),
        )


__all__ = ["KarmaEventHandler"]
