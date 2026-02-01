"""Experiment repository for PostgreSQL operations.

Provides data access for Experiment, ExperimentPlan, and ExperimentResult
entities stored in PostgreSQL.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, select, update
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from platform.infrastructure.database.models import Base
from platform.repositories.base import BaseRepository
from platform.repositories.exceptions import EntityNotFoundError, ValidationError
from platform.shared.utils.datetime_utils import utcnow
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# ===========================================
# EXPERIMENT ORM MODELS
# ===========================================


class HypothesisModel(Base):
    """Hypothesis ORM model for PostgreSQL storage."""

    __tablename__ = "hypotheses"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    hypothesis_type: Mapped[str] = mapped_column(String(50), nullable=False, default="descriptive")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    experiments: Mapped[list["ExperimentModel"]] = relationship(
        "ExperimentModel",
        secondary="experiment_hypotheses",
        back_populates="hypotheses",
    )


class ExperimentModel(Base):
    """Experiment ORM model for PostgreSQL storage."""

    __tablename__ = "experiments"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    domain: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    experiment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    variables: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    steps: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    results: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Foreign keys
    plan_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("experiment_plans.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    plan: Mapped["ExperimentPlanModel | None"] = relationship("ExperimentPlanModel", back_populates="experiments")
    hypotheses: Mapped[list["HypothesisModel"]] = relationship(
        "HypothesisModel",
        secondary="experiment_hypotheses",
        back_populates="experiments",
    )
    results_records: Mapped[list["ExperimentResultModel"]] = relationship(
        "ExperimentResultModel",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
    checkpoints: Mapped[list["CheckpointModel"]] = relationship(
        "CheckpointModel",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )

    def to_domain(self) -> "Experiment":
        """Convert ORM model to domain Experiment dataclass."""
        from platform.experiments.base import Experiment, ExperimentStatus

        return Experiment(
            experiment_id=str(self.id),
            name=self.name,
            description=self.description,
            domain=self.domain,
            experiment_type=self.experiment_type,
            status=ExperimentStatus(self.status),
            progress=self.progress,
            variables=self.variables or [],
            steps=self.steps or [],
            config=self.config or {},
            results=self.results or {},
            created_by=self.created_by,
            created_at=self.created_at,
            updated_at=self.updated_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
        )


class ExperimentHypothesisModel(Base):
    """Association table for experiments and hypotheses."""

    __tablename__ = "experiment_hypotheses"

    experiment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hypothesis_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hypotheses.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ExperimentPlanModel(Base):
    """Experiment plan ORM model for PostgreSQL storage."""

    __tablename__ = "experiment_plans"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    domain: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    dependencies: Mapped[dict[str, list[str]]] = mapped_column(JSONB, default=dict)
    total_resource_estimate: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    experiments: Mapped[list["ExperimentModel"]] = relationship(
        "ExperimentModel",
        back_populates="plan",
    )


class ExperimentResultModel(Base):
    """Experiment result ORM model for PostgreSQL storage."""

    __tablename__ = "experiment_results"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    statistics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    effect_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_data_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    artifacts: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    experiment: Mapped["ExperimentModel"] = relationship("ExperimentModel", back_populates="results_records")


class CheckpointModel(Base):
    """Experiment checkpoint ORM model for PostgreSQL storage."""

    __tablename__ = "experiment_checkpoints"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    checkpoint_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    experiment: Mapped["ExperimentModel"] = relationship("ExperimentModel", back_populates="checkpoints")


# ===========================================
# EXPERIMENT REPOSITORY
# ===========================================


class ExperimentRepository(BaseRepository[ExperimentModel]):
    """Repository for Experiment database operations.

    Provides CRUD operations and queries for experiments stored in PostgreSQL.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the experiment repository.

        Args:
            session: Async SQLAlchemy session
        """
        super().__init__(session)

    @property
    def model_class(self) -> type[ExperimentModel]:
        """Return the ExperimentModel class."""
        return ExperimentModel

    async def get_by_id(self, experiment_id: str | UUID) -> ExperimentModel | None:
        """Get an experiment by ID.

        Args:
            experiment_id: The experiment's unique identifier

        Returns:
            ExperimentModel if found, None otherwise
        """
        if isinstance(experiment_id, str):
            try:
                experiment_id = UUID(experiment_id)
            except ValueError:
                return None

        return await super().get_by_id(experiment_id)

    async def create_experiment(
        self,
        name: str,
        description: str,
        domain: str,
        experiment_type: str,
        created_by: str = "system",
        config: dict[str, Any] | None = None,
    ) -> ExperimentModel:
        """Create a new experiment.

        Args:
            name: Experiment name
            description: Experiment description
            domain: Scientific domain
            experiment_type: Type of experiment
            created_by: Creator identifier
            config: Experiment configuration

        Returns:
            The created ExperimentModel
        """
        experiment = ExperimentModel(
            name=name,
            description=description,
            domain=domain,
            experiment_type=experiment_type,
            created_by=created_by,
            config=config or {},
        )

        self.session.add(experiment)
        await self.session.flush()
        await self.session.refresh(experiment)

        logger.info(
            "experiment_created",
            experiment_id=str(experiment.id),
            name=name,
            domain=domain,
        )
        return experiment

    async def update_experiment(
        self,
        experiment_id: str | UUID,
        **kwargs: Any,
    ) -> ExperimentModel | None:
        """Update an experiment's fields.

        Args:
            experiment_id: The experiment ID to update
            **kwargs: Fields to update

        Returns:
            Updated ExperimentModel if found, None otherwise
        """
        if isinstance(experiment_id, str):
            experiment_id = UUID(experiment_id)

        return await super().update(experiment_id, **kwargs)

    async def update_status(
        self,
        experiment_id: str | UUID,
        status: str,
    ) -> bool:
        """Update an experiment's status.

        Args:
            experiment_id: The experiment ID
            status: New status value

        Returns:
            True if updated, False if experiment not found
        """
        if isinstance(experiment_id, str):
            experiment_id = UUID(experiment_id)

        updates: dict[str, Any] = {"status": status, "updated_at": utcnow()}

        if status == "running":
            updates["started_at"] = utcnow()
        elif status in ("completed", "failed"):
            updates["completed_at"] = utcnow()

        result = await self.session.execute(
            update(ExperimentModel)
            .where(ExperimentModel.id == experiment_id)
            .values(**updates)
        )

        if result.rowcount > 0:
            logger.info("experiment_status_updated", experiment_id=str(experiment_id), status=status)

        return result.rowcount > 0

    async def update_progress(
        self,
        experiment_id: str | UUID,
        progress: float,
    ) -> bool:
        """Update an experiment's progress.

        Args:
            experiment_id: The experiment ID
            progress: Progress value (0.0 to 1.0)

        Returns:
            True if updated, False if experiment not found
        """
        if isinstance(experiment_id, str):
            experiment_id = UUID(experiment_id)

        result = await self.session.execute(
            update(ExperimentModel)
            .where(ExperimentModel.id == experiment_id)
            .values(progress=progress, updated_at=utcnow())
        )
        return result.rowcount > 0

    async def update_results(
        self,
        experiment_id: str | UUID,
        results: dict[str, Any],
    ) -> bool:
        """Update an experiment's results.

        Args:
            experiment_id: The experiment ID
            results: Results data

        Returns:
            True if updated, False if experiment not found
        """
        if isinstance(experiment_id, str):
            experiment_id = UUID(experiment_id)

        result = await self.session.execute(
            update(ExperimentModel)
            .where(ExperimentModel.id == experiment_id)
            .values(results=results, updated_at=utcnow())
        )
        return result.rowcount > 0

    async def list_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExperimentModel]:
        """List experiments by status.

        Args:
            status: Status to filter by
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching experiments
        """
        query = (
            select(ExperimentModel)
            .where(ExperimentModel.status == status)
            .limit(limit)
            .offset(offset)
            .order_by(ExperimentModel.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_domain(
        self,
        domain: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExperimentModel]:
        """List experiments by domain.

        Args:
            domain: Domain to filter by
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching experiments
        """
        query = (
            select(ExperimentModel)
            .where(ExperimentModel.domain == domain)
            .limit(limit)
            .offset(offset)
            .order_by(ExperimentModel.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_creator(
        self,
        created_by: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExperimentModel]:
        """List experiments by creator.

        Args:
            created_by: Creator identifier
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching experiments
        """
        query = (
            select(ExperimentModel)
            .where(ExperimentModel.created_by == created_by)
            .limit(limit)
            .offset(offset)
            .order_by(ExperimentModel.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_plan(
        self,
        plan_id: str | UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExperimentModel]:
        """List experiments belonging to a plan.

        Args:
            plan_id: Plan identifier
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching experiments
        """
        if isinstance(plan_id, str):
            plan_id = UUID(plan_id)

        query = (
            select(ExperimentModel)
            .where(ExperimentModel.plan_id == plan_id)
            .limit(limit)
            .offset(offset)
            .order_by(ExperimentModel.created_at.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search(
        self,
        query_text: str,
        limit: int = 20,
    ) -> list[ExperimentModel]:
        """Search experiments by name or description.

        Args:
            query_text: Text to search for
            limit: Maximum number to return

        Returns:
            List of matching experiments
        """
        pattern = f"%{query_text}%"
        query = (
            select(ExperimentModel)
            .where(
                (ExperimentModel.name.ilike(pattern)) |
                (ExperimentModel.description.ilike(pattern))
            )
            .limit(limit)
            .order_by(ExperimentModel.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


# ===========================================
# EXPERIMENT PLAN REPOSITORY
# ===========================================


class ExperimentPlanRepository(BaseRepository[ExperimentPlanModel]):
    """Repository for ExperimentPlan database operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the experiment plan repository.

        Args:
            session: Async SQLAlchemy session
        """
        super().__init__(session)

    @property
    def model_class(self) -> type[ExperimentPlanModel]:
        """Return the ExperimentPlanModel class."""
        return ExperimentPlanModel

    async def get_by_id(self, plan_id: str | UUID) -> ExperimentPlanModel | None:
        """Get a plan by ID.

        Args:
            plan_id: The plan's unique identifier

        Returns:
            ExperimentPlanModel if found, None otherwise
        """
        if isinstance(plan_id, str):
            try:
                plan_id = UUID(plan_id)
            except ValueError:
                return None

        return await super().get_by_id(plan_id)

    async def create_plan(
        self,
        name: str,
        description: str,
        objective: str,
        domain: str,
        created_by: str = "system",
    ) -> ExperimentPlanModel:
        """Create a new experiment plan.

        Args:
            name: Plan name
            description: Plan description
            objective: Plan objective
            domain: Scientific domain
            created_by: Creator identifier

        Returns:
            The created ExperimentPlanModel
        """
        plan = ExperimentPlanModel(
            name=name,
            description=description,
            objective=objective,
            domain=domain,
            created_by=created_by,
        )

        self.session.add(plan)
        await self.session.flush()
        await self.session.refresh(plan)

        logger.info("experiment_plan_created", plan_id=str(plan.id), name=name)
        return plan

    async def update_status(
        self,
        plan_id: str | UUID,
        status: str,
    ) -> bool:
        """Update a plan's status.

        Args:
            plan_id: The plan ID
            status: New status value

        Returns:
            True if updated, False if plan not found
        """
        if isinstance(plan_id, str):
            plan_id = UUID(plan_id)

        result = await self.session.execute(
            update(ExperimentPlanModel)
            .where(ExperimentPlanModel.id == plan_id)
            .values(status=status, updated_at=utcnow())
        )
        return result.rowcount > 0

    async def list_by_domain(
        self,
        domain: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExperimentPlanModel]:
        """List plans by domain.

        Args:
            domain: Domain to filter by
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching plans
        """
        query = (
            select(ExperimentPlanModel)
            .where(ExperimentPlanModel.domain == domain)
            .limit(limit)
            .offset(offset)
            .order_by(ExperimentPlanModel.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExperimentPlanModel]:
        """List plans by status.

        Args:
            status: Status to filter by
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching plans
        """
        query = (
            select(ExperimentPlanModel)
            .where(ExperimentPlanModel.status == status)
            .limit(limit)
            .offset(offset)
            .order_by(ExperimentPlanModel.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


# ===========================================
# EXPERIMENT RESULT REPOSITORY
# ===========================================


class ExperimentResultRepository(BaseRepository[ExperimentResultModel]):
    """Repository for ExperimentResult database operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the experiment result repository.

        Args:
            session: Async SQLAlchemy session
        """
        super().__init__(session)

    @property
    def model_class(self) -> type[ExperimentResultModel]:
        """Return the ExperimentResultModel class."""
        return ExperimentResultModel

    async def create_result(
        self,
        experiment_id: str | UUID,
        metrics: dict[str, Any],
        statistics: dict[str, Any] | None = None,
        confidence: float = 0.0,
        p_value: float | None = None,
        effect_size: float | None = None,
        summary: str = "",
    ) -> ExperimentResultModel:
        """Create a new experiment result.

        Args:
            experiment_id: Associated experiment ID
            metrics: Result metrics
            statistics: Statistical data
            confidence: Confidence level
            p_value: P-value if applicable
            effect_size: Effect size if applicable
            summary: Result summary

        Returns:
            The created ExperimentResultModel
        """
        if isinstance(experiment_id, str):
            experiment_id = UUID(experiment_id)

        result = ExperimentResultModel(
            experiment_id=experiment_id,
            metrics=metrics,
            statistics=statistics or {},
            confidence=confidence,
            p_value=p_value,
            effect_size=effect_size,
            summary=summary,
        )

        self.session.add(result)
        await self.session.flush()
        await self.session.refresh(result)

        logger.info("experiment_result_created", result_id=str(result.id), experiment_id=str(experiment_id))
        return result

    async def list_by_experiment(
        self,
        experiment_id: str | UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExperimentResultModel]:
        """List results for an experiment.

        Args:
            experiment_id: Experiment identifier
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of results
        """
        if isinstance(experiment_id, str):
            experiment_id = UUID(experiment_id)

        query = (
            select(ExperimentResultModel)
            .where(ExperimentResultModel.experiment_id == experiment_id)
            .limit(limit)
            .offset(offset)
            .order_by(ExperimentResultModel.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


# ===========================================
# HYPOTHESIS REPOSITORY
# ===========================================


class HypothesisRepository(BaseRepository[HypothesisModel]):
    """Repository for Hypothesis database operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the hypothesis repository.

        Args:
            session: Async SQLAlchemy session
        """
        super().__init__(session)

    @property
    def model_class(self) -> type[HypothesisModel]:
        """Return the HypothesisModel class."""
        return HypothesisModel

    async def create_hypothesis(
        self,
        title: str,
        statement: str,
        domain: str,
        hypothesis_type: str = "descriptive",
        status: str = "proposed",
    ) -> HypothesisModel:
        """Create a new hypothesis.

        Args:
            title: Hypothesis title
            statement: Hypothesis statement
            domain: Scientific domain
            hypothesis_type: Type of hypothesis
            status: Current status

        Returns:
            The created HypothesisModel
        """
        hypothesis = HypothesisModel(
            title=title,
            statement=statement,
            domain=domain,
            hypothesis_type=hypothesis_type,
            status=status,
        )

        self.session.add(hypothesis)
        await self.session.flush()
        await self.session.refresh(hypothesis)

        logger.info("hypothesis_created", hypothesis_id=str(hypothesis.id), title=title)
        return hypothesis

    async def update_status(
        self,
        hypothesis_id: str | UUID,
        status: str,
        confidence: float | None = None,
    ) -> bool:
        """Update a hypothesis's status.

        Args:
            hypothesis_id: The hypothesis ID
            status: New status value
            confidence: Optional confidence update

        Returns:
            True if updated, False if hypothesis not found
        """
        if isinstance(hypothesis_id, str):
            hypothesis_id = UUID(hypothesis_id)

        updates: dict[str, Any] = {"status": status, "updated_at": utcnow()}
        if confidence is not None:
            updates["confidence"] = confidence

        result = await self.session.execute(
            update(HypothesisModel)
            .where(HypothesisModel.id == hypothesis_id)
            .values(**updates)
        )
        return result.rowcount > 0

    async def list_by_domain(
        self,
        domain: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[HypothesisModel]:
        """List hypotheses by domain.

        Args:
            domain: Domain to filter by
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching hypotheses
        """
        query = (
            select(HypothesisModel)
            .where(HypothesisModel.domain == domain)
            .limit(limit)
            .offset(offset)
            .order_by(HypothesisModel.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[HypothesisModel]:
        """List hypotheses by status.

        Args:
            status: Status to filter by
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching hypotheses
        """
        query = (
            select(HypothesisModel)
            .where(HypothesisModel.status == status)
            .limit(limit)
            .offset(offset)
            .order_by(HypothesisModel.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
