"""Metric comparison and statistical validation for ML experiments."""

import math
import statistics
from dataclasses import dataclass
from typing import Any

from platform.verification_engines.ml_verifier.base import (
    MetricComparison,
    MetricComparisonResult,
    MetricValue,
)
from platform.verification_engines.ml_verifier.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class StatisticalTest:
    """Result of a statistical test."""

    test_name: str
    statistic: float
    p_value: float
    significant: bool
    confidence_level: float = 0.95


class MetricComparator:
    """
    Compares claimed vs reproduced metrics with statistical rigor.

    Features:
    - Configurable tolerance thresholds per metric type
    - Statistical significance testing
    - Confidence interval analysis
    - Support for multi-run aggregation
    """

    # Default tolerances for common metrics (percentage)
    DEFAULT_TOLERANCES = {
        # Classification metrics
        "accuracy": 1.0,
        "precision": 1.5,
        "recall": 1.5,
        "f1": 1.5,
        "f1_score": 1.5,
        "auc": 1.0,
        "roc_auc": 1.0,

        # Regression metrics
        "mse": 5.0,
        "rmse": 5.0,
        "mae": 5.0,
        "r2": 2.0,

        # NLP metrics
        "bleu": 2.0,
        "rouge": 2.0,
        "rouge1": 2.0,
        "rouge2": 2.0,
        "rougeL": 2.0,
        "perplexity": 5.0,

        # Generation metrics
        "fid": 10.0,  # Frechet Inception Distance
        "inception_score": 5.0,

        # Speed metrics (more tolerance)
        "throughput": 15.0,
        "latency": 15.0,
        "tokens_per_second": 10.0,
    }

    def __init__(self, custom_tolerances: dict[str, float] | None = None):
        """
        Initialize metric comparator.

        Args:
            custom_tolerances: Custom tolerance percentages per metric
        """
        self._tolerances = {**self.DEFAULT_TOLERANCES}
        if custom_tolerances:
            self._tolerances.update(custom_tolerances)

    def compare_metrics(
        self,
        claimed: dict[str, float],
        reproduced: dict[str, float],
        tolerance_override: float | None = None,
    ) -> MetricComparisonResult:
        """
        Compare claimed vs reproduced metrics.

        Args:
            claimed: Claimed metric values
            reproduced: Reproduced metric values
            tolerance_override: Optional override for all tolerances

        Returns:
            MetricComparisonResult with comparisons
        """
        comparisons = []
        all_within_tolerance = True

        # Compare all metrics present in both
        common_metrics = set(claimed.keys()) & set(reproduced.keys())

        for metric_name in common_metrics:
            claimed_value = claimed[metric_name]
            reproduced_value = reproduced[metric_name]

            # Get tolerance
            if tolerance_override is not None:
                tolerance = tolerance_override
            else:
                tolerance = self._get_tolerance(metric_name)

            # Calculate deviation
            if claimed_value == 0:
                deviation = reproduced_value
                deviation_percent = 100.0 if reproduced_value != 0 else 0.0
            else:
                deviation = reproduced_value - claimed_value
                deviation_percent = abs(deviation / claimed_value) * 100

            within_tolerance = deviation_percent <= tolerance

            comparison = MetricComparison(
                metric_name=metric_name,
                claimed_value=claimed_value,
                reproduced_value=reproduced_value,
                deviation=deviation,
                deviation_percent=deviation_percent,
                within_tolerance=within_tolerance,
                tolerance_percent=tolerance,
            )
            comparisons.append(comparison)

            if not within_tolerance:
                all_within_tolerance = False

        # Check for metrics only in claimed (expected but not reproduced)
        missing_metrics = set(claimed.keys()) - set(reproduced.keys())
        if missing_metrics:
            all_within_tolerance = False
            for metric_name in missing_metrics:
                comparisons.append(MetricComparison(
                    metric_name=metric_name,
                    claimed_value=claimed[metric_name],
                    reproduced_value=float("nan"),
                    deviation=float("nan"),
                    deviation_percent=float("nan"),
                    within_tolerance=False,
                    tolerance_percent=self._get_tolerance(metric_name),
                ))

        message = "All metrics within tolerance" if all_within_tolerance else "Some metrics outside tolerance"

        return MetricComparisonResult(
            passed=all_within_tolerance,
            message=message,
            comparisons=comparisons,
            all_within_tolerance=all_within_tolerance,
            claimed_metrics=claimed,
            reproduced_metrics=reproduced,
        )

    def _get_tolerance(self, metric_name: str) -> float:
        """Get tolerance for a metric."""
        # Normalize metric name
        normalized = metric_name.lower().replace("-", "_").replace(" ", "_")

        # Check exact match
        if normalized in self._tolerances:
            return self._tolerances[normalized]

        # Check prefix matches
        for key, value in self._tolerances.items():
            if normalized.startswith(key) or normalized.endswith(key):
                return value

        # Default tolerance
        return settings.default_tolerance_percent

    def aggregate_runs(
        self,
        runs: list[dict[str, float]],
    ) -> dict[str, MetricValue]:
        """
        Aggregate metrics from multiple runs.

        Args:
            runs: List of metric dicts from different runs

        Returns:
            Aggregated metrics with statistics
        """
        if not runs:
            return {}

        # Collect all metric names
        all_metrics = set()
        for run in runs:
            all_metrics.update(run.keys())

        aggregated = {}
        for metric_name in all_metrics:
            values = [run[metric_name] for run in runs if metric_name in run]

            if not values:
                continue

            mean_val = statistics.mean(values)
            std_dev = statistics.stdev(values) if len(values) > 1 else 0.0

            # Calculate 95% confidence interval
            n = len(values)
            if n > 1:
                stderr = std_dev / math.sqrt(n)
                margin = 1.96 * stderr  # 95% CI
                ci = (mean_val - margin, mean_val + margin)
            else:
                ci = (mean_val, mean_val)

            aggregated[metric_name] = MetricValue(
                name=metric_name,
                value=mean_val,
                std_dev=std_dev,
                confidence_interval=ci,
                sample_size=n,
            )

        return aggregated

    def statistical_test(
        self,
        claimed_runs: list[dict[str, float]],
        reproduced_runs: list[dict[str, float]],
        metric_name: str,
    ) -> StatisticalTest | None:
        """
        Perform statistical test to compare claimed vs reproduced.

        Uses Welch's t-test for comparing means.

        Args:
            claimed_runs: Runs from original paper
            reproduced_runs: Reproduced runs
            metric_name: Metric to compare

        Returns:
            StatisticalTest result or None if insufficient data
        """
        claimed_values = [r[metric_name] for r in claimed_runs if metric_name in r]
        reproduced_values = [r[metric_name] for r in reproduced_runs if metric_name in r]

        if len(claimed_values) < 2 or len(reproduced_values) < 2:
            return None

        # Welch's t-test
        n1, n2 = len(claimed_values), len(reproduced_values)
        mean1, mean2 = statistics.mean(claimed_values), statistics.mean(reproduced_values)
        var1, var2 = statistics.variance(claimed_values), statistics.variance(reproduced_values)

        # Pooled standard error
        se = math.sqrt(var1 / n1 + var2 / n2)

        if se == 0:
            return StatisticalTest(
                test_name="welch_t_test",
                statistic=0.0,
                p_value=1.0,
                significant=False,
            )

        # t-statistic
        t_stat = (mean1 - mean2) / se

        # Degrees of freedom (Welch-Satterthwaite)
        df_num = (var1 / n1 + var2 / n2) ** 2
        df_denom = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
        df = df_num / df_denom if df_denom > 0 else 1

        # Approximate p-value using normal distribution (for simplicity)
        # In production, use scipy.stats.t.sf
        z = abs(t_stat)
        p_value = 2 * (1 - self._normal_cdf(z))

        significant = p_value < 0.05

        return StatisticalTest(
            test_name="welch_t_test",
            statistic=t_stat,
            p_value=p_value,
            significant=significant,
        )

    def _normal_cdf(self, z: float) -> float:
        """Approximate standard normal CDF."""
        # Approximation using error function
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))


