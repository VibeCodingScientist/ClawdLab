"""Citation Graph Service for cross-lab impact analysis.

Provides functionality for recording citations, computing impact metrics,
detecting research clusters via lab-to-lab citation adjacency, and
measuring per-lab impact.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.models import (
    Citation,
    Claim,
    Lab,
    LabMembership,
)
from platform.labs.repository import CitationRepository, LabRepository
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CitationGraphService:
    """Service for citation graph operations and impact analysis."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.citation_repo = CitationRepository(session)
        self.lab_repo = LabRepository(session)

    # ------------------------------------------------------------------
    # Record citation
    # ------------------------------------------------------------------

    async def record_citation(
        self,
        citing_claim_id: str | UUID,
        cited_claim_id: str | UUID,
        lab_id: str | UUID | None = None,
        context: str | None = None,
    ) -> dict[str, Any]:
        """Record a citation between two claims.

        Args:
            citing_claim_id: The claim that references another.
            cited_claim_id: The claim being referenced.
            lab_id: Optional lab context for the citation.
            context: Optional text describing why the citation was made.

        Returns:
            Dict representation of the created citation.

        Raises:
            ValueError: If citing and cited claim IDs are the same.
        """
        citing_id = UUID(str(citing_claim_id))
        cited_id = UUID(str(cited_claim_id))

        if citing_id == cited_id:
            raise ValueError("A claim cannot cite itself")

        # Verify both claims exist
        for cid, label in [(citing_id, "citing"), (cited_id, "cited")]:
            q = select(Claim.id).where(Claim.id == cid)
            result = await self.session.execute(q)
            if result.scalar_one_or_none() is None:
                raise ValueError(f"The {label} claim {cid} does not exist")

        citation = await self.citation_repo.create(
            citing_claim_id=citing_id,
            cited_claim_id=cited_id,
            citing_lab_id=UUID(str(lab_id)) if lab_id else None,
            context=context,
        )

        logger.info(
            "citation_recorded",
            citing=str(citing_id),
            cited=str(cited_id),
            lab_id=str(lab_id) if lab_id else None,
        )

        return {
            "id": str(citation.id),
            "citing_claim_id": str(citation.citing_claim_id),
            "cited_claim_id": str(citation.cited_claim_id),
            "citing_lab_id": str(citation.citing_lab_id) if citation.citing_lab_id else None,
            "context": citation.context,
            "created_at": citation.created_at.isoformat() if citation.created_at else None,
        }

    # ------------------------------------------------------------------
    # Impact metrics for a single claim
    # ------------------------------------------------------------------

    async def get_impact_metrics(self, claim_id: str | UUID) -> dict[str, Any]:
        """Compute citation impact metrics for a claim.

        Returns:
            Dict containing:
                - claim_id
                - direct_citations: number of claims that directly cite this
                - indirect_citations: 2nd-degree citations (claims citing claims
                  that cite this one)
                - cross_lab_citations: citations from claims in a different lab
                - total_impact: direct + indirect
        """
        cid = UUID(str(claim_id))

        # Direct citations: claims that cite this one
        direct_q = (
            select(func.count())
            .select_from(Citation)
            .where(Citation.cited_claim_id == cid)
        )
        direct_count = (await self.session.execute(direct_q)).scalar() or 0

        # 2nd-degree citations: claims citing the direct citers
        direct_citers_q = (
            select(Citation.citing_claim_id)
            .where(Citation.cited_claim_id == cid)
        )
        indirect_q = (
            select(func.count())
            .select_from(Citation)
            .where(
                Citation.cited_claim_id.in_(direct_citers_q)
            )
        )
        indirect_count = (await self.session.execute(indirect_q)).scalar() or 0

        # Cross-lab citations
        # Get the lab_id of the cited claim
        cited_claim_q = select(Claim.lab_id).where(Claim.id == cid)
        cited_lab_id = (await self.session.execute(cited_claim_q)).scalar()

        cross_lab_count = 0
        if cited_lab_id is not None:
            # Count citations where citing claim's lab differs from cited claim's lab
            cross_q = (
                select(func.count())
                .select_from(Citation)
                .join(Claim, Citation.citing_claim_id == Claim.id)
                .where(
                    and_(
                        Citation.cited_claim_id == cid,
                        Claim.lab_id.isnot(None),
                        Claim.lab_id != cited_lab_id,
                    )
                )
            )
            cross_lab_count = (await self.session.execute(cross_q)).scalar() or 0
        else:
            # If cited claim has no lab, all citations with a lab are cross-lab
            cross_q = (
                select(func.count())
                .select_from(Citation)
                .join(Claim, Citation.citing_claim_id == Claim.id)
                .where(
                    and_(
                        Citation.cited_claim_id == cid,
                        Claim.lab_id.isnot(None),
                    )
                )
            )
            cross_lab_count = (await self.session.execute(cross_q)).scalar() or 0

        logger.info(
            "impact_metrics_computed",
            claim_id=str(cid),
            direct=direct_count,
            indirect=indirect_count,
            cross_lab=cross_lab_count,
        )

        return {
            "claim_id": str(cid),
            "direct_citations": direct_count,
            "indirect_citations": indirect_count,
            "cross_lab_citations": cross_lab_count,
            "total_impact": direct_count + indirect_count,
        }

    # ------------------------------------------------------------------
    # Cluster detection
    # ------------------------------------------------------------------

    async def detect_clusters(self) -> list[dict[str, Any]]:
        """Detect research clusters via lab-to-lab citation adjacency.

        Uses a simple connected-components algorithm on the lab citation
        graph. Two labs are connected if there exists at least one citation
        from a claim in one lab to a claim in the other.

        Returns:
            List of cluster dicts, each containing ``cluster_id``,
            ``lab_ids``, ``lab_slugs``, ``edge_count``.
        """
        # Build lab-to-lab adjacency from citations
        citing_claim = select(Claim.id, Claim.lab_id).where(Claim.lab_id.isnot(None)).subquery("citing_alias")
        cited_claim = select(Claim.id, Claim.lab_id).where(Claim.lab_id.isnot(None)).subquery("cited_alias")

        edge_q = (
            select(
                citing_claim.c.lab_id.label("from_lab"),
                cited_claim.c.lab_id.label("to_lab"),
                func.count().label("edge_weight"),
            )
            .select_from(Citation)
            .join(citing_claim, Citation.citing_claim_id == citing_claim.c.id)
            .join(cited_claim, Citation.cited_claim_id == cited_claim.c.id)
            .where(citing_claim.c.lab_id != cited_claim.c.lab_id)
            .group_by(citing_claim.c.lab_id, cited_claim.c.lab_id)
        )
        edges = (await self.session.execute(edge_q)).all()

        if not edges:
            return []

        # Build adjacency list for union-find
        adjacency: dict[UUID, set[UUID]] = defaultdict(set)
        edge_counts: dict[tuple[UUID, UUID], int] = {}
        all_lab_ids: set[UUID] = set()

        for row in edges:
            from_lab = row.from_lab
            to_lab = row.to_lab
            adjacency[from_lab].add(to_lab)
            adjacency[to_lab].add(from_lab)
            all_lab_ids.add(from_lab)
            all_lab_ids.add(to_lab)
            key = tuple(sorted([str(from_lab), str(to_lab)]))
            normalized_key = (UUID(key[0]), UUID(key[1]))
            edge_counts[normalized_key] = edge_counts.get(normalized_key, 0) + row.edge_weight

        # Simple BFS-based connected components
        visited: set[UUID] = set()
        clusters: list[set[UUID]] = []

        for lab_id in all_lab_ids:
            if lab_id in visited:
                continue
            component: set[UUID] = set()
            queue = [lab_id]
            while queue:
                current = queue.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                for neighbor in adjacency.get(current, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)
            clusters.append(component)

        # Fetch lab slugs
        lab_slug_map: dict[UUID, str] = {}
        if all_lab_ids:
            slug_q = select(Lab.id, Lab.slug).where(Lab.id.in_(list(all_lab_ids)))
            slug_rows = (await self.session.execute(slug_q)).all()
            lab_slug_map = {row.id: row.slug for row in slug_rows}

        # Build result
        result = []
        for idx, component in enumerate(sorted(clusters, key=len, reverse=True)):
            lab_ids_list = sorted(str(lid) for lid in component)
            lab_slugs = [lab_slug_map.get(lid, "unknown") for lid in component]

            # Count edges within this cluster
            cluster_edges = 0
            for (a, b), weight in edge_counts.items():
                if a in component and b in component:
                    cluster_edges += weight

            result.append({
                "cluster_id": idx,
                "lab_ids": lab_ids_list,
                "lab_slugs": sorted(lab_slugs),
                "lab_count": len(component),
                "edge_count": cluster_edges,
            })

        logger.info("clusters_detected", cluster_count=len(result))
        return result

    # ------------------------------------------------------------------
    # Lab impact
    # ------------------------------------------------------------------

    async def get_lab_impact(self, slug: str) -> dict[str, Any]:
        """Compute impact metrics for a lab.

        Args:
            slug: Lab slug identifier.

        Returns:
            Dict containing:
                - lab_slug
                - total_claims: number of claims in the lab
                - verified_claims: number of verified claims
                - total_citations_received: citations to claims in this lab
                - cross_lab_citations_received: citations from other labs
                - total_citations_given: citations from claims in this lab
                - h_index: Hirsch index approximation
        """
        lab = await self.lab_repo.get_by_slug(slug)
        if lab is None:
            raise ValueError(f"Lab '{slug}' not found")

        lab_id = lab.id

        # Total claims in lab
        total_claims_q = (
            select(func.count())
            .select_from(Claim)
            .where(Claim.lab_id == lab_id)
        )
        total_claims = (await self.session.execute(total_claims_q)).scalar() or 0

        # Verified claims
        verified_q = (
            select(func.count())
            .select_from(Claim)
            .where(and_(Claim.lab_id == lab_id, Claim.verification_status == "verified"))
        )
        verified_claims = (await self.session.execute(verified_q)).scalar() or 0

        # Total citations received (where cited claim is in this lab)
        citations_received_q = (
            select(func.count())
            .select_from(Citation)
            .join(Claim, Citation.cited_claim_id == Claim.id)
            .where(Claim.lab_id == lab_id)
        )
        total_citations_received = (await self.session.execute(citations_received_q)).scalar() or 0

        # Cross-lab citations received
        cross_lab_q = (
            select(func.count())
            .select_from(Citation)
            .join(Claim, Citation.cited_claim_id == Claim.id)
            .where(
                and_(
                    Claim.lab_id == lab_id,
                    Citation.citing_claim_id.in_(
                        select(Claim.id).where(
                            and_(
                                Claim.lab_id.isnot(None),
                                Claim.lab_id != lab_id,
                            )
                        )
                    ),
                )
            )
        )
        cross_lab_citations = (await self.session.execute(cross_lab_q)).scalar() or 0

        # Citations given (from claims in this lab citing others)
        citations_given_q = (
            select(func.count())
            .select_from(Citation)
            .join(Claim, Citation.citing_claim_id == Claim.id)
            .where(Claim.lab_id == lab_id)
        )
        total_citations_given = (await self.session.execute(citations_given_q)).scalar() or 0

        # H-index: per-claim citation counts in the lab, then compute h
        per_claim_q = (
            select(
                Citation.cited_claim_id,
                func.count().label("cite_count"),
            )
            .join(Claim, Citation.cited_claim_id == Claim.id)
            .where(Claim.lab_id == lab_id)
            .group_by(Citation.cited_claim_id)
            .order_by(func.count().desc())
        )
        per_claim_rows = (await self.session.execute(per_claim_q)).all()
        citation_counts = sorted([row.cite_count for row in per_claim_rows], reverse=True)

        h_index = 0
        for i, count in enumerate(citation_counts, start=1):
            if count >= i:
                h_index = i
            else:
                break

        logger.info(
            "lab_impact_computed",
            slug=slug,
            total_claims=total_claims,
            citations_received=total_citations_received,
            h_index=h_index,
        )

        return {
            "lab_slug": slug,
            "lab_id": str(lab_id),
            "total_claims": total_claims,
            "verified_claims": verified_claims,
            "total_citations_received": total_citations_received,
            "cross_lab_citations_received": cross_lab_citations,
            "total_citations_given": total_citations_given,
            "h_index": h_index,
        }
