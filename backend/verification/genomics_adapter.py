"""Genomics verification: ClinVar + Ensembl VEP + MyVariant.info + GWAS Catalog.

Validates variant annotations, gene expression claims, and GWAS associations
using public genomics APIs.  API-based (no Docker).
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import httpx

from backend.logging_config import get_logger
from backend.verification.base import (
    VerificationAdapter,
    VerificationResult,
)

logger = get_logger(__name__)

NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ENSEMBL_REST = "https://rest.ensembl.org"
MYVARIANT_API = "https://myvariant.info/v1"
GWAS_CATALOG_API = "https://www.ebi.ac.uk/gwas/rest/api"
HTTP_TIMEOUT = 30

# Plausible ranges
MAX_MAF = 0.5  # allele frequency can't exceed 0.5 by definition
GENOME_WIDE_SIG = 5e-8


class GenomicsAdapter(VerificationAdapter):
    domain = "genomics"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        claim_type = task_result.get("claim_type", "variant_annotation")

        if claim_type == "variant_annotation":
            return await self._verify_variant_annotation(task_result)
        elif claim_type == "gene_expression":
            return await self._verify_gene_expression(task_result)
        elif claim_type == "gwas_association":
            return await self._verify_gwas_association(task_result)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    # ------------------------------------------------------------------
    # variant_annotation
    # ------------------------------------------------------------------

    async def _verify_variant_annotation(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        rsid = result.get("rsid", "")
        hgvs = result.get("hgvs", "")
        claimed_gene = result.get("gene", "")
        claimed_consequence = result.get("consequence", "")
        claimed_significance = result.get("clinical_significance", "")
        claimed_maf = result.get("maf")

        if not rsid and not hgvs:
            return VerificationResult.fail(self.domain, ["rsid or hgvs required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "variant_annotation"}

        variant_id = rsid or hgvs

        # Component 1: variant_exists (0.25)
        exists_result = await self._check_variant_exists(variant_id)
        component_scores["variant_exists"] = exists_result["score"]
        details["variant_exists"] = exists_result

        # Component 2: consequence_match (0.25)
        consequence_result = await self._check_consequence(variant_id, claimed_consequence)
        component_scores["consequence_match"] = consequence_result["score"]
        details["consequence_match"] = consequence_result

        # Component 3: gene_match (0.20)
        gene_result = await self._check_gene_match(variant_id, claimed_gene)
        component_scores["gene_match"] = gene_result["score"]
        details["gene_match"] = gene_result

        # Component 4: clinical_significance (0.15)
        clin_result = await self._check_clinical_significance(variant_id, claimed_significance)
        component_scores["clinical_significance"] = clin_result["score"]
        details["clinical_significance"] = clin_result

        # Component 5: population_frequency (0.15)
        freq_result = await self._check_population_frequency(variant_id, claimed_maf)
        component_scores["population_frequency"] = freq_result["score"]
        details["population_frequency"] = freq_result

        weights = {
            "variant_exists": 0.25,
            "consequence_match": 0.25,
            "gene_match": 0.20,
            "clinical_significance": 0.15,
            "population_frequency": 0.15,
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
    # gene_expression
    # ------------------------------------------------------------------

    async def _verify_gene_expression(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        gene = result.get("gene", "")
        dataset_accession = result.get("dataset_accession", "")
        fold_change = result.get("fold_change")
        p_value = result.get("p_value")

        if not gene:
            return VerificationResult.fail(self.domain, ["gene symbol required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "gene_expression"}

        # Component 1: gene_exists (0.20)
        gene_result = await self._check_gene_exists(gene)
        component_scores["gene_exists"] = gene_result["score"]
        details["gene_exists"] = gene_result

        # Component 2: dataset_exists (0.25)
        dataset_result = await self._check_dataset_exists(dataset_accession)
        component_scores["dataset_exists"] = dataset_result["score"]
        details["dataset_exists"] = dataset_result

        # Component 3: expression_range (0.25)
        expr_result = self._check_expression_range(fold_change)
        component_scores["expression_range"] = expr_result["score"]
        details["expression_range"] = expr_result

        # Component 4: statistics_valid (0.30)
        stats_result = await asyncio.to_thread(self._check_statistics, result)
        component_scores["statistics_valid"] = stats_result["score"]
        details["statistics_valid"] = stats_result

        weights = {
            "gene_exists": 0.20,
            "dataset_exists": 0.25,
            "expression_range": 0.25,
            "statistics_valid": 0.30,
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
    # gwas_association
    # ------------------------------------------------------------------

    async def _verify_gwas_association(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        rsid = result.get("rsid", "")
        claimed_pvalue = result.get("p_value")
        claimed_effect_size = result.get("effect_size")
        claimed_trait = result.get("trait", "")

        if not rsid:
            return VerificationResult.fail(self.domain, ["rsid required for GWAS claims"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "gwas_association"}

        # Component 1: variant_exists (0.20)
        exists_result = await self._check_variant_exists(rsid)
        component_scores["variant_exists"] = exists_result["score"]
        details["variant_exists"] = exists_result

        # Component 2: gwas_catalog_match (0.30)
        gwas_result = await self._check_gwas_catalog(rsid, claimed_trait)
        component_scores["gwas_catalog_match"] = gwas_result["score"]
        details["gwas_catalog_match"] = gwas_result

        # Component 3: pvalue_plausible (0.25)
        pval_result = self._check_pvalue_plausible(claimed_pvalue)
        component_scores["pvalue_plausible"] = pval_result["score"]
        details["pvalue_plausible"] = pval_result

        # Component 4: effect_size_plausible (0.25)
        effect_result = self._check_effect_size_plausible(claimed_effect_size)
        component_scores["effect_size_plausible"] = effect_result["score"]
        details["effect_size_plausible"] = effect_result

        weights = {
            "variant_exists": 0.20,
            "gwas_catalog_match": 0.30,
            "pvalue_plausible": 0.25,
            "effect_size_plausible": 0.25,
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
    # API helpers
    # ------------------------------------------------------------------

    async def _check_variant_exists(self, variant_id: str) -> dict:
        """Check if a variant (rsID or HGVS) exists in MyVariant.info."""
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{MYVARIANT_API}/variant/{variant_id}",
                    params={"fields": "dbsnp.rsid,clinvar.rcv.clinical_significance"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"score": 1.0, "found": True, "source": "myvariant"}
                # Try ClinVar via NCBI
                if variant_id.startswith("rs"):
                    resp2 = await client.get(
                        f"{NCBI_EUTILS}/esearch.fcgi",
                        params={"db": "snp", "term": variant_id, "retmode": "json"},
                    )
                    if resp2.status_code == 200:
                        data2 = resp2.json()
                        count = int(data2.get("esearchresult", {}).get("count", 0))
                        if count > 0:
                            return {"score": 1.0, "found": True, "source": "dbsnp"}
                return {"score": 0.0, "found": False}
        except Exception as e:
            logger.warning("variant_exists_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_consequence(self, variant_id: str, claimed: str) -> dict:
        """Compare claimed consequence vs Ensembl VEP."""
        if not claimed:
            return {"score": 0.5, "note": "No consequence claimed"}
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                # Try VEP for rsIDs
                if variant_id.startswith("rs"):
                    resp = await client.get(
                        f"{ENSEMBL_REST}/vep/human/id/{variant_id}",
                        headers={"Content-Type": "application/json"},
                    )
                else:
                    resp = await client.get(
                        f"{ENSEMBL_REST}/vep/human/hgvs/{variant_id}",
                        headers={"Content-Type": "application/json"},
                    )

                if resp.status_code != 200:
                    return {"score": 0.3, "note": f"VEP lookup failed (HTTP {resp.status_code})"}

                data = resp.json()
                if not data:
                    return {"score": 0.3, "note": "No VEP results"}

                # Collect all consequences
                consequences: set[str] = set()
                for entry in data:
                    for tc in entry.get("transcript_consequences", []):
                        for ct in tc.get("consequence_terms", []):
                            consequences.add(ct.lower().replace("_", " "))

                claimed_lower = claimed.lower().replace("_", " ")
                if claimed_lower in consequences:
                    return {"score": 1.0, "match": True, "vep_consequences": sorted(consequences)}

                # Partial match
                for c in consequences:
                    if claimed_lower in c or c in claimed_lower:
                        return {"score": 0.7, "partial_match": True, "vep_consequences": sorted(consequences)}

                return {"score": 0.0, "match": False, "claimed": claimed, "vep_consequences": sorted(consequences)}

        except Exception as e:
            logger.warning("consequence_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_gene_match(self, variant_id: str, claimed_gene: str) -> dict:
        """Check if variant maps to the claimed gene."""
        if not claimed_gene:
            return {"score": 0.5, "note": "No gene claimed"}
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{MYVARIANT_API}/variant/{variant_id}",
                    params={"fields": "dbsnp.gene.symbol,cadd.gene.genename"},
                )
                if resp.status_code != 200:
                    return {"score": 0.3, "note": "Gene lookup failed"}

                data = resp.json()
                genes: set[str] = set()

                # Extract gene symbols from various fields
                dbsnp_gene = data.get("dbsnp", {}).get("gene", {})
                if isinstance(dbsnp_gene, dict):
                    sym = dbsnp_gene.get("symbol", "")
                    if sym:
                        genes.add(sym.upper())
                elif isinstance(dbsnp_gene, list):
                    for g in dbsnp_gene:
                        sym = g.get("symbol", "") if isinstance(g, dict) else ""
                        if sym:
                            genes.add(sym.upper())

                cadd_gene = data.get("cadd", {}).get("gene", {})
                if isinstance(cadd_gene, dict):
                    gn = cadd_gene.get("genename", "")
                    if gn:
                        genes.add(gn.upper())

                if not genes:
                    return {"score": 0.5, "note": "No gene info in database"}

                if claimed_gene.upper() in genes:
                    return {"score": 1.0, "match": True, "db_genes": sorted(genes)}

                return {"score": 0.0, "match": False, "claimed": claimed_gene, "db_genes": sorted(genes)}

        except Exception as e:
            logger.warning("gene_match_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_clinical_significance(self, variant_id: str, claimed: str) -> dict:
        """Check claimed pathogenicity vs ClinVar."""
        if not claimed:
            return {"score": 0.5, "note": "No clinical significance claimed"}
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{MYVARIANT_API}/variant/{variant_id}",
                    params={"fields": "clinvar.rcv.clinical_significance"},
                )
                if resp.status_code != 200:
                    return {"score": 0.3, "note": "ClinVar lookup failed"}

                data = resp.json()
                clinvar = data.get("clinvar", {})
                rcv = clinvar.get("rcv", [])
                if isinstance(rcv, dict):
                    rcv = [rcv]

                significances: set[str] = set()
                for entry in rcv:
                    sig = entry.get("clinical_significance", "")
                    if sig:
                        significances.add(sig.lower())

                if not significances:
                    return {"score": 0.5, "note": "No ClinVar classification"}

                claimed_lower = claimed.lower()
                if claimed_lower in significances:
                    return {"score": 1.0, "match": True, "clinvar": sorted(significances)}

                # Partial match (e.g., "likely pathogenic" vs "pathogenic")
                for s in significances:
                    if claimed_lower in s or s in claimed_lower:
                        return {"score": 0.7, "partial_match": True, "clinvar": sorted(significances)}

                return {"score": 0.0, "match": False, "claimed": claimed, "clinvar": sorted(significances)}

        except Exception as e:
            logger.warning("clinical_significance_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_population_frequency(self, variant_id: str, claimed_maf: float | None) -> dict:
        """Compare claimed MAF vs gnomAD data from MyVariant.info."""
        if claimed_maf is None:
            return {"score": 0.5, "note": "No MAF claimed"}

        if not (0 <= claimed_maf <= MAX_MAF):
            return {"score": 0.0, "error": f"MAF {claimed_maf} out of range [0, {MAX_MAF}]"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{MYVARIANT_API}/variant/{variant_id}",
                    params={"fields": "gnomad_genome.af.af,dbsnp.alleles.freq"},
                )
                if resp.status_code != 200:
                    return {"score": 0.3, "note": "Frequency lookup failed"}

                data = resp.json()

                # Try gnomAD
                gnomad_af = data.get("gnomad_genome", {}).get("af", {}).get("af")
                if gnomad_af is not None:
                    tolerance = max(abs(gnomad_af) * 0.20, 0.01)
                    match = abs(claimed_maf - gnomad_af) <= tolerance
                    return {
                        "score": 1.0 if match else 0.3,
                        "match": match,
                        "claimed": claimed_maf,
                        "gnomad": gnomad_af,
                        "tolerance": tolerance,
                    }

                return {"score": 0.5, "note": "No frequency data available"}

        except Exception as e:
            logger.warning("frequency_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_gene_exists(self, gene: str) -> dict:
        """Check if gene symbol is valid in Ensembl."""
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{ENSEMBL_REST}/lookup/symbol/homo_sapiens/{gene}",
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "score": 1.0,
                        "found": True,
                        "ensembl_id": data.get("id", ""),
                        "biotype": data.get("biotype", ""),
                    }
                return {"score": 0.0, "found": False}
        except Exception as e:
            logger.warning("gene_exists_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_dataset_exists(self, accession: str) -> dict:
        """Check if GEO/ArrayExpress accession exists."""
        if not accession:
            return {"score": 0.5, "note": "No dataset accession provided"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                # GEO accession (GSE...)
                if accession.upper().startswith("GSE"):
                    resp = await client.get(
                        f"{NCBI_EUTILS}/esearch.fcgi",
                        params={"db": "gds", "term": accession, "retmode": "json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        count = int(data.get("esearchresult", {}).get("count", 0))
                        if count > 0:
                            return {"score": 1.0, "found": True, "source": "geo"}
                # ArrayExpress (E-MTAB-...)
                elif accession.upper().startswith("E-"):
                    resp = await client.get(
                        f"https://www.ebi.ac.uk/biostudies/api/v1/studies/{accession}",
                    )
                    if resp.status_code == 200:
                        return {"score": 1.0, "found": True, "source": "biostudies"}

                return {"score": 0.0, "found": False}
        except Exception as e:
            logger.warning("dataset_exists_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _check_expression_range(fold_change: float | None) -> dict:
        """Check if claimed fold change is biologically plausible."""
        if fold_change is None:
            return {"score": 0.5, "note": "No fold change claimed"}

        abs_fc = abs(fold_change)
        if abs_fc == 0:
            return {"score": 0.0, "error": "Fold change cannot be zero"}

        # Typical range: 0.1 to 100
        if 0.1 <= abs_fc <= 100:
            return {"score": 1.0, "plausible": True, "fold_change": fold_change}
        elif 0.01 <= abs_fc <= 1000:
            return {"score": 0.5, "plausible": "borderline", "fold_change": fold_change}
        else:
            return {"score": 0.0, "plausible": False, "fold_change": fold_change}

    @staticmethod
    def _check_statistics(result: dict) -> dict:
        """Re-run p-value calculation with scipy if data provided."""
        try:
            from scipy import stats as sp_stats
        except ImportError:
            return {"score": 0.5, "note": "scipy unavailable"}

        p_value = result.get("p_value")
        test_type = result.get("test_type", "")
        group1 = result.get("group1_data", [])
        group2 = result.get("group2_data", [])

        if p_value is None:
            return {"score": 0.5, "note": "No p-value claimed"}

        if not isinstance(p_value, (int, float)) or p_value < 0 or p_value > 1:
            return {"score": 0.0, "error": f"Invalid p-value: {p_value}"}

        # If raw data provided, re-compute
        if group1 and group2:
            try:
                if test_type == "mannwhitneyu":
                    _, recomputed_p = sp_stats.mannwhitneyu(group1, group2, alternative="two-sided")
                else:
                    _, recomputed_p = sp_stats.ttest_ind(group1, group2)

                tolerance = max(abs(recomputed_p) * 0.05, 1e-10)
                match = abs(p_value - recomputed_p) <= tolerance

                return {
                    "score": 1.0 if match else 0.3,
                    "match": match,
                    "claimed_p": p_value,
                    "recomputed_p": recomputed_p,
                }
            except Exception as e:
                return {"score": 0.3, "error": f"Re-computation failed: {e}"}

        # No raw data — just check plausibility
        return {"score": 0.5, "note": "No raw data for re-computation", "p_value": p_value}

    async def _check_gwas_catalog(self, rsid: str, claimed_trait: str) -> dict:
        """Cross-reference with NHGRI-EBI GWAS Catalog."""
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{GWAS_CATALOG_API}/singleNucleotidePolymorphisms/{rsid}/associations",
                )
                if resp.status_code != 200:
                    return {"score": 0.3, "note": f"GWAS Catalog lookup failed (HTTP {resp.status_code})"}

                data = resp.json()
                associations = data.get("_embedded", {}).get("associations", [])

                if not associations:
                    return {"score": 0.3, "note": "Not found in GWAS Catalog"}

                traits: list[str] = []
                for assoc in associations:
                    for ef in assoc.get("efoTraits", []):
                        traits.append(ef.get("trait", ""))

                if not claimed_trait:
                    return {"score": 0.7, "found_in_catalog": True, "n_associations": len(associations)}

                claimed_lower = claimed_trait.lower()
                for t in traits:
                    if claimed_lower in t.lower() or t.lower() in claimed_lower:
                        return {
                            "score": 1.0,
                            "trait_match": True,
                            "catalog_traits": traits[:10],
                            "n_associations": len(associations),
                        }

                return {
                    "score": 0.5,
                    "trait_match": False,
                    "claimed": claimed_trait,
                    "catalog_traits": traits[:10],
                }

        except Exception as e:
            logger.warning("gwas_catalog_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _check_pvalue_plausible(p_value: float | None) -> dict:
        """Check if GWAS p-value is in expected range."""
        if p_value is None:
            return {"score": 0.5, "note": "No p-value claimed"}

        if not isinstance(p_value, (int, float)):
            return {"score": 0.0, "error": "p-value must be numeric"}

        if p_value < 0 or p_value > 1:
            return {"score": 0.0, "error": f"p-value {p_value} out of range [0, 1]"}

        # For GWAS, genome-wide significance is typically 5e-8
        if p_value <= GENOME_WIDE_SIG:
            return {"score": 1.0, "genome_wide_significant": True, "p_value": p_value}
        elif p_value <= 1e-5:
            return {"score": 0.7, "suggestive_significance": True, "p_value": p_value}
        elif p_value <= 0.05:
            return {"score": 0.4, "nominally_significant": True, "p_value": p_value}
        else:
            return {"score": 0.2, "not_significant": True, "p_value": p_value}

    @staticmethod
    def _check_effect_size_plausible(effect_size: float | None) -> dict:
        """Check if GWAS effect size (beta or OR) is in reasonable range."""
        if effect_size is None:
            return {"score": 0.5, "note": "No effect size claimed"}

        if not isinstance(effect_size, (int, float)):
            return {"score": 0.0, "error": "Effect size must be numeric"}

        abs_effect = abs(effect_size)

        # For odds ratios (typically 0.5 - 5.0 for common variants)
        if effect_size > 0:
            if 0.5 <= abs_effect <= 5.0:
                return {"score": 1.0, "plausible": True, "effect_size": effect_size}
            elif 0.1 <= abs_effect <= 20.0:
                return {"score": 0.5, "plausible": "borderline", "effect_size": effect_size}
            else:
                return {"score": 0.1, "plausible": False, "effect_size": effect_size}

        # For betas (typically -2 to 2 for common variants)
        if abs_effect <= 2.0:
            return {"score": 1.0, "plausible": True, "effect_size": effect_size}
        elif abs_effect <= 10.0:
            return {"score": 0.5, "plausible": "borderline", "effect_size": effect_size}
        else:
            return {"score": 0.1, "plausible": False, "effect_size": effect_size}
