"""Tests for cross-cutting verifier base classes."""
import pytest

from backend.verification.cross_cutting_base import (
    CrossCuttingResult,
    CrossCuttingVerifier,
)


class TestCrossCuttingResult:
    def test_defaults(self):
        r = CrossCuttingResult(
            verifier_name="test",
            score=0.8,
            weight=0.10,
        )
        assert r.verifier_name == "test"
        assert r.score == 0.8
        assert r.weight == 0.10
        assert r.details == {}
        assert r.errors == []
        assert r.warnings == []
        assert r.compute_time_seconds == 0.0

    def test_with_details(self):
        r = CrossCuttingResult(
            verifier_name="citation",
            score=0.6,
            weight=0.15,
            details={"checked": 5},
            errors=["DOI failed"],
            warnings=["Old reference"],
            compute_time_seconds=1.5,
        )
        assert r.details == {"checked": 5}
        assert len(r.errors) == 1
        assert len(r.warnings) == 1
        assert r.compute_time_seconds == 1.5

    def test_score_bounds(self):
        r = CrossCuttingResult(verifier_name="t", score=0.0, weight=0.1)
        assert r.score == 0.0

        r2 = CrossCuttingResult(verifier_name="t", score=1.0, weight=0.1)
        assert r2.score == 1.0


class TestCrossCuttingVerifier:
    def test_default_attributes(self):
        v = CrossCuttingVerifier()
        assert v.name == ""
        assert v.default_weight == 0.10
        assert v.requires_docker is False

    def test_is_applicable_not_implemented(self):
        v = CrossCuttingVerifier()
        with pytest.raises(NotImplementedError):
            v.is_applicable({}, {})

    def test_verify_not_implemented(self):
        v = CrossCuttingVerifier()
        with pytest.raises(NotImplementedError):
            # Can't await in sync context, just test it raises
            import asyncio
            asyncio.get_event_loop().run_until_complete(v.verify({}, {}))

    def test_subclass(self):
        class MyVerifier(CrossCuttingVerifier):
            name = "my_verifier"
            default_weight = 0.20
            requires_docker = True

            def is_applicable(self, task_result, task_metadata):
                return "data" in task_result

            async def verify(self, task_result, task_metadata):
                return CrossCuttingResult(
                    verifier_name=self.name,
                    score=1.0,
                    weight=self.default_weight,
                )

        v = MyVerifier()
        assert v.name == "my_verifier"
        assert v.default_weight == 0.20
        assert v.requires_docker is True
        assert v.is_applicable({"data": [1]}, {}) is True
        assert v.is_applicable({"other": 1}, {}) is False
