"""Tests for VerificationPlanner."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestVerificationPlannerCreatePlan:
    """Tests for VerificationPlanner.create_plan."""

    @pytest.mark.asyncio
    async def test_plan_includes_domain_verification_step(self):
        """Plan should always include a domain verification step."""
        from platform.services.verification_orchestrator.planner import (
            VerificationPlanner,
        )

        planner = VerificationPlanner()
        plan = planner.create_plan(
            claim_id=str(uuid4()),
            domain="mathematics",
            claim_type="empirical",
            payload={"results": [1, 2, 3]},
        )

        domain_steps = [s for s in plan.steps if s.verifier_type == "domain"]
        assert len(domain_steps) == 1
        assert domain_steps[0].name == "mathematics_domain_verification"

    @pytest.mark.asyncio
    async def test_plan_includes_robustness_step(self):
        """Plan should include a robustness step for empirical claim types."""
        from platform.services.verification_orchestrator.planner import (
            VerificationPlanner,
        )

        planner = VerificationPlanner()
        plan = planner.create_plan(
            claim_id=str(uuid4()),
            domain="ml_ai",
            claim_type="empirical",
            payload={"metrics": {"accuracy": 0.95}},
        )

        robustness_steps = [s for s in plan.steps if s.verifier_type == "robustness"]
        assert len(robustness_steps) == 1
        assert robustness_steps[0].name == "ml_ai_robustness_check"

    @pytest.mark.asyncio
    async def test_plan_includes_consistency_step(self):
        """Plan should include a consistency step for empirical claim types."""
        from platform.services.verification_orchestrator.planner import (
            VerificationPlanner,
        )

        planner = VerificationPlanner()
        plan = planner.create_plan(
            claim_id=str(uuid4()),
            domain="ml_ai",
            claim_type="empirical",
            payload={"metrics": {"accuracy": 0.95}},
        )

        consistency_steps = [s for s in plan.steps if s.verifier_type == "consistency"]
        assert len(consistency_steps) == 1
        assert consistency_steps[0].name == "ml_ai_consistency_check"

    @pytest.mark.asyncio
    async def test_robustness_step_depends_on_domain_step(self):
        """Robustness step should depend on the domain verification step."""
        from platform.services.verification_orchestrator.planner import (
            VerificationPlanner,
        )

        planner = VerificationPlanner()
        plan = planner.create_plan(
            claim_id=str(uuid4()),
            domain="ml_ai",
            claim_type="empirical",
            payload={"metrics": {"accuracy": 0.95}},
        )

        domain_step = next(s for s in plan.steps if s.verifier_type == "domain")
        robustness_step = next(s for s in plan.steps if s.verifier_type == "robustness")

        assert domain_step.step_id in robustness_step.depends_on

    @pytest.mark.asyncio
    async def test_consistency_step_depends_on_domain_and_robustness(self):
        """Consistency step should depend on domain step, and also on
        robustness step when the latter is present."""
        from platform.services.verification_orchestrator.planner import (
            VerificationPlanner,
        )

        planner = VerificationPlanner()
        plan = planner.create_plan(
            claim_id=str(uuid4()),
            domain="ml_ai",
            claim_type="empirical",
            payload={"metrics": {"accuracy": 0.95}},
        )

        domain_step = next(s for s in plan.steps if s.verifier_type == "domain")
        robustness_step = next(s for s in plan.steps if s.verifier_type == "robustness")
        consistency_step = next(s for s in plan.steps if s.verifier_type == "consistency")

        assert domain_step.step_id in consistency_step.depends_on
        assert robustness_step.step_id in consistency_step.depends_on

    @pytest.mark.asyncio
    async def test_plan_has_correct_claim_id(self):
        """Plan should record the claim_id it was created for."""
        from platform.services.verification_orchestrator.planner import (
            VerificationPlanner,
        )

        planner = VerificationPlanner()
        claim_id = str(uuid4())
        plan = planner.create_plan(
            claim_id=claim_id,
            domain="mathematics",
            claim_type="proof",
            payload={"conclusion": "true"},
        )

        assert plan.claim_id == claim_id

    @pytest.mark.asyncio
    async def test_plan_for_math_domain(self):
        """Math domain should use the 600s timeout and 3 perturbations."""
        from platform.services.verification_orchestrator.planner import (
            VerificationPlanner,
        )

        planner = VerificationPlanner()
        plan = planner.create_plan(
            claim_id=str(uuid4()),
            domain="mathematics",
            claim_type="empirical",
            payload={"results": [1, 2]},
        )

        domain_step = next(s for s in plan.steps if s.verifier_type == "domain")
        assert domain_step.config["timeout"] == 600
        assert domain_step.domain == "mathematics"

        robustness_step = next(s for s in plan.steps if s.verifier_type == "robustness")
        assert robustness_step.config["perturbation_count"] == 3

    @pytest.mark.asyncio
    async def test_plan_for_ml_ai_domain(self):
        """ML/AI domain should use 7200s timeout and 10 perturbations."""
        from platform.services.verification_orchestrator.planner import (
            VerificationPlanner,
        )

        planner = VerificationPlanner()
        plan = planner.create_plan(
            claim_id=str(uuid4()),
            domain="ml_ai",
            claim_type="benchmark",
            payload={"scores": [0.9]},
        )

        domain_step = next(s for s in plan.steps if s.verifier_type == "domain")
        assert domain_step.config["timeout"] == 7200
        assert domain_step.domain == "ml_ai"

        robustness_step = next(s for s in plan.steps if s.verifier_type == "robustness")
        assert robustness_step.config["perturbation_count"] == 10

    @pytest.mark.asyncio
    async def test_plan_lab_context_triggers_consistency(self):
        """A lab context should cause a consistency step even for
        claim types that would not normally require one."""
        from platform.services.verification_orchestrator.planner import (
            VerificationPlanner,
        )

        planner = VerificationPlanner()
        plan = planner.create_plan(
            claim_id=str(uuid4()),
            domain="materials_science",
            claim_type="observational",
            payload={},
            lab_context={"lab_id": str(uuid4())},
        )

        consistency_steps = [s for s in plan.steps if s.verifier_type == "consistency"]
        assert len(consistency_steps) == 1

    @pytest.mark.asyncio
    async def test_plan_no_robustness_for_non_matching_type(self):
        """A claim type not in the robustness set and without
        metrics should NOT produce a robustness step."""
        from platform.services.verification_orchestrator.planner import (
            VerificationPlanner,
        )

        planner = VerificationPlanner()
        plan = planner.create_plan(
            claim_id=str(uuid4()),
            domain="mathematics",
            claim_type="observational",
            payload={"notes": "plain text"},
        )

        robustness_steps = [s for s in plan.steps if s.verifier_type == "robustness"]
        assert len(robustness_steps) == 0
