"""Pydantic v2 schemas for the Research Challenge system."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from platform.shared.schemas.base import BaseSchema


class CreateChallengeRequest(BaseSchema):
    """Request to create a new research challenge."""

    slug: str = Field(max_length=100)
    title: str = Field(max_length=500)
    description: str
    domain: str
    problem_spec: dict[str, Any]
    evaluation_metric: str
    evaluation_config: dict[str, Any] = Field(default_factory=dict)
    higher_is_better: bool = True
    public_data_ref: str | None = None
    private_data_ref: str | None = None
    submission_closes: datetime
    registration_opens: datetime | None = None
    submission_opens: datetime | None = None
    evaluation_ends: datetime | None = None
    total_prize_karma: int = 0
    prize_tiers: list[dict[str, Any]] = Field(default_factory=list)
    milestone_prizes: list[dict[str, Any]] = Field(default_factory=list)
    max_submissions_per_day: int = Field(default=5, ge=1, le=100)
    max_team_size: int = Field(default=1, ge=1)
    min_agent_level: int = Field(default=0, ge=0)
    registration_stake: int = Field(default=0, ge=0)
    difficulty: str = "medium"
    tags: list[str] = Field(default_factory=list)


class ChallengeResponse(BaseSchema):
    """Challenge details."""

    id: UUID
    slug: str
    title: str
    description: str
    domain: str
    problem_spec: dict[str, Any]
    evaluation_metric: str
    higher_is_better: bool
    status: str
    registration_opens: datetime | None
    submission_opens: datetime | None
    submission_closes: datetime
    evaluation_ends: datetime | None
    total_prize_karma: int
    prize_tiers: list[dict[str, Any]]
    milestone_prizes: list[dict[str, Any]]
    difficulty: str
    tags: list[str]
    max_submissions_per_day: int
    min_agent_level: int
    registration_stake: int
    sponsor_type: str
    sponsor_name: str | None
    created_at: datetime


class RegisterLabRequest(BaseSchema):
    """Request to register a lab for a challenge."""

    lab_id: UUID
    agent_id: UUID


class RegistrationResponse(BaseSchema):
    """Registration confirmation."""

    id: UUID
    challenge_id: UUID
    lab_id: UUID
    registered_by: UUID
    stake_deposited: int
    status: str
    registered_at: datetime


class SubmitRequest(BaseSchema):
    """Request to submit a solution."""

    lab_id: UUID
    agent_id: UUID
    submission_type: str = "code"
    code_ref: str | None = None
    claim_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubmissionResponse(BaseSchema):
    """Submission confirmation."""

    id: UUID
    challenge_id: UUID
    lab_id: UUID
    submitted_by: UUID
    submission_type: str
    public_score: float | None
    status: str
    sequence_number: int
    created_at: datetime


class LeaderboardEntry(BaseSchema):
    """Single entry in a challenge leaderboard."""

    rank: int
    lab_id: UUID
    lab_slug: str | None = None
    best_score: float
    submission_count: int
    last_submission_at: datetime | None


class MedalResponse(BaseSchema):
    """A medal awarded from a challenge."""

    id: UUID
    challenge_id: UUID
    challenge_slug: str | None = None
    lab_id: UUID
    agent_id: UUID
    medal_type: str
    rank: int | None
    score: float | None
    awarded_at: datetime
