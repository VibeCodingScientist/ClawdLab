"""Tests for cross-cutting runner: registration, filtering, merge math, exception handling."""
import pytest

from backend.verification.base import VerificationBadge, VerificationResult
from backend.verification.cross_cutting_base import (
    CrossCuttingResult,
    CrossCuttingVerifier,
)
from backend.verification.cross_cutting_runner import (
    _CC_VERIFIERS,
    merge_results,
    run_cross_cutting,
    register_cross_cutting,
    get_cross_cutting_verifiers,
)


class AlwaysApplicableVerifier(CrossCuttingVerifier):
    name = "always"
    default_weight = 0.10

    def is_applicable(self, task_result, task_metadata):
        return True

    async def verify(self, task_result, task_metadata):
        return CrossCuttingResult(
            verifier_name=self.name,
            score=0.8,
            weight=self.default_weight,
            details={"check": "passed"},
        )


class NeverApplicableVerifier(CrossCuttingVerifier):
    name = "never"
    default_weight = 0.10

    def is_applicable(self, task_result, task_metadata):
        return False

    async def verify(self, task_result, task_metadata):
        return CrossCuttingResult(verifier_name=self.name, score=1.0, weight=self.default_weight)


class CrashingVerifier(CrossCuttingVerifier):
    name = "crasher"
    default_weight = 0.10

    def is_applicable(self, task_result, task_metadata):
        return True

    async def verify(self, task_result, task_metadata):
        raise RuntimeError("Verifier exploded")


class CrashingApplicabilityVerifier(CrossCuttingVerifier):
    name = "bad_applicability"
    default_weight = 0.10

    def is_applicable(self, task_result, task_metadata):
        raise ValueError("Oops")

    async def verify(self, task_result, task_metadata):
        return CrossCuttingResult(verifier_name=self.name, score=1.0, weight=self.default_weight)


class TestRegistration:
    def test_builtin_verifiers_registered(self):
        """All 4 cross-cutting verifiers should be registered at import time."""
        names = {v.name for v in _CC_VERIFIERS}
        assert "citation_reference" in names
        assert "statistical_forensics" in names
        assert "reproducibility" in names
        assert "data_integrity" in names

    def test_get_cross_cutting_verifiers_returns_copy(self):
        verifiers = get_cross_cutting_verifiers()
        assert len(verifiers) >= 4
        # Modifying the returned list shouldn't affect the registry
        original_len = len(_CC_VERIFIERS)
        verifiers.append(AlwaysApplicableVerifier())
        assert len(_CC_VERIFIERS) == original_len


class TestMergeResults:
    def test_basic_merge(self):
        domain = VerificationResult(
            passed=True, score=0.8,
            badge=VerificationBadge.GREEN,
            domain="test",
            details={"domain_detail": True},
            compute_time_seconds=1.0,
        )
        cc = [
            CrossCuttingResult(
                verifier_name="v1", score=0.6, weight=0.15,
                details={"v1": True}, compute_time_seconds=0.5,
            ),
        ]
        merged = merge_results(domain, cc)

        # 0.70 * 0.8 + 0.30 * 0.6 = 0.56 + 0.18 = 0.74
        assert merged.score == 0.74
        assert merged.passed is True
        assert "cross_cutting" in merged.details
        assert "scoring" in merged.details
        assert merged.details["scoring"]["domain_score"] == 0.8
        assert merged.compute_time_seconds == 1.5

    def test_merge_with_multiple_cc(self):
        domain = VerificationResult(
            passed=True, score=0.8,
            badge=VerificationBadge.GREEN,
            domain="test",
        )
        cc = [
            CrossCuttingResult(verifier_name="v1", score=0.6, weight=0.15),
            CrossCuttingResult(verifier_name="v2", score=1.0, weight=0.10),
        ]
        merged = merge_results(domain, cc)

        # CC scores weighted: (0.15/0.25 * 0.6 + 0.10/0.25 * 1.0) = 0.36 + 0.4 = 0.76
        # Final: 0.70 * 0.8 + 0.30 * 0.76 = 0.56 + 0.228 = 0.788
        assert abs(merged.score - 0.788) < 0.001

    def test_merge_empty_cc_returns_domain(self):
        domain = VerificationResult(
            passed=True, score=0.9,
            badge=VerificationBadge.GREEN,
            domain="test",
        )
        merged = merge_results(domain, [])
        assert merged.score == 0.9

    def test_merge_preserves_errors_warnings(self):
        domain = VerificationResult(
            passed=True, score=0.8,
            badge=VerificationBadge.GREEN,
            domain="test",
            warnings=["domain warning"],
            errors=["domain error"],
        )
        cc = [
            CrossCuttingResult(
                verifier_name="v1", score=0.5, weight=0.1,
                warnings=["cc warning"],
                errors=["cc error"],
            ),
        ]
        merged = merge_results(domain, cc)
        assert "domain warning" in merged.warnings
        assert "cc warning" in merged.warnings
        assert "domain error" in merged.errors
        assert "cc error" in merged.errors

    def test_merge_badge_recalculated(self):
        # Domain passes green (0.9) but CC drags it down
        domain = VerificationResult(
            passed=True, score=0.9,
            badge=VerificationBadge.GREEN,
            domain="test",
        )
        cc = [
            CrossCuttingResult(verifier_name="v1", score=0.0, weight=0.10),
        ]
        merged = merge_results(domain, cc)
        # 0.70 * 0.9 + 0.30 * 0.0 = 0.63
        assert merged.score == 0.63
        assert merged.badge == VerificationBadge.AMBER

    def test_custom_domain_weight(self):
        domain = VerificationResult(
            passed=True, score=1.0,
            badge=VerificationBadge.GREEN,
            domain="test",
        )
        cc = [
            CrossCuttingResult(verifier_name="v1", score=0.0, weight=0.10),
        ]
        merged = merge_results(domain, cc, domain_weight=0.90)
        # 0.90 * 1.0 + 0.10 * 0.0 = 0.90
        assert merged.score == 0.9


@pytest.mark.asyncio
class TestRunCrossCutting:
    async def test_no_applicable_returns_empty(self):
        # With actual verifiers but task_result has no relevant keys
        results = await run_cross_cutting({}, {})
        assert results == []

    async def test_crashing_verifier_returns_zero_score(self):
        # Temporarily add a crashing verifier
        crasher = CrashingVerifier()
        _CC_VERIFIERS.append(crasher)
        try:
            results = await run_cross_cutting({"data": [1]}, {})
            # The crasher should produce score 0.0
            crasher_results = [r for r in results if r.verifier_name == "crasher"]
            if crasher_results:
                assert crasher_results[0].score == 0.0
                assert len(crasher_results[0].errors) > 0
        finally:
            _CC_VERIFIERS.remove(crasher)

    async def test_crashing_applicability_is_filtered(self):
        bad = CrashingApplicabilityVerifier()
        _CC_VERIFIERS.append(bad)
        try:
            # Should not crash, just skip the bad verifier
            results = await run_cross_cutting({"data": [1]}, {})
            assert all(r.verifier_name != "bad_applicability" for r in results)
        finally:
            _CC_VERIFIERS.remove(bad)
