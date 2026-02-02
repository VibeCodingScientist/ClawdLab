"""Celery tasks for verification engines."""

from typing import Any

from celery import shared_task

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# ===========================================
# MATHEMATICS VERIFICATION TASKS
# ===========================================


@shared_task(
    bind=True,
    name="verify.math.claim",
    queue="verify.math",
    max_retries=3,
    default_retry_delay=60,
)
def verify_math_claim(
    self,
    claim_id: str,
    payload: dict[str, Any],
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Verify a mathematical proof claim.

    Supports:
    - Lean 4 proofs (with Mathlib)
    - Coq proofs
    - Z3/CVC5 SMT problems

    Args:
        claim_id: ID of the claim
        payload: Claim payload containing proof
        job_id: Verification job ID

    Returns:
        Verification result
    """
    import asyncio

    logger.info(
        "math_verification_started",
        claim_id=claim_id,
        job_id=job_id,
        proof_system=payload.get("proof_system"),
    )

    try:
        # Import the math verification service
        from platform.verification_engines.math_verifier.service import (
            get_math_verification_service,
        )

        # Get the service instance
        service = get_math_verification_service()

        # Run verification asynchronously
        result = asyncio.run(service.verify_claim(claim_id, payload))

        logger.info(
            "math_verification_completed",
            claim_id=claim_id,
            job_id=job_id,
            verified=result.get("verified", False),
        )

        return result

    except Exception as e:
        logger.exception(
            "math_verification_error",
            claim_id=claim_id,
            job_id=job_id,
            error=str(e),
        )

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "verified": False,
            "status": "error",
            "verifier": "math_verifier",
            "message": f"Verification failed: {str(e)}",
            "error_type": "internal_error",
            "claim_id": claim_id,
        }


# ===========================================
# ML/AI VERIFICATION TASKS
# ===========================================


@shared_task(
    bind=True,
    name="verify.ml.claim",
    queue="verify.ml",
    max_retries=2,
    default_retry_delay=300,
)
def verify_ml_claim(
    self,
    claim_id: str,
    payload: dict[str, Any],
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Verify an ML experiment claim.

    Handles:
    - Code reproducibility
    - Benchmark reproduction
    - Metric validation

    Args:
        claim_id: ID of the claim
        payload: Claim payload with experiment details
        job_id: Verification job ID

    Returns:
        Verification result
    """
    import asyncio

    logger.info(
        "ml_verification_started",
        claim_id=claim_id,
        job_id=job_id,
        experiment_type=payload.get("experiment_type"),
    )

    try:
        # Import the ML verification service
        from platform.verification_engines.ml_verifier.service import (
            get_ml_verification_service,
        )

        # Get the service instance
        service = get_ml_verification_service()

        # Run verification asynchronously
        result = asyncio.run(service.verify_claim(claim_id, payload))

        logger.info(
            "ml_verification_completed",
            claim_id=claim_id,
            job_id=job_id,
            verified=result.get("verified", False),
        )

        return result

    except Exception as e:
        logger.exception(
            "ml_verification_error",
            claim_id=claim_id,
            job_id=job_id,
            error=str(e),
        )

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "verified": False,
            "status": "error",
            "verifier": "ml_verifier",
            "message": f"Verification failed: {str(e)}",
            "error_type": "internal_error",
            "claim_id": claim_id,
        }


# ===========================================
# COMPUTATIONAL BIOLOGY TASKS
# ===========================================


