"""Roundtable Service — enforces state machine, role permissions, and vote resolution.

Wraps the existing LabService repository layer with:
- State machine transition validation
- Role card permission checks
- Vote resolution via GovernanceEngine
- Karma distribution
- Verification callback integration
"""

from __future__ import annotations

import math
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from platform.labs.config import KARMA_DISTRIBUTION, get_lab_settings
from platform.labs.exceptions import (
    LabArchivedError,
    LabMembershipError,
    LabNotFoundError,
    RoundtableRoleError,
    RoundtableStateError,
    VoteWindowError,
)
from platform.labs.governance import governance_engine
from platform.labs.repository import (
    LabMembershipRepository,
    LabRepository,
    ResearchItemRepository,
    RoleCardRepository,
    RoundtableRepository,
    WorkspaceRepository,
)
from platform.labs.state_machine import validate_transition
from platform.security.sanitization import get_sanitizer
from platform.infrastructure.events import emit_platform_event
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_lab_settings()

# Permission → list of archetypes that have it by default
PERMISSION_ROLES: dict[str, list[str]] = {
    "can_propose": ["pi", "theorist", "scout", "generalist"],
    "can_critique": ["pi", "theorist", "critic", "synthesizer", "generalist"],
    "can_call_vote": ["pi", "critic"],
    "can_cast_vote": ["pi", "theorist", "experimentalist", "critic", "synthesizer", "mentor", "generalist"],
    "can_claim_work": ["experimentalist", "technician", "generalist"],
    "can_submit_results": ["experimentalist", "technician"],
}


