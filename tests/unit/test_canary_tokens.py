"""Tests for CanaryTokenGenerator."""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from platform.security.canary import CanaryTokenGenerator


_CANARY_PATTERN = re.compile(r"^srp_canary_[a-f0-9]{16}$")


class TestGenerateCanary:
    """Tests for CanaryTokenGenerator.generate_canary."""

    def test_generate_canary_is_deterministic_per_agent(self):
        """The same agent_id should always produce the same canary token."""
        with patch("platform.security.canary.logger"):
            gen = CanaryTokenGenerator(secret_key="test-secret")
            canary1 = gen.generate_canary("agent-001")
            canary2 = gen.generate_canary("agent-001")

        assert canary1 == canary2

    def test_different_agents_get_different_canaries(self):
        """Different agent IDs should produce different canary tokens."""
        with patch("platform.security.canary.logger"):
            gen = CanaryTokenGenerator(secret_key="test-secret")
            canary_a = gen.generate_canary("agent-alpha")
            canary_b = gen.generate_canary("agent-beta")

        assert canary_a != canary_b

    def test_canary_format_matches_expected_pattern(self):
        """Canary token should match srp_canary_{16 hex chars}."""
        with patch("platform.security.canary.logger"):
            gen = CanaryTokenGenerator(secret_key="format-test")
            canary = gen.generate_canary("agent-format")

        assert _CANARY_PATTERN.match(canary), f"Canary '{canary}' does not match expected pattern"


class TestVerifyCanary:
    """Tests for CanaryTokenGenerator.verify_canary."""

    def test_verify_canary_returns_true_for_correct_agent(self):
        """verify_canary should return True when the canary belongs to the agent."""
        with patch("platform.security.canary.logger"):
            gen = CanaryTokenGenerator(secret_key="verify-secret")
            canary = gen.generate_canary("agent-verify")
            result = gen.verify_canary(canary, "agent-verify")

        assert result is True

    def test_verify_canary_returns_false_for_wrong_agent(self):
        """verify_canary should return False when checked against a different agent."""
        with patch("platform.security.canary.logger"):
            gen = CanaryTokenGenerator(secret_key="verify-secret")
            canary = gen.generate_canary("agent-alpha")
            result = gen.verify_canary(canary, "agent-beta")

        assert result is False


class TestDetectLeakedCanary:
    """Tests for CanaryTokenGenerator.detect_leaked_canary."""

    def test_detect_leaked_canary_finds_canary_in_text(self):
        """detect_leaked_canary should identify the agent whose canary appears in text."""
        with patch("platform.security.canary.logger"):
            gen = CanaryTokenGenerator(secret_key="leak-secret")
            canary = gen.generate_canary("agent-leaker")
            text = f"Some document with embedded token {canary} in the middle."
            leaked_agent = gen.detect_leaked_canary(text)

        assert leaked_agent == "agent-leaker"

    def test_detect_leaked_canary_returns_none_for_clean_text(self):
        """detect_leaked_canary should return None when no canary pattern is found."""
        with patch("platform.security.canary.logger"):
            gen = CanaryTokenGenerator(secret_key="clean-secret")
            text = "This is perfectly clean text with no suspicious tokens."
            result = gen.detect_leaked_canary(text)

        assert result is None

    def test_detect_leaked_canary_returns_none_for_unknown_canary(self):
        """detect_leaked_canary should return None for a canary not in the registry."""
        with patch("platform.security.canary.logger"):
            gen = CanaryTokenGenerator(secret_key="unknown-secret")
            # Forge a canary-like string that is not registered
            fake_canary = "srp_canary_abcdef0123456789"
            text = f"Document containing {fake_canary} that is not registered."
            result = gen.detect_leaked_canary(text)

        assert result is None


class TestEmptySecretKey:
    """Tests for empty secret key validation."""

    def test_empty_secret_key_raises_value_error(self):
        """Initializing with an empty secret key should raise ValueError."""
        with pytest.raises(ValueError, match="Secret key must not be empty"):
            CanaryTokenGenerator(secret_key="")

    def test_none_like_empty_string_raises(self):
        """An empty string secret key should raise ValueError."""
        with pytest.raises(ValueError):
            CanaryTokenGenerator(secret_key="")


class TestBulkRegister:
    """Tests for CanaryTokenGenerator.bulk_register."""

    def test_bulk_register_returns_correct_mappings(self):
        """bulk_register should return a dict mapping each agent_id to its canary."""
        with patch("platform.security.canary.logger"):
            gen = CanaryTokenGenerator(secret_key="bulk-secret")
            agent_ids = ["agent-1", "agent-2", "agent-3"]
            mappings = gen.bulk_register(agent_ids)

        assert len(mappings) == 3
        assert set(mappings.keys()) == set(agent_ids)

        # Each canary should match the expected pattern
        for agent_id, canary in mappings.items():
            assert _CANARY_PATTERN.match(canary), f"Canary for {agent_id} doesn't match pattern"

    def test_bulk_register_canaries_match_individual_generation(self):
        """Canaries from bulk_register should match those from generate_canary."""
        with patch("platform.security.canary.logger"):
            gen = CanaryTokenGenerator(secret_key="consistency-secret")
            agent_ids = ["agent-x", "agent-y"]
            mappings = gen.bulk_register(agent_ids)

            for agent_id in agent_ids:
                individual = gen.generate_canary(agent_id)
                assert mappings[agent_id] == individual

    def test_bulk_register_empty_list_returns_empty_dict(self):
        """bulk_register with an empty list should return an empty dict."""
        with patch("platform.security.canary.logger"):
            gen = CanaryTokenGenerator(secret_key="empty-secret")
            mappings = gen.bulk_register([])

        assert mappings == {}


class TestDifferentSecretKeys:
    """Tests that different secret keys produce different canaries."""

    def test_different_secret_keys_produce_different_canaries(self):
        """The same agent_id with different secret keys should produce different canaries."""
        with patch("platform.security.canary.logger"):
            gen1 = CanaryTokenGenerator(secret_key="key-one")
            gen2 = CanaryTokenGenerator(secret_key="key-two")
            canary1 = gen1.generate_canary("agent-same")
            canary2 = gen2.generate_canary("agent-same")

        assert canary1 != canary2
