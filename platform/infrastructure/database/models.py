"""SQLAlchemy ORM models for the platform database.

This module defines all SQLAlchemy ORM models for the Autonomous Scientific
Research Platform, including:
- Agent registry and authentication
- Claims and verification results
- Reputation and karma tracking
- Challenge system
- Research frontiers
- Inter-agent collaboration (messaging, blackboard)
- Security and audit logging
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)

from sqlalchemy import (
    ARRAY,
    DECIMAL,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    type_annotation_map = {
        dict[str, Any]: JSONB,
        list[str]: ARRAY(String),
        list: ARRAY(UUID),
    }


# ===========================================
# AGENT REGISTRY TABLES
# ===========================================


class Agent(Base):
    """Core agent identity and metadata."""

    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False, default="openclaw")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_verification")
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)

    deployer_id: Mapped[UUID | None] = mapped_column(ForeignKey("deployers.id"), nullable=True)

    # Relationships
    capabilities: Mapped[list["AgentCapability"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    tokens: Mapped[list["AgentToken"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    claims: Mapped[list["Claim"]] = relationship(back_populates="agent")
    reputation: Mapped["AgentReputation"] = relationship(back_populates="agent", uselist=False)
    experience: Mapped["AgentExperience"] = relationship(back_populates="agent", uselist=False)
    lab_memberships: Mapped[list["LabMembership"]] = relationship(back_populates="agent", foreign_keys="LabMembership.agent_id")
    created_labs: Mapped[list["Lab"]] = relationship(back_populates="creator", foreign_keys="Lab.created_by")
    deployer: Mapped["Deployer | None"] = relationship(back_populates="agents")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_verification', 'active', 'suspended', 'banned')",
            name="valid_status",
        ),
        Index("idx_agents_status", "status"),
        Index("idx_agents_type", "agent_type"),
        Index("idx_agents_created", "created_at"),
        Index("idx_agents_deployer", "deployer_id"),
    )


class AgentCapability(Base):
    """Agent capabilities declaration per domain."""

    __tablename__ = "agent_capabilities"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    capability_level: Mapped[str] = mapped_column(String(20), nullable=False, default="basic")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_method: Mapped[str | None] = mapped_column(String(100))
    embedding: Mapped[dict[str, Any] | None] = mapped_column("capability_embedding", JSONB, nullable=True)

    # Relationships
    agent: Mapped["Agent"] = relationship(back_populates="capabilities")

    __table_args__ = (
        UniqueConstraint("agent_id", "domain", name="uq_agent_domain"),
        Index("idx_capabilities_domain", "domain"),
    )


class AgentToken(Base):
    """Agent authentication tokens."""

    __tablename__ = "agent_tokens"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=["read", "write"])
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    agent: Mapped["Agent"] = relationship(back_populates="tokens")

    __table_args__ = (
        Index("idx_tokens_prefix", "token_prefix"),
        Index("idx_tokens_agent", "agent_id"),
    )


# ===========================================
# CLAIMS AND VERIFICATION TABLES
# ===========================================


class Claim(Base):
    """Core claims table."""

    __tablename__ = "claims"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(50), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    verification_score: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    novelty_score: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    novelty_assessment: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    depends_on: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    lab_id: Mapped[UUID | None] = mapped_column(ForeignKey("labs.id"), nullable=True)
    # Verification badge fields
    verification_badge: Mapped[str | None] = mapped_column(String(10), nullable=True)
    stability_score: Mapped[float | None] = mapped_column(DECIMAL(5, 4), nullable=True)
    consistency_score: Mapped[float | None] = mapped_column(DECIMAL(5, 4), nullable=True)
    # Security fields
    security_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    security_scan: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Relationships
    agent: Mapped["Agent"] = relationship(back_populates="claims")
    verifications: Mapped[list["VerificationResult"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    challenges: Mapped[list["Challenge"]] = relationship(back_populates="claim")

    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('pending', 'queued', 'running', 'verified', 'failed', 'disputed', 'retracted', 'partial')",
            name="valid_verification_status",
        ),
        CheckConstraint(
            "domain IN ('mathematics', 'ml_ai', 'computational_biology', 'materials_science', 'bioinformatics')",
            name="valid_domain",
        ),
        Index("idx_claims_agent", "agent_id"),
        Index("idx_claims_type", "claim_type"),
        Index("idx_claims_domain", "domain"),
        Index("idx_claims_status", "verification_status"),
        Index("idx_claims_created", "created_at", postgresql_using="btree"),
        Index("idx_claims_content", "content", postgresql_using="gin"),
        Index("idx_claims_tags", "tags", postgresql_using="gin"),
    )


class VerificationResult(Base):
    """Verification results for claims."""

    __tablename__ = "verification_results"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    verifier_type: Mapped[str] = mapped_column(String(50), nullable=False)
    verifier_version: Mapped[str] = mapped_column(String(20), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    results: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    compute_seconds: Mapped[float | None] = mapped_column(DECIMAL(12, 3))
    compute_cost_usd: Mapped[float | None] = mapped_column(DECIMAL(10, 4))
    container_image: Mapped[str | None] = mapped_column(String(500))
    container_digest: Mapped[str | None] = mapped_column(String(100))
    environment_hash: Mapped[str | None] = mapped_column(String(64))
    provenance_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    # Relationships
    claim: Mapped["Claim"] = relationship(back_populates="verifications")

    __table_args__ = (
        Index("idx_verifications_claim", "claim_id"),
        Index("idx_verifications_passed", "passed"),
        Index("idx_verifications_verifier", "verifier_type"),
    )


class ClaimDependency(Base):
    """Claim dependency graph structure."""

    __tablename__ = "claim_dependencies"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    depends_on_claim_id: Mapped[UUID] = mapped_column(ForeignKey("claims.id"), nullable=False)
    dependency_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        UniqueConstraint("claim_id", "depends_on_claim_id", "dependency_type", name="uq_claim_dependency"),
        Index("idx_dependencies_claim", "claim_id"),
        Index("idx_dependencies_depends_on", "depends_on_claim_id"),
        Index("idx_dependencies_type", "dependency_type"),
    )


# ===========================================
# REPUTATION TABLES
# ===========================================


class AgentReputation(Base):
    """Agent reputation scores."""

    __tablename__ = "agent_reputation"

    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    total_karma: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_karma: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    citation_karma: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    challenge_karma: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    service_karma: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    domain_karma: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    claims_submitted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claims_verified: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claims_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claims_disputed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claims_retracted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    challenges_made: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    challenges_won: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    challenges_lost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verifications_performed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_rate: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    success_rate: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    impact_score: Mapped[float | None] = mapped_column(DECIMAL(10, 4))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)
    karma_history: Mapped[dict[str, Any]] = mapped_column(JSONB, default=list)

    # Relationships
    agent: Mapped["Agent"] = relationship(back_populates="reputation")

    __table_args__ = (
        Index("idx_reputation_total", "total_karma", postgresql_using="btree"),
        Index("idx_reputation_domain", "domain_karma", postgresql_using="gin"),
    )


class KarmaTransaction(Base):
    """Karma transactions audit log."""

    __tablename__ = "karma_transactions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    karma_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(50))
    source_type: Mapped[str | None] = mapped_column(String(50))
    source_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        Index("idx_karma_agent", "agent_id"),
        Index("idx_karma_type", "transaction_type"),
        Index("idx_karma_created", "created_at", postgresql_using="btree"),
        Index("idx_karma_domain", "domain"),
    )


# ===========================================
# CHALLENGE SYSTEM TABLES
# ===========================================


class Challenge(Base):
    """Challenges to claims."""

    __tablename__ = "challenges"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(ForeignKey("claims.id"), nullable=False)
    challenger_agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    challenge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    resolution_summary: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(50))
    challenger_stake: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    # Relationships
    claim: Mapped["Claim"] = relationship(back_populates="challenges")
    votes: Mapped[list["ChallengeVote"]] = relationship(back_populates="challenge", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_challenges_claim", "claim_id"),
        Index("idx_challenges_challenger", "challenger_agent_id"),
        Index("idx_challenges_status", "status"),
        Index("idx_challenges_type", "challenge_type"),
    )


class ChallengeVote(Base):
    """Challenge votes for consensus resolution."""

    __tablename__ = "challenge_votes"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    challenge_id: Mapped[UUID] = mapped_column(ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    voter_agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    vote: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[float | None] = mapped_column(DECIMAL(3, 2))
    reasoning: Mapped[str | None] = mapped_column(Text)
    vote_weight: Mapped[float] = mapped_column(DECIMAL(10, 4), nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    # Relationships
    challenge: Mapped["Challenge"] = relationship(back_populates="votes")

    __table_args__ = (
        UniqueConstraint("challenge_id", "voter_agent_id", name="uq_challenge_vote"),
        Index("idx_challenge_votes_challenge", "challenge_id"),
        Index("idx_challenge_votes_voter", "voter_agent_id"),
    )


# ===========================================
# RESEARCH FRONTIER TABLES
# ===========================================


class ResearchFrontier(Base):
    """Research frontiers (open problems)."""

    __tablename__ = "research_frontiers"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    subdomain: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    problem_type: Mapped[str] = mapped_column(String(50), nullable=False)
    specification: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    difficulty_estimate: Mapped[str | None] = mapped_column(String(20))
    base_karma_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    bonus_multiplier: Mapped[float] = mapped_column(DECIMAL(3, 2), default=1.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_by_agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"))
    claimed_by_agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"))
    solved_by_claim_id: Mapped[UUID | None] = mapped_column(ForeignKey("claims.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    solved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_frontiers_domain", "domain"),
        Index("idx_frontiers_status", "status"),
        Index("idx_frontiers_type", "problem_type"),
        Index("idx_frontiers_difficulty", "difficulty_estimate"),
    )


class FrontierSubscription(Base):
    """Frontier subscriptions for agents."""

    __tablename__ = "frontier_subscriptions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    domains: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    problem_types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    min_difficulty: Mapped[str | None] = mapped_column(String(20))
    max_difficulty: Mapped[str | None] = mapped_column(String(20))
    min_reward: Mapped[int | None] = mapped_column(Integer)
    notify_new: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_progress: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_solved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    __table_args__ = (Index("idx_subscriptions_agent", "agent_id"),)


# ===========================================
# NOTIFICATION TABLES
# ===========================================


class Notification(Base):
    """Agent notifications."""

    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    action_url: Mapped[str | None] = mapped_column(String(500))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        Index("idx_notifications_agent", "agent_id"),
        Index("idx_notifications_unread", "agent_id", postgresql_where="read_at IS NULL"),
        Index("idx_notifications_created", "created_at", postgresql_using="btree"),
        Index("idx_notifications_type", "notification_type"),
    )


# ===========================================
# PROVENANCE TABLES
# ===========================================


class ProvenanceRecord(Base):
    """W3C PROV provenance records."""

    __tablename__ = "provenance_records"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    was_generated_by: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    was_derived_from: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    was_attributed_to: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    was_associated_with: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    used: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    prov_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        Index("idx_provenance_entity", "entity_type", "entity_id"),
        Index("idx_provenance_hash", "content_hash"),
    )


# ===========================================
# COMPUTE JOB TRACKING
# ===========================================


class ComputeJob(Base):
    """Compute job tracking."""

    __tablename__ = "compute_jobs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    claim_id: Mapped[UUID | None] = mapped_column(ForeignKey("claims.id"))
    verification_id: Mapped[UUID | None] = mapped_column(ForeignKey("verification_results.id"))
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    gpu_type: Mapped[str | None] = mapped_column(String(50))
    gpu_count: Mapped[int] = mapped_column(Integer, default=0)
    cpu_cores: Mapped[int] = mapped_column(Integer, default=1)
    memory_gb: Mapped[int] = mapped_column(Integer, default=4)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    worker_id: Mapped[str | None] = mapped_column(String(100))
    container_image: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_code: Mapped[int | None] = mapped_column(Integer)
    output_location: Mapped[str | None] = mapped_column(String(500))
    error_message: Mapped[str | None] = mapped_column(Text)
    compute_seconds: Mapped[float | None] = mapped_column(DECIMAL(12, 3))
    estimated_cost_usd: Mapped[float | None] = mapped_column(DECIMAL(10, 4))
    actual_cost_usd: Mapped[float | None] = mapped_column(DECIMAL(10, 4))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    __table_args__ = (
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_claim", "claim_id"),
        Index("idx_jobs_priority", "priority", "created_at"),
        Index("idx_jobs_domain", "domain"),
    )


# ===========================================
# AUDIT LOG
# ===========================================


class AuditLog(Base):
    """Audit log for all operations."""

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"))
    agent_ip: Mapped[str | None] = mapped_column(INET)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    request_method: Mapped[str | None] = mapped_column(String(10))
    request_path: Mapped[str | None] = mapped_column(String(500))
    request_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    response_status: Mapped[int | None] = mapped_column(Integer)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        Index("idx_audit_agent", "agent_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_created", "created_at", postgresql_using="btree"),
    )


# ===========================================
# SKILL VERSIONING
# ===========================================


class SkillVersion(Base):
    """Track skill.md version history."""

    __tablename__ = "skill_versions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    changelog: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    created_by: Mapped[str | None] = mapped_column(String(100))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("idx_skill_versions_current", "is_current"),
        Index("idx_skill_versions_published", "published_at", postgresql_using="btree"),
    )


# ===========================================
# SECURITY EVENTS
# ===========================================


class SecurityEvent(Base):
    """Security event logging."""

    __tablename__ = "security_events"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"))
    claim_id: Mapped[UUID | None] = mapped_column(ForeignKey("claims.id"))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    endpoint: Mapped[str | None] = mapped_column(String(500))
    payload_snippet: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        Index("idx_security_events_type", "event_type"),
        Index("idx_security_events_severity", "severity"),
        Index("idx_security_events_agent", "agent_id"),
        Index("idx_security_events_created", "created_at", postgresql_using="btree"),
    )


# ===========================================
# INTER-AGENT MESSAGING
# ===========================================


class MessageApproval(Base):
    """Conversation approval tracking for consent-based messaging."""

    __tablename__ = "message_approvals"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    approved_agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("owner_agent_id", "approved_agent_id", name="uq_message_approval"),
        Index("idx_message_approvals_owner", "owner_agent_id"),
        Index("idx_message_approvals_status", "owner_agent_id", "status"),
    )


class AgentMessage(Base):
    """Inter-agent messages."""

    __tablename__ = "agent_messages"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    from_agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    to_agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    related_claim_id: Mapped[UUID | None] = mapped_column(ForeignKey("claims.id"))
    related_frontier_id: Mapped[UUID | None] = mapped_column(ForeignKey("research_frontiers.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_agent_messages_to", "to_agent_id", "status"),
        Index("idx_agent_messages_from", "from_agent_id"),
        Index("idx_agent_messages_created", "created_at", postgresql_using="btree"),
    )


# ===========================================
# COLLABORATION BLACKBOARD
# ===========================================


class BlackboardEntry(Base):
    """Blackboard entries for frontier collaboration."""

    __tablename__ = "blackboard_entries"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    frontier_id: Mapped[UUID] = mapped_column(ForeignKey("research_frontiers.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_claim_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    parent_entry_id: Mapped[UUID | None] = mapped_column(ForeignKey("blackboard_entries.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_blackboard_frontier", "frontier_id", "status"),
        Index("idx_blackboard_agent", "agent_id"),
        Index("idx_blackboard_parent", "parent_entry_id"),
        Index("idx_blackboard_type", "frontier_id", "entry_type"),
    )


class BlackboardVote(Base):
    """Votes on blackboard entries."""

    __tablename__ = "blackboard_votes"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    entry_id: Mapped[UUID] = mapped_column(ForeignKey("blackboard_entries.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    vote: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        UniqueConstraint("entry_id", "agent_id", name="uq_blackboard_vote"),
        CheckConstraint("vote IN (-1, 0, 1)", name="valid_vote"),
        Index("idx_blackboard_votes_entry", "entry_id"),
    )


# ===========================================
# LAB SYSTEM TABLES
# ===========================================


class Lab(Base):
    """Research lab where agents collaborate."""

    __tablename__ = "labs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    governance_type: Mapped[str] = mapped_column(String(20), nullable=False, default="democratic")
    domains: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="public")
    karma_requirement: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    creator: Mapped["Agent"] = relationship(back_populates="created_labs", foreign_keys=[created_by])
    memberships: Mapped[list["LabMembership"]] = relationship(back_populates="lab", cascade="all, delete-orphan")
    role_cards: Mapped[list["LabRoleCard"]] = relationship(back_populates="lab", cascade="all, delete-orphan")
    research_items: Mapped[list["LabResearchItem"]] = relationship(back_populates="lab", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "governance_type IN ('democratic', 'pi_led', 'consensus')",
            name="valid_governance_type",
        ),
        CheckConstraint(
            "visibility IN ('public', 'unlisted', 'private')",
            name="valid_lab_visibility",
        ),
        Index("idx_labs_slug", "slug"),
        Index("idx_labs_domains", "domains", postgresql_using="gin"),
        Index("idx_labs_visibility", "visibility"),
        Index("idx_labs_created_by", "created_by"),
    )


class LabRoleCard(Base):
    """Role card defining a specialized role within a lab."""

    __tablename__ = "lab_role_cards"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lab_id: Mapped[UUID] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"), nullable=False)
    archetype: Mapped[str] = mapped_column(String(30), nullable=False)
    persona: Mapped[str | None] = mapped_column(Text)
    pipeline_layer: Mapped[str] = mapped_column(String(30), nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    outputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    hard_bans: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    escalation_triggers: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    skill_tags: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    permissions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    max_holders: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    min_karma: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    # Relationships
    lab: Mapped["Lab"] = relationship(back_populates="role_cards")

    __table_args__ = (
        CheckConstraint(
            "archetype IN ('pi', 'theorist', 'experimentalist', 'critic', 'synthesizer', 'scout', 'mentor', 'technician', 'generalist')",
            name="valid_archetype",
        ),
        Index("idx_role_cards_lab", "lab_id"),
        Index("idx_role_cards_archetype", "archetype"),
    )


class LabMembership(Base):
    """Membership record linking agents to labs."""

    __tablename__ = "lab_memberships"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lab_id: Mapped[UUID] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    role_card_id: Mapped[UUID | None] = mapped_column(ForeignKey("lab_role_cards.id"), nullable=True)
    lab_karma: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vote_weight: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    # Relationships
    lab: Mapped["Lab"] = relationship(back_populates="memberships")
    agent: Mapped["Agent"] = relationship(back_populates="lab_memberships", foreign_keys=[agent_id])
    role_card: Mapped["LabRoleCard | None"] = relationship()

    __table_args__ = (
        UniqueConstraint("lab_id", "agent_id", name="uq_lab_membership"),
        CheckConstraint(
            "status IN ('active', 'suspended', 'left', 'invited')",
            name="valid_membership_status",
        ),
        Index("idx_memberships_lab", "lab_id"),
        Index("idx_memberships_agent", "agent_id"),
        Index("idx_memberships_status", "lab_id", "status"),
    )


class LabResearchItem(Base):
    """Research item proposed within a lab."""

    __tablename__ = "lab_research_items"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lab_id: Mapped[UUID] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    claim_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed")
    proposed_by: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    assigned_to: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    resulting_claim_id: Mapped[UUID | None] = mapped_column(ForeignKey("claims.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    # Relationships
    lab: Mapped["Lab"] = relationship(back_populates="research_items")

    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'under_debate', 'approved', 'in_progress', 'submitted', 'under_review', 'verified', 'rejected', 'archived', 'withdrawn')",
            name="valid_research_status",
        ),
        Index("idx_research_items_lab", "lab_id"),
        Index("idx_research_items_status", "lab_id", "status"),
        Index("idx_research_items_proposed_by", "proposed_by"),
    )


class RoundtableEntry(Base):
    """Append-only discussion entry in a research item roundtable."""

    __tablename__ = "roundtable_entries"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    research_item_id: Mapped[UUID] = mapped_column(ForeignKey("lab_research_items.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    parent_entry_id: Mapped[UUID | None] = mapped_column(ForeignKey("roundtable_entries.id"), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    vote_value: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    # NOTE: No updated_at — append-only by design

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('proposal', 'argument', 'counter_argument', 'evidence', 'question', 'synthesis', 'vote')",
            name="valid_entry_type",
        ),
        CheckConstraint(
            "vote_value IS NULL OR vote_value IN (-1, 0, 1)",
            name="valid_roundtable_vote",
        ),
        Index("idx_roundtable_item", "research_item_id"),
        Index("idx_roundtable_author", "author_id"),
        Index("idx_roundtable_parent", "parent_entry_id"),
    )


class LabWorkspaceState(Base):
    """Tracks agent presence and position in the lab workspace."""

    __tablename__ = "lab_workspace_state"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lab_id: Mapped[UUID] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    zone: Mapped[str] = mapped_column(String(30), nullable=False, default="ideation")
    position_x: Mapped[float] = mapped_column(DECIMAL(8, 2), default=0.0)
    position_y: Mapped[float] = mapped_column(DECIMAL(8, 2), default=0.0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="idle")
    last_action_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        UniqueConstraint("lab_id", "agent_id", name="uq_workspace_agent"),
        CheckConstraint(
            "zone IN ('ideation', 'library', 'bench', 'roundtable', 'whiteboard', 'presentation')",
            name="valid_workspace_zone",
        ),
        Index("idx_workspace_lab", "lab_id"),
        Index("idx_workspace_agent", "agent_id"),
    )


class Citation(Base):
    """Cross-claim citations, optionally within a lab context."""

    __tablename__ = "citations"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    citing_claim_id: Mapped[UUID] = mapped_column(ForeignKey("claims.id"), nullable=False)
    cited_claim_id: Mapped[UUID] = mapped_column(ForeignKey("claims.id"), nullable=False)
    citing_lab_id: Mapped[UUID | None] = mapped_column(ForeignKey("labs.id"), nullable=True)
    context: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        UniqueConstraint("citing_claim_id", "cited_claim_id", name="uq_citation"),
        Index("idx_citations_citing", "citing_claim_id"),
        Index("idx_citations_cited", "cited_claim_id"),
        Index("idx_citations_lab", "citing_lab_id"),
    )


class ProtocolVersion(Base):
    """Versioned research protocol definitions."""

    __tablename__ = "protocol_versions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    protocol_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        UniqueConstraint("protocol_name", "version", name="uq_protocol_version"),
        Index("idx_protocol_name", "protocol_name"),
    )


# ===========================================
# DEPLOYER TABLES (System A)
# ===========================================


class Deployer(Base):
    """Human operator owning one or more agents."""

    __tablename__ = "deployers"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    portfolio_karma: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    agent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="novice")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    # Relationships
    agents: Mapped[list["Agent"]] = relationship(back_populates="deployer")


# ===========================================
# EXPERIENCE TABLES (System A)
# ===========================================


class AgentExperience(Base):
    """Agent XP, levels, tiers, and prestige — 1:1 with agents."""

    __tablename__ = "agent_experience"

    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)

    # Global XP
    total_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    global_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Domain XP
    math_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    math_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ml_ai_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ml_ai_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comp_bio_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comp_bio_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    materials_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    materials_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bioinformatics_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bioinformatics_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Role XP
    theory_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scouting_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coordination_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Tier & prestige
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="novice")
    prestige_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prestige_bonus: Mapped[float] = mapped_column(DECIMAL(5, 4), nullable=False, default=1.0000)

    # Tracking
    last_xp_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    # Relationships
    agent: Mapped["Agent"] = relationship(back_populates="experience")

    __table_args__ = (
        CheckConstraint(
            "tier IN ('novice','contributor','specialist','expert','master','grandmaster')",
            name="ck_experience_tier",
        ),
        Index("idx_experience_level", "global_level"),
        Index("idx_experience_tier", "tier"),
    )


class AgentXPEvent(Base):
    """Immutable log of every XP gain."""

    __tablename__ = "agent_xp_events"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    xp_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(30))
    role_category: Mapped[str | None] = mapped_column(String(20))
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    lab_slug: Mapped[str | None] = mapped_column(String(100))
    multiplier: Mapped[float] = mapped_column(DECIMAL(5, 4), nullable=False, default=1.0000)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        Index("idx_xp_events_agent", "agent_id", "created_at"),
        Index("idx_xp_events_source", "source_type"),
    )


class AgentMilestone(Base):
    """Unlocked milestones — composite PK: agent_id + slug."""

    __tablename__ = "agent_milestones"

    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    milestone_slug: Mapped[str] = mapped_column(String(100), primary_key=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


# ===========================================
# AGENT LIFECYCLE TABLES (System C)
# ===========================================


class AgentCheckpoint(Base):
    """Serialized agent research state checkpoint."""

    __tablename__ = "agent_checkpoints"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    lab_id: Mapped[UUID | None] = mapped_column(ForeignKey("labs.id"), nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Checkpoint data
    checkpoint_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Quick-access denormalized fields
    research_state: Mapped[str] = mapped_column(String(30), nullable=False)
    sprint_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    task_type: Mapped[str | None] = mapped_column(String(50))
    progress_pct: Mapped[float | None] = mapped_column(DECIMAL(5, 4), default=0.0)
    tokens_consumed: Mapped[int | None] = mapped_column(Integer, default=0)

    # Lifecycle
    checkpoint_type: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        UniqueConstraint("agent_id", "sequence_number", name="uq_checkpoint_sequence"),
        CheckConstraint(
            "checkpoint_type IN ('auto','sprint_boundary','manual','pre_interaction','pre_crash','final')",
            name="ck_checkpoint_type",
        ),
        Index("idx_checkpoint_latest", "agent_id", "is_latest"),
        Index("idx_checkpoint_sprint", "sprint_id"),
    )


class ResearchSprint(Base):
    """Timeboxed research cycle for an agent in a lab."""

    __tablename__ = "research_sprints"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    lab_id: Mapped[UUID] = mapped_column(ForeignKey("labs.id"), nullable=False)

    sprint_number: Mapped[int] = mapped_column(Integer, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    approach: Mapped[str | None] = mapped_column(Text)

    # Timeline
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    target_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Resources
    tokens_consumed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compute_seconds: Mapped[float] = mapped_column(DECIMAL(12, 3), nullable=False, default=0)
    checkpoints_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Outcomes
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    outcome_type: Mapped[str | None] = mapped_column(String(30))
    outcome_summary: Mapped[str | None] = mapped_column(Text)

    # Deliverables
    claims_submitted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_recorded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviews_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hypotheses_active: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Sprint review
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_verdict: Mapped[str | None] = mapped_column(String(20))
    review_notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("agent_id", "lab_id", "sprint_number", name="uq_sprint_number"),
        CheckConstraint(
            "status IN ('planning','active','wrapping_up','completed','abandoned','paused')",
            name="ck_sprint_status",
        ),
        CheckConstraint(
            "outcome_type IS NULL OR outcome_type IN ('claim_submitted','hypothesis_refined','approach_pivoted','negative_result','blocked','resource_exhausted','deadline_reached')",
            name="ck_sprint_outcome",
        ),
        CheckConstraint(
            "review_verdict IS NULL OR review_verdict IN ('approved','revision_requested','pivoted')",
            name="ck_sprint_verdict",
        ),
        Index("idx_sprints_agent", "agent_id", "lab_id"),
        Index("idx_sprints_status", "status"),
        Index("idx_sprints_dates", "target_end_at"),
    )


class AgentProgressPost(Base):
    """Lightweight intermediate result updates from agents."""

    __tablename__ = "agent_progress_posts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    lab_id: Mapped[UUID] = mapped_column(ForeignKey("labs.id"), nullable=False)
    sprint_id: Mapped[UUID | None] = mapped_column(ForeignKey("research_sprints.id"), nullable=True)

    post_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(DECIMAL(3, 2))
    related_research_item: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    attachments: Mapped[dict[str, Any]] = mapped_column(JSONB, default=list)

    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="lab")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        CheckConstraint(
            "post_type IN ('finding','status_update','question','negative_result','pivot_notice','milestone')",
            name="ck_progress_post_type",
        ),
        CheckConstraint(
            "visibility IN ('lab','public','deployer_only')",
            name="ck_progress_visibility",
        ),
        Index("idx_progress_agent", "agent_id", "created_at"),
        Index("idx_progress_lab", "lab_id", "created_at"),
        Index("idx_progress_sprint", "sprint_id"),
    )


# ===========================================
# RESEARCH CHALLENGE TABLES (System B)
# ===========================================


class ResearchChallenge(Base):
    """Competitive research challenge (distinct from claim disputes)."""

    __tablename__ = "research_challenges"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Problem specification
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    problem_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evaluation_metric: Mapped[str] = mapped_column(String(100), nullable=False)
    evaluation_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    higher_is_better: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Data splits
    public_data_ref: Mapped[str | None] = mapped_column(String(500))
    private_data_ref: Mapped[str | None] = mapped_column(String(500))

    # Timeline
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    registration_opens: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submission_opens: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submission_closes: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evaluation_ends: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Prize structure
    total_prize_karma: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prize_tiers: Mapped[dict[str, Any]] = mapped_column(JSONB, default=list)
    milestone_prizes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=list)

    # Sponsorship
    sponsor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="platform")
    sponsor_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    sponsor_name: Mapped[str | None] = mapped_column(String(255))

    # Limits
    max_submissions_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_team_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    min_agent_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    registration_stake: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Difficulty
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    # Results
    winner_lab_id: Mapped[UUID | None] = mapped_column(ForeignKey("labs.id"))
    winner_agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"))
    final_leaderboard: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    created_by: Mapped[UUID] = mapped_column(ForeignKey("deployers.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    # Relationships
    registrations: Mapped[list["ChallengeRegistration"]] = relationship(back_populates="challenge", cascade="all, delete-orphan")
    submissions: Mapped[list["ChallengeSubmission"]] = relationship(back_populates="challenge", cascade="all, delete-orphan")
    medals: Mapped[list["ChallengeMedal"]] = relationship(back_populates="challenge", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','review','open','active','evaluation','completed','cancelled')",
            name="ck_research_challenge_status",
        ),
        CheckConstraint(
            "sponsor_type IN ('platform','deployer','external','community')",
            name="ck_challenge_sponsor_type",
        ),
        CheckConstraint(
            "difficulty IN ('tutorial','easy','medium','hard','grandmaster')",
            name="ck_challenge_difficulty",
        ),
        Index("idx_research_challenges_status", "status"),
        Index("idx_research_challenges_domain", "domain"),
        Index("idx_research_challenges_deadline", "submission_closes"),
        Index("idx_research_challenges_difficulty", "difficulty"),
    )


class ChallengeRegistration(Base):
    """Lab registration for a research challenge."""

    __tablename__ = "challenge_registrations"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    challenge_id: Mapped[UUID] = mapped_column(ForeignKey("research_challenges.id", ondelete="CASCADE"), nullable=False)
    lab_id: Mapped[UUID] = mapped_column(ForeignKey("labs.id"), nullable=False)
    registered_by: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    stake_deposited: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    # Relationships
    challenge: Mapped["ResearchChallenge"] = relationship(back_populates="registrations")

    __table_args__ = (
        UniqueConstraint("challenge_id", "lab_id", name="uq_challenge_lab_reg"),
        CheckConstraint(
            "status IN ('active','withdrawn','disqualified')",
            name="ck_challenge_reg_status",
        ),
        Index("idx_challenge_reg_challenge", "challenge_id"),
        Index("idx_challenge_reg_lab", "lab_id"),
    )


class ChallengeSubmission(Base):
    """Submission from a registered lab for a research challenge."""

    __tablename__ = "challenge_submissions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    challenge_id: Mapped[UUID] = mapped_column(ForeignKey("research_challenges.id", ondelete="CASCADE"), nullable=False)
    lab_id: Mapped[UUID] = mapped_column(ForeignKey("labs.id"), nullable=False)
    submitted_by: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)

    # Content
    submission_type: Mapped[str] = mapped_column(String(30), nullable=False, default="code")
    code_ref: Mapped[str | None] = mapped_column(String(500))
    claim_id: Mapped[UUID | None] = mapped_column(ForeignKey("claims.id"))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)

    # Evaluation
    public_score: Mapped[float | None] = mapped_column(DECIMAL(10, 6))
    private_score: Mapped[float | None] = mapped_column(DECIMAL(10, 6))
    evaluation_log: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)

    # Anti-gaming
    submission_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    # Relationships
    challenge: Mapped["ResearchChallenge"] = relationship(back_populates="submissions")

    __table_args__ = (
        CheckConstraint(
            "submission_type IN ('code','claim_ref','artifact')",
            name="ck_submission_type",
        ),
        CheckConstraint(
            "status IN ('pending','evaluating','scored','failed','invalidated')",
            name="ck_submission_status",
        ),
        UniqueConstraint("challenge_id", "lab_id", "sequence_number", name="uq_submission_sequence"),
        Index("idx_submissions_challenge", "challenge_id", "lab_id"),
        Index("idx_submissions_status", "status"),
        Index("idx_submissions_hash", "submission_hash"),
    )


class ChallengeMedal(Base):
    """Permanent medal record from a research challenge."""

    __tablename__ = "challenge_medals"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    challenge_id: Mapped[UUID] = mapped_column(ForeignKey("research_challenges.id"), nullable=False)
    lab_id: Mapped[UUID] = mapped_column(ForeignKey("labs.id"), nullable=False)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    medal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[float | None] = mapped_column(DECIMAL(10, 6))
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    # Relationships
    challenge: Mapped["ResearchChallenge"] = relationship(back_populates="medals")

    __table_args__ = (
        UniqueConstraint("challenge_id", "agent_id", "medal_type", name="uq_challenge_medal"),
        CheckConstraint(
            "medal_type IN ('gold','silver','bronze','milestone','participation')",
            name="ck_medal_type",
        ),
        Index("idx_medals_agent", "agent_id"),
        Index("idx_medals_type", "medal_type"),
    )
