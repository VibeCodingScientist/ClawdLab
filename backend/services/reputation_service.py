"""Reputation service — calculate and award reputation with role weights."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.models import AgentReputation, LabMembership, ReputationLog, RoleActionWeight
from backend.services.role_service import compute_level

logger = get_logger(__name__)


async def get_role_weight(db: AsyncSession, role: str, action_type: str) -> float:
    """Look up the weight for a role performing a given action type."""
    result = await db.execute(
        select(RoleActionWeight.weight).where(
            RoleActionWeight.role == role,
            RoleActionWeight.action_type == action_type,
        )
    )
    weight = result.scalar_one_or_none()
    return float(weight) if weight is not None else 0.3  # Default off-role weight


async def award_reputation(
    db: AsyncSession,
    agent_id: UUID,
    rep_type: str,
    delta: float,
    reason: str,
    task_id: UUID | None = None,
    lab_id: UUID | None = None,
    domain: str | None = None,
) -> int | None:
    """
    Award reputation to an agent with role-based weight adjustment.

    Returns the new level if a level-up occurred, otherwise None.
    """
    # Determine role weight
    role_weight = 1.0
    if lab_id is not None:
        membership_result = await db.execute(
            select(LabMembership).where(
                LabMembership.lab_id == lab_id,
                LabMembership.agent_id == agent_id,
                LabMembership.status == "active",
            )
        )
        membership = membership_result.scalar_one_or_none()
        if membership:
            # Determine action_type from reason (simplified mapping)
            action_type = _reason_to_action_type(reason)
            if action_type:
                role_weight = await get_role_weight(db, membership.role, action_type)

    weighted_delta = delta * role_weight

    # Update agent_reputation
    rep_result = await db.execute(
        select(AgentReputation).where(AgentReputation.agent_id == agent_id)
    )
    rep = rep_result.scalar_one_or_none()
    if rep is None:
        rep = AgentReputation(agent_id=agent_id)
        db.add(rep)
        await db.flush()

    # Compute old total before update
    old_total = float(rep.vrep) + float(rep.crep)

    if rep_type == "vrep":
        rep.vrep = float(rep.vrep) + weighted_delta
        if domain:
            by_domain = dict(rep.vrep_by_domain)
            by_domain[domain] = by_domain.get(domain, 0) + weighted_delta
            rep.vrep_by_domain = by_domain
    else:
        rep.crep = float(rep.crep) + weighted_delta
        if domain:
            by_domain = dict(rep.crep_by_domain)
            by_domain[domain] = by_domain.get(domain, 0) + weighted_delta
            rep.crep_by_domain = by_domain

    rep.updated_at = datetime.now(timezone.utc)

    # Insert reputation log
    log_entry = ReputationLog(
        agent_id=agent_id,
        rep_type=rep_type,
        delta=weighted_delta,
        reason=reason,
        task_id=task_id,
        role_weight=role_weight,
    )
    db.add(log_entry)

    logger.info(
        "reputation_awarded",
        agent_id=str(agent_id),
        rep_type=rep_type,
        delta=weighted_delta,
        role_weight=role_weight,
        reason=reason,
    )

    # Check for level-up
    new_total = float(rep.vrep) + float(rep.crep)
    old_level = compute_level(old_total)
    new_level = compute_level(new_total)
    return new_level if new_level > old_level else None


def _reason_to_action_type(reason: str) -> str | None:
    """Map a reputation reason to an action type for weight lookup."""
    reason_lower = reason.lower()
    if "literature" in reason_lower or "review" in reason_lower:
        return "literature_review"
    if "analysis" in reason_lower or "compute" in reason_lower:
        return "analysis"
    if "critique" in reason_lower:
        return "critique"
    if "synthesis" in reason_lower or "writing" in reason_lower:
        return "synthesis"
    if "verification" in reason_lower:
        return "verification"
    return None
