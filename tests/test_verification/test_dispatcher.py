"""Tests for verification dispatcher."""
import pytest

from backend.verification.base import (
    VerificationAdapter,
    VerificationBadge,
    VerificationResult,
)
from backend.verification.dispatcher import (
    _ADAPTERS,
    dispatch_verification,
    get_adapter,
    register_adapter,
)


class MockAdapter(VerificationAdapter):
    domain = "test_domain"

    def __init__(self, result: VerificationResult | None = None):
        self._result = result or VerificationResult(
            passed=True, score=1.0,
            badge=VerificationBadge.GREEN,
            domain="test_domain",
        )

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        return self._result


class FailingAdapter(VerificationAdapter):
    domain = "failing_domain"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        raise RuntimeError("Adapter exploded")


class TestRegistry:
    def test_register_and_get(self):
        adapter = MockAdapter()
        register_adapter(adapter)
        assert get_adapter("test_domain") is adapter
        # Cleanup
        _ADAPTERS.pop("test_domain", None)

    def test_get_unknown_domain(self):
        assert get_adapter("nonexistent_domain_xyz") is None

    def test_builtin_adapters_registered(self):
        """All 5 domain adapters should be registered at import time."""
        assert get_adapter("mathematics") is not None
        assert get_adapter("ml_ai") is not None
        assert get_adapter("computational_biology") is not None
        assert get_adapter("materials_science") is not None
        assert get_adapter("bioinformatics") is not None


@pytest.mark.asyncio
class TestDispatchVerification:
    async def test_dispatch_to_mock(self):
        expected = VerificationResult(
            passed=True, score=0.9,
            badge=VerificationBadge.GREEN,
            domain="test_domain",
        )
        adapter = MockAdapter(expected)
        register_adapter(adapter)

        result = await dispatch_verification("test_domain", {"key": "val"}, {"domain": "test_domain"})
        assert result.passed is True
        assert result.score == 0.9
        assert result.badge == VerificationBadge.GREEN

        _ADAPTERS.pop("test_domain", None)

    async def test_dispatch_unknown_domain(self):
        result = await dispatch_verification("unknown_domain_xyz", {}, {})
        assert result.passed is False
        assert result.score == 0.0
        assert result.badge == VerificationBadge.RED
        assert "No verification adapter" in result.errors[0]

    async def test_dispatch_adapter_exception(self):
        adapter = FailingAdapter()
        register_adapter(adapter)

        result = await dispatch_verification("failing_domain", {}, {})
        assert result.passed is False
        assert result.score == 0.0
        assert "Verification error" in result.errors[0]
        assert "exploded" in result.errors[0]

        _ADAPTERS.pop("failing_domain", None)
