"""Tests for verification base classes."""
import pytest

from backend.verification.base import VerificationBadge, VerificationResult


class TestVerificationBadge:
    def test_badge_values(self):
        assert VerificationBadge.GREEN.value == "green"
        assert VerificationBadge.AMBER.value == "amber"
        assert VerificationBadge.RED.value == "red"

    def test_badge_is_str_enum(self):
        assert isinstance(VerificationBadge.GREEN, str)
        assert VerificationBadge.GREEN == "green"


class TestVerificationResult:
    def test_creation(self):
        result = VerificationResult(
            passed=True,
            score=0.95,
            badge=VerificationBadge.GREEN,
            domain="mathematics",
        )
        assert result.passed is True
        assert result.score == 0.95
        assert result.badge == VerificationBadge.GREEN
        assert result.domain == "mathematics"
        assert result.details == {}
        assert result.errors == []
        assert result.warnings == []
        assert result.compute_time_seconds == 0.0

    def test_creation_with_details(self):
        result = VerificationResult(
            passed=False,
            score=0.3,
            badge=VerificationBadge.RED,
            domain="ml_ai",
            details={"model": "test"},
            errors=["Some error"],
            warnings=["Some warning"],
            compute_time_seconds=12.5,
        )
        assert result.details == {"model": "test"}
        assert result.errors == ["Some error"]
        assert result.warnings == ["Some warning"]
        assert result.compute_time_seconds == 12.5

    def test_score_to_badge_green(self):
        assert VerificationResult.score_to_badge(1.0) == VerificationBadge.GREEN
        assert VerificationResult.score_to_badge(0.8) == VerificationBadge.GREEN
        assert VerificationResult.score_to_badge(0.95) == VerificationBadge.GREEN

    def test_score_to_badge_amber(self):
        assert VerificationResult.score_to_badge(0.79) == VerificationBadge.AMBER
        assert VerificationResult.score_to_badge(0.5) == VerificationBadge.AMBER
        assert VerificationResult.score_to_badge(0.6) == VerificationBadge.AMBER

    def test_score_to_badge_red(self):
        assert VerificationResult.score_to_badge(0.49) == VerificationBadge.RED
        assert VerificationResult.score_to_badge(0.0) == VerificationBadge.RED
        assert VerificationResult.score_to_badge(0.1) == VerificationBadge.RED

    def test_fail_factory(self):
        result = VerificationResult.fail("mathematics", ["Proof failed to compile"])
        assert result.passed is False
        assert result.score == 0.0
        assert result.badge == VerificationBadge.RED
        assert result.domain == "mathematics"
        assert result.errors == ["Proof failed to compile"]

    def test_fail_multiple_errors(self):
        errors = ["Error 1", "Error 2", "Error 3"]
        result = VerificationResult.fail("ml_ai", errors)
        assert len(result.errors) == 3
        assert result.errors == errors
