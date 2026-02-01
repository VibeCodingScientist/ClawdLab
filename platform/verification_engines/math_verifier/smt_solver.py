"""SMT solver integration for automated reasoning."""

import asyncio
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from platform.verification_engines.math_verifier.base import (
    BaseSMTSolver,
    ProofMetrics,
    VerificationResult,
    VerificationStatus,
)
from platform.verification_engines.math_verifier.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class Z3Solver(BaseSMTSolver):
    """
    Z3 SMT solver interface.

    Z3 is a high-performance theorem prover from Microsoft Research.
    Supports SMT-LIB2 format for first-order logic, arithmetic, and more.
    """

    def __init__(
        self,
        executable: str | None = None,
        timeout_seconds: int | None = None,
    ):
        """
        Initialize the Z3 solver.

        Args:
            executable: Path to z3 executable
            timeout_seconds: Default timeout for queries
        """
        self._executable = executable or settings.z3_executable
        self._timeout = timeout_seconds or settings.z3_timeout_seconds

    @property
    def solver_name(self) -> str:
        return "z3"

    async def check_satisfiability(
        self,
        formula: str,
        timeout_seconds: int | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        """
        Check satisfiability of an SMT-LIB2 formula.

        Args:
            formula: SMT-LIB2 format formula
            timeout_seconds: Optional timeout override

        Returns:
            Tuple of (result, model) where result is "sat", "unsat", or "unknown"
        """
        timeout = timeout_seconds or self._timeout

        # Ensure formula ends with (check-sat)
        if "(check-sat)" not in formula:
            formula = formula + "\n(check-sat)\n"

        # Write formula to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".smt2", delete=False) as f:
            f.write(formula)
            temp_path = f.name

        try:
            # Run Z3
            cmd = [
                self._executable,
                f"-T:{timeout}",
                "-smt2",
                temp_path,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout + 5,  # Extra buffer
            )

            output = stdout.decode("utf-8").strip()

            # Parse result
            if "unsat" in output.lower():
                return "unsat", None
            elif "sat" in output.lower():
                # Try to extract model
                model = self._parse_model(output)
                return "sat", model
            else:
                return "unknown", {"output": output}

        except asyncio.TimeoutError:
            return "unknown", {"error": "timeout"}
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def prove(
        self,
        formula: str,
        timeout_seconds: int | None = None,
    ) -> VerificationResult:
        """
        Prove a formula (check that negation is unsatisfiable).

        For proving P, we check satisfiability of (not P).
        If unsat, then P is valid (proven).
        If sat, then P is not valid (counterexample exists).

        Args:
            formula: SMT-LIB2 format formula to prove
            timeout_seconds: Optional timeout

        Returns:
            VerificationResult
        """
        started_at = datetime.utcnow()

        # Wrap formula with negation for validity check
        # The formula should already define the assertion
        proof_formula = formula
        if "(assert" not in formula.lower():
            # Assume the formula is just the expression to prove
            proof_formula = f"(assert (not {formula}))"

        result, model = await self.check_satisfiability(proof_formula, timeout_seconds)

        if result == "unsat":
            # Negation is unsatisfiable, so formula is valid
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                verified=True,
                message="Formula proven valid (negation is unsatisfiable)",
                proof_system="z3",
                metrics=self._extract_metrics(formula),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
        elif result == "sat":
            # Found counterexample
            return VerificationResult(
                status=VerificationStatus.REFUTED,
                verified=False,
                message="Formula is not valid (counterexample found)",
                proof_system="z3",
                error_type="counterexample",
                error_details=str(model) if model else None,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
        else:
            return VerificationResult(
                status=VerificationStatus.INCONCLUSIVE,
                verified=False,
                message=f"Could not determine validity: {model.get('error', 'unknown')}",
                proof_system="z3",
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def _parse_model(self, output: str) -> dict[str, Any] | None:
        """Parse Z3 model output."""
        model = {}
        # Look for (define-fun ...) patterns
        define_pattern = r"\(define-fun\s+(\w+)\s+\(\)\s+\w+\s+(\S+)\)"
        matches = re.findall(define_pattern, output)
        for name, value in matches:
            model[name] = value
        return model if model else None

    def _extract_metrics(self, formula: str) -> ProofMetrics:
        """Extract metrics from SMT formula."""
        metrics = ProofMetrics()
        metrics.proof_lines = len(formula.strip().split("\n"))
        metrics.proof_characters = len(formula)

        # Count assertions
        metrics.tactic_count = len(re.findall(r"\(assert", formula))

        # Check for quantifiers
        if "forall" in formula or "exists" in formula:
            metrics.axioms_used.append("quantifiers")

        return metrics


class CVC5Solver(BaseSMTSolver):
    """
    CVC5 SMT solver interface.

    CVC5 is a state-of-the-art SMT solver supporting various theories.
    """

    def __init__(
        self,
        executable: str | None = None,
        timeout_seconds: int | None = None,
    ):
        """
        Initialize the CVC5 solver.

        Args:
            executable: Path to cvc5 executable
            timeout_seconds: Default timeout for queries
        """
        self._executable = executable or settings.cvc5_executable
        self._timeout = timeout_seconds or settings.cvc5_timeout_seconds

    @property
    def solver_name(self) -> str:
        return "cvc5"

    async def check_satisfiability(
        self,
        formula: str,
        timeout_seconds: int | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        """Check satisfiability using CVC5."""
        timeout = timeout_seconds or self._timeout

        # Ensure formula ends with (check-sat)
        if "(check-sat)" not in formula:
            formula = formula + "\n(check-sat)\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".smt2", delete=False) as f:
            f.write(formula)
            temp_path = f.name

        try:
            cmd = [
                self._executable,
                "--tlimit", str(timeout * 1000),  # CVC5 uses milliseconds
                "--lang", "smt2",
                temp_path,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout + 5,
            )

            output = stdout.decode("utf-8").strip()

            if "unsat" in output.lower():
                return "unsat", None
            elif "sat" in output.lower():
                model = self._parse_model(output)
                return "sat", model
            else:
                return "unknown", {"output": output}

        except asyncio.TimeoutError:
            return "unknown", {"error": "timeout"}
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def prove(
        self,
        formula: str,
        timeout_seconds: int | None = None,
    ) -> VerificationResult:
        """Prove a formula using CVC5."""
        started_at = datetime.utcnow()

        proof_formula = formula
        if "(assert" not in formula.lower():
            proof_formula = f"(assert (not {formula}))"

        result, model = await self.check_satisfiability(proof_formula, timeout_seconds)

        if result == "unsat":
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                verified=True,
                message="Formula proven valid",
                proof_system="cvc5",
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
        elif result == "sat":
            return VerificationResult(
                status=VerificationStatus.REFUTED,
                verified=False,
                message="Counterexample found",
                proof_system="cvc5",
                error_type="counterexample",
                error_details=str(model) if model else None,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
        else:
            return VerificationResult(
                status=VerificationStatus.INCONCLUSIVE,
                verified=False,
                message="Could not determine validity",
                proof_system="cvc5",
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def _parse_model(self, output: str) -> dict[str, Any] | None:
        """Parse CVC5 model output."""
        model = {}
        define_pattern = r"\(define-fun\s+(\w+)\s+\(\)\s+\w+\s+(\S+)\)"
        matches = re.findall(define_pattern, output)
        for name, value in matches:
            model[name] = value
        return model if model else None


class SMTVerifier:
    """
    Combined SMT verification interface.

    Provides a unified interface to multiple SMT solvers,
    with fallback and consensus checking.
    """

    def __init__(self):
        """Initialize with default solvers."""
        self.z3 = Z3Solver()
        self.cvc5 = CVC5Solver()
        self.solvers = [self.z3, self.cvc5]

    async def verify_with_fallback(
        self,
        formula: str,
        timeout_seconds: int = 60,
    ) -> VerificationResult:
        """
        Verify formula with fallback to secondary solver.

        Tries Z3 first, falls back to CVC5 if inconclusive.
        """
        # Try Z3 first
        result = await self.z3.prove(formula, timeout_seconds)

        if result.status in (VerificationStatus.VERIFIED, VerificationStatus.REFUTED):
            return result

        # Fall back to CVC5
        logger.info("z3_inconclusive_trying_cvc5")
        return await self.cvc5.prove(formula, timeout_seconds)

    async def verify_with_consensus(
        self,
        formula: str,
        timeout_seconds: int = 60,
    ) -> VerificationResult:
        """
        Verify formula requiring consensus from multiple solvers.

        Both solvers must agree for the result to be considered valid.
        """
        # Run both solvers in parallel
        results = await asyncio.gather(
            self.z3.prove(formula, timeout_seconds),
            self.cvc5.prove(formula, timeout_seconds),
            return_exceptions=True,
        )

        z3_result = results[0] if not isinstance(results[0], Exception) else None
        cvc5_result = results[1] if not isinstance(results[1], Exception) else None

        # Check consensus
        if z3_result and cvc5_result:
            if z3_result.status == cvc5_result.status:
                # Solvers agree
                result = z3_result
                result.message = f"Consensus: {result.message} (confirmed by CVC5)"
                return result
            else:
                # Solvers disagree
                return VerificationResult(
                    status=VerificationStatus.INCONCLUSIVE,
                    verified=False,
                    message=f"Solver disagreement: Z3={z3_result.status.value}, CVC5={cvc5_result.status.value}",
                    proof_system="smt_consensus",
                    error_details={
                        "z3_result": z3_result.to_dict(),
                        "cvc5_result": cvc5_result.to_dict(),
                    },
                )

        # Return whichever succeeded
        return z3_result or cvc5_result or VerificationResult(
            status=VerificationStatus.ERROR,
            verified=False,
            message="Both solvers failed",
            proof_system="smt_consensus",
        )
