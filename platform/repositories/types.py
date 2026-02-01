"""Typed structures for repository data.

Provides type-safe dataclasses for complex nested data structures
that are stored as JSON in the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ===========================================
# EXPERIMENT-RELATED TYPES
# ===========================================


class VariableType(str, Enum):
    """Types of experiment variables."""

    INDEPENDENT = "independent"
    DEPENDENT = "dependent"
    CONTROL = "control"
    CONFOUNDING = "confounding"


class StepStatus(str, Enum):
    """Status of an experiment step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExperimentVariable:
    """A variable in an experiment.

    Attributes:
        name: Variable name
        type: Variable type (independent, dependent, etc.)
        description: Description of the variable
        unit: Unit of measurement (if applicable)
        default_value: Default value for the variable
        constraints: Constraints on valid values
        metadata: Additional metadata
    """

    name: str
    type: VariableType
    description: str = ""
    unit: str | None = None
    default_value: Any = None
    constraints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "unit": self.unit,
            "default_value": self.default_value,
            "constraints": self.constraints,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentVariable:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            type=VariableType(data.get("type", "independent")),
            description=data.get("description", ""),
            unit=data.get("unit"),
            default_value=data.get("default_value"),
            constraints=data.get("constraints", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExperimentStep:
    """A step in an experiment workflow.

    Attributes:
        name: Step name
        description: Step description
        order: Order in the workflow
        status: Current status
        started_at: When step started
        completed_at: When step completed
        inputs: Input parameters
        outputs: Output results
        dependencies: Step names this depends on
        metadata: Additional metadata
    """

    name: str
    description: str = ""
    order: int = 0
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentStep:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            order=data.get("order", 0),
            status=StepStatus(data.get("status", "pending")),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            dependencies=data.get("dependencies", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExperimentArtifact:
    """An artifact produced by an experiment.

    Attributes:
        name: Artifact name
        type: Artifact type (file, model, dataset, etc.)
        path: Storage path
        size_bytes: Size in bytes
        checksum: File checksum (SHA256)
        created_at: Creation timestamp
        metadata: Additional metadata
    """

    name: str
    type: str
    path: str
    size_bytes: int = 0
    checksum: str = ""
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "name": self.name,
            "type": self.type,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentArtifact:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            type=data["type"],
            path=data["path"],
            size_bytes=data.get("size_bytes", 0),
            checksum=data.get("checksum", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            metadata=data.get("metadata", {}),
        )


# ===========================================
# HYPOTHESIS-RELATED TYPES
# ===========================================


class EvidenceType(str, Enum):
    """Types of evidence for a hypothesis."""

    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    NEUTRAL = "neutral"


@dataclass
class HypothesisEvidence:
    """Evidence for or against a hypothesis.

    Attributes:
        type: Evidence type
        source: Source of evidence (experiment ID, paper, etc.)
        description: Description of the evidence
        confidence: Confidence score (0-1)
        timestamp: When evidence was recorded
        metadata: Additional metadata
    """

    type: EvidenceType
    source: str
    description: str = ""
    confidence: float = 0.5
    timestamp: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "type": self.type.value,
            "source": self.source,
            "description": self.description,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HypothesisEvidence:
        """Create from dictionary."""
        return cls(
            type=EvidenceType(data.get("type", "neutral")),
            source=data["source"],
            description=data.get("description", ""),
            confidence=data.get("confidence", 0.5),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
            metadata=data.get("metadata", {}),
        )


# ===========================================
# RESOURCE ESTIMATION TYPES
# ===========================================


@dataclass
class ResourceEstimate:
    """Resource estimate for an experiment or plan.

    Attributes:
        cpu_hours: Estimated CPU hours
        gpu_hours: Estimated GPU hours
        memory_gb: Peak memory in GB
        storage_gb: Storage required in GB
        cost_estimate_usd: Estimated cost in USD
        duration_hours: Estimated duration in hours
        metadata: Additional resource details
    """

    cpu_hours: float = 0.0
    gpu_hours: float = 0.0
    memory_gb: float = 0.0
    storage_gb: float = 0.0
    cost_estimate_usd: float = 0.0
    duration_hours: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "cpu_hours": self.cpu_hours,
            "gpu_hours": self.gpu_hours,
            "memory_gb": self.memory_gb,
            "storage_gb": self.storage_gb,
            "cost_estimate_usd": self.cost_estimate_usd,
            "duration_hours": self.duration_hours,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceEstimate:
        """Create from dictionary."""
        return cls(
            cpu_hours=data.get("cpu_hours", 0.0),
            gpu_hours=data.get("gpu_hours", 0.0),
            memory_gb=data.get("memory_gb", 0.0),
            storage_gb=data.get("storage_gb", 0.0),
            cost_estimate_usd=data.get("cost_estimate_usd", 0.0),
            duration_hours=data.get("duration_hours", 0.0),
            metadata=data.get("metadata", {}),
        )

    def __add__(self, other: ResourceEstimate) -> ResourceEstimate:
        """Add two resource estimates together."""
        return ResourceEstimate(
            cpu_hours=self.cpu_hours + other.cpu_hours,
            gpu_hours=self.gpu_hours + other.gpu_hours,
            memory_gb=max(self.memory_gb, other.memory_gb),  # Peak memory
            storage_gb=self.storage_gb + other.storage_gb,
            cost_estimate_usd=self.cost_estimate_usd + other.cost_estimate_usd,
            duration_hours=self.duration_hours + other.duration_hours,
        )


# ===========================================
# HELPER FUNCTIONS
# ===========================================


def parse_variables(data: list[dict[str, Any]] | None) -> list[ExperimentVariable]:
    """Parse a list of variable dictionaries into typed objects.

    Args:
        data: List of variable dictionaries

    Returns:
        List of ExperimentVariable objects
    """
    if not data:
        return []
    return [ExperimentVariable.from_dict(v) for v in data]


def parse_steps(data: list[dict[str, Any]] | None) -> list[ExperimentStep]:
    """Parse a list of step dictionaries into typed objects.

    Args:
        data: List of step dictionaries

    Returns:
        List of ExperimentStep objects
    """
    if not data:
        return []
    return [ExperimentStep.from_dict(s) for s in data]


def parse_artifacts(data: list[dict[str, Any]] | None) -> list[ExperimentArtifact]:
    """Parse a list of artifact dictionaries into typed objects.

    Args:
        data: List of artifact dictionaries

    Returns:
        List of ExperimentArtifact objects
    """
    if not data:
        return []
    return [ExperimentArtifact.from_dict(a) for a in data]


def parse_evidence(data: list[dict[str, Any]] | None) -> list[HypothesisEvidence]:
    """Parse a list of evidence dictionaries into typed objects.

    Args:
        data: List of evidence dictionaries

    Returns:
        List of HypothesisEvidence objects
    """
    if not data:
        return []
    return [HypothesisEvidence.from_dict(e) for e in data]


__all__ = [
    # Enums
    "EvidenceType",
    "StepStatus",
    "VariableType",
    # Dataclasses
    "ExperimentArtifact",
    "ExperimentStep",
    "ExperimentVariable",
    "HypothesisEvidence",
    "ResourceEstimate",
    # Parser functions
    "parse_artifacts",
    "parse_evidence",
    "parse_steps",
    "parse_variables",
]
