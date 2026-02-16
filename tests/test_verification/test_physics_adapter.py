"""Tests for physics domain adapter."""
import pytest

from backend.verification.physics_adapter import PhysicsAdapter, PINT_AVAILABLE, SYMPY_AVAILABLE


@pytest.fixture
def adapter():
    return PhysicsAdapter()


class TestBasic:
    def test_domain(self, adapter):
        assert adapter.domain == "physics"


@pytest.mark.asyncio
class TestNumericalSimulation:
    async def test_unknown_claim_type(self, adapter):
        result = await adapter.verify({"claim_type": "unknown"}, {})
        assert result.passed is False

    async def test_no_data(self, adapter):
        result = await adapter.verify({
            "claim_type": "numerical_simulation",
        }, {})
        assert result.passed is False

    async def test_conservation_laws_pass(self, adapter):
        result = await adapter.verify({
            "claim_type": "numerical_simulation",
            "conservation_quantities": {
                "energy": {"initial": 100.0, "final": 100.0},
                "momentum": {"initial": 50.0, "final": 50.0},
            },
            "simulation_data": {},
        }, {})
        assert result.score > 0.0
        assert result.details["conservation"]["conserved"] == 2

    async def test_conservation_laws_violated(self, adapter):
        result = await adapter.verify({
            "claim_type": "numerical_simulation",
            "conservation_quantities": {
                "energy": {"initial": 100.0, "final": 50.0},
            },
            "simulation_data": {},
        }, {})
        assert result.details["conservation"]["conserved"] == 0


class TestConservation:
    def test_conserved(self):
        result = PhysicsAdapter._check_conservation(
            {"energy": {"initial": 100.0, "final": 100.0, "tolerance": 0.1}},
            {},
        )
        assert result["score"] == 1.0

    def test_violated(self):
        result = PhysicsAdapter._check_conservation(
            {"energy": {"initial": 100.0, "final": 50.0}},
            {},
        )
        assert result["score"] == 0.0

    def test_empty(self):
        result = PhysicsAdapter._check_conservation({}, {})
        assert result["applicable"] is False


class TestStability:
    def test_stable_series(self):
        result = PhysicsAdapter._check_stability({
            "time_series": {"temp": [100.0, 100.1, 99.9, 100.0, 100.2] * 10},
        })
        assert result["score"] == 1.0

    def test_nan_in_series(self):
        result = PhysicsAdapter._check_stability({
            "time_series": {"temp": [1.0, 2.0, float("nan"), 3.0]},
        })
        assert result["score"] < 1.0
        assert any("NaN" in issue for issue in result["issues"])

    def test_exponential_growth(self):
        # Create exponentially growing series
        values = [float(2 ** i) for i in range(40)]
        result = PhysicsAdapter._check_stability({
            "time_series": {"diverging": values},
        })
        assert result["score"] < 1.0

    def test_no_time_series(self):
        result = PhysicsAdapter._check_stability({})
        assert result["applicable"] is False


class TestConvergence:
    def test_monotonically_decreasing(self):
        result = PhysicsAdapter._check_convergence({
            "mesh_refinement": [
                {"resolution": 10, "error": 1.0},
                {"resolution": 20, "error": 0.5},
                {"resolution": 40, "error": 0.25},
            ],
        })
        assert result["score"] == 1.0
        assert result["monotonically_decreasing"] is True

    def test_non_monotonic(self):
        result = PhysicsAdapter._check_convergence({
            "mesh_refinement": [
                {"resolution": 10, "error": 1.0},
                {"resolution": 20, "error": 1.5},  # Error increased!
                {"resolution": 40, "error": 0.25},
            ],
        })
        assert result["score"] < 1.0

    def test_no_convergence_data(self):
        result = PhysicsAdapter._check_convergence({})
        assert result["applicable"] is False


class TestBoundaryConditions:
    def test_matching_boundaries(self):
        result = PhysicsAdapter._check_boundary_conditions({
            "boundary_conditions": {"left": 0.0, "right": 1.0},
            "boundary_results": {"left": 0.0, "right": 1.0},
        })
        assert result["score"] == 1.0

    def test_mismatched_boundaries(self):
        result = PhysicsAdapter._check_boundary_conditions({
            "boundary_conditions": {"left": 0.0, "right": 1.0},
            "boundary_results": {"left": 0.5, "right": 1.0},
        })
        assert result["score"] == 0.5

    def test_no_boundary_data(self):
        result = PhysicsAdapter._check_boundary_conditions({})
        assert result["applicable"] is False


