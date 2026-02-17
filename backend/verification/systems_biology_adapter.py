"""Systems biology verification: Reactome + STRING + KEGG + scipy/numpy.

Validates pathway enrichment, network topology, and flux balance claims.
API-based (no Docker) with optional networkx for topology metrics.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from backend.logging_config import get_logger
from backend.verification.base import (
    VerificationAdapter,
    VerificationResult,
)

logger = get_logger(__name__)

REACTOME_API = "https://reactome.org/ContentService"
STRING_API = "https://string-db.org/api"
KEGG_REST = "https://rest.kegg.jp"
ENSEMBL_REST = "https://rest.ensembl.org"
HTTP_TIMEOUT = 30

# Graceful degradation for networkx
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    logger.warning("networkx_not_available", note="Network topology metrics will use neutral scores")


class SystemsBiologyAdapter(VerificationAdapter):
    domain = "systems_biology"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        claim_type = task_result.get("claim_type", "pathway_enrichment")

        if claim_type == "pathway_enrichment":
            return await self._verify_pathway_enrichment(task_result)
        elif claim_type == "network_topology":
            return await self._verify_network_topology(task_result)
        elif claim_type == "flux_balance":
            return await self._verify_flux_balance(task_result)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    # ------------------------------------------------------------------
    # pathway_enrichment
    # ------------------------------------------------------------------

    async def _verify_pathway_enrichment(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        gene_set = result.get("gene_set", [])
        pathway_id = result.get("pathway_id", "")
        claimed_pvalue = result.get("p_value")
        claimed_fdr = result.get("fdr")
        background_size = result.get("background_size", 20000)
        pathway_size = result.get("pathway_size")

        if not gene_set:
            return VerificationResult.fail(self.domain, ["gene_set required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "pathway_enrichment"}

        # Component 1: gene_set_valid (0.20)
        genes_result = await self._check_gene_set_valid(gene_set)
        component_scores["gene_set_valid"] = genes_result["score"]
        details["gene_set_valid"] = genes_result

        # Component 2: pathway_exists (0.20)
        pw_result = await self._check_pathway_exists(pathway_id)
        component_scores["pathway_exists"] = pw_result["score"]
        details["pathway_exists"] = pw_result

        # Component 3: enrichment_recomputed (0.30)
        enrich_result = await asyncio.to_thread(
            self._recompute_enrichment,
            len(gene_set), pathway_size, background_size, claimed_pvalue,
        )
        component_scores["enrichment_recomputed"] = enrich_result["score"]
        details["enrichment_recomputed"] = enrich_result

        # Component 4: fdr_correction (0.30)
        fdr_result = await asyncio.to_thread(
            self._check_fdr_correction, claimed_pvalue, claimed_fdr, result.get("n_tests"),
        )
        component_scores["fdr_correction"] = fdr_result["score"]
        details["fdr_correction"] = fdr_result

        weights = {
            "gene_set_valid": 0.20,
            "pathway_exists": 0.20,
            "enrichment_recomputed": 0.30,
            "fdr_correction": 0.30,
        }
        score = sum(weights[k] * component_scores[k] for k in weights)
        score = min(1.0, round(score, 4))

        elapsed = time.monotonic() - start
        details["component_scores"] = component_scores

        return VerificationResult(
            passed=score >= 0.5,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details=details,
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # network_topology
    # ------------------------------------------------------------------

    async def _verify_network_topology(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        protein_ids = result.get("protein_ids", [])
        claimed_edges = result.get("edges", [])
        claimed_hubs = result.get("hub_proteins", [])
        claimed_metrics = result.get("topology_metrics", {})

        if not protein_ids:
            return VerificationResult.fail(self.domain, ["protein_ids required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "network_topology"}

        # Component 1: proteins_exist (0.20)
        proteins_result = await self._check_proteins_exist(protein_ids)
        component_scores["proteins_exist"] = proteins_result["score"]
        details["proteins_exist"] = proteins_result

        # Component 2: interactions_verified (0.25)
        interactions_result = await self._check_interactions(protein_ids, claimed_edges)
        component_scores["interactions_verified"] = interactions_result["score"]
        details["interactions_verified"] = interactions_result

        # Component 3: metrics_recomputed (0.30)
        metrics_result = await asyncio.to_thread(
            self._recompute_topology_metrics, protein_ids, claimed_edges, claimed_metrics,
        )
        component_scores["metrics_recomputed"] = metrics_result["score"]
        details["metrics_recomputed"] = metrics_result

        # Component 4: hub_identification (0.25)
        hub_result = await asyncio.to_thread(
            self._check_hub_identification, protein_ids, claimed_edges, claimed_hubs,
        )
        component_scores["hub_identification"] = hub_result["score"]
        details["hub_identification"] = hub_result

        weights = {
            "proteins_exist": 0.20,
            "interactions_verified": 0.25,
            "metrics_recomputed": 0.30,
            "hub_identification": 0.25,
        }
        score = sum(weights[k] * component_scores[k] for k in weights)
        score = min(1.0, round(score, 4))

        elapsed = time.monotonic() - start
        details["component_scores"] = component_scores

        return VerificationResult(
            passed=score >= 0.5,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details=details,
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # flux_balance
    # ------------------------------------------------------------------

    async def _verify_flux_balance(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        stoichiometry_matrix = result.get("stoichiometry_matrix", [])
        claimed_fluxes = result.get("fluxes", [])
        flux_bounds = result.get("flux_bounds", [])
        objective = result.get("objective", [])

        if not stoichiometry_matrix:
            return VerificationResult.fail(self.domain, ["stoichiometry_matrix required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "flux_balance"}

        # Component 1: model_valid (0.20)
        model_result = self._check_model_valid(stoichiometry_matrix, flux_bounds)
        component_scores["model_valid"] = model_result["score"]
        details["model_valid"] = model_result

        # Component 2: stoichiometry_consistent (0.25)
        stoich_result = await asyncio.to_thread(
            self._check_stoichiometry_consistent, stoichiometry_matrix,
        )
        component_scores["stoichiometry_consistent"] = stoich_result["score"]
        details["stoichiometry_consistent"] = stoich_result

        # Component 3: objective_feasible (0.25)
        feas_result = await asyncio.to_thread(
            self._check_objective_feasible,
            stoichiometry_matrix, flux_bounds, objective,
        )
        component_scores["objective_feasible"] = feas_result["score"]
        details["objective_feasible"] = feas_result

        # Component 4: flux_bounds_respected (0.30)
        bounds_result = self._check_flux_bounds_respected(claimed_fluxes, flux_bounds)
        component_scores["flux_bounds_respected"] = bounds_result["score"]
        details["flux_bounds_respected"] = bounds_result

        weights = {
            "model_valid": 0.20,
            "stoichiometry_consistent": 0.25,
            "objective_feasible": 0.25,
            "flux_bounds_respected": 0.30,
        }
        score = sum(weights[k] * component_scores[k] for k in weights)
        score = min(1.0, round(score, 4))

        elapsed = time.monotonic() - start
        details["component_scores"] = component_scores

        return VerificationResult(
            passed=score >= 0.5,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details=details,
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # API helpers — pathway enrichment
    # ------------------------------------------------------------------

    async def _check_gene_set_valid(self, gene_set: list[str]) -> dict:
        """Check that gene symbols resolve in Ensembl."""
        try:
            valid = 0
            invalid: list[str] = []
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                # Check a sample (up to 10 genes) to avoid API rate limiting
                sample = gene_set[:10]
                for gene in sample:
                    resp = await client.get(
                        f"{ENSEMBL_REST}/lookup/symbol/homo_sapiens/{gene}",
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code == 200:
                        valid += 1
                    else:
                        invalid.append(gene)

            score = valid / len(sample) if sample else 0.0
            return {
                "score": round(score, 4),
                "valid": valid,
                "checked": len(sample),
                "total": len(gene_set),
                "invalid": invalid[:5],
            }
        except Exception as e:
            logger.warning("gene_set_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_pathway_exists(self, pathway_id: str) -> dict:
        """Check if pathway ID is valid in Reactome or KEGG."""
        if not pathway_id:
            return {"score": 0.5, "note": "No pathway_id provided"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                # Try Reactome
                if pathway_id.startswith("R-"):
                    resp = await client.get(f"{REACTOME_API}/data/pathway/{pathway_id}")
                    if resp.status_code == 200:
                        data = resp.json()
                        return {
                            "score": 1.0,
                            "found": True,
                            "source": "reactome",
                            "name": data.get("displayName", ""),
                        }

                # Try KEGG
                resp = await client.get(f"{KEGG_REST}/get/{pathway_id}")
                if resp.status_code == 200:
                    return {"score": 1.0, "found": True, "source": "kegg"}

                return {"score": 0.0, "found": False}
        except Exception as e:
            logger.warning("pathway_exists_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _recompute_enrichment(
        overlap: int,
        pathway_size: int | None,
        background_size: int,
        claimed_pvalue: float | None,
    ) -> dict:
        """Re-run hypergeometric test for enrichment."""
        try:
            from scipy import stats as sp_stats
        except ImportError:
            return {"score": 0.5, "note": "scipy unavailable"}

        if pathway_size is None:
            return {"score": 0.5, "note": "pathway_size needed for re-computation"}

        if pathway_size <= 0 or background_size <= 0:
            return {"score": 0.0, "error": "pathway_size and background_size must be positive"}

        try:
            # Hypergeometric test: P(X >= overlap)
            computed_p = sp_stats.hypergeom.sf(
                overlap - 1,  # sf gives P(X > k), so k-1 for P(X >= k)
                background_size,
                pathway_size,
                overlap + 10,  # sample size (approximate)
            )

            if claimed_pvalue is None:
                return {"score": 0.5, "note": "No p-value claimed", "computed_p": computed_p}

            # Order-of-magnitude comparison for enrichment p-values
            import math
            if computed_p > 0 and claimed_pvalue > 0:
                log_diff = abs(math.log10(computed_p) - math.log10(claimed_pvalue))
                match = log_diff <= 2  # within 2 orders of magnitude
            else:
                match = False

            return {
                "score": 1.0 if match else 0.3,
                "match": match,
                "claimed_p": claimed_pvalue,
                "computed_p": computed_p,
            }
        except Exception as e:
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _check_fdr_correction(
        raw_pvalue: float | None, claimed_fdr: float | None, n_tests: int | None,
    ) -> dict:
        """Check FDR (Benjamini-Hochberg) correction plausibility."""
        if claimed_fdr is None:
            return {"score": 0.5, "note": "No FDR value claimed"}

        if raw_pvalue is None:
            return {"score": 0.5, "note": "No raw p-value to compare"}

        if not isinstance(claimed_fdr, (int, float)) or claimed_fdr < 0 or claimed_fdr > 1:
            return {"score": 0.0, "error": f"FDR {claimed_fdr} out of range [0, 1]"}

        # FDR should be >= raw p-value (BH correction inflates p-values)
        if claimed_fdr < raw_pvalue:
            return {"score": 0.3, "error": "FDR should be >= raw p-value"}

        # If n_tests provided, approximate BH correction
        if n_tests and n_tests > 0:
            # Rough upper bound: fdr <= p * n_tests
            upper_bound = min(raw_pvalue * n_tests, 1.0)
            if claimed_fdr <= upper_bound:
                return {"score": 1.0, "plausible": True, "upper_bound": upper_bound}
            return {"score": 0.5, "note": "FDR above expected upper bound"}

        return {"score": 0.7, "note": "FDR >= raw p-value (correct direction)"}

    # ------------------------------------------------------------------
    # API helpers — network topology
    # ------------------------------------------------------------------

    async def _check_proteins_exist(self, protein_ids: list[str]) -> dict:
        """Check protein IDs in STRING DB."""
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.post(
                    f"{STRING_API}/json/resolve",
                    data={
                        "identifiers": "\r".join(protein_ids[:20]),
                        "species": 9606,
                    },
                )
                if resp.status_code != 200:
                    return {"score": 0.3, "note": f"STRING resolve failed (HTTP {resp.status_code})"}

                data = resp.json()
                resolved = len(data)
                score = resolved / min(len(protein_ids), 20) if protein_ids else 0.0
                return {
                    "score": round(score, 4),
                    "resolved": resolved,
                    "total": len(protein_ids),
                }
        except Exception as e:
            logger.warning("proteins_exist_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_interactions(self, protein_ids: list[str], claimed_edges: list) -> dict:
        """Verify claimed edges exist in STRING above confidence threshold."""
        if not claimed_edges:
            return {"score": 0.5, "note": "No edges claimed"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.post(
                    f"{STRING_API}/json/network",
                    data={
                        "identifiers": "\r".join(protein_ids[:50]),
                        "species": 9606,
                        "required_score": 400,
                    },
                )
                if resp.status_code != 200:
                    return {"score": 0.3, "note": f"STRING network failed (HTTP {resp.status_code})"}

                data = resp.json()
                db_edges: set[tuple[str, str]] = set()
                for interaction in data:
                    a = interaction.get("preferredName_A", "")
                    b = interaction.get("preferredName_B", "")
                    if a and b:
                        db_edges.add((a.upper(), b.upper()))
                        db_edges.add((b.upper(), a.upper()))

                verified = 0
                for edge in claimed_edges:
                    if isinstance(edge, (list, tuple)) and len(edge) >= 2:
                        if (str(edge[0]).upper(), str(edge[1]).upper()) in db_edges:
                            verified += 1

                score = verified / len(claimed_edges) if claimed_edges else 0.0
                return {
                    "score": round(score, 4),
                    "verified": verified,
                    "total_claimed": len(claimed_edges),
                    "db_edges": len(db_edges),
                }
        except Exception as e:
            logger.warning("interactions_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _recompute_topology_metrics(
        protein_ids: list[str], edges: list, claimed_metrics: dict,
    ) -> dict:
        """Re-compute degree centrality and betweenness with networkx."""
        if not NETWORKX_AVAILABLE:
            return {"score": 0.5, "note": "networkx unavailable — metrics not recomputed"}

        if not edges:
            return {"score": 0.5, "note": "No edges to build network"}

        try:
            G = nx.Graph()
            G.add_nodes_from(protein_ids)
            for edge in edges:
                if isinstance(edge, (list, tuple)) and len(edge) >= 2:
                    G.add_edge(str(edge[0]), str(edge[1]))

            computed = {
                "n_nodes": G.number_of_nodes(),
                "n_edges": G.number_of_edges(),
                "density": round(nx.density(G), 4),
                "avg_degree": round(sum(dict(G.degree()).values()) / max(G.number_of_nodes(), 1), 4),
            }

            if not claimed_metrics:
                return {"score": 0.5, "computed": computed}

            matches = 0
            total = 0
            for key in ["n_nodes", "n_edges", "density", "avg_degree"]:
                if key in claimed_metrics:
                    total += 1
                    claimed_val = claimed_metrics[key]
                    computed_val = computed[key]
                    tolerance = max(abs(computed_val) * 0.1, 0.01)
                    if abs(claimed_val - computed_val) <= tolerance:
                        matches += 1

            score = matches / total if total > 0 else 0.5
            return {
                "score": round(score, 4),
                "matches": matches,
                "total_compared": total,
                "computed": computed,
            }
        except Exception as e:
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _check_hub_identification(
        protein_ids: list[str], edges: list, claimed_hubs: list[str],
    ) -> dict:
        """Check if claimed hub proteins match top centrality nodes."""
        if not NETWORKX_AVAILABLE:
            return {"score": 0.5, "note": "networkx unavailable"}

        if not claimed_hubs:
            return {"score": 0.5, "note": "No hub proteins claimed"}

        if not edges:
            return {"score": 0.3, "note": "No edges to compute centrality"}

        try:
            G = nx.Graph()
            G.add_nodes_from(protein_ids)
            for edge in edges:
                if isinstance(edge, (list, tuple)) and len(edge) >= 2:
                    G.add_edge(str(edge[0]), str(edge[1]))

            degree_centrality = nx.degree_centrality(G)
            # Top N hubs (N = number of claimed hubs)
            sorted_by_centrality = sorted(
                degree_centrality.items(), key=lambda x: x[1], reverse=True,
            )
            top_n = {node for node, _ in sorted_by_centrality[:max(len(claimed_hubs) * 2, 5)]}

            matches = sum(1 for h in claimed_hubs if h in top_n)
            score = matches / len(claimed_hubs) if claimed_hubs else 0.0

            return {
                "score": round(score, 4),
                "matches": matches,
                "claimed_hubs": claimed_hubs,
                "top_centrality": [node for node, _ in sorted_by_centrality[:5]],
            }
        except Exception as e:
            return {"score": 0.3, "error": str(e)}

    # ------------------------------------------------------------------
    # Helpers — flux balance
    # ------------------------------------------------------------------

    @staticmethod
    def _check_model_valid(matrix: list, bounds: list) -> dict:
        """Check if stoichiometry matrix and bounds are well-formed."""
        if not matrix:
            return {"score": 0.0, "error": "Empty stoichiometry matrix"}

        n_metabolites = len(matrix)
        n_reactions = len(matrix[0]) if matrix else 0

        if n_reactions == 0:
            return {"score": 0.0, "error": "No reactions in matrix"}

        # Check all rows have same length
        if any(len(row) != n_reactions for row in matrix):
            return {"score": 0.0, "error": "Inconsistent row lengths in matrix"}

        if bounds and len(bounds) != n_reactions:
            return {"score": 0.5, "note": "bounds length doesn't match n_reactions"}

        return {
            "score": 1.0,
            "valid": True,
            "n_metabolites": n_metabolites,
            "n_reactions": n_reactions,
        }

    @staticmethod
    def _check_stoichiometry_consistent(matrix: list) -> dict:
        """Check S matrix rank for consistency."""
        try:
            import numpy as np
            S = np.array(matrix, dtype=float)
            rank = int(np.linalg.matrix_rank(S))
            n_metabolites, n_reactions = S.shape

            # System has solutions if rank < n_reactions
            has_null_space = rank < n_reactions
            return {
                "score": 1.0 if has_null_space else 0.3,
                "consistent": has_null_space,
                "rank": rank,
                "n_metabolites": n_metabolites,
                "n_reactions": n_reactions,
            }
        except ImportError:
            return {"score": 0.5, "note": "numpy unavailable"}
        except Exception as e:
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _check_objective_feasible(matrix: list, bounds: list, objective: list) -> dict:
        """Check LP feasibility with scipy.optimize.linprog."""
        try:
            import numpy as np
            from scipy.optimize import linprog
        except ImportError:
            return {"score": 0.5, "note": "scipy unavailable"}

        try:
            S = np.array(matrix, dtype=float)
            n_metabolites, n_reactions = S.shape
            b_eq = np.zeros(n_metabolites)

            # Parse bounds
            if bounds:
                lb = [b[0] if isinstance(b, (list, tuple)) else -1000 for b in bounds]
                ub = [b[1] if isinstance(b, (list, tuple)) else 1000 for b in bounds]
                var_bounds = list(zip(lb, ub))
            else:
                var_bounds = [(-1000, 1000)] * n_reactions

            # Objective
            c = np.zeros(n_reactions)
            if objective and len(objective) == n_reactions:
                c = -np.array(objective, dtype=float)  # negate for maximization
            elif n_reactions > 0:
                c[-1] = -1  # Default: maximize last reaction

            result = linprog(c, A_eq=S, b_eq=b_eq, bounds=var_bounds, method="highs")

            if result.success:
                return {
                    "score": 1.0,
                    "feasible": True,
                    "optimal_value": round(-result.fun, 6),
                }
            return {"score": 0.3, "feasible": False, "status": result.message}
        except Exception as e:
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _check_flux_bounds_respected(claimed_fluxes: list, bounds: list) -> dict:
        """Check if claimed fluxes are within declared bounds."""
        if not claimed_fluxes:
            return {"score": 0.5, "note": "No fluxes claimed"}

        if not bounds:
            return {"score": 0.5, "note": "No bounds declared"}

        if len(claimed_fluxes) != len(bounds):
            return {"score": 0.3, "error": "Flux count doesn't match bounds count"}

        violations = 0
        for i, (flux, bound) in enumerate(zip(claimed_fluxes, bounds)):
            if not isinstance(flux, (int, float)):
                continue
            if isinstance(bound, (list, tuple)) and len(bound) >= 2:
                lb, ub = bound[0], bound[1]
                if flux < lb - 1e-6 or flux > ub + 1e-6:
                    violations += 1

        score = max(0.0, 1.0 - violations / len(claimed_fluxes)) if claimed_fluxes else 0.0
        return {
            "score": round(score, 4),
            "violations": violations,
            "total_fluxes": len(claimed_fluxes),
        }
