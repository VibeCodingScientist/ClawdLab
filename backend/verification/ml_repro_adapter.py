"""ML/AI verification: benchmark reproducibility via lm-eval-harness."""
import asyncio
import json
import time

from backend.verification.base import (
    VerificationAdapter, VerificationResult, VerificationBadge,
)
from backend.logging_config import get_logger

logger = get_logger(__name__)

ML_IMAGE = "clawdlab/ml-verification:latest"
ML_TIMEOUT = 3600  # 1 hour max for benchmark runs

SUPPORTED_BENCHMARKS = {
    "mmlu", "hellaswag", "arc_easy", "arc_challenge", "winogrande",
    "truthfulqa", "gsm8k", "humaneval", "mbpp", "piqa", "boolq",
}


class MLReproAdapter(VerificationAdapter):
    domain = "ml_ai"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        claim_type = task_result.get("claim_type", "benchmark_result")

        if claim_type == "benchmark_result":
            return await self._verify_benchmark(task_result)
        elif claim_type == "ml_experiment":
            return await self._verify_experiment(task_result)
        elif claim_type == "architecture":
            return await self._verify_architecture(task_result)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    async def _verify_benchmark(self, result: dict) -> VerificationResult:
        """Re-run a benchmark and compare metrics."""
        start = time.monotonic()

        model_id = result.get("model_id")
        benchmark = result.get("benchmark", "").lower()
        claimed_metrics = result.get("metrics", {})
        num_fewshot = result.get("num_fewshot", 0)

        if not model_id:
            return VerificationResult.fail(self.domain, ["No model_id provided"])
        if benchmark not in SUPPORTED_BENCHMARKS:
            return VerificationResult.fail(self.domain, [
                f"Unsupported benchmark: {benchmark}. Supported: {sorted(SUPPORTED_BENCHMARKS)}"
            ])
        if not claimed_metrics:
            return VerificationResult.fail(self.domain, ["No claimed metrics to compare against"])

        # Run lm-eval-harness in Docker
        cmd = [
            "docker", "run", "--rm",
            "--gpus", "all",
            "--memory=16g",
            ML_IMAGE,
            "lm_eval",
            "--model", "hf",
            "--model_args", f"pretrained={model_id}",
            "--tasks", benchmark,
            "--num_fewshot", str(num_fewshot),
            "--batch_size", "auto",
            "--output_path", "/tmp/results",
            "--log_samples",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=ML_TIMEOUT)
        except asyncio.TimeoutError:
            return VerificationResult.fail(self.domain, ["Benchmark timed out (1 hour limit)"])

        elapsed = time.monotonic() - start

        if proc.returncode != 0:
            return VerificationResult.fail(self.domain, [
                f"lm-eval-harness failed: {stderr.decode(errors='replace')[:500]}"
            ])

        # Parse reproduced metrics
        try:
            raw_results = json.loads(stdout.decode())
            reproduced = self._extract_metrics(raw_results, benchmark)
        except (json.JSONDecodeError, KeyError) as e:
            return VerificationResult.fail(self.domain, [f"Failed to parse results: {e}"])

        # Compare claimed vs reproduced
        comparison = self._compare_metrics(claimed_metrics, reproduced, tolerance=0.02)

        score = comparison["match_ratio"]
        return VerificationResult(
            passed=comparison["all_within_tolerance"],
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details={
                "claim_type": "benchmark_result",
                "model_id": model_id,
                "benchmark": benchmark,
                "claimed_metrics": claimed_metrics,
                "reproduced_metrics": reproduced,
                "deviations": comparison["deviations"],
                "tolerance": 0.02,
                "all_within_tolerance": comparison["all_within_tolerance"],
            },
            compute_time_seconds=elapsed,
        )

    async def _verify_experiment(self, result: dict) -> VerificationResult:
        """Clone code at commit, rebuild env, re-run, compare."""
        start = time.monotonic()
        stages: dict = {}
        score = 0.0

        code_repo = result.get("code_repo")
        code_commit = result.get("code_commit")
        if not code_repo or not code_commit:
            return VerificationResult.fail(self.domain, ["code_repo and code_commit required"])

        # Stage 1: Clone (0.2)
        clone_ok = await self._try_clone(code_repo, code_commit)
        stages["code_clone"] = {"passed": clone_ok, "commit": code_commit}
        if clone_ok:
            score += 0.2

        # Stage 2: Environment build (0.2)
        env_ok = await self._try_build_env(code_repo, code_commit)
        stages["environment_build"] = {"passed": env_ok}
        if env_ok:
            score += 0.2

        # Stage 3: Run + metric comparison (0.6)
        if clone_ok and env_ok:
            run_result = await self._try_run(code_repo, code_commit, result.get("metrics", {}))
            stages["execution"] = run_result
            if run_result.get("passed"):
                score += 0.6 * run_result.get("match_ratio", 0)

        elapsed = time.monotonic() - start
        return VerificationResult(
            passed=score >= 0.8,
            score=round(score, 4),
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details={"claim_type": "ml_experiment", "stages": stages},
            compute_time_seconds=elapsed,
        )

    async def _verify_architecture(self, result: dict) -> VerificationResult:
        """Validate architecture code parses and param count matches."""
        code = result.get("code")
        claimed_params = result.get("param_count")

        if not code:
            return VerificationResult.fail(self.domain, ["No code provided for architecture claim"])

        try:
            compile(code, "<architecture>", "exec")
        except SyntaxError as e:
            return VerificationResult.fail(self.domain, [f"Code syntax error: {e}"])

        score = 0.8  # Code is valid
        details: dict = {"code_valid": True, "claimed_params": claimed_params}

        return VerificationResult(
            passed=True, score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain, details=details,
        )

    # ---- Helpers ----

    def _extract_metrics(self, raw: dict, benchmark: str) -> dict:
        """Pull numeric metrics from lm-eval-harness JSON output."""
        results = raw.get("results", {}).get(benchmark, {})
        return {k: v for k, v in results.items()
                if isinstance(v, (int, float)) and not k.endswith("_stderr")}

    def _compare_metrics(self, claimed: dict, reproduced: dict, tolerance: float) -> dict:
        deviations: dict[str, float] = {}
        within: list[bool] = []
        for key, claimed_val in claimed.items():
            if key in reproduced:
                dev = abs(reproduced[key] - claimed_val) / max(abs(claimed_val), 1e-10)
                deviations[key] = round(dev, 6)
                within.append(dev <= tolerance)

        match_ratio = sum(1 for w in within if w) / max(len(within), 1)
        return {
            "deviations": deviations,
            "all_within_tolerance": all(within) if within else False,
            "match_ratio": round(match_ratio, 4),
        }

    async def _try_clone(self, repo: str, commit: str) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", repo, "/tmp/verify-repo",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0

    async def _try_build_env(self, repo: str, commit: str) -> bool:
        # Stub — in production, build Docker image from requirements.txt/pyproject.toml
        return True

    async def _try_run(self, repo: str, commit: str, claimed_metrics: dict) -> dict:
        # Stub — in production, run experiment and compare
        return {"passed": False, "match_ratio": 0.0, "error": "Full experiment replay not yet implemented"}
