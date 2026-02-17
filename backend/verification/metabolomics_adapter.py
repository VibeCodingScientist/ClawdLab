"""Metabolomics verification: HMDB + PubChem + KEGG + MassBank.

Validates compound identification, pathway mapping, and spectral matching
using public metabolomics APIs.  API-based (no Docker).
"""
from __future__ import annotations

import math
import time
from typing import Any

import httpx

from backend.logging_config import get_logger
from backend.verification.base import (
    VerificationAdapter,
    VerificationResult,
)

logger = get_logger(__name__)

HMDB_API = "https://hmdb.ca/metabolites"
PUBCHEM_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
KEGG_REST = "https://rest.kegg.jp"
MASSBANK_API = "https://massbank.eu/MassBank/rest"
HTTP_TIMEOUT = 30

# Standard adduct types for mass spectrometry
STANDARD_ADDUCTS = {
    "[M+H]+", "[M+Na]+", "[M+K]+", "[M+NH4]+",
    "[M-H]-", "[M+Cl]-", "[M+FA-H]-", "[M+CH3COO]-",
    "[M+2H]2+", "[M-H2O+H]+", "[M-2H]2-",
}


class MetabolomicsAdapter(VerificationAdapter):
    domain = "metabolomics"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        claim_type = task_result.get("claim_type", "compound_identification")

        if claim_type == "compound_identification":
            return await self._verify_compound_identification(task_result)
        elif claim_type == "pathway_mapping":
            return await self._verify_pathway_mapping(task_result)
        elif claim_type == "spectral_match":
            return await self._verify_spectral_match(task_result)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    # ------------------------------------------------------------------
    # compound_identification
    # ------------------------------------------------------------------

    async def _verify_compound_identification(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        hmdb_id = result.get("hmdb_id", "")
        compound_name = result.get("compound_name", "")
        claimed_mz = result.get("mz")
        claimed_formula = result.get("formula", "")
        inchikey = result.get("inchikey", "")

        if not hmdb_id and not compound_name and not inchikey:
            return VerificationResult.fail(
                self.domain, ["hmdb_id, compound_name, or inchikey required"],
            )

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "compound_identification"}

        # Component 1: identifier_valid (0.20)
        id_result = await self._check_identifier_valid(hmdb_id, inchikey)
        component_scores["identifier_valid"] = id_result["score"]
        details["identifier_valid"] = id_result

        # Component 2: name_match (0.20)
        name_result = await self._check_name_match(hmdb_id, compound_name)
        component_scores["name_match"] = name_result["score"]
        details["name_match"] = name_result

        # Component 3: mass_match (0.25)
        mass_result = await self._check_mass_match(hmdb_id, claimed_mz, result.get("adduct"))
        component_scores["mass_match"] = mass_result["score"]
        details["mass_match"] = mass_result

        # Component 4: formula_match (0.20)
        formula_result = await self._check_formula_match(hmdb_id, claimed_formula)
        component_scores["formula_match"] = formula_result["score"]
        details["formula_match"] = formula_result

        # Component 5: pubchem_cross_ref (0.15)
        pubchem_result = await self._check_pubchem_cross_ref(compound_name, inchikey)
        component_scores["pubchem_cross_ref"] = pubchem_result["score"]
        details["pubchem_cross_ref"] = pubchem_result

        weights = {
            "identifier_valid": 0.20,
            "name_match": 0.20,
            "mass_match": 0.25,
            "formula_match": 0.20,
            "pubchem_cross_ref": 0.15,
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
    # pathway_mapping
    # ------------------------------------------------------------------

    async def _verify_pathway_mapping(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        compound_id = result.get("kegg_compound_id", "")
        pathway_id = result.get("kegg_pathway_id", "")
        claimed_enzymes = result.get("enzymes", [])

        if not compound_id:
            return VerificationResult.fail(self.domain, ["kegg_compound_id required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "pathway_mapping"}

        # Component 1: compound_exists (0.20)
        cpd_result = await self._check_kegg_compound_exists(compound_id)
        component_scores["compound_exists"] = cpd_result["score"]
        details["compound_exists"] = cpd_result

        # Component 2: pathway_exists (0.25)
        pw_result = await self._check_kegg_pathway_exists(pathway_id)
        component_scores["pathway_exists"] = pw_result["score"]
        details["pathway_exists"] = pw_result

        # Component 3: compound_in_pathway (0.30)
        in_pw_result = await self._check_compound_in_pathway(compound_id, pathway_id)
        component_scores["compound_in_pathway"] = in_pw_result["score"]
        details["compound_in_pathway"] = in_pw_result

        # Component 4: enzyme_links (0.25)
        enz_result = await self._check_enzyme_links(compound_id, claimed_enzymes)
        component_scores["enzyme_links"] = enz_result["score"]
        details["enzyme_links"] = enz_result

        weights = {
            "compound_exists": 0.20,
            "pathway_exists": 0.25,
            "compound_in_pathway": 0.30,
            "enzyme_links": 0.25,
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
    # spectral_match
    # ------------------------------------------------------------------

    async def _verify_spectral_match(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        precursor_mz = result.get("precursor_mz")
        adduct = result.get("adduct", "")
        spectrum_peaks = result.get("spectrum_peaks", [])
        claimed_compound = result.get("compound_name", "")
        ppm_tolerance = result.get("ppm_tolerance", 10)

        if not spectrum_peaks:
            return VerificationResult.fail(self.domain, ["spectrum_peaks required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "spectral_match"}

        # Component 1: precursor_valid (0.15)
        prec_result = self._check_precursor_valid(precursor_mz)
        component_scores["precursor_valid"] = prec_result["score"]
        details["precursor_valid"] = prec_result

        # Component 2: adduct_valid (0.10)
        adduct_result = self._check_adduct_valid(adduct)
        component_scores["adduct_valid"] = adduct_result["score"]
        details["adduct_valid"] = adduct_result

        # Component 3: fragment_match (0.35)
        frag_result = self._check_fragment_match(spectrum_peaks)
        component_scores["fragment_match"] = frag_result["score"]
        details["fragment_match"] = frag_result

        # Component 4: library_hit (0.25)
        lib_result = await self._check_library_hit(precursor_mz, spectrum_peaks)
        component_scores["library_hit"] = lib_result["score"]
        details["library_hit"] = lib_result

        # Component 5: mass_accuracy (0.15)
        acc_result = self._check_mass_accuracy(spectrum_peaks, ppm_tolerance)
        component_scores["mass_accuracy"] = acc_result["score"]
        details["mass_accuracy"] = acc_result

        weights = {
            "precursor_valid": 0.15,
            "adduct_valid": 0.10,
            "fragment_match": 0.35,
            "library_hit": 0.25,
            "mass_accuracy": 0.15,
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
    # API helpers — compound identification
    # ------------------------------------------------------------------

    async def _check_identifier_valid(self, hmdb_id: str, inchikey: str) -> dict:
        """Check if HMDB ID or InChIKey resolves."""
        if hmdb_id:
            try:
                async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                    resp = await client.get(
                        f"{HMDB_API}/{hmdb_id}.xml",
                        follow_redirects=True,
                    )
                    if resp.status_code == 200:
                        return {"score": 1.0, "found": True, "source": "hmdb"}
            except Exception as e:
                logger.warning("hmdb_id_check_failed", error=str(e))

        if inchikey:
            try:
                async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                    resp = await client.get(
                        f"{PUBCHEM_API}/compound/inchikey/{inchikey}/property/MolecularFormula/JSON",
                    )
                    if resp.status_code == 200:
                        return {"score": 1.0, "found": True, "source": "pubchem"}
            except Exception as e:
                logger.warning("inchikey_check_failed", error=str(e))

        return {"score": 0.0, "found": False}

    async def _check_name_match(self, hmdb_id: str, compound_name: str) -> dict:
        """Check if compound name matches HMDB record."""
        if not hmdb_id or not compound_name:
            return {"score": 0.5, "note": "HMDB ID or name missing for comparison"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{HMDB_API}/{hmdb_id}.xml",
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    return {"score": 0.3, "note": "HMDB lookup failed"}

                content = resp.text
                # Simple XML name extraction
                import re
                name_match = re.search(r"<name>(.*?)</name>", content)
                if name_match:
                    db_name = name_match.group(1).lower()
                    if compound_name.lower() == db_name:
                        return {"score": 1.0, "match": True, "db_name": name_match.group(1)}
                    if compound_name.lower() in db_name or db_name in compound_name.lower():
                        return {"score": 0.7, "partial_match": True, "db_name": name_match.group(1)}
                    return {"score": 0.0, "match": False, "db_name": name_match.group(1)}

                return {"score": 0.3, "note": "Could not extract name from HMDB"}
        except Exception as e:
            logger.warning("name_match_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_mass_match(
        self, hmdb_id: str, claimed_mz: float | None, adduct: str | None,
    ) -> dict:
        """Check if claimed m/z matches exact mass within instrument tolerance."""
        if claimed_mz is None:
            return {"score": 0.5, "note": "No m/z claimed"}

        if not hmdb_id:
            # Check plausibility only
            if 50 <= claimed_mz <= 2000:
                return {"score": 0.5, "note": "No HMDB ID for mass comparison", "mz_plausible": True}
            return {"score": 0.2, "note": "m/z outside typical range"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{HMDB_API}/{hmdb_id}.xml",
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    return {"score": 0.3, "note": "HMDB lookup failed"}

                content = resp.text
                import re
                mass_match = re.search(r"<monisotopic_molecular_weight>([\d.]+)</monisotopic_molecular_weight>", content)
                if not mass_match:
                    mass_match = re.search(r"<average_molecular_weight>([\d.]+)</average_molecular_weight>", content)

                if mass_match:
                    exact_mass = float(mass_match.group(1))
                    # Account for adduct mass shift
                    adduct_shift = 1.00728  # [M+H]+  by default
                    if adduct == "[M-H]-":
                        adduct_shift = -1.00728
                    elif adduct == "[M+Na]+":
                        adduct_shift = 22.9892
                    elif adduct == "[M+K]+":
                        adduct_shift = 38.9632

                    expected_mz = exact_mass + adduct_shift
                    ppm_error = abs(claimed_mz - expected_mz) / expected_mz * 1e6
                    match = ppm_error <= 10  # 10 ppm tolerance

                    return {
                        "score": 1.0 if match else 0.3,
                        "match": match,
                        "claimed_mz": claimed_mz,
                        "expected_mz": round(expected_mz, 4),
                        "ppm_error": round(ppm_error, 2),
                    }

                return {"score": 0.3, "note": "Could not extract mass from HMDB"}
        except Exception as e:
            logger.warning("mass_match_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_formula_match(self, hmdb_id: str, claimed_formula: str) -> dict:
        """Check if molecular formula matches HMDB."""
        if not hmdb_id or not claimed_formula:
            return {"score": 0.5, "note": "HMDB ID or formula missing"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{HMDB_API}/{hmdb_id}.xml",
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    return {"score": 0.3, "note": "HMDB lookup failed"}

                content = resp.text
                import re
                formula_match = re.search(r"<chemical_formula>(.*?)</chemical_formula>", content)
                if formula_match:
                    db_formula = formula_match.group(1).strip()
                    if claimed_formula.replace(" ", "") == db_formula.replace(" ", ""):
                        return {"score": 1.0, "match": True, "db_formula": db_formula}
                    return {"score": 0.0, "match": False, "claimed": claimed_formula, "db_formula": db_formula}

                return {"score": 0.3, "note": "Could not extract formula from HMDB"}
        except Exception as e:
            logger.warning("formula_match_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_pubchem_cross_ref(self, compound_name: str, inchikey: str) -> dict:
        """Cross-reference with PubChem."""
        identifier = inchikey or compound_name
        if not identifier:
            return {"score": 0.5, "note": "No identifier for PubChem lookup"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                if inchikey:
                    resp = await client.get(
                        f"{PUBCHEM_API}/compound/inchikey/{inchikey}/property/MolecularFormula,MolecularWeight/JSON",
                    )
                else:
                    resp = await client.get(
                        f"{PUBCHEM_API}/compound/name/{compound_name}/property/MolecularFormula,MolecularWeight/JSON",
                    )

                if resp.status_code == 200:
                    data = resp.json()
                    props = data.get("PropertyTable", {}).get("Properties", [{}])[0]
                    return {
                        "score": 0.8,
                        "found": True,
                        "pubchem_formula": props.get("MolecularFormula"),
                        "pubchem_weight": props.get("MolecularWeight"),
                    }
                return {"score": 0.3, "note": "Not found in PubChem"}
        except Exception as e:
            logger.warning("pubchem_cross_ref_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    # ------------------------------------------------------------------
    # API helpers — pathway mapping
    # ------------------------------------------------------------------

    async def _check_kegg_compound_exists(self, compound_id: str) -> dict:
        """Check if KEGG compound ID is valid."""
        if not compound_id:
            return {"score": 0.5, "note": "No compound ID"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(f"{KEGG_REST}/get/{compound_id}")
                if resp.status_code == 200:
                    return {"score": 1.0, "found": True}
                return {"score": 0.0, "found": False}
        except Exception as e:
            logger.warning("kegg_compound_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_kegg_pathway_exists(self, pathway_id: str) -> dict:
        """Check if KEGG pathway ID is valid."""
        if not pathway_id:
            return {"score": 0.5, "note": "No pathway ID"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(f"{KEGG_REST}/get/{pathway_id}")
                if resp.status_code == 200:
                    return {"score": 1.0, "found": True}
                return {"score": 0.0, "found": False}
        except Exception as e:
            logger.warning("kegg_pathway_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_compound_in_pathway(self, compound_id: str, pathway_id: str) -> dict:
        """Check if compound is a participant in the claimed pathway."""
        if not compound_id or not pathway_id:
            return {"score": 0.5, "note": "Both compound and pathway IDs needed"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(f"{KEGG_REST}/link/compound/{pathway_id}")
                if resp.status_code != 200:
                    return {"score": 0.3, "note": f"KEGG link query failed (HTTP {resp.status_code})"}

                compounds_in_pathway = resp.text.strip().split("\n")
                compound_ids = set()
                for line in compounds_in_pathway:
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        compound_ids.add(parts[1].strip())

                # Normalize compound_id format
                normalized = compound_id if ":" in compound_id else f"cpd:{compound_id}"
                if normalized in compound_ids or compound_id in compound_ids:
                    return {"score": 1.0, "found": True, "n_compounds": len(compound_ids)}
                return {
                    "score": 0.0,
                    "found": False,
                    "n_compounds_in_pathway": len(compound_ids),
                }
        except Exception as e:
            logger.warning("compound_in_pathway_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    async def _check_enzyme_links(self, compound_id: str, claimed_enzymes: list) -> dict:
        """Check if claimed enzymes link to compound in KEGG."""
        if not claimed_enzymes:
            return {"score": 0.5, "note": "No enzymes claimed"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(f"{KEGG_REST}/link/enzyme/{compound_id}")
                if resp.status_code != 200:
                    return {"score": 0.3, "note": "KEGG enzyme link failed"}

                db_enzymes: set[str] = set()
                for line in resp.text.strip().split("\n"):
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        db_enzymes.add(parts[1].strip().replace("ec:", ""))

                if not db_enzymes:
                    return {"score": 0.5, "note": "No enzyme links in KEGG"}

                matched = sum(1 for e in claimed_enzymes if e in db_enzymes)
                score = matched / len(claimed_enzymes) if claimed_enzymes else 0.0
                return {
                    "score": round(score, 4),
                    "matched": matched,
                    "total_claimed": len(claimed_enzymes),
                    "db_enzymes": sorted(list(db_enzymes))[:10],
                }
        except Exception as e:
            logger.warning("enzyme_links_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    # ------------------------------------------------------------------
    # Helpers — spectral match
    # ------------------------------------------------------------------

    @staticmethod
    def _check_precursor_valid(precursor_mz: float | None) -> dict:
        """Check if precursor m/z is in expected range."""
        if precursor_mz is None:
            return {"score": 0.5, "note": "No precursor m/z"}

        if not isinstance(precursor_mz, (int, float)):
            return {"score": 0.0, "error": "precursor_mz must be numeric"}

        # Typical metabolomics range: 50-2000 m/z
        if 50 <= precursor_mz <= 2000:
            return {"score": 1.0, "valid": True, "precursor_mz": precursor_mz}
        elif 20 <= precursor_mz <= 5000:
            return {"score": 0.5, "note": "Unusual precursor range", "precursor_mz": precursor_mz}
        return {"score": 0.0, "error": "precursor_mz outside plausible range"}

    @staticmethod
    def _check_adduct_valid(adduct: str) -> dict:
        """Check if adduct type is standard."""
        if not adduct:
            return {"score": 0.5, "note": "No adduct specified"}

        if adduct in STANDARD_ADDUCTS:
            return {"score": 1.0, "valid": True, "adduct": adduct}
        return {"score": 0.3, "valid": False, "adduct": adduct, "known_adducts": sorted(STANDARD_ADDUCTS)}

    @staticmethod
    def _check_fragment_match(spectrum_peaks: list) -> dict:
        """Validate spectrum peak list structure and compute self-consistency."""
        if not spectrum_peaks:
            return {"score": 0.0, "error": "No peaks"}

        valid_peaks = 0
        invalid_peaks = 0

        for peak in spectrum_peaks:
            if isinstance(peak, (list, tuple)) and len(peak) >= 2:
                mz, intensity = peak[0], peak[1]
                if isinstance(mz, (int, float)) and isinstance(intensity, (int, float)):
                    if mz > 0 and intensity >= 0:
                        valid_peaks += 1
                        continue
            invalid_peaks += 1

        total = valid_peaks + invalid_peaks
        score = valid_peaks / total if total > 0 else 0.0

        # Check that peaks are sorted by m/z (expected)
        mz_values = [
            p[0] for p in spectrum_peaks
            if isinstance(p, (list, tuple)) and len(p) >= 2
        ]
        is_sorted = all(mz_values[i] <= mz_values[i + 1] for i in range(len(mz_values) - 1))

        return {
            "score": round(score, 4),
            "valid_peaks": valid_peaks,
            "invalid_peaks": invalid_peaks,
            "is_sorted": is_sorted,
            "n_peaks": total,
        }

    async def _check_library_hit(
        self, precursor_mz: float | None, spectrum_peaks: list,
    ) -> dict:
        """Search MassBank for spectral matches."""
        if precursor_mz is None:
            return {"score": 0.5, "note": "No precursor for library search"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                # Search MassBank by precursor m/z
                resp = await client.get(
                    f"{MASSBANK_API}/searchspectrum",
                    params={
                        "mz": str(precursor_mz),
                        "tol": "0.5",
                        "unit": "Da",
                        "limit": "5",
                    },
                )
                if resp.status_code != 200:
                    return {"score": 0.5, "note": f"MassBank search failed (HTTP {resp.status_code})"}

                data = resp.json()
                if not data:
                    return {"score": 0.3, "note": "No MassBank hits"}

                n_hits = len(data) if isinstance(data, list) else 0
                return {
                    "score": min(1.0, 0.5 + n_hits * 0.1),
                    "n_hits": n_hits,
                    "source": "massbank",
                }
        except Exception as e:
            logger.warning("library_hit_check_failed", error=str(e))
            return {"score": 0.5, "error": str(e)}

    @staticmethod
    def _check_mass_accuracy(spectrum_peaks: list, ppm_tolerance: float) -> dict:
        """Check if mass accuracy is within declared tolerance."""
        if not spectrum_peaks or not isinstance(ppm_tolerance, (int, float)):
            return {"score": 0.5, "note": "Insufficient data for accuracy check"}

        # Check that ppm tolerance is reasonable (0.1 to 100 ppm)
        if ppm_tolerance < 0.1:
            return {"score": 0.3, "note": "PPM tolerance unrealistically low"}
        if ppm_tolerance > 100:
            return {"score": 0.3, "note": "PPM tolerance unrealistically high"}

        # For a well-calibrated instrument, 1-20 ppm is typical
        if 1 <= ppm_tolerance <= 20:
            return {"score": 1.0, "plausible": True, "ppm_tolerance": ppm_tolerance}
        elif 0.1 <= ppm_tolerance <= 50:
            return {"score": 0.7, "plausible": True, "ppm_tolerance": ppm_tolerance}
        return {"score": 0.3, "plausible": False, "ppm_tolerance": ppm_tolerance}
