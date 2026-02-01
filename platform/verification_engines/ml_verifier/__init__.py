"""ML/AI Research Verification Engine.

This module provides verification of ML experiments through:
- Code repository cloning and verification
- Environment reproducibility (Docker, Nix)
- Dataset fetching and validation
- Experiment execution on Kubernetes
- Metric comparison with tolerance checking
- Integration with lm-evaluation-harness and HELM
"""

from platform.verification_engines.ml_verifier.base import (
    BaseEnvironmentBuilder,
    BaseJobRunner,
    BaseMLVerifier,
    CloneResult,
    DataFetchResult,
    EnvironmentResult,
    ExecutionResult,
    MetricComparison,
    MetricComparisonResult,
    MetricValue,
    MLVerificationResult,
    ResourceUsage,
    StageResult,
    VerificationStage,
    VerificationStatus,
)
from platform.verification_engines.ml_verifier.config import (
    EXPERIMENT_TYPES,
    GPU_CONFIGS,
    ML_FRAMEWORKS,
    get_settings,
)

__all__ = [
    # Config
    "get_settings",
    "EXPERIMENT_TYPES",
    "ML_FRAMEWORKS",
    "GPU_CONFIGS",
    # Base classes
    "BaseMLVerifier",
    "BaseEnvironmentBuilder",
    "BaseJobRunner",
    # Data classes
    "VerificationStage",
    "VerificationStatus",
    "StageResult",
    "CloneResult",
    "EnvironmentResult",
    "DataFetchResult",
    "ExecutionResult",
    "MetricValue",
    "MetricComparison",
    "MetricComparisonResult",
    "ResourceUsage",
    "MLVerificationResult",
]
