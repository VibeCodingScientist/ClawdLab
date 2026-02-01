"""Pydantic schemas for Agent Registry API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from platform.shared.schemas.base import Domain


# ===========================================
# REGISTRATION SCHEMAS
# ===========================================


class RegistrationInitiateRequest(BaseModel):
    """Request to initiate agent registration."""

    public_key: str = Field(
        ...,
        description="PEM-encoded Ed25519 public key",
        examples=["-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA..."],
    )
    display_name: str | None = Field(
        None,
        max_length=255,
        description="Human-readable display name",
    )
    agent_type: str = Field(
        default="openclaw",
        description="Type of agent",
        examples=["openclaw", "custom"],
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="List of domain capabilities",
        examples=[["mathematics", "ml_ai"]],
    )
    metadata: dict | None = Field(
        default=None,
        description="Additional agent metadata",
    )

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v):
        valid_domains = {d.value for d in Domain}
        invalid = set(v) - valid_domains
        if invalid:
            raise ValueError(f"Invalid capabilities: {invalid}. Valid: {valid_domains}")
        return v

    @field_validator("public_key")
    @classmethod
    def validate_public_key(cls, v):
        if not v.startswith("-----BEGIN PUBLIC KEY-----"):
            raise ValueError("Public key must be PEM-encoded")
        return v


class RegistrationChallengeResponse(BaseModel):
    """Response containing the registration challenge."""

    challenge_id: str = Field(..., description="Unique challenge identifier")
    challenge_nonce: str = Field(..., description="Nonce to sign with private key")
    message_to_sign: str = Field(
        ...,
        description="Complete message to sign: 'register:{nonce}'",
    )
    expires_at: datetime = Field(..., description="Challenge expiration time")
    instructions: str = Field(
        default="Sign the message_to_sign with your Ed25519 private key and submit to /register/complete",
    )


class RegistrationCompleteRequest(BaseModel):
    """Request to complete registration with signed challenge."""

    challenge_id: str = Field(..., description="Challenge ID from initiate response")
    signature: str = Field(
        ...,
        description="Base64-encoded Ed25519 signature of the message",
    )


class RegistrationCompleteResponse(BaseModel):
    """Response after successful registration."""

    agent_id: str = Field(..., description="Unique agent identifier")
    display_name: str | None
    agent_type: str
    capabilities: list[str]
    status: str
    created_at: datetime
    token: str = Field(..., description="API token for authentication")
    token_expires_at: datetime


# ===========================================
# AGENT SCHEMAS
# ===========================================


class AgentCapabilityResponse(BaseModel):
    """Agent capability information."""

    domain: str
    capability_level: str
    verified_at: datetime | None = None


class AgentResponse(BaseModel):
    """Agent profile response."""

    model_config = ConfigDict(from_attributes=True)

    agent_id: str = Field(..., alias="id")
    display_name: str | None
    agent_type: str
    status: str
    capabilities: list[AgentCapabilityResponse] = []
    created_at: datetime
    updated_at: datetime

    @field_validator("agent_id", mode="before")
    @classmethod
    def convert_uuid(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v


class AgentPublicResponse(BaseModel):
    """Public agent profile (limited info)."""

    agent_id: str
    display_name: str | None
    agent_type: str
    capabilities: list[str]
    created_at: datetime


class AgentUpdateRequest(BaseModel):
    """Request to update agent profile."""

    display_name: str | None = Field(None, max_length=255)
    metadata: dict | None = None


class CapabilityUpdateRequest(BaseModel):
    """Request to update agent capabilities."""

    add_capabilities: list[str] = Field(default_factory=list)
    remove_capabilities: list[str] = Field(default_factory=list)

    @field_validator("add_capabilities", "remove_capabilities")
    @classmethod
    def validate_capabilities(cls, v):
        valid_domains = {d.value for d in Domain}
        invalid = set(v) - valid_domains
        if invalid:
            raise ValueError(f"Invalid capabilities: {invalid}")
        return v


# ===========================================
# TOKEN SCHEMAS
# ===========================================


class TokenCreateRequest(BaseModel):
    """Request to create a new API token."""

    name: str = Field(..., max_length=255, description="Token name for identification")
    scopes: list[str] = Field(
        default=["read", "write"],
        description="Permission scopes",
    )
    expires_in_days: int = Field(
        default=365,
        ge=1,
        le=730,
        description="Token validity in days",
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v):
        valid_scopes = {"read", "write", "admin", "verify", "challenge"}
        invalid = set(v) - valid_scopes
        if invalid:
            raise ValueError(f"Invalid scopes: {invalid}")
        return v


class TokenResponse(BaseModel):
    """Token information response."""

    token_id: str
    token_prefix: str = Field(..., description="First 12 characters for identification")
    name: str | None
    scopes: list[str]
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    is_revoked: bool = False


class TokenCreateResponse(BaseModel):
    """Response after creating a token."""

    token: str = Field(..., description="Full token (only shown once)")
    token_id: str
    token_prefix: str
    name: str
    scopes: list[str]
    expires_at: datetime


class TokenListResponse(BaseModel):
    """List of tokens for an agent."""

    tokens: list[TokenResponse]
    total: int


# ===========================================
# ERROR SCHEMAS
# ===========================================


class ErrorResponse(BaseModel):
    """Standard error response (RFC 7807)."""

    type: str = Field(..., description="Error type URI")
    title: str = Field(..., description="Short error description")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Detailed error message")
    instance: str | None = Field(None, description="Request path")
