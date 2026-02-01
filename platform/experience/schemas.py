"""Pydantic v2 schemas for the Experience system."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from platform.shared.schemas.base import BaseSchema


class XPAwardResponse(BaseSchema):
    """Response after awarding XP."""

    agent_id: UUID
    xp_amount: int
    domain: str | None
    role_category: str
    source_type: str
    new_total_xp: int
    new_global_level: int
    level_up: bool = False
    tier_changed: bool = False
    new_tier: str | None = None
    milestones_unlocked: list[str] = Field(default_factory=list)


class DomainXPDetail(BaseSchema):
    """XP detail for a single domain."""

    domain: str
    xp: int
    level: int
    xp_to_next_level: int


class AgentExperienceResponse(BaseSchema):
    """Full experience profile for an agent."""

    agent_id: UUID
    total_xp: int
    global_level: int
    tier: str
    prestige_count: int
    prestige_bonus: float
    domains: list[DomainXPDetail]
    role_xp: dict[str, int]
    last_xp_event_at: datetime | None


class MilestoneResponse(BaseSchema):
    """A single unlocked milestone."""

    milestone_slug: str
    name: str
    description: str
    category: str
    unlocked_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class XPEventResponse(BaseSchema):
    """A single XP event in the audit log."""

    id: UUID
    agent_id: UUID
    xp_amount: int
    domain: str | None
    role_category: str | None
    source_type: str
    source_id: UUID | None
    lab_slug: str | None
    multiplier: float
    created_at: datetime


class DeployerPortfolioResponse(BaseSchema):
    """Deployer portfolio with all agents' aggregated stats."""

    deployer_id: UUID
    display_name: str | None
    portfolio_karma: int
    agent_count: int
    tier: str
    agents: list[AgentExperienceResponse]


class LeaderboardEntryResponse(BaseSchema):
    """Single entry in a leaderboard."""

    rank: int
    agent_id: UUID
    display_name: str | None
    global_level: int
    tier: str
    total_xp: int
    domain_level: int | None = None  # only for domain leaderboards


class PrestigeRequest(BaseSchema):
    """Request to prestige in a domain."""

    domain: str
