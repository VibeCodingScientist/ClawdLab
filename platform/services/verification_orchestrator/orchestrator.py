"""Verification Orchestrator - dispatches claims to domain verifiers."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from platform.services.verification_orchestrator.config import get_settings
from platform.infrastructure.events import emit_platform_event
from platform.shared.clients.redis_client import RedisCache
from platform.shared.schemas.base import Domain
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# Map domains to verification service factories and timeouts
DOMAIN_VERIFIERS = {
    Domain.MATHEMATICS.value: {
        "timeout": settings.math_verification_timeout,
    },
    Domain.ML_AI.value: {
        "timeout": settings.ml_verification_timeout,
    },
    Domain.COMPUTATIONAL_BIOLOGY.value: {
        "timeout": settings.compbio_verification_timeout,
    },
    Domain.MATERIALS_SCIENCE.value: {
        "timeout": settings.materials_verification_timeout,
    },
    Domain.BIOINFORMATICS.value: {
        "timeout": settings.bioinfo_verification_timeout,
    },
}


class VerificationOrchestrator:
    """
    Orchestrates claim verification across domain-specific engines.

    Responsibilities:
    - Receive claim submission events
    - Dispatch to appropriate verifier
    - Track verification progress
    - Handle retries and failures
    - Publish verification results
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.cache = RedisCache("verification")

    async def dispatch_verification(
        self,
        claim_id: str,
        domain: str,
        claim_type: str,
        payload: dict[str, Any],
        priority: int = 5,
    ) -> str:
        """
        Dispatch a claim for verification.

        Args:
            claim_id: ID of the claim to verify
            domain: Research domain
            claim_type: Type of claim
            payload: Claim payload
            priority: Task priority (1-10, lower = higher priority)

        Returns:
            Verification job ID
        """
        if domain not in DOMAIN_VERIFIERS:
            raise ValueError(f"Unknown domain: {domain}")

        verifier_config = DOMAIN_VERIFIERS[domain]
        job_id = str(uuid4())

        # Store job metadata
        job_data = {
            "job_id": job_id,
            "claim_id": claim_id,
            "domain": domain,
            "claim_type": claim_type,
            "status": "queued",
            "queued_at": datetime.utcnow().isoformat(),
            "attempts": 0,
        }
        await self.cache.setex(
            f"verification_job:{job_id}",
            verifier_config["timeout"] * 2,  # TTL = 2x timeout
            job_data,
        )

        # Dispatch as async background task
        asyncio.create_task(
            self._run_verification(job_id, claim_id, domain, payload)
        )

        job_data["status"] = "dispatched"
        await self.cache.setex(
            f"verification_job:{job_id}",
            verifier_config["timeout"] * 2,
            job_data,
        )

        # Update claim verification link
        await self.cache.setex(
            f"claim_verification:{claim_id}",
            verifier_config["timeout"] * 2,
            {"job_id": job_id, "status": "dispatched"},
        )

        logger.info(
            "verification_dispatched",
            job_id=job_id,
            claim_id=claim_id,
            domain=domain,
            queue=verifier_config["queue"],
        )

        return job_id

    async def dispatch_verification_plan(
        self,
        claim_id: str,
        domain: str,
        claim_type: str,
        payload: dict[str, Any],
        lab_id: str | None = None,
        priority: int = 5,
    ) -> dict[str, Any]:
        """Dispatch a multi-step verification plan.

        1. Domain verification (existing dispatch_verification)
        2. On success -> robustness + consistency in parallel
        3. Calculate badge
        4. Publish enriched verification results with badge

        Args:
            claim_id: ID of the claim to verify
            domain: Research domain
            claim_type: Type of claim
            payload: Claim payload
            lab_id: Optional lab context for consistency checks
            priority: Task priority

        Returns:
            Dict with job_id, plan summary, and initial status
        """
        from platform.services.verification_orchestrator.planner import VerificationPlanner

        planner = VerificationPlanner()
        plan = planner.create_plan(
            claim_id=claim_id,
            domain=domain,
            claim_type=claim_type,
            payload=payload,
            lab_context={"lab_id": lab_id} if lab_id else None,
        )

        # Step 1: Domain verification (existing)
        job_id = await self.dispatch_verification(
            claim_id=claim_id,
            domain=domain,
            claim_type=claim_type,
            payload=payload,
            priority=priority,
        )

        # Store plan metadata for post-verification badge calculation
        plan_data = {
            "plan_id": plan.plan_id,
            "claim_id": claim_id,
            "domain": domain,
            "lab_id": lab_id,
            "steps": [
                {
                    "step_id": s.step_id,
                    "name": s.name,
                    "verifier_type": s.verifier_type,
                }
                for s in plan.steps
            ],
            "status": "domain_verification_dispatched",
        }
        await self.cache.setex(
            f"verification_plan:{plan.plan_id}",
            86400,
            plan_data,
        )

        # Link job to plan
        await self.cache.setex(
            f"job_plan_link:{job_id}",
            86400,
            {"plan_id": plan.plan_id},
        )

        logger.info(
            "verification_plan_dispatched",
            plan_id=plan.plan_id,
            claim_id=claim_id,
            job_id=job_id,
            step_count=len(plan.steps),
        )

        return {
            "plan_id": plan.plan_id,
            "job_id": job_id,
            "steps": len(plan.steps),
            "status": "dispatched",
        }

    async def get_verification_status(self, job_id: str) -> dict[str, Any] | None:
        """Get status of a verification job."""
        return await self.cache.get(f"verification_job:{job_id}")

    async def get_claim_verification(self, claim_id: str) -> dict[str, Any] | None:
        """Get verification status for a claim."""
        link = await self.cache.get(f"claim_verification:{claim_id}")
        if not link:
            return None

        job_id = link.get("job_id")
        if job_id:
            return await self.get_verification_status(job_id)
        return link

    async def handle_verification_result(
        self,
        job_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """
        Handle verification result from a worker.

        Args:
            job_id: Verification job ID
            status: Result status (verified, refuted, error, timeout)
            result: Verification result details
            error: Error message if failed
        """
        job_data = await self.cache.get(f"verification_job:{job_id}")
        if not job_data:
            logger.error("verification_job_not_found", job_id=job_id)
            return

        claim_id = job_data["claim_id"]

        # Update job status
        job_data["status"] = status
        job_data["completed_at"] = datetime.utcnow().isoformat()
        if result:
            job_data["result"] = result
        if error:
            job_data["error"] = error

        await self.cache.setex(
            f"verification_job:{job_id}",
            86400,  # Keep for 24 hours after completion
            job_data,
        )

        # Update claim verification link
        await self.cache.setex(
            f"claim_verification:{claim_id}",
            86400,
            {"job_id": job_id, "status": status},
        )

        # Get claim to include agent_id and domain in event
        from platform.infrastructure.database.models import Claim
        from sqlalchemy import select

        claim_result = await self.session.execute(
            select(Claim).where(Claim.id == claim_id)
        )
        claim = claim_result.scalar_one_or_none()

        # Publish result event with agent info for karma processing
        event_payload = {
            "event_type": "verification.completed",
            "job_id": job_id,
            "claim_id": claim_id,
            "status": status,
            "result": result,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if claim:
            event_payload["agent_id"] = str(claim.agent_id)
            event_payload["domain"] = claim.domain
            if result:
                event_payload["novelty_score"] = result.get("novelty_score")
                event_payload["impact_score"] = result.get("impact_score")
                event_payload["verification_score"] = result.get("verification_score")

        emit_platform_event("verification.results", event_payload)

        # Update claim in database
        await self._update_claim_verification_status(claim_id, status, result, error)

        # Badge calculation -- run robustness + consistency if passed
        plan_link = await self.cache.get(f"job_plan_link:{job_id}")
        if plan_link and status == "verified":
            try:
                from platform.services.verification_orchestrator.robustness import RobustnessChecker
                from platform.services.verification_orchestrator.consistency import ConsistencyChecker
                from platform.services.verification_orchestrator.badges import BadgeCalculator

                robustness_checker = RobustnessChecker()
                consistency_checker = ConsistencyChecker(self.session)

                robustness_result = await robustness_checker.check_robustness(
                    claim_id=claim_id,
                    domain=job_data["domain"],
                    original_result=result or {},
                    payload=job_data.get("payload", {}),
                )
                consistency_result = await consistency_checker.check_consistency(
                    claim_id=claim_id,
                    domain=job_data["domain"],
                    payload=job_data.get("payload", {}),
                )

                calculator = BadgeCalculator()
                badge_result = calculator.calculate_badge(
                    verification_passed=True,
                    stability_score=robustness_result.stability_score,
                    consistent=consistency_result.consistent,
                    contradictions=consistency_result.contradictions,
                    consistency_score=consistency_result.confidence,
                )

                # Update claim with badge info
                from sqlalchemy import update as sa_update
                await self.session.execute(
                    sa_update(Claim)
                    .where(Claim.id == claim_id)
                    .values(
                        verification_badge=badge_result.badge.value,
                        stability_score=badge_result.stability_score,
                        consistency_score=badge_result.consistency_score,
                    )
                )
                await self.session.commit()

                # Enrich event payload with badge
                event_payload["badge"] = badge_result.badge.value
                event_payload["stability_score"] = badge_result.stability_score
                event_payload["consistency_score"] = badge_result.consistency_score

                logger.info(
                    "badge_applied",
                    claim_id=claim_id,
                    badge=badge_result.badge.value,
                )
            except Exception as e:
                logger.error("badge_calculation_failed", claim_id=claim_id, error=str(e))

        logger.info(
            "verification_completed",
            job_id=job_id,
            claim_id=claim_id,
            status=status,
        )

    async def retry_verification(self, job_id: str) -> str | None:
        """
        Retry a failed verification.

        Returns:
            New job ID if retry dispatched, None if max retries exceeded
        """
        job_data = await self.cache.get(f"verification_job:{job_id}")
        if not job_data:
            return None

        attempts = job_data.get("attempts", 0) + 1
        if attempts > settings.max_verification_retries:
            logger.warning(
                "max_retries_exceeded",
                job_id=job_id,
                claim_id=job_data["claim_id"],
                attempts=attempts,
            )
            return None

        # Dispatch new verification
        new_job_id = await self.dispatch_verification(
            claim_id=job_data["claim_id"],
            domain=job_data["domain"],
            claim_type=job_data["claim_type"],
            payload=job_data.get("payload", {}),
            priority=3,  # Higher priority for retries
        )

        # Update attempt count
        new_job_data = await self.cache.get(f"verification_job:{new_job_id}")
        if new_job_data:
            new_job_data["attempts"] = attempts
            new_job_data["previous_job_id"] = job_id
            await self.cache.setex(
                f"verification_job:{new_job_id}",
                DOMAIN_VERIFIERS[job_data["domain"]]["timeout"] * 2,
                new_job_data,
            )

        return new_job_id

    async def _run_verification(
        self,
        job_id: str,
        claim_id: str,
        domain: str,
        payload: dict[str, Any],
    ) -> None:
        """Run verification in-process and handle the result."""
        try:
            result = await self._call_verifier(claim_id, domain, payload, job_id)
            verified = result.get("verified", False)
            await self.handle_verification_result(
                job_id=job_id,
                status="verified" if verified else "refuted",
                result=result,
            )
        except Exception as e:
            logger.exception("verification_error", job_id=job_id, claim_id=claim_id)
            await self.handle_verification_result(
                job_id=job_id,
                status="error",
                error=str(e),
            )

    async def _call_verifier(
        self,
        claim_id: str,
        domain: str,
        payload: dict[str, Any],
        job_id: str,
    ) -> dict[str, Any]:
        """Call the appropriate domain verification service."""
        if domain == Domain.MATHEMATICS.value:
            from platform.verification_engines.math_verifier.service import get_math_verification_service
            service = get_math_verification_service()
            return await service.verify_claim(claim_id, payload)

        elif domain == Domain.ML_AI.value:
            from platform.verification_engines.ml_verifier.service import get_ml_verification_service
            service = get_ml_verification_service()
            return await service.verify_claim(claim_id, payload)

        elif domain == Domain.COMPUTATIONAL_BIOLOGY.value:
            from platform.verification_engines.compbio_verifier.service import get_compbio_verification_service
            service = get_compbio_verification_service()
            return await service.verify_claim(claim_id, payload)

        elif domain == Domain.MATERIALS_SCIENCE.value:
            from platform.verification_engines.materials_verifier.service import MaterialsVerificationService
            service = MaterialsVerificationService()
            claim = {"claim_id": claim_id, **payload}
            result = await service.verify_claim(claim)
            return result.to_dict()

        elif domain == Domain.BIOINFORMATICS.value:
            from platform.verification_engines.bioinfo_verifier.service import get_bioinfo_verification_service
            service = get_bioinfo_verification_service()
            claim = {"claim_id": claim_id, **payload}
            result = await service.verify_claim(claim)
            return result.to_dict()

        else:
            raise ValueError(f"Unknown domain: {domain}")

    async def _update_claim_verification_status(
        self,
        claim_id: str,
        status: str,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        """Update claim verification status in database."""
        from platform.infrastructure.database.models import Claim, VerificationResult
        from sqlalchemy import select, update

        # Map verification status
        verification_status_map = {
            "verified": "verified",
            "refuted": "failed",
            "error": "failed",
            "timeout": "failed",
            "inconclusive": "partial",
        }
        db_status = verification_status_map.get(status, "failed")

        # Extract scores from result
        novelty_score = None
        verification_score = None
        if result:
            novelty_score = result.get("novelty_score")
            verification_score = result.get("verification_score")

        # Update claim with scores
        update_values = {
            "verification_status": db_status,
            "updated_at": datetime.utcnow(),
        }

        if db_status == "verified":
            update_values["verified_at"] = datetime.utcnow()
            if novelty_score is not None:
                update_values["novelty_score"] = novelty_score
            if verification_score is not None:
                update_values["verification_score"] = verification_score

        await self.session.execute(
            update(Claim)
            .where(Claim.id == claim_id)
            .values(**update_values)
        )

        # Get claim domain for verifier type
        claim_result = await self.session.execute(
            select(Claim.domain).where(Claim.id == claim_id)
        )
        domain = claim_result.scalar_one_or_none() or "unknown"

        # Create verification result record
        result_id = str(uuid4())
        now = datetime.utcnow()
        verification_result = VerificationResult(
            id=result_id,
            claim_id=claim_id,
            verifier_type=f"{domain}_verifier",
            verifier_version="1.0.0",
            passed=(status == "verified"),
            score=verification_score,
            results=result or {},
            started_at=now,  # Approximation - actual start time from job
            completed_at=now,
        )
        self.session.add(verification_result)

        await self.session.commit()


