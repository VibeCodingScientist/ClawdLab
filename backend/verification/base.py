"""Base verification interface. All domain adapters implement this."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class VerificationBadge(str, enum.Enum):
    GREEN = "green"    # score >= 0.8 — strong verification
    AMBER = "amber"    # score >= 0.5 — partial / warnings
    RED = "red"        # score <  0.5 — failed


@dataclass
class VerificationResult:
    """Returned by every domain adapter."""
    passed: bool
    score: float                          # 0.0–1.0
    badge: VerificationBadge              # derived from score
    domain: str                           # echo back
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    compute_time_seconds: float = 0.0

    @staticmethod
    def score_to_badge(score: float) -> VerificationBadge:
        if score >= 0.8:
            return VerificationBadge.GREEN
        elif score >= 0.5:
            return VerificationBadge.AMBER
        return VerificationBadge.RED

    @staticmethod
    def fail(domain: str, errors: list[str]) -> VerificationResult:
        return VerificationResult(
            passed=False, score=0.0,
            badge=VerificationBadge.RED,
            domain=domain, errors=errors,
        )


class VerificationAdapter:
    """Abstract base. Subclass per domain."""
    domain: str = ""

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        """
        Args:
            task_result:   The JSONB from task.result (agent's submitted work)
            task_metadata: {task_type, domain, title, description, lab_slug}
        Returns:
            VerificationResult
        """
        raise NotImplementedError
