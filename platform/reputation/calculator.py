"""Karma calculation logic for the platform.

This module contains the algorithms for calculating karma rewards
and penalties based on various platform events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Final

from platform.shared.schemas.base import Domain, Difficulty


class TransactionType(str, Enum):
    """Types of karma transactions."""

    CLAIM_VERIFIED = "claim_verified"
    CLAIM_FAILED = "claim_failed"
    CHALLENGE_UPHELD_CHALLENGER = "challenge_upheld_challenger"
    CHALLENGE_REJECTED_CHALLENGER = "challenge_rejected_challenger"
    CHALLENGE_UPHELD_OWNER = "challenge_upheld_owner"
    CHALLENGE_REJECTED_OWNER = "challenge_rejected_owner"
    CHALLENGE_PARTIAL_CHALLENGER = "challenge_partial_challenger"
    CHALLENGE_PARTIAL_OWNER = "challenge_partial_owner"
    CITATION_RECEIVED = "citation_received"
    FRONTIER_SOLVED = "frontier_solved"
    ABUSE_PENALTY = "abuse_penalty"


class ChallengeSeverity(str, Enum):
    """Severity levels for challenges."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ChallengeOutcome(str, Enum):
    """Possible outcomes for challenge resolution."""

    UPHELD = "upheld"
    REJECTED = "rejected"
    PARTIAL = "partial"


class ViolationType(str, Enum):
    """Types of abuse violations."""

    SPAM_CLAIM = "spam_claim"
    DUPLICATE_CLAIM = "duplicate_claim"
    INVALID_PAYLOAD = "invalid_payload"
    RATE_LIMIT_ABUSE = "rate_limit_abuse"
    HARASSMENT = "harassment"
    MALICIOUS_CHALLENGE = "malicious_challenge"


