"""Materials science verification: pymatgen local + Materials Project API.

Validates crystal structures and cross-references properties against the
Materials Project database (150k+ DFT-computed entries).  No Docker needed.
"""
import asyncio
import os
import time

import httpx

from backend.verification.base import (
    VerificationAdapter, VerificationResult,
)
from backend.logging_config import get_logger

logger = get_logger(__name__)

MP_API_KEY = os.getenv("MP_API_KEY", "")
AFLOW_BASE = "http://aflowlib.org/API/aflux/"
TIMEOUT = 30  # seconds total


class MaterialsAdapter(VerificationAdapter):
    domain = "materials_science"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        claim_type = task_result.get("claim_type", "material_prediction")

        if claim_type == "material_prediction":
            return await self._verify_prediction(task_result)
        elif claim_type == "material_property":
            return await self._verify_property(task_result)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    # ------------------------------------------------------------------
    # material_prediction
    # ------------------------------------------------------------------

    async def _verify_prediction(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        formula = result.get("formula")
        cif_data = result.get("structure_cif")
        claimed_props = result.get("predicted_properties", {})

        if not cif_data:
            return VerificationResult.fail(self.domain, ["No structure_cif provided"])

        component_scores: dict[str, float] = {}
        details: dict = {"claim_type": "material_prediction", "formula": formula}
        warnings: list[str] = []

        # --- Check 1: CIF parsability (0.15) ---
        parse_result = await asyncio.to_thread(self._check_cif_parse, cif_data)
        component_scores["cif_parsability"] = parse_result["score"]
        details["structure"] = parse_result.get("metrics", {})

        if parse_result["score"] == 0.0:
            elapsed = time.monotonic() - start
            return VerificationResult(
                passed=False, score=0.0,
                badge=VerificationResult.score_to_badge(0.0),
                domain=self.domain,
                details=details,
                errors=["CIF file could not be parsed — structure is invalid"],
                compute_time_seconds=elapsed,
            )

        structure = parse_result.get("structure")

        # --- Check 2: Overlapping atoms (0.15) ---
        overlap_result = await asyncio.to_thread(self._check_overlapping_atoms, structure)
        component_scores["overlapping_atoms"] = overlap_result["score"]
        details["overlap"] = overlap_result.get("metrics", {})

        if overlap_result.get("severe"):
            elapsed = time.monotonic() - start
            score = self._weighted_score(component_scores)
            return VerificationResult(
                passed=False, score=score,
                badge=VerificationResult.score_to_badge(score),
                domain=self.domain,
                details=details,
                errors=["Severe overlapping atoms detected — physically impossible structure"],
                compute_time_seconds=elapsed,
            )

        # --- Check 3: Symmetry analysis (0.10) ---
        symmetry_result = await asyncio.to_thread(self._check_symmetry, structure)
        component_scores["symmetry"] = symmetry_result["score"]
        details["symmetry"] = symmetry_result.get("metrics", {})

        # --- Check 4: Composition validity (0.15) ---
        comp_result = await asyncio.to_thread(self._check_composition, structure)
        component_scores["composition"] = comp_result["score"]
        details["composition"] = comp_result.get("metrics", {})

        # --- Check 5 & 6: MP API energy + property cross-reference (0.25 + 0.20) ---
        mp_result = await self._check_materials_project(formula, claimed_props)
        component_scores["energy_crossref"] = mp_result.get("energy_score", 0.5)
        component_scores["property_crossref"] = mp_result.get("property_score", 0.5)
        details["materials_project"] = mp_result.get("metrics", {})
        if mp_result.get("warnings"):
            warnings.extend(mp_result["warnings"])

        # --- Aggregate ---
        score = self._weighted_score(component_scores)
        passed = score >= 0.5 and component_scores["cif_parsability"] > 0.0

        elapsed = time.monotonic() - start
        details["component_scores"] = component_scores

        return VerificationResult(
            passed=passed,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details=details,
            warnings=warnings,
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # material_property
    # ------------------------------------------------------------------

    async def _verify_property(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        mp_id = result.get("materials_project_id")
        formula = result.get("formula")
        claimed_props = result.get("properties", {})

        if not claimed_props:
            return VerificationResult.fail(self.domain, ["No properties provided to verify"])
        if not mp_id and not formula:
            return VerificationResult.fail(self.domain, ["materials_project_id or formula required"])

        mp_result = await self._lookup_mp_properties(mp_id, formula)

        if not mp_result.get("found"):
            elapsed = time.monotonic() - start
            return VerificationResult(
                passed=False, score=0.3,
                badge=VerificationResult.score_to_badge(0.3),
                domain=self.domain,
                details={
                    "claim_type": "material_property",
                    "lookup_id": mp_id or formula,
                    "note": "Material not found in Materials Project database",
                },
                compute_time_seconds=elapsed,
            )

        db_props = mp_result["properties"]
        matches = 0
        total = 0
        comparisons: dict = {}

        for prop_name, claimed_val in claimed_props.items():
            if prop_name in db_props and db_props[prop_name] is not None:
                total += 1
                db_val = db_props[prop_name]
                if isinstance(claimed_val, (int, float)) and isinstance(db_val, (int, float)):
                    denom = max(abs(db_val), 1e-10)
                    rel_error = abs(claimed_val - db_val) / denom
                    ok = rel_error <= 0.10  # 10% tolerance
                    comparisons[prop_name] = {
                        "claimed": claimed_val,
                        "database": db_val,
                        "relative_error": round(rel_error, 4),
                        "within_tolerance": ok,
                    }
                    if ok:
                        matches += 1
                else:
                    ok = str(claimed_val) == str(db_val)
                    comparisons[prop_name] = {
                        "claimed": claimed_val,
                        "database": db_val,
                        "match": ok,
                    }
                    if ok:
                        matches += 1

        score = matches / max(total, 1)
        elapsed = time.monotonic() - start

        return VerificationResult(
            passed=score >= 0.5,
            score=round(score, 4),
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details={
                "claim_type": "material_property",
                "lookup_id": mp_id or formula,
                "comparisons": comparisons,
                "matched": matches,
                "total_compared": total,
            },
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Local checks (run in thread via asyncio.to_thread)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_cif_parse(cif_data: str) -> dict:
        try:
            from pymatgen.core import Structure
            structure = Structure.from_str(cif_data, fmt="cif")
            if len(structure) == 0:
                return {"score": 0.0, "metrics": {"error": "Empty structure"}}
            return {
                "score": 1.0,
                "structure": structure,
                "metrics": {
                    "n_sites": len(structure),
                    "lattice_abc": [round(x, 3) for x in structure.lattice.abc],
                    "lattice_angles": [round(x, 2) for x in structure.lattice.angles],
                },
            }
        except Exception as e:
            return {"score": 0.0, "metrics": {"error": str(e)}}

    @staticmethod
    def _check_overlapping_atoms(structure) -> dict:
        if structure is None:
            return {"score": 0.0, "severe": True, "metrics": {"error": "No structure"}}
        try:
            dist_matrix = structure.distance_matrix
            n = len(structure)
            severe_count = 0
            for i in range(n):
                for j in range(i + 1, n):
                    if dist_matrix[i, j] < 0.5:
                        severe_count += 1

            if severe_count > 0:
                return {
                    "score": 0.0,
                    "severe": True,
                    "metrics": {"overlapping_pairs": severe_count},
                }
            return {"score": 1.0, "severe": False, "metrics": {"overlapping_pairs": 0}}
        except Exception as e:
            return {"score": 0.5, "severe": False, "metrics": {"error": str(e)}}

    @staticmethod
    def _check_symmetry(structure) -> dict:
        if structure is None:
            return {"score": 0.0, "metrics": {}}
        try:
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
            analyzer = SpacegroupAnalyzer(structure)
            sg_symbol = analyzer.get_space_group_symbol()
            sg_number = analyzer.get_space_group_number()
            crystal_system = analyzer.get_crystal_system()
            return {
                "score": 1.0,
                "metrics": {
                    "space_group_symbol": sg_symbol,
                    "space_group_number": sg_number,
                    "crystal_system": crystal_system,
                },
            }
        except Exception as e:
            return {"score": 0.3, "metrics": {"error": str(e)}}

    @staticmethod
    def _check_composition(structure) -> dict:
        if structure is None:
            return {"score": 0.0, "metrics": {}}
        try:
            from pymatgen.core import Element
            comp = structure.composition
            elements = comp.elements

            # Check all elements are real
            all_valid = all(isinstance(e, Element) for e in elements)
            if not all_valid:
                return {"score": 0.0, "metrics": {"error": "Invalid elements"}}

            # Check no negative or zero amounts
            amounts_ok = all(comp[e] > 0 for e in elements)

            # Check for electronegativity spread (simple plausibility)
            electroneg = [e.X for e in elements if e.X is not None]
            has_spread = (max(electroneg) - min(electroneg)) >= 0.0 if len(electroneg) >= 2 else True

            score = 1.0
            if not amounts_ok:
                score -= 0.5
            if not has_spread:
                score -= 0.2

            return {
                "score": max(0.0, score),
                "metrics": {
                    "formula": str(comp.reduced_formula),
                    "n_elements": len(elements),
                    "elements": [str(e) for e in elements],
                    "amounts_valid": amounts_ok,
                },
            }
        except Exception as e:
            return {"score": 0.3, "metrics": {"error": str(e)}}

    # ------------------------------------------------------------------
    # Materials Project API checks
    # ------------------------------------------------------------------

    async def _check_materials_project(
        self, formula: str | None, claimed_props: dict,
    ) -> dict:
        warnings: list[str] = []

        if not formula:
            return {
                "energy_score": 0.5,
                "property_score": 0.5,
                "warnings": ["No formula provided — skipping MP cross-reference"],
                "metrics": {},
            }

        # Try MP API first, then AFLOW fallback
        mp_data = await self._query_mp_api(formula)

        if mp_data is None:
            mp_data = await self._query_aflow(formula)

        if mp_data is None:
            warnings.append(f"No database entry found for {formula}")
            return {
                "energy_score": 0.5,
                "property_score": 0.5,
                "warnings": warnings,
                "metrics": {"note": "Formula not found in MP or AFLOW"},
            }

        # Energy cross-reference
        energy_score = 0.5
        energy_metrics: dict = {}
        db_energy = mp_data.get("energy_per_atom")
        claimed_energy = claimed_props.get("energy_per_atom")

        if db_energy is not None and claimed_energy is not None:
            diff = abs(claimed_energy - db_energy)
            # Within 0.1 eV/atom is excellent, within 0.5 is reasonable
            if diff <= 0.1:
                energy_score = 1.0
            elif diff <= 0.5:
                energy_score = 0.7
            elif diff <= 1.0:
                energy_score = 0.4
            else:
                energy_score = 0.1
            energy_metrics = {
                "claimed_energy_per_atom": claimed_energy,
                "database_energy_per_atom": db_energy,
                "difference_ev": round(diff, 4),
            }
        elif db_energy is not None:
            energy_score = 0.5
            energy_metrics = {"database_energy_per_atom": db_energy, "note": "No claimed energy to compare"}

        # Property cross-reference (band gap, formation energy, stability)
        property_score = 0.5
        prop_metrics: dict = {}

        db_band_gap = mp_data.get("band_gap")
        claimed_bg = claimed_props.get("band_gap")
        if db_band_gap is not None and claimed_bg is not None:
            bg_diff = abs(claimed_bg - db_band_gap)
            if bg_diff <= 0.2:
                property_score = 1.0
            elif bg_diff <= 0.5:
                property_score = 0.7
            elif bg_diff <= 1.0:
                property_score = 0.4
            else:
                property_score = 0.1
            prop_metrics["band_gap"] = {
                "claimed": claimed_bg,
                "database": db_band_gap,
                "difference_ev": round(bg_diff, 4),
            }

        db_ehull = mp_data.get("energy_above_hull")
        claimed_ehull = claimed_props.get("energy_above_hull")
        if db_ehull is not None and claimed_ehull is not None:
            ehull_diff = abs(claimed_ehull - db_ehull)
            ehull_ok = ehull_diff <= 0.05
            prop_metrics["energy_above_hull"] = {
                "claimed": claimed_ehull,
                "database": db_ehull,
                "match": ehull_ok,
            }
            if ehull_ok:
                property_score = min(1.0, property_score + 0.2)

        return {
            "energy_score": energy_score,
            "property_score": property_score,
            "warnings": warnings,
            "metrics": {
                "source": mp_data.get("source", "materials_project"),
                "energy": energy_metrics,
                "properties": prop_metrics,
                "mp_id": mp_data.get("material_id"),
            },
        }

    async def _query_mp_api(self, formula: str) -> dict | None:
        """Query Materials Project API via mp-api client or REST fallback."""
        if MP_API_KEY:
            try:
                from mp_api.client import MPRester
                result = await asyncio.to_thread(self._mp_rester_query, formula)
                return result
            except Exception as e:
                logger.warning("mp_api_client_failed", error=str(e))

        # REST fallback (works without key for some fields)
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                url = f"https://api.materialsproject.org/materials/summary/?formula={formula}&_limit=1"
                headers = {}
                if MP_API_KEY:
                    headers["X-API-KEY"] = MP_API_KEY
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return None
                data = resp.json()
                docs = data.get("data", [])
                if not docs:
                    return None
                doc = docs[0]
                return {
                    "source": "materials_project",
                    "material_id": doc.get("material_id"),
                    "energy_per_atom": doc.get("energy_per_atom"),
                    "band_gap": doc.get("band_gap"),
                    "energy_above_hull": doc.get("energy_above_hull"),
                    "formation_energy_per_atom": doc.get("formation_energy_per_atom"),
                }
        except Exception as e:
            logger.warning("mp_rest_failed", error=str(e))
            return None

    @staticmethod
    def _mp_rester_query(formula: str) -> dict | None:
        from mp_api.client import MPRester
        with MPRester(MP_API_KEY) as mpr:
            docs = mpr.materials.summary.search(
                formula=formula,
                fields=["material_id", "energy_per_atom", "band_gap",
                         "energy_above_hull", "formation_energy_per_atom"],
            )
            if not docs:
                return None
            doc = docs[0]
            return {
                "source": "materials_project",
                "material_id": str(doc.material_id),
                "energy_per_atom": doc.energy_per_atom,
                "band_gap": doc.band_gap,
                "energy_above_hull": doc.energy_above_hull,
                "formation_energy_per_atom": doc.formation_energy_per_atom,
            }

    async def _query_aflow(self, formula: str) -> dict | None:
        """AFLOW REST fallback — no API key needed."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                url = (
                    f"{AFLOW_BASE}?matchbook(compound({formula}),"
                    f"enthalpy_atom,Egap,energy_atom)"
                    f",$paging(1)"
                )
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None
                data = resp.json()
                if not data:
                    return None
                entry = data[0] if isinstance(data, list) else data
                return {
                    "source": "aflow",
                    "energy_per_atom": entry.get("energy_atom"),
                    "band_gap": entry.get("Egap"),
                    "energy_above_hull": None,
                    "formation_energy_per_atom": entry.get("enthalpy_atom"),
                }
        except Exception as e:
            logger.warning("aflow_query_failed", error=str(e))
            return None

    async def _lookup_mp_properties(
        self, mp_id: str | None, formula: str | None,
    ) -> dict:
        """Look up material by MP ID or formula for property verification."""
        if mp_id and MP_API_KEY:
            try:
                from mp_api.client import MPRester
                result = await asyncio.to_thread(self._mp_rester_by_id, mp_id)
                if result:
                    return {"found": True, "properties": result}
            except Exception as e:
                logger.warning("mp_id_lookup_failed", error=str(e))

        if formula:
            mp_data = await self._query_mp_api(formula)
            if mp_data:
                return {"found": True, "properties": mp_data}

        return {"found": False}

    @staticmethod
    def _mp_rester_by_id(mp_id: str) -> dict | None:
        from mp_api.client import MPRester
        with MPRester(MP_API_KEY) as mpr:
            docs = mpr.materials.summary.search(
                material_ids=[mp_id],
                fields=["material_id", "energy_per_atom", "band_gap",
                         "energy_above_hull", "formation_energy_per_atom",
                         "density", "volume"],
            )
            if not docs:
                return None
            doc = docs[0]
            return {
                "energy_per_atom": doc.energy_per_atom,
                "band_gap": doc.band_gap,
                "energy_above_hull": doc.energy_above_hull,
                "formation_energy_per_atom": doc.formation_energy_per_atom,
                "density": getattr(doc, "density", None),
                "volume": getattr(doc, "volume", None),
            }

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _weighted_score(component_scores: dict[str, float]) -> float:
        weights = {
            "cif_parsability": 0.15,
            "overlapping_atoms": 0.15,
            "symmetry": 0.10,
            "energy_crossref": 0.25,
            "property_crossref": 0.20,
            "composition": 0.15,
        }
        total = sum(
            weights.get(k, 0) * component_scores.get(k, 0.0)
            for k in weights
        )
        return min(1.0, round(total, 4))
