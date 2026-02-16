"""Cross-cutting verifier: Reproducibility Executor.

Clones a code repository, installs dependencies, runs the code in a
Docker sandbox, and compares outputs against claimed results.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shlex
import tempfile
import time
from pathlib import Path
from typing import Any

from backend.logging_config import get_logger
from backend.verification.cross_cutting_base import (
    CrossCuttingResult,
    CrossCuttingVerifier,
)

logger = get_logger(__name__)

REPRO_IMAGE = "clawdlab/reproducibility:latest"
REPRO_TIMEOUT = 300  # 5 minutes
CLONE_TIMEOUT = 60


class ReproducibilityExecutor(CrossCuttingVerifier):
    name = "reproducibility"
    default_weight = 0.15
    requires_docker = True

    def is_applicable(self, task_result: dict, task_metadata: dict) -> bool:
        return bool(task_result.get("code_repo") and task_result.get("code_commit"))

    async def verify(self, task_result: dict, task_metadata: dict) -> CrossCuttingResult:
        start = time.monotonic()

        code_repo = task_result["code_repo"]
        code_commit = task_result["code_commit"]
        claimed_results = task_result.get("claimed_results", {})
        output_checksums = task_result.get("output_checksums", {})
        entry_point = task_result.get("entry_point")

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {
            "repo": code_repo,
            "commit": code_commit,
        }
        warnings: list[str] = []
        errors: list[str] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            # Component 1: Repo cloneable (0.15)
            clone_ok, clone_detail = await self._clone_repo(code_repo, code_commit, tmpdir)
            component_scores["repo_cloneable"] = 1.0 if clone_ok else 0.0
            details["clone"] = clone_detail
            if not clone_ok:
                errors.append(clone_detail.get("error", "Clone failed"))
                elapsed = time.monotonic() - start
                return CrossCuttingResult(
                    verifier_name=self.name,
                    score=0.0,
                    weight=self.default_weight,
                    details=details,
                    errors=errors,
                    compute_time_seconds=elapsed,
                )

            # Component 2: Deps installable (0.25)
            deps_ok, deps_detail = await self._check_deps(tmpdir)
            component_scores["deps_installable"] = deps_detail.get("score", 0.0)
            details["deps"] = deps_detail

            # Component 3: Execution success (0.35)
            exec_ok, exec_detail = await self._execute(tmpdir, entry_point)
            component_scores["execution_success"] = 1.0 if exec_ok else 0.0
            details["execution"] = exec_detail
            if not exec_ok and exec_detail.get("error"):
                warnings.append(f"Execution: {exec_detail['error']}")

            # Component 4: Output match (0.25)
            output_score, output_detail = self._check_outputs(
                exec_detail.get("outputs", {}),
                claimed_results,
                output_checksums,
            )
            component_scores["output_match"] = output_score
            details["output_match"] = output_detail

        weights = {
            "repo_cloneable": 0.15,
            "deps_installable": 0.25,
            "execution_success": 0.35,
            "output_match": 0.25,
        }

        score = sum(weights[k] * component_scores.get(k, 0.0) for k in weights)
        score = min(1.0, round(score, 4))
        details["component_scores"] = component_scores

        elapsed = time.monotonic() - start
        return CrossCuttingResult(
            verifier_name=self.name,
            score=score,
            weight=self.default_weight,
            details=details,
            errors=errors,
            warnings=warnings,
            compute_time_seconds=elapsed,
        )

    async def _clone_repo(
        self, repo_url: str, commit: str, workdir: str,
    ) -> tuple[bool, dict]:
        """Clone repo and checkout specific commit."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth", "50", repo_url, f"{workdir}/repo",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=CLONE_TIMEOUT,
            )
            if proc.returncode != 0:
                return False, {
                    "error": stderr.decode(errors="replace")[:500],
                    "cloned": False,
                }

            # Checkout commit
            proc2 = await asyncio.create_subprocess_exec(
                "git", "-C", f"{workdir}/repo", "checkout", commit,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout2, stderr2 = await asyncio.wait_for(
                proc2.communicate(), timeout=15,
            )

            checked_out = proc2.returncode == 0
            return checked_out, {
                "cloned": True,
                "checked_out": checked_out,
                "commit": commit,
            }
        except asyncio.TimeoutError:
            return False, {"error": "Clone timed out", "cloned": False}
        except Exception as e:
            return False, {"error": str(e), "cloned": False}

    async def _check_deps(self, workdir: str) -> tuple[bool, dict]:
        """Check if dependency files exist and are installable."""
        repo_path = Path(workdir) / "repo"
        dep_files = {
            "requirements.txt": "pip install -r requirements.txt",
            "pyproject.toml": "pip install .",
            "setup.py": "pip install .",
            "environment.yml": "conda env create -f environment.yml",
        }

        found: list[str] = []
        for f in dep_files:
            if (repo_path / f).exists():
                found.append(f)

        if not found:
            return False, {
                "score": 0.3,
                "found": [],
                "note": "No dependency files found",
            }

        return True, {
            "score": 1.0 if "requirements.txt" in found or "pyproject.toml" in found else 0.7,
            "found": found,
        }

    async def _execute(
        self, workdir: str, entry_point: str | None,
    ) -> tuple[bool, dict]:
        """Run the code in a Docker sandbox."""
        repo_path = Path(workdir) / "repo"

        # Determine entry point
        if not entry_point:
            entry_point = self._detect_entry_point(repo_path)

        if not entry_point:
            return False, {
                "error": "No entry point found (Makefile, run.sh, main.py, reproduce.py)",
                "outputs": {},
            }

        # Sanitize entry_point — must be a simple filename
        if not re.match(r'^[A-Za-z0-9_.\-]+$', entry_point):
            return False, {
                "error": f"Invalid entry point name: {entry_point}",
                "outputs": {},
            }

        # Build docker command
        cmd = [
            "docker", "run", "--rm",
            "--network=none",
            "--memory=4g",
            "--cpus=2",
            "-v", f"{repo_path}:/workspace:ro",
            "-w", "/workspace",
            REPRO_IMAGE,
        ]

        if entry_point == "Makefile":
            cmd.extend(["make", "reproduce"])
        elif entry_point.endswith(".sh"):
            cmd.extend(["bash", entry_point])
        else:
            cmd.extend(["python", entry_point])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=REPRO_TIMEOUT,
            )

            stdout_text = stdout.decode(errors="replace")[:5000]
            stderr_text = stderr.decode(errors="replace")[:2000]
            success = proc.returncode == 0

            # Try to parse JSON output
            outputs: dict = {}
            try:
                outputs = json.loads(stdout_text)
            except (json.JSONDecodeError, ValueError):
                outputs = {"raw_output": stdout_text[:1000]}

            return success, {
                "exit_code": proc.returncode,
                "entry_point": entry_point,
                "stdout_preview": stdout_text[:500],
                "stderr_preview": stderr_text[:500] if not success else "",
                "outputs": outputs,
            }

        except asyncio.TimeoutError:
            return False, {"error": f"Execution timed out ({REPRO_TIMEOUT}s)", "outputs": {}}
        except FileNotFoundError:
            return False, {"error": "Docker not available", "outputs": {}}
        except Exception as e:
            return False, {"error": str(e), "outputs": {}}

    @staticmethod
    def _detect_entry_point(repo_path: Path) -> str | None:
        """Auto-detect the entry point for reproduction."""
        candidates = ["reproduce.py", "run.sh", "main.py", "Makefile"]
        for c in candidates:
            if (repo_path / c).exists():
                return c
        return None

    @staticmethod
    def _check_outputs(
        actual_outputs: dict,
        claimed_results: dict,
        output_checksums: dict,
    ) -> tuple[float, dict]:
        """Compare actual outputs against claimed results and checksums."""
        if not claimed_results and not output_checksums:
            return 0.5, {"note": "No claimed results to compare against"}

        checks: list[dict] = []
        matches = 0
        total = 0

        # Numeric comparison with tolerance
        for key, claimed in claimed_results.items():
            actual = actual_outputs.get(key)
            if actual is None:
                checks.append({"key": key, "match": False, "note": "Missing in output"})
                total += 1
                continue

            total += 1
            if isinstance(claimed, (int, float)) and isinstance(actual, (int, float)):
                tolerance = max(abs(claimed) * 0.05, 1e-6)
                match = abs(claimed - actual) <= tolerance
                checks.append({
                    "key": key, "match": match,
                    "claimed": claimed, "actual": actual,
                    "tolerance": tolerance,
                })
            else:
                match = str(claimed) == str(actual)
                checks.append({"key": key, "match": match})

            if match:
                matches += 1

        # Checksum verification
        for filename, expected_hash in output_checksums.items():
            total += 1
            actual_data = actual_outputs.get(filename)
            if actual_data:
                actual_hash = hashlib.sha256(str(actual_data).encode()).hexdigest()
                match = actual_hash == expected_hash
                checks.append({
                    "key": f"checksum:{filename}",
                    "match": match,
                    "expected": expected_hash[:16] + "...",
                    "actual": actual_hash[:16] + "...",
                })
                if match:
                    matches += 1
            else:
                checks.append({"key": f"checksum:{filename}", "match": False, "note": "File not in output"})

        score = matches / total if total > 0 else 0.5
        return round(score, 4), {"checks": checks, "matches": matches, "total": total}
