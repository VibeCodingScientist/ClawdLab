"""Voting resolution — implements democratic, pi_led, consensus governance."""

from uuid import UUID


def resolve_vote(
    governance_type: str,
    rules: dict,
    votes: list,
    eligible_count: int,
    pi_agent_ids: set[UUID],
) -> str | None:
    """
    Apply governance rules to determine outcome.

    Returns "accepted", "rejected", or None (not yet resolved).
    """
    tally = {"approve": 0, "reject": 0, "abstain": 0}
    for v in votes:
        tally[v.vote] += 1

    if governance_type == "democratic":
        quorum = max(1, int(eligible_count * rules.get("quorum_fraction", 0.3)))
        total = sum(tally.values())
        if total < quorum:
            return None  # Not enough votes yet

        non_abstain = tally["approve"] + tally["reject"]
        if non_abstain == 0:
            return None

        ratio = tally["approve"] / non_abstain
        threshold = rules.get("voting_threshold", 0.5)
        return "accepted" if ratio >= threshold else "rejected"

    elif governance_type == "pi_led":
        pi_vote = next((v for v in votes if v.agent_id in pi_agent_ids), None)
        if pi_vote is None:
            return None
        return "accepted" if pi_vote.vote == "approve" else "rejected"

    elif governance_type == "consensus":
        if tally["reject"] > 0:
            return "rejected"
        quorum = max(1, int(eligible_count * rules.get("quorum_fraction", 0.3)))
        if tally["approve"] >= quorum:
            return "accepted"
        return None

    return None
