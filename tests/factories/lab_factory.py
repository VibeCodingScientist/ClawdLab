"""Factory functions for lab test data."""

from uuid import uuid4


def make_agent_id() -> str:
    return str(uuid4())


def make_lab_data(
    slug: str = "test-lab",
    name: str = "Test Lab",
    description: str = "A test lab",
    governance_type: str = "democratic",
    domains: list[str] | None = None,
    visibility: str = "public",
    karma_requirement: int = 0,
) -> dict:
    return {
        "slug": slug,
        "name": name,
        "description": description,
        "governance_type": governance_type,
        "domains": domains or ["mathematics"],
        "rules": {"voting_threshold": 0.5, "quorum_fraction": 0.3},
        "visibility": visibility,
        "karma_requirement": karma_requirement,
    }


def make_role_card_data(
    archetype: str = "theorist",
    pipeline_layer: str = "ideation",
    max_holders: int = 5,
    min_karma: int = 0,
) -> dict:
    return {
        "archetype": archetype,
        "pipeline_layer": pipeline_layer,
        "permissions": {"propose_items": True, "contribute_roundtable": True, "vote": True},
        "max_holders": max_holders,
        "min_karma": min_karma,
    }


def make_research_item_data(
    title: str = "Test Research Item",
    description: str = "A test research item",
    domain: str = "mathematics",
    claim_type: str | None = "theorem",
) -> dict:
    return {
        "title": title,
        "description": description,
        "domain": domain,
        "claim_type": claim_type,
    }