@pytest.mark.asyncio
class TestAnalyticalDerivation:
    async def test_no_expression(self, adapter):
        result = await adapter.verify({
            "claim_type": "analytical_derivation",
        }, {})
        assert result.passed is False

    @pytest.mark.skipif(not SYMPY_AVAILABLE, reason="sympy not installed")
    async def test_valid_expression(self, adapter):
        result = await adapter.verify({
            "claim_type": "analytical_derivation",
            "expression": "x**2 + 2*x + 1",
            "units": {},
        }, {})
        assert result.score > 0.0

    @pytest.mark.skipif(not SYMPY_AVAILABLE, reason="sympy not installed")
    async def test_lhs_rhs_equal(self, adapter):
        result = await adapter.verify({
            "claim_type": "analytical_derivation",
            "lhs": "(x+1)**2",
            "rhs": "x**2 + 2*x + 1",
            "units": {},
        }, {})
        assert result.score > 0.0
        sym_detail = result.details.get("symbolic_validity", {})
        assert sym_detail.get("symbolically_equal") is True


class TestDimensionalConsistency:
    @pytest.mark.skipif(not PINT_AVAILABLE, reason="pint not installed")
    def test_compatible_units(self):
        result = PhysicsAdapter._check_dimensional_consistency(
            "F = m * a",
            {"lhs": "newton", "rhs": "kilogram * meter / second**2"},
        )
        assert result["score"] == 1.0
        assert result["compatible"] is True

    @pytest.mark.skipif(not PINT_AVAILABLE, reason="pint not installed")
    def test_incompatible_units(self):
        result = PhysicsAdapter._check_dimensional_consistency(
            "F = m * a",
            {"lhs": "meter", "rhs": "kilogram"},
        )
        assert result["score"] == 0.0
        assert result["compatible"] is False

    def test_no_units(self):
        result = PhysicsAdapter._check_dimensional_consistency("F = m*a", {})
        assert result["applicable"] is False


class TestSymbolicValidity:
    @pytest.mark.skipif(not SYMPY_AVAILABLE, reason="sympy not installed")
    def test_valid_expression(self):
        result = PhysicsAdapter._check_symbolic_validity("x**2 + 1", None, None)
        assert result["score"] == 1.0

    @pytest.mark.skipif(not SYMPY_AVAILABLE, reason="sympy not installed")
    def test_invalid_expression(self):
        result = PhysicsAdapter._check_symbolic_validity("x +++ y", None, None)
        assert result["score"] == 0.0

    @pytest.mark.skipif(not SYMPY_AVAILABLE, reason="sympy not installed")
    def test_equal_lhs_rhs(self):
        result = PhysicsAdapter._check_symbolic_validity(None, "x**2 + 2*x + 1", "(x+1)**2")
        assert result["symbolically_equal"] is True

    def test_no_expression(self):
        if SYMPY_AVAILABLE:
            result = PhysicsAdapter._check_symbolic_validity(None, None, None)
            assert result["applicable"] is False


class TestUnitConsistency:
    @pytest.mark.skipif(not PINT_AVAILABLE, reason="pint not installed")
    def test_parseable_units(self):
        result = PhysicsAdapter._check_unit_consistency({
            "force": "newton",
            "mass": "kilogram",
            "acceleration": "meter / second**2",
        })
        assert result["score"] == 1.0

    @pytest.mark.skipif(not PINT_AVAILABLE, reason="pint not installed")
    def test_conversion_check(self):
        result = PhysicsAdapter._check_unit_consistency({
            "conversions": [
                {"from_value": 1.0, "from_unit": "meter", "to_value": 100.0, "to_unit": "centimeter"},
            ],
        })
        assert result["score"] == 1.0

    @pytest.mark.skipif(not PINT_AVAILABLE, reason="pint not installed")
    def test_wrong_conversion(self):
        result = PhysicsAdapter._check_unit_consistency({
            "conversions": [
                {"from_value": 1.0, "from_unit": "meter", "to_value": 50.0, "to_unit": "centimeter"},
            ],
        })
        assert result["score"] == 0.0


@pytest.mark.asyncio
class TestDimensionalAnalysis:
    async def test_no_expression(self, adapter):
        result = await adapter.verify({
            "claim_type": "dimensional_analysis",
        }, {})
        assert result.passed is False

    @pytest.mark.skipif(not SYMPY_AVAILABLE, reason="sympy not installed")
    async def test_with_expression(self, adapter):
        result = await adapter.verify({
            "claim_type": "dimensional_analysis",
            "expression": "x**2 + y",
            "units": {},
        }, {})
        assert result.score > 0.0
