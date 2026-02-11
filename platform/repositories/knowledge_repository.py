"""Knowledge repository for PostgreSQL operations.

Provides data access for KnowledgeEntry, Citation, Relationship,
and Provenance entities.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, select, update
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
# KNOWLEDGE ORM MODELS
# ===========================================


class KnowledgeEntryModel(Base):
    """Knowledge entry ORM model for PostgreSQL storage."""

    __tablename__ = "knowledge_entries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    domain: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False, default="fact", index=True)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    citations_as_source: Mapped[list["CitationModel"]] = relationship(
        "CitationModel",
        foreign_keys="CitationModel.source_entry_id",
        back_populates="source_entry",
        cascade="all, delete-orphan",
    )
    citations_as_target: Mapped[list["CitationModel"]] = relationship(
        "CitationModel",
        foreign_keys="CitationModel.target_entry_id",
        back_populates="target_entry",
        cascade="all, delete-orphan",
    )
    provenance_records: Mapped[list["ProvenanceRecordModel"]] = relationship(
        "ProvenanceRecordModel",
        back_populates="entry",
        cascade="all, delete-orphan",
    )
    source_references: Mapped[list["SourceReferenceModel"]] = relationship(
        "SourceReferenceModel",
        secondary="entry_source_references",
        back_populates="entries",
    )

    def to_domain(self) -> "KnowledgeEntry":
        """Convert ORM model to domain KnowledgeEntry dataclass."""
        from platform.knowledge.base import EntryType, KnowledgeEntry, VerificationStatus

        return KnowledgeEntry(
            entry_id=str(self.id),
            title=self.title,
            content=self.content,
            summary=self.summary,
            domain=self.domain,
            entry_type=EntryType(self.entry_type),
            verification_status=VerificationStatus(self.verification_status),
            confidence_score=self.confidence_score,
            keywords=list(self.keywords) if self.keywords else [],
            tags=list(self.tags) if self.tags else [],
            metadata=dict(self.metadata_) if self.metadata_ else {},
            embedding=list(self.embedding) if self.embedding else None,
            version=self.version,
            is_archived=self.is_archived,
            created_by=self.created_by,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class CitationModel(Base):
    """Citation ORM model for PostgreSQL storage."""

    __tablename__ = "citations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_entry_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entry_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    citation_type: Mapped[str] = mapped_column(String(50), nullable=False, default="reference")
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    source_entry: Mapped["KnowledgeEntryModel"] = relationship(
        "KnowledgeEntryModel",
        foreign_keys=[source_entry_id],
        back_populates="citations_as_source",
    )
    target_entry: Mapped["KnowledgeEntryModel"] = relationship(
        "KnowledgeEntryModel",
        foreign_keys=[target_entry_id],
        back_populates="citations_as_target",
    )


class RelationshipModel(Base):
    """Knowledge relationship ORM model for PostgreSQL storage."""

    __tablename__ = "knowledge_relationships"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_entry_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entry_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    bidirectional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProvenanceRecordModel(Base):
    """Provenance record ORM model for PostgreSQL storage.

    Note: Table name is 'knowledge_provenance' to distinguish from
    the W3C PROV-based provenance_records table used elsewhere.
    """

    __tablename__ = "knowledge_provenance"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    entry_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    previous_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    entry: Mapped["KnowledgeEntryModel"] = relationship(
        "KnowledgeEntryModel",
        back_populates="provenance_records",
    )


class SourceReferenceModel(Base):
    """Source reference ORM model for PostgreSQL storage."""

    __tablename__ = "source_references"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    doi: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    entries: Mapped[list["KnowledgeEntryModel"]] = relationship(
        "KnowledgeEntryModel",
        secondary="entry_source_references",
        back_populates="source_references",
    )


class EntrySourceReferenceModel(Base):
    """Association table for entries and source references."""

    __tablename__ = "entry_source_references"

    entry_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_reference_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("source_references.id", ondelete="CASCADE"),
        primary_key=True,
    )


# ===========================================
# KNOWLEDGE ENTRY REPOSITORY
# ===========================================


class KnowledgeEntryRepository(BaseRepository[KnowledgeEntryModel]):
    """Repository for KnowledgeEntry database operations.

    Provides CRUD operations and queries for knowledge entries stored in PostgreSQL.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the knowledge entry repository.

        Args:
            session: Async SQLAlchemy session
        """
        super().__init__(session)

    @property
    def model_class(self) -> type[KnowledgeEntryModel]:
        """Return the KnowledgeEntryModel class."""
        return KnowledgeEntryModel

    async def get_by_id(self, entry_id: str | UUID) -> KnowledgeEntryModel | None:
        """Get an entry by ID.

        Args:
            entry_id: The entry's unique identifier

        Returns:
            KnowledgeEntryModel if found, None otherwise
        """
        if isinstance(entry_id, str):
            try:
                entry_id = UUID(entry_id)
            except ValueError:
                return None

        return await super().get_by_id(entry_id)

    async def create_entry(
        self,
        title: str,
        content: str,
        domain: str,
        entry_type: str = "fact",
        verification_status: str = "pending",
        keywords: list[str] | None = None,
        tags: list[str] | None = None,
        created_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeEntryModel:
        """Create a new knowledge entry.

        Args:
            title: Entry title
            content: Entry content
            domain: Scientific domain
            entry_type: Type of entry (fact, theory, claim, etc.)
            verification_status: Current verification status
            keywords: List of keywords
            tags: List of tags
            created_by: Creator identifier
            metadata: Additional metadata

        Returns:
            The created KnowledgeEntryModel
        """
        entry = KnowledgeEntryModel(
            title=title,
            content=content,
            domain=domain,
            entry_type=entry_type,
            verification_status=verification_status,
            keywords=keywords or [],
            tags=tags or [],
            created_by=created_by,
            metadata_=metadata or {},
        )

        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)

        # Create provenance record
        await self._record_provenance(
            entry_id=entry.id,
            action="created",
            actor_id=created_by,
            new_state=entry.to_domain().to_dict(),
        )

        logger.info(
            "knowledge_entry_created",
            entry_id=str(entry.id),
            title=title,
            domain=domain,
            entry_type=entry_type,
        )
        return entry

    async def update_entry(
        self,
        entry_id: str | UUID,
        updates: dict[str, Any],
        updated_by: str = "",
        reason: str = "",
    ) -> KnowledgeEntryModel | None:
        """Update an entry's fields.

        Args:
            entry_id: The entry ID to update
            updates: Fields to update
            updated_by: Who is updating
            reason: Reason for update

        Returns:
            Updated KnowledgeEntryModel if found, None otherwise
        """
        if isinstance(entry_id, str):
            entry_id = UUID(entry_id)

        entry = await self.get_by_id(entry_id)
        if not entry:
            return None

        # Store previous state for provenance
        previous_state = entry.to_domain().to_dict()

        # Map field names
        if "metadata" in updates:
            updates["metadata_"] = updates.pop("metadata")

        # Increment version
        updates["version"] = entry.version + 1
        updates["updated_at"] = utcnow()

        await self.session.execute(
            update(KnowledgeEntryModel)
            .where(KnowledgeEntryModel.id == entry_id)
            .values(**updates)
        )
        await self.session.flush()

        # Refresh and get new state
        entry = await self.get_by_id(entry_id)
        new_state = entry.to_domain().to_dict() if entry else None

        # Record provenance
        await self._record_provenance(
            entry_id=entry_id,
            action="updated",
            actor_id=updated_by,
            previous_state=previous_state,
            new_state=new_state,
            reason=reason,
        )

        return entry

    async def archive_entry(
        self,
        entry_id: str | UUID,
        archived_by: str = "",
        reason: str = "",
    ) -> bool:
        """Archive (soft delete) an entry.

        Args:
            entry_id: The entry ID to archive
            archived_by: Who is archiving
            reason: Reason for archival

        Returns:
            True if archived, False if not found
        """
        if isinstance(entry_id, str):
            entry_id = UUID(entry_id)

        entry = await self.get_by_id(entry_id)
        if not entry:
            return False

        previous_state = entry.to_domain().to_dict()

        result = await self.session.execute(
            update(KnowledgeEntryModel)
            .where(KnowledgeEntryModel.id == entry_id)
            .values(is_archived=True, updated_at=utcnow())
        )

        if result.rowcount > 0:
            entry = await self.get_by_id(entry_id)
            await self._record_provenance(
                entry_id=entry_id,
                action="archived",
                actor_id=archived_by,
                previous_state=previous_state,
                new_state=entry.to_domain().to_dict() if entry else None,
                reason=reason,
            )
            logger.info("knowledge_entry_archived", entry_id=str(entry_id))

        return result.rowcount > 0

    async def update_verification_status(
        self,
        entry_id: str | UUID,
        status: str,
        verified_by: str = "",
        reason: str = "",
    ) -> bool:
        """Update an entry's verification status.

        Args:
            entry_id: The entry ID
            status: New verification status
            verified_by: Who verified
            reason: Verification reason

        Returns:
            True if updated, False if not found
        """
        return await self.update_entry(
            entry_id=entry_id,
            updates={"verification_status": status},
            updated_by=verified_by,
            reason=reason,
        ) is not None

    async def update_embedding(
        self,
        entry_id: str | UUID,
        embedding: list[float],
    ) -> bool:
        """Update an entry's embedding vector.

        Args:
            entry_id: The entry ID
            embedding: Embedding vector

        Returns:
            True if updated, False if not found
        """
        if isinstance(entry_id, str):
            entry_id = UUID(entry_id)

        result = await self.session.execute(
            update(KnowledgeEntryModel)
            .where(KnowledgeEntryModel.id == entry_id)
            .values(embedding=embedding, updated_at=utcnow())
        )
        return result.rowcount > 0

    async def list_entries(
        self,
        entry_type: str | None = None,
        domain: str | None = None,
        verification_status: str | None = None,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeEntryModel]:
        """List knowledge entries with filtering.

        Args:
            entry_type: Filter by entry type
            domain: Filter by domain
            verification_status: Filter by verification status
            include_archived: Include archived entries
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of matching entries
        """
        query = select(KnowledgeEntryModel)

        if not include_archived:
            query = query.where(KnowledgeEntryModel.is_archived == False)  # noqa: E712

        if entry_type:
            query = query.where(KnowledgeEntryModel.entry_type == entry_type)

        if domain:
            query = query.where(KnowledgeEntryModel.domain == domain)

        if verification_status:
            query = query.where(KnowledgeEntryModel.verification_status == verification_status)

        query = query.limit(limit).offset(offset).order_by(KnowledgeEntryModel.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search_by_text(
        self,
        query_text: str,
        domain: str | None = None,
        limit: int = 20,
    ) -> list[KnowledgeEntryModel]:
        """Search entries by title or content.

        Args:
            query_text: Text to search for
            domain: Optional domain filter
            limit: Maximum number to return

        Returns:
            List of matching entries
        """
        pattern = f"%{query_text}%"
        query = (
            select(KnowledgeEntryModel)
            .where(
                KnowledgeEntryModel.is_archived == False,  # noqa: E712
                (KnowledgeEntryModel.title.ilike(pattern)) |
                (KnowledgeEntryModel.content.ilike(pattern))
            )
        )

        if domain:
            query = query.where(KnowledgeEntryModel.domain == domain)

        query = query.limit(limit).order_by(KnowledgeEntryModel.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search_by_keywords(
        self,
        keywords: list[str],
        limit: int = 20,
    ) -> list[KnowledgeEntryModel]:
        """Search entries by keywords.

        Args:
            keywords: Keywords to search for
            limit: Maximum number to return

        Returns:
            List of matching entries
        """
        query = (
            select(KnowledgeEntryModel)
            .where(
                KnowledgeEntryModel.is_archived == False,  # noqa: E712
                KnowledgeEntryModel.keywords.overlap(keywords)
            )
            .limit(limit)
            .order_by(KnowledgeEntryModel.created_at.desc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def _record_provenance(
        self,
        entry_id: UUID,
        action: str,
        actor_id: str,
        previous_state: dict[str, Any] | None = None,
        new_state: dict[str, Any] | None = None,
        reason: str = "",
    ) -> None:
        """Record a provenance entry.

        Args:
            entry_id: The entry ID
            action: Action performed
            actor_id: Who performed the action
            previous_state: State before action
            new_state: State after action
            reason: Reason for action
        """
        record = ProvenanceRecordModel(
            entry_id=entry_id,
            action=action,
            actor_id=actor_id,
            previous_state=previous_state,
            new_state=new_state,
            reason=reason,
        )
        self.session.add(record)
        await self.session.flush()


# ===========================================
# CITATION REPOSITORY
# ===========================================


class CitationRepository(BaseRepository[CitationModel]):
    """Repository for Citation database operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the citation repository.

        Args:
            session: Async SQLAlchemy session
        """
        super().__init__(session)

    @property
    def model_class(self) -> type[CitationModel]:
        """Return the CitationModel class."""
        return CitationModel

    async def create_citation(
        self,
        source_entry_id: str | UUID,
        target_entry_id: str | UUID,
        citation_type: str = "reference",
        context: str = "",
        page_number: int | None = None,
        section: str = "",
    ) -> CitationModel:
        """Create a new citation.

        Args:
            source_entry_id: Citing entry ID
            target_entry_id: Cited entry ID
            citation_type: Type of citation
            context: Citation context
            page_number: Page number if applicable
            section: Section if applicable

        Returns:
            The created CitationModel
        """
        if isinstance(source_entry_id, str):
            source_entry_id = UUID(source_entry_id)
        if isinstance(target_entry_id, str):
            target_entry_id = UUID(target_entry_id)

        citation = CitationModel(
            source_entry_id=source_entry_id,
            target_entry_id=target_entry_id,
            citation_type=citation_type,
            context=context,
            page_number=page_number,
            section=section,
        )

        self.session.add(citation)
        await self.session.flush()
        await self.session.refresh(citation)

        logger.info(
            "citation_created",
            citation_id=str(citation.id),
            source=str(source_entry_id),
            target=str(target_entry_id),
        )
        return citation

    async def get_citations_for_entry(
        self,
        entry_id: str | UUID,
        as_source: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CitationModel]:
        """Get citations for an entry.

        Args:
            entry_id: Entry ID
            as_source: If True, get citations where entry is source
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of citations
        """
        if isinstance(entry_id, str):
            entry_id = UUID(entry_id)

        if as_source:
            query = select(CitationModel).where(CitationModel.source_entry_id == entry_id)
        else:
            query = select(CitationModel).where(CitationModel.target_entry_id == entry_id)

        query = query.limit(limit).offset(offset).order_by(CitationModel.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())


# ===========================================
# RELATIONSHIP REPOSITORY
# ===========================================


class RelationshipRepository(BaseRepository[RelationshipModel]):
    """Repository for Relationship database operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the relationship repository.

        Args:
            session: Async SQLAlchemy session
        """
        super().__init__(session)

    @property
    def model_class(self) -> type[RelationshipModel]:
        """Return the RelationshipModel class."""
        return RelationshipModel

    async def create_relationship(
        self,
        source_entry_id: str | UUID,
        target_entry_id: str | UUID,
        relationship_type: str,
        description: str = "",
        weight: float = 1.0,
        bidirectional: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> RelationshipModel:
        """Create a new relationship.

        Args:
            source_entry_id: Source entry ID
            target_entry_id: Target entry ID
            relationship_type: Type of relationship
            description: Relationship description
            weight: Relationship weight
            bidirectional: Whether relationship is bidirectional
            metadata: Additional metadata

        Returns:
            The created RelationshipModel
        """
        if isinstance(source_entry_id, str):
            source_entry_id = UUID(source_entry_id)
        if isinstance(target_entry_id, str):
            target_entry_id = UUID(target_entry_id)

        relationship = RelationshipModel(
            source_entry_id=source_entry_id,
            target_entry_id=target_entry_id,
            relationship_type=relationship_type,
            description=description,
            weight=weight,
            bidirectional=bidirectional,
            metadata_=metadata or {},
        )

        self.session.add(relationship)
        await self.session.flush()
        await self.session.refresh(relationship)

        logger.info(
            "relationship_created",
            relationship_id=str(relationship.id),
            type=relationship_type,
            source=str(source_entry_id),
            target=str(target_entry_id),
        )
        return relationship

    async def get_relationships_for_entry(
        self,
        entry_id: str | UUID,
        as_source: bool = True,
        relationship_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RelationshipModel]:
        """Get relationships for an entry.

        Args:
            entry_id: Entry ID
            as_source: If True, get relationships where entry is source
            relationship_type: Filter by relationship type
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of relationships
        """
        if isinstance(entry_id, str):
            entry_id = UUID(entry_id)

        if as_source:
            query = select(RelationshipModel).where(RelationshipModel.source_entry_id == entry_id)
        else:
            query = select(RelationshipModel).where(RelationshipModel.target_entry_id == entry_id)

        if relationship_type:
            query = query.where(RelationshipModel.relationship_type == relationship_type)

        query = query.limit(limit).offset(offset).order_by(RelationshipModel.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_all_relationships_for_entry(
        self,
        entry_id: str | UUID,
        include_bidirectional: bool = True,
        limit: int = 100,
    ) -> list[RelationshipModel]:
        """Get all relationships involving an entry (as source or target).

        Args:
            entry_id: Entry ID
            include_bidirectional: Include bidirectional relationships from either direction
            limit: Maximum number to return

        Returns:
            List of relationships
        """
        if isinstance(entry_id, str):
            entry_id = UUID(entry_id)

        conditions = [
            RelationshipModel.source_entry_id == entry_id,
            RelationshipModel.target_entry_id == entry_id,
        ]

        if include_bidirectional:
            query = select(RelationshipModel).where(
                (RelationshipModel.source_entry_id == entry_id) |
                (RelationshipModel.target_entry_id == entry_id)
            )
        else:
            query = select(RelationshipModel).where(
                (RelationshipModel.source_entry_id == entry_id) |
                ((RelationshipModel.target_entry_id == entry_id) & (RelationshipModel.bidirectional == True))  # noqa: E712
            )

        query = query.limit(limit).order_by(RelationshipModel.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())


# ===========================================
# PROVENANCE REPOSITORY
# ===========================================


class ProvenanceRepository(BaseRepository[ProvenanceRecordModel]):
    """Repository for Provenance record database operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the provenance repository.

        Args:
            session: Async SQLAlchemy session
        """
        super().__init__(session)

    @property
    def model_class(self) -> type[ProvenanceRecordModel]:
        """Return the ProvenanceRecordModel class."""
        return ProvenanceRecordModel

    async def get_provenance_for_entry(
        self,
        entry_id: str | UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProvenanceRecordModel]:
        """Get provenance records for an entry.

        Args:
            entry_id: Entry ID
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of provenance records (most recent first)
        """
        if isinstance(entry_id, str):
            entry_id = UUID(entry_id)

        query = (
            select(ProvenanceRecordModel)
            .where(ProvenanceRecordModel.entry_id == entry_id)
            .limit(limit)
            .offset(offset)
            .order_by(ProvenanceRecordModel.timestamp.desc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_entry_history(
        self,
        entry_id: str | UUID,
    ) -> list[ProvenanceRecordModel]:
        """Get complete history of an entry.

        Args:
            entry_id: Entry ID

        Returns:
            Complete list of provenance records (oldest first)
        """
        if isinstance(entry_id, str):
            entry_id = UUID(entry_id)

        query = (
            select(ProvenanceRecordModel)
            .where(ProvenanceRecordModel.entry_id == entry_id)
            .order_by(ProvenanceRecordModel.timestamp.asc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())
