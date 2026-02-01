"""Verification Orchestrator - dispatches claims to domain verifiers."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.celery.tasks import (
    verify_bioinformatics_claim,
    verify_compbio_claim,
    verify_materials_claim,
    verify_math_claim,
    verify_ml_claim,
)
from platform.services.verification_orchestrator.config import get_settings
from platform.shared.clients.kafka_client import KafkaConsumer, KafkaProducer
from platform.shared.clients.redis_client import RedisCache
from platform.shared.schemas.base import Domain
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# Map domains to Celery tasks and queues
DOMAIN_VERIFIERS = {
    Domain.MATHEMATICS.value: {
        "task": verify_math_claim,
        "queue": "verify.math",
        "timeout": settings.math_verification_timeout,
    },
    Domain.ML_AI.value: {
        "task": verify_ml_claim,
        "queue": "verify.ml",
        "timeout": settings.ml_verification_timeout,
    },
    Domain.COMPUTATIONAL_BIOLOGY.value: {
        "task": verify_compbio_claim,
        "queue": "verify.compbio",
        "timeout": settings.compbio_verification_timeout,
    },
    Domain.MATERIALS_SCIENCE.value: {
        "task": verify_materials_claim,
        "queue": "verify.materials",
        "timeout": settings.materials_verification_timeout,
    },
    Domain.BIOINFORMATICS.value: {
        "task": verify_bioinfo_claim,
        "queue": "verify.bioinfo",
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
        self.producer = KafkaProducer()

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

        # Dispatch to Celery
        task = verifier_config["task"]
        result = task.apply_async(
            args=[claim_id, payload],
            kwargs={"job_id": job_id},
            queue=verifier_config["queue"],
            priority=priority,
            time_limit=verifier_config["timeout"],
            soft_time_limit=verifier_config["timeout"] - 30,
        )

        # Update job with task ID
        job_data["celery_task_id"] = result.id
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

        # Publish result event
        await self.producer.send(
            topic="verification.results",
            value={
                "event_type": "verification.completed",
                "job_id": job_id,
                "claim_id": claim_id,
                "status": status,
                "result": result,
                "error": error,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        # Update claim in database
        await self._update_claim_verification_status(claim_id, status, result, error)

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

    async def _update_claim_verification_status(
        self,
        claim_id: str,
        status: str,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        """Update claim verification status in database."""
        from platform.infrastructure.database.models import Claim, VerificationResult
        from sqlalchemy import update

        # Map verification status
        verification_status_map = {
            "verified": "verified",
            "refuted": "refuted",
            "error": "error",
            "timeout": "error",
            "inconclusive": "inconclusive",
        }
        db_status = verification_status_map.get(status, "error")

        # Update claim
        await self.session.execute(
            update(Claim)
            .where(Claim.id == claim_id)
            .values(
                verification_status=db_status,
                status="active" if db_status == "verified" else "pending",
                verified_at=datetime.utcnow() if db_status == "verified" else None,
                updated_at=datetime.utcnow(),
            )
        )

        # Create verification result record
        result_id = str(uuid4())
        verification_result = VerificationResult(
            id=result_id,
            claim_id=claim_id,
            verifier_type=f"domain_{status}",
            status=db_status,
            result=result or {},
            error_message=error,
            completed_at=datetime.utcnow(),
        )
        self.session.add(verification_result)

        await self.session.commit()


class ClaimEventConsumer:
    """
    Kafka consumer for claim events.

    Listens to claim.submitted events and dispatches verification.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.orchestrator = VerificationOrchestrator(session)
        self.consumer = KafkaConsumer(
            topics=["claims"],
            group_id="verification-orchestrator",
        )

    async def start(self) -> None:
        """Start consuming claim events."""
        logger.info("starting_claim_event_consumer")

        async for message in self.consumer.consume():
            try:
                await self._handle_message(message)
            except Exception as e:
                logger.exception("claim_event_handling_error", error=str(e))

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Handle a claim event message."""
        event_type = message.get("event_type")

        if event_type == "claim.submitted":
            await self._handle_claim_submitted(message)
        elif event_type == "claim.retracted":
            await self._handle_claim_retracted(message)

    async def _handle_claim_submitted(self, message: dict[str, Any]) -> None:
        """Handle claim submission - dispatch verification."""
        claim_id = message.get("claim_id")
        domain = message.get("domain")
        claim_type = message.get("claim_type")

        if not all([claim_id, domain, claim_type]):
            logger.error("invalid_claim_event", message=message)
            return

        # Get full claim payload from database
        from platform.infrastructure.database.models import Claim
        from sqlalchemy import select

        result = await self.session.execute(
            select(Claim).where(Claim.id == claim_id)
        )
        claim = result.scalar_one_or_none()

        if not claim:
            logger.error("claim_not_found", claim_id=claim_id)
            return

        # Dispatch verification
        await self.orchestrator.dispatch_verification(
            claim_id=claim_id,
            domain=domain,
            claim_type=claim_type,
            payload=claim.payload,
        )

    async def _handle_claim_retracted(self, message: dict[str, Any]) -> None:
        """Handle claim retraction - cancel pending verification."""
        claim_id = message.get("claim_id")

        # Get verification job
        link = await self.orchestrator.cache.get(f"claim_verification:{claim_id}")
        if link and link.get("status") in ("queued", "dispatched", "running"):
            # Cancel the job
            job_id = link.get("job_id")
            if job_id:
                job_data = await self.orchestrator.cache.get(f"verification_job:{job_id}")
                if job_data and job_data.get("celery_task_id"):
                    from platform.infrastructure.celery.app import celery_app
                    celery_app.control.revoke(job_data["celery_task_id"], terminate=True)

                    logger.info(
                        "verification_cancelled",
                        job_id=job_id,
                        claim_id=claim_id,
                    )
