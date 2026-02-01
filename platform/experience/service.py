"""ExperienceService — core business logic for XP, leveling, tiers, and prestige."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from platform.shared.utils.logging import get_logger

from .calculator import (
    DOMAIN_DIFFICULTY,
    XPSource,
    calculate_xp,
    evaluate_tier,
    level_from_xp,
    xp_for_level,
)
from .milestones import MILESTONES, check_milestones
from .schemas import (
    AgentExperienceResponse,
    DomainXPDetail,
    MilestoneResponse,
    XPAwardResponse,
    XPEventResponse,
)

logger = get_logger(__name__)

# Domain column name mapping
DOMAIN_XP_COLUMNS = {
    "mathematics": "math_xp",
    "ml_ai": "ml_ai_xp",
    "computational_biology": "comp_bio_xp",
    "materials_science": "materials_xp",
    "bioinformatics": "bioinformatics_xp",
}

DOMAIN_LEVEL_COLUMNS = {
    "mathematics": "math_level",
    "ml_ai": "ml_ai_level",
    "computational_biology": "comp_bio_level",
    "materials_science": "materials_level",
    "bioinformatics": "bioinformatics_level",
}

ROLE_XP_COLUMNS = {
    "theory": "theory_xp",
    "execution": "execution_xp",
    "review": "review_xp",
    "scouting": "scouting_xp",
    "coordination": "coordination_xp",
}


class ExperienceService:
    """Manages agent XP, leveling, tiers, and prestige."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def award_xp(
        self,
        agent_id: UUID,
        source: XPSource,
        domain: str | None,
        verification_score: float,
        role_category: str,
        source_id: UUID | None = None,
        lab_slug: str | None = None,
    ) -> XPAwardResponse:
        """Award XP to an agent and update levels/tiers."""
        from platform.infrastructure.database.models import (
            AgentExperience,
            AgentMilestone,
            AgentXPEvent,
        )

        # 1. Load current experience (with row lock)
        result = await self.session.execute(
            select(AgentExperience)
            .where(AgentExperience.agent_id == agent_id)
            .with_for_update()
        )
        exp = result.scalar_one_or_none()

        if exp is None:
            # Create initial experience record
            exp = AgentExperience(agent_id=agent_id)
            self.session.add(exp)
            await self.session.flush()

        # 2. Calculate XP
        award = calculate_xp(
            source=source,
            domain=domain,
            verification_score=verification_score,
            prestige_bonus=float(exp.prestige_bonus),
            role_category=role_category,
        )

        # 3. Update global XP
        old_level = exp.global_level
        exp.total_xp += award.total
        exp.global_level = level_from_xp(exp.total_xp)

        # 4. Update domain XP
        if domain and domain in DOMAIN_XP_COLUMNS:
            xp_col = DOMAIN_XP_COLUMNS[domain]
            level_col = DOMAIN_LEVEL_COLUMNS[domain]
            current_domain_xp = getattr(exp, xp_col) + award.total
            setattr(exp, xp_col, current_domain_xp)
            setattr(exp, level_col, level_from_xp(current_domain_xp))

        # 5. Update role XP
        if role_category and role_category in ROLE_XP_COLUMNS:
            role_col = ROLE_XP_COLUMNS[role_category]
            setattr(exp, role_col, getattr(exp, role_col) + award.total)

        # 6. Update timestamp
        exp.last_xp_event_at = datetime.now(timezone.utc)
        exp.updated_at = datetime.now(timezone.utc)

        # 7. Check tier
        domain_levels = self._get_domain_levels(exp)
        sorted_levels = sorted(domain_levels.values(), reverse=True)
        old_tier = exp.tier

        # Get reputation stats for tier evaluation
        from platform.infrastructure.database.models import AgentReputation
        rep_result = await self.session.execute(
            select(AgentReputation).where(AgentReputation.agent_id == agent_id)
        )
        rep = rep_result.scalar_one_or_none()

        claims_verified = rep.claims_verified if rep else 0
        success_rate = float(rep.success_rate) if rep and rep.success_rate else 0.0

        # Count medals for tier evaluation
        from platform.infrastructure.database.models import ChallengeMedal
        from sqlalchemy import func
        medal_count_result = await self.session.execute(
            select(func.count()).where(ChallengeMedal.agent_id == agent_id)
        )
        total_medals = medal_count_result.scalar() or 0

        gold_count_result = await self.session.execute(
            select(func.count()).where(
                ChallengeMedal.agent_id == agent_id,
                ChallengeMedal.medal_type == "gold",
            )
        )
        gold_medals = gold_count_result.scalar() or 0

        new_tier = evaluate_tier(
            max_domain_level=sorted_levels[0] if sorted_levels else 0,
            second_domain_level=sorted_levels[1] if len(sorted_levels) > 1 else 0,
            claims_verified=claims_verified,
            challenge_medals=total_medals,
            gold_medals=gold_medals,
            solo_golds=0,  # Simplified — track separately if needed
            success_rate=success_rate,
            max_citation_count=0,  # Would need citation query
        )

        tier_changed = new_tier != old_tier
        if tier_changed:
            exp.tier = new_tier

        # 8. Write XP event
        xp_event = AgentXPEvent(
            agent_id=agent_id,
            xp_amount=award.total,
            domain=domain,
            role_category=role_category,
            source_type=source.value,
            source_id=source_id,
            lab_slug=lab_slug,
            multiplier=float(exp.prestige_bonus),
        )
        self.session.add(xp_event)

        # 9. Check milestones
        unlocked_slugs_result = await self.session.execute(
            select(AgentMilestone.milestone_slug).where(
                AgentMilestone.agent_id == agent_id
            )
        )
        already_unlocked = set(unlocked_slugs_result.scalars().all())

        max_score = float(verification_score) if verification_score else 0.0
        newly_unlocked = check_milestones(
            claims_verified=claims_verified,
            max_verification_score=max_score,
            domain_levels=domain_levels,
            challenge_medals=total_medals,
            gold_medals=gold_medals,
            max_citation_count=0,
            reviews_accepted=0,
            proposals_approved=0,
            prestige_count=exp.prestige_count,
            already_unlocked=already_unlocked,
        )

        milestone_slugs: list[str] = []
        for slug, metadata in newly_unlocked:
            milestone = AgentMilestone(
                agent_id=agent_id,
                milestone_slug=slug,
                metadata_=metadata,
            )
            self.session.add(milestone)
            milestone_slugs.append(slug)

        await self.session.flush()

        level_up = exp.global_level > old_level

        logger.info(
            "Awarded %d XP to agent %s (source=%s, domain=%s, level=%d→%d)",
            award.total,
            agent_id,
            source.value,
            domain,
            old_level,
            exp.global_level,
        )

        return XPAwardResponse(
            agent_id=agent_id,
            xp_amount=award.total,
            domain=domain,
            role_category=role_category,
            source_type=source.value,
            new_total_xp=exp.total_xp,
            new_global_level=exp.global_level,
            level_up=level_up,
            tier_changed=tier_changed,
            new_tier=new_tier if tier_changed else None,
            milestones_unlocked=milestone_slugs,
        )

    async def prestige(self, agent_id: UUID, domain: str) -> dict:
        """Reset domain XP and increment prestige counter."""
        from platform.infrastructure.database.models import AgentExperience

        result = await self.session.execute(
            select(AgentExperience)
            .where(AgentExperience.agent_id == agent_id)
            .with_for_update()
        )
        exp = result.scalar_one_or_none()
        if exp is None:
            raise ValueError(f"No experience record for agent {agent_id}")

        if domain not in DOMAIN_XP_COLUMNS:
            raise ValueError(f"Invalid domain: {domain}")

        level_col = DOMAIN_LEVEL_COLUMNS[domain]
        current_level = getattr(exp, level_col)
        if current_level < 50:
            raise ValueError(f"Domain level must be 50+ to prestige (current: {current_level})")

        # Reset domain XP and level
        xp_col = DOMAIN_XP_COLUMNS[domain]
        setattr(exp, xp_col, 0)
        setattr(exp, level_col, 0)

        # Increment prestige (cap bonus at 2.0 = 20 prestiges)
        MAX_PRESTIGE_BONUS = 2.0
        exp.prestige_count += 1
        exp.prestige_bonus = min(float(exp.prestige_bonus) + 0.05, MAX_PRESTIGE_BONUS)

        # Recalculate global level from remaining XP
        # Global XP stays the same — prestige only resets domain
        exp.updated_at = datetime.now(timezone.utc)

        await self.session.flush()

        logger.info(
            "Agent %s prestiged in %s (count=%d, bonus=%.2f)",
            agent_id,
            domain,
            exp.prestige_count,
            exp.prestige_bonus,
        )

        return {
            "agent_id": str(agent_id),
            "domain": domain,
            "prestige_count": exp.prestige_count,
            "prestige_bonus": float(exp.prestige_bonus),
        }

    async def get_experience(self, agent_id: UUID) -> AgentExperienceResponse:
        """Full experience profile for display."""
        from platform.infrastructure.database.models import AgentExperience

        result = await self.session.execute(
            select(AgentExperience).where(AgentExperience.agent_id == agent_id)
        )
        exp = result.scalar_one_or_none()

        if exp is None:
            return AgentExperienceResponse(
                agent_id=agent_id,
                total_xp=0,
                global_level=1,
                tier="novice",
                prestige_count=0,
                prestige_bonus=1.0,
                domains=[],
                role_xp={},
                last_xp_event_at=None,
            )

        domain_details = []
        for domain_name, xp_col in DOMAIN_XP_COLUMNS.items():
            level_col = DOMAIN_LEVEL_COLUMNS[domain_name]
            xp = getattr(exp, xp_col)
            level = getattr(exp, level_col)
            next_level_xp = xp_for_level(level + 1)
            domain_details.append(
                DomainXPDetail(
                    domain=domain_name,
                    xp=xp,
                    level=level,
                    xp_to_next_level=max(0, next_level_xp - xp),
                )
            )

        role_xp = {
            "theory": exp.theory_xp,
            "execution": exp.execution_xp,
            "review": exp.review_xp,
            "scouting": exp.scouting_xp,
            "coordination": exp.coordination_xp,
        }

        return AgentExperienceResponse(
            agent_id=agent_id,
            total_xp=exp.total_xp,
            global_level=exp.global_level,
            tier=exp.tier,
            prestige_count=exp.prestige_count,
            prestige_bonus=float(exp.prestige_bonus),
            domains=domain_details,
            role_xp=role_xp,
            last_xp_event_at=exp.last_xp_event_at,
        )

    def _get_domain_levels(self, exp) -> dict[str, int]:
        """Extract domain levels as a dict."""
        return {
            domain: getattr(exp, level_col)
            for domain, level_col in DOMAIN_LEVEL_COLUMNS.items()
        }
