"""Immunoinformatics verification: IEDB API + UniProt + IMGT/HLA.

Validates epitope predictions, MHC binding affinity, and B-cell epitope
claims using public immunology APIs.  API-based (no Docker).
"""
from __future__ import annotations

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

IEDB_API = "http://tools-cluster-interface.iedb.org/tools_api"
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
ENSEMBL_REST = "https://rest.ensembl.org"
HTTP_TIMEOUT = 60  # IEDB can be slow

VALID_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")

# MHC-I typically binds 8-11mer, MHC-II 13-25mer
MHC_I_LENGTH = (8, 11)
MHC_II_LENGTH = (13, 25)

# IC50 binding thresholds (nM)
STRONG_BINDER_THRESHOLD = 50
WEAK_BINDER_THRESHOLD = 500


class ImmunoinformaticsAdapter(VerificationAdapter):
    domain = "immunoinformatics"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        claim_type = task_result.get("claim_type", "epitope_prediction")

        if claim_type == "epitope_prediction":
            return await self._verify_epitope_prediction(task_result)
        elif claim_type == "mhc_binding":
            return await self._verify_mhc_binding(task_result)
        elif claim_type == "bcell_epitope":
            return await self._verify_bcell_epitope(task_result)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    # ------------------------------------------------------------------
    # epitope_prediction
    # ------------------------------------------------------------------

    async def _verify_epitope_prediction(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        peptide = result.get("peptide", "")
        source_protein = result.get("source_protein", "")
        hla_allele = result.get("hla_allele", "")
        claimed_score = result.get("prediction_score")

        if not peptide:
            return VerificationResult.fail(self.domain, ["peptide sequence required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "epitope_prediction"}

        # Component 1: peptide_valid (0.15)
        pep_result = self._check_peptide_valid(peptide, min_len=8, max_len=15)
        component_scores["peptide_valid"] = pep_result["score"]
        details["peptide_valid"] = pep_result

        # Component 2: source_protein_valid (0.20)
        prot_result = await self._check_protein_valid(source_protein)
        component_scores["source_protein_valid"] = prot_result["score"]
        details["source_protein_valid"] = prot_result

        # Component 3: peptide_in_source (0.20)
        in_source_result = await self._check_peptide_in_source(peptide, source_protein)
        component_scores["peptide_in_source"] = in_source_result["score"]
        details["peptide_in_source"] = in_source_result

        # Component 4: iedb_score_check (0.25)
        iedb_result = await self._check_iedb_score(peptide, hla_allele, claimed_score)
        component_scores["iedb_score_check"] = iedb_result["score"]
        details["iedb_score_check"] = iedb_result

        # Component 5: allele_valid (0.20)
        allele_result = self._check_allele_valid(hla_allele)
        component_scores["allele_valid"] = allele_result["score"]
        details["allele_valid"] = allele_result

        weights = {
            "peptide_valid": 0.15,
            "source_protein_valid": 0.20,
            "peptide_in_source": 0.20,
            "iedb_score_check": 0.25,
            "allele_valid": 0.20,
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
    # mhc_binding
    # ------------------------------------------------------------------

    async def _verify_mhc_binding(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        peptide = result.get("peptide", "")
        hla_allele = result.get("hla_allele", "")
        mhc_class = result.get("mhc_class", "I")
        claimed_ic50 = result.get("binding_affinity")
        claimed_classification = result.get("classification", "")

        if not peptide:
            return VerificationResult.fail(self.domain, ["peptide sequence required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "mhc_binding"}

        # Component 1: allele_valid (0.20)
        allele_result = self._check_allele_valid(hla_allele)
        component_scores["allele_valid"] = allele_result["score"]
        details["allele_valid"] = allele_result

        # Component 2: peptide_length_valid (0.15)
        length_range = MHC_I_LENGTH if mhc_class.upper() in ("I", "1") else MHC_II_LENGTH
        length_result = self._check_peptide_valid(peptide, min_len=length_range[0], max_len=length_range[1])
        component_scores["peptide_length_valid"] = length_result["score"]
        details["peptide_length_valid"] = length_result

        # Component 3: binding_affinity_recomputed (0.35)
        binding_result = await self._check_binding_affinity(
            peptide, hla_allele, mhc_class, claimed_ic50,
        )
        component_scores["binding_affinity_recomputed"] = binding_result["score"]
        details["binding_affinity_recomputed"] = binding_result

        # Component 4: classification_consistent (0.30)
        class_result = self._check_classification_consistent(
            claimed_ic50, claimed_classification,
        )
        component_scores["classification_consistent"] = class_result["score"]
        details["classification_consistent"] = class_result

        weights = {
            "allele_valid": 0.20,
            "peptide_length_valid": 0.15,
            "binding_affinity_recomputed": 0.35,
            "classification_consistent": 0.30,
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
    # bcell_epitope
    # ------------------------------------------------------------------

    async def _verify_bcell_epitope(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        sequence = result.get("sequence", "")
        source_protein = result.get("source_protein", "")
        claimed_accessibility = result.get("surface_accessibility")

        if not sequence:
            return VerificationResult.fail(self.domain, ["sequence required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "bcell_epitope"}

        # Component 1: sequence_valid (0.15)
        seq_result = self._check_peptide_valid(sequence, min_len=5, max_len=50)
        component_scores["sequence_valid"] = seq_result["score"]
        details["sequence_valid"] = seq_result

        # Component 2: source_protein_valid (0.20)
        prot_result = await self._check_protein_valid(source_protein)
        component_scores["source_protein_valid"] = prot_result["score"]
        details["source_protein_valid"] = prot_result

        # Component 3: surface_accessibility (0.25)
        acc_result = self._check_surface_accessibility(sequence, claimed_accessibility)
        component_scores["surface_accessibility"] = acc_result["score"]
        details["surface_accessibility"] = acc_result

        # Component 4: iedb_bcell_check (0.25)
        bcell_result = await self._check_iedb_bcell(sequence)
        component_scores["iedb_bcell_check"] = bcell_result["score"]
        details["iedb_bcell_check"] = bcell_result

        # Component 5: conservation_check (0.15)
        conserv_result = await self._check_conservation(sequence, source_protein)
        component_scores["conservation_check"] = conserv_result["score"]
        details["conservation_check"] = conserv_result

        weights = {
            "sequence_valid": 0.15,
            "source_protein_valid": 0.20,
            "surface_accessibility": 0.25,
            "iedb_bcell_check": 0.25,
            "conservation_check": 0.15,
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
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_peptide_valid(peptide: str, min_len: int = 8, max_len: int = 15) -> dict:
        """Validate peptide sequence (standard amino acids, length)."""
        if not peptide:
            return {"score": 0.0, "error": "Empty peptide"}

        upper = peptide.upper()
        invalid = [aa for aa in upper if aa not in VALID_AMINO_ACIDS]

        if invalid:
            return {
                "score": 0.0,
                "error": f"Invalid amino acids: {''.join(set(invalid))}",
                "length": len(upper),
            }

        if len(upper) < min_len or len(upper) > max_len:
            return {
                "score": 0.3,
                "note": f"Length {len(upper)} outside [{min_len}, {max_len}]",
                "length": len(upper),
            }

        return {"score": 1.0, "valid": True, "length": len(upper)}

    async def _check_protein_valid(self, protein_id: str) -> dict:
        """Check if protein exists in UniProt."""
        if not protein_id:
            return {"score": 0.5, "note": "No source protein provided"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{UNIPROT_BASE}/{protein_id}",
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "score": 1.0,
                        "found": True,
                        "protein_name": data.get("proteinDescription", {})
                            .get("recommendedName", {}).get("fullName", {}).get("value", ""),
                        "organism": data.get("organism", {}).get("scientificName", ""),
                    }
                return {"score": 0.0, "found": False}
        except Exception as e:
            logger.warning("protein_valid_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_peptide_in_source(self, peptide: str, protein_id: str) -> dict:
        """Check if peptide is a substring of the source protein."""
        if not protein_id:
            return {"score": 0.5, "note": "No source protein to check"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{UNIPROT_BASE}/{protein_id}.fasta",
                )
                if resp.status_code != 200:
                    return {"score": 0.3, "note": "Could not fetch protein sequence"}

                fasta_lines = resp.text.strip().split("\n")
                protein_seq = "".join(line for line in fasta_lines if not line.startswith(">"))

                if peptide.upper() in protein_seq.upper():
                    return {"score": 1.0, "found": True}
                return {"score": 0.0, "found": False}
        except Exception as e:
            logger.warning("peptide_in_source_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _check_allele_valid(hla_allele: str) -> dict:
        """Validate HLA allele format."""
        if not hla_allele:
            return {"score": 0.5, "note": "No HLA allele provided"}

        # Standard HLA nomenclature: HLA-A*02:01, HLA-B*07:02, etc.
        pattern = r"^HLA-[A-Z]+\d?\*\d{2,4}:\d{2,4}$"
        if re.match(pattern, hla_allele):
            return {"score": 1.0, "valid": True, "allele": hla_allele}

        # Relaxed format: A*02:01, B0702
        relaxed = r"^[A-Z]+\d?\*?\d{2,4}:?\d{2,4}$"
        if re.match(relaxed, hla_allele):
            return {"score": 0.7, "valid": True, "note": "Non-standard format", "allele": hla_allele}

        return {"score": 0.0, "valid": False, "allele": hla_allele}

    async def _check_iedb_score(
        self, peptide: str, hla_allele: str, claimed_score: float | None,
    ) -> dict:
        """Run IEDB MHC-I prediction and compare score."""
        if not hla_allele:
            return {"score": 0.5, "note": "No allele for IEDB prediction"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.post(
                    f"{IEDB_API}/mhci/",
                    data={
                        "method": "recommended",
                        "sequence_text": peptide,
                        "allele": hla_allele,
                        "length": str(len(peptide)),
                    },
                )
                if resp.status_code != 200:
                    return {"score": 0.3, "note": f"IEDB API failed (HTTP {resp.status_code})"}

                text = resp.text.strip()
                if not text or "error" in text.lower():
                    return {"score": 0.3, "note": "IEDB returned error or empty"}

                # Parse tab-delimited results
                lines = text.strip().split("\n")
                if len(lines) < 2:
                    return {"score": 0.5, "note": "No prediction results"}

                # Last column is typically the score/IC50
                header = lines[0].split("\t")
                data_line = lines[-1].split("\t")

                if claimed_score is None:
                    return {"score": 0.5, "note": "No score claimed", "iedb_available": True}

                # Try to extract IC50 value
                try:
                    iedb_score = float(data_line[-1])
                    tolerance = max(abs(iedb_score) * 0.2, 1.0)
                    match = abs(claimed_score - iedb_score) <= tolerance
                    return {
                        "score": 1.0 if match else 0.3,
                        "match": match,
                        "claimed": claimed_score,
                        "iedb": iedb_score,
                    }
                except (ValueError, IndexError):
                    return {"score": 0.5, "note": "Could not parse IEDB score"}

        except Exception as e:
            logger.warning("iedb_score_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _check_classification_consistent(
        ic50: float | None, classification: str,
    ) -> dict:
        """Check if binder classification matches IC50 thresholds."""
        if not classification or ic50 is None:
            return {"score": 0.5, "note": "Classification or IC50 missing"}

        classification_lower = classification.lower()

        if "strong" in classification_lower:
            expected = ic50 <= STRONG_BINDER_THRESHOLD
        elif "weak" in classification_lower:
            expected = STRONG_BINDER_THRESHOLD < ic50 <= WEAK_BINDER_THRESHOLD
        elif "non" in classification_lower or "no" in classification_lower:
            expected = ic50 > WEAK_BINDER_THRESHOLD
        else:
            return {"score": 0.5, "note": f"Unknown classification: {classification}"}

        return {
            "score": 1.0 if expected else 0.0,
            "consistent": expected,
            "ic50": ic50,
            "classification": classification,
            "thresholds": {
                "strong": STRONG_BINDER_THRESHOLD,
                "weak": WEAK_BINDER_THRESHOLD,
            },
        }

    async def _check_binding_affinity(
        self, peptide: str, hla_allele: str, mhc_class: str, claimed_ic50: float | None,
    ) -> dict:
        """Re-run IEDB prediction for binding affinity."""
        if not hla_allele:
            return {"score": 0.5, "note": "No allele for binding prediction"}

        endpoint = "mhci" if mhc_class.upper() in ("I", "1") else "mhcii"

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                data = {
                    "method": "recommended",
                    "sequence_text": peptide,
                    "allele": hla_allele,
                    "length": str(len(peptide)),
                }
                resp = await client.post(f"{IEDB_API}/{endpoint}/", data=data)

                if resp.status_code != 200:
                    return {"score": 0.3, "note": f"IEDB binding API failed (HTTP {resp.status_code})"}

                text = resp.text.strip()
                lines = text.strip().split("\n")
                if len(lines) < 2:
                    return {"score": 0.5, "note": "No prediction results"}

                data_line = lines[-1].split("\t")

                if claimed_ic50 is None:
                    return {"score": 0.5, "note": "No IC50 claimed", "iedb_available": True}

                try:
                    iedb_ic50 = float(data_line[-1])
                    # Compare on log scale for IC50
                    import math
                    if iedb_ic50 > 0 and claimed_ic50 > 0:
                        log_diff = abs(math.log10(iedb_ic50) - math.log10(claimed_ic50))
                        match = log_diff <= 0.5  # within half an order of magnitude
                    else:
                        match = False

                    return {
                        "score": 1.0 if match else 0.3,
                        "match": match,
                        "claimed_ic50": claimed_ic50,
                        "iedb_ic50": iedb_ic50,
                    }
                except (ValueError, IndexError):
                    return {"score": 0.5, "note": "Could not parse IEDB IC50"}

        except Exception as e:
            logger.warning("binding_affinity_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _check_surface_accessibility(sequence: str, claimed_accessibility: float | None) -> dict:
        """Check surface accessibility using hydrophobicity profile."""
        if not sequence:
            return {"score": 0.5, "note": "No sequence for accessibility check"}

        # Kyte-Doolittle hydrophobicity scale
        kd_scale = {
            "A": 1.8, "C": 2.5, "D": -3.5, "E": -3.5, "F": 2.8,
            "G": -0.4, "H": -3.2, "I": 4.5, "K": -3.9, "L": 3.8,
            "M": 1.9, "N": -3.5, "P": -1.6, "Q": -3.5, "R": -4.5,
            "S": -0.8, "T": -0.7, "V": 4.2, "W": -0.9, "Y": -1.3,
        }

        hydrophobicity = [kd_scale.get(aa, 0) for aa in sequence.upper()]
        avg_hydrophobicity = sum(hydrophobicity) / len(hydrophobicity) if hydrophobicity else 0

        # B-cell epitopes tend to be hydrophilic (negative hydrophobicity)
        # Score higher if avg hydrophobicity is negative (more accessible)
        if avg_hydrophobicity < -1.0:
            access_score = 1.0
        elif avg_hydrophobicity < 0:
            access_score = 0.7
        elif avg_hydrophobicity < 1.0:
            access_score = 0.4
        else:
            access_score = 0.2

        result: dict[str, Any] = {
            "score": access_score,
            "avg_hydrophobicity": round(avg_hydrophobicity, 3),
        }

        if claimed_accessibility is not None:
            # If they claim high accessibility but peptide is hydrophobic, penalize
            if claimed_accessibility > 0.5 and avg_hydrophobicity > 1.0:
                result["score"] = 0.2
                result["note"] = "Claimed accessible but hydrophobic"
            elif claimed_accessibility < 0.3 and avg_hydrophobicity < -1.0:
                result["score"] = 0.2
                result["note"] = "Claimed buried but hydrophilic"

        return result

    async def _check_iedb_bcell(self, sequence: str) -> dict:
        """Run IEDB B-cell epitope prediction."""
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.post(
                    f"{IEDB_API}/bcell/",
                    data={
                        "method": "Bepipred",
                        "sequence_text": sequence,
                    },
                )
                if resp.status_code != 200:
                    return {"score": 0.5, "note": f"IEDB B-cell API failed (HTTP {resp.status_code})"}

                text = resp.text.strip()
                if not text or "error" in text.lower():
                    return {"score": 0.5, "note": "IEDB B-cell returned error"}

                # Parse results — look for positive predictions
                lines = text.strip().split("\n")
                if len(lines) < 2:
                    return {"score": 0.5, "note": "No B-cell prediction results"}

                # Count positive predictions
                positive = 0
                total = 0
                for line in lines[1:]:
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        total += 1
                        try:
                            score_val = float(parts[-1])
                            if score_val > 0.5:
                                positive += 1
                        except ValueError:
                            pass

                if total == 0:
                    return {"score": 0.5, "note": "Could not parse B-cell results"}

                frac_positive = positive / total
                return {
                    "score": min(1.0, frac_positive * 2),  # Scale up
                    "positive_residues": positive,
                    "total_residues": total,
                    "fraction_positive": round(frac_positive, 3),
                }

        except Exception as e:
            logger.warning("iedb_bcell_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_conservation(self, sequence: str, protein_id: str) -> dict:
        """Check sequence conservation (simplified check via UniProt)."""
        if not protein_id:
            return {"score": 0.5, "note": "No protein ID for conservation check"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                # Check if the protein has orthologs noted in UniProt
                resp = await client.get(
                    f"{UNIPROT_BASE}/{protein_id}",
                    headers={"Accept": "application/json"},
                )
                if resp.status_code != 200:
                    return {"score": 0.5, "note": "Could not fetch protein info"}

                data = resp.json()
                # Check for cross-references to ortholog databases
                xrefs = data.get("uniProtKBCrossReferences", [])
                orthodb_refs = [
                    x for x in xrefs
                    if x.get("database") in ("OrthoDB", "OMA", "InParanoid")
                ]

                if orthodb_refs:
                    return {
                        "score": 0.8,
                        "conserved": True,
                        "ortholog_databases": len(orthodb_refs),
                    }
                return {"score": 0.5, "note": "No ortholog data available"}

        except Exception as e:
            logger.warning("conservation_check_failed", error=str(e))
            return {"score": 0.5, "error": str(e)}
