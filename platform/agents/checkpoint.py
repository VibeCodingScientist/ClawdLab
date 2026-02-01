"""Agent checkpoint dataclasses with JSONB serialization.

A checkpoint captures everything needed to resume research from where it left off.
Follows LangGraph's checkpoint-per-super-step pattern.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from .lifecycle import AgentResearchState


@dataclass
class TaskSnapshot:
    """Current task the agent is working on."""

    task_id: str
    task_type: str  # 'research_item', 'challenge_submission', 'frontier_claim', 'review'
    source_id: str
    description: str
    started_at: str
    approach: str


@dataclass
class HypothesisState:
    """Active hypothesis with confidence tracking."""

    hypothesis_id: str
    statement: str
    confidence: float  # 0.0-1.0
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    status: str = "active"  # 'active', 'supported', 'refuted', 'abandoned'


@dataclass
class FindingSnapshot:
    """A research finding accumulated during a sprint."""

    finding_id: str
    description: str
    evidence_type: str  # 'computational', 'analytical', 'literature'
    confidence: float
    publishable: bool = False


@dataclass
class DecisionEntry:
    """A key decision made during research and its reasoning."""

    timestamp: str
    decision: str
    reasoning: str
    alternatives_considered: list[str] = field(default_factory=list)


@dataclass
class AgentCheckpointData:
    """Complete agent research state, serializable to JSONB.

    This is the *data* stored in agent_checkpoints.checkpoint_data.
    The DB model is separate (in models.py).
    """

    # Identity
    checkpoint_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    lab_id: str | None = None
    sequence_number: int = 0

    # Research context
    current_task: TaskSnapshot | None = None
    hypothesis_stack: list[HypothesisState] = field(default_factory=list)
    findings: list[FindingSnapshot] = field(default_factory=list)
    decision_log: list[DecisionEntry] = field(default_factory=list)

    # Memory tiers
    core_memory: dict[str, str] = field(default_factory=dict)
    working_memory: str = ""
    archival_refs: list[str] = field(default_factory=list)

    # External state references
    pending_compute_jobs: list[str] = field(default_factory=list)
    pending_verifications: list[str] = field(default_factory=list)
    data_versions: dict[str, str] = field(default_factory=dict)

    # Sprint context
    sprint_id: str | None = None
    sprint_progress_pct: float = 0.0
    tokens_consumed: int = 0
    compute_seconds_used: float = 0.0

    # State
    research_state: str = "idle"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Resumption hint
    resume_action: str = "continue"
    resume_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSONB-compatible dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentCheckpointData":
        """Deserialize from JSONB dict."""
        # Handle nested dataclasses
        task = data.get("current_task")
        if task and isinstance(task, dict):
            data["current_task"] = TaskSnapshot(**task)

        hypotheses = data.get("hypothesis_stack", [])
        if hypotheses and isinstance(hypotheses[0], dict):
            data["hypothesis_stack"] = [HypothesisState(**h) for h in hypotheses]

        findings = data.get("findings", [])
        if findings and isinstance(findings[0], dict):
            data["findings"] = [FindingSnapshot(**f) for f in findings]

        decisions = data.get("decision_log", [])
        if decisions and isinstance(decisions[0], dict):
            data["decision_log"] = [DecisionEntry(**d) for d in decisions]

        return cls(**data)
