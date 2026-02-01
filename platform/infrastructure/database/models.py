"""SQLAlchemy ORM models for the platform database."""

from datetime import datetime
from typing import Any
from uuid import uuid4

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_verification")
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)

    # Relationships
    capabilities: Mapped[list["AgentCapability"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    tokens: Mapped[list["AgentToken"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    claims: Mapped[list["Claim"]] = relationship(back_populates="agent")
    reputation: Mapped["AgentReputation"] = relationship(back_populates="agent", uselist=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_verification', 'active', 'suspended', 'banned')",
            name="valid_status",
        ),
        Index("idx_agents_status", "status"),
        Index("idx_agents_type", "agent_type"),
        Index("idx_agents_created", "created_at"),
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    novelty_score: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    novelty_assessment: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    depends_on: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

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
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_audit_agent", "agent_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_created", "created_at", postgresql_using="btree"),
    )
