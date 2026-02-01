"""Lean 4 proof verifier implementation."""

import asyncio
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from platform.verification_engines.math_verifier.base import (
    BaseProofVerifier,
    ProofMetrics,
    VerificationResult,
    VerificationStatus,
)
from platform.verification_engines.math_verifier.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class LeanVerifier(BaseProofVerifier):
    """
    Lean 4 proof verifier with Mathlib support.

    Verifies formal proofs by compiling them with the Lean 4 compiler
    and checking for errors. Supports Mathlib imports.
    """

    def __init__(
        self,
        lean_executable: str | None = None,
        timeout_seconds: int | None = None,
        memory_limit_mb: int | None = None,
        mathlib_path: str | None = None,
        use_sandbox: bool = True,
    ):
        """
        Initialize the Lean verifier.

        Args:
            lean_executable: Path to lake/lean executable
            timeout_seconds: Timeout for compilation
            memory_limit_mb: Memory limit for compilation
            mathlib_path: Path to Mathlib installation
            use_sandbox: Whether to use Singularity sandbox
        """
        self._lean_executable = lean_executable or settings.lean_executable
        self._timeout = timeout_seconds or settings.lean_timeout_seconds
        self._memory_limit = memory_limit_mb or settings.lean_memory_limit_mb
        self._mathlib_path = mathlib_path or settings.mathlib_path
        self._use_sandbox = use_sandbox and settings.sandbox_enabled

    @property
    def proof_system(self) -> str:
        return "lean4"

    @property
    def supported_extensions(self) -> list[str]:
        return [".lean"]

    async def verify(
        self,
        proof_code: str,
        theorem_statement: str,
        imports: list[str] | None = None,
        **kwargs,
    ) -> VerificationResult:
        """
        Verify a Lean 4 proof.

        Args:
            proof_code: Complete Lean 4 code including the proof
            theorem_statement: The theorem statement (for documentation)
            imports: Required Mathlib imports
            **kwargs: Additional options

        Returns:
            VerificationResult with verification status and details
        """
        started_at = datetime.utcnow()

        try:
            # Create temporary project directory
            with tempfile.TemporaryDirectory(prefix="lean_verify_") as temp_dir:
                temp_path = Path(temp_dir)

                # Prepare the Lean project
                await self._setup_lean_project(temp_path, proof_code, imports)

                # Run verification
                success, output, error, exec_time = await self._run_lean_build(temp_path)

                # Parse results
                if success:
                    metrics = self._extract_lean_metrics(proof_code, output)
                    metrics.compilation_time_seconds = exec_time

                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        verified=True,
                        message="Proof verified successfully",
                        proof_system=self.proof_system,
                        theorem_name=self._extract_theorem_name(proof_code),
                        metrics=metrics,
                        started_at=started_at,
                        completed_at=datetime.utcnow(),
                    )
                else:
                    error_info = self._parse_lean_error(error or output)
                    return VerificationResult(
                        status=VerificationStatus.REFUTED,
                        verified=False,
                        message=f"Proof verification failed: {error_info['message']}",
                        proof_system=self.proof_system,
                        theorem_name=self._extract_theorem_name(proof_code),
                        error_type=error_info["type"],
                        error_line=error_info.get("line"),
                        error_details=error_info.get("details"),
                        started_at=started_at,
                        completed_at=datetime.utcnow(),
                    )

        except asyncio.TimeoutError:
            return VerificationResult(
                status=VerificationStatus.TIMEOUT,
                verified=False,
                message=f"Verification timed out after {self._timeout} seconds",
                proof_system=self.proof_system,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
        except Exception as e:
            logger.exception("lean_verification_error")
            return VerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message=f"Verification error: {str(e)}",
                proof_system=self.proof_system,
                error_type="internal_error",
                error_details=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    async def check_syntax(self, proof_code: str) -> tuple[bool, str | None]:
        """Check Lean syntax without full verification."""
        # Basic syntax checks
        errors = []

        # Check for balanced parentheses/brackets
        stack = []
        brackets = {"(": ")", "[": "]", "{": "}"}
        for i, char in enumerate(proof_code):
            if char in brackets:
                stack.append((char, i))
            elif char in brackets.values():
                if not stack:
                    errors.append(f"Unmatched closing bracket at position {i}")
                else:
                    opening, _ = stack.pop()
                    if brackets[opening] != char:
                        errors.append(f"Mismatched bracket at position {i}")

        if stack:
            errors.append(f"Unclosed bracket at position {stack[-1][1]}")

        # Check for common keywords
        if "theorem" not in proof_code and "lemma" not in proof_code and "def" not in proof_code:
            errors.append("No theorem, lemma, or definition found")

        if errors:
            return False, "; ".join(errors)
        return True, None

    async def _setup_lean_project(
        self,
        project_dir: Path,
        proof_code: str,
        imports: list[str] | None,
    ) -> None:
        """Set up a temporary Lean project with the proof."""
        # Create lakefile.lean
        lakefile_content = """
import Lake
open Lake DSL

package proof_verification where
  -- Configuration

@[default_target]
lean_lib ProofVerification where
  -- Library configuration

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git"
"""
        (project_dir / "lakefile.lean").write_text(lakefile_content)

        # Create lean-toolchain
        (project_dir / "lean-toolchain").write_text("leanprover/lean4:v4.3.0")

        # Build import statements
        import_statements = []
        if imports:
            for imp in imports:
                if not imp.startswith("import "):
                    imp = f"import {imp}"
                import_statements.append(imp)
        else:
            # Default Mathlib imports
            import_statements = [
                "import Mathlib.Tactic",
                "import Mathlib.Data.Nat.Basic",
            ]

        # Create the proof file
        full_code = "\n".join(import_statements) + "\n\n" + proof_code
        proof_dir = project_dir / "ProofVerification"
        proof_dir.mkdir(exist_ok=True)
        (proof_dir / "Main.lean").write_text(full_code)

    async def _run_lean_build(
        self,
        project_dir: Path,
    ) -> tuple[bool, str, str, float]:
        """
        Run Lean build in the project directory.

        Returns:
            Tuple of (success, stdout, stderr, execution_time)
        """
        start_time = datetime.utcnow()

        if self._use_sandbox and settings.singularity_image:
            cmd = [
                "singularity",
                "exec",
                "--bind", f"{project_dir}:/workspace",
                "--pwd", "/workspace",
                settings.singularity_image,
                "lake", "build",
            ]
        else:
            cmd = [self._lean_executable, "build"]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(project_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **os.environ,
                    "LEAN_MEMORY_LIMIT": str(self._memory_limit * 1024 * 1024),
                },
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self._timeout,
            )

            exec_time = (datetime.utcnow() - start_time).total_seconds()

            return (
                process.returncode == 0,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
                exec_time,
            )

        except asyncio.TimeoutError:
            process.kill()
            raise

    def _extract_lean_metrics(self, proof_code: str, output: str) -> ProofMetrics:
        """Extract metrics from Lean proof and output."""
        metrics = ProofMetrics()

        # Basic metrics
        lines = proof_code.strip().split("\n")
        metrics.proof_lines = len(lines)
        metrics.proof_characters = len(proof_code)

        # Count tactics (common Lean 4 tactics)
        tactic_patterns = [
            r"\bby\b", r"\bsimp\b", r"\brfl\b", r"\bexact\b",
            r"\bapply\b", r"\bintro\b", r"\bhave\b", r"\blet\b",
            r"\binduction\b", r"\bcases\b", r"\bobtain\b",
            r"\brcases\b", r"\bext\b", r"\bfunext\b",
        ]
        metrics.tactic_count = sum(
            len(re.findall(pattern, proof_code, re.IGNORECASE))
            for pattern in tactic_patterns
        )

        # Extract imports
        import_pattern = r"import\s+([\w\.]+)"
        metrics.imports_used = re.findall(import_pattern, proof_code)

        # Check for classical logic markers
        metrics.uses_classical_logic = any(
            marker in proof_code.lower()
            for marker in ["classical", "em", "bycontradiction", "bycases"]
        )

        # Check for axiom of choice
        metrics.uses_axiom_of_choice = "choice" in proof_code.lower()

        # Constructive check (simple heuristic)
        metrics.is_constructive = not metrics.uses_classical_logic and not metrics.uses_axiom_of_choice

        return metrics

    def _extract_theorem_name(self, proof_code: str) -> str | None:
        """Extract the theorem name from the proof code."""
        patterns = [
            r"theorem\s+(\w+)",
            r"lemma\s+(\w+)",
            r"def\s+(\w+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, proof_code)
            if match:
                return match.group(1)
        return None

    def _parse_lean_error(self, error_output: str) -> dict[str, Any]:
        """Parse Lean error output to extract structured error info."""
        result = {
            "type": "compilation_error",
            "message": error_output[:500] if len(error_output) > 500 else error_output,
            "details": error_output,
        }

        # Try to extract line number
        line_match = re.search(r":(\d+):", error_output)
        if line_match:
            result["line"] = int(line_match.group(1))

        # Categorize error type
        error_lower = error_output.lower()
        if "type mismatch" in error_lower:
            result["type"] = "type_mismatch"
        elif "unknown identifier" in error_lower:
            result["type"] = "unknown_identifier"
        elif "unsolved goals" in error_lower:
            result["type"] = "incomplete_proof"
        elif "timeout" in error_lower:
            result["type"] = "timeout"
        elif "memory" in error_lower:
            result["type"] = "memory_exceeded"

        return result


class CoqVerifier(BaseProofVerifier):
    """
    Coq proof verifier.

    Placeholder for Coq verification support.
    """

    @property
    def proof_system(self) -> str:
        return "coq"

    @property
    def supported_extensions(self) -> list[str]:
        return [".v"]

    async def verify(
        self,
        proof_code: str,
        theorem_statement: str,
        imports: list[str] | None = None,
        **kwargs,
    ) -> VerificationResult:
        """Verify a Coq proof."""
        # Placeholder - would implement Coq verification
        return VerificationResult(
            status=VerificationStatus.ERROR,
            verified=False,
            message="Coq verification not yet implemented",
            proof_system=self.proof_system,
        )

    async def check_syntax(self, proof_code: str) -> tuple[bool, str | None]:
        """Check Coq syntax."""
        # Basic check for Coq structure
        if "Theorem" in proof_code or "Lemma" in proof_code or "Definition" in proof_code:
            if "Qed" in proof_code or "Defined" in proof_code:
                return True, None
        return False, "Missing Theorem/Lemma and Qed/Defined"
