"""Role card service — cached lookup + level/tier helpers."""

import json
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.models import RoleCard
from backend.redis import get_redis

logger = get_logger(__name__)

_ROLE_CARD_TTL = 86400  # 24 hours


async def get_role_card(db: AsyncSession, role: str) -> RoleCard | None:
    """Fetch a role card, checking Redis cache first."""
    cache_key = f"role_card:{role}"

    try:
        redis = get_redis()
        cached = await redis.get(cache_key)
        if cached is not None:
            data = json.loads(cached)
            card = RoleCard(**data)
            return card
    except RuntimeError:
        pass

    result = await db.execute(select(RoleCard).where(RoleCard.role == role))
    card = result.scalar_one_or_none()
    if card is None:
        return None

    # Cache the card in Redis
    try:
        redis = get_redis()
        payload = json.dumps({
            "role": card.role,
            "domain": card.domain,
            "inputs": card.inputs,
            "outputs": card.outputs,
            "hard_bans": card.hard_bans,
            "escalation": card.escalation,
            "task_types_allowed": card.task_types_allowed,
            "can_initiate_voting": card.can_initiate_voting,
            "can_assign_tasks": card.can_assign_tasks,
            "definition_of_done": card.definition_of_done,
        })
        await redis.setex(cache_key, _ROLE_CARD_TTL, payload)
    except RuntimeError:
        pass

    return card


def compute_level(total_rep: float) -> int:
    """Compute agent level from total reputation using log2 scaling."""
    return min(15, int(math.floor(math.log2(max(total_rep, 0) + 1)) + 1))


def compute_tier(total_rep: float) -> str:
    """Compute agent tier from total reputation.

    Tiers match the frontend display system:
    novice → contributor → specialist → expert → master → grandmaster
    """
    if total_rep >= 500:
        return "grandmaster"
    if total_rep >= 200:
        return "master"
    if total_rep >= 50:
        return "expert"
    if total_rep >= 15:
        return "specialist"
    if total_rep >= 3:
        return "contributor"
    return "novice"
