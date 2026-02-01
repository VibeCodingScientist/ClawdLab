"""Verification badge calculator.

After all verification steps complete (domain, robustness, consistency),
the badge calculator combines the results into a single
``VerificationBadge`` -- a traffic-light indicator that agents and
users can use to quickly assess claim trustworthiness.

Badge criteria
--------------

**GREEN** -- High confidence.
    * Domain verification passed.
    * Stability score >= 0.8 (robust).
    * Consistent with existing knowledge (no significant contradictions).

**AMBER** -- Moderate confidence, review recommended.
    * Domain verification passed, **but**:
      - Stability score < 0.8 (fragile), **or**
      - Contradictions found in the knowledge base.

**RED** -- Low confidence.
    * Domain verification failed, **or**
    * Stability score < 0.3 (very fragile).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Badge enum
# ---------------------------------------------------------------------------


class VerificationBadge(str, Enum):
    """Traffic-light verification badge."""

    GREEN = "green"
    AMBER = "amber"
    RED = "red"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class BadgeResult:
    """Outcome of badge calculation.

    Attributes:
        badge: The assigned verification badge colour.
        verification_passed: Whether domain verification passed.
        stability_score: Robustness stability score (0--1).
        consistency_score: Consistency confidence score (0--1).
        details: Breakdown of contributing factors.
    """

    badge: VerificationBadge
    verification_passed: bool
    stability_score: float
    consistency_score: float
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Robustness
STABILITY_HIGH: float = 0.8      # >= this is "robust"
STABILITY_VERY_LOW: float = 0.3  # < this is "very fragile" -> RED

# Consistency
CONSISTENCY_HIGH: float = 0.7    # >= this is "consistent"


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------


class BadgeCalculator:
    """Combines verification, robustness, and consistency into a badge.

    Usage::

        calc = BadgeCalculator()
        result = calc.calculate_badge(
            verification_passed=True,
            stability_score=0.85,
            consistent=True,
            contradictions=[],
        )
        print(result.badge)  # VerificationBadge.GREEN
    """

    def calculate_badge(
        self,
        verification_passed: bool,
        stability_score: float,
        consistent: bool,
        contradictions: list[dict[str, Any]] | None = None,
        consistency_score: float | None = None,
    ) -> BadgeResult:
        """Calculate the verification badge for a claim.

        Args:
            verification_passed: Whether domain verification passed.
            stability_score: Robustness score in [0, 1].
            consistent: Whether the consistency check passed.
            contradictions: List of contradiction detail dicts (may be
                empty).
            consistency_score: Optional explicit consistency confidence.
                If not provided it is derived from ``consistent`` and
                the number of contradictions.

        Returns:
            ``BadgeResult`` with badge colour and supporting details.
        """
        if contradictions is None:
            contradictions = []

        # Derive consistency score if not explicitly provided.
        if consistency_score is None:
            if consistent and not contradictions:
                consistency_score = 1.0
            elif consistent:
                consistency_score = max(0.7, 1.0 - 0.1 * len(contradictions))
            else:
                consistency_score = max(0.0, 0.5 - 0.1 * len(contradictions))

        # ---- Determine badge ----

        # RED: verification failed or extremely fragile
        if not verification_passed:
            badge = VerificationBadge.RED
            reason = "Domain verification failed"
        elif stability_score < STABILITY_VERY_LOW:
            badge = VerificationBadge.RED
            reason = (
                f"Very fragile result (stability={stability_score:.2f}, "
                f"threshold={STABILITY_VERY_LOW})"
            )
        # GREEN: passed, robust, and consistent
        elif stability_score >= STABILITY_HIGH and consistent:
            badge = VerificationBadge.GREEN
            reason = "Verified, robust, and consistent"
        # AMBER: passed but fragile or contradictory
        else:
            amber_reasons: list[str] = []
            if stability_score < STABILITY_HIGH:
                amber_reasons.append(
                    f"fragile (stability={stability_score:.2f}, "
                    f"threshold={STABILITY_HIGH})"
                )
            if not consistent:
                amber_reasons.append(
                    f"inconsistent ({len(contradictions)} contradiction(s))"
                )
            badge = VerificationBadge.AMBER
            reason = "Verified but " + " and ".join(amber_reasons)

        details = {
            "reason": reason,
            "thresholds": {
                "stability_high": STABILITY_HIGH,
                "stability_very_low": STABILITY_VERY_LOW,
                "consistency_high": CONSISTENCY_HIGH,
            },
            "inputs": {
                "verification_passed": verification_passed,
                "stability_score": stability_score,
                "consistent": consistent,
                "contradiction_count": len(contradictions),
                "consistency_score": consistency_score,
            },
        }

        if contradictions:
            details["contradictions"] = contradictions

        result = BadgeResult(
            badge=badge,
            verification_passed=verification_passed,
            stability_score=round(stability_score, 4),
            consistency_score=round(consistency_score, 4),
            details=details,
        )

        logger.info(
            "badge_calculated",
            badge=badge.value,
            verification_passed=verification_passed,
            stability_score=round(stability_score, 4),
            consistency_score=round(consistency_score, 4),
            reason=reason,
        )

        return result


__all__ = ["VerificationBadge", "BadgeResult", "BadgeCalculator"]
