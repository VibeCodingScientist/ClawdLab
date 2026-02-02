"""Base classes and data structures for Research Orchestration."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class WorkflowStatus(Enum):
    """Status of a research workflow."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskStatus(Enum):
    """Status of a research task."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class ClaimStatus(Enum):
    """Status of a claim verification."""

    PENDING = "pending"
    ROUTING = "routing"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"


class Priority(Enum):
    """Task priority levels."""

    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


# ===========================================
# CLAIM DATA CLASSES
# ===========================================


@dataclass
class Claim:
    """A scientific claim to be verified."""

    claim_id: str = field(default_factory=lambda: str(uuid4()))
    claim_type: str = ""
    content: str = ""
    domain: str | None = None
    source: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_type": self.claim_type,
            "content": self.content,
            "domain": self.domain,
            "source": self.source,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Claim":
        return cls(
            claim_id=data.get("claim_id", str(uuid4())),
            claim_type=data.get("claim_type", ""),
            content=data.get("content", ""),
            domain=data.get("domain"),
            source=data.get("source", ""),
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
        )


@dataclass
class ClaimVerificationResult:
    """Result of claim verification."""

    claim_id: str
    status: ClaimStatus
    verified: bool
    message: str
    verifier: str = ""
    domain: str = ""
    confidence: float = 0.0
    evidence: list[dict[str, Any]] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    execution_time_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "status": self.status.value,
            "verified": self.verified,
            "message": self.message,
            "verifier": self.verifier,
            "domain": self.domain,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "details": self.details,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_seconds": self.execution_time_seconds,
        }


# ===========================================
# TASK DATA CLASSES
# ===========================================


@dataclass
class ResearchTask:
    """A single research task within a workflow."""

    task_id: str = field(default_factory=lambda: str(uuid4()))
    task_type: str = ""
    name: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: Priority = Priority.NORMAL
    workflow_id: str | None = None
    parent_task_id: str | None = None
    dependencies: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    assigned_agent: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_minutes: int = 60
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]

    @property
    def can_run(self) -> bool:
        return self.status == TaskStatus.PENDING

    @property
    def execution_time_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "workflow_id": self.workflow_id,
            "parent_task_id": self.parent_task_id,
            "dependencies": self.dependencies,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "assigned_agent": self.assigned_agent,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_minutes": self.timeout_minutes,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "execution_time_seconds": self.execution_time_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchTask":
        return cls(
            task_id=data.get("task_id", str(uuid4())),
            task_type=data.get("task_type", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            priority=Priority(data.get("priority", 3)),
            workflow_id=data.get("workflow_id"),
            parent_task_id=data.get("parent_task_id"),
            dependencies=data.get("dependencies", []),
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            assigned_agent=data.get("assigned_agent"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            timeout_minutes=data.get("timeout_minutes", 60),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error_message=data.get("error_message"),
        )


# ===========================================
# WORKFLOW DATA CLASSES
# ===========================================


@dataclass
class WorkflowStep:
    """A step in a research workflow."""

    step_id: str = field(default_factory=lambda: str(uuid4()))
    step_name: str = ""
    step_type: str = ""
    order: int = 0
    task_ids: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "step_type": self.step_type,
            "order": self.order,
            "task_ids": self.task_ids,
            "status": self.status.value,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "depends_on": self.depends_on,
        }


@dataclass
class ResearchWorkflow:
    """A research workflow containing multiple steps and tasks."""

    workflow_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    template: str = ""
    status: WorkflowStatus = WorkflowStatus.PENDING
    priority: Priority = Priority.NORMAL
    owner_agent_id: str = ""
    steps: list[WorkflowStep] = field(default_factory=list)
    tasks: dict[str, ResearchTask] = field(default_factory=dict)
    claims: list[Claim] = field(default_factory=list)
    results: list[ClaimVerificationResult] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    timeout_hours: int = 24
    error_message: str | None = None

    @property
    def current_step(self) -> WorkflowStep | None:
        for step in sorted(self.steps, key=lambda s: s.order):
            if step.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                return step
        return None

    @property
    def progress_percent(self) -> float:
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status == TaskStatus.COMPLETED)
        return (completed / len(self.steps)) * 100

    @property
    def is_complete(self) -> bool:
        return self.status in [
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.TIMEOUT,
        ]

    @property
    def execution_time_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "status": self.status.value,
            "priority": self.priority.value,
            "owner_agent_id": self.owner_agent_id,
            "steps": [s.to_dict() for s in self.steps],
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "claims": [c.to_dict() for c in self.claims],
            "results": [r.to_dict() for r in self.results],
            "context": self.context,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "timeout_hours": self.timeout_hours,
            "progress_percent": self.progress_percent,
            "execution_time_seconds": self.execution_time_seconds,
            "error_message": self.error_message,
        }


# ===========================================
# SESSION DATA CLASSES
# ===========================================


@dataclass
class ResearchSession:
    """A research session tracking agent's ongoing work."""

    session_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    workflow_ids: list[str] = field(default_factory=list)
    active_task_ids: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "workflow_ids": self.workflow_ids,
            "active_task_ids": self.active_task_ids,
            "context": self.context,
            "num_checkpoints": len(self.checkpoints),
            "created_at": self.created_at.isoformat(),
            "last_active_at": self.last_active_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired,
        }


# ===========================================
# ROUTING DATA CLASSES
# ===========================================


@dataclass
class RoutingDecision:
    """Decision for routing a claim to a verifier."""

    claim_id: str
    domain: str
    verification_engine: str
    celery_queue: str
    confidence: float
    reasoning: str = ""
    alternative_domains: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "domain": self.domain,
            "verification_engine": self.verification_engine,
            "celery_queue": self.celery_queue,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "alternative_domains": self.alternative_domains,
        }


# ===========================================
# RESEARCH REQUEST/RESPONSE
# ===========================================


@dataclass
class ResearchRequest:
    """A request to conduct research."""

    request_id: str = field(default_factory=lambda: str(uuid4()))
    request_type: str = ""  # hypothesis_verification, literature_review, etc.
    title: str = ""
    description: str = ""
    claims: list[Claim] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    priority: Priority = Priority.NORMAL
    requester_agent_id: str = ""
    callback_url: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "request_type": self.request_type,
            "title": self.title,
            "description": self.description,
            "claims": [c.to_dict() for c in self.claims],
            "context": self.context,
            "files": self.files,
            "priority": self.priority.value,
            "requester_agent_id": self.requester_agent_id,
            "callback_url": self.callback_url,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ResearchResponse:
    """Response from research orchestration."""

    request_id: str
    workflow_id: str
    status: WorkflowStatus
    message: str
    results: list[ClaimVerificationResult] = field(default_factory=list)
    summary: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    @property
    def verified_count(self) -> int:
        return sum(1 for r in self.results if r.verified)

    @property
    def refuted_count(self) -> int:
        return sum(1 for r in self.results if r.status == ClaimStatus.REFUTED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "message": self.message,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
            "confidence": self.confidence,
            "verified_count": self.verified_count,
            "refuted_count": self.refuted_count,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


__all__ = [
    # Enums
    "WorkflowStatus",
    "TaskStatus",
    "ClaimStatus",
    "Priority",
    # Claim classes
    "Claim",
    "ClaimVerificationResult",
    # Task classes
    "ResearchTask",
    # Workflow classes
    "WorkflowStep",
    "ResearchWorkflow",
    # Session classes
    "ResearchSession",
    # Routing classes
    "RoutingDecision",
    # Request/Response classes
    "ResearchRequest",
    "ResearchResponse",
]
