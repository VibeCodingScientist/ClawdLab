"""Base class for cross-cutting verifiers that apply to any domain."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CrossCuttingResult:
    """Result from a single cross-cutting verifier."""
    verifier_name: str
    score: float          # 0.0-1.0
    weight: float         # contribution to final merged score
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    compute_time_seconds: float = 0.0


class CrossCuttingVerifier:
    """Abstract base for verifiers that enhance every domain adapter.

    Unlike domain adapters (which run for a single domain), cross-cutting
    verifiers apply to any task result that has the relevant data
    (citations, statistical claims, code repos, raw data, etc.).
    """
    name: str = ""
    default_weight: float = 0.10
    requires_docker: bool = False

    def is_applicable(self, task_result: dict, task_metadata: dict) -> bool:
        """Return True if this verifier should run on this job."""
        raise NotImplementedError

    async def verify(self, task_result: dict, task_metadata: dict) -> CrossCuttingResult:
        """Run verification and return result."""
        raise NotImplementedError
