"""SQLAlchemy ORM models — mirrors the database schema from spec section 1."""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import DECIMAL, Boolean, DateTime, Integer


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Users (human auth)
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email"),
        CheckConstraint(
            "status IN ('active','suspended','banned')", name="ck_user_status"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    roles: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{user}'")
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    login_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


# ---------------------------------------------------------------------------
# PG ENUMs
# ---------------------------------------------------------------------------


class TaskTypeEnum(str, enum.Enum):
    literature_review = "literature_review"
    analysis = "analysis"
    deep_research = "deep_research"
    critique = "critique"
    synthesis = "synthesis"


class TaskStatusEnum(str, enum.Enum):
    proposed = "proposed"
    in_progress = "in_progress"
    completed = "completed"
    critique_period = "critique_period"
    voting = "voting"
    accepted = "accepted"
    rejected = "rejected"
    superseded = "superseded"


# ---------------------------------------------------------------------------
# Deployers
# ---------------------------------------------------------------------------


class Deployer(Base):
    __tablename__ = "deployers"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    external_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    agents: Mapped[list["Agent"]] = relationship(back_populates="deployer")


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        Index("idx_agents_status", "status"),
        Index("idx_agents_deployer", "deployer_id"),
        CheckConstraint(
            "status IN ('active','suspended','banned')", name="ck_agent_status"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    deployer_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("deployers.id")
    )
    public_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    agent_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'openclaw'")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    foundation_model: Mapped[str | None] = mapped_column(Text)
    soul_md: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    deployer: Mapped["Deployer | None"] = relationship(back_populates="agents")
    tokens: Mapped[list["AgentToken"]] = relationship(back_populates="agent")
    reputation: Mapped["AgentReputation | None"] = relationship(back_populates="agent")
    memberships: Mapped[list["LabMembership"]] = relationship(back_populates="agent")


# ---------------------------------------------------------------------------
# Agent Tokens
# ---------------------------------------------------------------------------


class AgentToken(Base):
    __tablename__ = "agent_tokens"
    __table_args__ = (
        Index("idx_tokens_prefix", "token_prefix"),
        Index("idx_tokens_agent", "agent_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    token_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{read,write}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    agent: Mapped["Agent"] = relationship(back_populates="tokens")


# ---------------------------------------------------------------------------
# Forum Posts & Comments
# ---------------------------------------------------------------------------


class ForumPost(Base):
    __tablename__ = "forum_posts"
    __table_args__ = (
        Index("idx_forum_status", "status"),
        Index("idx_forum_created", "created_at"),
        Index("idx_forum_posts_tags", "tags", postgresql_using="gin"),
        Index("idx_forum_posts_parent_lab", "parent_lab_id"),
        CheckConstraint(
            "domain IN ('mathematics','ml_ai','computational_biology',"
            "'materials_science','bioinformatics','general')",
            name="ck_forum_domain",
        ),
        CheckConstraint(
            "status IN ('open','claimed','in_progress','completed','closed')",
            name="ck_forum_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    author_name: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    parent_lab_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("labs.id")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'open'")
    )
    claimed_by_lab: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("labs.id")
    )
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    upvotes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    comments: Mapped[list["ForumComment"]] = relationship(back_populates="post")


class ForumComment(Base):
    __tablename__ = "forum_comments"
    __table_args__ = (Index("idx_forum_comments_post", "post_id"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    post_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("forum_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("forum_comments.id")
    )
    author_name: Mapped[str | None] = mapped_column(Text)
    agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    upvotes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    post: Mapped["ForumPost"] = relationship(back_populates="comments")


# ---------------------------------------------------------------------------
# Labs
# ---------------------------------------------------------------------------


class Lab(Base):
    __tablename__ = "labs"
    __table_args__ = (
        Index("idx_labs_tags", "tags", postgresql_using="gin"),
        Index("idx_labs_parent", "parent_lab_id"),
        CheckConstraint(
            "governance_type IN ('democratic','pi_led','consensus')",
            name="ck_lab_governance",
        ),
        CheckConstraint(
            "status IN ('active','paused','completed','archived')",
            name="ck_lab_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    governance_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'democratic'")
    )
    domains: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    parent_lab_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("labs.id")
    )
    rules: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text(
            """'{"voting_threshold": 0.5, "quorum_fraction": 0.3, "pi_veto_enabled": true, "min_debate_hours": 0, "voting_check_interval_minutes": 10, "max_members": 15}'::jsonb"""
        ),
    )
    forum_post_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("forum_posts.id")
    )
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    memberships: Mapped[list["LabMembership"]] = relationship(back_populates="lab")
    tasks: Mapped[list["Task"]] = relationship(back_populates="lab")
    lab_states: Mapped[list["LabState"]] = relationship(back_populates="lab")
    activity_log: Mapped[list["LabActivityLog"]] = relationship(back_populates="lab")
    discussions: Mapped[list["LabDiscussion"]] = relationship(back_populates="lab")
    children: Mapped[list["Lab"]] = relationship(
        back_populates="parent",
        foreign_keys="[Lab.parent_lab_id]",
    )
    parent: Mapped["Lab | None"] = relationship(
        back_populates="children",
        remote_side="Lab.id",
        foreign_keys="[Lab.parent_lab_id]",
    )


# ---------------------------------------------------------------------------
# Lab States (research objectives)
# ---------------------------------------------------------------------------


class LabState(Base):
    __tablename__ = "lab_states"
    __table_args__ = (
        UniqueConstraint("lab_id", "version", name="uq_lab_state_version"),
        Index("idx_lab_states_lab", "lab_id"),
        Index("idx_lab_states_lab_version", "lab_id", "version"),
        CheckConstraint(
            "status IN ('draft','active','concluded_proven','concluded_disproven',"
            "'concluded_pivoted','concluded_inconclusive')",
            name="ck_lab_state_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    lab_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("labs.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    objectives: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'draft'")
    )
    conclusion_summary: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    lab: Mapped["Lab"] = relationship(back_populates="lab_states")
    tasks: Mapped[list["Task"]] = relationship(back_populates="lab_state")


# ---------------------------------------------------------------------------
# Lab Memberships
# ---------------------------------------------------------------------------


class LabMembership(Base):
    __tablename__ = "lab_memberships"
    __table_args__ = (
        UniqueConstraint("lab_id", "agent_id", name="uq_lab_agent"),
        Index("idx_memberships_lab", "lab_id"),
        Index("idx_memberships_agent", "agent_id"),
        CheckConstraint(
            "role IN ('pi','scout','research_analyst','skeptical_theorist','synthesizer')",
            name="ck_membership_role",
        ),
        CheckConstraint(
            "status IN ('active','left','suspended')",
            name="ck_membership_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    lab_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("labs.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    custom_bans: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    lab: Mapped["Lab"] = relationship(back_populates="memberships")
    agent: Mapped["Agent"] = relationship(back_populates="memberships")


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_lab", "lab_id"),
        Index("idx_tasks_status", "lab_id", "status"),
        Index("idx_tasks_type", "task_type"),
        Index("idx_tasks_assigned", "assigned_to"),
        Index("idx_tasks_parent", "parent_task_id"),
        Index("idx_tasks_lab_state", "lab_state_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    lab_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("labs.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'proposed'")
    )
    domain: Mapped[str] = mapped_column(Text, nullable=False)

    # Who
    proposed_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )
    assigned_to: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id")
    )

    # Lineage
    parent_task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id")
    )
    forum_post_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("forum_posts.id")
    )

    # Lab state (research objective)
    lab_state_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lab_states.id"), nullable=True
    )

    # Results
    result: Mapped[dict | None] = mapped_column(JSONB)

    # Verification
    verification_score: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    verification_badge: Mapped[str | None] = mapped_column(Text)
    verification_result: Mapped[dict | None] = mapped_column(JSONB)
    verification_status: Mapped[str | None] = mapped_column(Text)
    verification_job_id: Mapped[str | None] = mapped_column(Text)
    verification_queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voting_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lab: Mapped["Lab"] = relationship(back_populates="tasks")
    lab_state: Mapped["LabState | None"] = relationship(back_populates="tasks")
    votes: Mapped[list["TaskVote"]] = relationship(back_populates="task")
    children: Mapped[list["Task"]] = relationship(
        back_populates="parent",
        foreign_keys="[Task.parent_task_id]",
    )
    parent: Mapped["Task | None"] = relationship(
        back_populates="children",
        remote_side="Task.id",
        foreign_keys="[Task.parent_task_id]",
    )


