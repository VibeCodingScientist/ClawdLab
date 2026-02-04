"""Integration tests for experiment lifecycle.

Tests the complete experiment workflow:
- Hypothesis generation
- Experiment creation and design
- Plan creation and management
- Scheduling and execution
- Result recording and analysis
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from platform.experiments.service import ExperimentPlanningService, ExperimentStats
from platform.experiments.base import (
    Experiment,
    ExperimentStatus,
    Hypothesis,
    HypothesisStatus,
    ExperimentPlan,
    ResourceEstimate,
)
from platform.experiments.scheduler import ScheduledExperiment, ScheduleStatus


def utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture
def mock_hypothesis_generator():
    """Create mock hypothesis generator."""
    generator = AsyncMock()

    async def generate_from_gap(domain, gap_description, count):
        return [
            Hypothesis(
                hypothesis_id=f"hyp-{i}",
                title=f"Hypothesis {i}",
                statement=f"Test hypothesis about {gap_description}",
                domain=domain,
                status=HypothesisStatus.PROPOSED,
            )
            for i in range(count)
        ]

    async def generate_comparative(domain, entities):
        return [
            Hypothesis(
                hypothesis_id="hyp-comp-1",
                title="Comparative Hypothesis",
                statement=f"Comparing entities: {entities}",
                domain=domain,
                hypothesis_type="comparative",
            )
        ]

    async def generate_causal(domain, topic):
        return [
            Hypothesis(
                hypothesis_id="hyp-causal-1",
                title="Causal Hypothesis",
                statement=f"Causal relationship in {topic}",
                domain=domain,
                hypothesis_type="causal",
            )
        ]

    async def validate_hypothesis(hypothesis):
        return {
            "valid": True,
            "testability_score": 0.85,
            "specificity_score": 0.9,
            "recommendations": [],
        }

    async def prioritize_hypotheses(hypotheses):
        return sorted(hypotheses, key=lambda h: h.hypothesis_id)

    generator.generate_from_gap = generate_from_gap
    generator.generate_comparative = generate_comparative
    generator.generate_causal = generate_causal
    generator.validate_hypothesis = validate_hypothesis
    generator.prioritize_hypotheses = prioritize_hypotheses

    return generator


@pytest.fixture
def mock_experiment_designer():
    """Create mock experiment designer."""
    designer = AsyncMock()

    experiment_counter = [0]

    async def create_experiment(name, description, domain, experiment_type, created_by):
        experiment_counter[0] += 1
        return Experiment(
            experiment_id=f"exp-{experiment_counter[0]}",
            name=name,
            description=description,
            domain=domain,
            experiment_type=experiment_type,
            status=ExperimentStatus.DRAFT,
            created_by=created_by,
        )

    async def add_variable(exp, name, description, variable_type, data_type, unit):
        exp.variables.append({
            "name": name,
            "description": description,
            "variable_type": variable_type,
            "data_type": data_type,
            "unit": unit,
        })

    async def add_step(exp, name, description, step_type, order, command="", parameters=None):
        exp.steps.append({
            "name": name,
            "description": description,
            "step_type": step_type,
            "order": order,
            "command": command,
            "parameters": parameters or {},
        })

    async def set_config(exp, parameters, hyperparameters, random_seed, environment, dependencies, data_sources):
        exp.config = {
            "parameters": parameters,
            "hyperparameters": hyperparameters,
            "random_seed": random_seed,
            "environment": environment,
            "dependencies": dependencies,
            "data_sources": data_sources,
        }

    async def validate_design(experiment):
        return {
            "valid": True,
            "errors": [],
            "warnings": [],
        }

    async def clone_experiment(experiment, new_name, modifications):
        experiment_counter[0] += 1
        cloned = Experiment(
            experiment_id=f"exp-{experiment_counter[0]}",
            name=new_name or f"Clone of {experiment.name}",
            description=experiment.description,
            domain=experiment.domain,
            experiment_type=experiment.experiment_type,
            status=ExperimentStatus.DRAFT,
        )
        if modifications:
            for key, value in modifications.items():
                if hasattr(cloned, key):
                    setattr(cloned, key, value)
        return cloned

    designer.create_experiment = create_experiment
    designer.add_variable = add_variable
    designer.add_step = add_step
    designer.set_config = set_config
    designer.validate_design = validate_design
    designer.clone_experiment = clone_experiment

    return designer


@pytest.fixture
def mock_scheduler():
    """Create mock experiment scheduler."""
    scheduler = AsyncMock()

    schedule_counter = [0]

    async def schedule_experiment(experiment, priority=None, deadline=None):
        schedule_counter[0] += 1
        return ScheduledExperiment(
            schedule_id=f"sched-{schedule_counter[0]}",
            experiment_id=experiment.experiment_id,
            priority=priority or 1,
            status=ScheduleStatus.PENDING,
        )

    async def schedule_plan(plan):
        scheduled = []
        for exp in plan.experiments:
            schedule_counter[0] += 1
            scheduled.append(ScheduledExperiment(
                schedule_id=f"sched-{schedule_counter[0]}",
                experiment_id=exp.experiment_id,
                priority=1,
                status=ScheduleStatus.PENDING,
            ))
        return scheduled

    async def start_experiment(schedule_id):
        return ScheduledExperiment(
            schedule_id=schedule_id,
            experiment_id="exp-1",
            status=ScheduleStatus.RUNNING,
        )

    async def get_queue_status():
        return {
            "pending": [{"schedule_id": "sched-1", "experiment_id": "exp-1"}],
            "running": [],
            "completed": [],
        }

    scheduler.schedule_experiment = schedule_experiment
    scheduler.schedule_plan = schedule_plan
    scheduler.start_experiment = start_experiment
    scheduler.get_queue_status = get_queue_status
    scheduler.resource_estimator = MagicMock()
    scheduler.resource_estimator.estimate_plan = AsyncMock(return_value=ResourceEstimate(
        cpu_hours=10.0,
        gpu_hours=5.0,
        memory_gb=16.0,
        storage_gb=100.0,
    ))

    return scheduler


@pytest.fixture
def service(mock_hypothesis_generator, mock_experiment_designer, mock_scheduler):
    """Create ExperimentPlanningService with mocked dependencies."""
    with patch("platform.experiments.service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock()
        return ExperimentPlanningService(
            hypothesis_generator=mock_hypothesis_generator,
            experiment_designer=mock_experiment_designer,
            scheduler=mock_scheduler,
        )


# ===========================================
# HYPOTHESIS GENERATION FLOW
# ===========================================


class TestHypothesisGenerationFlow:
    """Tests for hypothesis generation workflow."""

    @pytest.mark.asyncio
    async def test_generate_hypotheses_from_gap(self, service):
        """Test generating hypotheses from research gap."""
        hypotheses = await service.generate_hypotheses(
            domain="ml_ai",
            topic="Neural network optimization",
            count=3,
        )

        assert len(hypotheses) == 3
        for h in hypotheses:
            assert h.domain == "ml_ai"
            assert h.status == HypothesisStatus.PROPOSED

    @pytest.mark.asyncio
    async def test_generate_comparative_hypotheses(self, service):
        """Test generating comparative hypotheses."""
        hypotheses = await service.generate_hypotheses(
            domain="ml_ai",
            topic="Model A, Model B",
            hypothesis_type="comparative",
        )

        assert len(hypotheses) >= 1
        assert hypotheses[0].hypothesis_type == "comparative"

    @pytest.mark.asyncio
    async def test_generate_causal_hypotheses(self, service):
        """Test generating causal hypotheses."""
        hypotheses = await service.generate_hypotheses(
            domain="computational_biology",
            topic="Protein folding",
            hypothesis_type="causal",
        )

        assert len(hypotheses) >= 1
        assert hypotheses[0].hypothesis_type == "causal"

    @pytest.mark.asyncio
    async def test_validate_hypothesis(self, service):
        """Test hypothesis validation."""
        hypotheses = await service.generate_hypotheses(
            domain="ml_ai",
            topic="Test topic",
            count=1,
        )

        validation = await service.validate_hypothesis(hypotheses[0])

        assert validation["valid"] is True
        assert validation["testability_score"] > 0
        assert validation["specificity_score"] > 0

    @pytest.mark.asyncio
    async def test_prioritize_hypotheses(self, service):
        """Test hypothesis prioritization."""
        hypotheses = await service.generate_hypotheses(
            domain="ml_ai",
            topic="Test topic",
            count=3,
        )

        prioritized = await service.prioritize_hypotheses(hypotheses)

        assert len(prioritized) == 3


# ===========================================
# EXPERIMENT CREATION FLOW
# ===========================================


class TestExperimentCreationFlow:
    """Tests for experiment creation workflow."""

    @pytest.mark.asyncio
    async def test_create_experiment(self, service):
        """Test creating a new experiment."""
        experiment = await service.create_experiment(
            name="Test Experiment",
            description="A test experiment",
            domain="ml_ai",
            experiment_type="ml_training",
            created_by="user-1",
        )

        assert experiment is not None
        assert experiment.name == "Test Experiment"
        assert experiment.domain == "ml_ai"
        assert experiment.status == ExperimentStatus.DRAFT

    @pytest.mark.asyncio
    async def test_create_experiment_with_hypotheses(self, service):
        """Test creating experiment with hypotheses."""
        hypotheses = await service.generate_hypotheses(
            domain="ml_ai",
            topic="Optimization",
            count=2,
        )

        experiment = await service.create_experiment(
            name="Hypothesis Test",
            description="Testing hypotheses",
            domain="ml_ai",
            experiment_type="ml_evaluation",
            hypotheses=hypotheses,
        )

        assert len(experiment.hypotheses) == 2

    @pytest.mark.asyncio
    async def test_create_experiment_from_hypothesis(self, service):
        """Test creating experiment from a hypothesis."""
        hypotheses = await service.generate_hypotheses(
            domain="ml_ai",
            topic="Performance comparison",
            count=1,
        )

        experiment = await service.create_experiment_from_hypothesis(
            hypothesis=hypotheses[0],
            domain="ml_ai",
            created_by="researcher-1",
        )

        assert experiment is not None
        assert len(experiment.hypotheses) == 1
        assert experiment.hypotheses[0].status == HypothesisStatus.TESTING

    @pytest.mark.asyncio
    async def test_design_experiment_with_variables(self, service):
        """Test designing experiment with variables."""
        experiment = await service.create_experiment(
            name="Variable Test",
            description="Testing variables",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        designed = await service.design_experiment(
            experiment_id=experiment.experiment_id,
            variables=[
                {
                    "name": "learning_rate",
                    "description": "Model learning rate",
                    "variable_type": "independent",
                    "data_type": "continuous",
                    "unit": "",
                },
                {
                    "name": "accuracy",
                    "description": "Model accuracy",
                    "variable_type": "dependent",
                    "data_type": "continuous",
                    "unit": "%",
                },
            ],
        )

        assert len(designed.variables) == 2

    @pytest.mark.asyncio
    async def test_design_experiment_with_steps(self, service):
        """Test designing experiment with steps."""
        experiment = await service.create_experiment(
            name="Steps Test",
            description="Testing steps",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        designed = await service.design_experiment(
            experiment_id=experiment.experiment_id,
            steps=[
                {"name": "Load Data", "step_type": "data_preparation", "order": 0},
                {"name": "Train Model", "step_type": "execution", "order": 1},
                {"name": "Evaluate", "step_type": "analysis", "order": 2},
            ],
        )

        assert len(designed.steps) == 3

    @pytest.mark.asyncio
    async def test_validate_experiment_design(self, service):
        """Test validating experiment design."""
        experiment = await service.create_experiment(
            name="Validation Test",
            description="Testing validation",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        validation = await service.validate_experiment_design(experiment.experiment_id)

        assert validation["valid"] is True
        assert validation["errors"] == []

    @pytest.mark.asyncio
    async def test_clone_experiment(self, service):
        """Test cloning an experiment."""
        original = await service.create_experiment(
            name="Original Experiment",
            description="To be cloned",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        cloned = await service.clone_experiment(
            experiment_id=original.experiment_id,
            new_name="Cloned Experiment",
        )

        assert cloned is not None
        assert cloned.experiment_id != original.experiment_id
        assert cloned.name == "Cloned Experiment"

    @pytest.mark.asyncio
    async def test_clone_experiment_with_modifications(self, service):
        """Test cloning with modifications."""
        original = await service.create_experiment(
            name="Original",
            description="Original description",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        cloned = await service.clone_experiment(
            experiment_id=original.experiment_id,
            new_name="Modified Clone",
            modifications={"description": "Modified description"},
        )

        assert cloned.description == "Modified description"


# ===========================================
# EXPERIMENT PLAN FLOW
# ===========================================


class TestExperimentPlanFlow:
    """Tests for experiment plan workflow."""

    @pytest.mark.asyncio
    async def test_create_plan(self, service):
        """Test creating an experiment plan."""
        plan = await service.create_plan(
            name="Research Plan",
            description="A research plan",
            objective="Test ML models",
            domain="ml_ai",
            created_by="user-1",
        )

        assert plan is not None
        assert plan.name == "Research Plan"
        assert plan.domain == "ml_ai"

    @pytest.mark.asyncio
    async def test_add_experiments_to_plan(self, service):
        """Test adding experiments to a plan."""
        plan = await service.create_plan(
            name="Multi-Experiment Plan",
            description="Plan with multiple experiments",
            objective="Compare models",
            domain="ml_ai",
        )

        exp1 = await service.create_experiment(
            name="Experiment 1",
            description="First experiment",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        exp2 = await service.create_experiment(
            name="Experiment 2",
            description="Second experiment",
            domain="ml_ai",
            experiment_type="ml_evaluation",
        )

        # Add experiments
        await service.add_experiment_to_plan(plan.plan_id, exp1.experiment_id)
        await service.add_experiment_to_plan(
            plan.plan_id,
            exp2.experiment_id,
            dependencies=[exp1.experiment_id],
        )

        updated_plan = await service.get_plan(plan.plan_id)

        assert len(updated_plan.experiments) == 2
        assert exp2.experiment_id in updated_plan.dependencies

    @pytest.mark.asyncio
    async def test_estimate_plan_resources(self, service):
        """Test estimating plan resources."""
        plan = await service.create_plan(
            name="Resource Plan",
            description="Plan for resource estimation",
            objective="Estimate resources",
            domain="ml_ai",
        )

        exp = await service.create_experiment(
            name="Resource Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        await service.add_experiment_to_plan(plan.plan_id, exp.experiment_id)

        estimate = await service.estimate_plan_resources(plan.plan_id)

        assert estimate is not None
        assert estimate.cpu_hours > 0
        assert estimate.gpu_hours >= 0

    @pytest.mark.asyncio
    async def test_list_plans(self, service):
        """Test listing experiment plans."""
        await service.create_plan(
            name="Plan 1",
            description="First plan",
            objective="Test",
            domain="ml_ai",
        )

        await service.create_plan(
            name="Plan 2",
            description="Second plan",
            objective="Test",
            domain="computational_biology",
        )

        all_plans = await service.list_plans()
        assert len(all_plans) == 2

        ml_plans = await service.list_plans(domain="ml_ai")
        assert len(ml_plans) == 1


# ===========================================
# SCHEDULING AND EXECUTION FLOW
# ===========================================


class TestSchedulingExecutionFlow:
    """Tests for scheduling and execution workflow."""

    @pytest.mark.asyncio
    async def test_schedule_experiment(self, service):
        """Test scheduling an experiment."""
        experiment = await service.create_experiment(
            name="Scheduled Experiment",
            description="To be scheduled",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        scheduled = await service.schedule_experiment(
            experiment_id=experiment.experiment_id,
            priority=1,
        )

        assert scheduled is not None
        assert scheduled.experiment_id == experiment.experiment_id
        assert scheduled.status == ScheduleStatus.PENDING

        # Verify experiment status updated
        exp = await service._experiments.get(experiment.experiment_id)
        assert exp.status == ExperimentStatus.QUEUED

    @pytest.mark.asyncio
    async def test_schedule_experiment_with_deadline(self, service):
        """Test scheduling with deadline."""
        experiment = await service.create_experiment(
            name="Deadline Experiment",
            description="Has a deadline",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        deadline = utcnow() + timedelta(hours=24)

        scheduled = await service.schedule_experiment(
            experiment_id=experiment.experiment_id,
            deadline=deadline,
        )

        assert scheduled is not None

    @pytest.mark.asyncio
    async def test_schedule_plan(self, service):
        """Test scheduling all experiments in a plan."""
        plan = await service.create_plan(
            name="Scheduled Plan",
            description="Plan to schedule",
            objective="Run experiments",
            domain="ml_ai",
        )

        exp1 = await service.create_experiment(
            name="Plan Exp 1",
            description="First",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        exp2 = await service.create_experiment(
            name="Plan Exp 2",
            description="Second",
            domain="ml_ai",
            experiment_type="ml_evaluation",
        )

        await service.add_experiment_to_plan(plan.plan_id, exp1.experiment_id)
        await service.add_experiment_to_plan(plan.plan_id, exp2.experiment_id)

        scheduled_list = await service.schedule_plan(plan.plan_id)

        assert len(scheduled_list) == 2

        # Verify plan status
        updated_plan = await service.get_plan(plan.plan_id)
        assert updated_plan.status == "scheduled"

    @pytest.mark.asyncio
    async def test_start_experiment(self, service):
        """Test starting a scheduled experiment."""
        experiment = await service.create_experiment(
            name="Start Test",
            description="To be started",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        await service.schedule_experiment(experiment.experiment_id)

        exp, scheduled = await service.start_experiment(experiment.experiment_id)

        if scheduled:
            assert scheduled.status == ScheduleStatus.RUNNING
            assert exp.status == ExperimentStatus.RUNNING
            assert exp.started_at is not None

    @pytest.mark.asyncio
    async def test_complete_experiment_success(self, service):
        """Test completing experiment successfully."""
        experiment = await service.create_experiment(
            name="Complete Test",
            description="To be completed",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        # Complete with results
        result = await service.complete_experiment(
            experiment_id=experiment.experiment_id,
            results={
                "metrics": {"accuracy": 0.95, "loss": 0.05},
                "statistics": {"mean": 0.9, "std": 0.02},
                "confidence": 0.95,
                "p_value": 0.01,
                "summary": "Experiment completed successfully",
            },
            success=True,
        )

        assert result is not None
        assert result.metrics["accuracy"] == 0.95

        # Verify experiment status
        exp = await service._experiments.get(experiment.experiment_id)
        assert exp.status == ExperimentStatus.COMPLETED
        assert exp.progress == 1.0

    @pytest.mark.asyncio
    async def test_complete_experiment_failure(self, service):
        """Test completing experiment with failure."""
        experiment = await service.create_experiment(
            name="Failure Test",
            description="Will fail",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        result = await service.complete_experiment(
            experiment_id=experiment.experiment_id,
            results={"error": "Out of memory"},
            success=False,
        )

        assert result is not None

        exp = await service._experiments.get(experiment.experiment_id)
        assert exp.status == ExperimentStatus.FAILED


# ===========================================
# COMPLETE LIFECYCLE FLOW
# ===========================================


class TestCompleteLifecycleFlow:
    """Tests for complete experiment lifecycle."""

    @pytest.mark.asyncio
    async def test_complete_research_workflow(self, service):
        """Test complete research workflow from hypothesis to results."""
        # 1. Generate hypotheses
        hypotheses = await service.generate_hypotheses(
            domain="ml_ai",
            topic="Transformer efficiency",
            count=2,
        )
        assert len(hypotheses) == 2

        # 2. Validate and prioritize
        for h in hypotheses:
            validation = await service.validate_hypothesis(h)
            assert validation["valid"]

        prioritized = await service.prioritize_hypotheses(hypotheses)

        # 3. Create experiment from top hypothesis
        experiment = await service.create_experiment_from_hypothesis(
            hypothesis=prioritized[0],
            domain="ml_ai",
            created_by="researcher-1",
        )
        assert experiment is not None

        # 4. Design experiment
        designed = await service.design_experiment(
            experiment_id=experiment.experiment_id,
            variables=[
                {"name": "batch_size", "variable_type": "independent", "data_type": "discrete"},
                {"name": "throughput", "variable_type": "dependent", "data_type": "continuous"},
            ],
            config={
                "parameters": {"epochs": 100},
                "hyperparameters": {"learning_rate": 0.001},
                "random_seed": 42,
            },
        )

        # 5. Validate design
        validation = await service.validate_experiment_design(designed.experiment_id)
        assert validation["valid"]

        # 6. Schedule experiment
        scheduled = await service.schedule_experiment(designed.experiment_id)
        assert scheduled is not None

        # 7. Start experiment
        exp, _ = await service.start_experiment(designed.experiment_id)

        # 8. Complete experiment
        result = await service.complete_experiment(
            experiment_id=exp.experiment_id,
            results={
                "metrics": {"throughput": 1000, "accuracy": 0.98},
                "confidence": 0.95,
                "summary": "Hypothesis supported",
            },
            success=True,
        )

        assert result is not None
        assert result.metrics["throughput"] == 1000

        # Verify final state
        final_exp = await service._experiments.get(exp.experiment_id)
        assert final_exp.status == ExperimentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_multi_experiment_plan_workflow(self, service):
        """Test workflow with multiple experiments in a plan."""
        # 1. Create plan
        plan = await service.create_plan(
            name="Comprehensive Study",
            description="Multiple related experiments",
            objective="Compare optimization methods",
            domain="ml_ai",
        )

        # 2. Create experiments
        exp1 = await service.create_experiment(
            name="SGD Experiment",
            description="Test SGD optimizer",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        exp2 = await service.create_experiment(
            name="Adam Experiment",
            description="Test Adam optimizer",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        exp3 = await service.create_experiment(
            name="Comparison Analysis",
            description="Compare results",
            domain="ml_ai",
            experiment_type="ml_evaluation",
        )

        # 3. Add to plan with dependencies
        await service.add_experiment_to_plan(plan.plan_id, exp1.experiment_id)
        await service.add_experiment_to_plan(plan.plan_id, exp2.experiment_id)
        await service.add_experiment_to_plan(
            plan.plan_id,
            exp3.experiment_id,
            dependencies=[exp1.experiment_id, exp2.experiment_id],
        )

        # 4. Estimate resources
        estimate = await service.estimate_plan_resources(plan.plan_id)
        assert estimate.cpu_hours > 0

        # 5. Schedule plan
        scheduled = await service.schedule_plan(plan.plan_id)
        assert len(scheduled) == 3

        # 6. Complete experiments in order
        await service.complete_experiment(
            exp1.experiment_id,
            results={"accuracy": 0.92},
            success=True,
        )

        await service.complete_experiment(
            exp2.experiment_id,
            results={"accuracy": 0.95},
            success=True,
        )

        await service.complete_experiment(
            exp3.experiment_id,
            results={"comparison": "Adam outperforms SGD"},
            success=True,
        )

        # Verify all completed
        for exp_id in [exp1.experiment_id, exp2.experiment_id, exp3.experiment_id]:
            exp = service._experiments.get(exp_id)
            assert exp.status == ExperimentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_experiment_iteration_workflow(self, service):
        """Test iterative experiment refinement."""
        # 1. Initial experiment
        exp1 = await service.create_experiment(
            name="Initial Experiment",
            description="First attempt",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        await service.design_experiment(
            exp1.experiment_id,
            config={"parameters": {"learning_rate": 0.01}},
        )

        # 2. Run and get poor results
        await service.complete_experiment(
            exp1.experiment_id,
            results={"accuracy": 0.75},
            success=True,
        )

        # 3. Clone and modify
        exp2 = await service.clone_experiment(
            exp1.experiment_id,
            new_name="Refined Experiment",
            modifications={"description": "Improved parameters"},
        )

        await service.design_experiment(
            exp2.experiment_id,
            config={"parameters": {"learning_rate": 0.001}},
        )

        # 4. Run refined experiment
        await service.complete_experiment(
            exp2.experiment_id,
            results={"accuracy": 0.90},
            success=True,
        )

        # 5. Further refinement
        exp3 = await service.clone_experiment(
            exp2.experiment_id,
            new_name="Final Experiment",
        )

        await service.complete_experiment(
            exp3.experiment_id,
            results={"accuracy": 0.95},
            success=True,
        )

        # Verify progression
        results = [
            service._experiments[exp1.experiment_id].results.get("accuracy", 0),
            service._experiments[exp2.experiment_id].results.get("accuracy", 0),
            service._experiments[exp3.experiment_id].results.get("accuracy", 0),
        ]

        # Each iteration should show improvement
        assert results[0] < results[1] < results[2]
