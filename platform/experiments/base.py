"""Base classes and data structures for Experiment Planning."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class ExperimentStatus(Enum):
    """Status of an experiment."""

    DRAFT = "draft"
    PLANNED = "planned"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class HypothesisStatus(Enum):
    """Status of a hypothesis."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    TESTING = "testing"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"
    REVISED = "revised"


class VariableType(Enum):
    """Types of experimental variables."""

    INDEPENDENT = "independent"
    DEPENDENT = "dependent"
    CONTROL = "control"
    CONFOUNDING = "confounding"
    COVARIATE = "covariate"


class ResourceType(Enum):
    """Types of compute resources."""

    GPU = "gpu"
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"


# ===========================================
# HYPOTHESIS DATA CLASSES
# ===========================================


@dataclass
class Hypothesis:
    """A scientific hypothesis to test."""

    hypothesis_id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    statement: str = ""
    hypothesis_type: str = "causal"  # causal, correlational, comparative, etc.
    variables: list[str] = field(default_factory=list)
    predictions: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    confidence: float = 0.0
    priority: int = 5
    source: str = ""  # literature, agent, user
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)
    related_papers: list[str] = field(default_factory=list)
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "title": self.title,
            "statement": self.statement,
            "hypothesis_type": self.hypothesis_type,
            "variables": self.variables,
            "predictions": self.predictions,
            "assumptions": self.assumptions,
            "status": self.status.value,
            "confidence": self.confidence,
            "priority": self.priority,
            "source": self.source,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "related_papers": self.related_papers,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Hypothesis":
        return cls(
            hypothesis_id=data.get("hypothesis_id", str(uuid4())),
            title=data.get("title", ""),
            statement=data.get("statement", ""),
            hypothesis_type=data.get("hypothesis_type", "causal"),
            variables=data.get("variables", []),
            predictions=data.get("predictions", []),
            assumptions=data.get("assumptions", []),
            status=HypothesisStatus(data.get("status", "proposed")),
            confidence=data.get("confidence", 0.0),
            priority=data.get("priority", 5),
            source=data.get("source", ""),
            supporting_evidence=data.get("supporting_evidence", []),
            contradicting_evidence=data.get("contradicting_evidence", []),
            related_papers=data.get("related_papers", []),
            created_by=data.get("created_by", ""),
            metadata=data.get("metadata", {}),
        )


# ===========================================
# VARIABLE DATA CLASSES
# ===========================================


@dataclass
class Variable:
    """An experimental variable."""

    variable_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    variable_type: VariableType = VariableType.INDEPENDENT
    data_type: str = "continuous"  # continuous, discrete, categorical, binary
    unit: str = ""
    min_value: float | None = None
    max_value: float | None = None
    default_value: Any = None
    possible_values: list[Any] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable_id": self.variable_id,
            "name": self.name,
            "description": self.description,
            "variable_type": self.variable_type.value,
            "data_type": self.data_type,
            "unit": self.unit,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "default_value": self.default_value,
            "possible_values": self.possible_values,
            "constraints": self.constraints,
        }


# ===========================================
# RESOURCE DATA CLASSES
# ===========================================


@dataclass
class ResourceRequirement:
    """Resource requirement for an experiment."""

    resource_type: ResourceType = ResourceType.CPU
    amount: float = 0.0
    unit: str = "hours"
    priority: str = "required"  # required, preferred, optional
    constraints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_type": self.resource_type.value,
            "amount": self.amount,
            "unit": self.unit,
            "priority": self.priority,
            "constraints": self.constraints,
        }


@dataclass
class ResourceEstimate:
    """Estimated resources for an experiment."""

    estimate_id: str = field(default_factory=lambda: str(uuid4()))
    gpu_hours: float = 0.0
    cpu_hours: float = 0.0
    memory_gb: float = 0.0
    storage_gb: float = 0.0
    estimated_duration_hours: float = 0.0
    estimated_cost: float = 0.0
    confidence: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimate_id": self.estimate_id,
            "gpu_hours": self.gpu_hours,
            "cpu_hours": self.cpu_hours,
            "memory_gb": self.memory_gb,
            "storage_gb": self.storage_gb,
            "estimated_duration_hours": self.estimated_duration_hours,
            "estimated_cost": self.estimated_cost,
            "confidence": self.confidence,
            "breakdown": self.breakdown,
            "assumptions": self.assumptions,
        }


# ===========================================
# EXPERIMENT DATA CLASSES
# ===========================================


@dataclass
class ExperimentConfig:
    """Configuration for an experiment."""

    config_id: str = field(default_factory=lambda: str(uuid4()))
    parameters: dict[str, Any] = field(default_factory=dict)
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    random_seed: int | None = None
    environment: dict[str, str] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    output_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_id": self.config_id,
            "parameters": self.parameters,
            "hyperparameters": self.hyperparameters,
            "random_seed": self.random_seed,
            "environment": self.environment,
            "dependencies": self.dependencies,
            "data_sources": self.data_sources,
            "output_config": self.output_config,
        }


