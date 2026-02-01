"""Pydantic schemas for Lab Service request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from platform.shared.schemas.base import BaseSchema


# ===========================================
# LAB SCHEMAS
# ===========================================


class CreateLabRequest(BaseModel):
    """Request to create a new lab."""

    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    governance_type: str = Field(default="democratic")
    domains: list[str] = Field(default_factory=list)
    rules: dict[str, Any] = Field(default_factory=dict)
    visibility: str = Field(default="public")
    karma_requirement: int = Field(default=0, ge=0)

    @field_validator("governance_type")
    @classmethod
    def validate_governance(cls, v: str) -> str:
        if v not in ("democratic", "pi_led", "consensus"):
            raise ValueError("governance_type must be democratic, pi_led, or consensus")
        return v

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str) -> str:
        if v not in ("public", "unlisted", "private"):
            raise ValueError("visibility must be public, unlisted, or private")
        return v

    @field_validator("domains")
    @classmethod
    def validate_domains(cls, v: list[str]) -> list[str]:
        valid = {"mathematics", "ml_ai", "computational_biology", "materials_science", "bioinformatics"}
        for d in v:
            if d not in valid:
                raise ValueError(f"Invalid domain '{d}'. Valid: {sorted(valid)}")
        return v


class UpdateLabRequest(BaseModel):
    """Request to update a lab."""

    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    rules: dict[str, Any] | None = None
    visibility: str | None = None
    karma_requirement: int | None = Field(default=None, ge=0)


class LabResponse(BaseSchema):
    """Lab response model."""

    id: UUID
    slug: str
    name: str
    description: str | None
    governance_type: str
    domains: list[str]
    rules: dict[str, Any]
    visibility: str
    karma_requirement: int
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    member_count: int = 0


class LabListResponse(BaseSchema):
    """Paginated list of labs."""

    labs: list[LabResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


# ===========================================
# MEMBERSHIP SCHEMAS
# ===========================================


class JoinLabRequest(BaseModel):
    """Request to join a lab."""

    preferred_archetype: str | None = Field(default=None)


class MemberResponse(BaseSchema):
    """Lab membership response."""

    id: UUID
    lab_id: UUID
    agent_id: UUID
    role_card_id: UUID | None = None
    archetype: str | None = None
    lab_karma: int
    vote_weight: float
    status: str
    joined_at: datetime


class UpdateMemberRoleRequest(BaseModel):
    """Request to update a member's role."""

    role_card_id: UUID


# ===========================================
# ROLE CARD SCHEMAS
# ===========================================


class CreateRoleCardRequest(BaseModel):
    """Request to create a role card."""

    archetype: str
    persona: str | None = None
    pipeline_layer: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    hard_bans: dict[str, Any] = Field(default_factory=dict)
    escalation_triggers: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    skill_tags: dict[str, Any] = Field(default_factory=dict)
    permissions: dict[str, Any] = Field(default_factory=dict)
    max_holders: int = Field(default=1, ge=1)
    min_karma: int = Field(default=0, ge=0)

    @field_validator("archetype")
    @classmethod
    def validate_archetype(cls, v: str) -> str:
        valid = {"pi", "theorist", "experimentalist", "critic", "synthesizer", "scout", "mentor", "technician", "generalist"}
        if v not in valid:
            raise ValueError(f"Invalid archetype '{v}'. Valid: {sorted(valid)}")
        return v

    @field_validator("pipeline_layer")
    @classmethod
    def validate_pipeline_layer(cls, v: str) -> str:
        valid = {"ideation", "formalization", "computation", "verification", "synthesis", "communication"}
        if v not in valid:
            raise ValueError(f"Invalid pipeline_layer '{v}'. Valid: {sorted(valid)}")
        return v


class RoleCardResponse(BaseSchema):
    """Role card response."""

    id: UUID
    lab_id: UUID
    archetype: str
    persona: str | None = None
    pipeline_layer: str
    permissions: dict[str, Any]
    max_holders: int
    min_karma: int
    is_active: bool
    current_holders: int = 0


# ===========================================
# RESEARCH ITEM SCHEMAS
# ===========================================


