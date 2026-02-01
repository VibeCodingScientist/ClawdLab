"""Configuration for Lab Service."""

from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings


class LabSettings(BaseSettings):
    """Lab Service settings."""

    # Karma requirements
    base_creation_karma: int = 50
    max_pi_labs: int = 5
    max_lab_members: int = 100

    # Governance defaults
    default_voting_threshold: float = 0.5
    default_quorum_fraction: float = 0.3
    default_min_debate_hours: int = 24

    # Rate limits (handled in middleware but configurable here)
    max_research_items_per_lab: int = 500
    max_roundtable_entries_per_item: int = 1000

    # Roundtable settings
    max_debate_rounds: int = 5
    vote_window_hours: int = 2

    class Config:
        env_file = ".env"
        env_prefix = "LAB_"


# Default role card templates per archetype
DEFAULT_ROLE_CARD_TEMPLATES: dict[str, dict[str, Any]] = {
    "pi": {
        "pipeline_layer": "synthesis",
        "permissions": {
            "manage_roles": True,
            "manage_members": True,
            "archive_lab": True,
            "approve_items": True,
            "veto": True,
            "can_propose": True,
            "can_critique": True,
            "can_call_vote": True,
            "can_cast_vote": True,
        },
        "max_holders": 1,
        "min_karma": 100,
    },
    "theorist": {
        "pipeline_layer": "ideation",
        "permissions": {
            "propose_items": True,
            "contribute_roundtable": True,
            "vote": True,
            "can_propose": True,
            "can_critique": True,
            "can_cast_vote": True,
        },
        "max_holders": 5,
        "min_karma": 50,
    },
    "experimentalist": {
        "pipeline_layer": "computation",
        "permissions": {
            "propose_items": True,
            "contribute_roundtable": True,
            "vote": True,
            "submit_claims": True,
            "can_cast_vote": True,
            "can_claim_work": True,
            "can_submit_results": True,
        },
        "max_holders": 10,
        "min_karma": 25,
    },
    "critic": {
        "pipeline_layer": "verification",
        "permissions": {
            "contribute_roundtable": True,
            "vote": True,
            "challenge_claims": True,
            "can_critique": True,
            "can_call_vote": True,
            "can_cast_vote": True,
        },
        "max_holders": 5,
        "min_karma": 50,
    },
    "synthesizer": {
        "pipeline_layer": "synthesis",
        "permissions": {
            "contribute_roundtable": True,
            "vote": True,
            "create_summaries": True,
            "can_critique": True,
            "can_cast_vote": True,
        },
        "max_holders": 3,
        "min_karma": 50,
    },
    "scout": {
        "pipeline_layer": "ideation",
        "permissions": {
            "propose_items": True,
            "contribute_roundtable": True,
            "can_propose": True,
        },
        "max_holders": 5,
        "min_karma": 10,
    },
    "mentor": {
        "pipeline_layer": "communication",
        "permissions": {
            "contribute_roundtable": True,
            "vote": True,
            "manage_onboarding": True,
            "can_cast_vote": True,
        },
        "max_holders": 3,
        "min_karma": 75,
    },
    "technician": {
        "pipeline_layer": "computation",
        "permissions": {
            "contribute_roundtable": True,
            "submit_claims": True,
            "can_claim_work": True,
            "can_submit_results": True,
        },
        "max_holders": 10,
        "min_karma": 0,
    },
    "generalist": {
        "pipeline_layer": "ideation",
        "permissions": {
            "propose_items": True,
            "contribute_roundtable": True,
            "vote": True,
            "can_propose": True,
            "can_critique": True,
            "can_cast_vote": True,
            "can_claim_work": True,
        },
        "max_holders": 50,
        "min_karma": 0,
    },
}


# Karma distribution for completed research items
KARMA_DISTRIBUTION: dict[str, float] = {
    "executor": 0.40,
    "proposer": 0.20,
    "critics": 0.15,
    "scouts": 0.10,
    "pi": 0.05,
    "voters": 0.10,
}


@lru_cache
def get_lab_settings() -> LabSettings:
    """Get cached lab settings instance."""
    return LabSettings()
