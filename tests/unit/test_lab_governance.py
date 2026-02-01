"""Tests for Lab Governance Engine."""

import pytest

from platform.labs.governance import GovernanceEngine


class TestDemocraticGovernance:
    """Tests for democratic governance model."""

    def setup_method(self):
        self.engine = GovernanceEngine()

    def test_democratic_approval_majority(self):
        """Should approve when majority votes approve."""
        approved, reason = self.engine.can_approve_item(
            governance_type="democratic",
            rules={"voting_threshold": 0.5, "quorum_fraction": 0.3},
            votes={"approve": 7, "reject": 3, "abstain": 0},
            total_eligible_voters=20,
        )
        assert approved is True
        assert "Approved" in reason

    def test_democratic_rejection_minority(self):
        """Should reject when minority approves."""
        approved, reason = self.engine.can_approve_item(
            governance_type="democratic",
            rules={"voting_threshold": 0.5, "quorum_fraction": 0.3},
            votes={"approve": 3, "reject": 7, "abstain": 0},
            total_eligible_voters=20,
        )
        assert approved is False
        assert "Rejected" in reason

    def test_democratic_quorum_not_met(self):
        """Should reject when quorum is not met."""
        approved, reason = self.engine.can_approve_item(
            governance_type="democratic",
            rules={"voting_threshold": 0.5, "quorum_fraction": 0.5},
            votes={"approve": 2, "reject": 0, "abstain": 0},
            total_eligible_voters=20,
        )
        assert approved is False
        assert "Quorum" in reason

    def test_democratic_custom_threshold(self):
        """Should respect custom voting threshold."""
        approved, _ = self.engine.can_approve_item(
            governance_type="democratic",
            rules={"voting_threshold": 0.75, "quorum_fraction": 0.1},
            votes={"approve": 6, "reject": 4, "abstain": 0},
            total_eligible_voters=20,
        )
        assert approved is False  # 60% < 75%

    def test_democratic_exact_threshold(self):
        """Should approve at exact threshold."""
        approved, _ = self.engine.can_approve_item(
            governance_type="democratic",
            rules={"voting_threshold": 0.5, "quorum_fraction": 0.1},
            votes={"approve": 5, "reject": 5, "abstain": 0},
            total_eligible_voters=20,
        )
        assert approved is True  # 50% >= 50%


class TestPILedGovernance:
    """Tests for PI-led governance model."""

    def setup_method(self):
        self.engine = GovernanceEngine()

    def test_pi_approval(self):
        """Should approve when PI votes yes."""
        approved, reason = self.engine.can_approve_item(
            governance_type="pi_led",
            rules={},
            votes={},
            total_eligible_voters=10,
            pi_voted=True,
            pi_vote_value=1,
        )
        assert approved is True
        assert "PI" in reason

    def test_pi_rejection(self):
        """Should reject when PI votes no."""
        approved, reason = self.engine.can_approve_item(
            governance_type="pi_led",
            rules={},
            votes={},
            total_eligible_voters=10,
            pi_voted=True,
            pi_vote_value=-1,
        )
        assert approved is False

    def test_pi_not_voted(self):
        """Should wait when PI hasn't voted."""
        approved, reason = self.engine.can_approve_item(
            governance_type="pi_led",
            rules={},
            votes={},
            total_eligible_voters=10,
            pi_voted=False,
        )
        assert approved is False
        assert "Awaiting" in reason

    def test_pi_abstain(self):
        """Should not approve when PI abstains."""
        approved, _ = self.engine.can_approve_item(
            governance_type="pi_led",
            rules={},
            votes={},
            total_eligible_voters=10,
            pi_voted=True,
            pi_vote_value=0,
        )
        assert approved is False


class TestConsensusGovernance:
    """Tests for consensus governance model."""

    def setup_method(self):
        self.engine = GovernanceEngine()

    def test_consensus_achieved(self):
        """Should approve when all votes are approvals."""
        approved, reason = self.engine.can_approve_item(
            governance_type="consensus",
            rules={"quorum_fraction": 0.3},
            votes={"approve": 8, "reject": 0, "abstain": 2},
            total_eligible_voters=20,
        )
        assert approved is True
        assert "Consensus" in reason

    def test_consensus_blocked(self):
        """Should reject when any vote is a rejection."""
        approved, reason = self.engine.can_approve_item(
            governance_type="consensus",
            rules={"quorum_fraction": 0.3},
            votes={"approve": 7, "reject": 1, "abstain": 2},
            total_eligible_voters=20,
        )
        assert approved is False
        assert "blocked" in reason

    def test_consensus_quorum_not_met(self):
        """Should reject when quorum is not met."""
        approved, reason = self.engine.can_approve_item(
            governance_type="consensus",
            rules={"quorum_fraction": 0.5},
            votes={"approve": 2, "reject": 0, "abstain": 0},
            total_eligible_voters=20,
        )
        assert approved is False
        assert "Quorum" in reason


class TestPermissions:
    """Tests for permission checks."""

    def setup_method(self):
        self.engine = GovernanceEngine()

    def test_pi_always_permitted(self):
        """PI should always have permission."""
        assert self.engine.can_perform_action("manage_roles", {}, is_pi=True) is True

    def test_permitted_action(self):
        """Should allow actions in role permissions."""
        perms = {"vote": True, "propose_items": True}
        assert self.engine.can_perform_action("vote", perms) is True

    def test_denied_action(self):
        """Should deny actions not in role permissions."""
        perms = {"vote": True}
        assert self.engine.can_perform_action("manage_roles", perms) is False

    def test_no_permissions(self):
        """Should deny when no permissions provided."""
        assert self.engine.can_perform_action("vote", None) is False


class TestPIVeto:
    """Tests for PI veto functionality."""

    def setup_method(self):
        self.engine = GovernanceEngine()

    def test_veto_enabled_and_active(self):
        """PI veto should block when enabled and PI voted -1."""
        assert self.engine.check_pi_veto({"pi_veto_enabled": True}, -1) is True

    def test_veto_enabled_no_veto(self):
        """PI approving should not trigger veto."""
        assert self.engine.check_pi_veto({"pi_veto_enabled": True}, 1) is False

    def test_veto_disabled(self):
        """PI veto should be ignored when disabled."""
        assert self.engine.check_pi_veto({"pi_veto_enabled": False}, -1) is False
