"""Base classes and data structures for ML verification."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class VerificationStage(Enum):
    """Stages of ML verification pipeline."""

    CODE_CLONE = "code_clone"
    ENVIRONMENT_BUILD = "environment_build"
    DATA_FETCH = "data_fetch"
    EXECUTION = "execution"
    METRIC_COMPARISON = "metric_comparison"


class VerificationStatus(Enum):
    """Status of ML verification."""

    VERIFIED = "verified"
    REFUTED = "refuted"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class StageResult:
    """Result of a single verification stage."""

    stage: VerificationStage
    passed: bool
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


@dataclass
class CloneResult(StageResult):
    """Result of repository cloning."""

    repo_url: str = ""
    commit_hash: str = ""
    branch: str = ""
    repo_size_mb: float = 0.0
    files_count: int = 0

    def __post_init__(self):
        self.stage = VerificationStage.CODE_CLONE
        self.details = {
            "repo_url": self.repo_url,
            "commit_hash": self.commit_hash,
            "branch": self.branch,
            "repo_size_mb": self.repo_size_mb,
            "files_count": self.files_count,
        }


@dataclass
class EnvironmentResult(StageResult):
    """Result of environment build."""

    environment_type: str = ""  # "docker" or "nix"
    image_hash: str = ""
    build_time_seconds: float = 0.0
    dependencies_installed: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.stage = VerificationStage.ENVIRONMENT_BUILD
        self.details = {
            "environment_type": self.environment_type,
            "image_hash": self.image_hash,
            "build_time_seconds": self.build_time_seconds,
            "dependencies_count": len(self.dependencies_installed),
        }


@dataclass
class DataFetchResult(StageResult):
    """Result of dataset fetching."""

    datasets_fetched: list[str] = field(default_factory=list)
    total_size_gb: float = 0.0
    checksums_valid: bool = False

    def __post_init__(self):
        self.stage = VerificationStage.DATA_FETCH
        self.details = {
            "datasets_fetched": self.datasets_fetched,
            "total_size_gb": self.total_size_gb,
            "checksums_valid": self.checksums_valid,
        }


@dataclass
class ExecutionResult(StageResult):
    """Result of experiment execution."""

    runtime_seconds: float = 0.0
    exit_code: int = 0
    stdout_tail: str = ""
    stderr_tail: str = ""
    gpu_hours: float = 0.0
    peak_memory_gb: float = 0.0
    output_files: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.stage = VerificationStage.EXECUTION
        self.details = {
            "runtime_seconds": self.runtime_seconds,
            "exit_code": self.exit_code,
            "gpu_hours": self.gpu_hours,
            "peak_memory_gb": self.peak_memory_gb,
            "output_files_count": len(self.output_files),
        }


@dataclass
class MetricValue:
    """A single metric value with uncertainty."""

    name: str
    value: float
    std_dev: float | None = None
    confidence_interval: tuple[float, float] | None = None
    sample_size: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "std_dev": self.std_dev,
            "confidence_interval": list(self.confidence_interval)
            if self.confidence_interval
            else None,
            "sample_size": self.sample_size,
        }


@dataclass
class MetricComparison:
    """Comparison between claimed and reproduced metrics."""

    metric_name: str
    claimed_value: float
    reproduced_value: float
    deviation: float
    deviation_percent: float
    within_tolerance: bool
    tolerance_percent: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "claimed": self.claimed_value,
            "reproduced": self.reproduced_value,
            "deviation": self.deviation,
            "deviation_percent": self.deviation_percent,
            "within_tolerance": self.within_tolerance,
            "tolerance_percent": self.tolerance_percent,
        }


@dataclass
class MetricComparisonResult(StageResult):
    """Result of metric comparison."""

    comparisons: list[MetricComparison] = field(default_factory=list)
    all_within_tolerance: bool = False
    claimed_metrics: dict[str, float] = field(default_factory=dict)
    reproduced_metrics: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        self.stage = VerificationStage.METRIC_COMPARISON
        self.details = {
            "comparisons_count": len(self.comparisons),
            "all_within_tolerance": self.all_within_tolerance,
            "claimed_metrics": self.claimed_metrics,
            "reproduced_metrics": self.reproduced_metrics,
        }


@dataclass
class ResourceUsage:
    """Resource usage during verification."""

    gpu_hours: float = 0.0
    cpu_hours: float = 0.0
    peak_memory_gb: float = 0.0
    storage_gb: float = 0.0
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "gpu_hours": self.gpu_hours,
            "cpu_hours": self.cpu_hours,
            "peak_memory_gb": self.peak_memory_gb,
            "storage_gb": self.storage_gb,
            "cost_usd": self.cost_usd,
        }


@dataclass
class MLVerificationResult:
    """Complete result of ML experiment verification."""

    status: VerificationStatus
    verified: bool
    message: str
    claim_id: str = ""
    experiment_type: str = ""

    # Stage results
    stages: dict[str, StageResult] = field(default_factory=dict)

    # Metrics
    claimed_metrics: dict[str, float] = field(default_factory=dict)
    reproduced_metrics: dict[str, float] = field(default_factory=dict)
    metric_comparisons: list[MetricComparison] = field(default_factory=list)
    all_metrics_within_tolerance: bool = False

    # Resources
    resources: ResourceUsage | None = None

    # Novelty
    novelty_score: float | None = None
    similar_papers: list[dict[str, Any]] = field(default_factory=list)

    # Timestamps
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Error details
    error_type: str | None = None
    error_details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "verified": self.verified,
            "message": self.message,
            "claim_id": self.claim_id,
            "experiment_type": self.experiment_type,
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
            "metrics": {
                "claimed": self.claimed_metrics,
                "reproduced": self.reproduced_metrics,
                "comparisons": [c.to_dict() for c in self.metric_comparisons],
                "all_within_tolerance": self.all_metrics_within_tolerance,
            },
            "resources": self.resources.to_dict() if self.resources else None,
            "novelty_score": self.novelty_score,
            "similar_papers": self.similar_papers,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_type": self.error_type,
            "error_details": self.error_details,
        }


class BaseMLVerifier(ABC):
    """Abstract base class for ML verification components."""

    @property
    @abstractmethod
    def component_name(self) -> str:
        """Name of this verification component."""
        pass

    @abstractmethod
    async def verify(self, *args, **kwargs) -> StageResult:
        """Perform verification and return result."""
        pass


class BaseEnvironmentBuilder(ABC):
    """Abstract base class for environment builders."""

    @property
    @abstractmethod
    def environment_type(self) -> str:
        """Type of environment (docker, nix, etc.)."""
        pass

    @abstractmethod
    async def build(
        self,
        specification: dict[str, Any],
        working_dir: str,
    ) -> EnvironmentResult:
        """Build the execution environment."""
        pass

    @abstractmethod
    async def cleanup(self, environment_id: str) -> None:
        """Clean up the environment."""
        pass


class BaseJobRunner(ABC):
    """Abstract base class for job runners."""

    @property
    @abstractmethod
    def runner_name(self) -> str:
        """Name of this runner."""
        pass

    @abstractmethod
    async def submit_job(
        self,
        job_spec: dict[str, Any],
        timeout_seconds: int,
    ) -> str:
        """Submit a job and return job ID."""
        pass

    @abstractmethod
    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get status of a submitted job."""
        pass

    @abstractmethod
    async def get_job_logs(self, job_id: str) -> str:
        """Get logs from a job."""
        pass

    @abstractmethod
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        pass

    @abstractmethod
    async def wait_for_completion(
        self,
        job_id: str,
        timeout_seconds: int,
    ) -> ExecutionResult:
        """Wait for job completion and return result."""
        pass


class BaseBenchmarkRunner(ABC):
    """Abstract base class for benchmark runners."""

    @property
    @abstractmethod
    def benchmark_name(self) -> str:
        """Name of the benchmark suite."""
        pass

    @abstractmethod
    async def run_benchmark(
        self,
        model_path: str,
        tasks: list[str],
        config: dict[str, Any],
    ) -> dict[str, MetricValue]:
        """Run benchmark evaluation."""
        pass

    @abstractmethod
    def get_supported_tasks(self) -> list[str]:
        """Get list of supported benchmark tasks."""
        pass
