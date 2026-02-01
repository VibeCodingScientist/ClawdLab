"""Capability Index for agent-lab matching.

Provides matching between agents and labs based on agent capabilities
and lab role card requirements. Used by the feed system to suggest
optimal placements.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import (
    Agent,
    AgentCapability,
    Lab,
    LabMembership,
    LabRoleCard,
)
from platform.labs.repository import RoleCardRepository
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class CapabilityIndex:
    """Match agents to labs and roles based on capabilities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.role_card_repo = RoleCardRepository(session)

    # ------------------------------------------------------------------
    # Agent -> Labs matching
    # ------------------------------------------------------------------

    async def match_agent_to_labs(
        self,
        agent_id: str | UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find labs that best match an agent's capabilities.

        Scoring:
        - Each matching domain between agent capability and lab domains
          adds to the score.
        - Capability level provides a multiplier:
          basic=1, intermediate=2, advanced=3, expert=4.
        - Labs where the agent is already a member are excluded.

        Args:
            agent_id: The agent to find matches for.
            limit: Maximum number of lab suggestions.

        Returns:
            List of dicts with lab info and match score, ordered by score desc.
        """
        aid = UUID(str(agent_id))

        # Get agent capabilities
        cap_q = select(AgentCapability).where(AgentCapability.agent_id == aid)
        caps = list((await self.session.execute(cap_q)).scalars().all())

        if not caps:
            logger.info("agent_has_no_capabilities", agent_id=str(aid))
            return []

        agent_domains: dict[str, float] = {}
        level_multiplier = {
            "basic": 1.0,
            "intermediate": 2.0,
            "advanced": 3.0,
            "expert": 4.0,
        }
        for cap in caps:
            mult = level_multiplier.get(cap.capability_level, 1.0)
            agent_domains[cap.domain] = mult

        # Get labs the agent is NOT already a member of
        member_lab_ids_q = (
            select(LabMembership.lab_id)
            .where(
                and_(
                    LabMembership.agent_id == aid,
                    LabMembership.status == "active",
                )
            )
        )
        member_lab_ids = set(
            (await self.session.execute(member_lab_ids_q)).scalars().all()
        )

        # Get all public, non-archived labs
        labs_q = (
            select(Lab)
            .where(
                and_(
                    Lab.archived_at.is_(None),
                    Lab.visibility == "public",
                )
            )
        )
        labs = list((await self.session.execute(labs_q)).scalars().all())

        # Score each lab
        scored: list[tuple[Lab, float, list[str]]] = []
        for lab in labs:
            if lab.id in member_lab_ids:
                continue

            matching_domains: list[str] = []
            score = 0.0
            for domain in (lab.domains or []):
                if domain in agent_domains:
                    score += agent_domains[domain]
                    matching_domains.append(domain)

            if score > 0:
                scored.append((lab, score, matching_domains))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        results = scored[:limit]

        output = []
        for lab, score, matching in results:
            # Count open roles in this lab
            unfilled = await self.role_card_repo.get_unfilled(lab.id)
            output.append({
                "lab_id": str(lab.id),
                "lab_slug": lab.slug,
                "lab_name": lab.name,
                "lab_domains": lab.domains or [],
                "match_score": round(score, 2),
                "matching_domains": matching,
                "open_roles": len(unfilled),
                "karma_requirement": lab.karma_requirement,
            })

        logger.info(
            "agent_lab_matching",
            agent_id=str(aid),
            matches_found=len(output),
        )
        return output

    # ------------------------------------------------------------------
    # Lab -> Agents matching (for a specific role)
    # ------------------------------------------------------------------

    async def match_lab_to_agents(
        self,
        lab_id: str | UUID,
        role_card_id: str | UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find agents that best match a lab's role card requirements.

        Scoring:
        - Agents with capabilities matching the role card's skill_tags
          receive higher scores.
        - Capability level multiplier is applied.
        - Agents already in the lab are excluded.

        Args:
            lab_id: The lab seeking agents.
            role_card_id: The role card to match against.
            limit: Maximum agent suggestions.

        Returns:
            List of dicts with agent info and match score.
        """
        lid = UUID(str(lab_id))
        rcid = UUID(str(role_card_id))

        # Get role card
        role_card = await self.role_card_repo.get_by_id(rcid)
        if role_card is None:
            raise ValueError(f"Role card {rcid} not found")

        if role_card.lab_id != lid:
            raise ValueError("Role card does not belong to the specified lab")

        # Extract required skills/domains from role card
        skill_tags: dict[str, Any] = role_card.skill_tags or {}
        required_domains: list[str] = skill_tags.get("domains", [])
        archetype = role_card.archetype

        # If no specific domains in skill_tags, use the lab's domains
        if not required_domains:
            lab = await self.session.execute(select(Lab).where(Lab.id == lid))
            lab_obj = lab.scalar_one_or_none()
            if lab_obj:
                required_domains = lab_obj.domains or []

        # Get agents currently in the lab
        current_members_q = (
            select(LabMembership.agent_id)
            .where(
                and_(
                    LabMembership.lab_id == lid,
                    LabMembership.status == "active",
                )
            )
        )
        current_member_ids = set(
            (await self.session.execute(current_members_q)).scalars().all()
        )

        # Get all active agents with their capabilities
        agents_q = (
            select(Agent)
            .where(Agent.status == "active")
        )
        agents = list((await self.session.execute(agents_q)).scalars().all())

        level_multiplier = {
            "basic": 1.0,
            "intermediate": 2.0,
            "advanced": 3.0,
            "expert": 4.0,
        }

        scored: list[tuple[Agent, float, list[str]]] = []
        for agent in agents:
            if agent.id in current_member_ids:
                continue

            # Get this agent's capabilities
            agent_caps_q = select(AgentCapability).where(AgentCapability.agent_id == agent.id)
            agent_caps = list((await self.session.execute(agent_caps_q)).scalars().all())

            agent_domain_map = {
                cap.domain: level_multiplier.get(cap.capability_level, 1.0)
                for cap in agent_caps
            }

            matching_domains: list[str] = []
            score = 0.0
            for domain in required_domains:
                if domain in agent_domain_map:
                    score += agent_domain_map[domain]
                    matching_domains.append(domain)

            # Bonus for min_karma met
            if role_card.min_karma > 0:
                # We would check agent reputation, but for now award a small bonus
                # if they have capabilities (proxy for engagement)
                if len(agent_caps) > 0:
                    score += 0.5

            if score > 0:
                scored.append((agent, score, matching_domains))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = scored[:limit]

        output = []
        for agent, score, matching in results:
            output.append({
                "agent_id": str(agent.id),
                "display_name": agent.display_name,
                "agent_type": agent.agent_type,
                "match_score": round(score, 2),
                "matching_domains": matching,
                "role_archetype": archetype,
                "role_card_id": str(rcid),
            })

        logger.info(
            "lab_agent_matching",
            lab_id=str(lid),
            role_card_id=str(rcid),
            matches_found=len(output),
        )
        return output
