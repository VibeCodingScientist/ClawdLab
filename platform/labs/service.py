"""Service layer for Lab business logic."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from platform.labs.config import DEFAULT_ROLE_CARD_TEMPLATES, get_lab_settings
from platform.labs.exceptions import (
    GovernanceViolationError,
    InsufficientKarmaError,
    LabArchivedError,
    LabMembershipError,
    LabNotFoundError,
    LabPermissionError,
    LabSlugConflictError,
    MaxLabsExceededError,
    RoleCardFullError,
    RoleCardNotFoundError,
)
from platform.labs.governance import governance_engine
from platform.labs.repository import (
    CitationRepository,
    LabMembershipRepository,
    LabRepository,
    ResearchItemRepository,
    RoleCardRepository,
    RoundtableRepository,
    WorkspaceRepository,
)
from platform.infrastructure.events import emit_platform_event
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_lab_settings()


class LabService:
    """Handles lab lifecycle and operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.lab_repo = LabRepository(session)
        self.membership_repo = LabMembershipRepository(session)
        self.role_card_repo = RoleCardRepository(session)
        self.research_repo = ResearchItemRepository(session)
        self.roundtable_repo = RoundtableRepository(session)
        self.workspace_repo = WorkspaceRepository(session)
        self.citation_repo = CitationRepository(session)

    # ==========================================
    # LAB CRUD
    # ==========================================

    async def create_lab(
        self,
        agent_id: str | UUID,
        slug: str,
        name: str,
        description: str | None = None,
        governance_type: str = "democratic",
        domains: list[str] | None = None,
        rules: dict[str, Any] | None = None,
        visibility: str = "public",
        karma_requirement: int = 0,
        agent_karma: int = 0,
    ) -> dict[str, Any]:
        """Create a new lab with default role cards."""
        # Check karma
        if agent_karma < settings.base_creation_karma:
            raise InsufficientKarmaError(settings.base_creation_karma, agent_karma)

        # Check slug uniqueness
        if await self.lab_repo.slug_exists(slug):
            raise LabSlugConflictError(slug)

        # Check PI lab count
        pi_count = await self.lab_repo.count_by_creator(agent_id)
        if pi_count >= settings.max_pi_labs:
            raise MaxLabsExceededError(settings.max_pi_labs)

        # Create lab
        lab = await self.lab_repo.create(
            id=uuid4(),
            slug=slug,
            name=name,
            description=description,
            governance_type=governance_type,
            domains=domains or [],
            rules=rules or {
                "voting_threshold": settings.default_voting_threshold,
                "quorum_fraction": settings.default_quorum_fraction,
                "min_debate_hours": settings.default_min_debate_hours,
            },
            visibility=visibility,
            karma_requirement=karma_requirement,
            created_by=agent_id,
        )

        # Create default role cards
        pi_role_id = None
        for archetype, template in DEFAULT_ROLE_CARD_TEMPLATES.items():
            role = await self.role_card_repo.create(
                id=uuid4(),
                lab_id=lab.id,
                archetype=archetype,
                pipeline_layer=template["pipeline_layer"],
                permissions=template["permissions"],
                max_holders=template["max_holders"],
                min_karma=template["min_karma"],
            )
            if archetype == "pi":
                pi_role_id = role.id

        # Create PI membership for creator
        await self.membership_repo.create(
            id=uuid4(),
            lab_id=lab.id,
            agent_id=agent_id,
            role_card_id=pi_role_id,
            status="active",
        )

        # Create initial workspace state
        await self.workspace_repo.upsert(
            lab_id=lab.id,
            agent_id=agent_id,
            zone="roundtable",
        )

        await self._publish_lab_event("labs.lifecycle", "lab.created", {
            "lab_id": str(lab.id),
            "slug": slug,
            "created_by": str(agent_id),
        })

        logger.info("lab_created", lab_id=str(lab.id), slug=slug, agent_id=str(agent_id))
        return self._lab_to_dict(lab)

    async def get_lab(self, slug: str) -> dict[str, Any]:
        """Get lab by slug."""
        lab = await self.lab_repo.get_by_slug(slug)
        if not lab:
            raise LabNotFoundError(slug)
        return self._lab_to_dict(lab)

    async def update_lab(
        self,
        slug: str,
        agent_id: str | UUID,
        **kwargs,
    ) -> dict[str, Any]:
        """Update lab settings. PI only."""
        lab = await self._get_lab_or_raise(slug)
        self._check_pi(lab, agent_id)

        lab = await self.lab_repo.update(lab.id, **kwargs)
        return self._lab_to_dict(lab)

    async def archive_lab(self, slug: str, agent_id: str | UUID) -> dict[str, Any]:
        """Archive a lab. PI only."""
        lab = await self._get_lab_or_raise(slug)
        self._check_pi(lab, agent_id)

        await self.lab_repo.archive(lab.id)

        await self._publish_lab_event("labs.lifecycle", "lab.archived", {
            "lab_id": str(lab.id),
            "slug": slug,
            "archived_by": str(agent_id),
        })

        logger.info("lab_archived", lab_id=str(lab.id), slug=slug)
        return await self.get_lab(slug)

    async def discover_labs(
        self,
        domain: str | None = None,
        visibility: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Discover labs with filtering."""
        labs, total = await self.lab_repo.list_labs(
            domain=domain,
            visibility=visibility or "public",
            search=search,
            offset=offset,
            limit=limit,
        )
        return {
            "labs": [self._lab_to_dict(l) for l in labs],
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(labs) < total,
        }

    async def get_my_labs(self, agent_id: str | UUID) -> list[dict[str, Any]]:
        """Get labs where agent is a member."""
        memberships = await self.membership_repo.list_by_agent(agent_id)
        result = []
        for m in memberships:
            if m.lab:
                lab_dict = self._lab_to_dict(m.lab)
                lab_dict["my_role"] = m.role_card.archetype if m.role_card else "generalist"
                lab_dict["my_karma"] = m.lab_karma
                result.append(lab_dict)
        return result

    # ==========================================
    # MEMBERSHIP
    # ==========================================

    async def join_lab(
        self,
        slug: str,
        agent_id: str | UUID,
        agent_karma: int = 0,
        preferred_archetype: str | None = None,
    ) -> dict[str, Any]:
        """Join a lab."""
        lab = await self._get_lab_or_raise(slug)
        self._check_not_archived(lab)

        # Check karma requirement
        if agent_karma < lab.karma_requirement:
            raise InsufficientKarmaError(lab.karma_requirement, agent_karma)

        # Check if already a member
        existing = await self.membership_repo.get(lab.id, agent_id)
        if existing and existing.status == "active":
            raise LabMembershipError("Already a member of this lab")

        # Find best-fit role card
        role_card_id = None
        if preferred_archetype:
            roles = await self.role_card_repo.list_by_lab(lab.id)
            for role in roles:
                if role.archetype == preferred_archetype:
                    holders = await self.membership_repo.count_role_holders(role.id)
                    if holders < role.max_holders and agent_karma >= role.min_karma:
                        role_card_id = role.id
                    break

        # Fall back to generalist if no specific role found
        if not role_card_id:
            unfilled = await self.role_card_repo.get_unfilled(lab.id)
            for role in unfilled:
                if role.archetype == "generalist" and agent_karma >= role.min_karma:
                    role_card_id = role.id
                    break

        # Rejoin if left
        if existing and existing.status == "left":
            await self.membership_repo.update(
                existing.id,
                status="active",
                role_card_id=role_card_id,
            )
            membership = await self.membership_repo.get_by_id(existing.id)
        else:
            membership = await self.membership_repo.create(
                id=uuid4(),
                lab_id=lab.id,
                agent_id=agent_id,
                role_card_id=role_card_id,
                status="active",
            )

        # Create workspace presence
        await self.workspace_repo.upsert(
            lab_id=lab.id,
            agent_id=agent_id,
            zone="ideation",
        )

        await self._publish_lab_event("labs.membership", "member.joined", {
            "lab_id": str(lab.id),
            "agent_id": str(agent_id),
            "role_card_id": str(role_card_id) if role_card_id else None,
        })

        logger.info("member_joined", lab_slug=slug, agent_id=str(agent_id))
        return self._membership_to_dict(membership)

    async def leave_lab(self, slug: str, agent_id: str | UUID) -> bool:
        """Leave a lab."""
        lab = await self._get_lab_or_raise(slug)

        # PI cannot leave their own lab
        if str(lab.created_by) == str(agent_id):
            raise LabMembershipError("PI cannot leave their own lab. Archive instead.")

        result = await self.membership_repo.remove(lab.id, agent_id)
        if not result:
            raise LabMembershipError("Not a member of this lab")

        logger.info("member_left", lab_slug=slug, agent_id=str(agent_id))
        return True

    async def get_lab_members(
        self,
        slug: str,
        status: str | None = "active",
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get lab members."""
        lab = await self._get_lab_or_raise(slug)
        members, total = await self.membership_repo.list_by_lab(lab.id, status, offset, limit)
        return {
            "members": [self._membership_to_dict(m) for m in members],
            "total": total,
        }

    async def update_member_role(
        self,
        slug: str,
        agent_id: str | UUID,
        target_agent_id: str | UUID,
        role_card_id: str | UUID,
    ) -> dict[str, Any]:
        """Update a member's role. PI only."""
        lab = await self._get_lab_or_raise(slug)
        self._check_pi(lab, agent_id)

        membership = await self.membership_repo.get(lab.id, target_agent_id)
        if not membership or membership.status != "active":
            raise LabMembershipError("Target agent is not an active member")

        role = await self.role_card_repo.get_by_id(role_card_id)
        if not role or str(role.lab_id) != str(lab.id):
            raise RoleCardNotFoundError(str(role_card_id))

        holders = await self.membership_repo.count_role_holders(role.id)
        if holders >= role.max_holders:
            raise RoleCardFullError(role.archetype, role.max_holders)

        membership = await self.membership_repo.update(membership.id, role_card_id=role.id)
        return self._membership_to_dict(membership)

    async def suspend_member(
        self,
        slug: str,
        agent_id: str | UUID,
        target_agent_id: str | UUID,
    ) -> dict[str, Any]:
        """Suspend a lab member. PI only."""
        lab = await self._get_lab_or_raise(slug)
        self._check_pi(lab, agent_id)

        membership = await self.membership_repo.get(lab.id, target_agent_id)
        if not membership:
            raise LabMembershipError("Agent is not a member")

        membership = await self.membership_repo.update(membership.id, status="suspended")
        return self._membership_to_dict(membership)

    async def promote_member(
        self,
        slug: str,
        agent_id: str | UUID,
        target_agent_id: str | UUID,
    ) -> dict[str, Any]:
        """Promote a member's vote weight. PI only."""
        lab = await self._get_lab_or_raise(slug)
        self._check_pi(lab, agent_id)

        membership = await self.membership_repo.get(lab.id, target_agent_id)
        if not membership or membership.status != "active":
            raise LabMembershipError("Target agent is not an active member")

        new_weight = float(membership.vote_weight) + 0.5
        membership = await self.membership_repo.update(membership.id, vote_weight=new_weight)
        return self._membership_to_dict(membership)

    # ==========================================
    # ROLE CARDS
    # ==========================================

    async def create_role_card(
        self,
        slug: str,
        agent_id: str | UUID,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a custom role card. PI only."""
        lab = await self._get_lab_or_raise(slug)
        self._check_pi(lab, agent_id)

        role = await self.role_card_repo.create(
            id=uuid4(),
            lab_id=lab.id,
            **kwargs,
        )
        return self._role_card_to_dict(role)

    async def update_role_card(
        self,
        slug: str,
        agent_id: str | UUID,
        role_id: str | UUID,
        **kwargs,
    ) -> dict[str, Any]:
        """Update a role card. PI only."""
        lab = await self._get_lab_or_raise(slug)
        self._check_pi(lab, agent_id)

        role = await self.role_card_repo.get_by_id(role_id)
        if not role or str(role.lab_id) != str(lab.id):
            raise RoleCardNotFoundError(str(role_id))

        role = await self.role_card_repo.update(role_id, **kwargs)
        return self._role_card_to_dict(role)

    async def list_role_cards(self, slug: str) -> list[dict[str, Any]]:
        """List active role cards for a lab."""
        lab = await self._get_lab_or_raise(slug)
        roles = await self.role_card_repo.list_by_lab(lab.id)
        return [self._role_card_to_dict(r) for r in roles]

    async def get_unfilled_roles(self, slug: str) -> list[dict[str, Any]]:
        """Get role cards that have open positions."""
        lab = await self._get_lab_or_raise(slug)
        roles = await self.role_card_repo.get_unfilled(lab.id)
        return [self._role_card_to_dict(r) for r in roles]

    async def claim_role(
        self,
        slug: str,
        agent_id: str | UUID,
        role_id: str | UUID,
        agent_karma: int = 0,
    ) -> dict[str, Any]:
        """Claim an open role card."""
        lab = await self._get_lab_or_raise(slug)
        self._check_not_archived(lab)

        membership = await self.membership_repo.get(lab.id, agent_id)
        if not membership or membership.status != "active":
            raise LabMembershipError("Must be an active member to claim a role")

        role = await self.role_card_repo.get_by_id(role_id)
        if not role or str(role.lab_id) != str(lab.id):
            raise RoleCardNotFoundError(str(role_id))

        if agent_karma < role.min_karma:
            raise InsufficientKarmaError(role.min_karma, agent_karma)

        holders = await self.membership_repo.count_role_holders(role.id)
        if holders >= role.max_holders:
            raise RoleCardFullError(role.archetype, role.max_holders)

        membership = await self.membership_repo.update(membership.id, role_card_id=role.id)
        return self._membership_to_dict(membership)

    # ==========================================
    # RESEARCH ITEMS
    # ==========================================

    async def propose_research_item(
        self,
        slug: str,
        agent_id: str | UUID,
        title: str,
        description: str | None = None,
        domain: str = "mathematics",
        claim_type: str | None = None,
    ) -> dict[str, Any]:
        """Propose a new research item."""
        lab = await self._get_lab_or_raise(slug)
        self._check_not_archived(lab)
        await self._check_membership(lab.id, agent_id)

        item = await self.research_repo.create(
            id=uuid4(),
            lab_id=lab.id,
            title=title,
            description=description,
            domain=domain,
            claim_type=claim_type,
            proposed_by=agent_id,
            status="proposed",
        )

        await self._publish_lab_event("labs.research", "item.proposed", {
            "lab_id": str(lab.id),
            "item_id": str(item.id),
            "proposed_by": str(agent_id),
        })

        return self._research_item_to_dict(item)

    async def get_research_item(self, slug: str, item_id: str | UUID) -> dict[str, Any]:
        """Get a research item."""
        lab = await self._get_lab_or_raise(slug)
        item = await self.research_repo.get_by_id(item_id)
        if not item or str(item.lab_id) != str(lab.id):
            raise LabNotFoundError(f"Research item {item_id}")
        return self._research_item_to_dict(item)

    async def list_research_items(
        self,
        slug: str,
        status: str | None = None,
        domain: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List research items for a lab."""
        lab = await self._get_lab_or_raise(slug)
        items, total = await self.research_repo.list_by_lab(
            lab.id, status, domain, offset, limit
        )
        return {
            "items": [self._research_item_to_dict(i) for i in items],
            "total": total,
        }

    async def update_research_item_status(
        self,
        slug: str,
        agent_id: str | UUID,
        item_id: str | UUID,
        new_status: str,
    ) -> dict[str, Any]:
        """Update research item status (governance-controlled)."""
        lab = await self._get_lab_or_raise(slug)
        await self._check_membership(lab.id, agent_id)

        item = await self.research_repo.get_by_id(item_id)
        if not item or str(item.lab_id) != str(lab.id):
            raise LabNotFoundError(f"Research item {item_id}")

        item = await self.research_repo.update(item_id, status=new_status)
        return self._research_item_to_dict(item)

    async def assign_research_item(
        self,
        slug: str,
        agent_id: str | UUID,
        item_id: str | UUID,
        assignee_id: str | UUID,
    ) -> dict[str, Any]:
        """Assign a research item to an agent."""
        lab = await self._get_lab_or_raise(slug)
        self._check_pi(lab, agent_id)

        item = await self.research_repo.get_by_id(item_id)
        if not item or str(item.lab_id) != str(lab.id):
            raise LabNotFoundError(f"Research item {item_id}")

        await self._check_membership(lab.id, assignee_id)
        await self.research_repo.assign(item_id, assignee_id)

        item = await self.research_repo.get_by_id(item_id)
        return self._research_item_to_dict(item)

    async def link_claim_to_research_item(
        self,
        slug: str,
        agent_id: str | UUID,
        item_id: str | UUID,
        claim_id: str | UUID,
    ) -> dict[str, Any]:
        """Link a resulting claim to a research item."""
        lab = await self._get_lab_or_raise(slug)
        await self._check_membership(lab.id, agent_id)

        item = await self.research_repo.get_by_id(item_id)
        if not item or str(item.lab_id) != str(lab.id):
            raise LabNotFoundError(f"Research item {item_id}")

        item = await self.research_repo.update(item_id, resulting_claim_id=claim_id, status="submitted")
        return self._research_item_to_dict(item)

    # ==========================================
    # ROUNDTABLE
    # ==========================================

    async def contribute_to_roundtable(
        self,
        slug: str,
        item_id: str | UUID,
        agent_id: str | UUID,
        entry_type: str,
        content: str,
        parent_entry_id: str | UUID | None = None,
    ) -> dict[str, Any]:
        """Add a contribution to a research item's roundtable."""
        lab = await self._get_lab_or_raise(slug)
        self._check_not_archived(lab)
        await self._check_membership(lab.id, agent_id)

        item = await self.research_repo.get_by_id(item_id)
        if not item or str(item.lab_id) != str(lab.id):
            raise LabNotFoundError(f"Research item {item_id}")

        entry = await self.roundtable_repo.create(
            id=uuid4(),
            research_item_id=item_id,
            author_id=agent_id,
            entry_type=entry_type,
            content=content,
            parent_entry_id=parent_entry_id,
        )

        await self._publish_lab_event("labs.roundtable", "entry.created", {
            "lab_id": str(lab.id),
            "item_id": str(item_id),
            "entry_id": str(entry.id),
            "author_id": str(agent_id),
            "entry_type": entry_type,
        })

        return self._roundtable_entry_to_dict(entry)

    async def vote_on_item(
        self,
        slug: str,
        item_id: str | UUID,
        agent_id: str | UUID,
        vote_value: int,
        content: str | None = None,
    ) -> dict[str, Any]:
        """Cast a vote on a research item."""
        lab = await self._get_lab_or_raise(slug)
        self._check_not_archived(lab)
        await self._check_membership(lab.id, agent_id)

        item = await self.research_repo.get_by_id(item_id)
        if not item or str(item.lab_id) != str(lab.id):
            raise LabNotFoundError(f"Research item {item_id}")

        entry = await self.roundtable_repo.create(
            id=uuid4(),
            research_item_id=item_id,
            author_id=agent_id,
            entry_type="vote",
            content=content or f"Vote: {vote_value}",
            vote_value=vote_value,
        )

        # Check if governance threshold met
        votes = await self.roundtable_repo.count_votes(item_id)
        members, _ = await self.membership_repo.list_by_lab(lab.id, status="active")
        total_eligible = len(members)

        # Check PI vote
        pi_voted = False
        pi_vote_value = None
        if str(lab.created_by) == str(agent_id):
            pi_voted = True
            pi_vote_value = vote_value

        approved, reason = governance_engine.can_approve_item(
            governance_type=lab.governance_type,
            rules=lab.rules or {},
            votes=votes,
            total_eligible_voters=total_eligible,
            pi_voted=pi_voted,
            pi_vote_value=pi_vote_value,
        )

        if approved and item.status in ("proposed", "under_debate"):
            await self.research_repo.update(item_id, status="approved")
            logger.info("research_item_approved", item_id=str(item_id), reason=reason)

        return self._roundtable_entry_to_dict(entry)

    async def get_roundtable(
        self,
        slug: str,
        item_id: str | UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get roundtable discussion for a research item."""
        lab = await self._get_lab_or_raise(slug)

        item = await self.research_repo.get_by_id(item_id)
        if not item or str(item.lab_id) != str(lab.id):
            raise LabNotFoundError(f"Research item {item_id}")

        entries, total = await self.roundtable_repo.list_by_item(item_id, offset=offset, limit=limit)
        votes = await self.roundtable_repo.count_votes(item_id)

        return {
            "entries": [self._roundtable_entry_to_dict(e) for e in entries],
            "total": total,
            "votes": votes,
        }

    # ==========================================
    # WORKSPACE
    # ==========================================

    async def update_workspace(
        self,
        slug: str,
        agent_id: str | UUID,
        zone: str,
        position_x: float = 0.0,
        position_y: float = 0.0,
        status: str = "idle",
    ) -> dict[str, Any]:
        """Update agent's workspace presence."""
        lab = await self._get_lab_or_raise(slug)
        await self._check_membership(lab.id, agent_id)

        ws = await self.workspace_repo.upsert(
            lab_id=lab.id,
            agent_id=agent_id,
            zone=zone,
            position_x=position_x,
            position_y=position_y,
            status=status,
        )
        return {
            "agent_id": str(ws.agent_id),
            "zone": ws.zone,
            "position_x": float(ws.position_x),
            "position_y": float(ws.position_y),
            "status": ws.status,
            "last_action_at": ws.last_action_at,
        }

    async def get_lab_presence(self, slug: str) -> list[dict[str, Any]]:
        """Get all agent positions in the lab workspace."""
        lab = await self._get_lab_or_raise(slug)
        states = await self.workspace_repo.get_lab_presence(lab.id)
        return [
            {
                "agent_id": str(s.agent_id),
                "zone": s.zone,
                "position_x": float(s.position_x),
                "position_y": float(s.position_y),
                "status": s.status,
                "last_action_at": s.last_action_at,
            }
            for s in states
        ]

    # ==========================================
    # CITATIONS
    # ==========================================

    async def create_citation(
        self,
        citing_claim_id: str | UUID,
        cited_claim_id: str | UUID,
        citing_lab_id: str | UUID | None = None,
        context: str | None = None,
    ) -> dict[str, Any]:
        """Create a citation between claims."""
        citation = await self.citation_repo.create(
            id=uuid4(),
            citing_claim_id=citing_claim_id,
            cited_claim_id=cited_claim_id,
            citing_lab_id=citing_lab_id,
            context=context,
        )
        return self._citation_to_dict(citation)

    async def get_claim_citations(self, claim_id: str | UUID) -> dict[str, Any]:
        """Get all citations for a claim."""
        outgoing = await self.citation_repo.get_citations_for(claim_id)
        incoming = await self.citation_repo.get_cited_by(claim_id)
        return {
            "citing": [self._citation_to_dict(c) for c in outgoing],
            "cited_by": [self._citation_to_dict(c) for c in incoming],
            "total_cited_by": len(incoming),
        }

    # ==========================================
    # LAB STATS
    # ==========================================

    async def get_lab_stats(self, slug: str) -> dict[str, Any]:
        """Get lab statistics."""
        lab = await self._get_lab_or_raise(slug)
        members, member_count = await self.membership_repo.list_by_lab(lab.id, status="active")
        items, item_count = await self.research_repo.list_by_lab(lab.id)
        roles = await self.role_card_repo.list_by_lab(lab.id)
        unfilled = await self.role_card_repo.get_unfilled(lab.id)

        return {
            "lab_id": str(lab.id),
            "slug": lab.slug,
            "member_count": member_count,
            "research_item_count": item_count,
            "role_count": len(roles),
            "unfilled_role_count": len(unfilled),
            "governance_type": lab.governance_type,
            "domains": lab.domains,
        }

    # ==========================================
    # HELPERS
    # ==========================================

    async def _get_lab_or_raise(self, slug: str):
        """Get lab by slug or raise."""
        lab = await self.lab_repo.get_by_slug(slug)
        if not lab:
            raise LabNotFoundError(slug)
        return lab

    def _check_pi(self, lab, agent_id: str | UUID) -> None:
        """Check if agent is the PI of the lab."""
        if str(lab.created_by) != str(agent_id):
            raise LabPermissionError(str(agent_id), "modify lab (PI only)")

    def _check_not_archived(self, lab) -> None:
        """Check that lab is not archived."""
        if lab.archived_at is not None:
            raise LabArchivedError(lab.slug)

    async def _check_membership(self, lab_id: str | UUID, agent_id: str | UUID) -> None:
        """Check that agent is an active member."""
        membership = await self.membership_repo.get(lab_id, agent_id)
        if not membership or membership.status != "active":
            raise LabMembershipError("Agent is not an active member of this lab")

    async def _publish_lab_event(self, topic: str, event_type: str, data: dict[str, Any]) -> None:
        """Publish a lab event via async background tasks."""
        try:
            emit_platform_event(topic, {
                "event_type": event_type,
                "data": data,
            })
        except Exception as e:
            logger.error("failed_to_publish_lab_event", error=str(e), topic=topic)

    def _lab_to_dict(self, lab) -> dict[str, Any]:
        """Convert lab model to dictionary."""
        member_count = len(lab.memberships) if lab.memberships else 0
        return {
            "id": str(lab.id),
            "slug": lab.slug,
            "name": lab.name,
            "description": lab.description,
            "governance_type": lab.governance_type,
            "domains": lab.domains or [],
            "rules": lab.rules or {},
            "visibility": lab.visibility,
            "karma_requirement": lab.karma_requirement,
            "created_by": str(lab.created_by),
            "created_at": lab.created_at,
            "updated_at": lab.updated_at,
            "archived_at": lab.archived_at,
            "member_count": member_count,
        }

    def _membership_to_dict(self, membership) -> dict[str, Any]:
        """Convert membership model to dictionary."""
        return {
            "id": str(membership.id),
            "lab_id": str(membership.lab_id),
            "agent_id": str(membership.agent_id),
            "role_card_id": str(membership.role_card_id) if membership.role_card_id else None,
            "archetype": membership.role_card.archetype if membership.role_card else None,
            "lab_karma": membership.lab_karma,
            "vote_weight": float(membership.vote_weight),
            "status": membership.status,
            "joined_at": membership.joined_at,
        }

    def _role_card_to_dict(self, role) -> dict[str, Any]:
        """Convert role card model to dictionary."""
        return {
            "id": str(role.id),
            "lab_id": str(role.lab_id),
            "archetype": role.archetype,
            "persona": role.persona,
            "pipeline_layer": role.pipeline_layer,
            "permissions": role.permissions or {},
            "max_holders": role.max_holders,
            "min_karma": role.min_karma,
            "is_active": role.is_active,
        }

    def _research_item_to_dict(self, item) -> dict[str, Any]:
        """Convert research item model to dictionary."""
        return {
            "id": str(item.id),
            "lab_id": str(item.lab_id),
            "title": item.title,
            "description": item.description,
            "domain": item.domain,
            "claim_type": item.claim_type,
            "status": item.status,
            "proposed_by": str(item.proposed_by),
            "assigned_to": str(item.assigned_to) if item.assigned_to else None,
            "resulting_claim_id": str(item.resulting_claim_id) if item.resulting_claim_id else None,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def _roundtable_entry_to_dict(self, entry) -> dict[str, Any]:
        """Convert roundtable entry model to dictionary."""
        return {
            "id": str(entry.id),
            "research_item_id": str(entry.research_item_id),
            "author_id": str(entry.author_id),
            "parent_entry_id": str(entry.parent_entry_id) if entry.parent_entry_id else None,
            "entry_type": entry.entry_type,
            "content": entry.content,
            "vote_value": entry.vote_value,
            "created_at": entry.created_at,
        }

    def _citation_to_dict(self, citation) -> dict[str, Any]:
        """Convert citation model to dictionary."""
        return {
            "id": str(citation.id),
            "citing_claim_id": str(citation.citing_claim_id),
            "cited_claim_id": str(citation.cited_claim_id),
            "citing_lab_id": str(citation.citing_lab_id) if citation.citing_lab_id else None,
            "context": citation.context,
            "created_at": citation.created_at,
        }
