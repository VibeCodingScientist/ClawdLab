"""Experiment Planning Module.

This module provides comprehensive experiment planning capabilities:
- Hypothesis generation and validation
- Experiment design with variables, steps, and configuration
- Resource estimation and cost calculation
- Experiment scheduling and execution management
- Checkpoint and result tracking
- Experiment plans for coordinated research

The experiment planning layer enables agents to design, execute,
and track scientific experiments with proper resource management.
"""

from platform.experiments.base import (
    # Enums
    ExperimentStatus,
    HypothesisStatus,
    ResourceType,
    VariableType,
    # Hypothesis classes
    Hypothesis,
    # Variable classes
    Variable,
    # Resource classes
    ResourceEstimate,
    ResourceRequirement,
    # Experiment classes
    Experiment,
    ExperimentConfig,
    ExperimentStep,
    # Plan classes
    ExperimentPlan,
    # Result classes
    Checkpoint,
    ExperimentResult,
)
from platform.experiments.config import (
    EXPERIMENT_PHASES,
    EXPERIMENT_STATUSES,
    EXPERIMENT_TYPES,
    HYPOTHESIS_TYPES,
    PRIORITY_LEVELS,
    RESOURCE_TYPES,
    VARIABLE_TYPES,
    ExperimentSettings,
    get_settings,
)
from platform.experiments.designer import (
    ExperimentDesigner,
    get_designer,
)
from platform.experiments.hypothesis import (
    HypothesisGenerator,
    get_hypothesis_generator,
)
from platform.experiments.scheduler import (
    ExperimentScheduler,
    ResourceEstimator,
    ResourcePool,
    ScheduledExperiment,
    ScheduleStatus,
    get_scheduler,
)
from platform.experiments.service import (
    ExperimentPlanningService,
    ExperimentStats,
    get_experiment_service,
)

__all__ = [
    # Config
    "get_settings",
    "ExperimentSettings",
    "EXPERIMENT_TYPES",
    "EXPERIMENT_STATUSES",
    "EXPERIMENT_PHASES",
    "HYPOTHESIS_TYPES",
    "RESOURCE_TYPES",
    "VARIABLE_TYPES",
    "PRIORITY_LEVELS",
    # Enums
    "ExperimentStatus",
    "HypothesisStatus",
    "VariableType",
    "ResourceType",
    "ScheduleStatus",
    # Hypothesis classes
    "Hypothesis",
    # Variable classes
    "Variable",
    # Resource classes
    "ResourceRequirement",
    "ResourceEstimate",
    "ResourcePool",
    # Experiment classes
    "ExperimentConfig",
    "ExperimentStep",
    "Experiment",
    # Plan classes
    "ExperimentPlan",
    # Result classes
    "ExperimentResult",
    "Checkpoint",
    # Scheduling classes
    "ScheduledExperiment",
    # Generators and designers
    "HypothesisGenerator",
    "get_hypothesis_generator",
    "ExperimentDesigner",
    "get_designer",
    # Scheduler
    "ResourceEstimator",
    "ExperimentScheduler",
    "get_scheduler",
    # Main service
    "ExperimentPlanningService",
    "ExperimentStats",
    "get_experiment_service",
]