class MetricParser:
    """
    Parses metrics from various output formats.

    Supports:
    - JSON output files
    - TensorBoard logs
    - wandb exports
    - Plain text logs
    """

    def parse_json_metrics(self, json_data: dict[str, Any]) -> dict[str, float]:
        """Parse metrics from JSON format."""
        metrics = {}

        def extract_metrics(obj: Any, prefix: str = "") -> None:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_prefix = f"{prefix}{key}/" if prefix else f"{key}/"
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        # This is a metric value
                        metric_name = new_prefix.rstrip("/")
                        metrics[metric_name] = float(value)
                    else:
                        extract_metrics(value, new_prefix)
            elif isinstance(obj, list):
                # Take last value if it's a list of numbers
                if obj and isinstance(obj[-1], (int, float)):
                    metrics[prefix.rstrip("/")] = float(obj[-1])

        extract_metrics(json_data)
        return metrics

    def parse_text_metrics(self, text: str) -> dict[str, float]:
        """
        Parse metrics from plain text output.

        Looks for patterns like:
        - "accuracy: 0.95"
        - "loss = 0.05"
        - "F1 Score: 0.92"
        """
        import re

        metrics = {}

        # Pattern: metric_name: value or metric_name = value
        patterns = [
            r"(\w+[\w\s]*?)[:=]\s*(\d+\.?\d*)",
            r"(\w+[\w\s]*?)\s+(\d+\.?\d*)\s*%",  # Percentage format
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for name, value in matches:
                metric_name = name.strip().lower().replace(" ", "_")
                try:
                    metrics[metric_name] = float(value)
                except ValueError:
                    continue

        return metrics

    def parse_tensorboard_scalars(self, log_dir: str) -> dict[str, list[float]]:
        """Parse scalars from TensorBoard logs."""
        # Placeholder - would use tensorboard.backend.event_processing
        return {}

    def parse_wandb_export(self, export_file: str) -> dict[str, float]:
        """Parse metrics from wandb export."""
        import json
        from pathlib import Path

        data = json.loads(Path(export_file).read_text())

        metrics = {}
        if "summary" in data:
            for key, value in data["summary"].items():
                if isinstance(value, (int, float)) and not key.startswith("_"):
                    metrics[key] = float(value)

        return metrics
