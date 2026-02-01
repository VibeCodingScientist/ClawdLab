"""Unit tests for ExperimentPlanningService."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from platform.experiments.service import ExperimentPlanningService, ExperimentStats
from platform.experiments.base import (
    Experiment,
    ExperimentPlan,
    ExperimentResult,
    ExperimentStatus,
    Hypothesis,
    HypothesisStatus,
    Checkpoint,
    ResourceEstimate,
)


class TestExperimentPlanningService:
    """Tests for ExperimentPlanningService class."""

    @pytest.fixture
    def mock_hypothesis_generator(self) -> AsyncMock:
        """Create mock hypothesis generator."""
        mock = AsyncMock()
        mock.generate_from_gap.return_value = [
            Hypothesis(
                title="Test Hypothesis",
                statement="Testing that X leads to Y",
                hypothesis_type="causal",
            )
        ]
        mock.generate_causal.return_value = [
            Hypothesis(
                title="Causal Hypothesis",
                statement="X causes Y",
                hypothesis_type="causal",
            )
        ]
        mock.generate_comparative.return_value = [
            Hypothesis(
                title="Comparative Hypothesis",
                statement="X is better than Y",
                hypothesis_type="comparative",
            )
        ]
        mock.validate_hypothesis.return_value = {"valid": True, "issues": []}
        mock.prioritize_hypotheses.return_value = []
        return mock

    @pytest.fixture
    def mock_designer(self) -> AsyncMock:
        """Create mock experiment designer."""
        mock = AsyncMock()
        mock.create_experiment.return_value = Experiment(
            name="Test Experiment",
            description="Test Description",
            domain="ml_ai",
            experiment_type="ml_training",
            created_by="test-user",
        )
        mock.add_step.return_value = None
        mock.add_variable.return_value = None
        mock.set_config.return_value = None
        mock.validate_design.return_value = {"valid": True, "issues": []}
        mock.clone_experiment.return_value = Experiment(
            name="Cloned Experiment",
            description="Cloned Description",
            domain="ml_ai",
            experiment_type="ml_training",
        )
        return mock

    @pytest.fixture
    def mock_scheduler(self) -> AsyncMock:
        """Create mock scheduler."""
        mock = AsyncMock()
        mock.schedule_experiment.return_value = MagicMock(schedule_id="schedule-1")
        mock.schedule_plan.return_value = [MagicMock(schedule_id="schedule-1")]
        mock.get_queue_status.return_value = {"pending": [], "running": []}
        mock.start_experiment.return_value = MagicMock(schedule_id="schedule-1")
        mock.complete_experiment.return_value = None
        mock.cancel_experiment.return_value = None
        mock.resource_estimator = MagicMock()
        mock.resource_estimator.estimate_plan = AsyncMock(
            return_value=ResourceEstimate(
                gpu_hours=10.0, cpu_hours=20.0, memory_gb=16.0
            )
        )
        mock.get_resource_status.return_value = {"available": True}
        return mock

    @pytest.fixture
    def service(
        self,
        mock_hypothesis_generator,
        mock_designer,
        mock_scheduler,
    ) -> ExperimentPlanningService:
        """Create service with mocked dependencies."""
        return ExperimentPlanningService(
            hypothesis_generator=mock_hypothesis_generator,
            experiment_designer=mock_designer,
            scheduler=mock_scheduler,
        )

    # ===================================
    # HYPOTHESIS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_generate_hypotheses_from_gap(
        self,
        service: ExperimentPlanningService,
        mock_hypothesis_generator: AsyncMock,
    ):
        """Test hypothesis generation from research gap."""
        hypotheses = await service.generate_hypotheses(
            domain="ml_ai",
            topic="transformer efficiency",
            count=3,
        )

        assert len(hypotheses) == 1
        mock_hypothesis_generator.generate_from_gap.assert_called_once_with(
            domain="ml_ai",
            gap_description="transformer efficiency",
            count=3,
        )

    @pytest.mark.asyncio
    async def test_generate_hypotheses_causal(
        self,
        service: ExperimentPlanningService,
        mock_hypothesis_generator: AsyncMock,
    ):
        """Test causal hypothesis generation."""
        hypotheses = await service.generate_hypotheses(
            domain="ml_ai",
            topic="attention mechanism",
            hypothesis_type="causal",
        )

        assert len(hypotheses) == 1
        mock_hypothesis_generator.generate_causal.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_hypotheses_comparative(
        self,
        service: ExperimentPlanningService,
        mock_hypothesis_generator: AsyncMock,
    ):
        """Test comparative hypothesis generation."""
        hypotheses = await service.generate_hypotheses(
            domain="ml_ai",
            topic="GPT vs BERT",
            hypothesis_type="comparative",
        )

        assert len(hypotheses) == 1
        mock_hypothesis_generator.generate_comparative.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_hypothesis(
        self,
        service: ExperimentPlanningService,
        mock_hypothesis_generator: AsyncMock,
    ):
        """Test hypothesis validation."""
        hypothesis = Hypothesis(
            title="Test Hypothesis",
            statement="X leads to Y",
        )

        result = await service.validate_hypothesis(hypothesis)

        assert result["valid"] is True
        mock_hypothesis_generator.validate_hypothesis.assert_called_once_with(hypothesis)

    # ===================================
    # EXPERIMENT CREATION TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_create_experiment(
        self,
        service: ExperimentPlanningService,
        mock_designer: AsyncMock,
    ):
        """Test experiment creation."""
        experiment = await service.create_experiment(
            name="Test Experiment",
            description="A test experiment",
            domain="ml_ai",
            experiment_type="ml_training",
            created_by="user-1",
        )

        assert experiment is not None
        assert experiment.name == "Test Experiment"
        assert experiment.experiment_id in service._experiments

    @pytest.mark.asyncio
    async def test_create_experiment_with_hypotheses(
        self,
        service: ExperimentPlanningService,
        mock_designer: AsyncMock,
    ):
        """Test experiment creation with hypotheses."""
        hypotheses = [
            Hypothesis(title="H1", statement="Test 1"),
            Hypothesis(title="H2", statement="Test 2"),
        ]

        experiment = await service.create_experiment(
            name="Test Experiment",
            description="A test experiment",
            domain="ml_ai",
            experiment_type="ml_training",
            hypotheses=hypotheses,
        )

        assert len(experiment.hypotheses) == 2

    @pytest.mark.asyncio
    async def test_create_experiment_from_hypothesis(
        self,
        service: ExperimentPlanningService,
        mock_designer: AsyncMock,
    ):
        """Test experiment creation from hypothesis."""
        hypothesis = Hypothesis(
            title="Test Hypothesis",
            statement="Testing performance improvement",
            hypothesis_type="causal",
        )

        experiment = await service.create_experiment_from_hypothesis(
            hypothesis=hypothesis,
            domain="ml_ai",
            created_by="user-1",
        )

        assert experiment is not None
        assert hypothesis.status == HypothesisStatus.TESTING
        # Should add default steps
        assert mock_designer.add_step.call_count == 5

    @pytest.mark.asyncio
    async def test_design_experiment(
        self,
        service: ExperimentPlanningService,
        mock_designer: AsyncMock,
    ):
        """Test experiment design with variables and steps."""
        # Create experiment first
        experiment = await service.create_experiment(
            name="Test Experiment",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        # Design it
        designed = await service.design_experiment(
            experiment_id=experiment.experiment_id,
            variables=[
                {"name": "learning_rate", "variable_type": "independent"},
            ],
            steps=[
                {"name": "Train", "step_type": "execution"},
            ],
            config={
                "parameters": {"epochs": 100},
                "hyperparameters": {"batch_size": 32},
            },
        )

        assert designed is not None
        mock_designer.add_variable.assert_called()
        mock_designer.add_step.assert_called()
        mock_designer.set_config.assert_called()

    @pytest.mark.asyncio
    async def test_design_experiment_not_found(
        self,
        service: ExperimentPlanningService,
    ):
        """Test designing non-existent experiment raises error."""
        with pytest.raises(ValueError, match="Experiment not found"):
            await service.design_experiment(
                experiment_id="non-existent",
                variables=[],
            )

    @pytest.mark.asyncio
    async def test_clone_experiment(
        self,
        service: ExperimentPlanningService,
        mock_designer: AsyncMock,
    ):
        """Test experiment cloning."""
        # Create original
        original = await service.create_experiment(
            name="Original",
            description="Original experiment",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        # Clone it
        cloned = await service.clone_experiment(
            experiment_id=original.experiment_id,
            new_name="Cloned",
        )

        assert cloned is not None
        assert cloned.experiment_id != original.experiment_id
        assert cloned.experiment_id in service._experiments

    # ===================================
    # EXPERIMENT PLAN TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_create_plan(self, service: ExperimentPlanningService):
        """Test experiment plan creation."""
        plan = await service.create_plan(
            name="Test Plan",
            description="A test plan",
            objective="Test objective",
            domain="ml_ai",
            created_by="user-1",
        )

        assert plan is not None
        assert plan.name == "Test Plan"
        assert plan.plan_id in service._plans

    @pytest.mark.asyncio
    async def test_add_experiment_to_plan(self, service: ExperimentPlanningService):
        """Test adding experiment to plan."""
        # Create plan
        plan = await service.create_plan(
            name="Test Plan",
            description="Test",
            objective="Test",
            domain="ml_ai",
        )

        # Create experiment
        experiment = await service.create_experiment(
            name="Test Experiment",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        # Add to plan
        updated_plan = await service.add_experiment_to_plan(
            plan_id=plan.plan_id,
            experiment_id=experiment.experiment_id,
            dependencies=["dep-1"],
        )

        assert len(updated_plan.experiments) == 1
        assert experiment.experiment_id in updated_plan.dependencies

    @pytest.mark.asyncio
    async def test_add_experiment_to_plan_not_found(
        self, service: ExperimentPlanningService
    ):
        """Test adding experiment to non-existent plan raises error."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        with pytest.raises(ValueError, match="Plan not found"):
            await service.add_experiment_to_plan(
                plan_id="non-existent",
                experiment_id=experiment.experiment_id,
            )

    @pytest.mark.asyncio
    async def test_estimate_plan_resources(
        self,
        service: ExperimentPlanningService,
        mock_scheduler: AsyncMock,
    ):
        """Test resource estimation for plan."""
        plan = await service.create_plan(
            name="Test Plan",
            description="Test",
            objective="Test",
            domain="ml_ai",
        )

        estimate = await service.estimate_plan_resources(plan.plan_id)

        assert estimate is not None
        assert estimate.gpu_hours == 10.0
        assert estimate.cpu_hours == 20.0

    @pytest.mark.asyncio
    async def test_get_plan(self, service: ExperimentPlanningService):
        """Test getting plan by ID."""
        plan = await service.create_plan(
            name="Test Plan",
            description="Test",
            objective="Test",
            domain="ml_ai",
        )

        retrieved = await service.get_plan(plan.plan_id)
        assert retrieved is not None
        assert retrieved.plan_id == plan.plan_id

    @pytest.mark.asyncio
    async def test_list_plans(self, service: ExperimentPlanningService):
        """Test listing plans with filters."""
        await service.create_plan(
            name="Plan 1",
            description="Test",
            objective="Test",
            domain="ml_ai",
        )
        await service.create_plan(
            name="Plan 2",
            description="Test",
            objective="Test",
            domain="mathematics",
        )

        all_plans = await service.list_plans()
        assert len(all_plans) == 2

        ml_plans = await service.list_plans(domain="ml_ai")
        assert len(ml_plans) == 1

    # ===================================
    # SCHEDULING AND EXECUTION TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_schedule_experiment(
        self,
        service: ExperimentPlanningService,
        mock_scheduler: AsyncMock,
    ):
        """Test scheduling experiment."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        scheduled = await service.schedule_experiment(
            experiment_id=experiment.experiment_id,
            priority=1,
        )

        assert scheduled is not None
        assert experiment.status == ExperimentStatus.QUEUED
        mock_scheduler.schedule_experiment.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_plan(
        self,
        service: ExperimentPlanningService,
        mock_scheduler: AsyncMock,
    ):
        """Test scheduling all experiments in a plan."""
        plan = await service.create_plan(
            name="Test Plan",
            description="Test",
            objective="Test",
            domain="ml_ai",
        )
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )
        await service.add_experiment_to_plan(plan.plan_id, experiment.experiment_id)

        scheduled_list = await service.schedule_plan(plan.plan_id)

        assert len(scheduled_list) == 1
        assert plan.status == "scheduled"
        mock_scheduler.schedule_plan.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_experiment_success(
        self,
        service: ExperimentPlanningService,
    ):
        """Test completing experiment with success."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )
        hypothesis = Hypothesis(title="Test", statement="Test")
        experiment.hypotheses.append(hypothesis)

        result = await service.complete_experiment(
            experiment_id=experiment.experiment_id,
            results={
                "metrics": {"accuracy": 0.95},
                "summary": "Test completed",
                "hypothesis_outcomes": {hypothesis.hypothesis_id: "supported"},
            },
            success=True,
        )

        assert result is not None
        assert experiment.status == ExperimentStatus.COMPLETED
        assert experiment.progress == 1.0
        assert hypothesis.status == HypothesisStatus.SUPPORTED
        assert result.result_id in service._results

    @pytest.mark.asyncio
    async def test_complete_experiment_failure(
        self,
        service: ExperimentPlanningService,
    ):
        """Test completing experiment with failure."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        result = await service.complete_experiment(
            experiment_id=experiment.experiment_id,
            results={"error": "Training failed"},
            success=False,
        )

        assert experiment.status == ExperimentStatus.FAILED

    @pytest.mark.asyncio
    async def test_pause_experiment(self, service: ExperimentPlanningService):
        """Test pausing experiment."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )
        experiment.status = ExperimentStatus.RUNNING

        paused = await service.pause_experiment(experiment.experiment_id)

        assert paused.status == ExperimentStatus.PAUSED

    @pytest.mark.asyncio
    async def test_resume_experiment(self, service: ExperimentPlanningService):
        """Test resuming paused experiment."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )
        experiment.status = ExperimentStatus.PAUSED

        resumed = await service.resume_experiment(experiment.experiment_id)

        assert resumed.status == ExperimentStatus.RUNNING

    @pytest.mark.asyncio
    async def test_cancel_experiment(
        self,
        service: ExperimentPlanningService,
        mock_scheduler: AsyncMock,
    ):
        """Test cancelling experiment."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        cancelled = await service.cancel_experiment(experiment.experiment_id)

        assert cancelled.status == ExperimentStatus.CANCELLED

    # ===================================
    # CHECKPOINT TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_create_checkpoint(self, service: ExperimentPlanningService):
        """Test creating checkpoint."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        checkpoint = await service.create_checkpoint(
            experiment_id=experiment.experiment_id,
            step_id="step-1",
            state={"epoch": 50, "model_weights": "path/to/weights"},
            metrics={"loss": 0.5},
        )

        assert checkpoint is not None
        assert checkpoint.experiment_id == experiment.experiment_id
        assert checkpoint.state["epoch"] == 50

    @pytest.mark.asyncio
    async def test_get_checkpoints(self, service: ExperimentPlanningService):
        """Test getting checkpoints for experiment."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        await service.create_checkpoint(
            experiment_id=experiment.experiment_id,
            step_id="step-1",
            state={"epoch": 10},
        )
        await service.create_checkpoint(
            experiment_id=experiment.experiment_id,
            step_id="step-1",
            state={"epoch": 20},
        )

        checkpoints = await service.get_checkpoints(experiment.experiment_id)
        assert len(checkpoints) == 2

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint(self, service: ExperimentPlanningService):
        """Test restoring from checkpoint."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        checkpoint = await service.create_checkpoint(
            experiment_id=experiment.experiment_id,
            step_id="step-1",
            state={"epoch": 50, "weights": "data"},
        )

        state = await service.restore_from_checkpoint(
            experiment_id=experiment.experiment_id,
            checkpoint_id=checkpoint.checkpoint_id,
        )

        assert state is not None
        assert state["epoch"] == 50

    # ===================================
    # QUERY AND RETRIEVAL TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_experiment(self, service: ExperimentPlanningService):
        """Test getting experiment by ID."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        retrieved = await service.get_experiment(experiment.experiment_id)
        assert retrieved is not None
        assert retrieved.experiment_id == experiment.experiment_id

    @pytest.mark.asyncio
    async def test_get_experiment_not_found(self, service: ExperimentPlanningService):
        """Test getting non-existent experiment returns None."""
        result = await service.get_experiment("non-existent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_experiments(self, service: ExperimentPlanningService):
        """Test listing experiments with filters."""
        await service.create_experiment(
            name="ML Exp",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )
        await service.create_experiment(
            name="Math Exp",
            description="Test",
            domain="mathematics",
            experiment_type="proof_verification",
        )

        all_exp = await service.list_experiments()
        assert len(all_exp) == 2

        ml_exp = await service.list_experiments(domain="ml_ai")
        assert len(ml_exp) == 1
        assert ml_exp[0].domain == "ml_ai"

    @pytest.mark.asyncio
    async def test_list_experiments_pagination(self, service: ExperimentPlanningService):
        """Test listing experiments with pagination."""
        for i in range(10):
            await service.create_experiment(
                name=f"Exp {i}",
                description="Test",
                domain="ml_ai",
                experiment_type="ml_training",
            )

        page1 = await service.list_experiments(limit=5, offset=0)
        page2 = await service.list_experiments(limit=5, offset=5)

        assert len(page1) == 5
        assert len(page2) == 5

    @pytest.mark.asyncio
    async def test_search_experiments(self, service: ExperimentPlanningService):
        """Test searching experiments."""
        await service.create_experiment(
            name="Transformer Training",
            description="Training a transformer model",
            domain="ml_ai",
            experiment_type="ml_training",
        )
        await service.create_experiment(
            name="CNN Evaluation",
            description="Evaluating CNN performance",
            domain="ml_ai",
            experiment_type="ml_evaluation",
        )

        results = await service.search_experiments("transformer")
        assert len(results) == 1
        assert "Transformer" in results[0].name

    @pytest.mark.asyncio
    async def test_get_result(self, service: ExperimentPlanningService):
        """Test getting experiment result."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        result = await service.complete_experiment(
            experiment_id=experiment.experiment_id,
            results={"metrics": {"accuracy": 0.95}},
            success=True,
        )

        retrieved = await service.get_result(result.result_id)
        assert retrieved is not None
        assert retrieved.result_id == result.result_id

    @pytest.mark.asyncio
    async def test_get_results_for_experiment(self, service: ExperimentPlanningService):
        """Test getting all results for an experiment."""
        experiment = await service.create_experiment(
            name="Test",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )

        await service.complete_experiment(
            experiment_id=experiment.experiment_id,
            results={"metrics": {"accuracy": 0.95}},
            success=True,
        )

        results = await service.get_results_for_experiment(experiment.experiment_id)
        assert len(results) == 1

    # ===================================
    # STATISTICS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_stats(self, service: ExperimentPlanningService):
        """Test getting experiment statistics."""
        exp1 = await service.create_experiment(
            name="Exp 1",
            description="Test",
            domain="ml_ai",
            experiment_type="ml_training",
        )
        exp2 = await service.create_experiment(
            name="Exp 2",
            description="Test",
            domain="mathematics",
            experiment_type="proof_verification",
        )

        exp1.status = ExperimentStatus.COMPLETED
        exp2.status = ExperimentStatus.RUNNING

        hypothesis = Hypothesis(title="H1", statement="Test")
        hypothesis.status = HypothesisStatus.SUPPORTED
        exp1.hypotheses.append(hypothesis)

        stats = await service.get_stats()

        assert stats.total_experiments == 2
        assert stats.completed_count == 1
        assert stats.running_count == 1
        assert stats.total_hypotheses == 1
        assert stats.supported_hypotheses == 1

    @pytest.mark.asyncio
    async def test_get_queue_status(
        self,
        service: ExperimentPlanningService,
        mock_scheduler: AsyncMock,
    ):
        """Test getting scheduler queue status."""
        status = await service.get_queue_status()

        assert "pending" in status
        assert "running" in status
        mock_scheduler.get_queue_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_resource_status(
        self,
        service: ExperimentPlanningService,
        mock_scheduler: AsyncMock,
    ):
        """Test getting resource status."""
        status = await service.get_resource_status()

        assert status is not None
        mock_scheduler.get_resource_status.assert_called_once()

    # ===================================
    # EXPERIMENT TYPE DETERMINATION TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_determine_experiment_type_ml_performance(
        self, service: ExperimentPlanningService
    ):
        """Test experiment type determination for ML performance."""
        hypothesis = Hypothesis(
            title="Test",
            statement="This model achieves better performance",
        )

        exp_type = service._determine_experiment_type(hypothesis, "ml_ai")
        assert exp_type == "ml_evaluation"

    @pytest.mark.asyncio
    async def test_determine_experiment_type_math_proof(
        self, service: ExperimentPlanningService
    ):
        """Test experiment type determination for math proof."""
        hypothesis = Hypothesis(
            title="Test",
            statement="The proof of theorem X",
        )

        exp_type = service._determine_experiment_type(hypothesis, "mathematics")
        assert exp_type == "proof_verification"

    @pytest.mark.asyncio
    async def test_determine_experiment_type_biology_structure(
        self, service: ExperimentPlanningService
    ):
        """Test experiment type determination for biology structure."""
        hypothesis = Hypothesis(
            title="Test",
            statement="The protein structure determines function",
        )

        exp_type = service._determine_experiment_type(hypothesis, "computational_biology")
        assert exp_type == "structure_prediction"
