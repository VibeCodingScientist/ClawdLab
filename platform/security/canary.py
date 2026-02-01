"""Canary Token Generator and Detector.

Generates deterministic HMAC-based canary tokens unique to each agent.
These invisible markers can be embedded in content to detect unauthorized
leaks or exfiltration. If a canary appears in unexpected places, the
system can trace it back to the originating agent.

Canary format: ``srp_canary_{hmac_hex[:16]}``

Usage:
    generator = CanaryTokenGenerator(secret_key="your-secret")
    canary = generator.generate_canary("agent-123")
    assert generator.verify_canary(canary, "agent-123")

    # Detect leaks in arbitrary content
    leaked_agent = generator.detect_leaked_canary(suspicious_text)
"""

from __future__ import annotations

import hashlib
import hmac
import re
from functools import lru_cache
from typing import Any

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

# Canary token prefix and regex pattern
_CANARY_PREFIX = "srp_canary_"
_CANARY_RE = re.compile(r"srp_canary_([a-f0-9]{16})")


class CanaryTokenGenerator:
    """Generate, verify, and detect HMAC-based canary tokens."""

    def __init__(self, secret_key: str) -> None:
        """Initialize with a secret key for HMAC computation.

        Args:
            secret_key: Secret key used for HMAC. Must be kept confidential.

        Raises:
            ValueError: If the secret key is empty.
        """
        if not secret_key:
            raise ValueError("Secret key must not be empty")
        self._secret_key = secret_key.encode("utf-8")
        # Internal mapping of canary -> agent_id for detection
        # Uses an LRU cache for bounded memory usage
        self._canary_to_agent: dict[str, str] = {}

    def generate_canary(self, agent_id: str) -> str:
        """Generate a deterministic canary token for an agent.

        The canary is an HMAC-SHA256 of the agent_id, truncated to 16 hex
        characters. Deterministic: same agent_id always produces the same canary.

        Args:
            agent_id: The agent identifier.

        Returns:
            A canary token string in the format ``srp_canary_{hex}``.
        """
        hmac_hex = self._compute_hmac(agent_id)
        canary = f"{_CANARY_PREFIX}{hmac_hex[:16]}"

        # Store mapping for detection
        self._register_canary(canary, agent_id)

        logger.info(
            "canary_generated",
            agent_id=agent_id,
            canary_prefix=canary[:20] + "...",
        )
        return canary

    def verify_canary(self, canary: str, agent_id: str) -> bool:
        """Verify that a canary token belongs to a specific agent.

        Args:
            canary: The canary token to verify.
            agent_id: The expected agent identifier.

        Returns:
            True if the canary matches the expected agent.
        """
        expected_hmac = self._compute_hmac(agent_id)
        expected_canary = f"{_CANARY_PREFIX}{expected_hmac[:16]}"

        is_valid = hmac.compare_digest(canary, expected_canary)

        if not is_valid:
            logger.warning(
                "canary_verification_failed",
                agent_id=agent_id,
            )

        return is_valid

    def detect_leaked_canary(self, content: str) -> str | None:
        """Scan content for canary token patterns and identify the leaking agent.

        Searches for any ``srp_canary_`` pattern in the content and checks
        the internal registry to identify which agent the canary belongs to.

        Args:
            content: Text content to scan for canary tokens.

        Returns:
            The agent_id of the leaking agent, or None if no canary is found.
        """
        matches = _CANARY_RE.findall(content)

        if not matches:
            return None

        for hmac_fragment in matches:
            canary = f"{_CANARY_PREFIX}{hmac_fragment}"

            # Check the internal registry
            agent_id = self._canary_to_agent.get(canary)
            if agent_id is not None:
                logger.warning(
                    "canary_leak_detected",
                    agent_id=agent_id,
                    canary=canary,
                )
                return agent_id

            # Brute-force check against known agents is not feasible here;
            # we rely on the registry. Log the unknown canary.
            logger.warning(
                "unknown_canary_detected",
                canary=canary,
            )

        # Found canary pattern but could not identify the agent
        return None

    def register_agent(self, agent_id: str) -> str:
        """Pre-register an agent and return their canary.

        This ensures the canary-to-agent mapping is populated for detection.

        Args:
            agent_id: The agent identifier.

        Returns:
            The generated canary token.
        """
        return self.generate_canary(agent_id)

    def bulk_register(self, agent_ids: list[str]) -> dict[str, str]:
        """Register multiple agents and return their canary mappings.

        Args:
            agent_ids: List of agent identifiers.

        Returns:
            Dict mapping agent_id -> canary token.
        """
        return {aid: self.generate_canary(aid) for aid in agent_ids}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_hmac(self, agent_id: str) -> str:
        """Compute HMAC-SHA256 of the agent_id."""
        return hmac.new(
            self._secret_key,
            agent_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _register_canary(self, canary: str, agent_id: str) -> None:
        """Store canary-to-agent mapping with bounded size.

        Keeps at most 10,000 entries. When exceeded, the oldest entries
        are evicted (simple FIFO via dict ordering in Python 3.7+).
        """
        max_entries = 10_000
        if len(self._canary_to_agent) >= max_entries:
            # Evict oldest 10% of entries
            evict_count = max_entries // 10
            keys_to_remove = list(self._canary_to_agent.keys())[:evict_count]
            for key in keys_to_remove:
                del self._canary_to_agent[key]

        self._canary_to_agent[canary] = agent_id
