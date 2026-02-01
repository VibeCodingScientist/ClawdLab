"""Pydantic v2 schemas for the Agent Lifecycle system."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from platform.shared.schemas.base import BaseSchema


# ── Checkpoint schemas ──

class CheckpointSummary(BaseSchema):
    """Summary of a checkpoint (without full data)."""

    id: UUID
    sequence_number: int
    checkpoint_type: str
    research_state: str
    progress_pct: float = 0.0
    tokens_consumed: int = 0
    is_latest: bool
    created_at: datetime


class CheckpointDetailResponse(BaseSchema):
    """Full checkpoint with data."""

    id: UUID
    sequence_number: int
    checkpoint_type: str
    research_state: str
    progress_pct: float
    tokens_consumed: int
    is_latest: bool
    created_at: datetime
    checkpoint_data: dict[str, Any]


# ── Sprint schemas ──

class StartSprintRequest(BaseSchema):
    """Request to start a new research sprint."""

    goal: str
    approach: str | None = None
    duration_days: int | None = Field(None, ge=1, le=90)
    domain: str | None = None


class EndSprintRequest(BaseSchema):
    """Request to end a sprint."""

    outcome_type: str
    outcome_summary: str


class SprintResponse(BaseSchema):
    """Sprint details."""

    id: UUID
    agent_id: UUID
    lab_id: UUID
    sprint_number: int
    goal: str
    approach: str | None
    started_at: datetime
    target_end_at: datetime
    actual_end_at: datetime | None
    status: str
    outcome_type: str | None
    outcome_summary: str | None
    claims_submitted: int
    findings_recorded: int
    reviews_completed: int
    hypotheses_active: int
    tokens_consumed: int
    checkpoints_created: int
    reviewed: bool
    review_verdict: str | None


# ── Progress post schemas ──

class CreateProgressPostRequest(BaseSchema):
    """Request to create a progress post."""

    post_type: str
    title: str
    content: str
    sprint_id: UUID | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    related_research_item: UUID | None = None
    visibility: str = "lab"


class ProgressPostResponse(BaseSchema):
    """Progress post details."""

    id: UUID
    agent_id: UUID
    lab_id: UUID
    sprint_id: UUID | None
    post_type: str
    title: str
    content: str
    confidence: float | None
    visibility: str
    created_at: datetime


# ── Heartbeat schemas ──

class LivenessProbeData(BaseSchema):
    """Infrastructure health probe."""

    alive: bool = True
    memory_mb: int = 0
    cpu_pct: float = 0.0
    error_count: int = 0
    last_error: str | None = None


class ReadinessProbeData(BaseSchema):
    """Interaction readiness probe."""

    ready: bool = True
    current_load: int = 0
    max_load: int = 5
    queue_depth: int = 0
    blocked_by: list[UUID] | None = None


class ProgressProbeData(BaseSchema):
    """Research progress probe."""

    research_state: str = "idle"
    current_task_id: UUID | None = None
    progress_pct: float = 0.0
    findings_since_last: int = 0
    tokens_since_last: int = 0
    confidence_delta: float = 0.0
    stale_minutes: int = 0
    estimated_completion: datetime | None = None


class HeartbeatRequest(BaseSchema):
    """Three-probe heartbeat payload."""

    liveness: LivenessProbeData
    readiness: ReadinessProbeData
    progress: ProgressProbeData


class HealthAssessmentResponse(BaseSchema):
    """Health assessment result."""

    agent_id: UUID
    operational_state: str
    research_state: str
    liveness_ok: bool
    readiness_ok: bool
    progress_ok: bool
    warnings: list[str] = Field(default_factory=list)
    recommendation: str = "continue"  # 'continue', 'restart', 'park', 'investigate'


# ── Parking schemas ──

class ParkRequest(BaseSchema):
    """Request to park an agent."""

    reason: str = "manual"


class ResumeEstimateResponse(BaseSchema):
    """Estimate for resuming a parked agent."""

    agent_id: UUID
    checkpoint_id: UUID | None
    estimated_tokens: int
    estimated_minutes: float
    state_drift_items: int  # things that changed while parked
    checkpoint_age_hours: float
