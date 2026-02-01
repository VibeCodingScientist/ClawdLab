"""Base classes for mathematical proof verification."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class VerificationStatus(str, Enum):
    """Status of a verification attempt."""

    PENDING = "pending"
    RUNNING = "running"
    VERIFIED = "verified"
    REFUTED = "refuted"
    ERROR = "error"
    TIMEOUT = "timeout"
    INCONCLUSIVE = "inconclusive"


@dataclass
class ProofMetrics:
    """Metrics extracted from a mathematical proof."""

    # Size metrics
    proof_lines: int = 0
    proof_characters: int = 0
    tactic_count: int = 0

    # Complexity metrics
    axioms_used: list[str] = field(default_factory=list)
    lemmas_used: list[str] = field(default_factory=list)
    imports_used: list[str] = field(default_factory=list)

    # Performance metrics
    compilation_time_seconds: float = 0.0
    memory_used_mb: float = 0.0

    # Quality indicators
    is_constructive: bool = False
    uses_classical_logic: bool = False
    uses_axiom_of_choice: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "proof_lines": self.proof_lines,
            "proof_characters": self.proof_characters,
            "tactic_count": self.tactic_count,
            "axioms_used": self.axioms_used,
            "lemmas_used": self.lemmas_used,
            "imports_used": self.imports_used,
            "compilation_time_seconds": self.compilation_time_seconds,
            "memory_used_mb": self.memory_used_mb,
            "is_constructive": self.is_constructive,
            "uses_classical_logic": self.uses_classical_logic,
            "uses_axiom_of_choice": self.uses_axiom_of_choice,
        }


@dataclass
class VerificationResult:
    """Result of a verification attempt."""

    status: VerificationStatus
    verified: bool
    message: str

    # Proof details
    proof_system: str
    theorem_name: str | None = None

    # Metrics
    metrics: ProofMetrics | None = None

    # Error information
    error_type: str | None = None
    error_line: int | None = None
    error_details: str | None = None

    # Novelty information
    novelty_score: float | None = None
    similar_theorems: list[dict[str, Any]] = field(default_factory=list)

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "verified": self.verified,
            "message": self.message,
            "proof_system": self.proof_system,
            "theorem_name": self.theorem_name,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "error_type": self.error_type,
            "error_line": self.error_line,
            "error_details": self.error_details,
            "novelty_score": self.novelty_score,
            "similar_theorems": self.similar_theorems,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class BaseProofVerifier(ABC):
    """Abstract base class for proof verifiers."""

    @property
    @abstractmethod
    def proof_system(self) -> str:
        """Return the proof system name."""
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        pass

    @abstractmethod
    async def verify(
        self,
        proof_code: str,
        theorem_statement: str,
        imports: list[str] | None = None,
        **kwargs,
    ) -> VerificationResult:
        """
        Verify a mathematical proof.

        Args:
            proof_code: The proof code to verify
            theorem_statement: The theorem being proven
            imports: Required library imports
            **kwargs: Additional verifier-specific options

        Returns:
            VerificationResult with status and details
        """
        pass

    @abstractmethod
    async def check_syntax(self, proof_code: str) -> tuple[bool, str | None]:
        """
        Check proof syntax without full verification.

        Args:
            proof_code: The proof code to check

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass

    def extract_metrics(self, proof_code: str, result: dict[str, Any]) -> ProofMetrics:
        """
        Extract metrics from a proof.

        Override in subclasses for proof-system-specific extraction.
        """
        metrics = ProofMetrics()
        metrics.proof_lines = len(proof_code.strip().split("\n"))
        metrics.proof_characters = len(proof_code)
        return metrics


class BaseSMTSolver(ABC):
    """Abstract base class for SMT solvers."""

    @property
    @abstractmethod
    def solver_name(self) -> str:
        """Return the solver name."""
        pass

    @abstractmethod
    async def check_satisfiability(
        self,
        formula: str,
        timeout_seconds: int | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        """
        Check satisfiability of an SMT formula.

        Args:
            formula: SMT-LIB2 format formula
            timeout_seconds: Optional timeout

        Returns:
            Tuple of (result, model) where result is "sat", "unsat", or "unknown"
        """
        pass

    @abstractmethod
    async def prove(
        self,
        formula: str,
        timeout_seconds: int | None = None,
    ) -> VerificationResult:
        """
        Prove a formula (check that negation is unsatisfiable).

        Args:
            formula: SMT-LIB2 format formula to prove
            timeout_seconds: Optional timeout

        Returns:
            VerificationResult
        """
        pass
