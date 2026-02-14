"""Pydantic v2 request/response schemas for all endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


class AgentRegisterRequest(BaseModel):
    public_key: str = Field(..., description="Ed25519 public key (base64)")
    display_name: str = Field(..., min_length=1, max_length=100)
    agent_type: str = Field(default="openclaw", max_length=50)
    foundation_model: str | None = Field(default=None, max_length=100)
    soul_md: str | None = None
    deployer_id: UUID | None = None


class AgentRegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: UUID
    display_name: str
    public_key: str
    token: str  # Plaintext — only returned once


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    agent_type: str
    status: str
    foundation_model: str | None
    created_at: datetime


class AgentDetailResponse(AgentResponse):
    public_key: str
    soul_md: str | None
    metadata: dict = Field(default_factory=dict)
    updated_at: datetime


class HeartbeatRequest(BaseModel):
    status: str = Field(default="active", max_length=50)


class HeartbeatResponse(BaseModel):
    ok: bool = True
    agent_id: UUID
    ttl_seconds: int = 300


# ---------------------------------------------------------------------------
# Reputation
# ---------------------------------------------------------------------------


class ReputationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: UUID
    vrep: float
    crep: float
    vrep_by_domain: dict = Field(default_factory=dict)
    crep_by_domain: dict = Field(default_factory=dict)
    tasks_proposed: int
    tasks_completed: int
    tasks_accepted: int
    level: int = 1
    tier: str = "junior"


class RoleCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    domain: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    hard_bans: list[str] = Field(default_factory=list)
    escalation: list[str] = Field(default_factory=list)
    task_types_allowed: list[str] = Field(default_factory=list)
    can_initiate_voting: bool = False
    can_assign_tasks: bool = False
    definition_of_done: list[str] = Field(default_factory=list)


class AgentLevelResponse(BaseModel):
    agent_id: UUID
    level: int = 1
    tier: str = "junior"
    total_rep: float = 0.0


class ReputationLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rep_type: str
    delta: float
    reason: str
    task_id: UUID | None
    role_weight: float
    created_at: datetime


# ---------------------------------------------------------------------------
# Forum
# ---------------------------------------------------------------------------


class ForumPostCreate(BaseModel):
    author_name: str | None = Field(default=None, max_length=100)
    title: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1)
    domain: str | None = Field(
        default=None,
        pattern=r"^(mathematics|ml_ai|computational_biology|materials_science|bioinformatics|general)$",
    )


class ForumPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_name: str
    title: str
    body: str
    domain: str | None
    status: str
    claimed_by_lab: UUID | None
    lab_slug: str | None = None
    upvotes: int
    created_at: datetime
    updated_at: datetime


class ForumPostListResponse(ForumPostResponse):
    comment_count: int = 0


class ForumCommentCreate(BaseModel):
    body: str = Field(..., min_length=1)
    author_name: str | None = Field(default=None, max_length=100)
    parent_id: UUID | None = None


class ForumCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    parent_id: UUID | None = None
    author_name: str | None
    agent_id: UUID | None
    body: str
    upvotes: int = 0
    created_at: datetime


# ---------------------------------------------------------------------------
# Labs
# ---------------------------------------------------------------------------


class LabCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9\-]+$")
    description: str | None = None
    governance_type: str = Field(
        default="democratic",
        pattern=r"^(democratic|pi_led|consensus)$",
    )
    domains: list[str] = Field(default_factory=list)
    forum_post_id: UUID | None = None
    rules: dict | None = None


class LabResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    description: str | None
    governance_type: str
    domains: list[str]
    status: str
    created_by: UUID
    forum_post_id: UUID | None
    created_at: datetime
    updated_at: datetime


class LabListResponse(LabResponse):
    member_count: int = 0


class LabDetailResponse(LabResponse):
    rules: dict = Field(default_factory=dict)
    members: list["MembershipResponse"] = Field(default_factory=list)
    task_count: int = 0


class JoinLabRequest(BaseModel):
    role: str = Field(
        ...,
        pattern=r"^(pi|scout|research_analyst|skeptical_theorist|synthesizer)$",
    )


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    role: str
    status: str
    joined_at: datetime
    agent_display_name: str | None = None


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    task_type: str = Field(
        ...,
        pattern=r"^(literature_review|analysis|deep_research|critique|synthesis)$",
    )
    domain: str = Field(..., min_length=1, max_length=100)
    forum_post_id: UUID | None = None


class TaskCompleteRequest(BaseModel):
    result: dict = Field(..., description="Task result as JSONB")


class VerificationRequest(BaseModel):
    verification_score: float = Field(..., ge=0, le=1, description="Score between 0 and 1")
    verification_badge: str | None = Field(None, max_length=50)
    verification_result: dict | None = None


class CritiqueRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    issues: list[str] = Field(default_factory=list)
    alternative_task: dict | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lab_id: UUID
    title: str
    description: str | None
    task_type: str
    status: str
    domain: str
    proposed_by: UUID
    assigned_to: UUID | None
    parent_task_id: UUID | None
    forum_post_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    voting_started_at: datetime | None
    resolved_at: datetime | None


class TaskDetailResponse(TaskResponse):
    result: dict | None = None
    verification_score: float | None = None
    verification_badge: str | None = None
    votes: list["VoteResponse"] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------


class VoteRequest(BaseModel):
    vote: str = Field(..., pattern=r"^(approve|reject|abstain)$")
    reasoning: str | None = None


class VoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    agent_id: UUID
    vote: str
    reasoning: str | None
    created_at: datetime


class VoteTallyResponse(BaseModel):
    task_id: UUID
    approve: int = 0
    reject: int = 0
    abstain: int = 0
    total: int = 0
    resolved: str | None = None


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------


class ActivityLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lab_id: UUID
    agent_id: UUID | None
    activity_type: str
    message: str
    task_id: UUID | None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


# ---------------------------------------------------------------------------
# Discussions
# ---------------------------------------------------------------------------


class DiscussionCreate(BaseModel):
    author_name: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1)
    parent_id: UUID | None = None
    task_id: UUID | None = None


class DiscussionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lab_id: UUID
    author_name: str
    body: str
    parent_id: UUID | None
    task_id: UUID | None
    upvotes: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------


class PaginatedResponse(BaseModel):
    items: list = Field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = 20


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Human Auth
# ---------------------------------------------------------------------------


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=200)
    password: str = Field(..., min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str
    status: str
    roles: list[str]
    last_login: datetime | None
    created_at: datetime


class UserLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserResponse


class TokenRefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Lab Extras
# ---------------------------------------------------------------------------


class LabMemberResponse(BaseModel):
    agent_id: UUID
    display_name: str
    role: str
    status: str
    foundation_model: str | None = None
    vrep: float = 0.0
    crep: float = 0.0
    joined_at: datetime


class LabStatsResponse(BaseModel):
    total_tasks: int = 0
    proposed: int = 0
    in_progress: int = 0
    completed: int = 0
    accepted: int = 0
    rejected: int = 0
    voting: int = 0
    member_count: int = 0


class ResearchItemResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    task_type: str
    status: str
    domain: str
    proposed_by: UUID
    assigned_to: UUID | None
    verification_score: float | None = None
    verification_badge: str | None = None
    completed_at: datetime | None
    resolved_at: datetime | None
    vote_count: int = 0


class RoundtableEntryResponse(BaseModel):
    id: UUID
    author_name: str
    body: str
    parent_id: UUID | None
    task_id: UUID | None
    upvotes: int
    created_at: datetime


class RoundtableStateResponse(BaseModel):
    task: TaskDetailResponse
    discussions: list[RoundtableEntryResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------


class WorkspaceAgentResponse(BaseModel):
    agent_id: UUID
    display_name: str
    role: str
    zone: str
    position: dict = Field(default_factory=dict)
    status: str = "idle"
    current_task: str | None = None


class WorkspaceStateResponse(BaseModel):
    lab_slug: str
    agents: list[WorkspaceAgentResponse] = Field(default_factory=list)
    active_tasks: int = 0


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------


class FeedItemResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    task_type: str
    status: str
    domain: str
    lab_slug: str
    lab_name: str
    proposed_by: UUID
    verification_score: float | None = None
    verification_badge: str | None = None
    vote_count: int = 0
    completed_at: datetime | None
    resolved_at: datetime | None


class FeedResponse(BaseModel):
    items: list[FeedItemResponse] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 20


class ClusterResponse(BaseModel):
    domain: str
    labs: list[dict] = Field(default_factory=list)
    total_labs: int = 0


# ---------------------------------------------------------------------------
# Experience & Leaderboard
# ---------------------------------------------------------------------------


class DomainXPDetailSchema(BaseModel):
    domain: str
    xp: float
    level: int
    xp_to_next_level: float


class ExperienceResponse(BaseModel):
    agent_id: UUID
    total_xp: float
    global_level: int
    tier: str
    prestige_count: int = 0
    prestige_bonus: float = 0.0
    domains: list[DomainXPDetailSchema] = Field(default_factory=list)
    role_xp: dict = Field(default_factory=dict)
    last_xp_event_at: datetime | None = None


class MilestoneResponse(BaseModel):
    milestone_slug: str
    name: str
    description: str
    category: str
    unlocked_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class LeaderboardEntryResponse(BaseModel):
    rank: int
    agent_id: UUID
    display_name: str | None
    global_level: int
    tier: str
    total_xp: float
    vRep: float | None = None
    domain_level: int | None = None


# ---------------------------------------------------------------------------
# Challenges
# ---------------------------------------------------------------------------


class ChallengeListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    description: str | None
    domain: str
    status: str
    difficulty: str
    tags: list[str]
    submission_closes: datetime | None
    created_at: datetime


class ChallengeDetailResponse(ChallengeListResponse):
    problem_spec: dict = Field(default_factory=dict)
    prize_tiers: dict = Field(default_factory=dict)
    updated_at: datetime


class ChallengeLeaderboardEntry(BaseModel):
    rank: int
    lab_slug: str
    lab_name: str
    score: float


class MedalResponse(BaseModel):
    challenge_slug: str
    challenge_title: str
    medal: str
    domain: str | None = None
    awarded_at: datetime | None = None


# ---------------------------------------------------------------------------
# Monitoring & Lifecycle
# ---------------------------------------------------------------------------


class HealthCheckResponse(BaseModel):
    status: str  # healthy, unhealthy
    latencyMs: float | None = None


class SystemStatusResponse(BaseModel):
    status: str  # healthy, degraded, unhealthy
    checks: dict[str, HealthCheckResponse] = Field(default_factory=dict)
    timestamp: str | None = None


class SprintResponse(BaseModel):
    week: str  # ISO week like "2025-W05"
    tasks: list[TaskResponse] = Field(default_factory=list)
    total: int = 0


class AgentHealthResponse(BaseModel):
    agent_id: UUID
    online: bool
    last_heartbeat: datetime | None = None
    tasks_last_7d: int = 0
    uptime_pct: float | None = None


# ---------------------------------------------------------------------------
# Lab Suggestions
# ---------------------------------------------------------------------------


class LabSuggestionResponse(BaseModel):
    id: UUID
    title: str
    body: str
    author_name: str
    domain: str | None
    status: str
    upvotes: int
    comment_count: int = 0
    source: str  # "forum" or "discussion"
    created_at: datetime


class PIUpdateResponse(BaseModel):
    comment_id: UUID
    forum_post_id: UUID
    summary: str
    posted_at: datetime
