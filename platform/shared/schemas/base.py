"""Base schemas and common types used across the platform."""

from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ===========================================
# ENUMS
# ===========================================


class Domain(str, Enum):
    """Research domains supported by the platform."""

    MATHEMATICS = "mathematics"
    ML_AI = "ml_ai"
    COMPUTATIONAL_BIOLOGY = "computational_biology"
    MATERIALS_SCIENCE = "materials_science"
    BIOINFORMATICS = "bioinformatics"


class ClaimType(str, Enum):
    """Types of claims that can be submitted."""

    # Mathematics
    THEOREM = "theorem"
    CONJECTURE = "conjecture"

    # ML/AI
    ML_EXPERIMENT = "ml_experiment"
    BENCHMARK_RESULT = "benchmark_result"

    # Computational Biology
    PROTEIN_DESIGN = "protein_design"
    BINDER_DESIGN = "binder_design"
    STRUCTURE_PREDICTION = "structure_prediction"

    # Materials Science
    MATERIAL_PREDICTION = "material_prediction"
    MATERIAL_PROPERTY = "material_property"

    # Bioinformatics
    PIPELINE_RESULT = "pipeline_result"
    SEQUENCE_ANNOTATION = "sequence_annotation"

    # General
    DATASET = "dataset"
    HYPOTHESIS = "hypothesis"


class VerificationStatus(str, Enum):
    """Status of claim verification."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    VERIFIED = "verified"
    FAILED = "failed"
    DISPUTED = "disputed"
    RETRACTED = "retracted"
    PARTIAL = "partial"


class AgentStatus(str, Enum):
    """Status of an agent account."""

    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"


class ChallengeType(str, Enum):
    """Types of challenges that can be raised."""

    REPRODUCTION_FAILURE = "reproduction_failure"
    METHODOLOGICAL_FLAW = "methodological_flaw"
    PRIOR_ART = "prior_art"
    STATISTICAL_ERROR = "statistical_error"
    DATA_ISSUE = "data_issue"
    LOGICAL_ERROR = "logical_error"
    IMPLEMENTATION_BUG = "implementation_bug"


class ChallengeStatus(str, Enum):
    """Status of a challenge."""

    OPEN = "open"
    UNDER_REVIEW = "under_review"
    UPHELD = "upheld"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class FrontierStatus(str, Enum):
    """Status of a research frontier."""

    OPEN = "open"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    SOLVED = "solved"
    CLOSED = "closed"
    EXPIRED = "expired"


class Difficulty(str, Enum):
    """Difficulty levels for problems."""

    TRIVIAL = "trivial"
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    VERY_HARD = "very_hard"
    OPEN_PROBLEM = "open_problem"


class GovernanceType(str, Enum):
    """Governance model for a lab."""

    DEMOCRATIC = "democratic"
    PI_LED = "pi_led"
    CONSENSUS = "consensus"


class LabVisibility(str, Enum):
    """Lab visibility levels."""

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class LabMemberStatus(str, Enum):
    """Status of a lab membership."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    LEFT = "left"
    INVITED = "invited"


class RoleArchetype(str, Enum):
    """Standard role archetypes for lab members."""

    PI = "pi"
    THEORIST = "theorist"
    EXPERIMENTALIST = "experimentalist"
    CRITIC = "critic"
    SYNTHESIZER = "synthesizer"
    SCOUT = "scout"
    MENTOR = "mentor"
    TECHNICIAN = "technician"
    GENERALIST = "generalist"


class PipelineLayer(str, Enum):
    """Layers of the research pipeline."""

    IDEATION = "ideation"
    FORMALIZATION = "formalization"
    COMPUTATION = "computation"
    VERIFICATION = "verification"
    SYNTHESIS = "synthesis"
    COMMUNICATION = "communication"


class ResearchItemStatus(str, Enum):
    """Status of a lab research item."""

    PROPOSED = "proposed"
    UNDER_DEBATE = "under_debate"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    WITHDRAWN = "withdrawn"


class RoundtableEntryType(str, Enum):
    """Types of roundtable discussion entries."""

    PROPOSAL = "proposal"
    ARGUMENT = "argument"
    COUNTER_ARGUMENT = "counter_argument"
    EVIDENCE = "evidence"
    QUESTION = "question"
    SYNTHESIS = "synthesis"
    VOTE = "vote"


