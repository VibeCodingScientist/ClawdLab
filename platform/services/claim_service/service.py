"""Service layer for Claim Service business logic."""

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from platform.services.claim_service.config import get_settings
from platform.services.claim_service.exceptions import (
    ChallengeAlreadyExistsError,
    ChallengeNotFoundError,
    ClaimAlreadyExistsError,
    ClaimNotChallengableError,
    ClaimNotFoundError,
    ClaimNotRetractableError,
    CyclicDependencyError,
    DependencyNotFoundError,
    DependencyNotVerifiedError,
    InvalidClaimError,
    UnauthorizedClaimAccessError,
)
from platform.services.claim_service.repository import (
    ChallengeRepository,
    ClaimRepository,
    VerificationResultRepository,
)
from platform.infrastructure.events import emit_platform_event
from platform.shared.clients.redis_client import RedisCache
from platform.shared.schemas.claim_payloads import validate_payload
from platform.security.sanitization import get_sanitizer, ThreatLevel
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ClaimService:
    """Handles claim lifecycle operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.claim_repo = ClaimRepository(session)
        self.challenge_repo = ChallengeRepository(session)
        self.verification_repo = VerificationResultRepository(session)
        self.cache = RedisCache("claims")

    def _compute_payload_hash(self, payload: dict[str, Any]) -> str:
        """Compute deterministic hash of claim payload."""
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def _check_cyclic_dependencies(
        self,
        claim_id: str,
        dependencies: list[str],
        visited: set[str] | None = None,
    ) -> None:
        """Check for cyclic dependencies in claim graph."""
        if visited is None:
            visited = set()

        if claim_id in visited:
            raise CyclicDependencyError(list(visited) + [claim_id])

        visited.add(claim_id)

        for dep_id in dependencies:
            dep_claim = await self.claim_repo.get_by_id(dep_id)
            if dep_claim:
                # Get dependencies of the dependency
                dep_deps = await self.claim_repo.get_dependencies(dep_id)
                dep_dep_ids = [str(d.id) for d in dep_deps]
                await self._check_cyclic_dependencies(dep_id, dep_dep_ids, visited.copy())

    async def submit_claim(
        self,
        agent_id: str,
        domain: str,
        claim_type: str,
        title: str,
        abstract: str,
        payload: dict[str, Any],
        dependencies: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Submit a new claim for verification.

        Args:
            agent_id: ID of the submitting agent
            domain: Research domain
            claim_type: Type of claim
            title: Claim title
            abstract: Claim abstract
            payload: Domain-specific payload
            dependencies: IDs of claims this depends on
            tags: Categorization tags
            metadata: Additional metadata

        Returns:
            Created claim data

        Raises:
            ClaimAlreadyExistsError: If identical claim exists
            DependencyNotFoundError: If dependency doesn't exist
            DependencyNotVerifiedError: If dependency isn't verified
            CyclicDependencyError: If dependencies form a cycle
        """
        # Compute payload hash for deduplication
        payload_hash = self._compute_payload_hash(payload)

        # Validate domain-specific payload schema
        try:
            validated_payload = validate_payload(domain, claim_type, payload)
            payload = validated_payload  # Use normalized payload
        except ValueError as e:
            raise InvalidClaimError(str(e), field="payload")

        # Security scan the validated payload
        scan_result = get_sanitizer().scan(payload)
        security_flagged = not scan_result.is_safe
        if scan_result.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            raise InvalidClaimError(
                f"Payload flagged for security concerns: {scan_result.threat_level.value}",
                field="payload",
            )

        # Check for duplicate
        existing = await self.claim_repo.get_by_hash(payload_hash)
        if existing:
            raise ClaimAlreadyExistsError(payload_hash)

        # Validate dependencies
        dependencies = dependencies or []
        if len(dependencies) > settings.max_dependencies_per_claim:
            raise ValueError(
                f"Too many dependencies. Maximum is {settings.max_dependencies_per_claim}"
            )

        for dep_id in dependencies:
            dep_claim = await self.claim_repo.get_by_id(dep_id)
            if not dep_claim:
                raise DependencyNotFoundError(dep_id)
            # Dependencies must be verified (or at least not refuted)
            if dep_claim.verification_status == "refuted":
                raise DependencyNotVerifiedError(dep_id)

        # Generate claim ID
        claim_id = str(uuid4())

        # Check for cyclic dependencies
        await self._check_cyclic_dependencies(claim_id, dependencies)

        # Create claim
        claim = await self.claim_repo.create(
            claim_id=claim_id,
            agent_id=agent_id,
            domain=domain,
            claim_type=claim_type,
            title=title,
            abstract=abstract,
            payload=payload,
            payload_hash=payload_hash,
            dependencies=dependencies,
            tags=tags,
            metadata=metadata,
        )

        # Store security scan results
        if security_flagged:
            await self.claim_repo.update(
                claim_id,
                security_flagged=True,
                security_scan=scan_result.to_dict(),
            )

        # Publish event for verification
        await self._publish_claim_event(claim, "claim.submitted")

        logger.info(
            "claim_submitted",
            claim_id=claim_id,
            agent_id=agent_id,
            domain=domain,
        )

        return self._claim_to_dict(claim)

    async def get_claim(self, claim_id: str) -> dict[str, Any]:
        """Get claim by ID with full details."""
        claim = await self.claim_repo.get_by_id(claim_id)
        if not claim:
            raise ClaimNotFoundError(claim_id)

        result = self._claim_to_dict(claim)

        # Add dependencies
        deps = await self.claim_repo.get_dependencies(claim_id)
        result["dependency_claims"] = [
            {
                "claim_id": str(d.id),
                "title": d.title,
                "domain": d.domain,
                "status": d.status,
                "verification_status": d.verification_status,
                "agent_id": str(d.agent_id),
            }
            for d in deps
        ]

        # Add dependents
        dependents = await self.claim_repo.get_dependents(claim_id)
        result["dependent_claims"] = [
            {
                "claim_id": str(d.id),
                "title": d.title,
                "domain": d.domain,
                "status": d.status,
                "verification_status": d.verification_status,
                "agent_id": str(d.agent_id),
            }
            for d in dependents
        ]

        # Add challenges
        challenges = await self.challenge_repo.get_by_claim(claim_id)
        result["challenges"] = [
            {
                "challenge_id": str(c.id),
                "challenge_type": c.challenge_type,
                "title": c.title,
                "status": c.status,
                "severity": c.severity,
                "challenger_id": str(c.challenger_id),
            }
            for c in challenges
        ]

        # Add citation count
        result["citations"] = await self.claim_repo.count_citations(claim_id)

        # Add latest verification result
        latest_result = await self.verification_repo.get_latest_by_claim(claim_id)
        if latest_result:
            result["verification_result"] = {
                "status": latest_result.status,
                "verifier_type": latest_result.verifier_type,
                "result": latest_result.result,
                "error_message": latest_result.error_message,
                "completed_at": latest_result.completed_at,
            }

        return result

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
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """List claims with filtering and pagination."""
        offset = (page - 1) * page_size

        claims, total = await self.claim_repo.list_claims(
            domain=domain,
            claim_type=claim_type,
            agent_id=agent_id,
            status=status,
            verification_status=verification_status,
            tags=tags,
            created_after=created_after,
            created_before=created_before,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=offset,
            limit=page_size,
        )

        return {
            "claims": [self._claim_to_dict(c) for c in claims],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": offset + len(claims) < total,
        }

    async def update_claim(
        self,
        claim_id: str,
        agent_id: str,
        title: str | None = None,
        abstract: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update claim metadata (not payload - that's immutable)."""
        claim = await self.claim_repo.get_by_id(claim_id)
        if not claim:
            raise ClaimNotFoundError(claim_id)

        if str(claim.agent_id) != agent_id:
            raise UnauthorizedClaimAccessError(claim_id, agent_id)

        updates = {}
        if title is not None:
            updates["title"] = title
        if abstract is not None:
            updates["abstract"] = abstract
        if tags is not None:
            updates["tags"] = tags
        if metadata is not None:
            updates["metadata_"] = metadata

        claim = await self.claim_repo.update(claim_id, **updates)
        return self._claim_to_dict(claim)

    async def retract_claim(
        self,
        claim_id: str,
        agent_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """
        Retract a claim.

        A claim can only be retracted by its owner and if it hasn't been
        cited by other verified claims.
        """
        claim = await self.claim_repo.get_by_id(claim_id)
        if not claim:
            raise ClaimNotFoundError(claim_id)

        if str(claim.agent_id) != agent_id:
            raise UnauthorizedClaimAccessError(claim_id, agent_id)

        if claim.status == "retracted":
            raise ClaimNotRetractableError(claim_id, "Already retracted")

        # Check if any verified claims depend on this
        dependents = await self.claim_repo.get_dependents(claim_id)
        verified_dependents = [
            d for d in dependents if d.verification_status == "verified"
        ]
        if verified_dependents:
            raise ClaimNotRetractableError(
                claim_id,
                f"Cannot retract: {len(verified_dependents)} verified claims depend on this",
            )

        # Update status
        await self.claim_repo.update(
            claim_id,
            status="retracted",
            metadata_={**(claim.metadata_ or {}), "retraction_reason": reason},
        )

        # Notify dependents
        await self._publish_claim_event(claim, "claim.retracted")

        logger.info("claim_retracted", claim_id=claim_id, agent_id=agent_id)

        return await self.get_claim(claim_id)

    async def search_claims(
        self,
        query: str,
        domain: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Full-text search across claims."""
        claims = await self.claim_repo.search_full_text(query, domain, limit)
        return [self._claim_to_dict(c) for c in claims]

    def _claim_to_dict(self, claim) -> dict[str, Any]:
        """Convert claim model to dictionary."""
        return {
            "claim_id": str(claim.id),
            "agent_id": str(claim.agent_id),
            "domain": claim.domain,
            "claim_type": claim.claim_type,
            "title": claim.title,
            "abstract": claim.abstract,
            "status": claim.status,
            "verification_status": claim.verification_status,
            "payload": claim.payload,
            "payload_hash": claim.payload_hash,
            "tags": claim.tags or [],
            "created_at": claim.created_at,
            "updated_at": claim.updated_at,
            "verified_at": claim.verified_at,
        }

    async def _publish_claim_event(self, claim, event_type: str) -> None:
        """Publish claim event via async background tasks."""
        try:
            emit_platform_event("claims", {
                "event_type": event_type,
                "claim_id": str(claim.id),
                "agent_id": str(claim.agent_id),
                "domain": claim.domain,
                "claim_type": claim.claim_type,
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            logger.error("failed_to_publish_claim_event", error=str(e))


class ChallengeService:
    """Handles challenge operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.claim_repo = ClaimRepository(session)
        self.challenge_repo = ChallengeRepository(session)

    async def submit_challenge(
        self,
        claim_id: str,
        challenger_id: str,
        challenge_type: str,
        title: str,
        description: str,
        evidence: dict[str, Any],
        severity: str,
    ) -> dict[str, Any]:
        """
        Submit a challenge against a claim.

        Args:
            claim_id: ID of the claim being challenged
            challenger_id: ID of the challenging agent
            challenge_type: Type of challenge
            title: Challenge title
            description: Detailed description
            evidence: Supporting evidence
            severity: Challenge severity

        Returns:
            Created challenge data

        Raises:
            ClaimNotFoundError: If claim doesn't exist
            ClaimNotChallengableError: If claim can't be challenged
            ChallengeAlreadyExistsError: If agent already has active challenge
        """
        # Verify claim exists
        claim = await self.claim_repo.get_by_id(claim_id)
        if not claim:
            raise ClaimNotFoundError(claim_id)

        # Can't challenge own claims
        if str(claim.agent_id) == challenger_id:
            raise ClaimNotChallengableError(claim_id, "Cannot challenge your own claim")

        # Can only challenge verified or pending claims
        if claim.status not in ("active", "pending"):
            raise ClaimNotChallengableError(
                claim_id, f"Claim status is {claim.status}"
            )

        # Check for existing active challenge
        existing = await self.challenge_repo.get_active_by_claim_and_agent(
            claim_id, challenger_id
        )
        if existing:
            raise ChallengeAlreadyExistsError(claim_id, challenger_id)

        # Create challenge
        challenge_id = str(uuid4())
        challenge = await self.challenge_repo.create(
            challenge_id=challenge_id,
            claim_id=claim_id,
            challenger_id=challenger_id,
            challenge_type=challenge_type,
            title=title,
            description=description,
            evidence=evidence,
            severity=severity,
        )

        logger.info(
            "challenge_submitted",
            challenge_id=challenge_id,
            claim_id=claim_id,
            challenger_id=challenger_id,
        )

        return self._challenge_to_dict(challenge)

    async def get_challenge(self, challenge_id: str) -> dict[str, Any]:
        """Get challenge by ID."""
        challenge = await self.challenge_repo.get_by_id(challenge_id)
        if not challenge:
            raise ChallengeNotFoundError(challenge_id)
        return self._challenge_to_dict(challenge)

    async def list_challenges(self, claim_id: str) -> dict[str, Any]:
        """List all challenges for a claim."""
        # Verify claim exists
        claim = await self.claim_repo.get_by_id(claim_id)
        if not claim:
            raise ClaimNotFoundError(claim_id)

        challenges = await self.challenge_repo.get_by_claim(claim_id)
        return {
            "challenges": [self._challenge_to_dict(c) for c in challenges],
            "total": len(challenges),
        }

    async def resolve_challenge(
        self,
        challenge_id: str,
        resolver_id: str,
        resolution: str,
        response: str,
    ) -> dict[str, Any]:
        """
        Resolve a challenge.

        Only the claim owner or platform can resolve challenges.
        """
        challenge = await self.challenge_repo.get_by_id(challenge_id)
        if not challenge:
            raise ChallengeNotFoundError(challenge_id)

        # Verify resolver is claim owner
        claim = await self.claim_repo.get_by_id(challenge.claim_id)
        if str(claim.agent_id) != resolver_id:
            raise UnauthorizedClaimAccessError(str(challenge.claim_id), resolver_id)

        # Update challenge status
        await self.challenge_repo.update_status(
            challenge_id,
            status="resolved",
            resolution=resolution,
        )

        # If challenge accepted, may need to update claim status
        if resolution == "accepted":
            # Mark claim as needing re-verification
            await self.claim_repo.update_status(
                challenge.claim_id,
                status="challenged",
                verification_status="pending",
            )

        logger.info(
            "challenge_resolved",
            challenge_id=challenge_id,
            resolution=resolution,
        )

        return await self.get_challenge(challenge_id)

    def _challenge_to_dict(self, challenge) -> dict[str, Any]:
        """Convert challenge model to dictionary."""
        return {
            "challenge_id": str(challenge.id),
            "claim_id": str(challenge.claim_id),
            "challenger_id": str(challenge.challenger_id),
            "challenge_type": challenge.challenge_type,
            "title": challenge.title,
            "description": challenge.description,
            "evidence": challenge.evidence,
            "status": challenge.status,
            "severity": challenge.severity,
            "created_at": challenge.created_at,
            "resolved_at": challenge.resolved_at,
            "resolution": challenge.resolution,
        }
