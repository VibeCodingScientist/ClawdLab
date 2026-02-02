"""Configuration for Experiment Planning."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class ExperimentSettings(BaseSettings):
    """Settings for experiment planning."""

    model_config = {"env_prefix": "EXPERIMENT_", "case_sensitive": False}

    # Resource Limits
    max_gpu_hours: int = Field(
        default=1000,
        description="Maximum GPU hours per experiment",
    )
    max_cpu_hours: int = Field(
        default=10000,
        description="Maximum CPU hours per experiment",
    )
    max_memory_gb: int = Field(
        default=256,
        description="Maximum memory in GB",
    )
    max_storage_gb: int = Field(
        default=1000,
        description="Maximum storage in GB",
    )

    # Scheduling Settings
    default_priority: int = Field(
        default=5,
        description="Default experiment priority (1-10)",
    )
    max_concurrent_experiments: int = Field(
        default=10,
        description="Maximum concurrent experiments",
    )
    scheduling_interval_seconds: int = Field(
        default=60,
        description="Scheduling check interval",
    )
    experiment_timeout_hours: int = Field(
        default=168,  # 1 week
        description="Maximum experiment duration",
    )

    # Hypothesis Settings
    max_hypotheses_per_experiment: int = Field(
        default=10,
        description="Maximum hypotheses per experiment",
    )
    hypothesis_confidence_threshold: float = Field(
        default=0.6,
        description="Minimum confidence for hypothesis",
    )

    # Reproducibility Settings
    require_random_seed: bool = Field(
        default=True,
        description="Require random seed for reproducibility",
    )
    checkpoint_interval_minutes: int = Field(
        default=30,
        description="Checkpoint save interval",
    )
    max_checkpoints: int = Field(
        default=10,
        description="Maximum checkpoints to keep",
    )

    # Result Settings
    result_retention_days: int = Field(
        default=365,
        description="Days to retain experiment results",
    )
    auto_archive_completed: bool = Field(
        default=True,
        description="Auto-archive completed experiments",
    )


@lru_cache
def get_settings() -> ExperimentSettings:
    """Get cached experiment settings."""
    return ExperimentSettings()


# Experiment Types
EXPERIMENT_TYPES = {
    "computational": {
        "name": "Computational Experiment",
        "description": "Pure computational analysis or simulation",
        "domains": ["mathematics", "ml_ai", "materials_science"],
        "typical_resources": {"gpu_hours": 100, "cpu_hours": 500},
    },
    "ml_training": {
        "name": "ML Model Training",
        "description": "Training machine learning models",
        "domains": ["ml_ai"],
        "typical_resources": {"gpu_hours": 500, "cpu_hours": 100},
    },
    "ml_evaluation": {
        "name": "ML Model Evaluation",
        "description": "Evaluating trained models on benchmarks",
        "domains": ["ml_ai"],
        "typical_resources": {"gpu_hours": 50, "cpu_hours": 100},
    },
    "proof_verification": {
        "name": "Proof Verification",
        "description": "Verifying mathematical proofs",
        "domains": ["mathematics"],
        "typical_resources": {"gpu_hours": 0, "cpu_hours": 200},
    },
    "structure_prediction": {
        "name": "Structure Prediction",
        "description": "Predicting molecular/crystal structures",
        "domains": ["computational_biology", "materials_science"],
        "typical_resources": {"gpu_hours": 200, "cpu_hours": 100},
    },
    "molecular_simulation": {
        "name": "Molecular Simulation",
        "description": "Molecular dynamics or Monte Carlo simulations",
        "domains": ["computational_biology", "materials_science"],
        "typical_resources": {"gpu_hours": 300, "cpu_hours": 500},
    },
    "bioinformatics_pipeline": {
        "name": "Bioinformatics Pipeline",
        "description": "Running bioinformatics analysis pipelines",
        "domains": ["bioinformatics"],
        "typical_resources": {"gpu_hours": 50, "cpu_hours": 1000},
    },
    "statistical_analysis": {
        "name": "Statistical Analysis",
        "description": "Statistical analysis of data",
        "domains": ["bioinformatics", "ml_ai"],
        "typical_resources": {"gpu_hours": 0, "cpu_hours": 100},
    },
    "benchmark_reproduction": {
        "name": "Benchmark Reproduction",
        "description": "Reproducing published benchmark results",
        "domains": ["ml_ai", "computational_biology"],
        "typical_resources": {"gpu_hours": 200, "cpu_hours": 200},
    },
}

# Experiment Status
EXPERIMENT_STATUSES = [
    "draft",
    "planned",
    "queued",
    "running",
    "paused",
    "completed",
    "failed",
    "cancelled",
    "archived",
]

# Hypothesis Types
HYPOTHESIS_TYPES = {
    "causal": {
        "name": "Causal Hypothesis",
        "description": "Claims a causal relationship",
        "template": "If {condition}, then {outcome} because {mechanism}",
    },
    "correlational": {
        "name": "Correlational Hypothesis",
        "description": "Claims a correlation between variables",
        "template": "{variable_a} is correlated with {variable_b}",
    },
    "comparative": {
        "name": "Comparative Hypothesis",
        "description": "Compares two or more conditions",
        "template": "{condition_a} performs better than {condition_b} on {metric}",
    },
    "existence": {
        "name": "Existence Hypothesis",
        "description": "Claims something exists or is possible",
        "template": "There exists {entity} with property {property}",
    },
    "null": {
        "name": "Null Hypothesis",
        "description": "No significant effect or difference",
        "template": "There is no significant difference between {a} and {b}",
    },
}

# Resource Types
RESOURCE_TYPES = {
    "gpu": {
        "name": "GPU",
        "unit": "hours",
        "cost_per_unit": 1.0,
    },
    "cpu": {
        "name": "CPU",
        "unit": "hours",
        "cost_per_unit": 0.1,
    },
    "memory": {
        "name": "Memory",
        "unit": "GB-hours",
        "cost_per_unit": 0.01,
    },
    "storage": {
        "name": "Storage",
        "unit": "GB",
        "cost_per_unit": 0.05,
    },
    "network": {
        "name": "Network",
        "unit": "GB",
        "cost_per_unit": 0.02,
    },
}

# Variable Types
VARIABLE_TYPES = {
    "independent": "Manipulated variable",
    "dependent": "Measured outcome variable",
    "control": "Held constant variable",
    "confounding": "Potential confounding variable",
    "covariate": "Additional measured variable",
}

# Experiment Phases
EXPERIMENT_PHASES = [
    "design",
    "setup",
    "data_preparation",
    "execution",
    "analysis",
    "validation",
    "reporting",
]

# Priority Levels
PRIORITY_LEVELS = {
    1: {"name": "Critical", "description": "Highest priority, immediate execution"},
    2: {"name": "High", "description": "High priority"},
    3: {"name": "Above Normal", "description": "Above normal priority"},
    5: {"name": "Normal", "description": "Normal priority"},
    7: {"name": "Below Normal", "description": "Below normal priority"},
    9: {"name": "Low", "description": "Low priority, background execution"},
    10: {"name": "Idle", "description": "Only when resources are free"},
}
