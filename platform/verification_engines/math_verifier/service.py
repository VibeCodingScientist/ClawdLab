"""Main mathematics verification service."""

from datetime import datetime
from typing import Any

from platform.verification_engines.math_verifier.base import (
    ProofMetrics,
    VerificationResult,
    VerificationStatus,
)
from platform.verification_engines.math_verifier.config import PROOF_SYSTEMS, get_settings
from platform.verification_engines.math_verifier.lean_verifier import CoqVerifier, LeanVerifier
from platform.verification_engines.math_verifier.novelty_checker import TheoremNoveltyChecker
from platform.verification_engines.math_verifier.smt_solver import SMTVerifier
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class MathVerificationService:
    """
    Main service for mathematical proof verification.

    Orchestrates verification across multiple proof systems:
    - Lean 4 (with Mathlib support)
    - Coq
    - SMT solvers (Z3, CVC5)

    Also performs novelty checking to detect prior art.
    """

    def __init__(self):
        """Initialize the verification service with all components."""
        self.lean_verifier = LeanVerifier()
        self.coq_verifier = CoqVerifier()
        self.smt_verifier = SMTVerifier()
        self.novelty_checker = TheoremNoveltyChecker()

        # Map proof systems to verifiers
        self._verifiers = {
            "lean4": self.lean_verifier,
            "coq": self.coq_verifier,
            "z3": self.smt_verifier.z3,
            "cvc5": self.smt_verifier.cvc5,
        }

    async def verify_claim(
        self,
        claim_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Verify a mathematical claim.

        This is the main entry point called by the verification dispatcher.

        Args:
            claim_id: ID of the claim being verified
            payload: Claim payload containing proof details

        Returns:
            Verification result dictionary
        """
        started_at = datetime.utcnow()

        # Extract payload fields
        proof_system = payload.get("proof_system", "lean4")
        theorem_statement = payload.get("theorem_statement", "")
        proof_code = payload.get("proof_code", "")
        imports = payload.get("imports", [])
        axioms_used = payload.get("axioms_used", [])

        logger.info(
            "math_verification_started",
            claim_id=claim_id,
            proof_system=proof_system,
        )

        # Validate proof system
        if proof_system not in PROOF_SYSTEMS:
            return self._error_result(
                f"Unsupported proof system: {proof_system}",
                started_at,
            )

        # Step 1: Syntax check
        syntax_result = await self._check_syntax(proof_system, proof_code)
        if not syntax_result["valid"]:
            return {
                "verified": False,
                "status": "refuted",
                "message": f"Syntax error: {syntax_result['error']}",
                "proof_system": proof_system,
                "error_type": "syntax_error",
                "started_at": started_at.isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
            }

        # Step 2: Verify the proof
        verification_result = await self._verify_proof(
            proof_system=proof_system,
            proof_code=proof_code,
            theorem_statement=theorem_statement,
            imports=imports,
        )

        # Step 3: Check novelty (only if proof verified)
        novelty_result = None
        if verification_result.verified and settings.novelty_check_enabled:
            novelty_result = await self.novelty_checker.check_novelty(
                theorem_statement=theorem_statement,
                proof_code=proof_code,
            )
            verification_result.novelty_score = novelty_result.novelty_score
            verification_result.similar_theorems = [
                t.to_dict() for t in novelty_result.similar_theorems
            ]

        # Step 4: Validate axioms used
        if axioms_used:
            axiom_validation = self._validate_axioms(axioms_used)
            if verification_result.metrics:
                verification_result.metrics.axioms_used = axioms_used

        # Build final result
        result = verification_result.to_dict()
        result["claim_id"] = claim_id
        result["proof_system"] = proof_system

        if novelty_result:
            result["novelty"] = {
                "is_novel": novelty_result.is_novel,
                "novelty_score": novelty_result.novelty_score,
                "analysis": novelty_result.analysis,
                "similar_count": len(novelty_result.similar_theorems),
            }

        logger.info(
            "math_verification_completed",
            claim_id=claim_id,
            verified=verification_result.verified,
            proof_system=proof_system,
        )

        return result

    async def _check_syntax(
        self,
        proof_system: str,
        proof_code: str,
    ) -> dict[str, Any]:
        """Check proof syntax."""
        verifier = self._verifiers.get(proof_system)
        if not verifier:
            return {"valid": False, "error": f"No verifier for {proof_system}"}

        if hasattr(verifier, "check_syntax"):
            valid, error = await verifier.check_syntax(proof_code)
            return {"valid": valid, "error": error}

        return {"valid": True, "error": None}

    async def _verify_proof(
        self,
        proof_system: str,
        proof_code: str,
        theorem_statement: str,
        imports: list[str],
    ) -> VerificationResult:
        """Verify the proof using appropriate verifier."""
        # Get the verifier
        if proof_system in ("z3", "cvc5"):
            # SMT verification
            return await self.smt_verifier.verify_with_fallback(
                proof_code,
                timeout_seconds=settings.z3_timeout_seconds,
            )
        elif proof_system == "lean4":
            return await self.lean_verifier.verify(
                proof_code=proof_code,
                theorem_statement=theorem_statement,
                imports=imports,
            )
        elif proof_system == "coq":
            return await self.coq_verifier.verify(
                proof_code=proof_code,
                theorem_statement=theorem_statement,
                imports=imports,
            )
        else:
            return VerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message=f"Verifier not implemented for {proof_system}",
                proof_system=proof_system,
            )

    def _validate_axioms(self, axioms: list[str]) -> dict[str, Any]:
        """Validate that used axioms are acceptable."""
        # Standard/accepted axioms
        standard_axioms = {
            "propext",  # Propositional extensionality
            "funext",  # Function extensionality
            "quot.sound",  # Quotient soundness
            "classical.choice",  # Classical axiom of choice
            "em",  # Excluded middle
        }

        # Axioms that require extra scrutiny
        scrutiny_axioms = {
            "sorry",  # Incomplete proof
            "axiom",  # Custom axiom
        }

        non_standard = [a for a in axioms if a.lower() not in standard_axioms]
        problematic = [a for a in axioms if a.lower() in scrutiny_axioms]

        return {
            "valid": len(problematic) == 0,
            "non_standard": non_standard,
            "problematic": problematic,
            "message": "Proof contains 'sorry' - incomplete" if "sorry" in problematic else None,
        }

    def _error_result(self, message: str, started_at: datetime) -> dict[str, Any]:
        """Create an error result dictionary."""
        return {
            "verified": False,
            "status": "error",
            "message": message,
            "error_type": "validation_error",
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

    async def verify_quick(
        self,
        proof_system: str,
        proof_code: str,
    ) -> dict[str, Any]:
        """
        Quick verification without novelty checking.

        Useful for testing and development.
        """
        started_at = datetime.utcnow()

        result = await self._verify_proof(
            proof_system=proof_system,
            proof_code=proof_code,
            theorem_statement="",
            imports=[],
        )

        return {
            "verified": result.verified,
            "status": result.status.value,
            "message": result.message,
            "proof_system": proof_system,
            "metrics": result.metrics.to_dict() if result.metrics else None,
            "error": result.error_details,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

    def get_supported_systems(self) -> list[dict[str, Any]]:
        """Get list of supported proof systems."""
        return [
            {
                "id": system_id,
                "name": info["name"],
                "description": info["description"],
                "file_extension": info["file_extension"],
            }
            for system_id, info in PROOF_SYSTEMS.items()
        ]


# Singleton instance for use by verification dispatcher
_service_instance: MathVerificationService | None = None


def get_math_verification_service() -> MathVerificationService:
    """Get or create the math verification service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = MathVerificationService()
    return _service_instance
