"""Claim and verification test data factory."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass
class ClaimFactory:
    """Factory for creating Claim test instances."""

    _counter: int = field(default=0, repr=False)

    VALID_TYPES = [
        "theorem",
        "lemma",
        "conjecture",
        "observation",
        "hypothesis",
        "result",
    ]

    VALID_DOMAINS = [
        "mathematics",
        "ml_ai",
        "computational_biology",
        "materials_science",
        "bioinformatics",
    ]

    VALID_STATUSES = [
        "pending",
        "queued",
        "running",
        "verified",
        "failed",
        "disputed",
        "retracted",
        "partial",
    ]

    @classmethod
    def create(
        cls,
        claim_id: str | None = None,
        agent_id: str | None = None,
        claim_type: str = "theorem",
        domain: str = "mathematics",
        title: str | None = None,
        description: str | None = None,
        content: dict[str, Any] | None = None,
        verification_status: str = "pending",
        verification_score: float | None = None,
        novelty_score: float | None = None,
        novelty_assessment: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        is_public: bool = True,
        depends_on: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a claim data dictionary with sensible defaults."""
        cls._counter = getattr(cls, "_counter", 0) + 1

        return {
            "claim_id": claim_id or str(uuid4()),
            "agent_id": agent_id or str(uuid4()),
            "claim_type": claim_type,
            "domain": domain,
            "title": title or f"Test Claim {cls._counter}",
            "description": description or f"Description for test claim {cls._counter}",
            "content": content or cls._default_content(domain, claim_type),
            "verification_status": verification_status,
            "verification_score": verification_score,
            "novelty_score": novelty_score,
            "novelty_assessment": novelty_assessment,
            "tags": tags or ["test", "automated"],
            "is_public": is_public,
            "depends_on": depends_on or [],
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
            "verified_at": None,
            **kwargs,
        }

    @classmethod
    def _default_content(cls, domain: str, claim_type: str) -> dict[str, Any]:
        """Generate default content based on domain and type."""
        if domain == "mathematics":
            return {
                "statement": "For all n > 0, the sum 1 + 2 + ... + n = n*(n+1)/2",
                "proof": "By mathematical induction on n...",
                "formal_statement": "theorem sum_formula (n : Nat) (h : n > 0) : sum_to n = n * (n + 1) / 2",
            }
        elif domain == "ml_ai":
            return {
                "claim": "The proposed architecture achieves state-of-the-art results",
                "method": "Transformer with attention modifications",
                "dataset": "ImageNet-1K",
                "metrics": {"accuracy": 0.87, "f1": 0.86},
            }
        elif domain == "computational_biology":
            return {
                "claim": "Protein X binds to receptor Y with high affinity",
                "binding_site": "residues 100-120",
                "affinity_kd": 1e-9,
                "method": "molecular dynamics simulation",
            }
        elif domain == "materials_science":
            return {
                "claim": "Novel material exhibits superconductivity at 200K",
                "composition": "H3S under high pressure",
                "critical_temperature": 200,
                "pressure_gpa": 150,
            }
        else:  # bioinformatics
            return {
                "claim": "Gene X is significantly upregulated in condition Y",
                "gene_id": "ENSG00000139618",
                "fold_change": 2.5,
                "p_value": 0.001,
            }

    @classmethod
    def create_math_theorem(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a mathematical theorem claim."""
        return cls.create(
            claim_type="theorem",
            domain="mathematics",
            content=kwargs.pop("content", {
                "statement": "Every even integer greater than 2 can be expressed as the sum of two primes",
                "proof_sketch": "We proceed by strong induction...",
                "formal_statement": "theorem goldbach (n : Nat) (h : n > 2) (heven : Even n) : ∃ p q, Prime p ∧ Prime q ∧ p + q = n",
                "proof_system": "lean4",
            }),
            tags=kwargs.pop("tags", ["number-theory", "primes"]),
            **kwargs,
        )

    @classmethod
    def create_ml_result(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a machine learning result claim."""
        return cls.create(
            claim_type="result",
            domain="ml_ai",
            content=kwargs.pop("content", {
                "model": "TransformerV2",
                "task": "image_classification",
                "dataset": "ImageNet-1K",
                "metrics": {
                    "top1_accuracy": 0.89,
                    "top5_accuracy": 0.97,
                    "inference_time_ms": 15,
                },
                "comparison_to_baseline": "+2.3% top1 accuracy",
            }),
            tags=kwargs.pop("tags", ["deep-learning", "vision", "transformers"]),
            **kwargs,
        )

    @classmethod
    def create_biology_claim(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a computational biology claim."""
        return cls.create(
            claim_type="observation",
            domain="computational_biology",
            content=kwargs.pop("content", {
                "finding": "Structure prediction for protein ABC123",
                "method": "AlphaFold2",
                "confidence": 0.92,
                "plddt_score": 85.3,
                "structure_url": "https://example.com/structure.pdb",
            }),
            tags=kwargs.pop("tags", ["protein-structure", "alphafold"]),
            **kwargs,
        )

    @classmethod
    def create_verified(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a verified claim."""
        claim = cls.create(
            verification_status="verified",
            verification_score=kwargs.pop("verification_score", 0.95),
            novelty_score=kwargs.pop("novelty_score", 0.75),
            novelty_assessment=kwargs.pop("novelty_assessment", {
                "is_novel": True,
                "similar_claims": [],
                "novelty_factors": ["new_method", "improved_results"],
            }),
            **kwargs,
        )
        claim["verified_at"] = _utcnow()
        return claim

    @classmethod
    def create_failed(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a failed claim."""
        return cls.create(
            verification_status="failed",
            verification_score=kwargs.pop("verification_score", 0.2),
            **kwargs,
        )

    @classmethod
    def create_disputed(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a disputed claim."""
        return cls.create(
            verification_status="disputed",
            verification_score=kwargs.pop("verification_score", 0.5),
            **kwargs,
        )

    @classmethod
    def create_with_dependencies(
        cls,
        dependency_claim_ids: list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a claim that depends on other claims."""
        return cls.create(
            depends_on=dependency_claim_ids,
            **kwargs,
        )

    @classmethod
    def create_batch(cls, count: int, **kwargs: Any) -> list[dict[str, Any]]:
        """Create multiple claim instances."""
        return [cls.create(**kwargs) for _ in range(count)]


@dataclass
class VerificationResultFactory:
    """Factory for creating VerificationResult test instances."""

    _counter: int = field(default=0, repr=False)

    VERIFIER_TYPES = [
        "lean4",
        "coq",
        "z3",
        "pytorch_eval",
        "alphafold",
        "molecular_dynamics",
    ]

    @classmethod
    def create(
        cls,
        verification_id: str | None = None,
        claim_id: str | None = None,
        verifier_type: str = "lean4",
        verifier_version: str = "4.0.0",
        passed: bool = True,
        score: float | None = None,
        results: dict[str, Any] | None = None,
        compute_seconds: float | None = None,
        compute_cost_usd: float | None = None,
        container_image: str | None = None,
        container_digest: str | None = None,
        environment_hash: str | None = None,
        provenance_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a verification result data dictionary."""
        cls._counter = getattr(cls, "_counter", 0) + 1

        start_time = _utcnow() - timedelta(minutes=5)
        end_time = _utcnow()

        return {
            "verification_id": verification_id or str(uuid4()),
            "claim_id": claim_id or str(uuid4()),
            "verifier_type": verifier_type,
            "verifier_version": verifier_version,
            "passed": passed,
            "score": score if score is not None else (0.95 if passed else 0.1),
            "results": results or cls._default_results(verifier_type, passed),
            "started_at": start_time,
            "completed_at": end_time,
            "compute_seconds": compute_seconds or 300.0,
            "compute_cost_usd": compute_cost_usd or 0.50,
            "container_image": container_image or f"ghcr.io/asrp/verifier-{verifier_type}:latest",
            "container_digest": container_digest or "sha256:" + "a" * 64,
            "environment_hash": environment_hash or "b" * 64,
            "provenance_id": provenance_id,
            "created_at": _utcnow(),
            **kwargs,
        }

    @classmethod
    def _default_results(cls, verifier_type: str, passed: bool) -> dict[str, Any]:
        """Generate default results based on verifier type."""
        if verifier_type in ["lean4", "coq"]:
            return {
                "proof_valid": passed,
                "goals_completed": 5 if passed else 3,
                "total_goals": 5,
                "tactics_used": ["induction", "simp", "ring"],
                "proof_length": 42,
            }
        elif verifier_type == "z3":
            return {
                "satisfiable": not passed,  # Proof is valid if formula is unsatisfiable
                "model": None if passed else {"x": 1, "y": 2},
                "statistics": {"time": 0.5, "memory": 100},
            }
        elif verifier_type == "pytorch_eval":
            return {
                "metrics_match": passed,
                "accuracy": 0.89 if passed else 0.45,
                "loss": 0.11 if passed else 0.95,
                "samples_evaluated": 10000,
            }
        elif verifier_type == "alphafold":
            return {
                "prediction_valid": passed,
                "plddt_score": 85.0 if passed else 45.0,
                "ptm_score": 0.8 if passed else 0.3,
                "structure_generated": passed,
            }
        else:
            return {
                "verification_passed": passed,
                "details": "Default verification results",
            }

    @classmethod
    def create_math_verification(cls, passed: bool = True, **kwargs: Any) -> dict[str, Any]:
        """Create a mathematical verification result."""
        return cls.create(
            verifier_type=kwargs.pop("verifier_type", "lean4"),
            verifier_version=kwargs.pop("verifier_version", "4.3.0"),
            passed=passed,
            results=kwargs.pop("results", {
                "proof_valid": passed,
                "type_checked": passed,
                "goals_completed": 5 if passed else 2,
                "total_goals": 5,
                "error_messages": [] if passed else ["goal not solved"],
            }),
            **kwargs,
        )

    @classmethod
    def create_ml_verification(cls, passed: bool = True, **kwargs: Any) -> dict[str, Any]:
        """Create a machine learning verification result."""
        return cls.create(
            verifier_type=kwargs.pop("verifier_type", "pytorch_eval"),
            verifier_version=kwargs.pop("verifier_version", "2.0.0"),
            passed=passed,
            results=kwargs.pop("results", {
                "metrics_reproduced": passed,
                "accuracy_reported": 0.89,
                "accuracy_reproduced": 0.88 if passed else 0.65,
                "within_tolerance": passed,
                "tolerance": 0.02,
            }),
            compute_seconds=kwargs.pop("compute_seconds", 3600.0),
            compute_cost_usd=kwargs.pop("compute_cost_usd", 5.00),
            **kwargs,
        )

    @classmethod
    def create_bio_verification(cls, passed: bool = True, **kwargs: Any) -> dict[str, Any]:
        """Create a computational biology verification result."""
        return cls.create(
            verifier_type=kwargs.pop("verifier_type", "alphafold"),
            verifier_version=kwargs.pop("verifier_version", "2.3.1"),
            passed=passed,
            results=kwargs.pop("results", {
                "structure_predicted": passed,
                "plddt_score": 87.5 if passed else 42.0,
                "ptm_score": 0.85 if passed else 0.35,
                "rmsd_to_reference": 1.2 if passed else 8.5,
                "acceptable_rmsd_threshold": 2.0,
            }),
            compute_seconds=kwargs.pop("compute_seconds", 7200.0),
            compute_cost_usd=kwargs.pop("compute_cost_usd", 15.00),
            **kwargs,
        )

    @classmethod
    def create_batch(
        cls,
        count: int,
        claim_id: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Create multiple verification results for a claim."""
        return [cls.create(claim_id=claim_id, **kwargs) for _ in range(count)]


@dataclass
class ChallengeFactory:
    """Factory for creating Challenge test instances."""

    _counter: int = field(default=0, repr=False)

    CHALLENGE_TYPES = [
        "methodology",
        "reproducibility",
        "proof_error",
        "data_quality",
        "statistical",
    ]

    CHALLENGE_STATUSES = [
        "open",
        "under_review",
        "resolved_accepted",
        "resolved_rejected",
        "withdrawn",
    ]

    @classmethod
    def create(
        cls,
        challenge_id: str | None = None,
        claim_id: str | None = None,
        challenger_agent_id: str | None = None,
        challenge_type: str = "methodology",
        status: str = "open",
        title: str | None = None,
        description: str | None = None,
        evidence: dict[str, Any] | None = None,
        challenger_stake: int = 100,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a challenge data dictionary."""
        cls._counter = getattr(cls, "_counter", 0) + 1

        return {
            "challenge_id": challenge_id or str(uuid4()),
            "claim_id": claim_id or str(uuid4()),
            "challenger_agent_id": challenger_agent_id or str(uuid4()),
            "challenge_type": challenge_type,
            "status": status,
            "title": title or f"Test Challenge {cls._counter}",
            "description": description or f"Challenge description {cls._counter}",
            "evidence": evidence or {
                "type": "counter_example",
                "details": "Found edge case where claim fails",
            },
            "challenger_stake": challenger_stake,
            "resolution_summary": None,
            "resolved_at": None,
            "resolved_by": None,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
            **kwargs,
        }

    @classmethod
    def create_resolved_accepted(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a resolved challenge that was accepted (claim invalidated)."""
        challenge = cls.create(
            status="resolved_accepted",
            **kwargs,
        )
        challenge["resolved_at"] = _utcnow()
        challenge["resolved_by"] = "consensus"
        challenge["resolution_summary"] = "Challenge accepted. Claim has fundamental flaw."
        return challenge

    @classmethod
    def create_resolved_rejected(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a resolved challenge that was rejected (claim upheld)."""
        challenge = cls.create(
            status="resolved_rejected",
            **kwargs,
        )
        challenge["resolved_at"] = _utcnow()
        challenge["resolved_by"] = "consensus"
        challenge["resolution_summary"] = "Challenge rejected. Original claim is valid."
        return challenge


@dataclass
class ChallengeVoteFactory:
    """Factory for creating ChallengeVote test instances."""

    @classmethod
    def create(
        cls,
        vote_id: str | None = None,
        challenge_id: str | None = None,
        voter_agent_id: str | None = None,
        vote: str = "uphold",
        confidence: float = 0.8,
        reasoning: str | None = None,
        vote_weight: float = 1.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a challenge vote data dictionary."""
        return {
            "vote_id": vote_id or str(uuid4()),
            "challenge_id": challenge_id or str(uuid4()),
            "voter_agent_id": voter_agent_id or str(uuid4()),
            "vote": vote,  # "uphold", "reject", or "abstain"
            "confidence": confidence,
            "reasoning": reasoning or "Based on my analysis of the evidence...",
            "vote_weight": vote_weight,
            "created_at": _utcnow(),
            **kwargs,
        }

    @classmethod
    def create_uphold_vote(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a vote to uphold the challenge (invalidate claim)."""
        return cls.create(
            vote="uphold",
            confidence=kwargs.pop("confidence", 0.85),
            reasoning=kwargs.pop("reasoning", "The challenger's evidence is compelling."),
            **kwargs,
        )

    @classmethod
    def create_reject_vote(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a vote to reject the challenge (uphold claim)."""
        return cls.create(
            vote="reject",
            confidence=kwargs.pop("confidence", 0.9),
            reasoning=kwargs.pop("reasoning", "The original claim is well-supported."),
            **kwargs,
        )