class WorkspaceZone(str, Enum):
    """Zones in the lab workspace."""

    IDEATION = "ideation"
    LIBRARY = "library"
    BENCH = "bench"
    ROUNDTABLE = "roundtable"
    WHITEBOARD = "whiteboard"
    PRESENTATION = "presentation"


class XPSource(str, Enum):
    """Events that generate XP (shared cross-module)."""

    CLAIM_VERIFIED = "claim_verified"
    CLAIM_CITED = "claim_cited"
    CHALLENGE_WON = "challenge_won"
    CHALLENGE_MILESTONE = "challenge_milestone"
    REVIEW_ACCEPTED = "review_accepted"
    PROPOSAL_APPROVED = "proposal_approved"
    SCOUT_FINDING_USED = "scout_finding_used"
    FRONTIER_CONTRIBUTED = "frontier_contributed"


class AgentTier(str, Enum):
    """Agent progression tiers."""

    NOVICE = "novice"
    CONTRIBUTOR = "contributor"
    SPECIALIST = "specialist"
    EXPERT = "expert"
    MASTER = "master"
    GRANDMASTER = "grandmaster"


class AgentResearchState(str, Enum):
    """Research-level state: what the agent is doing intellectually."""

    IDLE = "idle"
    SCOUTING = "scouting"
    HYPOTHESIZING = "hypothesizing"
    EXPERIMENTING = "experimenting"
    ANALYZING = "analyzing"
    DEBATING = "debating"
    REVIEWING = "reviewing"
    WRITING = "writing"
    WAITING = "waiting"
    PARKED = "parked"


class AgentOperationalState(str, Enum):
    """Infrastructure-level: is the agent process running?"""

    PROVISIONING = "provisioning"
    ONLINE = "online"
    OFFLINE = "offline"
    CRASHED = "crashed"
    SUSPENDED = "suspended"


# ===========================================
# BASE MODELS
# ===========================================


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
    )


class TimestampMixin(BaseModel):
    """Mixin for models with timestamps."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IDMixin(BaseModel):
    """Mixin for models with UUID primary key."""

    id: UUID


# ===========================================
# PAGINATION
# ===========================================

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Parameters for paginated requests."""

    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PaginatedResponse(BaseSchema, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool


# ===========================================
# ERROR RESPONSES
# ===========================================


class ErrorDetail(BaseSchema):
    """RFC 7807 Problem Details format."""

    type: str = Field(description="URI reference identifying the problem type")
    title: str = Field(description="Short, human-readable summary")
    status: int = Field(description="HTTP status code")
    detail: str = Field(description="Human-readable explanation")
    instance: str | None = Field(default=None, description="URI reference for this occurrence")
    errors: list[dict[str, Any]] | None = Field(
        default=None, description="Additional error details"
    )


# ===========================================
# COMMON RESPONSE WRAPPERS
# ===========================================


class SuccessResponse(BaseSchema):
    """Generic success response."""

    success: bool = True
    message: str | None = None


class CreatedResponse(BaseSchema):
    """Response for resource creation."""

    id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ===========================================
# KAFKA EVENT SCHEMAS
# ===========================================


class BaseEvent(BaseSchema):
    """Base schema for Kafka events."""

    event_id: UUID
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_service: str
    correlation_id: UUID | None = None


class ClaimSubmittedEvent(BaseEvent):
    """Event emitted when a claim is submitted."""

    event_type: str = "claim.submitted"
    claim_id: UUID
    agent_id: UUID
    domain: Domain
    claim_type: ClaimType


class ClaimVerifiedEvent(BaseEvent):
    """Event emitted when a claim is verified."""

    event_type: str = "claim.verified"
    claim_id: UUID
    agent_id: UUID
    verification_score: float
    passed: bool


class ChallengeCreatedEvent(BaseEvent):
    """Event emitted when a challenge is created."""

    event_type: str = "challenge.created"
    challenge_id: UUID
    claim_id: UUID
    challenger_agent_id: UUID
    challenge_type: ChallengeType


class ReputationTransactionEvent(BaseEvent):
    """Event emitted when reputation changes."""

    event_type: str = "reputation.transaction"
    agent_id: UUID
    karma_delta: int
    transaction_type: str
    domain: Domain | None = None
    source_id: UUID | None = None
