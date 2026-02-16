"""Cross-cutting verifier: Statistical Forensics.

Detects fabricated or implausible statistics via:
- GRIM test (granularity-related inconsistency of means)
- SPRITE test (sample parameter reconstruction via iteration)
- Benford's law (first-digit distribution)
- P-curve analysis (p-value distribution shape)
"""
from __future__ import annotations

import asyncio
import math
import random
import time
from typing import Any

from backend.logging_config import get_logger
from backend.verification.cross_cutting_base import (
    CrossCuttingResult,
    CrossCuttingVerifier,
)

logger = get_logger(__name__)


class StatisticalForensicsVerifier(CrossCuttingVerifier):
    name = "statistical_forensics"
    default_weight = 0.10

    def is_applicable(self, task_result: dict, task_metadata: dict) -> bool:
        stat_keys = {"statistical_claims", "means", "p_values", "metrics", "results_summary"}
        return any(k in task_result and task_result[k] for k in stat_keys)

    async def verify(self, task_result: dict, task_metadata: dict) -> CrossCuttingResult:
        start = time.monotonic()

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {}
        warnings: list[str] = []

        # Extract data for each test
        means_data = self._extract_means(task_result)
        p_values = self._extract_p_values(task_result)
        all_numbers = self._extract_all_numbers(task_result)

        # Run all tests concurrently via threads (CPU-bound)
        grim_task = asyncio.to_thread(self._run_grim, means_data) if means_data else _noop_result("grim", "No means data")
        sprite_task = asyncio.to_thread(self._run_sprite, means_data) if means_data else _noop_result("sprite", "No means data")
        benford_task = asyncio.to_thread(self._run_benford, all_numbers) if len(all_numbers) >= 10 else _noop_result("benford", "Insufficient numbers (<10)")
        pcurve_task = asyncio.to_thread(self._run_pcurve, p_values) if len(p_values) >= 3 else _noop_result("pcurve", "Insufficient p-values (<3)")

        grim_result, sprite_result, benford_result, pcurve_result = await asyncio.gather(
            grim_task, sprite_task, benford_task, pcurve_task,
        )

        for name, result in [("grim", grim_result), ("sprite", sprite_result),
                             ("benford", benford_result), ("pcurve", pcurve_result)]:
            component_scores[name] = result.get("score", 0.5)
            details[name] = result
            if result.get("warnings"):
                warnings.extend(result["warnings"])

        # Equal weight for all 4 components
        applicable = [k for k in component_scores if details[k].get("applicable", True)]
        if applicable:
            score = sum(component_scores[k] for k in applicable) / len(applicable)
        else:
            score = 0.5  # neutral

        elapsed = time.monotonic() - start

        return CrossCuttingResult(
            verifier_name=self.name,
            score=round(score, 4),
            weight=self.default_weight,
            details=details,
            warnings=warnings,
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Data extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_means(task_result: dict) -> list[dict]:
        """Extract mean/n/sd triples from results."""
        means = task_result.get("means", [])
        if isinstance(means, list):
            return [m for m in means if isinstance(m, dict) and "mean" in m]

        # Also check statistical_claims
        claims = task_result.get("statistical_claims", [])
        extracted = []
        for claim in claims:
            if isinstance(claim, dict) and "mean" in claim:
                extracted.append(claim)
        return extracted

    @staticmethod
    def _extract_p_values(task_result: dict) -> list[float]:
        """Extract p-values from results."""
        direct = task_result.get("p_values", [])
        if isinstance(direct, list) and direct:
            return [float(p) for p in direct if isinstance(p, (int, float)) and 0 < p < 1]

        # From statistical_claims
        p_vals = []
        for claim in task_result.get("statistical_claims", []):
            if isinstance(claim, dict):
                p = claim.get("p_value")
                if isinstance(p, (int, float)) and 0 < p < 1:
                    p_vals.append(float(p))
        return p_vals

    @staticmethod
    def _extract_all_numbers(task_result: dict) -> list[float]:
        """Recursively extract all numeric values from the result."""
        numbers: list[float] = []

        def _walk(obj: Any) -> None:
            if isinstance(obj, (int, float)) and not isinstance(obj, bool):
                if obj != 0 and math.isfinite(obj):
                    numbers.append(float(abs(obj)))
            elif isinstance(obj, dict):
                for v in obj.values():
                    _walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    _walk(item)

        for key in ("metrics", "results_summary", "statistical_claims", "means", "p_values"):
            if key in task_result:
                _walk(task_result[key])
        return numbers

    # ------------------------------------------------------------------
    # GRIM test
    # ------------------------------------------------------------------

    @staticmethod
    def _run_grim(means_data: list[dict]) -> dict:
        """GRIM test: are reported means possible given sample size?

        For integer-valued measurements, n * mean must be an integer
        (within rounding tolerance).
        """
        if not means_data:
            return {"score": 0.5, "applicable": False, "note": "No means data"}

        passed = 0
        failed = 0
        results: list[dict] = []

        for entry in means_data:
            mean = entry.get("mean")
            n = entry.get("n") or entry.get("sample_size")
            if mean is None or n is None:
                continue
            if not isinstance(n, (int, float)) or n <= 0:
                continue

            n = int(n)
            product = n * float(mean)
            # Check if product is close to an integer
            remainder = abs(product - round(product))
            # Allow for rounding to 2 decimal places
            tolerance = n * 0.005 + 0.01
            is_consistent = remainder <= tolerance

            results.append({
                "mean": mean, "n": n,
                "product": round(product, 4),
                "remainder": round(remainder, 4),
                "consistent": is_consistent,
            })

            if is_consistent:
                passed += 1
            else:
                failed += 1

        if not results:
            return {"score": 0.5, "applicable": False, "note": "No mean+n pairs"}

        score = passed / len(results) if results else 0.5
        return {
            "score": round(score, 4),
            "applicable": True,
            "passed": passed,
            "failed": failed,
            "total": len(results),
            "results": results[:10],
            "warnings": [f"GRIM: {failed} inconsistent mean(s)"] if failed else [],
        }

    # ------------------------------------------------------------------
    # SPRITE test
    # ------------------------------------------------------------------

    @staticmethod
    def _run_sprite(means_data: list[dict]) -> dict:
        """SPRITE: can a mean+SD combination be achieved with integer data?

        Uses simulated annealing to find a valid dataset, capped at n=200.
        """
        results: list[dict] = []
        passed = 0
        failed = 0

        for entry in means_data:
            mean = entry.get("mean")
            sd = entry.get("sd") or entry.get("std")
            n = entry.get("n") or entry.get("sample_size")
            scale_min = entry.get("scale_min", 1)
            scale_max = entry.get("scale_max", 7)

            if mean is None or sd is None or n is None:
                continue
            n = int(n)
            if n <= 0 or n > 200:
                continue

            mean, sd = float(mean), float(sd)
            achievable = _sprite_check(mean, sd, n, int(scale_min), int(scale_max))

            results.append({
                "mean": mean, "sd": sd, "n": n,
                "achievable": achievable,
            })

            if achievable:
                passed += 1
            else:
                failed += 1

        if not results:
            return {"score": 0.5, "applicable": False, "note": "No mean+sd+n triples"}

        score = passed / len(results) if results else 0.5
        return {
            "score": round(score, 4),
            "applicable": True,
            "passed": passed,
            "failed": failed,
            "total": len(results),
            "results": results[:10],
            "warnings": [f"SPRITE: {failed} implausible mean/SD combination(s)"] if failed else [],
        }

    # ------------------------------------------------------------------
    # Benford's law
    # ------------------------------------------------------------------

    @staticmethod
    def _run_benford(numbers: list[float]) -> dict:
        """Check first-digit distribution against Benford's law."""
        if len(numbers) < 10:
            return {"score": 0.5, "applicable": False, "note": "Too few numbers"}

        # Count first digits
        digit_counts = [0] * 10
        for num in numbers:
            s = f"{abs(num):.10g}".lstrip("0").lstrip(".")
            if s and s[0].isdigit():
                d = int(s[0])
                if 1 <= d <= 9:
                    digit_counts[d] += 1

        total = sum(digit_counts[1:])
        if total < 10:
            return {"score": 0.5, "applicable": False, "note": "Too few leading digits"}

        # Expected Benford frequencies
        expected = [0.0] + [math.log10(1 + 1 / d) for d in range(1, 10)]
        observed_freq = [0.0] + [digit_counts[d] / total for d in range(1, 10)]

        # Chi-square statistic
        chi2 = sum(
            (observed_freq[d] - expected[d]) ** 2 / expected[d]
            for d in range(1, 10)
        ) * total

        # 8 degrees of freedom, critical value at p=0.05 is 15.507
        p_approx = _chi2_survival(chi2, 8)

        # Score based on p-value: high p = consistent with Benford
        if p_approx > 0.10:
            score = 1.0
        elif p_approx > 0.05:
            score = 0.7
        elif p_approx > 0.01:
            score = 0.4
        else:
            score = 0.1

        return {
            "score": round(score, 4),
            "applicable": True,
            "chi2": round(chi2, 4),
            "p_value_approx": round(p_approx, 6),
            "digit_counts": {str(d): digit_counts[d] for d in range(1, 10)},
            "total_numbers": total,
            "warnings": [f"Benford's law: chi2={chi2:.2f}, p={p_approx:.4f}"] if p_approx < 0.05 else [],
        }

    # ------------------------------------------------------------------
    # P-curve analysis
    # ------------------------------------------------------------------

    @staticmethod
    def _run_pcurve(p_values: list[float]) -> dict:
        """P-curve: significant p-values should be right-skewed under real effects."""
        if len(p_values) < 3:
            return {"score": 0.5, "applicable": False, "note": "Too few p-values"}

        sig_ps = [p for p in p_values if 0 < p < 0.05]
        if len(sig_ps) < 3:
            return {"score": 0.5, "applicable": False, "note": "Too few significant p-values"}

        # Under a real effect, p-values < 0.05 should be right-skewed
        # (more p-values near 0 than near 0.05)
        # Under p-hacking, distribution is uniform or left-skewed

        # Simple test: proportion below 0.025 should be > 0.5 if real effect
        below_midpoint = sum(1 for p in sig_ps if p < 0.025)
        prop_below = below_midpoint / len(sig_ps)

        # KS test against uniform on [0, 0.05]
        # Normalise to [0, 1]
        normalised = sorted([p / 0.05 for p in sig_ps])
        n = len(normalised)
        ks_stat = max(
            max(abs((i + 1) / n - normalised[i]) for i in range(n)),
            max(abs(normalised[i] - i / n) for i in range(n)),
        )

        # KS critical value approximation at alpha=0.05: 1.36 / sqrt(n)
        ks_critical = 1.36 / math.sqrt(n)
        uniform_rejected = ks_stat > ks_critical

        # Score: right-skewed = good (real effect), uniform/left-skewed = suspicious
        if prop_below > 0.6:
            score = 1.0
        elif prop_below > 0.4:
            score = 0.7 if not uniform_rejected else 0.5
        else:
            score = 0.3

        return {
            "score": round(score, 4),
            "applicable": True,
            "significant_p_count": len(sig_ps),
            "total_p_count": len(p_values),
            "proportion_below_025": round(prop_below, 4),
            "ks_statistic": round(ks_stat, 4),
            "ks_critical_005": round(ks_critical, 4),
            "uniform_rejected": uniform_rejected,
            "warnings": ["P-curve suggests possible p-hacking"] if score < 0.5 else [],
        }


# ------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------


def _sprite_check(
    target_mean: float,
    target_sd: float,
    n: int,
    scale_min: int,
    scale_max: int,
    max_iter: int = 5000,
) -> bool:
    """Simulated annealing SPRITE check."""
    if n <= 0:
        return False

    rng = random.Random(42)

    # Initialise dataset
    data = [rng.randint(scale_min, scale_max) for _ in range(n)]

    # Compute target sum
    target_sum = target_mean * n
    target_var = target_sd ** 2

    for _ in range(max_iter):
        current_mean = sum(data) / n
        current_var = sum((x - current_mean) ** 2 for x in data) / max(n - 1, 1) if n > 1 else 0
        current_sd = math.sqrt(current_var) if current_var > 0 else 0

        mean_ok = abs(current_mean - target_mean) < 0.005
        sd_ok = abs(current_sd - target_sd) < 0.05

        if mean_ok and sd_ok:
            return True

        # Adjust a random element
        idx = rng.randint(0, n - 1)
        old_val = data[idx]
        if current_mean < target_mean:
            new_val = min(old_val + 1, scale_max)
        elif current_mean > target_mean:
            new_val = max(old_val - 1, scale_min)
        else:
            new_val = rng.randint(scale_min, scale_max)
        data[idx] = new_val

    return False


def _chi2_survival(x: float, df: int) -> float:
    """Approximate chi-squared survival function P(X > x).

    Uses the Wilson-Hilferty normal approximation.
    """
    if x <= 0:
        return 1.0
    if df <= 0:
        return 0.0

    z = ((x / df) ** (1 / 3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))

    # Standard normal CDF approximation
    t = 1.0 / (1.0 + 0.2316419 * abs(z))
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + 1.330274429 * t))))
    pdf = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
    cdf = 1.0 - pdf * poly if z > 0 else pdf * poly

    return max(0.0, min(1.0, 1.0 - cdf))


async def _noop_result(name: str, note: str) -> dict:
    """Return a neutral result for non-applicable tests."""
    return {"score": 0.5, "applicable": False, "note": note}
