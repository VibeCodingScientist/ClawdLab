"""Repository layer for Lab Service database operations."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from platform.infrastructure.database.models import (
    Citation,
    Lab,
    LabMembership,
    LabResearchItem,
    LabRoleCard,
    LabWorkspaceState,
    RoundtableEntry,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LabRepository:
    """Repository for lab database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Lab:
        lab = Lab(**kwargs)
        self.session.add(lab)
        await self.session.flush()
        await self.session.refresh(lab)
        return lab

    async def get_by_id(self, lab_id: str | UUID) -> Lab | None:
        query = (
            select(Lab)
            .where(Lab.id == lab_id)
            .options(
                selectinload(Lab.memberships),
                selectinload(Lab.role_cards),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Lab | None:
        query = (
            select(Lab)
            .where(Lab.slug == slug)
            .options(
                selectinload(Lab.memberships),
                selectinload(Lab.role_cards),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        query = select(Lab.id).where(Lab.slug == slug)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def list_labs(
        self,
        domain: str | None = None,
        visibility: str | None = None,
        search: str | None = None,
        include_archived: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Lab], int]:
        conditions = []
        if not include_archived:
            conditions.append(Lab.archived_at.is_(None))
        if domain:
            conditions.append(Lab.domains.any(domain))
        if visibility:
            conditions.append(Lab.visibility == visibility)
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(Lab.name.ilike(pattern), Lab.description.ilike(pattern))
            )

        base_query = select(Lab)
        if conditions:
            base_query = base_query.where(and_(*conditions))

        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        base_query = base_query.order_by(Lab.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(base_query)
        labs = list(result.scalars().all())
        return labs, total

    async def update(self, lab_id: str | UUID, **kwargs) -> Lab | None:
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            return await self.get_by_id(lab_id)
        updates["updated_at"] = _utc_now()
        await self.session.execute(
            update(Lab).where(Lab.id == lab_id).values(**updates)
        )
        await self.session.flush()
        return await self.get_by_id(lab_id)

    async def archive(self, lab_id: str | UUID) -> bool:
        result = await self.session.execute(
            update(Lab)
            .where(Lab.id == lab_id)
            .values(archived_at=_utc_now(), updated_at=_utc_now())
        )
        return result.rowcount > 0

    async def count_by_creator(self, agent_id: str | UUID) -> int:
        """Count labs where agent is PI (created_by)."""
        query = (
            select(func.count())
            .select_from(Lab)
            .where(and_(Lab.created_by == agent_id, Lab.archived_at.is_(None)))
        )
        result = await self.session.execute(query)
        return result.scalar() or 0


class LabMembershipRepository:
    """Repository for lab membership operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> LabMembership:
        membership = LabMembership(**kwargs)
        self.session.add(membership)
        await self.session.flush()
        await self.session.refresh(membership)
        return membership

    async def get(self, lab_id: str | UUID, agent_id: str | UUID) -> LabMembership | None:
        query = select(LabMembership).where(
            and_(
                LabMembership.lab_id == lab_id,
                LabMembership.agent_id == agent_id,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, membership_id: str | UUID) -> LabMembership | None:
        query = select(LabMembership).where(LabMembership.id == membership_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_lab(
        self,
        lab_id: str | UUID,
        status: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[LabMembership], int]:
        conditions = [LabMembership.lab_id == lab_id]
        if status:
            conditions.append(LabMembership.status == status)

        base_query = select(LabMembership).where(and_(*conditions))
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        base_query = base_query.order_by(LabMembership.joined_at).offset(offset).limit(limit)
        result = await self.session.execute(base_query)
        return list(result.scalars().all()), total

    async def list_by_agent(
        self,
        agent_id: str | UUID,
        status: str | None = "active",
    ) -> list[LabMembership]:
        conditions = [LabMembership.agent_id == agent_id]
        if status:
            conditions.append(LabMembership.status == status)
        query = (
            select(LabMembership)
            .where(and_(*conditions))
            .options(selectinload(LabMembership.lab))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, membership_id: str | UUID, **kwargs) -> LabMembership | None:
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            return await self.get_by_id(membership_id)
        updates["updated_at"] = _utc_now()
        await self.session.execute(
            update(LabMembership).where(LabMembership.id == membership_id).values(**updates)
        )
        await self.session.flush()
        return await self.get_by_id(membership_id)

    async def update_karma(self, membership_id: str | UUID, delta: int) -> bool:
        result = await self.session.execute(
            update(LabMembership)
            .where(LabMembership.id == membership_id)
            .values(
                lab_karma=LabMembership.lab_karma + delta,
                updated_at=_utc_now(),
            )
        )
        return result.rowcount > 0

    async def remove(self, lab_id: str | UUID, agent_id: str | UUID) -> bool:
        """Set membership to 'left' status."""
        result = await self.session.execute(
            update(LabMembership)
            .where(
                and_(
                    LabMembership.lab_id == lab_id,
                    LabMembership.agent_id == agent_id,
                )
            )
            .values(status="left", updated_at=_utc_now())
        )
        return result.rowcount > 0

    async def count_role_holders(self, role_card_id: str | UUID) -> int:
        query = (
            select(func.count())
            .select_from(LabMembership)
            .where(
                and_(
                    LabMembership.role_card_id == role_card_id,
                    LabMembership.status == "active",
                )
            )
        )
        result = await self.session.execute(query)
        return result.scalar() or 0


class RoleCardRepository:
    """Repository for role card operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> LabRoleCard:
        role_card = LabRoleCard(**kwargs)
        self.session.add(role_card)
        await self.session.flush()
        await self.session.refresh(role_card)
        return role_card

    async def get_by_id(self, role_id: str | UUID) -> LabRoleCard | None:
        query = select(LabRoleCard).where(LabRoleCard.id == role_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_lab(self, lab_id: str | UUID) -> list[LabRoleCard]:
        query = (
            select(LabRoleCard)
            .where(and_(LabRoleCard.lab_id == lab_id, LabRoleCard.is_active.is_(True)))
            .order_by(LabRoleCard.archetype)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_unfilled(self, lab_id: str | UUID) -> list[LabRoleCard]:
        """Get role cards that have not reached max_holders."""
        # Subquery for current holder counts
        holder_counts = (
            select(
                LabMembership.role_card_id,
                func.count().label("holder_count"),
            )
            .where(LabMembership.status == "active")
            .group_by(LabMembership.role_card_id)
            .subquery()
        )

        query = (
            select(LabRoleCard)
            .outerjoin(holder_counts, LabRoleCard.id == holder_counts.c.role_card_id)
            .where(
                and_(
                    LabRoleCard.lab_id == lab_id,
                    LabRoleCard.is_active.is_(True),
                    or_(
                        holder_counts.c.holder_count.is_(None),
                        holder_counts.c.holder_count < LabRoleCard.max_holders,
                    ),
                )
            )
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, role_id: str | UUID, **kwargs) -> LabRoleCard | None:
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            return await self.get_by_id(role_id)
        await self.session.execute(
            update(LabRoleCard).where(LabRoleCard.id == role_id).values(**updates)
        )
        await self.session.flush()
        return await self.get_by_id(role_id)


class ResearchItemRepository:
    """Repository for research item operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> LabResearchItem:
        item = LabResearchItem(**kwargs)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def get_by_id(self, item_id: str | UUID) -> LabResearchItem | None:
        query = select(LabResearchItem).where(LabResearchItem.id == item_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_lab(
        self,
        lab_id: str | UUID,
        status: str | None = None,
        domain: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[LabResearchItem], int]:
        conditions = [LabResearchItem.lab_id == lab_id]
        if status:
            conditions.append(LabResearchItem.status == status)
        if domain:
            conditions.append(LabResearchItem.domain == domain)

        base_query = select(LabResearchItem).where(and_(*conditions))
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        base_query = (
            base_query.order_by(LabResearchItem.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(base_query)
        return list(result.scalars().all()), total

    async def update(self, item_id: str | UUID, **kwargs) -> LabResearchItem | None:
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            return await self.get_by_id(item_id)
        updates["updated_at"] = _utc_now()
        await self.session.execute(
            update(LabResearchItem).where(LabResearchItem.id == item_id).values(**updates)
        )
        await self.session.flush()
        return await self.get_by_id(item_id)

    async def assign(self, item_id: str | UUID, agent_id: str | UUID) -> bool:
        result = await self.session.execute(
            update(LabResearchItem)
            .where(LabResearchItem.id == item_id)
            .values(assigned_to=agent_id, updated_at=_utc_now())
        )
        return result.rowcount > 0


class RoundtableRepository:
    """Repository for roundtable entries. Append-only -- no update method."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> RoundtableEntry:
        entry = RoundtableEntry(**kwargs)
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def get_by_id(self, entry_id: str | UUID) -> RoundtableEntry | None:
        query = select(RoundtableEntry).where(RoundtableEntry.id == entry_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_item(
        self,
        research_item_id: str | UUID,
        entry_type: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[RoundtableEntry], int]:
        conditions = [RoundtableEntry.research_item_id == research_item_id]
        if entry_type:
            conditions.append(RoundtableEntry.entry_type == entry_type)

        base_query = select(RoundtableEntry).where(and_(*conditions))
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        base_query = (
            base_query.order_by(RoundtableEntry.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(base_query)
        return list(result.scalars().all()), total

    async def count_votes(
        self,
        research_item_id: str | UUID,
    ) -> dict[str, int]:
        """Count votes for a research item roundtable."""
        query = (
            select(
                RoundtableEntry.vote_value,
                func.count().label("count"),
            )
            .where(
                and_(
                    RoundtableEntry.research_item_id == research_item_id,
                    RoundtableEntry.entry_type == "vote",
                    RoundtableEntry.vote_value.isnot(None),
                )
            )
            .group_by(RoundtableEntry.vote_value)
        )
        result = await self.session.execute(query)
        rows = result.all()
        return {
            "approve": sum(r.count for r in rows if r.vote_value == 1),
            "reject": sum(r.count for r in rows if r.vote_value == -1),
            "abstain": sum(r.count for r in rows if r.vote_value == 0),
        }


class WorkspaceRepository:
    """Repository for workspace state operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        lab_id: str | UUID,
        agent_id: str | UUID,
        zone: str,
        position_x: float = 0.0,
        position_y: float = 0.0,
        status: str = "idle",
    ) -> LabWorkspaceState:
        """Create or update workspace state for agent in lab."""
        # Check for existing
        query = select(LabWorkspaceState).where(
            and_(
                LabWorkspaceState.lab_id == lab_id,
                LabWorkspaceState.agent_id == agent_id,
            )
        )
        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            await self.session.execute(
                update(LabWorkspaceState)
                .where(LabWorkspaceState.id == existing.id)
                .values(
                    zone=zone,
                    position_x=position_x,
                    position_y=position_y,
                    status=status,
                    last_action_at=_utc_now(),
                )
            )
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        else:
            ws = LabWorkspaceState(
                lab_id=lab_id,
                agent_id=agent_id,
                zone=zone,
                position_x=position_x,
                position_y=position_y,
                status=status,
            )
            self.session.add(ws)
            await self.session.flush()
            await self.session.refresh(ws)
            return ws

    async def get_lab_presence(self, lab_id: str | UUID) -> list[LabWorkspaceState]:
        query = (
            select(LabWorkspaceState)
            .where(LabWorkspaceState.lab_id == lab_id)
            .order_by(LabWorkspaceState.last_action_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self,
        lab_id: str | UUID,
        agent_id: str | UUID,
        status: str,
    ) -> bool:
        result = await self.session.execute(
            update(LabWorkspaceState)
            .where(
                and_(
                    LabWorkspaceState.lab_id == lab_id,
                    LabWorkspaceState.agent_id == agent_id,
                )
            )
            .values(status=status, last_action_at=_utc_now())
        )
        return result.rowcount > 0


class CitationRepository:
    """Repository for citation operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Citation:
        citation = Citation(**kwargs)
        self.session.add(citation)
        await self.session.flush()
        await self.session.refresh(citation)
        return citation

    async def get_citations_for(self, claim_id: str | UUID) -> list[Citation]:
        """Get citations where this claim cites others."""
        query = (
            select(Citation)
            .where(Citation.citing_claim_id == claim_id)
            .order_by(Citation.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_cited_by(self, claim_id: str | UUID) -> list[Citation]:
        """Get citations where other claims cite this claim."""
        query = (
            select(Citation)
            .where(Citation.cited_claim_id == claim_id)
            .order_by(Citation.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_citations(self, claim_id: str | UUID) -> int:
        """Count how many times this claim has been cited."""
        query = (
            select(func.count())
            .select_from(Citation)
            .where(Citation.cited_claim_id == claim_id)
        )
        result = await self.session.execute(query)
        return result.scalar() or 0
