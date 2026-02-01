"""Consistency checker for verified claims.

After a claim passes domain verification (and optionally robustness
checking), the consistency checker examines how it relates to existing
claims in the knowledge base.  Contradictions with previously verified
claims reduce confidence and may result in an AMBER badge.

The checker uses ``CitationRepository`` to find related claims (those
that cite or are cited by the current claim, or that share the same
domain and tags) and performs pairwise consistency analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import Claim, Citation
from platform.labs.repository import CitationRepository
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ConsistencyResult:
    """Outcome of a consistency check.

    Attributes:
        consistent: ``True`` if no significant contradictions were found.
        contradictions: List of dicts describing each contradiction, with
            keys ``claim_id``, ``title``, ``relationship``, ``severity``,
            ``description``.
        confidence: Float in [0, 1] representing overall consistency
            confidence.  1.0 = fully consistent, 0.0 = severe
            contradictions.
    """

    consistent: bool
    contradictions: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------


class ConsistencyChecker:
    """Checks a claim for consistency against the existing knowledge base.

    Uses citation relationships and domain/tag overlap to find related
    claims, then performs pairwise consistency analysis.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.citation_repo = CitationRepository(session)

    async def check_consistency(
        self,
        claim_id: str,
        domain: str,
        payload: dict[str, Any],
        max_related: int = 20,
        contradiction_threshold: float = 0.7,
    ) -> ConsistencyResult:
        """Analyse a claim against related claims for contradictions.

        Args:
            claim_id: UUID of the claim to check.
            domain: Scientific domain string.
            payload: Claim content/payload dict.
            max_related: Maximum number of related claims to inspect.
            contradiction_threshold: Confidence below this value means
                the claim is flagged inconsistent.

        Returns:
            ``ConsistencyResult`` with contradiction details.
        """
        cid = UUID(claim_id) if isinstance(claim_id, str) else claim_id

        # ---- Gather related claims ----
        related_claims = await self._find_related_claims(
            cid, domain, payload, max_related
        )

        if not related_claims:
            logger.info(
                "consistency_no_related_claims",
                claim_id=claim_id,
                domain=domain,
            )
            return ConsistencyResult(
                consistent=True,
                contradictions=[],
                confidence=1.0,
            )

        # ---- Pairwise consistency analysis ----
        contradictions: list[dict[str, Any]] = []
        for related in related_claims:
            contradiction = await self._check_pairwise(
                claim_payload=payload,
                claim_domain=domain,
                related_claim=related,
            )
            if contradiction is not None:
                contradictions.append(contradiction)

        # ---- Compute overall confidence ----
        if not contradictions:
            confidence = 1.0
        else:
            # Each contradiction reduces confidence proportionally to
            # its severity.
            severity_sum = sum(
                c.get("severity_score", 0.5) for c in contradictions
            )
            confidence = max(0.0, 1.0 - severity_sum / max(len(related_claims), 1))

        consistent = confidence >= contradiction_threshold

        logger.info(
            "consistency_check_complete",
            claim_id=claim_id,
            domain=domain,
            related_count=len(related_claims),
            contradiction_count=len(contradictions),
            confidence=round(confidence, 4),
            consistent=consistent,
        )

        return ConsistencyResult(
            consistent=consistent,
            contradictions=contradictions,
            confidence=round(confidence, 4),
        )

    # ------------------------------------------------------------------
    # Related claim discovery
    # ------------------------------------------------------------------

    async def _find_related_claims(
        self,
        claim_id: UUID,
        domain: str,
        payload: dict[str, Any],
        max_related: int,
    ) -> list[dict[str, Any]]:
        """Find claims related to the target by citations, domain, and tags.

        The union of the following sets is returned (de-duplicated):

        1. Claims that the target cites.
        2. Claims that cite the target.
        3. Claims in the same domain that are verified and share at
           least one tag.
        """
        related_ids: set[str] = set()
        related_claims: list[dict[str, Any]] = []

        # 1 & 2 -- citation relationships
        citing = await self.citation_repo.get_citations_for(claim_id)
        cited_by = await self.citation_repo.get_cited_by(claim_id)

        for c in citing:
            related_ids.add(str(c.cited_claim_id))
        for c in cited_by:
            related_ids.add(str(c.citing_claim_id))

        # 3 -- domain + tag overlap
        tags = payload.get("tags", [])
        tag_query = (
            select(Claim)
            .where(
                and_(
                    Claim.domain == domain,
                    Claim.verification_status == "verified",
                    Claim.id != claim_id,
                )
            )
            .order_by(Claim.created_at.desc())
            .limit(max_related)
        )
        # If we have tags, prefer claims sharing them
        if tags:
            tag_query = tag_query.where(Claim.tags.overlap(tags))

        tag_result = await self.session.execute(tag_query)
        for claim in tag_result.scalars().all():
            related_ids.add(str(claim.id))

        # Remove self
        related_ids.discard(str(claim_id))

        # Fetch full rows for all related IDs (up to limit)
        if not related_ids:
            return []

        target_ids = [UUID(rid) for rid in list(related_ids)[:max_related]]
        result = await self.session.execute(
            select(Claim).where(Claim.id.in_(target_ids))
        )

        for claim in result.scalars().all():
            related_claims.append({
                "claim_id": str(claim.id),
                "title": claim.title,
                "domain": claim.domain,
                "claim_type": claim.claim_type,
                "verification_status": claim.verification_status,
                "content": claim.content,
                "tags": list(claim.tags) if claim.tags else [],
            })

        return related_claims

    # ------------------------------------------------------------------
    # Pairwise analysis
    # ------------------------------------------------------------------

    async def _check_pairwise(
        self,
        claim_payload: dict[str, Any],
        claim_domain: str,
        related_claim: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Compare two claims for contradictions.

        The comparison is domain-aware:

        **mathematics**: Checks for contradictory conclusions (e.g.
        one proves P, the other disproves P or proves not-P).

        **ml_ai**: Checks for conflicting performance claims on the
        same benchmark/dataset (e.g. one reports SOTA accuracy of X,
        the other reports a higher baseline accuracy on the same
        benchmark).

        **computational_biology / bioinformatics**: Checks for
        contradictory biological conclusions (e.g. gene A is
        upregulated vs downregulated in the same condition).

        **materials_science**: Checks for conflicting property
        predictions for the same material/composition.

        Returns a contradiction dict or ``None`` if no contradiction
        is detected.
        """
        related_content = related_claim.get("content", {})

        # Domain-specific comparators
        if claim_domain == "mathematics":
            return self._compare_math(claim_payload, related_claim, related_content)
        elif claim_domain == "ml_ai":
            return self._compare_ml(claim_payload, related_claim, related_content)
        elif claim_domain in ("computational_biology", "bioinformatics"):
            return self._compare_bio(claim_payload, related_claim, related_content)
        elif claim_domain == "materials_science":
            return self._compare_materials(claim_payload, related_claim, related_content)

        # Generic fallback: no contradiction detected
        return None

    # ------------------------------------------------------------------
    # Domain comparators
    # ------------------------------------------------------------------

    @staticmethod
    def _compare_math(
        payload: dict[str, Any],
        related: dict[str, Any],
        related_content: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Check for contradictory mathematical conclusions."""
        conclusion = payload.get("conclusion", "").lower()
        related_conclusion = related_content.get("conclusion", "").lower()

        if not conclusion or not related_conclusion:
            return None

        # Simple negation detection
        negation_pairs = [
            ("true", "false"),
            ("provable", "unprovable"),
            ("convergent", "divergent"),
            ("bounded", "unbounded"),
            ("exists", "does not exist"),
        ]

        for pos, neg in negation_pairs:
            if (pos in conclusion and neg in related_conclusion) or \
               (neg in conclusion and pos in related_conclusion):
                return {
                    "claim_id": related["claim_id"],
                    "title": related["title"],
                    "relationship": "contradictory_conclusion",
                    "severity": "high",
                    "severity_score": 0.8,
                    "description": (
                        f"Mathematical contradiction: current claim concludes "
                        f"'{conclusion[:100]}' while related claim concludes "
                        f"'{related_conclusion[:100]}'"
                    ),
                }
        return None

    @staticmethod
    def _compare_ml(
        payload: dict[str, Any],
        related: dict[str, Any],
        related_content: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Check for conflicting ML performance claims on the same benchmark."""
        dataset = payload.get("dataset", "")
        related_dataset = related_content.get("dataset", "")

        if not dataset or dataset.lower() != related_dataset.lower():
            return None  # Different benchmarks -- not comparable

        metrics = payload.get("metrics", {})
        related_metrics = related_content.get("metrics", {})

        for metric_name in metrics:
            if metric_name in related_metrics:
                val = metrics[metric_name]
                related_val = related_metrics[metric_name]
                if isinstance(val, (int, float)) and isinstance(related_val, (int, float)):
                    # Flag if the difference is > 20% of the larger value
                    max_val = max(abs(val), abs(related_val), 1e-9)
                    relative_diff = abs(val - related_val) / max_val
                    if relative_diff > 0.20:
                        return {
                            "claim_id": related["claim_id"],
                            "title": related["title"],
                            "relationship": "conflicting_benchmark_result",
                            "severity": "medium",
                            "severity_score": 0.5,
                            "description": (
                                f"Conflicting {metric_name} on dataset '{dataset}': "
                                f"current={val}, related={related_val} "
                                f"(relative diff: {relative_diff:.2%})"
                            ),
                        }
        return None

    @staticmethod
    def _compare_bio(
        payload: dict[str, Any],
        related: dict[str, Any],
        related_content: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Check for contradictory biological findings."""
        gene = payload.get("gene", "").upper()
        related_gene = related_content.get("gene", "").upper()

        if not gene or gene != related_gene:
            return None

        condition = payload.get("condition", "").lower()
        related_condition = related_content.get("condition", "").lower()

        if condition != related_condition:
            return None

        direction = payload.get("direction", "").lower()
        related_direction = related_content.get("direction", "").lower()

        opposite_pairs = {
            ("upregulated", "downregulated"),
            ("increased", "decreased"),
            ("activated", "inhibited"),
            ("overexpressed", "underexpressed"),
        }

        for a, b in opposite_pairs:
            if (direction == a and related_direction == b) or \
               (direction == b and related_direction == a):
                return {
                    "claim_id": related["claim_id"],
                    "title": related["title"],
                    "relationship": "contradictory_biological_finding",
                    "severity": "high",
                    "severity_score": 0.7,
                    "description": (
                        f"Contradictory finding for gene {gene} under "
                        f"condition '{condition}': current={direction}, "
                        f"related={related_direction}"
                    ),
                }
        return None

    @staticmethod
    def _compare_materials(
        payload: dict[str, Any],
        related: dict[str, Any],
        related_content: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Check for conflicting property predictions for the same material."""
        composition = payload.get("composition", "")
        related_composition = related_content.get("composition", "")

        if not composition or composition.lower() != related_composition.lower():
            return None

        properties = payload.get("properties", {})
        related_properties = related_content.get("properties", {})

        for prop_name in properties:
            if prop_name in related_properties:
                val = properties[prop_name]
                related_val = related_properties[prop_name]
                if isinstance(val, (int, float)) and isinstance(related_val, (int, float)):
                    max_val = max(abs(val), abs(related_val), 1e-9)
                    relative_diff = abs(val - related_val) / max_val
                    if relative_diff > 0.30:
                        return {
                            "claim_id": related["claim_id"],
                            "title": related["title"],
                            "relationship": "conflicting_material_property",
                            "severity": "medium",
                            "severity_score": 0.5,
                            "description": (
                                f"Conflicting {prop_name} for composition "
                                f"'{composition}': current={val}, "
                                f"related={related_val} "
                                f"(relative diff: {relative_diff:.2%})"
                            ),
                        }
        return None


__all__ = ["ConsistencyResult", "ConsistencyChecker"]
