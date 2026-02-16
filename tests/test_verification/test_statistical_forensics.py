"""Tests for statistical forensics verifier."""
import pytest

from backend.verification.statistical_forensics import (
    StatisticalForensicsVerifier,
    _sprite_check,
    _chi2_survival,
)


@pytest.fixture
def verifier():
    return StatisticalForensicsVerifier()


class TestApplicability:
    def test_applicable_with_statistical_claims(self, verifier):
        assert verifier.is_applicable({"statistical_claims": [{"p_value": 0.03}]}, {}) is True

    def test_applicable_with_means(self, verifier):
        assert verifier.is_applicable({"means": [{"mean": 3.5, "n": 20}]}, {}) is True

    def test_applicable_with_p_values(self, verifier):
        assert verifier.is_applicable({"p_values": [0.01, 0.04]}, {}) is True

    def test_applicable_with_metrics(self, verifier):
        assert verifier.is_applicable({"metrics": {"accuracy": 0.95}}, {}) is True

    def test_not_applicable_empty(self, verifier):
        assert verifier.is_applicable({}, {}) is False

    def test_not_applicable_empty_values(self, verifier):
        assert verifier.is_applicable({"means": [], "p_values": []}, {}) is False


class TestGRIM:
    def test_consistent_mean(self, verifier):
        # Mean of 3.5 with n=10: 10*3.5 = 35.0 (integer) -> consistent
        result = verifier._run_grim([{"mean": 3.5, "n": 10}])
        assert result["score"] == 1.0
        assert result["passed"] == 1

    def test_inconsistent_mean(self, verifier):
        # Mean of 3.47 with n=3: 3*3.47 = 10.41 (not integer) -> inconsistent
        result = verifier._run_grim([{"mean": 3.47, "n": 3}])
        # Tolerance is n * 0.005 + 0.01 = 0.025. Remainder 0.41 > 0.025
        assert result["failed"] >= 1

    def test_no_data(self, verifier):
        result = verifier._run_grim([])
        assert result["applicable"] is False

    def test_missing_n(self, verifier):
        result = verifier._run_grim([{"mean": 3.5}])
        assert result["applicable"] is False


class TestSPRITE:
    def test_achievable_combination(self):
        # Mean=4.0, SD=1.5 on 1-7 scale, n=20: should be achievable
        assert _sprite_check(4.0, 1.5, 20, 1, 7) is True

    def test_impossible_combination(self):
        # Mean=1.0, SD=3.0 on 1-7 scale, n=5: impossible (all must be 1 for mean=1, SD=0)
        result = _sprite_check(1.0, 3.0, 5, 1, 7)
        assert result is False

    def test_edge_case_n_zero(self):
        assert _sprite_check(3.0, 1.0, 0, 1, 7) is False


class TestBenford:
    def test_benford_conforming_data(self, verifier):
        # Generate Benford-conforming first digits
        import math
        numbers = []
        for d in range(1, 10):
            count = int(100 * math.log10(1 + 1 / d))
            numbers.extend([d * 10 + i for i in range(count)])

        result = verifier._run_benford(numbers)
        assert result["applicable"] is True
        # Should score well since data conforms to Benford
        assert result["score"] >= 0.4

    def test_insufficient_data(self, verifier):
        result = verifier._run_benford([1, 2, 3])
        assert result["applicable"] is False

    def test_uniform_first_digits(self, verifier):
        # Uniform first digits should violate Benford's law
        numbers = [d * 100 for d in range(1, 10)] * 20
        result = verifier._run_benford(numbers)
        assert result["applicable"] is True
        # Uniform distribution should get lower score
        assert result["chi2"] > 0


class TestPCurve:
    def test_right_skewed_passes(self, verifier):
        # Real effect: more p-values near 0 than near 0.05
        p_values = [0.001, 0.002, 0.005, 0.008, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04]
        result = verifier._run_pcurve(p_values)
        assert result["applicable"] is True
        assert result["score"] >= 0.7

    def test_uniform_suspicious(self, verifier):
        # Uniform p-values suggest p-hacking
        p_values = [0.005 * i for i in range(1, 11)]
        result = verifier._run_pcurve(p_values)
        assert result["applicable"] is True

    def test_insufficient_p_values(self, verifier):
        result = verifier._run_pcurve([0.01, 0.02])
        assert result["applicable"] is False


class TestChi2Survival:
    def test_zero_returns_one(self):
        assert _chi2_survival(0.0, 8) == 1.0

    def test_large_value_returns_low(self):
        assert _chi2_survival(100.0, 8) < 0.01

    def test_critical_value(self):
        # Chi2 = 15.507 with df=8 should give p ~ 0.05
        p = _chi2_survival(15.507, 8)
        assert 0.01 < p < 0.15


@pytest.mark.asyncio
class TestVerify:
    async def test_no_applicable_data(self, verifier):
        result = await verifier.verify({"unrelated": "data"}, {})
        # All tests return neutral 0.5
        assert abs(result.score - 0.5) < 0.1

    async def test_with_means_and_p_values(self, verifier):
        task_result = {
            "means": [{"mean": 3.5, "n": 10, "sd": 1.2}],
            "p_values": [0.001, 0.005, 0.01, 0.02, 0.03],
            "metrics": {"acc1": 95.3, "acc2": 87.1, "loss": 0.23, "f1": 0.89,
                        "prec": 0.91, "recall": 0.87, "mcc": 0.72, "auc": 0.94,
                        "r2": 0.88, "rmse": 1.23, "mae": 0.95},
        }
        result = await verifier.verify(task_result, {})
        assert result.verifier_name == "statistical_forensics"
        assert 0.0 <= result.score <= 1.0
        assert "grim" in result.details
        assert "sprite" in result.details
        assert "benford" in result.details
        assert "pcurve" in result.details