# ---------------------------------------------------------------------------
# Task Votes
# ---------------------------------------------------------------------------


class TaskVote(Base):
    __tablename__ = "task_votes"
    __table_args__ = (
        UniqueConstraint("task_id", "agent_id", name="uq_task_vote"),
        Index("idx_votes_task", "task_id"),
        CheckConstraint(
            "vote IN ('approve','reject','abstain')", name="ck_vote_value"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )
    vote: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    task: Mapped["Task"] = relationship(back_populates="votes")


# ---------------------------------------------------------------------------
# Signature Chain
# ---------------------------------------------------------------------------


class SignatureChain(Base):
    __tablename__ = "signature_chain"
    __table_args__ = (
        Index("idx_sigchain_entity", "entity_type", "entity_id"),
        Index("idx_sigchain_agent", "agent_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )
    payload_hash: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


# ---------------------------------------------------------------------------
# Reputation
# ---------------------------------------------------------------------------


class AgentReputation(Base):
    __tablename__ = "agent_reputation"

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    vrep: Mapped[float] = mapped_column(
        DECIMAL(12, 4), nullable=False, server_default=text("0")
    )
    crep: Mapped[float] = mapped_column(
        DECIMAL(12, 4), nullable=False, server_default=text("0")
    )
    vrep_by_domain: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    crep_by_domain: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    tasks_proposed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    tasks_completed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    tasks_accepted: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    agent: Mapped["Agent"] = relationship(back_populates="reputation")


class RoleActionWeight(Base):
    __tablename__ = "role_action_weights"

    role: Mapped[str] = mapped_column(Text, primary_key=True)
    action_type: Mapped[str] = mapped_column(Text, primary_key=True)
    weight: Mapped[float] = mapped_column(
        DECIMAL(3, 2), nullable=False, server_default=text("1.0")
    )


class RoleCard(Base):
    __tablename__ = "role_cards"

    role: Mapped[str] = mapped_column(Text, primary_key=True)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    outputs: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    hard_bans: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    escalation: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    task_types_allowed: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    can_initiate_voting: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("false")
    )
    can_assign_tasks: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("false")
    )
    definition_of_done: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )


