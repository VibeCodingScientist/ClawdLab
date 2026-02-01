"""Tests for BadgeCalculator."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestBadgeCalculator:
    """Tests for BadgeCalculator.calculate_badge."""

    def _calculator(self):
        from platform.services.verification_orchestrator.badges import BadgeCalculator
        return BadgeCalculator()

    def test_green_badge_verified_robust_consistent(self):
        """GREEN badge when verified + robust (>=0.8) + consistent."""
        from platform.services.verification_orchestrator.badges import (
            VerificationBadge,
        )

        calc = self._calculator()
        result = calc.calculate_badge(
            verification_passed=True,
            stability_score=0.9,
            consistent=True,
            contradictions=[],
        )

        assert result.badge == VerificationBadge.GREEN

    def test_amber_badge_verified_but_fragile(self):
        """AMBER badge when verified but stability < 0.8."""
        from platform.services.verification_orchestrator.badges import (
            VerificationBadge,
        )

        calc = self._calculator()
        result = calc.calculate_badge(
            verification_passed=True,
            stability_score=0.5,
            consistent=True,
            contradictions=[],
        )

        assert result.badge == VerificationBadge.AMBER

    def test_amber_badge_verified_but_inconsistent(self):
        """AMBER badge when verified and robust but inconsistent."""
        from platform.services.verification_orchestrator.badges import (
            VerificationBadge,
        )

        calc = self._calculator()
        result = calc.calculate_badge(
            verification_passed=True,
            stability_score=0.85,
            consistent=False,
            contradictions=[{"claim_id": str(uuid4()), "severity": "high"}],
        )

        assert result.badge == VerificationBadge.AMBER

    def test_amber_badge_verified_fragile_and_inconsistent(self):
        """AMBER badge when verified but both fragile AND inconsistent."""
        from platform.services.verification_orchestrator.badges import (
            VerificationBadge,
        )

        calc = self._calculator()
        result = calc.calculate_badge(
            verification_passed=True,
            stability_score=0.6,
            consistent=False,
            contradictions=[{"claim_id": str(uuid4())}],
        )

        assert result.badge == VerificationBadge.AMBER

    def test_red_badge_verification_failed(self):
        """RED badge when domain verification failed."""
        from platform.services.verification_orchestrator.badges import (
            VerificationBadge,
        )

        calc = self._calculator()
        result = calc.calculate_badge(
            verification_passed=False,
            stability_score=0.9,
            consistent=True,
        )

        assert result.badge == VerificationBadge.RED

    def test_red_badge_very_fragile(self):
        """RED badge when stability is below 0.3 (very fragile)."""
        from platform.services.verification_orchestrator.badges import (
            VerificationBadge,
        )

        calc = self._calculator()
        result = calc.calculate_badge(
            verification_passed=True,
            stability_score=0.2,
            consistent=True,
        )

        assert result.badge == VerificationBadge.RED

    def test_boundary_at_exactly_0_8_stability(self):
        """At exactly 0.8 stability the claim should be GREEN (>= threshold)."""
        from platform.services.verification_orchestrator.badges import (
            VerificationBadge,
        )

        calc = self._calculator()
        result = calc.calculate_badge(
            verification_passed=True,
            stability_score=0.8,
            consistent=True,
        )

        assert result.badge == VerificationBadge.GREEN

    def test_boundary_at_exactly_0_3_stability(self):
        """At exactly 0.3 stability the claim should be AMBER, not RED
        (RED requires *below* 0.3)."""
        from platform.services.verification_orchestrator.badges import (
            VerificationBadge,
        )

        calc = self._calculator()
        result = calc.calculate_badge(
            verification_passed=True,
            stability_score=0.3,
            consistent=True,
        )

        # 0.3 is not < 0.3, so not RED; but 0.3 < 0.8, so AMBER
        assert result.badge == VerificationBadge.AMBER

    def test_details_dict_contains_reason(self):
        """BadgeResult details should contain a reason string."""
        calc = self._calculator()
        result = calc.calculate_badge(
            verification_passed=True,
            stability_score=0.9,
            consistent=True,
        )

        assert "reason" in result.details
        assert isinstance(result.details["reason"], str)

    def test_details_dict_contains_thresholds(self):
        """BadgeResult details should contain the thresholds used."""
        calc = self._calculator()
        result = calc.calculate_badge(
            verification_passed=True,
            stability_score=0.9,
            consistent=True,
        )

        assert "thresholds" in result.details
        thresholds = result.details["thresholds"]
        assert "stability_high" in thresholds
        assert "stability_very_low" in thresholds
        assert "consistency_high" in thresholds
        assert thresholds["stability_high"] == 0.8
        assert thresholds["stability_very_low"] == 0.3
        assert thresholds["consistency_high"] == 0.7
