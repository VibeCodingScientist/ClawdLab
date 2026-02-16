"""Mathematics verification via Lean 4 + Mathlib in Docker sandbox."""
import asyncio
import tempfile
import time
from pathlib import Path

from backend.verification.base import (
    VerificationAdapter, VerificationResult, VerificationBadge,
)
from backend.logging_config import get_logger

logger = get_logger(__name__)

# Configurable via env
LEAN4_IMAGE = "clawdlab/lean4-mathlib:latest"
LEAN4_TIMEOUT = 300  # 5 min max

COQ_IMAGE = "clawdlab/coq:latest"
COQ_TIMEOUT = 300

ISABELLE_IMAGE = "clawdlab/isabelle:latest"
ISABELLE_TIMEOUT = 300


class Lean4Adapter(VerificationAdapter):
    domain = "mathematics"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        proof_code = task_result.get("proof_code")
        if not proof_code:
            return VerificationResult.fail(self.domain, ["No proof_code in result"])

        claim_type = task_result.get("claim_type", "theorem")
        proof_system = task_result.get("proof_system", "lean4")
        dependencies = task_result.get("dependencies", [])
        statement = task_result.get("statement")

        # Route to proof system
        if proof_system == "coq":
            return await self._verify_coq(task_result)
        elif proof_system == "isabelle":
            return await self._verify_isabelle(task_result)

        # Default: Lean 4
        if claim_type == "theorem":
            return await self._verify_theorem(proof_code, dependencies, statement)
        elif claim_type == "conjecture":
            return await self._verify_conjecture(proof_code, statement)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    async def _verify_theorem(
        self, proof_code: str, dependencies: list[str], statement: str | None
    ) -> VerificationResult:
        """Compile proof in Lean 4 sandbox. Binary pass/fail."""
        start = time.monotonic()

        # Build the full .lean file
        imports = "\n".join(f"import {dep}" for dep in dependencies) if dependencies else "import Mathlib"
        full_code = f"{imports}\n\n{proof_code}"

        with tempfile.TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "Proof.lean"
            proof_path.write_text(full_code)

            # Write minimal lakefile
            lakefile = Path(tmpdir) / "lakefile.lean"
            lakefile.write_text(
                'import Lake\nopen Lake DSL\n'
                'require mathlib from git "https://github.com/leanprover-community/mathlib4"\n'
                'package proof where\n  leanOptions := #[]\n'
                'lean_lib Proof\n'
            )

            # Run in Docker sandbox
            cmd = [
                "docker", "run", "--rm",
                "--network=none",          # No network access
                "--memory=4g",             # Memory cap
                "--cpus=2",                # CPU cap
                "-v", f"{tmpdir}:/workspace:ro",
                "-w", "/workspace",
                LEAN4_IMAGE,
                "lake", "build",
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=LEAN4_TIMEOUT
                )
            except asyncio.TimeoutError:
                return VerificationResult.fail(self.domain, ["Lean 4 compilation timed out (5 min limit)"])

        elapsed = time.monotonic() - start
        stdout_text = stdout.decode(errors="replace")
        stderr_text = stderr.decode(errors="replace")

        if proc.returncode == 0:
            # Parse proof metrics from output
            metrics = self._parse_lean_metrics(stdout_text, stderr_text, full_code)
            return VerificationResult(
                passed=True,
                score=1.0,
                badge=VerificationBadge.GREEN,
                domain=self.domain,
                details={
                    "compiler": "lean4",
                    "compile_time_seconds": round(elapsed, 2),
                    "proof_stats": metrics,
                    "statement": statement,
                },
                compute_time_seconds=elapsed,
            )
        else:
            errors = [line for line in stderr_text.splitlines() if "error" in line.lower()][:10]
            return VerificationResult(
                passed=False,
                score=0.0,
                badge=VerificationBadge.RED,
                domain=self.domain,
                errors=errors or [stderr_text[:500]],
                details={"compiler_output": stderr_text[:2000]},
                compute_time_seconds=elapsed,
            )

    async def _verify_conjecture(self, proof_code: str, statement: str | None) -> VerificationResult:
        """Verify conjecture: check that the formal statement parses."""
        start = time.monotonic()

        if not statement:
            return VerificationResult.fail(self.domain, ["No statement provided for conjecture"])

        with tempfile.TemporaryDirectory() as tmpdir:
            check_path = Path(tmpdir) / "Check.lean"
            check_path.write_text(f"import Mathlib\n\n#check ({statement})")

            cmd = [
                "docker", "run", "--rm", "--network=none", "--memory=2g",
                "-v", f"{tmpdir}:/workspace:ro", "-w", "/workspace",
                LEAN4_IMAGE, "lean", "Check.lean",
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            except asyncio.TimeoutError:
                return VerificationResult.fail(self.domain, ["Statement check timed out"])

        elapsed = time.monotonic() - start
        passed = proc.returncode == 0

        return VerificationResult(
            passed=passed,
            score=0.7 if passed else 0.0,
            badge=VerificationBadge.AMBER if passed else VerificationBadge.RED,
            domain=self.domain,
            details={"claim_type": "conjecture", "statement_valid": passed},
            compute_time_seconds=elapsed,
        )

    def _parse_lean_metrics(self, stdout: str, stderr: str, code: str) -> dict:
        """Extract proof metrics from code + compiler output."""
        lines = code.strip().splitlines()
        tactic_keywords = {"simp", "ring", "linarith", "omega", "norm_num", "exact", "apply",
                           "intro", "cases", "induction", "rfl", "have", "let", "calc", "rw"}
        tactics_used: dict[str, int] = {}
        for line in lines:
            stripped = line.strip()
            for t in tactic_keywords:
                if stripped.startswith(t) or f" {t}" in stripped:
                    tactics_used[t] = tactics_used.get(t, 0) + 1

        return {
            "lines_of_code": len(lines),
            "tactics_used": tactics_used,
            "tactic_count": sum(tactics_used.values()),
        }

    # ------------------------------------------------------------------
    # Coq verification
    # ------------------------------------------------------------------

    async def _verify_coq(self, task_result: dict) -> VerificationResult:
        """Verify proof using Coq in Docker sandbox."""
        start = time.monotonic()

        proof_code = task_result.get("proof_code", "")
        statement = task_result.get("statement")
        dependencies = task_result.get("dependencies", [])

        # Build .v file
        imports = "\n".join(f"Require Import {dep}." for dep in dependencies) if dependencies else ""
        full_code = f"{imports}\n\n{proof_code}" if imports else proof_code

        with tempfile.TemporaryDirectory() as tmpdir:
            proof_path = Path(tmpdir) / "Proof.v"
            proof_path.write_text(full_code)

            cmd = [
                "docker", "run", "--rm",
                "--network=none",
                "--memory=4g",
                "--cpus=2",
                "-v", f"{tmpdir}:/workspace:ro",
                "-w", "/workspace",
                COQ_IMAGE,
                "coqc", "Proof.v",
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=COQ_TIMEOUT,
                )
            except asyncio.TimeoutError:
                return VerificationResult.fail(
                    self.domain, ["Coq compilation timed out (5 min limit)"],
                )

        elapsed = time.monotonic() - start
        stderr_text = stderr.decode(errors="replace")

        if proc.returncode == 0:
            return VerificationResult(
                passed=True,
                score=1.0,
                badge=VerificationBadge.GREEN,
                domain=self.domain,
                details={
                    "compiler": "coq",
                    "compile_time_seconds": round(elapsed, 2),
                    "statement": statement,
                },
                compute_time_seconds=elapsed,
            )
        else:
            errors = [line for line in stderr_text.splitlines() if "Error" in line][:10]
            return VerificationResult(
                passed=False,
                score=0.0,
                badge=VerificationBadge.RED,
                domain=self.domain,
                errors=errors or [stderr_text[:500]],
                details={"compiler": "coq", "compiler_output": stderr_text[:2000]},
                compute_time_seconds=elapsed,
            )

    # ------------------------------------------------------------------
    # Isabelle verification
    # ------------------------------------------------------------------

    async def _verify_isabelle(self, task_result: dict) -> VerificationResult:
        """Verify proof using Isabelle/HOL in Docker sandbox."""
        start = time.monotonic()

        proof_code = task_result.get("proof_code", "")
        statement = task_result.get("statement")
        theory_name = task_result.get("theory_name", "Proof")

        # Build .thy file
        full_code = f'theory {theory_name}\nimports Main\nbegin\n\n{proof_code}\n\nend'

        with tempfile.TemporaryDirectory() as tmpdir:
            thy_path = Path(tmpdir) / f"{theory_name}.thy"
            thy_path.write_text(full_code)

            # Write ROOT file for isabelle build
            root_path = Path(tmpdir) / "ROOT"
            root_path.write_text(f'session "{theory_name}" = HOL +\n  theories {theory_name}\n')

            cmd = [
                "docker", "run", "--rm",
                "--network=none",
                "--memory=4g",
                "--cpus=2",
                "-v", f"{tmpdir}:/workspace:ro",
                "-w", "/workspace",
                ISABELLE_IMAGE,
                "isabelle", "build", "-D", ".",
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=ISABELLE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                return VerificationResult.fail(
                    self.domain, ["Isabelle build timed out (5 min limit)"],
                )

        elapsed = time.monotonic() - start
        stdout_text = stdout.decode(errors="replace")
        stderr_text = stderr.decode(errors="replace")

        if proc.returncode == 0:
            return VerificationResult(
                passed=True,
                score=1.0,
                badge=VerificationBadge.GREEN,
                domain=self.domain,
                details={
                    "compiler": "isabelle",
                    "compile_time_seconds": round(elapsed, 2),
                    "statement": statement,
                    "theory_name": theory_name,
                },
                compute_time_seconds=elapsed,
            )
        else:
            combined = f"{stdout_text}\n{stderr_text}"
            errors = [line for line in combined.splitlines() if "Error" in line or "***" in line][:10]
            return VerificationResult(
                passed=False,
                score=0.0,
                badge=VerificationBadge.RED,
                domain=self.domain,
                errors=errors or [combined[:500]],
                details={"compiler": "isabelle", "compiler_output": combined[:2000]},
                compute_time_seconds=elapsed,
            )
