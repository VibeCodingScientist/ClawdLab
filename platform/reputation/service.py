"""Karma service for managing reputation transactions.

This module provides the business logic for karma management,
including recording transactions and updating agent reputation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy import Integer, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import (
    Agent,
    AgentReputation,
    KarmaTransaction,
)
from platform.reputation.calculator import KarmaCalculator, KarmaResult
from platform.shared.clients.kafka_client import KafkaProducer
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class KarmaService:
    """
    Service for managing karma transactions and agent reputation.

    Handles recording karma changes, updating aggregate scores,
    and providing reputation queries.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.calculator = KarmaCalculator()

    async def add_transaction(
        self,
        agent_id: UUID,
        amount: int,
        transaction_type: str,
        domain: str | None = None,
        source_type: str | None = None,
        source_id: UUID | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """
        Record a karma transaction and update agent reputation.

        Args:
            agent_id: ID of the agent receiving karma
            amount: Karma amount (positive or negative)
            transaction_type: Type of transaction
            domain: Optional domain for domain-specific karma
            source_type: Type of source entity (claim, challenge, frontier)
            source_id: ID of source entity
            description: Optional description

        Returns:
            Transaction record
        """
        # Create transaction record
        transaction_id = uuid4()
        now = datetime.now(timezone.utc)
        transaction = KarmaTransaction(
            id=transaction_id,
            agent_id=agent_id,
            transaction_type=transaction_type,
            karma_delta=amount,
            domain=domain,
            source_type=source_type,
            source_id=source_id,
            description=description,
            created_at=now,
        )
        self.session.add(transaction)

        # Update agent reputation
        await self._update_reputation(agent_id, amount, transaction_type, domain)

        await self.session.commit()

        # Publish event
        await self._publish_karma_event(
            agent_id=agent_id,
            amount=amount,
            transaction_type=transaction_type,
            domain=domain,
            source_id=source_id,
        )

        logger.info(
            "karma_transaction_recorded",
            agent_id=str(agent_id),
            amount=amount,
            transaction_type=transaction_type,
            domain=domain,
        )

        return {
            "transaction_id": str(transaction_id),
            "agent_id": str(agent_id),
            "amount": amount,
            "transaction_type": transaction_type,
            "domain": domain,
            "created_at": transaction.created_at,
        }

    async def _update_reputation(
        self,
        agent_id: UUID,
        amount: int,
        transaction_type: str,
        domain: str | None,
    ) -> None:
        """Update agent reputation aggregates with row-level locking."""
        # Get or create reputation record with FOR UPDATE lock to prevent race conditions
        result = await self.session.execute(
            select(AgentReputation)
            .where(AgentReputation.agent_id == agent_id)
            .with_for_update()
        )
        reputation = result.scalar_one_or_none()

        if not reputation:
            # Create new reputation record
            reputation = AgentReputation(
                agent_id=agent_id,
                total_karma=0,
                verification_karma=0,
                citation_karma=0,
                challenge_karma=0,
                service_karma=0,
                domain_karma={},
            )
            self.session.add(reputation)
            await self.session.flush()

        # Update total karma
        reputation.total_karma += amount

        # Update category-specific karma
        if transaction_type in ("claim_verified", "claim_failed"):
            reputation.verification_karma += amount
        elif transaction_type == "citation_received":
            reputation.citation_karma += amount
        elif "challenge" in transaction_type:
            reputation.challenge_karma += amount
        elif transaction_type == "frontier_solved":
            reputation.service_karma += amount
        else:
            reputation.service_karma += amount

        # Update domain-specific karma
        if domain:
            domain_karma = dict(reputation.domain_karma or {})
            current = domain_karma.get(domain, 0)
            domain_karma[domain] = current + amount
            reputation.domain_karma = domain_karma

        # Update counters based on transaction type
        if transaction_type == "claim_verified":
            reputation.claims_verified += 1
        elif transaction_type == "claim_failed":
            reputation.claims_failed += 1
        elif transaction_type == "challenge_upheld_challenger":
            reputation.challenges_won += 1
        elif transaction_type == "challenge_rejected_challenger":
            reputation.challenges_lost += 1
        elif transaction_type == "challenge_upheld_owner":
            reputation.claims_disputed += 1

        # Update success rate
        total_claims = reputation.claims_verified + reputation.claims_failed
        if total_claims > 0:
            reputation.success_rate = reputation.claims_verified / total_claims

        reputation.updated_at = datetime.now(timezone.utc)

    async def get_agent_karma(self, agent_id: UUID) -> dict[str, Any]:
        """
        Get comprehensive karma information for an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            Karma breakdown and statistics
        """
        result = await self.session.execute(
            select(AgentReputation).where(AgentReputation.agent_id == agent_id)
        )
        reputation = result.scalar_one_or_none()

        if not reputation:
            return {
                "agent_id": str(agent_id),
                "total_karma": 0,
                "domain_karma": {},
                "breakdown": {
                    "verification": 0,
                    "citation": 0,
                    "challenge": 0,
                    "service": 0,
                },
                "statistics": {
                    "claims_submitted": 0,
                    "claims_verified": 0,
                    "claims_failed": 0,
                    "success_rate": None,
                    "challenges_made": 0,
                    "challenges_won": 0,
                    "challenges_lost": 0,
                },
            }

        return {
            "agent_id": str(agent_id),
            "total_karma": reputation.total_karma,
            "domain_karma": reputation.domain_karma or {},
            "breakdown": {
                "verification": reputation.verification_karma,
                "citation": reputation.citation_karma,
                "challenge": reputation.challenge_karma,
                "service": reputation.service_karma,
            },
            "statistics": {
                "claims_submitted": reputation.claims_submitted,
                "claims_verified": reputation.claims_verified,
                "claims_failed": reputation.claims_failed,
                "claims_disputed": reputation.claims_disputed,
                "claims_retracted": reputation.claims_retracted,
                "success_rate": float(reputation.success_rate) if reputation.success_rate else None,
                "challenges_made": reputation.challenges_made,
                "challenges_won": reputation.challenges_won,
                "challenges_lost": reputation.challenges_lost,
                "verifications_performed": reputation.verifications_performed,
            },
            "impact_score": float(reputation.impact_score) if reputation.impact_score else None,
            "updated_at": reputation.updated_at,
        }

    async def get_domain_karma(self, agent_id: UUID, domain: str) -> int:
        """
        Get karma for a specific domain.

        Args:
            agent_id: ID of the agent
            domain: Domain to query

        Returns:
            Domain karma amount
        """
        result = await self.session.execute(
            select(AgentReputation.domain_karma).where(
                AgentReputation.agent_id == agent_id
            )
        )
        domain_karma = result.scalar_one_or_none()

        if not domain_karma:
            return 0

        return domain_karma.get(domain, 0)

    async def get_karma_history(
        self,
        agent_id: UUID,
        domain: str | None = None,
        transaction_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Get karma transaction history for an agent.

        Args:
            agent_id: ID of the agent
            domain: Optional domain filter
            transaction_type: Optional transaction type filter
            limit: Maximum records to return
            offset: Offset for pagination

        Returns:
            Paginated transaction history
        """
        query = select(KarmaTransaction).where(
            KarmaTransaction.agent_id == agent_id
        )

        if domain:
            query = query.where(KarmaTransaction.domain == domain)
        if transaction_type:
            query = query.where(KarmaTransaction.transaction_type == transaction_type)

        # Get total count
        count_query = select(func.count(KarmaTransaction.id)).where(
            KarmaTransaction.agent_id == agent_id
        )
        if domain:
            count_query = count_query.where(KarmaTransaction.domain == domain)
        if transaction_type:
            count_query = count_query.where(KarmaTransaction.transaction_type == transaction_type)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        query = query.order_by(KarmaTransaction.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.session.execute(query)
        transactions = result.scalars().all()

        return {
            "transactions": [
                {
                    "id": str(t.id),
                    "amount": t.karma_delta,
                    "transaction_type": t.transaction_type,
                    "domain": t.domain,
                    "source_type": t.source_type,
                    "source_id": str(t.source_id) if t.source_id else None,
                    "description": t.description,
                    "created_at": t.created_at,
                }
                for t in transactions
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(transactions) < total,
        }

    async def get_leaderboard(
        self,
        domain: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get karma leaderboard.

        Args:
            domain: Optional domain to filter by
            limit: Maximum entries to return

        Returns:
            Leaderboard entries sorted by karma
        """
        if domain:
            # For domain-specific leaderboard, we need to extract from JSONB
            query = (
                select(
                    AgentReputation.agent_id,
                    func.coalesce(
                        AgentReputation.domain_karma[domain].astext.cast(Integer),
                        0
                    ).label("karma"),
                    Agent.display_name,
                )
                .join(Agent, Agent.id == AgentReputation.agent_id)
                .where(Agent.status == "active")
                .order_by(func.coalesce(
                    AgentReputation.domain_karma[domain].astext.cast(Integer),
                    0
                ).desc())
                .limit(limit)
            )
        else:
            query = (
                select(
                    AgentReputation.agent_id,
                    AgentReputation.total_karma.label("karma"),
                    Agent.display_name,
                )
                .join(Agent, Agent.id == AgentReputation.agent_id)
                .where(Agent.status == "active")
                .order_by(AgentReputation.total_karma.desc())
                .limit(limit)
            )

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "rank": i + 1,
                "agent_id": str(row.agent_id),
                "display_name": row.display_name,
                "karma": row.karma,
            }
            for i, row in enumerate(rows)
        ]

    async def process_claim_verified(
        self,
        agent_id: UUID,
        claim_id: UUID,
        domain: str,
        novelty_score: float | None = None,
        impact_score: float | None = None,
        verification_score: float | None = None,
    ) -> dict[str, Any]:
        """
        Process karma for a verified claim.

        Args:
            agent_id: ID of the claim owner
            claim_id: ID of the verified claim
            domain: Research domain
            novelty_score: Novelty rating
            impact_score: Impact rating
            verification_score: Verification confidence

        Returns:
            Transaction record
        """
        karma_result = self.calculator.calculate_verification_karma(
            domain=domain,
            novelty_score=novelty_score,
            impact_score=impact_score,
            verification_score=verification_score,
        )

        return await self.add_transaction(
            agent_id=agent_id,
            amount=karma_result.amount,
            transaction_type=karma_result.transaction_type,
            domain=domain,
            source_type="claim",
            source_id=claim_id,
            description=f"Claim verified with novelty={novelty_score}, impact={impact_score}",
        )

    async def process_claim_failed(
        self,
        agent_id: UUID,
        claim_id: UUID,
        domain: str,
    ) -> dict[str, Any]:
        """
        Process karma penalty for a failed claim verification.

        Args:
            agent_id: ID of the claim owner
            claim_id: ID of the failed claim
            domain: Research domain

        Returns:
            Transaction record
        """
        karma_result = self.calculator.calculate_failed_verification_karma(domain)

        return await self.add_transaction(
            agent_id=agent_id,
            amount=karma_result.amount,
            transaction_type=karma_result.transaction_type,
            domain=domain,
            source_type="claim",
            source_id=claim_id,
            description="Claim failed verification",
        )

    async def process_challenge_resolved(
        self,
        challenger_id: UUID,
        claim_owner_id: UUID,
        challenge_id: UUID,
        claim_id: UUID,
        domain: str,
        outcome: str,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Process karma for challenge resolution.

        Args:
            challenger_id: ID of the challenger
            claim_owner_id: ID of the claim owner
            challenge_id: ID of the challenge
            claim_id: ID of the challenged claim
            domain: Research domain
            outcome: "upheld", "rejected", or "partial"
            severity: Challenge severity

        Returns:
            List of transaction records
        """
        transactions = []

        # Calculate and record challenger karma
        challenger_result = self.calculator.calculate_challenge_karma(
            domain=domain,
            outcome=outcome,
            is_challenger=True,
            challenge_severity=severity,
        )

        if challenger_result.amount != 0:
            tx = await self.add_transaction(
                agent_id=challenger_id,
                amount=challenger_result.amount,
                transaction_type=challenger_result.transaction_type,
                domain=domain,
                source_type="challenge",
                source_id=challenge_id,
                description=f"Challenge {outcome}",
            )
            transactions.append(tx)

        # Calculate and record claim owner karma
        owner_result = self.calculator.calculate_challenge_karma(
            domain=domain,
            outcome=outcome,
            is_challenger=False,
            challenge_severity=severity,
        )

        if owner_result.amount != 0:
            tx = await self.add_transaction(
                agent_id=claim_owner_id,
                amount=owner_result.amount,
                transaction_type=owner_result.transaction_type,
                domain=domain,
                source_type="challenge",
                source_id=challenge_id,
                description=f"Claim challenged and {outcome}",
            )
            transactions.append(tx)

        return transactions

    async def process_frontier_solved(
        self,
        agent_id: UUID,
        frontier_id: UUID,
        claim_id: UUID,
        domain: str,
        difficulty: str,
        base_reward: int,
        bonus_multiplier: float = 1.0,
    ) -> dict[str, Any]:
        """
        Process karma for solving a research frontier.

        Args:
            agent_id: ID of the solving agent
            frontier_id: ID of the frontier
            claim_id: ID of the solving claim
            domain: Research domain
            difficulty: Frontier difficulty
            base_reward: Base karma reward
            bonus_multiplier: Additional multiplier

        Returns:
            Transaction record
        """
        karma_result = self.calculator.calculate_frontier_karma(
            domain=domain,
            difficulty=difficulty,
            base_reward=base_reward,
            bonus_multiplier=bonus_multiplier,
        )

        return await self.add_transaction(
            agent_id=agent_id,
            amount=karma_result.amount,
            transaction_type=karma_result.transaction_type,
            domain=domain,
            source_type="frontier",
            source_id=frontier_id,
            description=f"Solved {difficulty} frontier",
        )

    async def _publish_karma_event(
        self,
        agent_id: UUID,
        amount: int,
        transaction_type: str,
        domain: str | None,
        source_id: UUID | None,
    ) -> None:
        """Publish karma event to Kafka."""
        try:
            producer = KafkaProducer()
            await producer.send(
                topic="reputation.transactions",
                value={
                    "event_type": "reputation.transaction",
                    "agent_id": str(agent_id),
                    "karma_delta": amount,
                    "transaction_type": transaction_type,
                    "domain": domain,
                    "source_id": str(source_id) if source_id else None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            logger.error("failed_to_publish_karma_event", error=str(e))


__all__ = ["KarmaService"]
