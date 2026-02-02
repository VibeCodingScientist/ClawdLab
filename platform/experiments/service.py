"""Main Experiment Planning Service."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from platform.experiments.base import (
    Checkpoint,
    Experiment,
    ExperimentPlan,
    ExperimentResult,
    ExperimentStatus,
    Hypothesis,
    HypothesisStatus,
    ResourceEstimate,
)
from platform.experiments.config import get_settings
from platform.experiments.designer import ExperimentDesigner, get_designer
from platform.experiments.hypothesis import HypothesisGenerator, get_hypothesis_generator
from platform.experiments.scheduler import (
    ExperimentScheduler,
    ResourceEstimator,
    ScheduledExperiment,
    ScheduleStatus,
    get_scheduler,
)


@dataclass
class ExperimentStats:
    """Statistics about experiments."""

    total_experiments: int = 0
    draft_count: int = 0
    planned_count: int = 0
    queued_count: int = 0
    running_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    total_hypotheses: int = 0
    supported_hypotheses: int = 0
    refuted_hypotheses: int = 0
    total_plans: int = 0
    total_gpu_hours_used: float = 0.0
    total_cpu_hours_used: float = 0.0
    avg_experiment_duration: float = 0.0


class ExperimentPlanningService:
    """Main service for experiment planning and management."""

    def __init__(
        self,
        hypothesis_generator: HypothesisGenerator | None = None,
        experiment_designer: ExperimentDesigner | None = None,
        scheduler: ExperimentScheduler | None = None,
    ) -> None:
        self._settings = get_settings()
        self._hypothesis_generator = hypothesis_generator or get_hypothesis_generator()
        self._experiment_designer = experiment_designer or get_designer()
        self._scheduler = scheduler or get_scheduler()

        # Storage
        self._experiments: dict[str, Experiment] = {}
        self._plans: dict[str, ExperimentPlan] = {}
        self._results: dict[str, ExperimentResult] = {}
        self._checkpoints: dict[str, list[Checkpoint]] = {}

    # ===========================================
    # HYPOTHESIS MANAGEMENT
    # ===========================================

    async def generate_hypotheses(
        self,
        domain: str,
        topic: str,
        count: int = 3,
        hypothesis_type: str | None = None,
    ) -> list[Hypothesis]:
        """Generate hypotheses for a domain and topic."""
        if hypothesis_type == "comparative":
            return await self._hypothesis_generator.generate_comparative(
                domain=domain,
                entities=[topic],  # Topic can contain comma-separated entities
            )
        elif hypothesis_type == "causal":
            return await self._hypothesis_generator.generate_causal(
                domain=domain,
                topic=topic,
            )
        else:
            return await self._hypothesis_generator.generate_from_gap(
                domain=domain,
                gap_description=topic,
                count=count,
            )

    async def validate_hypothesis(self, hypothesis: Hypothesis) -> dict[str, Any]:
        """Validate a hypothesis."""
        return await self._hypothesis_generator.validate_hypothesis(hypothesis)

    async def prioritize_hypotheses(
        self,
        hypotheses: list[Hypothesis],
    ) -> list[Hypothesis]:
        """Prioritize hypotheses by testability and impact."""
        return await self._hypothesis_generator.prioritize_hypotheses(hypotheses)

    # ===========================================
    # EXPERIMENT DESIGN
    # ===========================================

    async def create_experiment(
        self,
        name: str,
        description: str,
        domain: str,
        experiment_type: str,
        hypotheses: list[Hypothesis] | None = None,
        created_by: str = "system",
    ) -> Experiment:
        """Create a new experiment."""
        experiment = await self._experiment_designer.create_experiment(
            name=name,
            description=description,
            domain=domain,
            experiment_type=experiment_type,
            created_by=created_by,
        )

        if hypotheses:
            for h in hypotheses:
                experiment.hypotheses.append(h)

        self._experiments[experiment.experiment_id] = experiment
        return experiment

    async def create_experiment_from_hypothesis(
        self,
        hypothesis: Hypothesis,
        domain: str,
        created_by: str = "system",
    ) -> Experiment:
        """Create an experiment to test a specific hypothesis."""
        # Determine experiment type based on hypothesis
        exp_type = self._determine_experiment_type(hypothesis, domain)

        experiment = await self._experiment_designer.create_experiment(
            name=f"Test: {hypothesis.title}",
            description=f"Experiment to test hypothesis: {hypothesis.statement}",
            domain=domain,
            experiment_type=exp_type,
            created_by=created_by,
        )

        # Update hypothesis status
        hypothesis.status = HypothesisStatus.TESTING
        experiment.hypotheses.append(hypothesis)

        # Add default steps based on hypothesis type
        await self._add_default_steps(experiment, hypothesis)

        self._experiments[experiment.experiment_id] = experiment
        return experiment

    def _determine_experiment_type(self, hypothesis: Hypothesis, domain: str) -> str:
        """Determine appropriate experiment type from hypothesis and domain."""
        h_type = hypothesis.hypothesis_type

        if domain == "ml_ai":
            if "performance" in hypothesis.statement.lower():
                return "ml_evaluation"
            return "ml_training"
        elif domain == "mathematics":
            if "proof" in hypothesis.statement.lower():
                return "proof_verification"
            return "computational"
        elif domain == "computational_biology":
            if "structure" in hypothesis.statement.lower():
                return "structure_prediction"
            return "molecular_simulation"
        elif domain == "bioinformatics":
            return "bioinformatics_pipeline"
        elif domain == "materials_science":
            return "molecular_simulation"

        return "computational"

    async def _add_default_steps(
        self,
        experiment: Experiment,
        hypothesis: Hypothesis,
    ) -> None:
        """Add default experiment steps based on hypothesis."""
        # Setup step
        await self._experiment_designer.add_step(
            experiment,
            name="Setup Environment",
            description="Prepare experimental environment and dependencies",
            step_type="setup",
            order=0,
        )

        # Data preparation step
        await self._experiment_designer.add_step(
            experiment,
            name="Prepare Data",
            description="Prepare input data for experiment",
            step_type="data_preparation",
            order=1,
        )

        # Execution step
        await self._experiment_designer.add_step(
            experiment,
            name="Execute Experiment",
            description=f"Run experiment to test: {hypothesis.statement[:100]}",
            step_type="execution",
            order=2,
        )

        # Analysis step
        await self._experiment_designer.add_step(
            experiment,
            name="Analyze Results",
            description="Analyze experimental results",
            step_type="analysis",
            order=3,
        )

        # Validation step
        await self._experiment_designer.add_step(
            experiment,
            name="Validate Findings",
            description="Validate and verify findings",
            step_type="validation",
            order=4,
        )

    async def design_experiment(
        self,
        experiment_id: str,
        variables: list[dict[str, Any]] | None = None,
        steps: list[dict[str, Any]] | None = None,
        config: dict[str, Any] | None = None,
    ) -> Experiment:
        """Complete experiment design with variables, steps, and config."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")

        # Add variables
        if variables:
            for var_data in variables:
                await self._experiment_designer.add_variable(
                    experiment,
                    name=var_data.get("name", ""),
                    description=var_data.get("description", ""),
                    variable_type=var_data.get("variable_type", "independent"),
                    data_type=var_data.get("data_type", "continuous"),
                    unit=var_data.get("unit", ""),
                )

        # Add steps
        if steps:
            for i, step_data in enumerate(steps):
                await self._experiment_designer.add_step(
                    experiment,
                    name=step_data.get("name", f"Step {i+1}"),
                    description=step_data.get("description", ""),
                    step_type=step_data.get("step_type", "execution"),
                    order=step_data.get("order", i),
                    command=step_data.get("command", ""),
                    parameters=step_data.get("parameters", {}),
                )

        # Set config
        if config:
            await self._experiment_designer.set_config(
                experiment,
                parameters=config.get("parameters", {}),
                hyperparameters=config.get("hyperparameters", {}),
                random_seed=config.get("random_seed"),
                environment=config.get("environment", {}),
                dependencies=config.get("dependencies", []),
                data_sources=config.get("data_sources", []),
            )

        experiment.updated_at = datetime.utcnow()
        return experiment

    async def validate_experiment_design(
        self,
        experiment_id: str,
    ) -> dict[str, Any]:
        """Validate experiment design."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")

        return await self._experiment_designer.validate_design(experiment)

    async def clone_experiment(
        self,
        experiment_id: str,
        new_name: str | None = None,
        modifications: dict[str, Any] | None = None,
    ) -> Experiment:
        """Clone an existing experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")

        cloned = await self._experiment_designer.clone_experiment(
            experiment,
            new_name=new_name,
            modifications=modifications,
        )

        self._experiments[cloned.experiment_id] = cloned
        return cloned

    # ===========================================
    # EXPERIMENT PLAN MANAGEMENT
    # ===========================================

    async def create_plan(
        self,
        name: str,
        description: str,
        objective: str,
        domain: str,
        created_by: str = "system",
    ) -> ExperimentPlan:
        """Create a new experiment plan."""
        plan = ExperimentPlan(
            name=name,
            description=description,
            objective=objective,
            domain=domain,
            created_by=created_by,
        )

        self._plans[plan.plan_id] = plan
        return plan

    async def add_experiment_to_plan(
        self,
        plan_id: str,
        experiment_id: str,
        dependencies: list[str] | None = None,
    ) -> ExperimentPlan:
        """Add an experiment to a plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")

        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")

        plan.experiments.append(experiment)

        if dependencies:
            plan.dependencies[experiment_id] = dependencies

        plan.updated_at = datetime.utcnow()
        return plan

    async def estimate_plan_resources(
        self,
        plan_id: str,
    ) -> ResourceEstimate:
        """Estimate total resources for a plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")

        estimator = self._scheduler.resource_estimator
        estimate = await estimator.estimate_plan(plan)

        plan.total_resource_estimate = estimate
        return estimate

    async def get_plan(self, plan_id: str) -> ExperimentPlan | None:
        """Get an experiment plan."""
        return self._plans.get(plan_id)

    async def list_plans(
        self,
        domain: str | None = None,
        status: str | None = None,
    ) -> list[ExperimentPlan]:
        """List experiment plans."""
        plans = list(self._plans.values())

        if domain:
            plans = [p for p in plans if p.domain == domain]

        if status:
            plans = [p for p in plans if p.status == status]

        return plans

    # ===========================================
    # SCHEDULING AND EXECUTION
    # ===========================================

    async def schedule_experiment(
        self,
        experiment_id: str,
        priority: int | None = None,
        deadline: datetime | None = None,
    ) -> ScheduledExperiment:
        """Schedule an experiment for execution."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")

        # Update experiment status
        experiment.status = ExperimentStatus.QUEUED
        experiment.updated_at = datetime.utcnow()

        return await self._scheduler.schedule_experiment(
            experiment,
            priority=priority,
            deadline=deadline,
        )

    async def schedule_plan(self, plan_id: str) -> list[ScheduledExperiment]:
        """Schedule all experiments in a plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")

        # Update plan status
        plan.status = "scheduled"
        plan.updated_at = datetime.utcnow()

        # Update experiment statuses
        for exp in plan.experiments:
            exp.status = ExperimentStatus.QUEUED

        return await self._scheduler.schedule_plan(plan)

    async def start_experiment(
        self,
        experiment_id: str,
    ) -> tuple[Experiment, ScheduledExperiment | None]:
        """Start an experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")

        # Find scheduled experiment
        scheduled = None
        status = await self._scheduler.get_queue_status()

        for s in status.get("pending", []):
            if s.get("experiment_id") == experiment_id:
                scheduled = await self._scheduler.start_experiment(s.get("schedule_id"))
                break

        if scheduled:
            experiment.status = ExperimentStatus.RUNNING
            experiment.started_at = datetime.utcnow()
            experiment.updated_at = datetime.utcnow()

        return experiment, scheduled

    async def complete_experiment(
        self,
        experiment_id: str,
        results: dict[str, Any],
        success: bool = True,
    ) -> ExperimentResult:
        """Complete an experiment with results."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")

        # Update experiment
        experiment.status = ExperimentStatus.COMPLETED if success else ExperimentStatus.FAILED
        experiment.completed_at = datetime.utcnow()
        experiment.results = results
        experiment.progress = 1.0

        # Create result record
        result = ExperimentResult(
            experiment_id=experiment_id,
            metrics=results.get("metrics", {}),
            statistics=results.get("statistics", {}),
            confidence=results.get("confidence", 0.0),
            p_value=results.get("p_value"),
            effect_size=results.get("effect_size"),
            summary=results.get("summary", ""),
        )

        # Update hypothesis outcomes
        for hypothesis in experiment.hypotheses:
            outcome = results.get("hypothesis_outcomes", {}).get(hypothesis.hypothesis_id)
            if outcome == "supported":
                hypothesis.status = HypothesisStatus.SUPPORTED
            elif outcome == "refuted":
                hypothesis.status = HypothesisStatus.REFUTED
            else:
                hypothesis.status = HypothesisStatus.INCONCLUSIVE

            result.hypothesis_id = hypothesis.hypothesis_id
            result.outcome = outcome or "inconclusive"

        self._results[result.result_id] = result

        # Update scheduler
        queue_status = await self._scheduler.get_queue_status()
        for s in queue_status.get("running", []):
            if s.get("experiment_id") == experiment_id:
                await self._scheduler.complete_experiment(
                    s.get("schedule_id"),
                    success=success,
                )
                break

        return result

    async def pause_experiment(self, experiment_id: str) -> Experiment:
        """Pause a running experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")

        experiment.status = ExperimentStatus.PAUSED
        experiment.updated_at = datetime.utcnow()
        return experiment

    async def resume_experiment(self, experiment_id: str) -> Experiment:
        """Resume a paused experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")

        if experiment.status == ExperimentStatus.PAUSED:
            experiment.status = ExperimentStatus.RUNNING
            experiment.updated_at = datetime.utcnow()

        return experiment

    async def cancel_experiment(self, experiment_id: str) -> Experiment:
        """Cancel an experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")

        experiment.status = ExperimentStatus.CANCELLED
        experiment.updated_at = datetime.utcnow()

        # Cancel in scheduler
        queue_status = await self._scheduler.get_queue_status()
        for s in queue_status.get("pending", []) + queue_status.get("running", []):
            if s.get("experiment_id") == experiment_id:
                await self._scheduler.cancel_experiment(s.get("schedule_id"))
                break

        return experiment

    # ===========================================
    # CHECKPOINT MANAGEMENT
    # ===========================================

    async def create_checkpoint(
        self,
        experiment_id: str,
        step_id: str,
        state: dict[str, Any],
        metrics: dict[str, float] | None = None,
    ) -> Checkpoint:
        """Create a checkpoint for experiment state."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")

        checkpoint = Checkpoint(
            experiment_id=experiment_id,
            step_id=step_id,
            state=state,
            metrics=metrics or {},
            path=f"checkpoints/{experiment_id}/{step_id}/{datetime.utcnow().isoformat()}",
        )

        if experiment_id not in self._checkpoints:
            self._checkpoints[experiment_id] = []

        self._checkpoints[experiment_id].append(checkpoint)

        # Limit checkpoints
        max_checkpoints = self._settings.max_checkpoints
        if len(self._checkpoints[experiment_id]) > max_checkpoints:
            self._checkpoints[experiment_id] = self._checkpoints[experiment_id][-max_checkpoints:]

        return checkpoint

    async def get_checkpoints(self, experiment_id: str) -> list[Checkpoint]:
        """Get checkpoints for an experiment."""
        return self._checkpoints.get(experiment_id, [])

    async def restore_from_checkpoint(
        self,
        experiment_id: str,
        checkpoint_id: str,
    ) -> dict[str, Any] | None:
        """Restore experiment state from checkpoint."""
        checkpoints = self._checkpoints.get(experiment_id, [])

        for checkpoint in checkpoints:
            if checkpoint.checkpoint_id == checkpoint_id:
                return checkpoint.state

        return None

    # ===========================================
    # QUERY AND RETRIEVAL
    # ===========================================

    async def get_experiment(self, experiment_id: str) -> Experiment | None:
        """Get an experiment by ID."""
        return self._experiments.get(experiment_id)

    async def list_experiments(
        self,
        domain: str | None = None,
        status: ExperimentStatus | None = None,
        experiment_type: str | None = None,
        created_by: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Experiment]:
        """List experiments with filters."""
        experiments = list(self._experiments.values())

        if domain:
            experiments = [e for e in experiments if e.domain == domain]

        if status:
            experiments = [e for e in experiments if e.status == status]

        if experiment_type:
            experiments = [e for e in experiments if e.experiment_type == experiment_type]

        if created_by:
            experiments = [e for e in experiments if e.created_by == created_by]

        # Sort by created date descending
        experiments.sort(key=lambda e: e.created_at, reverse=True)

        return experiments[offset : offset + limit]

    async def get_result(self, result_id: str) -> ExperimentResult | None:
        """Get an experiment result by ID."""
        return self._results.get(result_id)

    async def get_results_for_experiment(
        self,
        experiment_id: str,
    ) -> list[ExperimentResult]:
        """Get all results for an experiment."""
        return [r for r in self._results.values() if r.experiment_id == experiment_id]

    async def search_experiments(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Experiment]:
        """Search experiments by name or description."""
        query_lower = query.lower()
        results = []

        for experiment in self._experiments.values():
            if (
                query_lower in experiment.name.lower()
                or query_lower in experiment.description.lower()
            ):
                results.append(experiment)

        return results[:limit]

    # ===========================================
    # STATISTICS
    # ===========================================

    async def get_stats(self) -> ExperimentStats:
        """Get experiment statistics."""
        experiments = list(self._experiments.values())

        stats = ExperimentStats(
            total_experiments=len(experiments),
            total_plans=len(self._plans),
        )

        # Count by status
        for exp in experiments:
            if exp.status == ExperimentStatus.DRAFT:
                stats.draft_count += 1
            elif exp.status == ExperimentStatus.PLANNED:
                stats.planned_count += 1
            elif exp.status == ExperimentStatus.QUEUED:
                stats.queued_count += 1
            elif exp.status == ExperimentStatus.RUNNING:
                stats.running_count += 1
            elif exp.status == ExperimentStatus.COMPLETED:
                stats.completed_count += 1
            elif exp.status == ExperimentStatus.FAILED:
                stats.failed_count += 1

            # Resource usage from estimates
            if exp.resource_estimate:
                stats.total_gpu_hours_used += exp.resource_estimate.gpu_hours
                stats.total_cpu_hours_used += exp.resource_estimate.cpu_hours

            # Hypothesis counts
            for h in exp.hypotheses:
                stats.total_hypotheses += 1
                if h.status == HypothesisStatus.SUPPORTED:
                    stats.supported_hypotheses += 1
                elif h.status == HypothesisStatus.REFUTED:
                    stats.refuted_hypotheses += 1

        # Average duration
        completed = [e for e in experiments if e.completed_at and e.started_at]
        if completed:
            durations = [
                (e.completed_at - e.started_at).total_seconds() / 3600
                for e in completed
            ]
            stats.avg_experiment_duration = sum(durations) / len(durations)

        return stats

    async def get_queue_status(self) -> dict[str, Any]:
        """Get scheduler queue status."""
        return await self._scheduler.get_queue_status()

    async def get_resource_status(self) -> dict[str, Any]:
        """Get resource pool status."""
        return await self._scheduler.get_resource_status()


# Singleton instance
_service: ExperimentPlanningService | None = None


def get_experiment_service() -> ExperimentPlanningService:
    """Get or create experiment planning service singleton."""
    global _service
    if _service is None:
        _service = ExperimentPlanningService()
    return _service


__all__ = [
    "ExperimentStats",
    "ExperimentPlanningService",
    "get_experiment_service",
]