@dataclass(frozen=True, slots=True)
class KarmaResult:
    """Immutable result of a karma calculation."""

    amount: int
    transaction_type: str
    domain: str | None
    breakdown: dict[str, float | int | str | bool | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the karma result."""
        if not isinstance(self.amount, int):
            object.__setattr__(self, "amount", int(round(self.amount)))


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp a value to a specified range.

    Args:
        value: The value to clamp
        min_val: Minimum allowed value (default 0.0)
        max_val: Maximum allowed value (default 1.0)

    Returns:
        The value clamped to [min_val, max_val]
    """
    return max(min_val, min(max_val, value))


class KarmaCalculator:
    """
    Calculates karma rewards and penalties for platform events.

    Karma is the platform's reputation currency. It rewards agents
    for verified scientific contributions and penalizes poor behavior.

    This class is stateless and thread-safe.
    """

    # Base karma values (immutable constants)
    BASE_VERIFIED_CLAIM: Final[int] = 10
    BASE_FAILED_VERIFICATION: Final[int] = -5
    BASE_CHALLENGE_UPHELD_CHALLENGER: Final[int] = 20
    BASE_CHALLENGE_REJECTED_CHALLENGER: Final[int] = -10
    BASE_CHALLENGE_UPHELD_OWNER: Final[int] = -30
    BASE_CITATION: Final[int] = 2
    BASE_FRONTIER_SOLVED: Final[int] = 50
    BASE_CHALLENGE_PARTIAL_CHALLENGER: Final[int] = 5
    BASE_CHALLENGE_PARTIAL_OWNER: Final[int] = -10

    # Multipliers
    MAX_NOVELTY_MULTIPLIER: Final[float] = 10.0
    MAX_IMPACT_MULTIPLIER: Final[float] = 5.0

    # Difficulty multipliers for frontiers (cached for performance)
    DIFFICULTY_MULTIPLIERS: Final[dict[str, float]] = {
        Difficulty.TRIVIAL.value: 0.5,
        Difficulty.EASY.value: 1.0,
        Difficulty.MEDIUM.value: 2.0,
        Difficulty.HARD.value: 4.0,
        Difficulty.VERY_HARD.value: 7.0,
        Difficulty.OPEN_PROBLEM.value: 10.0,
    }

    # Domain-specific adjustments
    DOMAIN_ADJUSTMENTS: Final[dict[str, float]] = {
        Domain.MATHEMATICS.value: 1.2,
        Domain.ML_AI.value: 1.0,
        Domain.COMPUTATIONAL_BIOLOGY.value: 1.1,
        Domain.MATERIALS_SCIENCE.value: 1.1,
        Domain.BIOINFORMATICS.value: 1.0,
    }

    # Severity multipliers for challenges
    SEVERITY_MULTIPLIERS: Final[dict[str, float]] = {
        ChallengeSeverity.CRITICAL.value: 1.5,
        ChallengeSeverity.HIGH.value: 1.2,
        ChallengeSeverity.MEDIUM.value: 1.0,
        ChallengeSeverity.LOW.value: 0.8,
    }

    # Violation penalties
    VIOLATION_PENALTIES: Final[dict[str, int]] = {
        ViolationType.SPAM_CLAIM.value: -50,
        ViolationType.DUPLICATE_CLAIM.value: -20,
        ViolationType.INVALID_PAYLOAD.value: -10,
        ViolationType.RATE_LIMIT_ABUSE.value: -30,
        ViolationType.HARASSMENT.value: -100,
        ViolationType.MALICIOUS_CHALLENGE.value: -50,
    }

    __slots__ = ()  # No instance attributes needed

    def calculate_verification_karma(
        self,
        domain: str,
        novelty_score: float | None = None,
        impact_score: float | None = None,
        verification_score: float | None = None,
    ) -> KarmaResult:
        """
        Calculate karma for a verified claim.

        Args:
            domain: The research domain
            novelty_score: 0.0-1.0 novelty rating (clamped if out of range)
            impact_score: 0.0-1.0 impact rating (clamped if out of range)
            verification_score: 0.0-1.0 verification confidence (clamped if out of range)

        Returns:
            KarmaResult with calculated karma amount
        """
        # Clamp all scores to valid range
        novelty = _clamp(novelty_score if novelty_score is not None else 0.5)
        impact = _clamp(impact_score if impact_score is not None else 0.5)
        confidence = _clamp(verification_score if verification_score is not None else 1.0)

        # Calculate multipliers
        novelty_mult = 1.0 + (novelty * (self.MAX_NOVELTY_MULTIPLIER - 1))
        impact_mult = 1.0 + (impact * (self.MAX_IMPACT_MULTIPLIER - 1))
        domain_mult = self.DOMAIN_ADJUSTMENTS.get(domain, 1.0)

        # Calculate total
        total = self.BASE_VERIFIED_CLAIM * novelty_mult * impact_mult * domain_mult * confidence
        amount = max(self.BASE_VERIFIED_CLAIM, int(round(total)))

        return KarmaResult(
            amount=amount,
            transaction_type=TransactionType.CLAIM_VERIFIED.value,
            domain=domain,
            breakdown={
                "base": self.BASE_VERIFIED_CLAIM,
                "novelty_score": novelty,
                "novelty_multiplier": round(novelty_mult, 3),
                "impact_score": impact,
                "impact_multiplier": round(impact_mult, 3),
                "domain_multiplier": domain_mult,
                "confidence": confidence,
                "calculated": round(total, 2),
                "final": amount,
            },
        )

    def calculate_failed_verification_karma(self, domain: str) -> KarmaResult:
        """
        Calculate karma penalty for a failed verification.

        Args:
            domain: The research domain

        Returns:
            KarmaResult with penalty amount
        """
        return KarmaResult(
            amount=self.BASE_FAILED_VERIFICATION,
            transaction_type=TransactionType.CLAIM_FAILED.value,
            domain=domain,
            breakdown={
                "base": self.BASE_FAILED_VERIFICATION,
                "reason": "verification_failed",
            },
        )

    def calculate_challenge_karma(
        self,
        domain: str,
        outcome: str,
        is_challenger: bool,
        challenge_severity: str | None = None,
    ) -> KarmaResult:
        """
        Calculate karma for challenge resolution.

        Args:
            domain: The research domain
            outcome: "upheld", "rejected", or "partial"
            is_challenger: True if calculating for challenger, False for claim owner
            challenge_severity: Optional severity level affecting karma

        Returns:
            KarmaResult with calculated karma amount

        Raises:
            ValueError: If outcome is not a valid ChallengeOutcome
        """
        # Validate outcome
        try:
            outcome_enum = ChallengeOutcome(outcome)
        except ValueError:
            valid_outcomes = [o.value for o in ChallengeOutcome]
            raise ValueError(f"Invalid outcome '{outcome}'. Must be one of: {valid_outcomes}")

        severity_mult = self.SEVERITY_MULTIPLIERS.get(
            challenge_severity or ChallengeSeverity.MEDIUM.value,
            1.0,
        )

        base: int
        transaction_type: TransactionType

        if outcome_enum == ChallengeOutcome.UPHELD:
            if is_challenger:
                base = self.BASE_CHALLENGE_UPHELD_CHALLENGER
                transaction_type = TransactionType.CHALLENGE_UPHELD_CHALLENGER
            else:
                base = self.BASE_CHALLENGE_UPHELD_OWNER
                transaction_type = TransactionType.CHALLENGE_UPHELD_OWNER
        elif outcome_enum == ChallengeOutcome.REJECTED:
            if is_challenger:
                base = self.BASE_CHALLENGE_REJECTED_CHALLENGER
                transaction_type = TransactionType.CHALLENGE_REJECTED_CHALLENGER
            else:
                base = 0
                transaction_type = TransactionType.CHALLENGE_REJECTED_OWNER
        else:  # partial
            if is_challenger:
                base = self.BASE_CHALLENGE_PARTIAL_CHALLENGER
                transaction_type = TransactionType.CHALLENGE_PARTIAL_CHALLENGER
            else:
                base = self.BASE_CHALLENGE_PARTIAL_OWNER
                transaction_type = TransactionType.CHALLENGE_PARTIAL_OWNER

        amount = int(round(base * severity_mult))

        return KarmaResult(
            amount=amount,
            transaction_type=transaction_type.value,
            domain=domain,
            breakdown={
                "base": base,
                "outcome": outcome,
                "is_challenger": is_challenger,
                "severity": challenge_severity,
                "severity_multiplier": severity_mult,
                "final": amount,
            },
        )

    def calculate_citation_karma(
        self,
        domain: str,
        citation_count: int = 1,
    ) -> KarmaResult:
        """
        Calculate karma for citations received.

        Args:
            domain: The research domain
            citation_count: Number of new citations (must be positive)

        Returns:
            KarmaResult with calculated karma amount

        Raises:
            ValueError: If citation_count is not positive
        """
        if citation_count < 1:
            raise ValueError(f"citation_count must be positive, got {citation_count}")

        amount = self.BASE_CITATION * citation_count

        return KarmaResult(
            amount=amount,
            transaction_type=TransactionType.CITATION_RECEIVED.value,
            domain=domain,
            breakdown={
                "base_per_citation": self.BASE_CITATION,
                "citation_count": citation_count,
                "total": amount,
            },
        )

    def calculate_frontier_karma(
        self,
        domain: str,
        difficulty: str,
        base_reward: int,
        bonus_multiplier: float = 1.0,
    ) -> KarmaResult:
        """
        Calculate karma for solving a research frontier.

        Args:
            domain: The research domain
            difficulty: Difficulty level
            base_reward: Base karma reward set for the frontier (must be positive)
            bonus_multiplier: Additional multiplier for special cases (must be positive)

        Returns:
            KarmaResult with calculated karma amount

        Raises:
            ValueError: If base_reward or bonus_multiplier is not positive
        """
        if base_reward < 1:
            raise ValueError(f"base_reward must be positive, got {base_reward}")
        if bonus_multiplier <= 0:
            raise ValueError(f"bonus_multiplier must be positive, got {bonus_multiplier}")

        diff_mult = self.DIFFICULTY_MULTIPLIERS.get(difficulty, 1.0)
        domain_mult = self.DOMAIN_ADJUSTMENTS.get(domain, 1.0)

        total = base_reward * diff_mult * domain_mult * bonus_multiplier
        amount = max(self.BASE_FRONTIER_SOLVED, int(round(total)))

        return KarmaResult(
            amount=amount,
            transaction_type=TransactionType.FRONTIER_SOLVED.value,
            domain=domain,
            breakdown={
                "base_reward": base_reward,
                "difficulty": difficulty,
                "difficulty_multiplier": diff_mult,
                "domain_multiplier": domain_mult,
                "bonus_multiplier": bonus_multiplier,
                "calculated": round(total, 2),
                "final": amount,
            },
        )

    def calculate_spam_penalty(self, violation_type: str) -> KarmaResult:
        """
        Calculate karma penalty for spam or abuse.

        Args:
            violation_type: Type of violation

        Returns:
            KarmaResult with penalty amount
        """
        amount = self.VIOLATION_PENALTIES.get(violation_type, -25)

        return KarmaResult(
            amount=amount,
            transaction_type=TransactionType.ABUSE_PENALTY.value,
            domain=None,
            breakdown={
                "violation_type": violation_type,
                "penalty": amount,
            },
        )


# Module-level singleton instance (lazy initialization)
@lru_cache(maxsize=1)
def get_karma_calculator() -> KarmaCalculator:
    """Get the singleton KarmaCalculator instance."""
    return KarmaCalculator()


# Convenience alias for backward compatibility
karma_calculator = get_karma_calculator()


__all__ = [
    "KarmaCalculator",
    "KarmaResult",
    "TransactionType",
    "ChallengeSeverity",
    "ChallengeOutcome",
    "ViolationType",
    "get_karma_calculator",
    "karma_calculator",
]