@dataclass
class ExperimentStep:
    """A step in an experiment."""

    step_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    step_type: str = ""  # setup, execution, analysis, validation
    order: int = 0
    command: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # step_ids
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "step_type": self.step_type,
            "order": self.order,
            "command": self.command,
            "parameters": self.parameters,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "dependencies": self.dependencies,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
        }


@dataclass
class Experiment:
    """A scientific experiment."""

    experiment_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    experiment_type: str = "computational"
    domain: str = ""
    status: ExperimentStatus = ExperimentStatus.DRAFT

    # Hypothesis and design
    hypotheses: list[Hypothesis] = field(default_factory=list)
    variables: list[Variable] = field(default_factory=list)
    config: ExperimentConfig = field(default_factory=ExperimentConfig)
    steps: list[ExperimentStep] = field(default_factory=list)

    # Resources
    resource_requirements: list[ResourceRequirement] = field(default_factory=list)
    resource_estimate: ResourceEstimate | None = None

    # Scheduling
    priority: int = 5
    scheduled_start: datetime | None = None
    deadline: datetime | None = None

    # Execution tracking
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: float = 0.0
    current_step: str = ""

    # Results
    results: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)

    # Metadata
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Relationships
    parent_experiment_id: str | None = None
    related_experiments: list[str] = field(default_factory=list)
    knowledge_entries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "experiment_type": self.experiment_type,
            "domain": self.domain,
            "status": self.status.value,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "variables": [v.to_dict() for v in self.variables],
            "config": self.config.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
            "resource_requirements": [r.to_dict() for r in self.resource_requirements],
            "resource_estimate": self.resource_estimate.to_dict() if self.resource_estimate else None,
            "priority": self.priority,
            "scheduled_start": self.scheduled_start.isoformat() if self.scheduled_start else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "current_step": self.current_step,
            "results": self.results,
            "artifacts": self.artifacts,
            "logs": self.logs,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "metadata": self.metadata,
            "parent_experiment_id": self.parent_experiment_id,
            "related_experiments": self.related_experiments,
            "knowledge_entries": self.knowledge_entries,
        }


# ===========================================
# PLAN DATA CLASSES
# ===========================================


@dataclass
class ExperimentPlan:
    """A plan for conducting experiments."""

    plan_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    objective: str = ""
    domain: str = ""

    # Content
    hypotheses: list[Hypothesis] = field(default_factory=list)
    experiments: list[Experiment] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)  # exp_id -> [dep_ids]

    # Resources
    total_resource_estimate: ResourceEstimate | None = None
    budget_limit: float | None = None

    # Timeline
    start_date: datetime | None = None
    end_date: datetime | None = None
    milestones: list[dict[str, Any]] = field(default_factory=list)

    # Status
    status: str = "draft"
    progress: float = 0.0

    # Metadata
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "objective": self.objective,
            "domain": self.domain,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "experiments": [e.to_dict() for e in self.experiments],
            "dependencies": self.dependencies,
            "total_resource_estimate": (
                self.total_resource_estimate.to_dict() if self.total_resource_estimate else None
            ),
            "budget_limit": self.budget_limit,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "milestones": self.milestones,
            "status": self.status,
            "progress": self.progress,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


# ===========================================
# RESULT DATA CLASSES
# ===========================================


@dataclass
class ExperimentResult:
    """Results from an experiment."""

    result_id: str = field(default_factory=lambda: str(uuid4()))
    experiment_id: str = ""
    hypothesis_id: str = ""
    outcome: str = ""  # supported, refuted, inconclusive
    metrics: dict[str, float] = field(default_factory=dict)
    statistics: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    p_value: float | None = None
    effect_size: float | None = None
    summary: str = ""
    visualizations: list[str] = field(default_factory=list)
    raw_data_path: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "experiment_id": self.experiment_id,
            "hypothesis_id": self.hypothesis_id,
            "outcome": self.outcome,
            "metrics": self.metrics,
            "statistics": self.statistics,
            "confidence": self.confidence,
            "p_value": self.p_value,
            "effect_size": self.effect_size,
            "summary": self.summary,
            "visualizations": self.visualizations,
            "raw_data_path": self.raw_data_path,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Checkpoint:
    """A checkpoint of experiment state."""

    checkpoint_id: str = field(default_factory=lambda: str(uuid4()))
    experiment_id: str = ""
    step_id: str = ""
    state: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    path: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "experiment_id": self.experiment_id,
            "step_id": self.step_id,
            "state": self.state,
            "metrics": self.metrics,
            "path": self.path,
            "created_at": self.created_at.isoformat(),
        }


__all__ = [
    # Enums
    "ExperimentStatus",
    "HypothesisStatus",
    "VariableType",
    "ResourceType",
    # Hypothesis classes
    "Hypothesis",
    # Variable classes
    "Variable",
    # Resource classes
    "ResourceRequirement",
    "ResourceEstimate",
    # Experiment classes
    "ExperimentConfig",
    "ExperimentStep",
    "Experiment",
    # Plan classes
    "ExperimentPlan",
    # Result classes
    "ExperimentResult",
    "Checkpoint",
]
