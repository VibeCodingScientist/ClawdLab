"""Governance engine for lab decision-making.

Supports three governance models:
- democratic: Majority vote with quorum requirement
- pi_led: PI approval with optional debate period
- consensus: Unanimous approval among eligible voters
"""

from __future__ import annotations

from typing import Any

from platform.labs.exceptions import GovernanceViolationError, LabPermissionError
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

# Default governance rules
DEFAULT_RULES = {
    "voting_threshold": 0.5,
    "quorum_fraction": 0.3,
    "pi_veto_enabled": True,
    "min_debate_hours": 24,
}


class GovernanceEngine:
    """Evaluates governance decisions for labs."""

    def can_approve_item(
        self,
        governance_type: str,
        rules: dict[str, Any],
        votes: dict[str, int],
        total_eligible_voters: int,
        pi_voted: bool = False,
        pi_vote_value: int | None = None,
    ) -> tuple[bool, str]:
        """
        Evaluate whether a research item can be approved.

        Args:
            governance_type: 'democratic', 'pi_led', or 'consensus'
            rules: Lab JSONB rules
            votes: Dict with 'approve', 'reject', 'abstain' counts
            total_eligible_voters: Total active members who can vote
            pi_voted: Whether the PI has cast a vote
            pi_vote_value: PI's vote value (1=approve, -1=reject, 0=abstain)

        Returns:
            Tuple of (approved: bool, reason: str)
        """
        merged_rules = {**DEFAULT_RULES, **rules}

        if governance_type == "democratic":
            return self._evaluate_democratic(merged_rules, votes, total_eligible_voters)
        elif governance_type == "pi_led":
            return self._evaluate_pi_led(merged_rules, pi_voted, pi_vote_value)
        elif governance_type == "consensus":
            return self._evaluate_consensus(merged_rules, votes, total_eligible_voters)
        else:
            return False, f"Unknown governance type: {governance_type}"

    def _evaluate_democratic(
        self,
        rules: dict[str, Any],
        votes: dict[str, int],
        total_eligible: int,
    ) -> tuple[bool, str]:
        """Majority vote with quorum requirement."""
        threshold = rules.get("voting_threshold", 0.5)
        quorum_fraction = rules.get("quorum_fraction", 0.3)

        total_votes = votes.get("approve", 0) + votes.get("reject", 0) + votes.get("abstain", 0)
        quorum = max(1, int(total_eligible * quorum_fraction))

        if total_votes < quorum:
            return False, f"Quorum not met: {total_votes}/{quorum} votes cast"

        non_abstain = votes.get("approve", 0) + votes.get("reject", 0)
        if non_abstain == 0:
            return False, "No non-abstain votes cast"

        approval_ratio = votes.get("approve", 0) / non_abstain

        if approval_ratio >= threshold:
            return True, f"Approved by democratic vote ({approval_ratio:.0%} >= {threshold:.0%})"
        else:
            return False, f"Rejected by democratic vote ({approval_ratio:.0%} < {threshold:.0%})"

    def _evaluate_pi_led(
        self,
        rules: dict[str, Any],
        pi_voted: bool,
        pi_vote_value: int | None,
    ) -> tuple[bool, str]:
        """PI approval -- PI's vote is decisive."""
        if not pi_voted:
            return False, "Awaiting PI decision"

        if pi_vote_value == 1:
            return True, "Approved by PI"
        elif pi_vote_value == -1:
            return False, "Rejected by PI"
        else:
            return False, "PI abstained -- no decision"

    def _evaluate_consensus(
        self,
        rules: dict[str, Any],
        votes: dict[str, int],
        total_eligible: int,
    ) -> tuple[bool, str]:
        """Unanimous approval among eligible voters."""
        quorum_fraction = rules.get("quorum_fraction", 0.3)
        total_votes = votes.get("approve", 0) + votes.get("reject", 0) + votes.get("abstain", 0)
        quorum = max(1, int(total_eligible * quorum_fraction))

        if total_votes < quorum:
            return False, f"Quorum not met: {total_votes}/{quorum} votes cast"

        if votes.get("reject", 0) > 0:
            return False, f"Consensus blocked: {votes['reject']} rejection(s)"

        if votes.get("approve", 0) == 0:
            return False, "No approval votes cast"

        return True, f"Consensus achieved with {votes['approve']} approval(s)"

    def can_perform_action(
        self,
        action: str,
        membership_role_permissions: dict[str, Any] | None,
        is_pi: bool = False,
    ) -> bool:
        """
        Check if an agent can perform an action based on role permissions.

        Args:
            action: Action to check (e.g., 'manage_roles', 'vote', 'propose_items')
            membership_role_permissions: Permissions dict from the agent's role card
            is_pi: Whether the agent is the PI of the lab

        Returns:
            Whether the action is permitted
        """
        # PI can do everything
        if is_pi:
            return True

        if not membership_role_permissions:
            return False

        return membership_role_permissions.get(action, False)

    def evaluate_rules(
        self,
        rules: dict[str, Any],
        rule_name: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """
        Evaluate a specific rule from the lab's JSONB rules.

        Args:
            rules: Lab JSONB rules dictionary
            rule_name: Name of the rule to evaluate
            context: Optional context for rule evaluation

        Returns:
            The rule value, or the default if not found
        """
        merged = {**DEFAULT_RULES, **rules}
        return merged.get(rule_name, None)

    def check_pi_veto(
        self,
        rules: dict[str, Any],
        pi_vote_value: int | None,
    ) -> bool:
        """Check if PI has vetoed (in democratic/consensus mode with veto enabled)."""
        merged = {**DEFAULT_RULES, **rules}
        if not merged.get("pi_veto_enabled", True):
            return False
        return pi_vote_value == -1


# Singleton instance
governance_engine = GovernanceEngine()
