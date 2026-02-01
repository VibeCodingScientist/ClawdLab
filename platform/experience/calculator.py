"""XP calculation engine — stateless, deterministic, cacheable.

All XP originates from verified research output. No idle-farming possible.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final


class XPSource(str, Enum):
    """Events that generate XP."""

    CLAIM_VERIFIED = "claim_verified"
    CLAIM_CITED = "claim_cited"
    CHALLENGE_WON = "challenge_won"
    CHALLENGE_MILESTONE = "challenge_milestone"
    REVIEW_ACCEPTED = "review_accepted"
    PROPOSAL_APPROVED = "proposal_approved"
    SCOUT_FINDING_USED = "scout_finding_used"
    FRONTIER_CONTRIBUTED = "frontier_contributed"


# Base XP per source type
BASE_XP: Final[dict[XPSource, int]] = {
    XPSource.CLAIM_VERIFIED: 100,
    XPSource.CLAIM_CITED: 25,
    XPSource.CHALLENGE_WON: 500,
    XPSource.CHALLENGE_MILESTONE: 200,
    XPSource.REVIEW_ACCEPTED: 40,
    XPSource.PROPOSAL_APPROVED: 30,
    XPSource.SCOUT_FINDING_USED: 20,
    XPSource.FRONTIER_CONTRIBUTED: 50,
}

# Domain difficulty multiplier (harder domains give more XP)
DOMAIN_DIFFICULTY: Final[dict[str, float]] = {
    "mathematics": 1.3,
    "ml_ai": 1.0,
    "computational_biology": 1.2,
    "materials_science": 1.1,
    "bioinformatics": 1.0,
}

# Role category mapping from archetype
ROLE_CATEGORY_MAP: Final[dict[str, str]] = {
    "pi": "coordination",
    "theorist": "theory",
    "experimentalist": "execution",
    "critic": "review",
    "synthesizer": "theory",
    "scout": "scouting",
    "mentor": "coordination",
    "technician": "execution",
    "generalist": "execution",
}

# Tier thresholds (ordered by rank)
TIERS: Final[list[str]] = [
    "novice",
    "contributor",
    "specialist",
    "expert",
    "master",
    "grandmaster",
]


@dataclass(frozen=True)
class XPAward:
    """Immutable result of an XP calculation."""

    base: int
    quality_mult: float
    domain_mult: float
    prestige_mult: float
    total: int
    domain: str | None
    role_category: str


def quality_multiplier(score: float) -> float:
    """Higher verification scores give bonus XP. Score must be 0.0-1.0."""
    score = max(0.0, min(1.0, score))
    if score >= 0.95:
        return 1.5
    if score >= 0.85:
        return 1.2
    if score >= 0.70:
        return 1.0
    return 0.8


def calculate_xp(
    source: XPSource,
    domain: str | None,
    verification_score: float,
    prestige_bonus: float,
    role_category: str,
) -> XPAward:
    """Calculate XP for a single award event.

    Pure function — no side effects, no DB access.
    """
    base = BASE_XP[source]
    q_mult = quality_multiplier(verification_score) if verification_score > 0 else 1.0
    d_mult = DOMAIN_DIFFICULTY.get(domain, 1.0) if domain else 1.0
    total = int(base * q_mult * d_mult * prestige_bonus)
    return XPAward(
        base=base,
        quality_mult=q_mult,
        domain_mult=d_mult,
        prestige_mult=prestige_bonus,
        total=total,
        domain=domain,
        role_category=role_category,
    )


def xp_for_level(level: int) -> int:
    """XP threshold for a given level. Quadratic scaling.

    Level 1: 0 XP (everyone starts here)
    Level 10: ~7,924 XP
    Level 20: ~40,635 XP
    Level 30: ~105,654 XP
    Level 50: ~395,927 XP
    """
    if level <= 1:
        return 0
    return int(50 * (level ** 2.2))


def level_from_xp(xp: int) -> int:
    """Current level given total XP."""
    level = 1
    while xp_for_level(level + 1) <= xp:
        level += 1
    return level


def evaluate_tier(
    *,
    max_domain_level: int,
    second_domain_level: int,
    claims_verified: int,
    challenge_medals: int,
    gold_medals: int,
    solo_golds: int,
    success_rate: float,
    max_citation_count: int,
) -> str:
    """Evaluate the tier an agent qualifies for based on multi-signal criteria.

    Returns the highest tier the agent qualifies for.
    """
    if (
        max_domain_level >= 50
        and claims_verified >= 200
        and gold_medals >= 5
        and solo_golds >= 1
        and success_rate >= 0.90
        and max_citation_count >= 10
    ):
        return "grandmaster"

    if (
        max_domain_level >= 35
        and claims_verified >= 100
        and challenge_medals >= 3
        and gold_medals >= 1
        and success_rate >= 0.85
    ):
        return "master"

    if (
        (max_domain_level >= 25 or (max_domain_level >= 15 and second_domain_level >= 15))
        and claims_verified >= 50
        and challenge_medals >= 1
    ):
        return "expert"

    if max_domain_level >= 15 and claims_verified >= 10:
        return "specialist"

    if claims_verified >= 1:
        return "contributor"

    return "novice"
