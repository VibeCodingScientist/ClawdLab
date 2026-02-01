"""Experiment designer for creating and configuring experiments."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from platform.experiments.base import (
    Experiment,
    ExperimentConfig,
    ExperimentStatus,
    ExperimentStep,
    Hypothesis,
    ResourceRequirement,
    ResourceType,
    Variable,
    VariableType,
)
from platform.experiments.config import EXPERIMENT_TYPES, get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class ExperimentTemplate:
    """Template for creating experiments."""

    template_id: str
    name: str
    description: str
    experiment_type: str
    domain: str
    default_variables: list[dict[str, Any]] = field(default_factory=list)
    default_steps: list[dict[str, Any]] = field(default_factory=list)
    default_config: dict[str, Any] = field(default_factory=dict)
    resource_profile: dict[str, float] = field(default_factory=dict)


# Pre-defined templates
TEMPLATES = {
    "ml_benchmark": ExperimentTemplate(
        template_id="ml_benchmark",
        name="ML Benchmark Evaluation",
        description="Evaluate ML models on standard benchmarks",
        experiment_type="ml_evaluation",
        domain="ml_ai",
        default_variables=[
            {"name": "model", "type": "independent", "data_type": "categorical"},
            {"name": "dataset", "type": "independent", "data_type": "categorical"},
            {"name": "accuracy", "type": "dependent", "data_type": "continuous"},
            {"name": "f1_score", "type": "dependent", "data_type": "continuous"},
        ],
        default_steps=[
            {"name": "Setup Environment", "step_type": "setup", "order": 1},
            {"name": "Load Data", "step_type": "setup", "order": 2},
            {"name": "Run Evaluation", "step_type": "execution", "order": 3},
            {"name": "Compute Metrics", "step_type": "analysis", "order": 4},
            {"name": "Generate Report", "step_type": "reporting", "order": 5},
        ],
        resource_profile={"gpu_hours": 50, "cpu_hours": 100},
    ),
    "ml_training": ExperimentTemplate(
        template_id="ml_training",
        name="ML Model Training",
        description="Train ML models with hyperparameter tuning",
        experiment_type="ml_training",
        domain="ml_ai",
        default_variables=[
            {"name": "learning_rate", "type": "independent", "data_type": "continuous"},
            {"name": "batch_size", "type": "independent", "data_type": "discrete"},
            {"name": "epochs", "type": "independent", "data_type": "discrete"},
            {"name": "train_loss", "type": "dependent", "data_type": "continuous"},
            {"name": "val_loss", "type": "dependent", "data_type": "continuous"},
        ],
        default_steps=[
            {"name": "Prepare Data", "step_type": "setup", "order": 1},
            {"name": "Initialize Model", "step_type": "setup", "order": 2},
            {"name": "Training Loop", "step_type": "execution", "order": 3},
            {"name": "Validation", "step_type": "execution", "order": 4},
            {"name": "Save Checkpoint", "step_type": "execution", "order": 5},
            {"name": "Evaluate", "step_type": "analysis", "order": 6},
        ],
        resource_profile={"gpu_hours": 200, "cpu_hours": 50},
    ),
    "structure_prediction": ExperimentTemplate(
        template_id="structure_prediction",
        name="Structure Prediction",
        description="Predict protein or crystal structures",
        experiment_type="structure_prediction",
        domain="computational_biology",
        default_variables=[
            {"name": "sequence", "type": "independent", "data_type": "categorical"},
            {"name": "model_type", "type": "independent", "data_type": "categorical"},
            {"name": "plddt_score", "type": "dependent", "data_type": "continuous"},
            {"name": "rmsd", "type": "dependent", "data_type": "continuous"},
        ],
        default_steps=[
            {"name": "Parse Input", "step_type": "setup", "order": 1},
            {"name": "Run Prediction", "step_type": "execution", "order": 2},
            {"name": "Refine Structure", "step_type": "execution", "order": 3},
            {"name": "Validate", "step_type": "validation", "order": 4},
            {"name": "Analyze Results", "step_type": "analysis", "order": 5},
        ],
        resource_profile={"gpu_hours": 100, "cpu_hours": 50},
    ),
    "statistical_analysis": ExperimentTemplate(
        template_id="statistical_analysis",
        name="Statistical Analysis",
        description="Perform statistical analysis on data",
        experiment_type="statistical_analysis",
        domain="bioinformatics",
        default_variables=[
            {"name": "treatment_group", "type": "independent", "data_type": "categorical"},
            {"name": "control_group", "type": "control", "data_type": "categorical"},
            {"name": "p_value", "type": "dependent", "data_type": "continuous"},
            {"name": "effect_size", "type": "dependent", "data_type": "continuous"},
        ],
        default_steps=[
            {"name": "Load Data", "step_type": "setup", "order": 1},
            {"name": "Preprocess", "step_type": "setup", "order": 2},
            {"name": "Run Analysis", "step_type": "execution", "order": 3},
            {"name": "Multiple Testing Correction", "step_type": "analysis", "order": 4},
            {"name": "Generate Plots", "step_type": "reporting", "order": 5},
        ],
        resource_profile={"gpu_hours": 0, "cpu_hours": 100},
    ),
}


class ExperimentDesigner:
    """
    Designer for creating and configuring experiments.

    Creates experiment configurations, defines variables,
    controls, and expected outcomes.
    """

    def __init__(self, mcp_tool_provider: Any | None = None):
        """
        Initialize experiment designer.

        Args:
            mcp_tool_provider: Optional MCP tool provider
        """
        self._mcp_provider = mcp_tool_provider
        self._experiments: dict[str, Experiment] = {}
        self._templates = TEMPLATES

    async def create_experiment(
        self,
        name: str,
        description: str,
        experiment_type: str,
        domain: str,
        hypotheses: list[Hypothesis] | None = None,
        template_id: str | None = None,
        created_by: str = "",
    ) -> Experiment:
        """
        Create a new experiment.

        Args:
            name: Experiment name
            description: Experiment description
            experiment_type: Type of experiment
            domain: Research domain
            hypotheses: Hypotheses to test
            template_id: Optional template to use
            created_by: Creator ID

        Returns:
            Created experiment
        """
        # Start from template if provided
        if template_id and template_id in self._templates:
            template = self._templates[template_id]
            experiment = await self._create_from_template(
                template, name, description, hypotheses, created_by
            )
        else:
            experiment = Experiment(
                name=name,
                description=description,
                experiment_type=experiment_type,
                domain=domain,
                hypotheses=hypotheses or [],
                created_by=created_by,
            )

        # Add default config
        if not experiment.config.random_seed and settings.require_random_seed:
            experiment.config.random_seed = self._generate_random_seed()

        self._experiments[experiment.experiment_id] = experiment

        logger.info(
            "experiment_created",
            experiment_id=experiment.experiment_id,
            name=name,
            type=experiment_type,
        )

        return experiment

    async def _create_from_template(
        self,
        template: ExperimentTemplate,
        name: str,
        description: str,
        hypotheses: list[Hypothesis] | None,
        created_by: str,
    ) -> Experiment:
        """Create experiment from template."""
        # Create variables
        variables = []
        for var_def in template.default_variables:
            variable = Variable(
                name=var_def["name"],
                variable_type=VariableType(var_def.get("type", "independent")),
                data_type=var_def.get("data_type", "continuous"),
            )
            variables.append(variable)

        # Create steps
        steps = []
        for step_def in template.default_steps:
            step = ExperimentStep(
                name=step_def["name"],
                step_type=step_def.get("step_type", "execution"),
                order=step_def.get("order", 0),
            )
            steps.append(step)

        # Create resource requirements
        resources = []
        if template.resource_profile.get("gpu_hours", 0) > 0:
            resources.append(
                ResourceRequirement(
                    resource_type=ResourceType.GPU,
                    amount=template.resource_profile["gpu_hours"],
                    unit="hours",
                )
            )
        if template.resource_profile.get("cpu_hours", 0) > 0:
            resources.append(
                ResourceRequirement(
                    resource_type=ResourceType.CPU,
                    amount=template.resource_profile["cpu_hours"],
                    unit="hours",
                )
            )

        # Create config
        config = ExperimentConfig(
            parameters=template.default_config.copy(),
        )

        return Experiment(
            name=name,
            description=description,
            experiment_type=template.experiment_type,
            domain=template.domain,
            hypotheses=hypotheses or [],
            variables=variables,
            steps=steps,
            resource_requirements=resources,
            config=config,
            created_by=created_by,
            metadata={"template_id": template.template_id},
        )

    async def add_variable(
        self,
        experiment_id: str,
        name: str,
        variable_type: VariableType,
        data_type: str = "continuous",
        unit: str = "",
        min_value: float | None = None,
        max_value: float | None = None,
        possible_values: list[Any] | None = None,
    ) -> Variable | None:
        """
        Add a variable to an experiment.

        Args:
            experiment_id: Experiment ID
            name: Variable name
            variable_type: Type of variable
            data_type: Data type
            unit: Unit of measurement
            min_value: Minimum value
            max_value: Maximum value
            possible_values: Possible values for categorical

        Returns:
            Created variable or None
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None

        variable = Variable(
            name=name,
            variable_type=variable_type,
            data_type=data_type,
            unit=unit,
            min_value=min_value,
            max_value=max_value,
            possible_values=possible_values or [],
        )

        experiment.variables.append(variable)
        experiment.updated_at = datetime.utcnow()

        return variable

    async def add_step(
        self,
        experiment_id: str,
        name: str,
        step_type: str,
        command: str = "",
        parameters: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
    ) -> ExperimentStep | None:
        """
        Add a step to an experiment.

        Args:
            experiment_id: Experiment ID
            name: Step name
            step_type: Type of step
            command: Command to execute
            parameters: Step parameters
            dependencies: Step dependencies

        Returns:
            Created step or None
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None

        # Determine order
        order = len(experiment.steps) + 1

        step = ExperimentStep(
            name=name,
            step_type=step_type,
            order=order,
            command=command,
            parameters=parameters or {},
            dependencies=dependencies or [],
        )

        experiment.steps.append(step)
        experiment.updated_at = datetime.utcnow()

        return step

    async def set_config(
        self,
        experiment_id: str,
        parameters: dict[str, Any] | None = None,
        hyperparameters: dict[str, Any] | None = None,
        random_seed: int | None = None,
        environment: dict[str, str] | None = None,
        data_sources: list[str] | None = None,
    ) -> ExperimentConfig | None:
        """
        Set experiment configuration.

        Args:
            experiment_id: Experiment ID
            parameters: General parameters
            hyperparameters: Hyperparameters
            random_seed: Random seed
            environment: Environment variables
            data_sources: Data source paths/URIs

        Returns:
            Updated config or None
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None

        if parameters:
            experiment.config.parameters.update(parameters)
        if hyperparameters:
            experiment.config.hyperparameters.update(hyperparameters)
        if random_seed is not None:
            experiment.config.random_seed = random_seed
        if environment:
            experiment.config.environment.update(environment)
        if data_sources:
            experiment.config.data_sources.extend(data_sources)

        experiment.updated_at = datetime.utcnow()

        return experiment.config

    async def add_resource_requirement(
        self,
        experiment_id: str,
        resource_type: ResourceType,
        amount: float,
        unit: str = "hours",
        priority: str = "required",
    ) -> ResourceRequirement | None:
        """
        Add resource requirement to experiment.

        Args:
            experiment_id: Experiment ID
            resource_type: Type of resource
            amount: Amount needed
            unit: Unit of measurement
            priority: Requirement priority

        Returns:
            Created requirement or None
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None

        requirement = ResourceRequirement(
            resource_type=resource_type,
            amount=amount,
            unit=unit,
            priority=priority,
        )

        experiment.resource_requirements.append(requirement)
        experiment.updated_at = datetime.utcnow()

        return requirement

    async def validate_design(
        self,
        experiment_id: str,
    ) -> dict[str, Any]:
        """
        Validate experiment design.

        Args:
            experiment_id: Experiment ID

        Returns:
            Validation result with issues and suggestions
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return {"valid": False, "issues": ["Experiment not found"]}

        issues = []
        warnings = []
        suggestions = []

        # Check hypotheses
        if not experiment.hypotheses:
            warnings.append("No hypotheses defined")
            suggestions.append("Add at least one hypothesis to test")

        # Check variables
        has_independent = any(
            v.variable_type == VariableType.INDEPENDENT for v in experiment.variables
        )
        has_dependent = any(
            v.variable_type == VariableType.DEPENDENT for v in experiment.variables
        )

        if not has_independent:
            issues.append("No independent variables defined")
        if not has_dependent:
            issues.append("No dependent variables defined")

        # Check steps
        if not experiment.steps:
            issues.append("No experiment steps defined")

        # Check step dependencies
        step_ids = {s.step_id for s in experiment.steps}
        for step in experiment.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    issues.append(f"Step {step.name} has invalid dependency: {dep}")

        # Check config
        if settings.require_random_seed and not experiment.config.random_seed:
            issues.append("Random seed required but not set")

        # Check resources
        if not experiment.resource_requirements:
            warnings.append("No resource requirements specified")
            suggestions.append("Add resource estimates for better scheduling")

        is_valid = len(issues) == 0

        return {
            "valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "suggestions": suggestions,
            "completeness": self._calculate_completeness(experiment),
        }

    async def clone_experiment(
        self,
        experiment_id: str,
        new_name: str,
        modifications: dict[str, Any] | None = None,
    ) -> Experiment | None:
        """
        Clone an experiment with optional modifications.

        Args:
            experiment_id: Experiment to clone
            new_name: Name for cloned experiment
            modifications: Modifications to apply

        Returns:
            Cloned experiment or None
        """
        original = self._experiments.get(experiment_id)
        if not original:
            return None

        # Deep copy
        cloned = Experiment(
            name=new_name,
            description=original.description,
            experiment_type=original.experiment_type,
            domain=original.domain,
            hypotheses=[
                Hypothesis(
                    title=h.title,
                    statement=h.statement,
                    hypothesis_type=h.hypothesis_type,
                    variables=h.variables.copy(),
                    predictions=h.predictions.copy(),
                    assumptions=h.assumptions.copy(),
                )
                for h in original.hypotheses
            ],
            variables=[
                Variable(
                    name=v.name,
                    variable_type=v.variable_type,
                    data_type=v.data_type,
                    unit=v.unit,
                    min_value=v.min_value,
                    max_value=v.max_value,
                    possible_values=v.possible_values.copy(),
                )
                for v in original.variables
            ],
            config=ExperimentConfig(
                parameters=original.config.parameters.copy(),
                hyperparameters=original.config.hyperparameters.copy(),
                random_seed=self._generate_random_seed(),  # New seed
                environment=original.config.environment.copy(),
                dependencies=original.config.dependencies.copy(),
                data_sources=original.config.data_sources.copy(),
            ),
            steps=[
                ExperimentStep(
                    name=s.name,
                    step_type=s.step_type,
                    order=s.order,
                    command=s.command,
                    parameters=s.parameters.copy(),
                )
                for s in original.steps
            ],
            resource_requirements=[
                ResourceRequirement(
                    resource_type=r.resource_type,
                    amount=r.amount,
                    unit=r.unit,
                    priority=r.priority,
                )
                for r in original.resource_requirements
            ],
            parent_experiment_id=experiment_id,
            metadata={**original.metadata, "cloned_from": experiment_id},
        )

        # Apply modifications
        if modifications:
            if "parameters" in modifications:
                cloned.config.parameters.update(modifications["parameters"])
            if "hyperparameters" in modifications:
                cloned.config.hyperparameters.update(modifications["hyperparameters"])

        self._experiments[cloned.experiment_id] = cloned

        logger.info(
            "experiment_cloned",
            original_id=experiment_id,
            cloned_id=cloned.experiment_id,
        )

        return cloned

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        """Get experiment by ID."""
        return self._experiments.get(experiment_id)

    def list_experiments(
        self,
        status: ExperimentStatus | None = None,
        domain: str | None = None,
        experiment_type: str | None = None,
    ) -> list[Experiment]:
        """List experiments with optional filtering."""
        experiments = list(self._experiments.values())

        if status:
            experiments = [e for e in experiments if e.status == status]
        if domain:
            experiments = [e for e in experiments if e.domain == domain]
        if experiment_type:
            experiments = [e for e in experiments if e.experiment_type == experiment_type]

        return sorted(experiments, key=lambda e: e.created_at, reverse=True)

    def get_templates(self) -> list[ExperimentTemplate]:
        """Get available experiment templates."""
        return list(self._templates.values())

    def _generate_random_seed(self) -> int:
        """Generate a random seed."""
        import random
        return random.randint(0, 2**31 - 1)

    def _calculate_completeness(self, experiment: Experiment) -> float:
        """Calculate experiment design completeness."""
        checks = [
            bool(experiment.name),
            bool(experiment.description),
            bool(experiment.hypotheses),
            any(v.variable_type == VariableType.INDEPENDENT for v in experiment.variables),
            any(v.variable_type == VariableType.DEPENDENT for v in experiment.variables),
            bool(experiment.steps),
            bool(experiment.config.random_seed) if settings.require_random_seed else True,
            bool(experiment.resource_requirements),
        ]

        return sum(checks) / len(checks)


# Singleton instance
_experiment_designer: ExperimentDesigner | None = None


def get_experiment_designer(
    mcp_tool_provider: Any | None = None,
) -> ExperimentDesigner:
    """Get singleton ExperimentDesigner instance."""
    global _experiment_designer
    if _experiment_designer is None:
        _experiment_designer = ExperimentDesigner(mcp_tool_provider)
    return _experiment_designer
