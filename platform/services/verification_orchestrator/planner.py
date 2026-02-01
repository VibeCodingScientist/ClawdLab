"""Verification plan builder for multi-step claim verification.

The planner analyses a claim's domain, type, and optional lab context to
produce a ``VerificationPlan`` -- an ordered DAG of ``VerificationStep``
instances that the orchestrator can execute in dependency order.

Each plan always includes a *domain* verification step, followed by
optional *robustness* and *consistency* checks depending on the claim
type and domain characteristics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class VerificationStep:
    """A single unit of work within a verification plan.

    Attributes:
        step_id: Unique identifier for this step.
        name: Human-readable step name.
        verifier_type: Category -- ``"domain"``, ``"robustness"``, or
            ``"consistency"``.
        domain: Scientific domain of the parent claim.
        config: Verifier-specific configuration dict (e.g. timeout,
            perturbation count, comparator settings).
        depends_on: List of ``step_id`` values that must complete
            successfully before this step can run.
    """

    step_id: str
    name: str
    verifier_type: str  # "domain", "robustness", "consistency"
    domain: str
    config: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class VerificationPlan:
    """Complete verification plan for a single claim.

    Attributes:
        plan_id: Unique plan identifier.
        claim_id: The claim being verified.
        steps: Ordered list of verification steps (may have internal
            dependencies expressed through ``depends_on``).
        lab_id: Optional lab context for lab-scoped claims.
    """

    plan_id: str
    claim_id: str
    steps: list[VerificationStep]
    lab_id: str | None = None


# ---------------------------------------------------------------------------
# Domain-specific defaults
# ---------------------------------------------------------------------------

# Timeout (seconds) per domain for the primary domain verification step.
_DOMAIN_TIMEOUTS: dict[str, int] = {
    "mathematics": 600,
    "ml_ai": 7200,
    "computational_biology": 3600,
    "materials_science": 1800,
    "bioinformatics": 7200,
}

# Number of perturbation runs for robustness checking, per domain.
_ROBUSTNESS_PERTURBATIONS: dict[str, int] = {
    "mathematics": 3,
    "ml_ai": 10,
    "computational_biology": 5,
    "materials_science": 5,
    "bioinformatics": 5,
}

# Claim types that should always include robustness checking.
_ROBUSTNESS_CLAIM_TYPES: set[str] = {
    "empirical",
    "experimental",
    "computational",
    "statistical",
    "benchmark",
}

# Claim types that should always include consistency checking.
_CONSISTENCY_CLAIM_TYPES: set[str] = {
    "empirical",
    "theoretical",
    "proof",
    "computational",
    "meta_analysis",
}


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class VerificationPlanner:
    """Builds multi-step verification plans for claims.

    Usage::

        planner = VerificationPlanner()
        plan = planner.create_plan(
            claim_id="...",
            domain="ml_ai",
            claim_type="empirical",
            payload={...},
            lab_context={"lab_id": "..."},
        )
    """

    def create_plan(
        self,
        claim_id: str,
        domain: str,
        claim_type: str,
        payload: dict[str, Any],
        lab_context: dict[str, Any] | None = None,
    ) -> VerificationPlan:
        """Create a verification plan for a claim.

        The plan always contains at least a ``domain`` verification step.
        Robustness and consistency steps are added based on the claim
        type and domain heuristics.

        Args:
            claim_id: UUID of the claim.
            domain: Scientific domain string.
            claim_type: Claim type string (e.g. ``empirical``, ``proof``).
            payload: Full claim content/payload.
            lab_context: Optional dict with ``lab_id`` and other lab
                metadata for lab-scoped verifications.

        Returns:
            A ``VerificationPlan`` ready for execution.
        """
        plan_id = str(uuid4())
        steps: list[VerificationStep] = []
        lab_id = lab_context.get("lab_id") if lab_context else None

        # ---- Step 1: Domain verification (always present) ----
        domain_step_id = str(uuid4())
        domain_timeout = _DOMAIN_TIMEOUTS.get(domain, 3600)
        steps.append(
            VerificationStep(
                step_id=domain_step_id,
                name=f"{domain}_domain_verification",
                verifier_type="domain",
                domain=domain,
                config={
                    "timeout": domain_timeout,
                    "claim_type": claim_type,
                    "payload_keys": list(payload.keys()) if payload else [],
                    "lab_id": lab_id,
                },
                depends_on=[],
            )
        )

        # ---- Step 2: Robustness check (conditional) ----
        robustness_step_id: str | None = None
        if self._needs_robustness(claim_type, domain, payload):
            robustness_step_id = str(uuid4())
            perturbation_count = _ROBUSTNESS_PERTURBATIONS.get(domain, 5)
            steps.append(
                VerificationStep(
                    step_id=robustness_step_id,
                    name=f"{domain}_robustness_check",
                    verifier_type="robustness",
                    domain=domain,
                    config={
                        "perturbation_count": perturbation_count,
                        "stability_threshold": 0.8,
                        "claim_type": claim_type,
                    },
                    depends_on=[domain_step_id],
                )
            )

        # ---- Step 3: Consistency check (conditional) ----
        if self._needs_consistency(claim_type, domain, payload, lab_context):
            consistency_step_id = str(uuid4())
            depends = [domain_step_id]
            if robustness_step_id:
                depends.append(robustness_step_id)

            steps.append(
                VerificationStep(
                    step_id=consistency_step_id,
                    name=f"{domain}_consistency_check",
                    verifier_type="consistency",
                    domain=domain,
                    config={
                        "max_related_claims": 20,
                        "contradiction_threshold": 0.7,
                        "lab_id": lab_id,
                    },
                    depends_on=depends,
                )
            )

        plan = VerificationPlan(
            plan_id=plan_id,
            claim_id=claim_id,
            steps=steps,
            lab_id=lab_id,
        )

        logger.info(
            "verification_plan_created",
            plan_id=plan_id,
            claim_id=claim_id,
            domain=domain,
            claim_type=claim_type,
            step_count=len(steps),
            step_types=[s.verifier_type for s in steps],
        )

        return plan

    # ------------------------------------------------------------------
    # Heuristics
    # ------------------------------------------------------------------

    @staticmethod
    def _needs_robustness(
        claim_type: str,
        domain: str,
        payload: dict[str, Any],
    ) -> bool:
        """Determine whether a robustness check is warranted.

        Robustness checks are added when:
        - The claim type is in ``_ROBUSTNESS_CLAIM_TYPES``, or
        - The payload includes numerical results / model outputs, or
        - The domain is ``ml_ai`` (models are commonly sensitive to
          hyperparameters and data splits).
        """
        if claim_type.lower() in _ROBUSTNESS_CLAIM_TYPES:
            return True
        if domain == "ml_ai":
            return True
        # Heuristic: payloads with metrics / results are worth perturbing.
        has_metrics = any(
            k in payload
            for k in ("metrics", "results", "scores", "output", "predictions")
        )
        return has_metrics

    @staticmethod
    def _needs_consistency(
        claim_type: str,
        domain: str,
        payload: dict[str, Any],
        lab_context: dict[str, Any] | None,
    ) -> bool:
        """Determine whether a consistency check is warranted.

        Consistency checks are added when:
        - The claim type is in ``_CONSISTENCY_CLAIM_TYPES``, or
        - The claim is submitted within a lab context (lab claims
          should be consistent with prior lab work), or
        - The payload references other claims (``depends_on``).
        """
        if claim_type.lower() in _CONSISTENCY_CLAIM_TYPES:
            return True
        if lab_context and lab_context.get("lab_id"):
            return True
        if payload.get("depends_on"):
            return True
        return False


__all__ = ["VerificationStep", "VerificationPlan", "VerificationPlanner"]
