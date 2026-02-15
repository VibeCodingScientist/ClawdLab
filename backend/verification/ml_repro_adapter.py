"""ML/AI verification: HF leaderboard lookups + Hub API checks.

Cross-references claimed benchmark scores against the Open LLM Leaderboard
and HuggingFace Hub model cards.  No Docker, no GPU.
"""
import asyncio
import io
import time

import httpx

from backend.verification.base import (
    VerificationAdapter, VerificationResult,
)
from backend.logging_config import get_logger

logger = get_logger(__name__)

HF_API_BASE = "https://huggingface.co/api"
LEADERBOARD_PARQUET_URL = (
    "https://huggingface.co/datasets/open-llm-leaderboard/contents"
    "/resolve/main/default/train-00000-of-00001.parquet"
)
TIMEOUT = 30

SUPPORTED_BENCHMARKS = {
    "mmlu", "hellaswag", "arc_easy", "arc_challenge", "winogrande",
    "truthfulqa", "gsm8k", "humaneval", "mbpp", "piqa", "boolq",
}

# Cached leaderboard dataframe
_leaderboard_df = None
_leaderboard_loaded = False


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

    # ------------------------------------------------------------------
    # benchmark_result
    # ------------------------------------------------------------------

    async def _verify_benchmark(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        model_id = result.get("model_id")
        benchmark = result.get("benchmark", "").lower()
        claimed_metrics = result.get("metrics", {})
        num_fewshot = result.get("num_fewshot")

        if not model_id:
            return VerificationResult.fail(self.domain, ["No model_id provided"])
        if benchmark not in SUPPORTED_BENCHMARKS:
            return VerificationResult.fail(self.domain, [
                f"Unsupported benchmark: {benchmark}. Supported: {sorted(SUPPORTED_BENCHMARKS)}"
            ])
        if not claimed_metrics:
            return VerificationResult.fail(self.domain, ["No claimed metrics to compare against"])

        component_scores: dict[str, float] = {}
        details: dict = {
            "claim_type": "benchmark_result",
            "model_id": model_id,
            "benchmark": benchmark,
        }
        warnings: list[str] = []

        # --- Check 1: Model exists on HF Hub (0.15) ---
        model_info = await self._check_model_exists(model_id)
        component_scores["model_exists"] = model_info["score"]
        details["model_info"] = model_info.get("metrics", {})

        if model_info["score"] == 0.0:
            elapsed = time.monotonic() - start
            return VerificationResult(
                passed=False, score=0.0,
                badge=VerificationResult.score_to_badge(0.0),
                domain=self.domain,
                details=details,
                errors=[f"Model '{model_id}' not found on HuggingFace Hub"],
                compute_time_seconds=elapsed,
            )

        # --- Check 2: Leaderboard score lookup (0.40) ---
        lb_result = await self._check_leaderboard(model_id, benchmark, claimed_metrics)
        component_scores["leaderboard"] = lb_result["score"]
        details["leaderboard"] = lb_result.get("metrics", {})
        if lb_result.get("warnings"):
            warnings.extend(lb_result["warnings"])

        # --- Check 3: Model card eval results (0.25) ---
        card_result = await self._check_model_card(model_id, benchmark, claimed_metrics)
        component_scores["model_card"] = card_result["score"]
        details["model_card"] = card_result.get("metrics", {})

        # --- Check 4: Claimed metrics plausibility (0.10) ---
        plaus_result = self._check_metric_plausibility(benchmark, claimed_metrics)
        component_scores["plausibility"] = plaus_result["score"]
        details["plausibility"] = plaus_result.get("metrics", {})

        # --- Check 5: Model metadata consistency (0.10) ---
        meta_result = self._check_metadata_consistency(
            model_info.get("raw", {}), result,
        )
        component_scores["metadata"] = meta_result["score"]
        details["metadata"] = meta_result.get("metrics", {})

        # --- Aggregate ---
        weights = {
            "model_exists": 0.15,
            "leaderboard": 0.40,
            "model_card": 0.25,
            "plausibility": 0.10,
            "metadata": 0.10,
        }
        score = sum(weights.get(k, 0) * component_scores.get(k, 0.0) for k in weights)
        score = min(1.0, round(score, 4))

        passed = score >= 0.5 and component_scores["model_exists"] > 0.0
        elapsed = time.monotonic() - start
        details["component_scores"] = component_scores

        return VerificationResult(
            passed=passed,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details=details,
            warnings=warnings,
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # ml_experiment — git-based provenance
    # ------------------------------------------------------------------

    async def _verify_experiment(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        code_repo = result.get("code_repo")
        code_commit = result.get("code_commit")

        if not code_repo or not code_commit:
            return VerificationResult.fail(self.domain, ["code_repo and code_commit required"])

        component_scores: dict[str, float] = {}
        details: dict = {"claim_type": "ml_experiment", "repo": code_repo, "commit": code_commit}

        # --- Check 1: Repo exists (0.30) ---
        repo_ok = await self._check_repo_exists(code_repo)
        component_scores["repo_exists"] = 1.0 if repo_ok else 0.0
        details["repo_exists"] = repo_ok

        # --- Check 2: Commit exists (0.30) ---
        commit_ok = False
        if repo_ok:
            commit_ok = await self._check_commit_exists(code_repo, code_commit)
        component_scores["commit_exists"] = 1.0 if commit_ok else 0.0
        details["commit_exists"] = commit_ok

        # --- Check 3: Reproducibility files (0.40) ---
        repro_result = await self._check_repro_files(code_repo, code_commit)
        component_scores["repro_files"] = repro_result["score"]
        details["repro_files"] = repro_result.get("metrics", {})

        score = (
            0.30 * component_scores["repo_exists"]
            + 0.30 * component_scores["commit_exists"]
            + 0.40 * component_scores["repro_files"]
        )
        score = min(1.0, round(score, 4))

        elapsed = time.monotonic() - start
        details["component_scores"] = component_scores

        return VerificationResult(
            passed=score >= 0.5,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details=details,
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # architecture — kept as-is (CPU-only compile check)
    # ------------------------------------------------------------------

    async def _verify_architecture(self, result: dict) -> VerificationResult:
        code = result.get("code")
        claimed_params = result.get("param_count")

        if not code:
            return VerificationResult.fail(self.domain, ["No code provided for architecture claim"])

        try:
            compile(code, "<architecture>", "exec")
        except SyntaxError as e:
            return VerificationResult.fail(self.domain, [f"Code syntax error: {e}"])

        score = 0.8
        details: dict = {"claim_type": "architecture", "code_valid": True, "claimed_params": claimed_params}

        return VerificationResult(
            passed=True, score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain, details=details,
        )

    # ------------------------------------------------------------------
    # HF Hub helpers
    # ------------------------------------------------------------------

    async def _check_model_exists(self, model_id: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(f"{HF_API_BASE}/models/{model_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "score": 1.0,
                        "raw": data,
                        "metrics": {
                            "model_id": model_id,
                            "pipeline_tag": data.get("pipeline_tag"),
                            "downloads": data.get("downloads"),
                            "likes": data.get("likes"),
                        },
                    }
                return {"score": 0.0, "metrics": {"status": resp.status_code}}
        except Exception as e:
            logger.warning("hf_model_check_failed", error=str(e))
            return {"score": 0.5, "metrics": {"error": str(e)}}

    async def _check_leaderboard(
        self, model_id: str, benchmark: str, claimed_metrics: dict,
    ) -> dict:
        global _leaderboard_df, _leaderboard_loaded

        if not _leaderboard_loaded:
            _leaderboard_df = await self._load_leaderboard()
            _leaderboard_loaded = True

        if _leaderboard_df is None:
            return {
                "score": 0.0,
                "warnings": ["Could not load Open LLM Leaderboard data"],
                "metrics": {"note": "Leaderboard unavailable"},
            }

        try:
            import pandas as pd
            df = _leaderboard_df

            # Search for model — try exact match then partial
            model_rows = df[df["model_name_or_path"].str.contains(
                model_id, case=False, na=False,
            )]

            if model_rows.empty:
                return {
                    "score": 0.0,
                    "warnings": [f"Model '{model_id}' not found in leaderboard"],
                    "metrics": {"note": "Model not in leaderboard"},
                }

            row = model_rows.iloc[0]

            # Find benchmark columns — leaderboard uses various naming
            benchmark_cols = [
                c for c in df.columns
                if benchmark.lower() in c.lower()
            ]

            if not benchmark_cols:
                return {
                    "score": 0.0,
                    "warnings": [f"Benchmark '{benchmark}' column not found in leaderboard"],
                    "metrics": {"note": "Benchmark column not found"},
                }

            # Compare claimed vs leaderboard values
            comparisons: dict = {}
            all_within_tolerance = True

            for col in benchmark_cols:
                lb_val = row.get(col)
                if lb_val is None or (isinstance(lb_val, float) and pd.isna(lb_val)):
                    continue

                # Find matching claimed metric
                for metric_name, claimed_val in claimed_metrics.items():
                    if not isinstance(claimed_val, (int, float)):
                        continue
                    denom = max(abs(lb_val), 1e-10)
                    deviation = abs(claimed_val - lb_val) / denom
                    within = deviation <= 0.02  # 2% tolerance
                    comparisons[f"{col}:{metric_name}"] = {
                        "claimed": claimed_val,
                        "leaderboard": float(lb_val),
                        "deviation": round(deviation, 6),
                        "within_tolerance": within,
                    }
                    if not within:
                        all_within_tolerance = False

            if not comparisons:
                return {
                    "score": 0.3,
                    "metrics": {"note": "Found model but no comparable metrics"},
                }

            n_within = sum(1 for c in comparisons.values() if c["within_tolerance"])
            match_ratio = n_within / len(comparisons)
            score = match_ratio

            return {
                "score": round(score, 4),
                "metrics": {
                    "comparisons": comparisons,
                    "all_within_tolerance": all_within_tolerance,
                    "match_ratio": round(match_ratio, 4),
                },
            }

        except Exception as e:
            logger.warning("leaderboard_comparison_failed", error=str(e))
            return {"score": 0.0, "metrics": {"error": str(e)}}

    async def _load_leaderboard(self):
        """Download and cache Open LLM Leaderboard parquet."""
        try:
            import pandas as pd
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(LEADERBOARD_PARQUET_URL)
                if resp.status_code != 200:
                    logger.warning("leaderboard_download_failed", status=resp.status_code)
                    return None
                df = await asyncio.to_thread(pd.read_parquet, io.BytesIO(resp.content))
                logger.info("leaderboard_loaded", rows=len(df))
                return df
        except Exception as e:
            logger.warning("leaderboard_load_failed", error=str(e))
            return None

    async def _check_model_card(
        self, model_id: str, benchmark: str, claimed_metrics: dict,
    ) -> dict:
        """Check model card metadata for eval results."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(f"{HF_API_BASE}/models/{model_id}")
                if resp.status_code != 200:
                    return {"score": 0.0, "metrics": {"error": "Could not fetch model card"}}

                data = resp.json()
                card_data = data.get("cardData", {})
                eval_results = card_data.get("eval_results", [])

                if not eval_results:
                    # Also check model-index format
                    model_index = card_data.get("model-index", [])
                    for entry in model_index:
                        for result_entry in entry.get("results", []):
                            eval_results.append(result_entry)

                if not eval_results:
                    return {
                        "score": 0.3,
                        "metrics": {"note": "No eval results in model card"},
                    }

                # Find matching benchmark results
                matched = False
                comparisons: dict = {}
                for eval_entry in eval_results:
                    dataset = eval_entry.get("dataset", {})
                    dataset_name = dataset.get("name", "").lower() if isinstance(dataset, dict) else str(dataset).lower()

                    if benchmark not in dataset_name:
                        continue

                    for metric_entry in eval_entry.get("metrics", []):
                        metric_name = metric_entry.get("name", "")
                        metric_val = metric_entry.get("value")
                        if metric_val is None or not isinstance(metric_val, (int, float)):
                            continue

                        matched = True
                        for claimed_name, claimed_val in claimed_metrics.items():
                            if not isinstance(claimed_val, (int, float)):
                                continue
                            denom = max(abs(metric_val), 1e-10)
                            dev = abs(claimed_val - metric_val) / denom
                            comparisons[f"{metric_name}:{claimed_name}"] = {
                                "claimed": claimed_val,
                                "card": metric_val,
                                "deviation": round(dev, 6),
                                "within_tolerance": dev <= 0.02,
                            }

                if not matched:
                    return {
                        "score": 0.3,
                        "metrics": {"note": f"No {benchmark} results in model card"},
                    }

                n_ok = sum(1 for c in comparisons.values() if c["within_tolerance"])
                score = n_ok / max(len(comparisons), 1)
                return {
                    "score": round(score, 4),
                    "metrics": {"comparisons": comparisons},
                }

        except Exception as e:
            logger.warning("model_card_check_failed", error=str(e))
            return {"score": 0.0, "metrics": {"error": str(e)}}

    @staticmethod
    def _check_metric_plausibility(benchmark: str, claimed_metrics: dict) -> dict:
        """Range checks for claimed metric values."""
        issues: list[str] = []
        all_ok = True

        for name, val in claimed_metrics.items():
            if not isinstance(val, (int, float)):
                continue

            # Accuracy-like metrics should be 0-100 (or 0-1)
            if any(kw in name.lower() for kw in ("acc", "accuracy", "score", "exact_match")):
                if val < 0 or val > 100:
                    issues.append(f"{name}={val} outside [0, 100]")
                    all_ok = False
                elif val > 99.5:
                    issues.append(f"{name}={val} suspiciously high")
            # F1, precision, recall typically 0-1 or 0-100
            if "f1" in name.lower() and (val < 0 or val > 100):
                issues.append(f"{name}={val} outside valid range")
                all_ok = False

        score = 1.0 if all_ok else max(0.0, 1.0 - 0.3 * len(issues))
        return {"score": round(score, 4), "metrics": {"issues": issues}}

    @staticmethod
    def _check_metadata_consistency(model_data: dict, result: dict) -> dict:
        """Check param count, architecture match."""
        comparisons: dict = {}
        score = 0.5  # neutral default

        claimed_params = result.get("param_count")
        if claimed_params and model_data:
            safetensors = model_data.get("safetensors", {})
            actual_params = safetensors.get("total") if safetensors else None
            if actual_params:
                ratio = min(claimed_params, actual_params) / max(claimed_params, actual_params)
                match = ratio >= 0.95
                comparisons["param_count"] = {
                    "claimed": claimed_params,
                    "hub": actual_params,
                    "ratio": round(ratio, 4),
                    "match": match,
                }
                score = 1.0 if match else 0.2

        return {"score": score, "metrics": comparisons}

    # ------------------------------------------------------------------
    # Git provenance helpers (for ml_experiment)
    # ------------------------------------------------------------------

    async def _check_repo_exists(self, repo_url: str) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "ls-remote", "--exit-code", repo_url,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=15)
            return proc.returncode == 0
        except (asyncio.TimeoutError, Exception):
            return False

    async def _check_commit_exists(self, repo_url: str, commit: str) -> bool:
        """Check commit via GitHub API if it's a GitHub URL, else git ls-remote."""
        if "github.com" in repo_url:
            try:
                parts = repo_url.rstrip("/").rstrip(".git").split("github.com/")[-1]
                owner_repo = parts.split("/")
                if len(owner_repo) >= 2:
                    owner, repo = owner_repo[0], owner_repo[1]
                    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                        resp = await client.get(
                            f"https://api.github.com/repos/{owner}/{repo}/commits/{commit}"
                        )
                        return resp.status_code == 200
            except Exception:
                pass

        # Fallback: try git ls-remote for tag/branch
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "ls-remote", repo_url, commit,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            return len(stdout.decode().strip()) > 0
        except (asyncio.TimeoutError, Exception):
            return False

    async def _check_repro_files(self, repo_url: str, commit: str) -> dict:
        """Check for requirements.txt, pyproject.toml, etc. via GitHub API."""
        repro_files = {"requirements.txt", "pyproject.toml", "setup.py", "environment.yml", "Dockerfile"}
        found: list[str] = []

        if "github.com" in repo_url:
            try:
                parts = repo_url.rstrip("/").rstrip(".git").split("github.com/")[-1]
                owner_repo = parts.split("/")
                if len(owner_repo) >= 2:
                    owner, repo = owner_repo[0], owner_repo[1]
                    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                        resp = await client.get(
                            f"https://api.github.com/repos/{owner}/{repo}/contents?ref={commit}"
                        )
                        if resp.status_code == 200:
                            files = {f["name"] for f in resp.json() if isinstance(f, dict)}
                            found = [f for f in repro_files if f in files]
            except Exception as e:
                logger.warning("repro_files_check_failed", error=str(e))

        score = min(1.0, len(found) * 0.5) if found else 0.0
        return {
            "score": round(score, 4),
            "metrics": {"found": found, "checked": sorted(repro_files)},
        }
