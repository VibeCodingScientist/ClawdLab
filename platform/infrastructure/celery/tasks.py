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
    - Statistical validation (p-values, effect sizes, multiple testing)
    - Differential expression (DESeq2, edgeR, limma)
    - Sequence analysis and variant calling

    Args:
        claim_id: ID of the claim
        payload: Claim payload with pipeline/analysis data
        job_id: Verification job ID

    Returns:
        Verification result
    """
    import asyncio

    logger.info(
        "bioinfo_verification_started",
        claim_id=claim_id,
        job_id=job_id,
        claim_type=payload.get("claim_type"),
    )

    try:
        # Import the Bioinformatics verification service
        from platform.verification_engines.bioinfo_verifier.service import (
            get_bioinfo_verification_service,
        )

        # Get the service instance
        service = get_bioinfo_verification_service()

        # Build claim dict
        claim = {
            "claim_id": claim_id,
            **payload,
        }

        # Run verification asynchronously
        result = asyncio.run(service.verify_claim(claim))

        logger.info(
            "bioinfo_verification_completed",
            claim_id=claim_id,
            job_id=job_id,
            verified=result.verified,
            status=result.status.value,
        )

        return result.to_dict()

    except Exception as e:
        logger.exception(
            "bioinfo_verification_error",
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
            "verifier": "bioinfo_verifier",
            "message": f"Verification failed: {str(e)}",
            "error_type": "internal_error",
            "claim_id": claim_id,
        }


# ===========================================
# ORCHESTRATION TASKS
# ===========================================


@shared_task(
    bind=True,
    name="orchestration.process_workflow",
    queue="orchestration",
    max_retries=2,
    default_retry_delay=60,
)
def process_workflow(
    self,
    workflow_id: str,
) -> dict[str, Any]:
    """
    Process a research workflow.

    Advances the workflow through its steps and handles claim verification.

    Args:
        workflow_id: ID of workflow to process

    Returns:
        Workflow status
    """
    import asyncio

    logger.info("workflow_processing_started", workflow_id=workflow_id)

    try:
        from platform.orchestration.service import get_orchestration_service

        service = get_orchestration_service()

        # Process workflow claims
        asyncio.run(service.process_workflow_claims(workflow_id))

        # Get updated status
        status = asyncio.run(service.get_workflow_status(workflow_id))

        logger.info(
            "workflow_processing_completed",
            workflow_id=workflow_id,
            status=status.get("status"),
        )

        return status

    except Exception as e:
        logger.exception("workflow_processing_error", workflow_id=workflow_id)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "workflow_id": workflow_id,
            "status": "error",
            "error": str(e),
        }


@shared_task(
    bind=True,
    name="orchestration.route_claim",
    queue="orchestration",
    max_retries=2,
)
def route_and_verify_claim(
    self,
    claim_id: str,
    claim_data: dict[str, Any],
    workflow_id: str | None = None,
) -> dict[str, Any]:
    """
    Route a claim and submit for verification.

    Args:
        claim_id: Claim ID
        claim_data: Claim data
        workflow_id: Optional workflow context

    Returns:
        Routing result
    """
    import asyncio

    logger.info("claim_routing_started", claim_id=claim_id)

    try:
        from platform.orchestration.base import Claim
        from platform.orchestration.service import get_orchestration_service

        service = get_orchestration_service()

        # Create claim object
        claim = Claim(
            claim_id=claim_id,
            claim_type=claim_data.get("claim_type", ""),
            content=claim_data.get("content", ""),
            domain=claim_data.get("domain"),
            source=claim_data.get("source", ""),
            metadata=claim_data.get("metadata", {}),
        )

        # Process claim
        result = asyncio.run(service.process_claim(claim, workflow_id))

        logger.info(
            "claim_routing_completed",
            claim_id=claim_id,
            domain=result.domain,
            verifier=result.verifier,
        )

        return result.to_dict()

    except Exception as e:
        logger.exception("claim_routing_error", claim_id=claim_id)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "claim_id": claim_id,
            "status": "error",
            "error": str(e),
        }


@shared_task(name="orchestration.handle_result")
def handle_verification_result(
    workflow_id: str,
    claim_id: str,
    result: dict[str, Any],
) -> None:
    """
    Handle a verification result from a verification engine.

    Updates the workflow with the result.

    Args:
        workflow_id: Workflow ID
        claim_id: Claim ID
        result: Verification result
    """
    import asyncio

    logger.info(
        "verification_result_received",
        workflow_id=workflow_id,
        claim_id=claim_id,
    )

    try:
        from platform.orchestration.service import get_orchestration_service

        service = get_orchestration_service()

        asyncio.run(service.handle_verification_result(workflow_id, claim_id, result))

    except Exception as e:
        logger.exception(
            "verification_result_handling_error",
            workflow_id=workflow_id,
            claim_id=claim_id,
            error=str(e),
        )


@shared_task(name="orchestration.cleanup_sessions")
def cleanup_expired_sessions() -> int:
    """
    Periodic task to clean up expired sessions.

    Returns:
        Number of sessions cleaned up
    """
    import asyncio

    from platform.orchestration.session_manager import get_session_manager

    manager = get_session_manager()
    count = asyncio.run(manager.cleanup_expired_sessions())

    logger.info("expired_sessions_cleaned", count=count)
    return count


@shared_task(name="orchestration.check_timeouts")
def check_task_timeouts() -> list[str]:
    """
    Periodic task to check for timed out tasks.

    Returns:
        List of timed out task IDs
    """
    import asyncio

    from platform.orchestration.task_scheduler import get_task_scheduler

    scheduler = get_task_scheduler()
    timed_out = asyncio.run(scheduler.check_timeouts())

    if timed_out:
        logger.warning("tasks_timed_out", count=len(timed_out))

    return timed_out


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
