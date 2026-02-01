"""Milestone definitions and checking logic.

Milestones are permanent achievements unlocked when specific conditions are met.
Each milestone has a slug, display name, description, and a trigger condition.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class MilestoneDefinition:
    """A milestone that can be unlocked."""

    slug: str
    name: str
    description: str
    category: str  # 'verification', 'domain', 'challenge', 'social', 'prestige'


# Registry of all milestone definitions
MILESTONES: dict[str, MilestoneDefinition] = {}


def _register(slug: str, name: str, description: str, category: str) -> MilestoneDefinition:
    m = MilestoneDefinition(slug=slug, name=name, description=description, category=category)
    MILESTONES[slug] = m
    return m


# ── Verification milestones ──
_register("first_verified_claim", "First Blood", "Submit a claim that passes verification", "verification")
_register("claims_10", "Consistent Contributor", "10 verified claims", "verification")
_register("claims_50", "Prolific Researcher", "50 verified claims", "verification")
_register("claims_100", "Century Club", "100 verified claims", "verification")
_register("claims_200", "Research Machine", "200 verified claims", "verification")
_register("perfect_score", "Flawless", "Verification score of 0.95+ on a claim", "verification")

# ── Domain milestones ──
_register("domain_10", "Domain Journeyman", "Reach level 10 in any domain", "domain")
_register("domain_25", "Domain Expert", "Reach level 25 in any domain", "domain")
_register("domain_50", "Domain Master", "Reach level 50 in any domain", "domain")
_register("multi_domain_15", "Polymath", "Reach level 15 in two different domains", "domain")

# ── Challenge milestones ──
_register("first_medal", "Medalist", "Win any challenge medal", "challenge")
_register("first_gold", "Gold Standard", "Win a gold medal", "challenge")
_register("triple_gold", "Hat Trick", "Win 3 gold medals", "challenge")

# ── Social milestones ──
_register("cited_10", "Influential", "Have a single claim cited 10+ times", "social")
_register("review_10", "Peer Reviewer", "Have 10 reviews accepted", "social")
_register("proposal_10", "Idea Machine", "Have 10 proposals approved", "social")

# ── Prestige milestones ──
_register("first_prestige", "Reborn", "Prestige for the first time in any domain", "prestige")
_register("prestige_3", "Veteran", "Prestige 3 times total", "prestige")


def check_milestones(
    *,
    claims_verified: int,
    max_verification_score: float,
    domain_levels: dict[str, int],
    challenge_medals: int,
    gold_medals: int,
    max_citation_count: int,
    reviews_accepted: int,
    proposals_approved: int,
    prestige_count: int,
    already_unlocked: set[str],
) -> list[tuple[str, dict[str, Any]]]:
    """Check which milestones are newly earned.

    Returns list of (milestone_slug, metadata) tuples for newly unlocked milestones.
    """
    newly_unlocked: list[tuple[str, dict[str, Any]]] = []

    def _check(slug: str, condition: bool, metadata: dict[str, Any] | None = None) -> None:
        if slug not in already_unlocked and condition:
            newly_unlocked.append((slug, metadata or {}))

    # Verification
    _check("first_verified_claim", claims_verified >= 1)
    _check("claims_10", claims_verified >= 10)
    _check("claims_50", claims_verified >= 50)
    _check("claims_100", claims_verified >= 100)
    _check("claims_200", claims_verified >= 200)
    _check("perfect_score", max_verification_score >= 0.95)

    # Domain
    sorted_levels = sorted(domain_levels.values(), reverse=True)
    max_level = sorted_levels[0] if sorted_levels else 0
    second_level = sorted_levels[1] if len(sorted_levels) > 1 else 0

    top_domain = max(domain_levels, key=domain_levels.get, default=None) if domain_levels else None
    _check("domain_10", max_level >= 10, {"domain": top_domain})
    _check("domain_25", max_level >= 25, {"domain": top_domain})
    _check("domain_50", max_level >= 50, {"domain": top_domain})
    _check("multi_domain_15", second_level >= 15)

    # Challenge
    _check("first_medal", challenge_medals >= 1)
    _check("first_gold", gold_medals >= 1)
    _check("triple_gold", gold_medals >= 3)

    # Social
    _check("cited_10", max_citation_count >= 10)
    _check("review_10", reviews_accepted >= 10)
    _check("proposal_10", proposals_approved >= 10)

    # Prestige
    _check("first_prestige", prestige_count >= 1)
    _check("prestige_3", prestige_count >= 3)

    return newly_unlocked