@shared_task(
    bind=True,
    name="verify.compbio.claim",
    queue="verify.compbio",
    max_retries=2,
    default_retry_delay=300,
)
def verify_compbio_claim(
    self,
    claim_id: str,
    payload: dict[str, Any],
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Verify a computational biology claim.

    Handles:
    - Protein structure prediction (AlphaFold, ESMFold)
    - Protein design verification
    - Binder design verification

    Args:
        claim_id: ID of the claim
        payload: Claim payload with protein/design data
        job_id: Verification job ID

    Returns:
        Verification result
    """
    import asyncio

    logger.info(
        "compbio_verification_started",
        claim_id=claim_id,
        job_id=job_id,
        claim_type=payload.get("claim_type"),
    )

    try:
        # Import the CompBio verification service
        from platform.verification_engines.compbio_verifier.service import (
            get_compbio_verification_service,
        )

        # Get the service instance
        service = get_compbio_verification_service()

        # Run verification asynchronously
        result = asyncio.run(service.verify_claim(claim_id, payload))

        logger.info(
            "compbio_verification_completed",
            claim_id=claim_id,
            job_id=job_id,
            verified=result.get("verified", False),
        )

        return result

    except Exception as e:
        logger.exception(
            "compbio_verification_error",
            claim_id=claim_id,
            job_id=job_id,
            error=str(e),
        )

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "verified": False,
            "status": "error",
            "verifier": "compbio_verifier",
            "message": f"Verification failed: {str(e)}",
            "error_type": "internal_error",
            "claim_id": claim_id,
        }


# ===========================================
# MATERIALS SCIENCE TASKS
# ===========================================


@shared_task(
    bind=True,
    name="verify.materials.claim",
    queue="verify.materials",
    max_retries=3,
    default_retry_delay=120,
)
def verify_materials_claim(
    self,
    claim_id: str,
    payload: dict[str, Any],
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Verify a materials science claim.

    Handles:
    - Crystal structure validation
    - Stability calculations (MACE, CHGNet, M3GNet)
    - Property predictions
    - Novelty checking (MP, AFLOW, OQMD)

    Args:
        claim_id: ID of the claim
        payload: Claim payload with structure/property data
        job_id: Verification job ID

    Returns:
        Verification result
    """
    import asyncio

    logger.info(
        "materials_verification_started",
        claim_id=claim_id,
        job_id=job_id,
        claim_type=payload.get("claim_type"),
    )

    try:
        # Import the Materials verification service
        from platform.verification_engines.materials_verifier.service import (
            MaterialsVerificationService,
        )

        # Create service instance (MCP tool provider can be injected)
        service = MaterialsVerificationService()

        # Build claim dict
        claim = {
            "claim_id": claim_id,
            **payload,
        }

        # Run verification asynchronously
        result = asyncio.run(service.verify_claim(claim))

        logger.info(
            "materials_verification_completed",
            claim_id=claim_id,
            job_id=job_id,
            verified=result.verified,
            status=result.status.value,
        )

        return result.to_dict()

    except Exception as e:
        logger.exception(
            "materials_verification_error",
            claim_id=claim_id,
            job_id=job_id,
            error=str(e),
        )

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "verified": False,
            "status": "error",
            "verifier": "materials_verifier",
            "message": f"Verification failed: {str(e)}",
            "error_type": "internal_error",
            "claim_id": claim_id,
        }


# ===========================================
# BIOINFORMATICS TASKS
# ===========================================


@shared_task(
    bind=True,
    name="verify.bioinfo.claim",
    queue="verify.bioinfo",
    max_retries=2,
    default_retry_delay=300,
)
def verify_bioinformatics_claim(
    self,
    claim_id: str,
    payload: dict[str, Any],
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Verify a bioinformatics claim.

    Handles:
    - Pipeline execution (Nextflow, Snakemake)
    - Statistical validation
    - Result reproduction

    Args:
        claim_id: ID of the claim
        payload: Claim payload with pipeline/analysis data
        job_id: Verification job ID

    Returns:
        Verification result
    """
    logger.info(
        "bioinfo_verification_started",
        claim_id=claim_id,
        job_id=job_id,
        analysis_type=payload.get("analysis_type"),
    )

    result = {
        "verified": False,
        "status": "pending_implementation",
        "verifier": "bioinfo_verifier",
        "message": "Bioinformatics verification engine not yet implemented",
        "details": {
            "analysis_type": payload.get("analysis_type"),
            "pipeline": payload.get("pipeline"),
            "claim_id": claim_id,
        },
    }

    return result


# ===========================================
# UTILITY TASKS
# ===========================================


@shared_task(name="verification.callback")
def verification_callback(
    result: dict[str, Any],
    job_id: str,
    claim_id: str,
) -> None:
    """
    Callback task for handling verification results.

    Called after a verification task completes.
    """
    from platform.shared.clients.kafka_client import KafkaProducer
    from datetime import datetime
    import asyncio

    async def send_result():
        producer = KafkaProducer()
        await producer.send(
            topic="verification.results",
            value={
                "event_type": "verification.completed",
                "job_id": job_id,
                "claim_id": claim_id,
                "status": "verified" if result.get("verified") else "refuted",
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    asyncio.run(send_result())


@shared_task(name="verification.cleanup")
def cleanup_old_jobs() -> int:
    """
    Periodic task to clean up old verification job data.

    Returns:
        Number of jobs cleaned up
    """
    # Placeholder - would clean up old Redis keys
    logger.info("cleanup_old_jobs_executed")
    return 0
