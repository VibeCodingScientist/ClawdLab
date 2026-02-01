"""Repository layer for Claim Service database operations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from platform.infrastructure.database.models import (
    Challenge,
    Claim,
    ClaimDependency,
    VerificationResult,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class ClaimRepository:
    """Repository for claim database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        claim_id: str,
        agent_id: str,
        domain: str,
        claim_type: str,
        title: str,
        abstract: str,
        payload: dict[str, Any],
        payload_hash: str,
        dependencies: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Claim:
        """Create a new claim."""
        claim = Claim(
            id=claim_id,
            agent_id=agent_id,
            domain=domain,
            claim_type=claim_type,
            title=title,
            abstract=abstract,
            payload=payload,
            payload_hash=payload_hash,
            tags=tags or [],
            metadata_=metadata or {},
            status="pending",
            verification_status="pending",
        )
        self.session.add(claim)

        # Create dependency records
        if dependencies:
            for dep_id in dependencies:
                dep = ClaimDependency(
                    claim_id=claim_id,
                    depends_on_id=dep_id,
                )
                self.session.add(dep)

        await self.session.flush()
        await self.session.refresh(claim)

        logger.info("claim_created", claim_id=claim_id, domain=domain)
        return claim

    async def get_by_id(self, claim_id: str | UUID) -> Claim | None:
        """Get claim by ID with dependencies loaded."""
        query = (
            select(Claim)
            .where(Claim.id == claim_id)
            .options(
                selectinload(Claim.dependencies),
                selectinload(Claim.dependents),
                selectinload(Claim.challenges),
                selectinload(Claim.verification_results),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_hash(self, payload_hash: str) -> Claim | None:
        """Get claim by payload hash (for duplicate detection)."""
        query = select(Claim).where(Claim.payload_hash == payload_hash)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def exists(self, claim_id: str | UUID) -> bool:
        """Check if claim exists."""
        query = select(Claim.id).where(Claim.id == claim_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def list_claims(
        self,
        domain: str | None = None,
        claim_type: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
        verification_status: str | None = None,
        tags: list[str] | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Claim], int]:
        """List claims with filtering and pagination."""
        conditions = []

        if domain:
            conditions.append(Claim.domain == domain)
        if claim_type:
            conditions.append(Claim.claim_type == claim_type)
        if agent_id:
            conditions.append(Claim.agent_id == agent_id)
        if status:
            conditions.append(Claim.status == status)
        if verification_status:
            conditions.append(Claim.verification_status == verification_status)
        if tags:
            # Check if any tag matches
            conditions.append(Claim.tags.overlap(tags))
        if created_after:
            conditions.append(Claim.created_at >= created_after)
        if created_before:
            conditions.append(Claim.created_at <= created_before)

        # Build query
        base_query = select(Claim)
        if conditions:
            base_query = base_query.where(and_(*conditions))

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(Claim, sort_by, Claim.created_at)
        if sort_order == "desc":
            base_query = base_query.order_by(sort_column.desc())
        else:
            base_query = base_query.order_by(sort_column.asc())

        # Apply pagination
        base_query = base_query.offset(offset).limit(limit)

        result = await self.session.execute(base_query)
        claims = list(result.scalars().all())

        return claims, total

    async def update(
        self,
        claim_id: str | UUID,
        **kwargs,
    ) -> Claim | None:
        """Update claim fields."""
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            return await self.get_by_id(claim_id)

        updates["updated_at"] = datetime.utcnow()

        await self.session.execute(
            update(Claim).where(Claim.id == claim_id).values(**updates)
        )
        await self.session.flush()

        return await self.get_by_id(claim_id)

    async def update_status(
        self,
        claim_id: str | UUID,
        status: str,
        verification_status: str | None = None,
    ) -> bool:
        """Update claim status."""
        updates = {"status": status, "updated_at": datetime.utcnow()}
        if verification_status:
            updates["verification_status"] = verification_status
            if verification_status == "verified":
                updates["verified_at"] = datetime.utcnow()

        result = await self.session.execute(
            update(Claim).where(Claim.id == claim_id).values(**updates)
        )
        return result.rowcount > 0

    async def get_dependencies(self, claim_id: str | UUID) -> list[Claim]:
        """Get claims that this claim depends on."""
        query = (
            select(Claim)
            .join(ClaimDependency, ClaimDependency.depends_on_id == Claim.id)
            .where(ClaimDependency.claim_id == claim_id)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_dependents(self, claim_id: str | UUID) -> list[Claim]:
        """Get claims that depend on this claim."""
        query = (
            select(Claim)
            .join(ClaimDependency, ClaimDependency.claim_id == Claim.id)
            .where(ClaimDependency.depends_on_id == claim_id)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def add_dependency(self, claim_id: str, depends_on_id: str) -> bool:
        """Add a dependency between claims."""
        dep = ClaimDependency(claim_id=claim_id, depends_on_id=depends_on_id)
        self.session.add(dep)
        await self.session.flush()
        return True

    async def remove_dependency(self, claim_id: str, depends_on_id: str) -> bool:
        """Remove a dependency between claims."""
        result = await self.session.execute(
            delete(ClaimDependency).where(
                ClaimDependency.claim_id == claim_id,
                ClaimDependency.depends_on_id == depends_on_id,
            )
        )
        return result.rowcount > 0

    async def count_citations(self, claim_id: str | UUID) -> int:
        """Count how many claims cite this claim as a dependency."""
        query = (
            select(func.count())
            .select_from(ClaimDependency)
            .where(ClaimDependency.depends_on_id == claim_id)
        )
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def search_full_text(
        self,
        query: str,
        domain: str | None = None,
        limit: int = 20,
    ) -> list[Claim]:
        """Full-text search across claims."""
        # Simple LIKE search - in production, use PostgreSQL full-text search
        search_pattern = f"%{query}%"
        conditions = [
            or_(
                Claim.title.ilike(search_pattern),
                Claim.abstract.ilike(search_pattern),
            )
        ]
        if domain:
            conditions.append(Claim.domain == domain)

        stmt = (
            select(Claim)
            .where(and_(*conditions))
            .order_by(Claim.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ChallengeRepository:
    """Repository for challenge database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        challenge_id: str,
        claim_id: str,
        challenger_id: str,
        challenge_type: str,
        title: str,
        description: str,
        evidence: dict[str, Any],
        severity: str,
    ) -> Challenge:
        """Create a new challenge."""
        challenge = Challenge(
            id=challenge_id,
            claim_id=claim_id,
            challenger_id=challenger_id,
            challenge_type=challenge_type,
            title=title,
            description=description,
            evidence=evidence,
            severity=severity,
            status="open",
        )
        self.session.add(challenge)
        await self.session.flush()
        await self.session.refresh(challenge)

        logger.info(
            "challenge_created",
            challenge_id=challenge_id,
            claim_id=claim_id,
            challenger_id=challenger_id,
        )
        return challenge

    async def get_by_id(self, challenge_id: str | UUID) -> Challenge | None:
        """Get challenge by ID."""
        query = select(Challenge).where(Challenge.id == challenge_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_claim(self, claim_id: str | UUID) -> list[Challenge]:
        """Get all challenges for a claim."""
        query = (
            select(Challenge)
            .where(Challenge.claim_id == claim_id)
            .order_by(Challenge.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_by_claim_and_agent(
        self,
        claim_id: str | UUID,
        challenger_id: str | UUID,
    ) -> Challenge | None:
        """Check if agent has an active challenge on a claim."""
        query = select(Challenge).where(
            Challenge.claim_id == claim_id,
            Challenge.challenger_id == challenger_id,
            Challenge.status == "open",
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        challenge_id: str | UUID,
        status: str,
        resolution: str | None = None,
    ) -> bool:
        """Update challenge status."""
        updates = {"status": status, "updated_at": datetime.utcnow()}
        if status in ("resolved", "rejected", "accepted"):
            updates["resolved_at"] = datetime.utcnow()
        if resolution:
            updates["resolution"] = resolution

        result = await self.session.execute(
            update(Challenge).where(Challenge.id == challenge_id).values(**updates)
        )
        return result.rowcount > 0


class VerificationResultRepository:
    """Repository for verification result database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        result_id: str,
        claim_id: str,
        verifier_type: str,
        status: str,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
        compute_time_seconds: float | None = None,
    ) -> VerificationResult:
        """Create a verification result."""
        verification = VerificationResult(
            id=result_id,
            claim_id=claim_id,
            verifier_type=verifier_type,
            status=status,
            result=result or {},
            error_message=error_message,
            compute_time_seconds=compute_time_seconds,
        )
        self.session.add(verification)
        await self.session.flush()
        await self.session.refresh(verification)

        logger.info(
            "verification_result_created",
            result_id=result_id,
            claim_id=claim_id,
            status=status,
        )
        return verification

    async def get_by_claim(self, claim_id: str | UUID) -> list[VerificationResult]:
        """Get all verification results for a claim."""
        query = (
            select(VerificationResult)
            .where(VerificationResult.claim_id == claim_id)
            .order_by(VerificationResult.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_latest_by_claim(self, claim_id: str | UUID) -> VerificationResult | None:
        """Get the most recent verification result for a claim."""
        query = (
            select(VerificationResult)
            .where(VerificationResult.claim_id == claim_id)
            .order_by(VerificationResult.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update(
        self,
        result_id: str | UUID,
        status: str,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
        compute_time_seconds: float | None = None,
    ) -> bool:
        """Update verification result."""
        updates = {"status": status, "updated_at": datetime.utcnow()}
        if result is not None:
            updates["result"] = result
        if error_message is not None:
            updates["error_message"] = error_message
        if compute_time_seconds is not None:
            updates["compute_time_seconds"] = compute_time_seconds
        if status in ("verified", "refuted", "error"):
            updates["completed_at"] = datetime.utcnow()

        stmt = (
            update(VerificationResult)
            .where(VerificationResult.id == result_id)
            .values(**updates)
        )
        res = await self.session.execute(stmt)
        return res.rowcount > 0
