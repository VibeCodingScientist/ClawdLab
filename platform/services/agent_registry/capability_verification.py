"""Capability verification service for Agent Registry.

This module provides basic capability testing for agents to verify
their declared domain capabilities. Each domain has simple verification
challenges that agents must complete to prove competency.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from platform.services.agent_registry.repository import AgentRepository
from platform.shared.clients.redis_client import RedisCache
from platform.shared.schemas.base import Domain
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# ===========================================
# CAPABILITY CHALLENGES BY DOMAIN
# ===========================================

# Simple verification challenges for each domain
# These are basic tests to verify the agent has minimum competency

DOMAIN_CHALLENGES = {
    Domain.MATHEMATICS.value: {
        "id": "math_basic_001",
        "type": "proof_completion",
        "description": "Complete a simple mathematical proof",
        "challenge": {
            "statement": "Prove that for all natural numbers n, 0 + n = n",
            "hint": "Use induction or the definition of addition",
            "expected_elements": ["base case", "inductive step", "qed"],
        },
        "timeout_seconds": 300,
    },
    Domain.ML_AI.value: {
        "id": "ml_basic_001",
        "type": "model_evaluation",
        "description": "Evaluate a simple classification model",
        "challenge": {
            "task": "Calculate precision, recall, and F1 score from confusion matrix",
            "confusion_matrix": {
                "true_positive": 85,
                "false_positive": 15,
                "false_negative": 10,
                "true_negative": 90,
            },
            "expected_precision": 0.85,
            "expected_recall": 0.895,
            "expected_f1": 0.872,
            "tolerance": 0.01,
        },
        "timeout_seconds": 60,
    },
    Domain.COMPUTATIONAL_BIOLOGY.value: {
        "id": "compbio_basic_001",
        "type": "sequence_analysis",
        "description": "Analyze a protein sequence",
        "challenge": {
            "task": "Calculate molecular weight and identify sequence motifs",
            "sequence": "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSH",
            "expected_amino_acid_count": 51,
            "expected_motif": "heme binding",
        },
        "timeout_seconds": 120,
    },
    Domain.MATERIALS_SCIENCE.value: {
        "id": "matsci_basic_001",
        "type": "structure_analysis",
        "description": "Analyze a crystal structure",
        "challenge": {
            "task": "Identify crystal system and space group from lattice parameters",
            "lattice": {"a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
            "expected_crystal_system": "cubic",
            "expected_formula": "Si",
        },
        "timeout_seconds": 120,
    },
    Domain.BIOINFORMATICS.value: {
        "id": "bioinfo_basic_001",
        "type": "pipeline_design",
        "description": "Design a basic RNA-seq analysis pipeline",
        "challenge": {
            "task": "Outline the main steps for a differential expression analysis",
            "expected_steps": [
                "quality_control",
                "trimming",
                "alignment",
                "quantification",
                "normalization",
                "differential_expression",
            ],
        },
        "timeout_seconds": 180,
    },
}


class CapabilityVerificationService:
    """
    Service for verifying agent domain capabilities.

    Provides basic capability tests that agents must complete
    to prove competency in declared domains.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.agent_repo = AgentRepository(session)
        self.cache = RedisCache("capability_verification")

    async def get_verification_challenge(
        self,
        agent_id: str | UUID,
        domain: str,
    ) -> dict[str, Any]:
        """
        Get a verification challenge for a domain.

        Args:
            agent_id: Agent requesting verification
            domain: Domain to verify

        Returns:
            Challenge data for the agent to complete
        """
        if domain not in DOMAIN_CHALLENGES:
            raise ValueError(f"No verification challenge for domain: {domain}")

        challenge = DOMAIN_CHALLENGES[domain].copy()
        challenge_id = f"cap_verify:{agent_id}:{domain}:{datetime.utcnow().timestamp()}"

        # Store challenge state in cache
        await self.cache.setex(
            challenge_id,
            challenge["timeout_seconds"] + 60,  # Extra buffer
            {
                "agent_id": str(agent_id),
                "domain": domain,
                "challenge_data": challenge,
                "started_at": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            "capability_challenge_issued",
            agent_id=str(agent_id),
            domain=domain,
            challenge_id=challenge_id,
        )

        return {
            "challenge_id": challenge_id,
            "domain": domain,
            "challenge_type": challenge["type"],
            "description": challenge["description"],
            "challenge": challenge["challenge"],
            "timeout_seconds": challenge["timeout_seconds"],
            "expires_at": datetime.utcnow() + timedelta(seconds=challenge["timeout_seconds"]),
        }

    async def submit_verification_response(
        self,
        challenge_id: str,
        agent_id: str | UUID,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Submit a response to a verification challenge.

        Args:
            challenge_id: Challenge being responded to
            agent_id: Agent submitting response
            response: Agent's response to the challenge

        Returns:
            Verification result
        """
        # Retrieve challenge data
        challenge_data = await self.cache.get(challenge_id)
        if not challenge_data:
            return {
                "verified": False,
                "error": "Challenge expired or not found",
            }

        if challenge_data["agent_id"] != str(agent_id):
            return {
                "verified": False,
                "error": "Challenge does not belong to this agent",
            }

        domain = challenge_data["domain"]
        challenge = challenge_data["challenge_data"]["challenge"]

        # Verify the response based on domain
        verified, details = self._verify_response(domain, challenge, response)

        if verified:
            # Update agent capability level
            await self._upgrade_capability(agent_id, domain)
            await self.session.commit()

        # Clean up challenge
        await self.cache.delete(challenge_id)

        logger.info(
            "capability_verification_completed",
            agent_id=str(agent_id),
            domain=domain,
            verified=verified,
        )

        return {
            "verified": verified,
            "domain": domain,
            "capability_level": "verified" if verified else "basic",
            "details": details,
        }

    def _verify_response(
        self,
        domain: str,
        challenge: dict,
        response: dict,
    ) -> tuple[bool, dict]:
        """
        Verify a response for a specific domain challenge.

        This is a simplified verification. In production, each domain
        would have more sophisticated verification logic.
        """
        try:
            if domain == Domain.ML_AI.value:
                return self._verify_ml_response(challenge, response)
            elif domain == Domain.MATHEMATICS.value:
                return self._verify_math_response(challenge, response)
            elif domain == Domain.COMPUTATIONAL_BIOLOGY.value:
                return self._verify_compbio_response(challenge, response)
            elif domain == Domain.MATERIALS_SCIENCE.value:
                return self._verify_matsci_response(challenge, response)
            elif domain == Domain.BIOINFORMATICS.value:
                return self._verify_bioinfo_response(challenge, response)
            else:
                return False, {"error": f"Unknown domain: {domain}"}
        except Exception as e:
            logger.exception("verification_error", domain=domain)
            return False, {"error": str(e)}

    def _verify_ml_response(self, challenge: dict, response: dict) -> tuple[bool, dict]:
        """Verify ML/AI challenge response."""
        cm = challenge["confusion_matrix"]
        tolerance = challenge["tolerance"]

        expected_precision = challenge["expected_precision"]
        expected_recall = challenge["expected_recall"]
        expected_f1 = challenge["expected_f1"]

        precision = response.get("precision", 0)
        recall = response.get("recall", 0)
        f1 = response.get("f1", 0)

        precision_ok = abs(precision - expected_precision) <= tolerance
        recall_ok = abs(recall - expected_recall) <= tolerance
        f1_ok = abs(f1 - expected_f1) <= tolerance

        verified = precision_ok and recall_ok and f1_ok

        return verified, {
            "precision": {"submitted": precision, "expected": expected_precision, "correct": precision_ok},
            "recall": {"submitted": recall, "expected": expected_recall, "correct": recall_ok},
            "f1": {"submitted": f1, "expected": expected_f1, "correct": f1_ok},
        }

    def _verify_math_response(self, challenge: dict, response: dict) -> tuple[bool, dict]:
        """Verify mathematics challenge response."""
        proof = response.get("proof", "").lower()
        expected_elements = challenge["expected_elements"]

        found_elements = []
        missing_elements = []

        for element in expected_elements:
            if element.lower() in proof:
                found_elements.append(element)
            else:
                missing_elements.append(element)

        verified = len(missing_elements) == 0 and len(proof) > 50

        return verified, {
            "found_elements": found_elements,
            "missing_elements": missing_elements,
            "proof_length": len(proof),
        }

    def _verify_compbio_response(self, challenge: dict, response: dict) -> tuple[bool, dict]:
        """Verify computational biology challenge response."""
        amino_acid_count = response.get("amino_acid_count", 0)
        expected_count = challenge["expected_amino_acid_count"]

        count_ok = amino_acid_count == expected_count
        motif_identified = challenge["expected_motif"].lower() in response.get("motifs", "").lower()

        verified = count_ok and motif_identified

        return verified, {
            "amino_acid_count": {"submitted": amino_acid_count, "expected": expected_count, "correct": count_ok},
            "motif_identification": motif_identified,
        }

    def _verify_matsci_response(self, challenge: dict, response: dict) -> tuple[bool, dict]:
        """Verify materials science challenge response."""
        crystal_system = response.get("crystal_system", "").lower()
        expected_system = challenge["expected_crystal_system"].lower()

        system_ok = crystal_system == expected_system

        return system_ok, {
            "crystal_system": {"submitted": crystal_system, "expected": expected_system, "correct": system_ok},
        }

    def _verify_bioinfo_response(self, challenge: dict, response: dict) -> tuple[bool, dict]:
        """Verify bioinformatics challenge response."""
        submitted_steps = [s.lower() for s in response.get("pipeline_steps", [])]
        expected_steps = [s.lower() for s in challenge["expected_steps"]]

        found_steps = []
        missing_steps = []

        for step in expected_steps:
            if any(step in submitted for submitted in submitted_steps):
                found_steps.append(step)
            else:
                missing_steps.append(step)

        verified = len(missing_steps) <= 1  # Allow one missing step

        return verified, {
            "found_steps": found_steps,
            "missing_steps": missing_steps,
        }

    async def _upgrade_capability(self, agent_id: str | UUID, domain: str) -> None:
        """Upgrade agent's capability level after verification."""
        from platform.infrastructure.database.models import AgentCapability
        from sqlalchemy import update

        await self.session.execute(
            update(AgentCapability)
            .where(
                AgentCapability.agent_id == agent_id,
                AgentCapability.domain == domain,
            )
            .values(
                capability_level="verified",
                verified_at=datetime.utcnow(),
            )
        )

    async def get_agent_capabilities(self, agent_id: str | UUID) -> list[dict[str, Any]]:
        """Get all capabilities and their verification status for an agent."""
        capabilities = await self.agent_repo.get_capabilities(agent_id)
        return [
            {
                "domain": c.domain,
                "level": c.capability_level,
                "verified_at": c.verified_at,
                "is_verified": c.capability_level == "verified",
            }
            for c in capabilities
        ]

    async def check_capability_expiry(self, agent_id: str | UUID) -> list[str]:
        """
        Check for capabilities that need re-verification.

        Capabilities expire after 90 days of inactivity and need
        to be re-verified.

        Returns:
            List of domains that need re-verification
        """
        expiry_days = 90
        cutoff = datetime.utcnow() - timedelta(days=expiry_days)

        capabilities = await self.agent_repo.get_capabilities(agent_id)
        expired = []

        for cap in capabilities:
            if cap.capability_level == "verified" and cap.verified_at:
                if cap.verified_at < cutoff:
                    expired.append(cap.domain)

        return expired
