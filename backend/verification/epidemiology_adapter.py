"""Epidemiology verification: WHO GHO API + scipy statistical re-computation.

Validates incidence rates, odds ratios (2x2 tables), and survival analyses.
Primarily computational (scipy-based), with WHO data cross-referencing.
API-based (no Docker).
"""
from __future__ import annotations

import asyncio
import math
import time
from typing import Any

import httpx

from backend.logging_config import get_logger
from backend.verification.base import (
    VerificationAdapter,
    VerificationResult,
)

logger = get_logger(__name__)

WHO_GHO_API = "https://ghoapi.azureedge.net/api"
HTTP_TIMEOUT = 30

# Graceful degradation for lifelines (survival analysis)
try:
    from lifelines import KaplanMeierFitter
    from lifelines.statistics import logrank_test
    LIFELINES_AVAILABLE = True
except ImportError:
    LIFELINES_AVAILABLE = False
    logger.warning("lifelines_not_available", note="Survival analysis will use neutral scores")


class EpidemiologyAdapter(VerificationAdapter):
    domain = "epidemiology"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        claim_type = task_result.get("claim_type", "incidence_rate")

        if claim_type == "incidence_rate":
            return await self._verify_incidence_rate(task_result)
        elif claim_type == "odds_ratio":
            return await self._verify_odds_ratio(task_result)
        elif claim_type == "survival_analysis":
            return await self._verify_survival_analysis(task_result)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    # ------------------------------------------------------------------
    # incidence_rate
    # ------------------------------------------------------------------

    async def _verify_incidence_rate(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        rate = result.get("rate")
        denominator = result.get("denominator")
        cases = result.get("cases")
        comparison_rate = result.get("comparison_rate")
        disease_code = result.get("disease_code", "")

        if rate is None:
            return VerificationResult.fail(self.domain, ["rate is required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "incidence_rate"}

        # Component 1: rate_plausible (0.25)
        rate_result = await self._check_rate_plausible(rate, disease_code)
        component_scores["rate_plausible"] = rate_result["score"]
        details["rate_plausible"] = rate_result

        # Component 2: denominator_valid (0.20)
        denom_result = self._check_denominator_valid(denominator)
        component_scores["denominator_valid"] = denom_result["score"]
        details["denominator_valid"] = denom_result

        # Component 3: confidence_interval (0.25)
        ci_result = await asyncio.to_thread(
            self._check_confidence_interval, rate, cases, denominator, result,
        )
        component_scores["confidence_interval"] = ci_result["score"]
        details["confidence_interval"] = ci_result

        # Component 4: comparison_valid (0.30)
        comp_result = await self._check_comparison_valid(rate, comparison_rate, disease_code)
        component_scores["comparison_valid"] = comp_result["score"]
        details["comparison_valid"] = comp_result

        weights = {
            "rate_plausible": 0.25,
            "denominator_valid": 0.20,
            "confidence_interval": 0.25,
            "comparison_valid": 0.30,
        }
        score = sum(weights[k] * component_scores[k] for k in weights)
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
    # odds_ratio
    # ------------------------------------------------------------------

    async def _verify_odds_ratio(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        contingency_table = result.get("contingency_table", [])
        claimed_or = result.get("odds_ratio")
        claimed_ci_lower = result.get("ci_lower")
        claimed_ci_upper = result.get("ci_upper")
        claimed_pvalue = result.get("p_value")

        if not contingency_table:
            return VerificationResult.fail(self.domain, ["contingency_table (2x2) required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "odds_ratio"}

        # Component 1: contingency_valid (0.20)
        valid_result = self._check_contingency_valid(contingency_table)
        component_scores["contingency_valid"] = valid_result["score"]
        details["contingency_valid"] = valid_result

        # Component 2: or_recomputed (0.30)
        or_result = await asyncio.to_thread(
            self._recompute_odds_ratio, contingency_table, claimed_or,
        )
        component_scores["or_recomputed"] = or_result["score"]
        details["or_recomputed"] = or_result

        # Component 3: ci_recomputed (0.25)
        ci_result = await asyncio.to_thread(
            self._recompute_ci, contingency_table, claimed_ci_lower, claimed_ci_upper,
        )
        component_scores["ci_recomputed"] = ci_result["score"]
        details["ci_recomputed"] = ci_result

        # Component 4: pvalue_recomputed (0.25)
        pval_result = await asyncio.to_thread(
            self._recompute_pvalue, contingency_table, claimed_pvalue,
        )
        component_scores["pvalue_recomputed"] = pval_result["score"]
        details["pvalue_recomputed"] = pval_result

        weights = {
            "contingency_valid": 0.20,
            "or_recomputed": 0.30,
            "ci_recomputed": 0.25,
            "pvalue_recomputed": 0.25,
        }
        score = sum(weights[k] * component_scores[k] for k in weights)
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
    # survival_analysis
    # ------------------------------------------------------------------

    async def _verify_survival_analysis(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        time_data = result.get("time_data", [])
        event_data = result.get("event_data", [])
        group_labels = result.get("group_labels", [])
        claimed_median = result.get("median_survival")
        claimed_pvalue = result.get("p_value")
        claimed_hr = result.get("hazard_ratio")

        if not time_data or not event_data:
            return VerificationResult.fail(self.domain, ["time_data and event_data required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "survival_analysis"}
        warnings: list[str] = []

        # Component 1: data_valid (0.15)
        valid_result = self._check_survival_data_valid(time_data, event_data)
        component_scores["data_valid"] = valid_result["score"]
        details["data_valid"] = valid_result

        # Component 2: km_recomputed (0.35)
        km_result = await asyncio.to_thread(
            self._recompute_km, time_data, event_data, group_labels, claimed_median,
        )
        component_scores["km_recomputed"] = km_result["score"]
        details["km_recomputed"] = km_result
        if km_result.get("warnings"):
            warnings.extend(km_result["warnings"])

        # Component 3: logrank_recomputed (0.30)
        lr_result = await asyncio.to_thread(
            self._recompute_logrank, time_data, event_data, group_labels, claimed_pvalue,
        )
        component_scores["logrank_recomputed"] = lr_result["score"]
        details["logrank_recomputed"] = lr_result

        # Component 4: hazard_ratio_check (0.20)
        hr_result = self._check_hazard_ratio(claimed_hr)
        component_scores["hazard_ratio_check"] = hr_result["score"]
        details["hazard_ratio_check"] = hr_result

        weights = {
            "data_valid": 0.15,
            "km_recomputed": 0.35,
            "logrank_recomputed": 0.30,
            "hazard_ratio_check": 0.20,
        }
        score = sum(weights[k] * component_scores[k] for k in weights)
        score = min(1.0, round(score, 4))

        elapsed = time.monotonic() - start
        details["component_scores"] = component_scores

        return VerificationResult(
            passed=score >= 0.5,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details=details,
            warnings=warnings,
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Helpers — incidence rate
    # ------------------------------------------------------------------

    async def _check_rate_plausible(self, rate: float, disease_code: str) -> dict:
        """Check if claimed rate is in plausible range, optionally vs WHO data."""
        if not isinstance(rate, (int, float)) or rate < 0:
            return {"score": 0.0, "error": "Rate must be non-negative numeric"}

        # If WHO disease code provided, cross-reference
        if disease_code:
            try:
                async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                    resp = await client.get(f"{WHO_GHO_API}/{disease_code}")
                    if resp.status_code == 200:
                        data = resp.json()
                        values = data.get("value", [])
                        if values:
                            ref_values = [
                                v.get("NumericValue") for v in values
                                if v.get("NumericValue") is not None
                            ]
                            if ref_values:
                                ref_min = min(ref_values)
                                ref_max = max(ref_values)
                                # Allow 10x range around reference
                                if ref_min / 10 <= rate <= ref_max * 10:
                                    return {"score": 1.0, "plausible": True, "who_range": [ref_min, ref_max]}
                                return {"score": 0.3, "plausible": False, "who_range": [ref_min, ref_max]}
            except Exception as e:
                logger.warning("who_rate_check_failed", error=str(e))

        # Basic plausibility: incidence per 100k should be 0-100000
        if 0 <= rate <= 100000:
            return {"score": 0.7, "plausible": True, "note": "In general plausible range"}
        return {"score": 0.2, "plausible": False}

    @staticmethod
    def _check_denominator_valid(denominator: int | float | None) -> dict:
        """Check if population denominator is reasonable."""
        if denominator is None:
            return {"score": 0.5, "note": "No denominator provided"}

        if not isinstance(denominator, (int, float)) or denominator <= 0:
            return {"score": 0.0, "error": "Denominator must be positive"}

        # Reasonable study sizes: 10 to 10 billion
        if 10 <= denominator <= 1e10:
            return {"score": 1.0, "valid": True, "denominator": denominator}
        elif denominator < 10:
            return {"score": 0.3, "note": "Very small denominator", "denominator": denominator}
        else:
            return {"score": 0.2, "note": "Unreasonably large denominator"}

    @staticmethod
    def _check_confidence_interval(
        rate: float, cases: int | None, denominator: int | float | None, result: dict,
    ) -> dict:
        """Recompute CI from rate + sample size."""
        try:
            from scipy import stats as sp_stats
        except ImportError:
            return {"score": 0.5, "note": "scipy unavailable"}

        claimed_ci_lower = result.get("ci_lower")
        claimed_ci_upper = result.get("ci_upper")

        if claimed_ci_lower is None or claimed_ci_upper is None:
            return {"score": 0.5, "note": "No CI claimed"}

        if cases is not None and denominator is not None and denominator > 0:
            p_hat = cases / denominator
            se = math.sqrt(p_hat * (1 - p_hat) / denominator) if 0 < p_hat < 1 else 0
            z = sp_stats.norm.ppf(0.975)
            computed_lower = (p_hat - z * se) * (rate / p_hat) if p_hat > 0 else 0
            computed_upper = (p_hat + z * se) * (rate / p_hat) if p_hat > 0 else 0

            lower_match = abs(claimed_ci_lower - computed_lower) <= max(abs(computed_lower) * 0.1, 0.01)
            upper_match = abs(claimed_ci_upper - computed_upper) <= max(abs(computed_upper) * 0.1, 0.01)

            score = (0.5 if lower_match else 0.0) + (0.5 if upper_match else 0.0)
            return {
                "score": round(score, 4),
                "claimed_ci": [claimed_ci_lower, claimed_ci_upper],
                "computed_ci": [round(computed_lower, 4), round(computed_upper, 4)],
            }

        # Just check CI ordering
        if claimed_ci_lower <= rate <= claimed_ci_upper:
            return {"score": 0.7, "ci_ordered": True}
        return {"score": 0.2, "ci_ordered": False}

    async def _check_comparison_valid(
        self, rate: float, comparison_rate: float | None, disease_code: str,
    ) -> dict:
        """If comparative rate given, check direction + magnitude."""
        if comparison_rate is None:
            return {"score": 0.5, "note": "No comparison rate provided"}

        if not isinstance(comparison_rate, (int, float)) or comparison_rate < 0:
            return {"score": 0.0, "error": "Comparison rate must be non-negative"}

        ratio = rate / comparison_rate if comparison_rate > 0 else float("inf")
        if 0.01 <= ratio <= 100:
            return {"score": 1.0, "plausible": True, "rate_ratio": round(ratio, 4)}
        return {"score": 0.2, "plausible": False, "rate_ratio": round(ratio, 4)}

    # ------------------------------------------------------------------
    # Helpers — odds ratio
    # ------------------------------------------------------------------

    @staticmethod
    def _check_contingency_valid(table: list) -> dict:
        """Validate 2x2 contingency table."""
        try:
            if len(table) != 2 or len(table[0]) != 2 or len(table[1]) != 2:
                return {"score": 0.0, "error": "Must be 2x2 table"}

            a, b = table[0][0], table[0][1]
            c, d = table[1][0], table[1][1]

            if any(not isinstance(v, (int, float)) for v in [a, b, c, d]):
                return {"score": 0.0, "error": "All cells must be numeric"}

            if any(v < 0 for v in [a, b, c, d]):
                return {"score": 0.0, "error": "All cells must be non-negative"}

            total = a + b + c + d
            if total == 0:
                return {"score": 0.0, "error": "Empty table"}

            return {"score": 1.0, "valid": True, "total": total, "cells": [a, b, c, d]}
        except Exception:
            return {"score": 0.0, "error": "Invalid table format"}

    @staticmethod
    def _recompute_odds_ratio(table: list, claimed_or: float | None) -> dict:
        """Recompute OR from 2x2 table."""
        try:
            a, b = table[0][0], table[0][1]
            c, d = table[1][0], table[1][1]

            if b == 0 or c == 0:
                return {"score": 0.5, "note": "Zero cell — OR undefined or infinite"}

            computed_or = (a * d) / (b * c)

            if claimed_or is None:
                return {"score": 0.5, "note": "No OR claimed", "computed_or": round(computed_or, 4)}

            tolerance = max(abs(computed_or) * 0.05, 0.01)
            match = abs(claimed_or - computed_or) <= tolerance

            return {
                "score": 1.0 if match else 0.2,
                "match": match,
                "claimed": claimed_or,
                "computed": round(computed_or, 4),
            }
        except Exception as e:
            return {"score": 0.0, "error": str(e)}

    @staticmethod
    def _recompute_ci(table: list, claimed_lower: float | None, claimed_upper: float | None) -> dict:
        """Recompute 95% CI for OR using Woolf's method."""
        try:
            a, b = table[0][0], table[0][1]
            c, d = table[1][0], table[1][1]

            if any(v == 0 for v in [a, b, c, d]):
                return {"score": 0.5, "note": "Zero cell — CI computation unreliable"}

            ln_or = math.log((a * d) / (b * c))
            se_ln_or = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
            lower = math.exp(ln_or - 1.96 * se_ln_or)
            upper = math.exp(ln_or + 1.96 * se_ln_or)

            if claimed_lower is None or claimed_upper is None:
                return {
                    "score": 0.5,
                    "note": "No CI claimed",
                    "computed_ci": [round(lower, 4), round(upper, 4)],
                }

            lower_tol = max(abs(lower) * 0.1, 0.01)
            upper_tol = max(abs(upper) * 0.1, 0.01)
            lower_match = abs(claimed_lower - lower) <= lower_tol
            upper_match = abs(claimed_upper - upper) <= upper_tol

            score = (0.5 if lower_match else 0.0) + (0.5 if upper_match else 0.0)

            return {
                "score": round(score, 4),
                "claimed_ci": [claimed_lower, claimed_upper],
                "computed_ci": [round(lower, 4), round(upper, 4)],
            }
        except Exception as e:
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _recompute_pvalue(table: list, claimed_pvalue: float | None) -> dict:
        """Recompute p-value from 2x2 table using Fisher's exact or chi-square."""
        try:
            from scipy import stats as sp_stats
        except ImportError:
            return {"score": 0.5, "note": "scipy unavailable"}

        try:
            a, b = int(table[0][0]), int(table[0][1])
            c, d = int(table[1][0]), int(table[1][1])

            total = a + b + c + d
            # Use Fisher's exact for small samples, chi-square for large
            if total < 100:
                _, recomputed_p = sp_stats.fisher_exact([[a, b], [c, d]])
            else:
                chi2, recomputed_p, _, _ = sp_stats.chi2_contingency([[a, b], [c, d]])

            if claimed_pvalue is None:
                return {"score": 0.5, "note": "No p-value claimed", "computed_p": recomputed_p}

            tolerance = max(abs(recomputed_p) * 0.05, 1e-10)
            match = abs(claimed_pvalue - recomputed_p) <= tolerance

            return {
                "score": 1.0 if match else 0.2,
                "match": match,
                "claimed_p": claimed_pvalue,
                "computed_p": recomputed_p,
            }
        except Exception as e:
            return {"score": 0.3, "error": str(e)}

    # ------------------------------------------------------------------
    # Helpers — survival analysis
    # ------------------------------------------------------------------

    @staticmethod
    def _check_survival_data_valid(time_data: list, event_data: list) -> dict:
        """Check that time/event arrays are well-formed."""
        if len(time_data) != len(event_data):
            return {"score": 0.0, "error": "time_data and event_data must have same length"}

        if len(time_data) < 3:
            return {"score": 0.0, "error": "Need at least 3 observations"}

        if any(not isinstance(t, (int, float)) or t < 0 for t in time_data):
            return {"score": 0.0, "error": "time_data must be non-negative numbers"}

        if any(e not in (0, 1) for e in event_data):
            return {"score": 0.0, "error": "event_data must be 0 or 1"}

        n_events = sum(event_data)
        return {
            "score": 1.0,
            "valid": True,
            "n_observations": len(time_data),
            "n_events": n_events,
            "censoring_rate": round(1 - n_events / len(event_data), 3),
        }

    @staticmethod
    def _recompute_km(
        time_data: list, event_data: list, group_labels: list, claimed_median: float | None,
    ) -> dict:
        """Re-run Kaplan-Meier and compare median survival."""
        if not LIFELINES_AVAILABLE:
            return {"score": 0.5, "warnings": ["lifelines unavailable — KM not recomputed"]}

        try:
            import numpy as np

            times = np.array(time_data, dtype=float)
            events = np.array(event_data, dtype=int)

            kmf = KaplanMeierFitter()
            kmf.fit(times, event_observed=events)

            computed_median = kmf.median_survival_time_
            if math.isinf(computed_median) or math.isnan(computed_median):
                computed_note = "Median not reached"
                if claimed_median is None:
                    return {"score": 0.7, "note": computed_note}
                return {"score": 0.5, "note": computed_note, "claimed_median": claimed_median}

            if claimed_median is None:
                return {"score": 0.5, "note": "No median claimed", "computed_median": float(computed_median)}

            tolerance = max(abs(computed_median) * 0.1, 0.5)
            match = abs(claimed_median - computed_median) <= tolerance

            return {
                "score": 1.0 if match else 0.3,
                "match": match,
                "claimed_median": claimed_median,
                "computed_median": round(float(computed_median), 4),
            }
        except Exception as e:
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _recompute_logrank(
        time_data: list, event_data: list, group_labels: list, claimed_pvalue: float | None,
    ) -> dict:
        """Re-run log-rank test between two groups."""
        if not LIFELINES_AVAILABLE:
            return {"score": 0.5, "note": "lifelines unavailable — log-rank not recomputed"}

        if not group_labels or len(group_labels) != len(time_data):
            return {"score": 0.5, "note": "group_labels required for log-rank test"}

        try:
            import numpy as np

            times = np.array(time_data, dtype=float)
            events = np.array(event_data, dtype=int)
            groups = np.array(group_labels)

            unique_groups = np.unique(groups)
            if len(unique_groups) != 2:
                return {"score": 0.5, "note": f"Need exactly 2 groups, got {len(unique_groups)}"}

            mask1 = groups == unique_groups[0]
            mask2 = groups == unique_groups[1]

            lr_result = logrank_test(
                times[mask1], times[mask2],
                event_observed_A=events[mask1],
                event_observed_B=events[mask2],
            )
            computed_p = lr_result.p_value

            if claimed_pvalue is None:
                return {"score": 0.5, "note": "No p-value claimed", "computed_p": computed_p}

            tolerance = max(abs(computed_p) * 0.05, 1e-10)
            match = abs(claimed_pvalue - computed_p) <= tolerance

            return {
                "score": 1.0 if match else 0.2,
                "match": match,
                "claimed_p": claimed_pvalue,
                "computed_p": computed_p,
                "test_statistic": lr_result.test_statistic,
            }
        except Exception as e:
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _check_hazard_ratio(hr: float | None) -> dict:
        """Check if hazard ratio is in plausible range."""
        if hr is None:
            return {"score": 0.5, "note": "No hazard ratio claimed"}

        if not isinstance(hr, (int, float)) or hr <= 0:
            return {"score": 0.0, "error": "HR must be positive"}

        # Typical HR range: 0.1 to 10
        if 0.1 <= hr <= 10:
            return {"score": 1.0, "plausible": True, "hazard_ratio": hr}
        elif 0.01 <= hr <= 100:
            return {"score": 0.5, "plausible": "borderline", "hazard_ratio": hr}
        else:
            return {"score": 0.1, "plausible": False, "hazard_ratio": hr}
