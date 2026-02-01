"""Main ML/AI verification service."""

from datetime import datetime
from typing import Any

from platform.verification_engines.ml_verifier.base import (
    MLVerificationResult,
    ResourceUsage,
    VerificationStatus,
)
from platform.verification_engines.ml_verifier.config import EXPERIMENT_TYPES, get_settings
from platform.verification_engines.ml_verifier.dataset import DatasetFetcher
from platform.verification_engines.ml_verifier.environment import EnvironmentManager
from platform.verification_engines.ml_verifier.k8s_runner import KubernetesJobRunner, LocalJobRunner
from platform.verification_engines.ml_verifier.metrics import MetricComparator, MetricParser
from platform.verification_engines.ml_verifier.novelty_checker import MLNoveltyChecker
from platform.verification_engines.ml_verifier.repository import (
    CodeIntegrityChecker,
    GitRepoCloner,
    RequirementsExtractor,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class MLVerificationService:
    """
    Main service for ML/AI experiment verification.

    Orchestrates the complete verification pipeline:
    1. Clone and verify source code
    2. Build reproducible environment
    3. Fetch and validate datasets
    4. Execute experiment
    5. Compare metrics to claimed results
    6. Check novelty against existing work
    """

    def __init__(self, use_local_runner: bool = False):
        """
        Initialize the ML verification service.

        Args:
            use_local_runner: Use local Docker instead of Kubernetes
        """
        self.repo_cloner = GitRepoCloner()
        self.integrity_checker = CodeIntegrityChecker()
        self.requirements_extractor = RequirementsExtractor()
        self.environment_manager = EnvironmentManager()
        self.dataset_fetcher = DatasetFetcher()
        self.metric_comparator = MetricComparator()
        self.metric_parser = MetricParser()
        self.novelty_checker = MLNoveltyChecker()

        if use_local_runner:
            self.job_runner = LocalJobRunner()
        else:
            self.job_runner = KubernetesJobRunner()

    async def verify_claim(
        self,
        claim_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Verify an ML experiment claim.

        This is the main entry point called by the Celery task.

        Args:
            claim_id: ID of the claim being verified
            payload: Claim payload containing:
                - experiment_type: Type of experiment
                - repo_url: Git repository URL
                - commit_hash: Specific commit
                - claimed_metrics: Dict of claimed metrics
                - datasets: List of dataset specifications
                - run_command: Command to run experiment
                - timeout_seconds: Execution timeout
                - gpu_config: GPU configuration

        Returns:
            Verification result dictionary
        """
        started_at = datetime.utcnow()

        # Extract payload fields
        experiment_type = payload.get("experiment_type", "inference")
        repo_url = payload.get("repo_url", "")
        commit_hash = payload.get("commit_hash")
        branch = payload.get("branch")
        claimed_metrics = payload.get("claimed_metrics", {})
        datasets = payload.get("datasets", [])
        run_command = payload.get("run_command", "python main.py")
        timeout_seconds = payload.get("timeout_seconds", settings.default_timeout_seconds)
        gpu_config = payload.get("gpu_config", {})

        logger.info(
            "ml_verification_started",
            claim_id=claim_id,
            experiment_type=experiment_type,
            repo_url=repo_url,
        )

        result = MLVerificationResult(
            status=VerificationStatus.PENDING,
            verified=False,
            message="Verification in progress",
            claim_id=claim_id,
            experiment_type=experiment_type,
            claimed_metrics=claimed_metrics,
            started_at=started_at,
        )

        try:
            # Validate experiment type
            if experiment_type not in EXPERIMENT_TYPES:
                result.status = VerificationStatus.ERROR
                result.message = f"Unsupported experiment type: {experiment_type}"
                result.error_type = "validation_error"
                result.completed_at = datetime.utcnow()
                return result.to_dict()

            # Stage 1: Clone repository
            clone_result = await self.repo_cloner.verify(
                repo_url=repo_url,
                commit_hash=commit_hash,
                branch=branch,
            )
            result.stages["code_clone"] = clone_result

            if not clone_result.passed:
                result.status = VerificationStatus.ERROR
                result.message = f"Code clone failed: {clone_result.message}"
                result.error_type = "clone_error"
                result.completed_at = datetime.utcnow()
                return result.to_dict()

            repo_path = self.repo_cloner.get_repo_path(repo_url, commit_hash)

            # Check code integrity
            integrity_result = await self.integrity_checker.check_integrity(repo_path)
            if not integrity_result["passed"]:
                logger.warning(
                    "code_integrity_issues",
                    claim_id=claim_id,
                    issues=integrity_result["issues_count"],
                )

            # Extract requirements
            requirements = await self.requirements_extractor.extract_requirements(repo_path)

            # Stage 2: Build environment
            env_result = await self.environment_manager.build_environment(
                repo_path=repo_path,
                requirements=requirements,
            )
            result.stages["environment_build"] = env_result

            if not env_result.passed:
                result.status = VerificationStatus.ERROR
                result.message = f"Environment build failed: {env_result.message}"
                result.error_type = "environment_error"
                result.completed_at = datetime.utcnow()
                return result.to_dict()

            # Stage 3: Fetch datasets
            if datasets:
                data_result = await self.dataset_fetcher.verify(
                    datasets=datasets,
                    working_dir=repo_path,
                )
                result.stages["data_fetch"] = data_result

                if not data_result.passed:
                    result.status = VerificationStatus.ERROR
                    result.message = f"Dataset fetch failed: {data_result.message}"
                    result.error_type = "data_error"
                    result.completed_at = datetime.utcnow()
                    return result.to_dict()

            # Stage 4: Execute experiment
            job_spec = self._build_job_spec(
                repo_path=repo_path,
                env_result=env_result,
                run_command=run_command,
                gpu_config=gpu_config,
                payload=payload,
            )

            job_id = await self.job_runner.submit_job(
                job_spec=job_spec,
                timeout_seconds=timeout_seconds,
            )

            exec_result = await self.job_runner.wait_for_completion(
                job_id=job_id,
                timeout_seconds=timeout_seconds,
            )
            result.stages["execution"] = exec_result

            if not exec_result.passed:
                result.status = VerificationStatus.REFUTED
                result.message = f"Experiment execution failed: {exec_result.message}"
                result.error_type = "execution_error"
                result.error_details = exec_result.stderr_tail
                result.completed_at = datetime.utcnow()
                return result.to_dict()

            # Parse output metrics
            reproduced_metrics = await self._extract_metrics(
                repo_path=repo_path,
                exec_output=exec_result.stdout_tail,
            )
            result.reproduced_metrics = reproduced_metrics

            # Stage 5: Compare metrics
            comparison_result = self.metric_comparator.compare_metrics(
                claimed=claimed_metrics,
                reproduced=reproduced_metrics,
            )
            result.stages["metric_comparison"] = comparison_result
            result.metric_comparisons = comparison_result.comparisons
            result.all_metrics_within_tolerance = comparison_result.all_within_tolerance

            # Stage 6: Calculate resource usage
            result.resources = ResourceUsage(
                gpu_hours=exec_result.gpu_hours,
                peak_memory_gb=exec_result.peak_memory_gb,
                cpu_hours=exec_result.runtime_seconds / 3600,
            )

            # Stage 7: Check novelty (optional, for novel claims)
            if settings.papers_with_code_enabled and payload.get("check_novelty", False):
                novelty_result = await self.novelty_checker.check_novelty(
                    experiment_description=payload.get("description", ""),
                    tasks=payload.get("tasks", []),
                    metrics=reproduced_metrics,
                    dataset_names=[d.get("name") for d in datasets],
                    model_architecture=payload.get("model_architecture"),
                )
                result.novelty_score = novelty_result.novelty_score
                result.similar_papers = [p.to_dict() for p in novelty_result.similar_papers]

            # Final status determination
            if comparison_result.all_within_tolerance:
                result.status = VerificationStatus.VERIFIED
                result.verified = True
                result.message = "Experiment reproduced successfully, all metrics within tolerance"
            else:
                result.status = VerificationStatus.REFUTED
                result.verified = False
                failed_metrics = [
                    c.metric_name for c in comparison_result.comparisons
                    if not c.within_tolerance
                ]
                result.message = f"Metrics outside tolerance: {', '.join(failed_metrics)}"

            result.completed_at = datetime.utcnow()

            logger.info(
                "ml_verification_completed",
                claim_id=claim_id,
                verified=result.verified,
                status=result.status.value,
            )

            return result.to_dict()

        except Exception as e:
            logger.exception(
                "ml_verification_error",
                claim_id=claim_id,
                error=str(e),
            )

            result.status = VerificationStatus.ERROR
            result.verified = False
            result.message = f"Verification failed: {str(e)}"
            result.error_type = "internal_error"
            result.error_details = str(e)
            result.completed_at = datetime.utcnow()

            return result.to_dict()

    def _build_job_spec(
        self,
        repo_path: str,
        env_result: Any,
        run_command: str,
        gpu_config: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Build job specification for execution."""
        # Determine image
        if env_result.environment_type == "docker":
            image = f"{settings.container_registry}/ml-verify:{env_result.image_hash}"
        else:
            image = payload.get("base_image", "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime")

        # Build environment variables
        env = {
            "PYTHONPATH": "/workspace",
            "CUDA_VISIBLE_DEVICES": "0",
            "HF_HOME": "/data/hf_cache",
            "TRANSFORMERS_CACHE": "/data/hf_cache",
            "WANDB_DISABLED": "true",  # Disable wandb for verification
        }
        env.update(payload.get("env", {}))

        # Parse run command
        if isinstance(run_command, str):
            command = ["/bin/bash"]
            args = ["-c", run_command]
        else:
            command = run_command
            args = []

        return {
            "image": image,
            "command": command,
            "args": args,
            "env": env,
            "gpu_type": gpu_config.get("gpu_type", "a100_40gb"),
            "gpu_count": gpu_config.get("gpu_count", 1),
            "memory_gb": gpu_config.get("memory_gb", 32),
            "cpu_cores": gpu_config.get("cpu_cores", 8),
            "working_dir": repo_path,
        }

    async def _extract_metrics(
        self,
        repo_path: str,
        exec_output: str,
    ) -> dict[str, float]:
        """Extract metrics from execution output."""
        metrics = {}

        # Try to parse from output
        text_metrics = self.metric_parser.parse_text_metrics(exec_output)
        metrics.update(text_metrics)

        # Check for results files
        from pathlib import Path
        import json

        results_patterns = [
            "results.json",
            "metrics.json",
            "output/results.json",
            "logs/metrics.json",
        ]

        for pattern in results_patterns:
            results_path = Path(repo_path) / pattern
            if results_path.exists():
                try:
                    data = json.loads(results_path.read_text())
                    json_metrics = self.metric_parser.parse_json_metrics(data)
                    metrics.update(json_metrics)
                except Exception:
                    pass

        return metrics

    async def verify_quick(
        self,
        repo_url: str,
        run_command: str,
        claimed_metrics: dict[str, float],
    ) -> dict[str, Any]:
        """
        Quick verification without full pipeline.

        Useful for testing and simple experiments.
        """
        return await self.verify_claim(
            claim_id="quick-verify",
            payload={
                "experiment_type": "inference",
                "repo_url": repo_url,
                "run_command": run_command,
                "claimed_metrics": claimed_metrics,
                "timeout_seconds": 600,
            },
        )

    def get_supported_experiment_types(self) -> list[dict[str, Any]]:
        """Get list of supported experiment types."""
        return [
            {
                "id": exp_id,
                "name": info["name"],
                "description": info["description"],
                "requires_gpu": info["requires_gpu"],
            }
            for exp_id, info in EXPERIMENT_TYPES.items()
        ]


# Singleton instance
_service_instance: MLVerificationService | None = None


def get_ml_verification_service() -> MLVerificationService:
    """Get or create the ML verification service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = MLVerificationService()
    return _service_instance