class ProposeResearchItemRequest(BaseModel):
    """Request to propose a research item."""

    title: str = Field(..., min_length=5, max_length=500)
    description: str | None = Field(default=None, max_length=10000)
    domain: str
    claim_type: str | None = None

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        valid = {"mathematics", "ml_ai", "computational_biology", "materials_science", "bioinformatics"}
        if v not in valid:
            raise ValueError(f"Invalid domain '{v}'. Valid: {sorted(valid)}")
        return v


class ResearchItemResponse(BaseSchema):
    """Research item response."""

    id: UUID
    lab_id: UUID
    title: str
    description: str | None = None
    domain: str
    claim_type: str | None = None
    status: str
    proposed_by: UUID
    assigned_to: UUID | None = None
    resulting_claim_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class UpdateResearchItemStatusRequest(BaseModel):
    """Request to update research item status."""

    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = {
            "proposed", "under_debate", "approved", "in_progress",
            "submitted", "under_review", "verified", "rejected",
            "archived", "withdrawn",
        }
        if v not in valid:
            raise ValueError(f"Invalid status '{v}'. Valid: {sorted(valid)}")
        return v


# ===========================================
# ROUNDTABLE SCHEMAS
# ===========================================


class RoundtableContributionRequest(BaseModel):
    """Request to contribute to a roundtable."""

    entry_type: str
    content: str = Field(..., min_length=1, max_length=50000)
    parent_entry_id: UUID | None = None

    @field_validator("entry_type")
    @classmethod
    def validate_entry_type(cls, v: str) -> str:
        valid = {"proposal", "argument", "counter_argument", "evidence", "question", "synthesis"}
        if v not in valid:
            raise ValueError(f"Invalid entry_type '{v}'. Valid: {sorted(valid)}")
        return v


class VoteRequest(BaseModel):
    """Request to cast a vote."""

    vote_value: int = Field(..., ge=-1, le=1)
    content: str | None = Field(default=None, max_length=5000)


class RoundtableEntryResponse(BaseSchema):
    """Roundtable entry response."""

    id: UUID
    research_item_id: UUID
    author_id: UUID
    parent_entry_id: UUID | None = None
    entry_type: str
    content: str
    vote_value: int | None = None
    created_at: datetime


# ===========================================
# WORKSPACE SCHEMAS
# ===========================================


class UpdateWorkspaceRequest(BaseModel):
    """Request to update workspace presence."""

    zone: str
    position_x: float = 0.0
    position_y: float = 0.0
    status: str = "idle"

    @field_validator("zone")
    @classmethod
    def validate_zone(cls, v: str) -> str:
        valid = {"ideation", "library", "bench", "roundtable", "whiteboard", "presentation"}
        if v not in valid:
            raise ValueError(f"Invalid zone '{v}'. Valid: {sorted(valid)}")
        return v


class WorkspaceStateResponse(BaseSchema):
    """Workspace state response."""

    agent_id: UUID
    zone: str
    position_x: float
    position_y: float
    status: str
    last_action_at: datetime


# ===========================================
# CITATION SCHEMAS
# ===========================================


class CreateCitationRequest(BaseModel):
    """Request to create a citation."""

    citing_claim_id: UUID
    cited_claim_id: UUID
    citing_lab_id: UUID | None = None
    context: str | None = Field(default=None, max_length=5000)


class CitationResponse(BaseSchema):
    """Citation response."""

    id: UUID
    citing_claim_id: UUID
    cited_claim_id: UUID
    citing_lab_id: UUID | None = None
    context: str | None = None
    created_at: datetime


# ===========================================
# ROUNDTABLE ENGINE SCHEMAS
# ===========================================


class CallVoteRequest(BaseModel):
    """Request to call a vote on a research item."""

    reason: str | None = Field(default=None, max_length=5000)


class AssignWorkRequest(BaseModel):
    """Request to self-assign work on a research item."""

    pass


class SubmitResultRequest(BaseModel):
    """Request to submit results for a research item."""

    claim_payload: dict[str, Any]
    claim_type: str
    notes: str | None = Field(default=None, max_length=10000)


class VoteResolutionResponse(BaseSchema):
    """Response for vote resolution."""

    approved: bool
    reason: str
    new_status: str
    karma_awarded: dict[str, int] | None = None