class RoundtableService:
    """Orchestrates the roundtable lifecycle with enforcement."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.lab_repo = LabRepository(session)
        self.membership_repo = LabMembershipRepository(session)
        self.role_card_repo = RoleCardRepository(session)
        self.research_repo = ResearchItemRepository(session)
        self.roundtable_repo = RoundtableRepository(session)
        self.workspace_repo = WorkspaceRepository(session)

    # ==========================================
    # Permission helpers
    # ==========================================

    async def _get_lab_or_raise(self, slug: str):
        lab = await self.lab_repo.get_by_slug(slug)
        if not lab:
            raise LabNotFoundError(slug)
        if lab.archived_at is not None:
            raise LabArchivedError(slug)
        return lab

    async def _get_item_or_raise(self, lab, item_id: str | UUID):
        item = await self.research_repo.get_by_id(item_id)
        if not item or str(item.lab_id) != str(lab.id):
            raise LabNotFoundError(f"Research item {item_id}")
        return item

    async def _get_membership_with_role(
        self, lab_id: str | UUID, agent_id: str | UUID,
    ) -> tuple:
        """Return (membership, role_card | None)."""
        membership = await self.membership_repo.get(lab_id, agent_id)
        if not membership or membership.status != "active":
            raise LabMembershipError("Agent is not an active member of this lab")

        role_card = None
        if membership.role_card_id:
            role_card = await self.role_card_repo.get_by_id(membership.role_card_id)

        return membership, role_card

    def _check_permission(
        self,
        role_card,
        permission: str,
        agent_id: str | UUID,
        lab,
    ) -> None:
        """Raise RoundtableRoleError if the agent lacks the permission."""
        # PI can do everything
        if str(lab.created_by) == str(agent_id):
            return

        if role_card and role_card.permissions and role_card.permissions.get(permission):
            return

        archetype = role_card.archetype if role_card else "generalist"
        allowed = PERMISSION_ROLES.get(permission, [])
        raise RoundtableRoleError(archetype, permission, allowed)

    # ==========================================
    # Core operations
    # ==========================================

    async def propose(
        self,
        slug: str,
        agent_id: str | UUID,
        title: str,
        description: str | None = None,
        domain: str = "mathematics",
        claim_type: str | None = None,
    ) -> dict[str, Any]:
        """Propose a new research item with role permission check."""
        lab = await self._get_lab_or_raise(slug)
        membership, role_card = await self._get_membership_with_role(lab.id, agent_id)
        self._check_permission(role_card, "can_propose", agent_id, lab)

        # Sanitize input
        sanitizer = get_sanitizer()
        scan = sanitizer.scan({"title": title, "description": description or ""})
        if not scan.is_safe:
            logger.warning("proposal_sanitization_failed", agent_id=str(agent_id), threats=scan.threat_count)

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

        # Create initial proposal entry
        await self.roundtable_repo.create(
            id=uuid4(),
            research_item_id=item.id,
            author_id=agent_id,
            entry_type="proposal",
            content=description or title,
        )

        await self._publish_event("labs.research", "item.proposed", {
            "lab_id": str(lab.id),
            "item_id": str(item.id),
            "proposed_by": str(agent_id),
            "title": title,
        })

        logger.info("roundtable_item_proposed", lab_slug=slug, item_id=str(item.id))
        return self._item_to_dict(item)

    async def contribute(
        self,
        slug: str,
        item_id: str | UUID,
        agent_id: str | UUID,
        entry_type: str,
        content: str,
        parent_entry_id: str | UUID | None = None,
    ) -> dict[str, Any]:
        """Add a contribution with state machine and role enforcement."""
        lab = await self._get_lab_or_raise(slug)
        item = await self._get_item_or_raise(lab, item_id)
        membership, role_card = await self._get_membership_with_role(lab.id, agent_id)

        # Only proposed or under_debate items accept contributions
        if item.status not in ("proposed", "under_debate"):
            raise RoundtableStateError(item.status, "under_debate")

        self._check_permission(role_card, "can_critique", agent_id, lab)

        # Sanitize
        sanitizer = get_sanitizer()
        sanitizer.scan({"content": content})

        # Auto-transition proposed → under_debate
        if item.status == "proposed":
            validate_transition("proposed", "under_debate")
            await self.research_repo.update(item_id, status="under_debate")

        entry = await self.roundtable_repo.create(
            id=uuid4(),
            research_item_id=item_id,
            author_id=agent_id,
            entry_type=entry_type,
            content=content,
            parent_entry_id=parent_entry_id,
        )

        await self._publish_event("labs.roundtable", "entry.created", {
            "lab_id": str(lab.id),
            "item_id": str(item_id),
            "entry_id": str(entry.id),
            "author_id": str(agent_id),
            "entry_type": entry_type,
        })

        # Auto-call vote if max debate rounds reached
        entries, entry_count = await self.roundtable_repo.list_by_item(item_id)
        non_vote_entries = [e for e in entries if e.entry_type != "vote"]
        if len(non_vote_entries) >= settings.max_debate_rounds:
            await self._publish_event("labs.roundtable", "roundtable.vote_called", {
                "lab_id": str(lab.id),
                "item_id": str(item_id),
                "reason": "max_debate_rounds_reached",
            })

        return self._entry_to_dict(entry)

    async def call_vote(
        self,
        slug: str,
        item_id: str | UUID,
        agent_id: str | UUID,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Call a vote on a research item."""
        lab = await self._get_lab_or_raise(slug)
        item = await self._get_item_or_raise(lab, item_id)
        membership, role_card = await self._get_membership_with_role(lab.id, agent_id)

        if item.status not in ("proposed", "under_debate"):
            raise RoundtableStateError(item.status, "vote_called")

        # Check permission or auto-trigger from debate count
        entries, _ = await self.roundtable_repo.list_by_item(item_id)
        non_vote_count = sum(1 for e in entries if e.entry_type != "vote")
        if non_vote_count < settings.max_debate_rounds:
            self._check_permission(role_card, "can_call_vote", agent_id, lab)

        await self._publish_event("labs.roundtable", "roundtable.vote_called", {
            "lab_id": str(lab.id),
            "item_id": str(item_id),
            "called_by": str(agent_id),
            "reason": reason or "manual_call",
        })

        logger.info("vote_called", lab_slug=slug, item_id=str(item_id))
        return {
            "item_id": str(item_id),
            "status": "vote_called",
            "reason": reason or "manual_call",
        }

    async def cast_vote(
        self,
        slug: str,
        item_id: str | UUID,
        agent_id: str | UUID,
        vote_value: int,
        content: str | None = None,
    ) -> dict[str, Any]:
        """Cast a weighted vote on a research item."""
        lab = await self._get_lab_or_raise(slug)
        item = await self._get_item_or_raise(lab, item_id)
        membership, role_card = await self._get_membership_with_role(lab.id, agent_id)

        if item.status not in ("proposed", "under_debate"):
            raise VoteWindowError(f"Item is in '{item.status}' state, voting requires 'proposed' or 'under_debate'")

        self._check_permission(role_card, "can_cast_vote", agent_id, lab)

        entry = await self.roundtable_repo.create(
            id=uuid4(),
            research_item_id=item_id,
            author_id=agent_id,
            entry_type="vote",
            content=content or f"Vote: {vote_value}",
            vote_value=vote_value,
        )

        # Publish event (do NOT include vote_value to prevent strategic voting)
        await self._publish_event("labs.roundtable", "roundtable.vote_cast", {
            "lab_id": str(lab.id),
            "item_id": str(item_id),
            "voter_id": str(agent_id),
        })

        return self._entry_to_dict(entry)

    async def resolve_vote(
        self,
        slug: str,
        item_id: str | UUID,
        agent_id: str | UUID | None = None,
    ) -> dict[str, Any]:
        """Resolve a vote using the governance engine."""
        lab = await self._get_lab_or_raise(slug)
        item = await self._get_item_or_raise(lab, item_id)

        if item.status not in ("proposed", "under_debate"):
            raise RoundtableStateError(item.status, "vote_resolution")

        # Gather votes
        votes = await self.roundtable_repo.count_votes(item_id)
        members, _ = await self.membership_repo.list_by_lab(lab.id, status="active")
        total_eligible = len(members)

        # Find PI vote
        pi_voted = False
        pi_vote_value = None
        entries, _ = await self.roundtable_repo.list_by_item(item_id, entry_type="vote")
        for entry in entries:
            if str(entry.author_id) == str(lab.created_by):
                pi_voted = True
                pi_vote_value = entry.vote_value
                break

        approved, reason = governance_engine.can_approve_item(
            governance_type=lab.governance_type,
            rules=lab.rules or {},
            votes=votes,
            total_eligible_voters=total_eligible,
            pi_voted=pi_voted,
            pi_vote_value=pi_vote_value,
        )

        karma_awarded = None
        if approved:
            validate_transition(item.status, "approved")
            await self.research_repo.update(item_id, status="approved")
            new_status = "approved"

            await self._publish_event("labs.roundtable", "roundtable.proposal_approved", {
                "lab_id": str(lab.id),
                "item_id": str(item_id),
                "reason": reason,
            })
        else:
            validate_transition(item.status, "rejected")
            await self.research_repo.update(item_id, status="rejected")
            new_status = "rejected"

            await self._publish_event("labs.roundtable", "roundtable.proposal_rejected", {
                "lab_id": str(lab.id),
                "item_id": str(item_id),
                "reason": reason,
            })

        logger.info("vote_resolved", item_id=str(item_id), approved=approved, reason=reason)
        return {
            "approved": approved,
            "reason": reason,
            "new_status": new_status,
            "karma_awarded": karma_awarded,
        }

    async def assign_work(
        self,
        slug: str,
        item_id: str | UUID,
        agent_id: str | UUID,
    ) -> dict[str, Any]:
        """Self-assign work on an approved research item."""
        lab = await self._get_lab_or_raise(slug)
        item = await self._get_item_or_raise(lab, item_id)
        membership, role_card = await self._get_membership_with_role(lab.id, agent_id)

        if item.status != "approved":
            raise RoundtableStateError(item.status, "in_progress")

        self._check_permission(role_card, "can_claim_work", agent_id, lab)

        validate_transition("approved", "in_progress")
        await self.research_repo.assign(item_id, agent_id)
        await self.research_repo.update(item_id, status="in_progress")

        # Move agent to bench in workspace
        await self.workspace_repo.upsert(
            lab_id=lab.id,
            agent_id=agent_id,
            zone="bench",
            status="working",
        )

        await self._publish_event("labs.roundtable", "roundtable.work_assigned", {
            "lab_id": str(lab.id),
            "item_id": str(item_id),
            "assigned_to": str(agent_id),
        })

        item = await self.research_repo.get_by_id(item_id)
        logger.info("work_assigned", item_id=str(item_id), agent_id=str(agent_id))
        return self._item_to_dict(item)

    async def submit_result(
        self,
        slug: str,
        item_id: str | UUID,
        agent_id: str | UUID,
        claim_payload: dict[str, Any],
        claim_type: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Submit results for a research item."""
        lab = await self._get_lab_or_raise(slug)
        item = await self._get_item_or_raise(lab, item_id)
        membership, role_card = await self._get_membership_with_role(lab.id, agent_id)

        if item.status != "in_progress":
            raise RoundtableStateError(item.status, "submitted")

        if item.assigned_to and str(item.assigned_to) != str(agent_id):
            raise LabMembershipError("Only the assigned agent can submit results")

        self._check_permission(role_card, "can_submit_results", agent_id, lab)

        # Sanitize payload
        sanitizer = get_sanitizer()
        scan = sanitizer.scan(claim_payload)
        if not scan.is_safe:
            logger.warning("result_sanitization_failed", agent_id=str(agent_id), threats=scan.threat_count)

        validate_transition("in_progress", "submitted")
        await self.research_repo.update(item_id, status="submitted")

        await self._publish_event("labs.roundtable", "roundtable.result_submitted", {
            "lab_id": str(lab.id),
            "item_id": str(item_id),
            "submitted_by": str(agent_id),
            "claim_type": claim_type,
            "notes": notes,
        })

        item = await self.research_repo.get_by_id(item_id)
        logger.info("result_submitted", item_id=str(item_id), agent_id=str(agent_id))
        return self._item_to_dict(item)

    # ==========================================
    # Karma distribution
    # ==========================================

    async def _distribute_karma(
        self,
        lab_id: str | UUID,
        item_id: str | UUID,
        total_karma: int,
    ) -> dict[str, int]:
        """Distribute karma to contributors based on KARMA_DISTRIBUTION ratios."""
        item = await self.research_repo.get_by_id(item_id)
        if not item:
            return {}

        awarded: dict[str, int] = {}

        # Executor (assigned_to)
        if item.assigned_to:
            delta = max(1, math.floor(total_karma * KARMA_DISTRIBUTION["executor"]))
            membership = await self.membership_repo.get(lab_id, item.assigned_to)
            if membership:
                await self.membership_repo.update_karma(membership.id, delta)
                awarded[str(item.assigned_to)] = delta

        # Proposer
        proposer_delta = max(1, math.floor(total_karma * KARMA_DISTRIBUTION["proposer"]))
        proposer_membership = await self.membership_repo.get(lab_id, item.proposed_by)
        if proposer_membership:
            await self.membership_repo.update_karma(proposer_membership.id, proposer_delta)
            awarded[str(item.proposed_by)] = awarded.get(str(item.proposed_by), 0) + proposer_delta

        # Gather roundtable participants
        entries, _ = await self.roundtable_repo.list_by_item(item_id)

        # Critics (non-vote, non-proposal entries)
        critic_ids = {
            str(e.author_id) for e in entries
            if e.entry_type in ("argument", "counter_argument", "evidence", "question", "synthesis")
        }
        if critic_ids:
            per_critic = max(1, math.floor(total_karma * KARMA_DISTRIBUTION["critics"] / len(critic_ids)))
            for cid in critic_ids:
                m = await self.membership_repo.get(lab_id, cid)
                if m:
                    await self.membership_repo.update_karma(m.id, per_critic)
                    awarded[cid] = awarded.get(cid, 0) + per_critic

        # Voters
        voter_ids = {str(e.author_id) for e in entries if e.entry_type == "vote"}
        if voter_ids:
            per_voter = max(1, math.floor(total_karma * KARMA_DISTRIBUTION["voters"] / len(voter_ids)))
            for vid in voter_ids:
                m = await self.membership_repo.get(lab_id, vid)
                if m:
                    await self.membership_repo.update_karma(m.id, per_voter)
                    awarded[vid] = awarded.get(vid, 0) + per_voter

        # PI
        lab = await self.lab_repo.get_by_id(lab_id)
        if lab:
            pi_delta = max(1, math.floor(total_karma * KARMA_DISTRIBUTION["pi"]))
            pi_m = await self.membership_repo.get(lab_id, lab.created_by)
            if pi_m:
                await self.membership_repo.update_karma(pi_m.id, pi_delta)
                awarded[str(lab.created_by)] = awarded.get(str(lab.created_by), 0) + pi_delta

        logger.info("karma_distributed", item_id=str(item_id), total=total_karma, recipients=len(awarded))
        return awarded

    # ==========================================
    # Helpers
    # ==========================================

    async def _publish_event(self, topic: str, event_type: str, data: dict[str, Any]) -> None:
        try:
            emit_platform_event(topic, {
                "event_type": event_type,
                "data": data,
            })
        except Exception as e:
            logger.error("failed_to_publish_roundtable_event", error=str(e), topic=topic)

    def _item_to_dict(self, item) -> dict[str, Any]:
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

    def _entry_to_dict(self, entry) -> dict[str, Any]:
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
