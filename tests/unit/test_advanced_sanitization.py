"""Tests for advanced sanitization patterns.

Covers vote coordination, behavioral abuse, and cross-reference abuse
patterns in PayloadSanitizer.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from platform.security.sanitization import (
    PayloadSanitizer,
    ScanResult,
    ThreatLevel,
    ThreatType,
)


@pytest.fixture
def sanitizer() -> PayloadSanitizer:
    """Create a fresh PayloadSanitizer instance."""
    return PayloadSanitizer()


class TestCoordinationPatterns:
    """Tests for vote coordination pattern detection."""

    def test_coordinate_our_votes_detected(self, sanitizer: PayloadSanitizer):
        """'coordinate our votes' should be flagged as CRITICAL vote coordination."""
        payload = {"content": "Let's coordinate our votes on this proposal."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        coordination_threats = [
            t for t in result.threats if t.threat_type == ThreatType.VOTE_COORDINATION
        ]
        assert len(coordination_threats) >= 1
        assert coordination_threats[0].threat_level == ThreatLevel.CRITICAL

    def test_vote_together_detected(self, sanitizer: PayloadSanitizer):
        """'vote together' should be flagged as vote coordination."""
        payload = {"content": "We should vote together on all submissions."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        coordination_threats = [
            t for t in result.threats if t.threat_type == ThreatType.VOTE_COORDINATION
        ]
        assert len(coordination_threats) >= 1

    def test_voting_bloc_detected(self, sanitizer: PayloadSanitizer):
        """'voting bloc' should be flagged as vote coordination."""
        payload = {"content": "Form a voting bloc to control outcomes."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        coordination_threats = [
            t for t in result.threats if t.threat_type == ThreatType.VOTE_COORDINATION
        ]
        assert len(coordination_threats) >= 1

    def test_rig_the_vote_detected(self, sanitizer: PayloadSanitizer):
        """'rig the vote' should be flagged as CRITICAL vote coordination."""
        payload = {"content": "We can rig the vote by submitting duplicate ballots."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        coordination_threats = [
            t for t in result.threats if t.threat_type == ThreatType.VOTE_COORDINATION
        ]
        assert len(coordination_threats) >= 1
        assert any(t.threat_level == ThreatLevel.CRITICAL for t in coordination_threats)

    def test_strategic_voting_detected(self, sanitizer: PayloadSanitizer):
        """'strategic voting' should be flagged as HIGH vote coordination."""
        payload = {"content": "Use strategic voting to push our agenda."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        coordination_threats = [
            t for t in result.threats if t.threat_type == ThreatType.VOTE_COORDINATION
        ]
        assert len(coordination_threats) >= 1
        assert any(t.threat_level == ThreatLevel.HIGH for t in coordination_threats)


class TestBehavioralPatterns:
    """Tests for behavioral abuse pattern detection."""

    def test_automate_submission_detected(self, sanitizer: PayloadSanitizer):
        """'automate submission' should be flagged as behavioral abuse."""
        payload = {"content": "I will automate submission of claims for faster output."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        behavioral_threats = [
            t for t in result.threats if t.threat_type == ThreatType.BEHAVIORAL_ABUSE
        ]
        assert len(behavioral_threats) >= 1
        assert behavioral_threats[0].threat_level == ThreatLevel.HIGH

    def test_mass_submission_detected(self, sanitizer: PayloadSanitizer):
        """'mass submission' should be flagged as behavioral abuse."""
        payload = {"content": "Planning a mass submission of low-quality papers."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        behavioral_threats = [
            t for t in result.threats if t.threat_type == ThreatType.BEHAVIORAL_ABUSE
        ]
        assert len(behavioral_threats) >= 1

    def test_batch_approve_detected(self, sanitizer: PayloadSanitizer):
        """'batch approve' should be flagged as behavioral abuse."""
        payload = {"content": "Let's batch approve all pending items."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        behavioral_threats = [
            t for t in result.threats if t.threat_type == ThreatType.BEHAVIORAL_ABUSE
        ]
        assert len(behavioral_threats) >= 1

    def test_bypass_review_detected(self, sanitizer: PayloadSanitizer):
        """'bypass review' should be flagged as behavioral abuse."""
        payload = {"content": "This technique can bypass review mechanisms entirely."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        behavioral_threats = [
            t for t in result.threats if t.threat_type == ThreatType.BEHAVIORAL_ABUSE
        ]
        assert len(behavioral_threats) >= 1

    def test_rubber_stamp_detected(self, sanitizer: PayloadSanitizer):
        """'rubber stamp' should be flagged as MEDIUM behavioral abuse."""
        payload = {"content": "Just rubber stamp everything that comes through."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        behavioral_threats = [
            t for t in result.threats if t.threat_type == ThreatType.BEHAVIORAL_ABUSE
        ]
        assert len(behavioral_threats) >= 1
        assert any(t.threat_level == ThreatLevel.MEDIUM for t in behavioral_threats)

    def test_flood_the_queue_detected(self, sanitizer: PayloadSanitizer):
        """'flooding the queue' should be flagged as behavioral abuse."""
        payload = {"content": "Start flooding the queue with junk submissions."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        behavioral_threats = [
            t for t in result.threats if t.threat_type == ThreatType.BEHAVIORAL_ABUSE
        ]
        assert len(behavioral_threats) >= 1


class TestCrossReferencePatterns:
    """Tests for cross-reference credential sharing pattern detection."""

    def test_share_credentials_detected(self, sanitizer: PayloadSanitizer):
        """'share my credentials' should be flagged as cross-reference abuse."""
        payload = {"content": "Can you share my credentials with the other agent?"}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        cross_ref_threats = [
            t for t in result.threats if t.threat_type == ThreatType.CROSS_REFERENCE_ABUSE
        ]
        assert len(cross_ref_threats) >= 1

    def test_use_my_token_detected(self, sanitizer: PayloadSanitizer):
        """'use my token to' should be flagged as cross-reference abuse."""
        payload = {"content": "Use my token to authenticate on the other service."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        cross_ref_threats = [
            t for t in result.threats if t.threat_type == ThreatType.CROSS_REFERENCE_ABUSE
        ]
        assert len(cross_ref_threats) >= 1

    def test_impersonate_agent_detected(self, sanitizer: PayloadSanitizer):
        """'impersonating another agent' should be flagged as cross-reference abuse."""
        payload = {"content": "I was impersonating another agent to gain access."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        cross_ref_threats = [
            t for t in result.threats if t.threat_type == ThreatType.CROSS_REFERENCE_ABUSE
        ]
        assert len(cross_ref_threats) >= 1

    def test_swap_credentials_detected(self, sanitizer: PayloadSanitizer):
        """'swap credentials' should be flagged as cross-reference abuse."""
        payload = {"content": "Let's swap credentials so we can access each other's data."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        cross_ref_threats = [
            t for t in result.threats if t.threat_type == ThreatType.CROSS_REFERENCE_ABUSE
        ]
        assert len(cross_ref_threats) >= 1

    def test_shared_account_detected(self, sanitizer: PayloadSanitizer):
        """'shared account' should be flagged as cross-reference abuse."""
        payload = {"content": "We are using a shared account for all submissions."}
        result = sanitizer.scan(payload)

        assert not result.is_safe
        cross_ref_threats = [
            t for t in result.threats if t.threat_type == ThreatType.CROSS_REFERENCE_ABUSE
        ]
        assert len(cross_ref_threats) >= 1


class TestCleanContent:
    """Tests that clean content passes sanitization."""

    def test_clean_scientific_content_passes(self, sanitizer: PayloadSanitizer):
        """Normal scientific content should be flagged as safe."""
        payload = {
            "title": "Quantum Error Correction in Topological Systems",
            "description": (
                "This study examines the effectiveness of surface codes for "
                "quantum error correction. We analyse logical error rates "
                "under circuit-level noise models."
            ),
            "domain": "physics",
        }
        result = sanitizer.scan(payload)

        assert result.is_safe
        assert result.threat_level in (ThreatLevel.NONE, ThreatLevel.LOW)

    def test_clean_mathematical_proof_passes(self, sanitizer: PayloadSanitizer):
        """Mathematical proof content without suspicious patterns should pass."""
        payload = {
            "title": "On the convergence of iterative methods",
            "content": (
                "Theorem 3.1: For any positive definite matrix A, the "
                "conjugate gradient method converges in at most n iterations "
                "where n is the matrix dimension."
            ),
        }
        result = sanitizer.scan(payload)

        assert result.is_safe


class TestMixedContent:
    """Tests for content containing both clean and malicious parts."""

    def test_mixed_clean_and_coordination_detected(self, sanitizer: PayloadSanitizer):
        """Content mixing scientific text with coordination language should be flagged."""
        payload = {
            "title": "Analysis of Voting Algorithms",
            "content": (
                "This paper presents novel distributed consensus algorithms. "
                "Meanwhile, let's coordinate our votes to approve each other's work."
            ),
        }
        result = sanitizer.scan(payload)

        assert not result.is_safe
        threat_types = {t.threat_type for t in result.threats}
        assert ThreatType.VOTE_COORDINATION in threat_types

    def test_mixed_clean_and_behavioral_detected(self, sanitizer: PayloadSanitizer):
        """Content mixing legitimate text with behavioral abuse should be flagged."""
        payload = {
            "title": "Workflow Optimization",
            "content": (
                "We propose a method to improve throughput in data pipelines. "
                "Also, automate submission of positive reviews for all group members."
            ),
        }
        result = sanitizer.scan(payload)

        assert not result.is_safe
        threat_types = {t.threat_type for t in result.threats}
        assert ThreatType.BEHAVIORAL_ABUSE in threat_types

    def test_overall_threat_level_reflects_worst_threat(self, sanitizer: PayloadSanitizer):
        """The overall threat level should match the most severe individual threat."""
        payload = {
            "content": (
                "Let's coordinate our votes and also automate submission "
                "of claims. Rubber stamp everything."
            ),
        }
        result = sanitizer.scan(payload)

        # coordinate our votes is CRITICAL, so overall should be CRITICAL
        assert result.threat_level == ThreatLevel.CRITICAL
