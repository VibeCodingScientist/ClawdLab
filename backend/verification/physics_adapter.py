"""Physics verification: conservation laws, dimensional analysis, symbolic math.

CPU-only (no Docker) — pint and sympy via asyncio.to_thread().
"""
from __future__ import annotations

import asyncio
import math
import time
from typing import Any

from backend.logging_config import get_logger
from backend.verification.base import (
    VerificationAdapter,
    VerificationBadge,
    VerificationResult,
)

logger = get_logger(__name__)

# Graceful imports
try:
    import pint
    PINT_AVAILABLE = True
    _ureg = pint.UnitRegistry()
except ImportError:
    PINT_AVAILABLE = False
    _ureg = None
    logger.warning("pint_not_available")

try:
    import sympy
    from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False
    logger.warning("sympy_not_available")


class PhysicsAdapter(VerificationAdapter):
    domain = "physics"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        claim_type = task_result.get("claim_type", "numerical_simulation")

        if claim_type == "numerical_simulation":
            return await self._verify_simulation(task_result)
        elif claim_type == "analytical_derivation":
            return await self._verify_derivation(task_result)
        elif claim_type == "dimensional_analysis":
            return await self._verify_dimensions(task_result)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    # ------------------------------------------------------------------
    # numerical_simulation
    # ------------------------------------------------------------------

    async def _verify_simulation(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        sim_data = result.get("simulation_data", {})
        conservation = result.get("conservation_quantities", {})

        if not sim_data and not conservation:
            return VerificationResult.fail(self.domain, ["No simulation_data or conservation_quantities"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "numerical_simulation"}
        warnings: list[str] = []

        # Component 1: Conservation laws (0.35)
        conserv_result = await asyncio.to_thread(
            self._check_conservation, conservation, sim_data,
        )
        component_scores["conservation_laws"] = conserv_result["score"]
        details["conservation"] = conserv_result
        if conserv_result.get("warnings"):
            warnings.extend(conserv_result["warnings"])

        # Component 2: Stability (0.25)
        stability_result = await asyncio.to_thread(self._check_stability, sim_data)
        component_scores["stability"] = stability_result["score"]
        details["stability"] = stability_result

        # Component 3: Convergence (0.25)
        convergence_result = await asyncio.to_thread(
            self._check_convergence, sim_data,
        )
        component_scores["convergence"] = convergence_result["score"]
        details["convergence"] = convergence_result

        # Component 4: Boundary conditions (0.15)
        boundary_result = await asyncio.to_thread(
            self._check_boundary_conditions, sim_data,
        )
        component_scores["boundary_conditions"] = boundary_result["score"]
        details["boundary_conditions"] = boundary_result

        weights = {
            "conservation_laws": 0.35,
            "stability": 0.25,
            "convergence": 0.25,
            "boundary_conditions": 0.15,
        }
        score = sum(weights[k] * component_scores.get(k, 0.0) for k in weights)
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
    # analytical_derivation
    # ------------------------------------------------------------------

    async def _verify_derivation(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        expression = result.get("expression")
        units = result.get("units", {})
        lhs = result.get("lhs")
        rhs = result.get("rhs")

        if not expression and not (lhs and rhs):
            return VerificationResult.fail(
                self.domain, ["No expression or lhs/rhs provided"],
            )

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "analytical_derivation"}
        warnings: list[str] = []

        # Component 1: Dimensional consistency (0.40)
        dim_result = await asyncio.to_thread(
            self._check_dimensional_consistency, expression or f"({lhs}) - ({rhs})", units,
        )
        component_scores["dimensional_consistency"] = dim_result["score"]
        details["dimensional_consistency"] = dim_result

        # Component 2: Symbolic validity (0.30)
        sym_result = await asyncio.to_thread(
            self._check_symbolic_validity, expression, lhs, rhs,
        )
        component_scores["symbolic_validity"] = sym_result["score"]
        details["symbolic_validity"] = sym_result

        # Component 3: Unit consistency (0.30)
        unit_result = await asyncio.to_thread(
            self._check_unit_consistency, units,
        )
        component_scores["unit_consistency"] = unit_result["score"]
        details["unit_consistency"] = unit_result

        weights = {
            "dimensional_consistency": 0.40,
            "symbolic_validity": 0.30,
            "unit_consistency": 0.30,
        }
        score = sum(weights[k] * component_scores.get(k, 0.0) for k in weights)
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
    # dimensional_analysis
    # ------------------------------------------------------------------

    async def _verify_dimensions(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        expression = result.get("expression")
        lhs = result.get("lhs")
        rhs = result.get("rhs")
        units = result.get("units", {})

        if not expression and not (lhs and rhs):
            return VerificationResult.fail(self.domain, ["No expression or lhs/rhs"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "dimensional_analysis"}

        # Component 1: Dimensions match (0.50)
        dim_result = await asyncio.to_thread(
            self._check_dimensional_consistency, expression or f"({lhs}) - ({rhs})", units,
        )
        component_scores["dimensions_match"] = dim_result["score"]
        details["dimensions"] = dim_result

        # Component 2: Units consistent (0.30)
        unit_result = await asyncio.to_thread(
            self._check_unit_consistency, units,
        )
        component_scores["units_consistent"] = unit_result["score"]
        details["units"] = unit_result

        # Component 3: Expression valid (0.20)
        expr_result = await asyncio.to_thread(
            self._check_expression_valid, expression or f"({lhs}) - ({rhs})",
        )
        component_scores["expression_valid"] = expr_result["score"]
        details["expression"] = expr_result

        weights = {"dimensions_match": 0.50, "units_consistent": 0.30, "expression_valid": 0.20}
        score = sum(weights[k] * component_scores.get(k, 0.0) for k in weights)
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
    # Component check implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _check_conservation(
        conservation: dict, sim_data: dict,
    ) -> dict:
        """Check conservation of energy/momentum/mass."""
        if not conservation:
            return {"score": 0.5, "applicable": False, "note": "No conservation quantities"}

        results: list[dict] = []
        conserved = 0

        for quantity, data in conservation.items():
            if not isinstance(data, dict):
                continue

            initial = data.get("initial")
            final = data.get("final")

            if initial is None or final is None:
                continue

            if not isinstance(initial, (int, float)) or not isinstance(final, (int, float)):
                continue

            tolerance = data.get("tolerance", max(abs(initial) * 0.01, 1e-10))
            deviation = abs(final - initial)
            is_conserved = deviation <= tolerance

            results.append({
                "quantity": quantity,
                "initial": initial,
                "final": final,
                "deviation": deviation,
                "tolerance": tolerance,
                "conserved": is_conserved,
            })

            if is_conserved:
                conserved += 1

        if not results:
            return {"score": 0.5, "applicable": False, "note": "No initial/final pairs"}

        score = conserved / len(results)
        return {
            "score": round(score, 4),
            "applicable": True,
            "conserved": conserved,
            "total": len(results),
            "results": results,
            "warnings": [f"Conservation violated for {len(results) - conserved} quantit(ies)"]
                        if conserved < len(results) else [],
        }

    @staticmethod
    def _check_stability(sim_data: dict) -> dict:
        """Check for diverging quantities (NaN, Inf, exponential growth)."""
        time_series = sim_data.get("time_series", {})
        if not time_series:
            return {"score": 0.5, "applicable": False, "note": "No time series data"}

        issues: list[str] = []

        for name, values in time_series.items():
            if not isinstance(values, list):
                continue

            has_nan = any(
                (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))
                for v in values if isinstance(v, (int, float))
            )
            if has_nan:
                issues.append(f"{name}: contains NaN/Inf")
                continue

            # Check for exponential growth in last quarter
            numeric_vals = [float(v) for v in values if isinstance(v, (int, float))]
            if len(numeric_vals) < 4:
                continue

            quarter = len(numeric_vals) // 4
            last_quarter = numeric_vals[-quarter:]
            first_quarter = numeric_vals[:quarter]

            if first_quarter and last_quarter:
                first_mean = sum(abs(v) for v in first_quarter) / len(first_quarter)
                last_mean = sum(abs(v) for v in last_quarter) / len(last_quarter)

                if first_mean > 0 and last_mean / first_mean > 100:
                    issues.append(f"{name}: possible exponential growth (ratio={last_mean / first_mean:.0f})")

        if not time_series:
            score = 0.5
        elif not issues:
            score = 1.0
        else:
            score = max(0.0, 1.0 - 0.3 * len(issues))

        return {
            "score": round(score, 4),
            "applicable": bool(time_series),
            "series_checked": len(time_series),
            "issues": issues[:10],
        }

    @staticmethod
    def _check_convergence(sim_data: dict) -> dict:
        """Check if error decreases with mesh refinement."""
        refinement = sim_data.get("mesh_refinement") or sim_data.get("convergence_data")
        if not refinement:
            return {"score": 0.5, "applicable": False, "note": "No convergence data"}

        if isinstance(refinement, list) and len(refinement) >= 2:
            # Expect list of {resolution, error} dicts
            errors = []
            for entry in refinement:
                if isinstance(entry, dict) and "error" in entry:
                    errors.append(float(entry["error"]))

            if len(errors) >= 2:
                # Error should decrease monotonically
                decreasing = all(errors[i] >= errors[i + 1] for i in range(len(errors) - 1))
                if decreasing:
                    score = 1.0
                else:
                    # Partial credit for mostly decreasing
                    n_decreasing = sum(1 for i in range(len(errors) - 1) if errors[i] >= errors[i + 1])
                    score = n_decreasing / (len(errors) - 1)

                return {
                    "score": round(score, 4),
                    "applicable": True,
                    "errors": errors,
                    "monotonically_decreasing": decreasing,
                }

        return {"score": 0.5, "applicable": False, "note": "Could not parse convergence data"}

    @staticmethod
    def _check_boundary_conditions(sim_data: dict) -> dict:
        """Check boundary values consistency."""
        boundaries = sim_data.get("boundary_conditions", {})
        if not boundaries:
            return {"score": 0.5, "applicable": False, "note": "No boundary conditions specified"}

        results = sim_data.get("boundary_results", {})
        if not results:
            return {"score": 0.5, "applicable": False, "note": "No boundary results to check"}

        matches = 0
        total = 0
        checks: list[dict] = []

        for location, expected in boundaries.items():
            actual = results.get(location)
            if actual is None:
                checks.append({"location": location, "match": False, "note": "No result"})
                total += 1
                continue

            total += 1
            if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
                tolerance = max(abs(expected) * 0.01, 1e-10)
                match = abs(expected - actual) <= tolerance
            else:
                match = expected == actual

            checks.append({
                "location": location,
                "expected": expected,
                "actual": actual,
                "match": match,
            })
            if match:
                matches += 1

        score = matches / total if total > 0 else 0.5
        return {
            "score": round(score, 4),
            "applicable": True,
            "checks": checks,
            "matches": matches,
            "total": total,
        }

    @staticmethod
    def _check_dimensional_consistency(expression: str, units: dict) -> dict:
        """Check all terms in an equation have the same dimensions."""
        if not PINT_AVAILABLE:
            return {"score": 0.5, "note": "pint unavailable"}

        if not units:
            return {"score": 0.5, "applicable": False, "note": "No units specified"}

        try:
            # Try to parse each variable's units and check consistency
            parsed_units: dict[str, Any] = {}
            for var_name, unit_str in units.items():
                try:
                    parsed_units[var_name] = _ureg.parse_expression(unit_str)
                except Exception:
                    return {
                        "score": 0.3,
                        "applicable": True,
                        "error": f"Could not parse unit: {unit_str} for {var_name}",
                    }

            # If we have lhs_units and rhs_units, check they're compatible
            lhs_unit = parsed_units.get("lhs") or parsed_units.get("result")
            rhs_unit = parsed_units.get("rhs") or parsed_units.get("expression")

            if lhs_unit is not None and rhs_unit is not None:
                try:
                    lhs_unit.to(rhs_unit.units)
                    return {
                        "score": 1.0,
                        "applicable": True,
                        "lhs_dimensions": str(lhs_unit.dimensionality),
                        "rhs_dimensions": str(rhs_unit.dimensionality),
                        "compatible": True,
                    }
                except pint.DimensionalityError:
                    return {
                        "score": 0.0,
                        "applicable": True,
                        "lhs_dimensions": str(lhs_unit.dimensionality),
                        "rhs_dimensions": str(rhs_unit.dimensionality),
                        "compatible": False,
                    }

            return {"score": 0.7, "applicable": True, "note": "Units parsed but no LHS/RHS pair to compare"}

        except Exception as e:
            return {"score": 0.3, "applicable": True, "error": str(e)}

    @staticmethod
    def _check_symbolic_validity(
        expression: str | None,
        lhs: str | None,
        rhs: str | None,
    ) -> dict:
        """Check expression parses and simplifies correctly."""
        if not SYMPY_AVAILABLE:
            return {"score": 0.5, "note": "sympy unavailable"}

        try:
            transformations = standard_transformations + (implicit_multiplication_application,)

            if expression:
                expr = parse_expr(expression, transformations=transformations)
                simplified = sympy.simplify(expr)
                return {
                    "score": 1.0,
                    "applicable": True,
                    "parsed": str(expr),
                    "simplified": str(simplified),
                    "is_zero": simplified == 0,
                }

            if lhs and rhs:
                lhs_expr = parse_expr(lhs, transformations=transformations)
                rhs_expr = parse_expr(rhs, transformations=transformations)
                diff = sympy.simplify(lhs_expr - rhs_expr)
                is_equal = diff == 0

                return {
                    "score": 1.0 if is_equal else 0.7,
                    "applicable": True,
                    "lhs_parsed": str(lhs_expr),
                    "rhs_parsed": str(rhs_expr),
                    "difference": str(diff),
                    "symbolically_equal": is_equal,
                }

            return {"score": 0.5, "applicable": False, "note": "No expression to parse"}

        except Exception as e:
            return {"score": 0.0, "applicable": True, "error": f"Parse error: {str(e)}"}

    @staticmethod
    def _check_unit_consistency(units: dict) -> dict:
        """Verify units convert correctly between systems."""
        if not PINT_AVAILABLE:
            return {"score": 0.5, "note": "pint unavailable"}

        if not units:
            return {"score": 0.5, "applicable": False, "note": "No units"}

        conversions = units.get("conversions", [])
        if not conversions:
            # Just check all units are parseable
            parseable = 0
            for name, unit_str in units.items():
                if name == "conversions":
                    continue
                try:
                    _ureg.parse_expression(unit_str)
                    parseable += 1
                except Exception:
                    pass

            total = len([k for k in units if k != "conversions"])
            score = parseable / total if total > 0 else 0.5
            return {
                "score": round(score, 4),
                "applicable": True,
                "parseable": parseable,
                "total": total,
            }

        # Check explicit conversions
        correct = 0
        for conv in conversions:
            if not isinstance(conv, dict):
                continue
            from_val = conv.get("from_value")
            from_unit = conv.get("from_unit")
            to_val = conv.get("to_value")
            to_unit = conv.get("to_unit")

            if None in (from_val, from_unit, to_val, to_unit):
                continue

            try:
                quantity = _ureg.Quantity(float(from_val), from_unit)
                converted = quantity.to(to_unit).magnitude
                tolerance = max(abs(float(to_val)) * 0.01, 1e-10)
                if abs(converted - float(to_val)) <= tolerance:
                    correct += 1
            except Exception:
                pass

        score = correct / len(conversions) if conversions else 0.5
        return {
            "score": round(score, 4),
            "applicable": True,
            "correct_conversions": correct,
            "total_conversions": len(conversions),
        }

    @staticmethod
    def _check_expression_valid(expression: str) -> dict:
        """Check if expression is syntactically valid."""
        if not SYMPY_AVAILABLE:
            return {"score": 0.5, "note": "sympy unavailable"}

        try:
            transformations = standard_transformations + (implicit_multiplication_application,)
            expr = parse_expr(expression, transformations=transformations)
            return {
                "score": 1.0,
                "applicable": True,
                "parsed": str(expr),
                "free_symbols": [str(s) for s in expr.free_symbols],
            }
        except Exception as e:
            return {"score": 0.0, "applicable": True, "error": str(e)}