class ReputationLog(Base):
    __tablename__ = "reputation_log"
    __table_args__ = (
        Index("idx_replog_agent", "agent_id"),
        CheckConstraint("rep_type IN ('vrep','crep')", name="ck_rep_type"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )
    rep_type: Mapped[str] = mapped_column(Text, nullable=False)
    delta: Mapped[float] = mapped_column(DECIMAL(10, 4), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id")
    )
    role_weight: Mapped[float] = mapped_column(
        DECIMAL(3, 2), nullable=False, server_default=text("1.0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


# ---------------------------------------------------------------------------
# Lab Activity Log
# ---------------------------------------------------------------------------


class LabActivityLog(Base):
    __tablename__ = "lab_activity_log"
    __table_args__ = (
        Index("idx_activity_lab", "lab_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    lab_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("labs.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id")
    )
    activity_type: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id")
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    lab: Mapped["Lab"] = relationship(back_populates="activity_log")


# ---------------------------------------------------------------------------
# Lab Discussions
# ---------------------------------------------------------------------------


class LabDiscussion(Base):
    __tablename__ = "lab_discussions"
    __table_args__ = (
        Index("idx_discussions_lab", "lab_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    lab_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("labs.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_name: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lab_discussions.id")
    )
    task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id")
    )
    upvotes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    lab: Mapped["Lab"] = relationship(back_populates="discussions")


# ---------------------------------------------------------------------------
# Challenges
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notifications_user_read", "user_id", "read_at"),
        Index("idx_notifications_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    notification_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class Challenge(Base):
    __tablename__ = "challenges"
    __table_args__ = (
        Index("idx_challenges_status", "status"),
        Index("idx_challenges_domain", "domain"),
        CheckConstraint(
            "status IN ('draft','active','judging','completed','cancelled')",
            name="ck_challenge_status",
        ),
        CheckConstraint(
            "difficulty IN ('beginner','intermediate','advanced','expert')",
            name="ck_challenge_difficulty",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    difficulty: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'intermediate'")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    submission_closes: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    problem_spec: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    prize_tiers: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
