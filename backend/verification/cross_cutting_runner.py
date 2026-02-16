"""Orchestrator for cross-cutting verifiers.

Collects all registered CrossCuttingVerifier instances, filters to
applicable ones, runs them concurrently, and merges results with
the domain adapter result using weighted scoring.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from backend.logging_config import get_logger
from backend.verification.base import VerificationResult
from backend.verification.cross_cutting_base import (
    CrossCuttingResult,
    CrossCuttingVerifier,
)

logger = get_logger(__name__)

# Registry of all cross-cutting verifiers
_CC_VERIFIERS: list[CrossCuttingVerifier] = []


def register_cross_cutting(verifier: CrossCuttingVerifier) -> None:
    """Register a cross-cutting verifier."""
    _CC_VERIFIERS.append(verifier)
    logger.info("cross_cutting_registered", name=verifier.name)


def get_cross_cutting_verifiers() -> list[CrossCuttingVerifier]:
    """Return all registered cross-cutting verifiers."""
    return list(_CC_VERIFIERS)


async def _run_single(
    verifier: CrossCuttingVerifier,
    task_result: dict,
    task_metadata: dict,
) -> CrossCuttingResult:
    """Run a single cross-cutting verifier with error handling."""
    start = time.monotonic()
    try:
        result = await verifier.verify(task_result, task_metadata)
        result.compute_time_seconds = time.monotonic() - start
        return result
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.exception("cross_cutting_verifier_failed", name=verifier.name)
        return CrossCuttingResult(
            verifier_name=verifier.name,
            score=0.0,
            weight=verifier.default_weight,
            errors=[f"Verifier crashed: {str(e)}"],
            compute_time_seconds=elapsed,
        )


async def run_cross_cutting(
    task_result: dict,
    task_metadata: dict,
) -> list[CrossCuttingResult]:
    """Run all applicable cross-cutting verifiers concurrently."""
    applicable = [
        v for v in _CC_VERIFIERS
        if _safe_is_applicable(v, task_result, task_metadata)
    ]

    if not applicable:
        return []

    logger.info(
        "cross_cutting_running",
        count=len(applicable),
        names=[v.name for v in applicable],
    )

    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                *[_run_single(v, task_result, task_metadata) for v in applicable]
            ),
            timeout=120,
        )
    except asyncio.TimeoutError:
        logger.warning("cross_cutting_gather_timeout", names=[v.name for v in applicable])
        return []

    return list(results)


def _safe_is_applicable(
    verifier: CrossCuttingVerifier,
    task_result: dict,
    task_metadata: dict,
) -> bool:
    """Check applicability without crashing."""
    try:
        return verifier.is_applicable(task_result, task_metadata)
    except Exception:
        logger.exception("cross_cutting_applicability_error", name=verifier.name)
        return False


def merge_results(
    domain_result: VerificationResult,
    cc_results: list[CrossCuttingResult],
    domain_weight: float = 0.70,
) -> VerificationResult:
    """Merge domain adapter result with cross-cutting verifier results.

    Domain adapter gets ``domain_weight`` (default 70%) of the final score.
    Cross-cutting verifiers share the remaining ``1 - domain_weight`` (30%),
    distributed proportionally to their individual weights.
    """
    if not cc_results:
        return domain_result

    # Normalise cross-cutting weights so they sum to 1.0
    total_cc_weight = sum(r.weight for r in cc_results)
    if total_cc_weight <= 0:
        return domain_result

    cc_weight_share = 1.0 - domain_weight

    cc_score = sum(
        (r.weight / total_cc_weight) * r.score for r in cc_results
    )

    final_score = domain_weight * domain_result.score + cc_weight_share * cc_score
    final_score = min(1.0, round(final_score, 4))

    # Merge warnings, errors, and details
    all_warnings = list(domain_result.warnings)
    all_errors = list(domain_result.errors)
    cc_details: list[dict[str, Any]] = []

    for r in cc_results:
        all_warnings.extend(r.warnings)
        all_errors.extend(r.errors)
        cc_details.append({
            "verifier": r.verifier_name,
            "score": r.score,
            "weight": r.weight,
            "details": r.details,
            "errors": r.errors,
            "warnings": r.warnings,
            "compute_time_seconds": r.compute_time_seconds,
        })

    merged_details = dict(domain_result.details)
    merged_details["cross_cutting"] = cc_details
    merged_details["scoring"] = {
        "domain_score": domain_result.score,
        "domain_weight": domain_weight,
        "cc_aggregate_score": round(cc_score, 4),
        "cc_weight_share": cc_weight_share,
        "final_score": final_score,
    }

    return VerificationResult(
        passed=final_score >= 0.5,
        score=final_score,
        badge=VerificationResult.score_to_badge(final_score),
        domain=domain_result.domain,
        details=merged_details,
        errors=all_errors,
        warnings=all_warnings,
        compute_time_seconds=domain_result.compute_time_seconds + sum(
            r.compute_time_seconds for r in cc_results
        ),
    )


def _register_all_cross_cutting() -> None:
    """Import and register all cross-cutting verifiers. Called once at startup."""
    from backend.verification.citation_verifier import CitationVerifier
    from backend.verification.statistical_forensics import StatisticalForensicsVerifier
    from backend.verification.reproducibility_executor import ReproducibilityExecutor
    from backend.verification.data_integrity import DataIntegrityVerifier

    for cls in [CitationVerifier, StatisticalForensicsVerifier, ReproducibilityExecutor, DataIntegrityVerifier]:
        register_cross_cutting(cls())


_register_all_cross_cutting()
