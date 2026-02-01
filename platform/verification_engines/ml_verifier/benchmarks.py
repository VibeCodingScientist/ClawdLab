"""Benchmark integration for standardized ML evaluation."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from platform.verification_engines.ml_verifier.base import (
    BaseBenchmarkRunner,
    MetricValue,
)
from platform.verification_engines.ml_verifier.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class LMEvalHarness(BaseBenchmarkRunner):
    """
    Integration with EleutherAI's lm-evaluation-harness.

    Supports standardized evaluation of language models on
    common benchmarks like MMLU, HellaSwag, ARC, etc.
    """

    # Common benchmark tasks
    BENCHMARK_TASKS = {
        "mmlu": {
            "tasks": ["mmlu"],
            "description": "Massive Multitask Language Understanding",
            "metrics": ["acc", "acc_norm"],
        },
        "hellaswag": {
            "tasks": ["hellaswag"],
            "description": "HellaSwag commonsense reasoning",
            "metrics": ["acc", "acc_norm"],
        },
        "arc_challenge": {
            "tasks": ["arc_challenge"],
            "description": "AI2 Reasoning Challenge",
            "metrics": ["acc", "acc_norm"],
        },
        "arc_easy": {
            "tasks": ["arc_easy"],
            "description": "AI2 Reasoning Challenge (Easy)",
            "metrics": ["acc", "acc_norm"],
        },
        "winogrande": {
            "tasks": ["winogrande"],
            "description": "Winogrande commonsense",
            "metrics": ["acc"],
        },
        "truthfulqa_mc": {
            "tasks": ["truthfulqa_mc"],
            "description": "TruthfulQA multiple choice",
            "metrics": ["mc1", "mc2"],
        },
        "gsm8k": {
            "tasks": ["gsm8k"],
            "description": "Grade School Math 8K",
            "metrics": ["acc"],
        },
        "humaneval": {
            "tasks": ["humaneval"],
            "description": "HumanEval code generation",
            "metrics": ["pass@1", "pass@10"],
        },
    }

    def __init__(self, harness_path: str | None = None):
        """
        Initialize lm-evaluation-harness integration.

        Args:
            harness_path: Path to lm-evaluation-harness installation
        """
        self._harness_path = harness_path or settings.lm_eval_harness_path

    @property
    def benchmark_name(self) -> str:
        return "lm-evaluation-harness"

    async def run_benchmark(
        self,
        model_path: str,
        tasks: list[str],
        config: dict[str, Any],
    ) -> dict[str, MetricValue]:
        """
        Run benchmark evaluation.

        Args:
            model_path: Path to model or HuggingFace model ID
            tasks: List of benchmark tasks to run
            config: Benchmark configuration including:
                - batch_size: Evaluation batch size
                - num_fewshot: Number of few-shot examples
                - device: Device to use (cuda, cpu)
                - trust_remote_code: Whether to trust remote code

        Returns:
            Dict of metric name to MetricValue
        """
        batch_size = config.get("batch_size", 4)
        num_fewshot = config.get("num_fewshot", 0)
        device = config.get("device", "cuda")
        trust_remote_code = config.get("trust_remote_code", False)

        # Build command
        cmd = [
            "python", "-m", "lm_eval",
            "--model", "hf",
            "--model_args", f"pretrained={model_path}",
            "--tasks", ",".join(tasks),
            "--batch_size", str(batch_size),
            "--device", device,
            "--output_path", "/tmp/lm_eval_results",
        ]

        if num_fewshot > 0:
            cmd.extend(["--num_fewshot", str(num_fewshot)])

        if trust_remote_code:
            cmd.append("--trust_remote_code")

        logger.info(
            "lm_eval_started",
            model=model_path,
            tasks=tasks,
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._harness_path,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.default_timeout_seconds,
            )

            if process.returncode != 0:
                logger.error(
                    "lm_eval_failed",
                    error=stderr.decode()[:500],
                )
                return {}

            # Parse results
            results = self._parse_results("/tmp/lm_eval_results")

            logger.info(
                "lm_eval_completed",
                model=model_path,
                metrics_count=len(results),
            )

            return results

        except asyncio.TimeoutError:
            logger.error("lm_eval_timeout", model=model_path)
            return {}

    def _parse_results(self, output_path: str) -> dict[str, MetricValue]:
        """Parse lm-eval results from output directory."""
        metrics = {}

        results_dir = Path(output_path)
        for json_file in results_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text())
                results = data.get("results", {})

                for task_name, task_results in results.items():
                    for metric_name, value in task_results.items():
                        if isinstance(value, (int, float)):
                            full_name = f"{task_name}/{metric_name}"
                            metrics[full_name] = MetricValue(
                                name=full_name,
                                value=float(value),
                            )

            except Exception as e:
                logger.warning("lm_eval_parse_error", file=str(json_file), error=str(e))

        return metrics

    def get_supported_tasks(self) -> list[str]:
        """Get list of supported benchmark tasks."""
        return list(self.BENCHMARK_TASKS.keys())


class HELMBenchmark(BaseBenchmarkRunner):
    """
    Integration with Stanford's HELM (Holistic Evaluation of Language Models).

    Provides comprehensive evaluation across multiple scenarios
    including accuracy, calibration, robustness, and fairness.
    """

    # HELM scenarios
    SCENARIOS = {
        "mmlu": {
            "description": "Massive Multitask Language Understanding",
            "metrics": ["exact_match", "quasi_exact_match"],
        },
        "boolq": {
            "description": "Boolean Questions",
            "metrics": ["exact_match"],
        },
        "narrative_qa": {
            "description": "NarrativeQA Reading Comprehension",
            "metrics": ["f1_score"],
        },
        "natural_qa": {
            "description": "Natural Questions",
            "metrics": ["f1_score", "exact_match"],
        },
        "quac": {
            "description": "Question Answering in Context",
            "metrics": ["f1_score"],
        },
        "raft": {
            "description": "Real-world Annotated Few-shot Tasks",
            "metrics": ["exact_match"],
        },
        "summarization_xsum": {
            "description": "XSum Summarization",
            "metrics": ["rouge_1", "rouge_2", "rouge_l"],
        },
        "summarization_cnndm": {
            "description": "CNN/DailyMail Summarization",
            "metrics": ["rouge_1", "rouge_2", "rouge_l"],
        },
        "code_humaneval": {
            "description": "HumanEval Code Generation",
            "metrics": ["pass_at_1", "pass_at_10"],
        },
    }

    def __init__(self, helm_path: str | None = None):
        """
        Initialize HELM integration.

        Args:
            helm_path: Path to HELM installation
        """
        self._helm_path = helm_path or settings.helm_path

    @property
    def benchmark_name(self) -> str:
        return "helm"

    async def run_benchmark(
        self,
        model_path: str,
        tasks: list[str],
        config: dict[str, Any],
    ) -> dict[str, MetricValue]:
        """
        Run HELM benchmark evaluation.

        Args:
            model_path: Path to model
            tasks: List of HELM scenarios
            config: Benchmark configuration

        Returns:
            Dict of metric name to MetricValue
        """
        # Generate run spec
        run_spec = self._generate_run_spec(model_path, tasks, config)
        spec_path = Path("/tmp/helm_spec.yaml")
        spec_path.write_text(run_spec)

        # Run HELM
        cmd = [
            "helm-run",
            "--conf-paths", str(spec_path),
            "--suite", "verification",
            "--max-eval-instances", str(config.get("max_instances", 1000)),
        ]

        logger.info("helm_started", model=model_path, tasks=tasks)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._helm_path,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.default_timeout_seconds,
            )

            if process.returncode != 0:
                logger.error("helm_failed", error=stderr.decode()[:500])
                return {}

            # Parse results
            results = self._parse_helm_results()

            logger.info(
                "helm_completed",
                model=model_path,
                metrics_count=len(results),
            )

            return results

        except asyncio.TimeoutError:
            logger.error("helm_timeout", model=model_path)
            return {}

    def _generate_run_spec(
        self,
        model_path: str,
        tasks: list[str],
        config: dict[str, Any],
    ) -> str:
        """Generate HELM run specification."""
        entries = []
        for task in tasks:
            entry = {
                "scenario": task,
                "model": model_path,
                "num_train_trials": config.get("num_trials", 1),
            }
            entries.append(entry)

        spec = {
            "entries": entries,
            "models": [
                {
                    "name": model_path,
                    "deployment": "local",
                }
            ],
        }

        import yaml
        return yaml.dump(spec)

    def _parse_helm_results(self) -> dict[str, MetricValue]:
        """Parse HELM benchmark results."""
        metrics = {}

        results_dir = Path(self._helm_path) / "benchmark_output" / "runs" / "verification"
        if not results_dir.exists():
            return metrics

        for scenario_dir in results_dir.iterdir():
            if scenario_dir.is_dir():
                stats_file = scenario_dir / "stats.json"
                if stats_file.exists():
                    try:
                        data = json.loads(stats_file.read_text())
                        for stat in data:
                            metric_name = f"{scenario_dir.name}/{stat['name']['name']}"
                            metrics[metric_name] = MetricValue(
                                name=metric_name,
                                value=stat.get("mean", 0.0),
                                std_dev=stat.get("std", None),
                            )
                    except Exception as e:
                        logger.warning(
                            "helm_parse_error",
                            scenario=scenario_dir.name,
                            error=str(e),
                        )

        return metrics

    def get_supported_tasks(self) -> list[str]:
        """Get list of supported HELM scenarios."""
        return list(self.SCENARIOS.keys())


class BenchmarkManager:
    """
    Manages benchmark execution across multiple frameworks.

    Provides unified interface for lm-evaluation-harness and HELM.
    """

    def __init__(self):
        """Initialize benchmark manager."""
        self.lm_eval = LMEvalHarness()
        self.helm = HELMBenchmark()

    async def run_benchmarks(
        self,
        model_path: str,
        benchmark_suite: str,
        tasks: list[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, MetricValue]:
        """
        Run benchmarks from specified suite.

        Args:
            model_path: Path to model
            benchmark_suite: "lm_eval" or "helm"
            tasks: Specific tasks to run (or all if None)
            config: Benchmark configuration

        Returns:
            Combined metrics from all benchmarks
        """
        config = config or {}

        if benchmark_suite == "lm_eval":
            tasks = tasks or list(self.lm_eval.BENCHMARK_TASKS.keys())
            return await self.lm_eval.run_benchmark(model_path, tasks, config)

        elif benchmark_suite == "helm":
            tasks = tasks or list(self.helm.SCENARIOS.keys())
            return await self.helm.run_benchmark(model_path, tasks, config)

        else:
            raise ValueError(f"Unknown benchmark suite: {benchmark_suite}")

    async def run_standard_suite(
        self,
        model_path: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, MetricValue]:
        """
        Run standard evaluation suite (common benchmarks from both).

        Args:
            model_path: Path to model
            config: Benchmark configuration

        Returns:
            Combined metrics
        """
        config = config or {}

        # Standard benchmarks for LLM evaluation
        lm_eval_tasks = ["mmlu", "hellaswag", "arc_challenge", "winogrande"]
        helm_tasks = ["boolq", "narrative_qa"]

        # Run in parallel
        lm_eval_result, helm_result = await asyncio.gather(
            self.lm_eval.run_benchmark(model_path, lm_eval_tasks, config),
            self.helm.run_benchmark(model_path, helm_tasks, config),
            return_exceptions=True,
        )

        metrics = {}

        if isinstance(lm_eval_result, dict):
            for key, value in lm_eval_result.items():
                metrics[f"lm_eval/{key}"] = value

        if isinstance(helm_result, dict):
            for key, value in helm_result.items():
                metrics[f"helm/{key}"] = value

        return metrics

    def get_all_supported_tasks(self) -> dict[str, list[str]]:
        """Get all supported benchmark tasks."""
        return {
            "lm_eval": self.lm_eval.get_supported_tasks(),
            "helm": self.helm.get_supported_tasks(),
        }
