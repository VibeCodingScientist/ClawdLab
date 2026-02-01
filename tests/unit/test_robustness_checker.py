"""Tests for RobustnessChecker."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestRobustnessChecker:
    """Tests for RobustnessChecker.check_robustness."""

    @pytest.mark.asyncio
    async def test_returns_robustness_result_dataclass(self):
        """check_robustness should return a RobustnessResult instance."""
        from platform.services.verification_orchestrator.robustness import (
            RobustnessChecker,
            RobustnessResult,
        )

        checker = RobustnessChecker()
        result = await checker.check_robustness(
            claim_id=str(uuid4()),
            domain="mathematics",
            original_result={"verified": True},
            payload={"constants": {"a": 1.0, "b": 2.0}},
            perturbation_count=3,
        )

        assert isinstance(result, RobustnessResult)

    @pytest.mark.asyncio
    async def test_stability_score_between_zero_and_one(self):
        """Stability score must be in the range [0, 1]."""
        from platform.services.verification_orchestrator.robustness import (
            RobustnessChecker,
        )

        checker = RobustnessChecker()
        result = await checker.check_robustness(
            claim_id=str(uuid4()),
            domain="ml_ai",
            original_result={"accuracy": 0.9},
            payload={
                "random_seed": 42,
                "hyperparameters": {"lr": 0.001, "batch_size": 32},
            },
            perturbation_count=5,
        )

        assert 0.0 <= result.stability_score <= 1.0

    @pytest.mark.asyncio
    async def test_perturbations_run_count(self):
        """perturbations_run should equal the requested count."""
        from platform.services.verification_orchestrator.robustness import (
            RobustnessChecker,
        )

        checker = RobustnessChecker()
        count = 4
        result = await checker.check_robustness(
            claim_id=str(uuid4()),
            domain="mathematics",
            original_result={"verified": True},
            payload={"constants": {"x": 10}},
            perturbation_count=count,
        )

        assert result.perturbations_run == count

    @pytest.mark.asyncio
    async def test_math_domain_perturbations(self):
        """Mathematics domain should use constant_shift perturbations."""
        from platform.services.verification_orchestrator.robustness import (
            RobustnessChecker,
        )

        checker = RobustnessChecker()
        result = await checker.check_robustness(
            claim_id=str(uuid4()),
            domain="mathematics",
            original_result={"proved": True},
            payload={"constants": {"pi_approx": 3.14159}},
            perturbation_count=3,
        )

        # All perturbations should use the constant_shift strategy
        perturbation_details = result.details.get("perturbations", [])
        assert len(perturbation_details) == 3
        for p in perturbation_details:
            assert p["strategy"] == "constant_shift"

    @pytest.mark.asyncio
    async def test_ml_ai_domain_perturbations(self):
        """ML/AI domain should use seed_and_hyperparam perturbations."""
        from platform.services.verification_orchestrator.robustness import (
            RobustnessChecker,
        )

        checker = RobustnessChecker()
        result = await checker.check_robustness(
            claim_id=str(uuid4()),
            domain="ml_ai",
            original_result={"accuracy": 0.95},
            payload={
                "random_seed": 42,
                "hyperparameters": {"lr": 0.001},
            },
            perturbation_count=5,
        )

        perturbation_details = result.details.get("perturbations", [])
        assert len(perturbation_details) == 5
        for p in perturbation_details:
            assert p["strategy"] == "seed_and_hyperparam"

    @pytest.mark.asyncio
    async def test_unknown_domain_returns_stable(self):
        """An unknown domain with no generator should return stability=1.0."""
        from platform.services.verification_orchestrator.robustness import (
            RobustnessChecker,
        )

        checker = RobustnessChecker()
        result = await checker.check_robustness(
            claim_id=str(uuid4()),
            domain="quantum_physics",
            original_result={"valid": True},
            payload={},
        )

        assert result.stability_score == 1.0
        assert result.perturbations_run == 0

    @pytest.mark.asyncio
    async def test_perturbations_passed_lte_perturbations_run(self):
        """perturbations_passed should not exceed perturbations_run."""
        from platform.services.verification_orchestrator.robustness import (
            RobustnessChecker,
        )

        checker = RobustnessChecker()
        result = await checker.check_robustness(
            claim_id=str(uuid4()),
            domain="computational_biology",
            original_result={"aligned": True},
            payload={
                "gap_open_penalty": -10,
                "gap_extend_penalty": -1,
            },
            perturbation_count=5,
        )

        assert result.perturbations_passed <= result.perturbations_run
