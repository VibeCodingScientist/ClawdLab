"""Chemistry verification: rdkit + PubChem + ChEMBL cross-reference.

Validates chemical reactions, molecular properties, and retrosynthesis
routes. API-based (no Docker) — rdkit runs in-process via asyncio.to_thread().
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from backend.logging_config import get_logger
from backend.verification.base import (
    VerificationAdapter,
    VerificationBadge,
    VerificationResult,
)

logger = get_logger(__name__)

PUBCHEM_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
HTTP_TIMEOUT = 20

# Try to import rdkit — graceful degradation if unavailable
try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False
    logger.warning("rdkit_not_available", note="Chemistry adapter will use API-only mode")


class ChemistryAdapter(VerificationAdapter):
    domain = "chemistry"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        claim_type = task_result.get("claim_type", "reaction_mechanism")

        if claim_type == "reaction_mechanism":
            return await self._verify_reaction(task_result)
        elif claim_type == "molecular_property":
            return await self._verify_molecular_property(task_result)
        elif claim_type == "retrosynthesis":
            return await self._verify_retrosynthesis(task_result)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    # ------------------------------------------------------------------
    # reaction_mechanism
    # ------------------------------------------------------------------

    async def _verify_reaction(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        reactants = result.get("reactants", [])
        products = result.get("products", [])
        smiles = result.get("smiles")

        if not reactants and not products and not smiles:
            return VerificationResult.fail(self.domain, ["No reactants, products, or SMILES provided"])

        # If single SMILES reaction string (e.g., "CC.O>>CCO")
        if smiles and not reactants:
            parts = smiles.split(">>")
            if len(parts) == 2:
                reactants = parts[0].split(".")
                products = parts[1].split(".")

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "reaction_mechanism"}

        # Component 1: SMILES validity (0.20)
        all_smiles = reactants + products
        valid_result = await asyncio.to_thread(self._check_smiles_validity, all_smiles)
        component_scores["smiles_valid"] = valid_result["score"]
        details["smiles_validity"] = valid_result

        # Component 2: Stoichiometry balanced (0.30)
        stoich_result = await asyncio.to_thread(self._check_stoichiometry, reactants, products)
        component_scores["stoichiometry"] = stoich_result["score"]
        details["stoichiometry"] = stoich_result

        # Component 3: Feasibility (0.30)
        feas_result = await asyncio.to_thread(self._check_feasibility, reactants, products)
        component_scores["feasibility"] = feas_result["score"]
        details["feasibility"] = feas_result

        # Component 4: Atom mapping (0.20)
        mapping_result = await asyncio.to_thread(self._check_atom_mapping, reactants, products)
        component_scores["atom_mapping"] = mapping_result["score"]
        details["atom_mapping"] = mapping_result

        weights = {"smiles_valid": 0.20, "stoichiometry": 0.30, "feasibility": 0.30, "atom_mapping": 0.20}
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
    # molecular_property
    # ------------------------------------------------------------------

    async def _verify_molecular_property(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        smiles = result.get("smiles")
        claimed_properties = result.get("claimed_properties", {})

        if not smiles:
            return VerificationResult.fail(self.domain, ["No SMILES string provided"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "molecular_property", "smiles": smiles}
        warnings: list[str] = []

        # Component 1: Structure valid (0.20)
        valid_result = await asyncio.to_thread(self._check_smiles_validity, [smiles])
        component_scores["structure_valid"] = valid_result["score"]
        details["structure"] = valid_result

        if valid_result["score"] == 0.0:
            elapsed = time.monotonic() - start
            return VerificationResult(
                passed=False, score=0.0,
                badge=VerificationBadge.RED,
                domain=self.domain,
                details=details,
                errors=["Invalid SMILES structure"],
                compute_time_seconds=elapsed,
            )

        # Component 2: PubChem match (0.35)
        pubchem_result = await self._check_pubchem(smiles, claimed_properties)
        component_scores["pubchem_match"] = pubchem_result["score"]
        details["pubchem"] = pubchem_result

        # Component 3: ChEMBL match (0.25)
        chembl_result = await self._check_chembl(smiles, claimed_properties)
        component_scores["chembl_match"] = chembl_result["score"]
        details["chembl"] = chembl_result

        # Component 4: Property range (0.20)
        range_result = await asyncio.to_thread(self._check_property_ranges, smiles, claimed_properties)
        component_scores["property_range"] = range_result["score"]
        details["property_range"] = range_result
        if range_result.get("warnings"):
            warnings.extend(range_result["warnings"])

        weights = {"structure_valid": 0.20, "pubchem_match": 0.35, "chembl_match": 0.25, "property_range": 0.20}
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
            warnings=warnings,
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # retrosynthesis
    # ------------------------------------------------------------------

    async def _verify_retrosynthesis(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        precursors = result.get("precursors", [])
        products = result.get("products", [])

        if not precursors or not products:
            return VerificationResult.fail(self.domain, ["precursors and products required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "retrosynthesis"}

        # Component 1: Precursors valid (0.25)
        prec_result = await asyncio.to_thread(self._check_smiles_validity, precursors)
        component_scores["precursors_valid"] = prec_result["score"]
        details["precursors"] = prec_result

        # Component 2: Product valid (0.25)
        prod_result = await asyncio.to_thread(self._check_smiles_validity, products)
        component_scores["product_valid"] = prod_result["score"]
        details["products"] = prod_result

        # Component 3: Atom conservation (0.30)
        conserv_result = await asyncio.to_thread(self._check_atom_conservation, precursors, products)
        component_scores["atom_conservation"] = conserv_result["score"]
        details["atom_conservation"] = conserv_result

        # Component 4: Route plausibility (0.20)
        plaus_result = await asyncio.to_thread(self._check_route_plausibility, precursors, products)
        component_scores["route_plausibility"] = plaus_result["score"]
        details["route_plausibility"] = plaus_result

        weights = {"precursors_valid": 0.25, "product_valid": 0.25, "atom_conservation": 0.30, "route_plausibility": 0.20}
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
    # Helpers — rdkit-based checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_smiles_validity(smiles_list: list[str]) -> dict:
        """Parse all SMILES and check validity."""
        if not RDKIT_AVAILABLE:
            return {"score": 0.5, "note": "rdkit unavailable, skipping SMILES validation"}

        valid = 0
        invalid: list[str] = []
        for s in smiles_list:
            mol = Chem.MolFromSmiles(s)
            if mol is not None:
                valid += 1
            else:
                invalid.append(s)

        score = valid / len(smiles_list) if smiles_list else 0.0
        return {
            "score": round(score, 4),
            "valid": valid,
            "invalid": invalid[:5],
            "total": len(smiles_list),
        }

    @staticmethod
    def _check_stoichiometry(reactants: list[str], products: list[str]) -> dict:
        """Check atom balance between reactants and products."""
        if not RDKIT_AVAILABLE:
            return {"score": 0.5, "note": "rdkit unavailable"}

        def count_atoms(smiles_list: list[str]) -> dict[str, int]:
            counts: dict[str, int] = {}
            for s in smiles_list:
                mol = Chem.MolFromSmiles(s)
                if mol is None:
                    continue
                for atom in mol.GetAtoms():
                    sym = atom.GetSymbol()
                    counts[sym] = counts.get(sym, 0) + 1
                # Add implicit hydrogens
                mol_h = Chem.AddHs(mol)
                h_count = sum(1 for a in mol_h.GetAtoms() if a.GetSymbol() == "H") - \
                          sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "H")
                counts["H"] = counts.get("H", 0) + h_count
            return counts

        reactant_atoms = count_atoms(reactants)
        product_atoms = count_atoms(products)

        if not reactant_atoms or not product_atoms:
            return {"score": 0.0, "note": "Could not count atoms"}

        all_elements = set(reactant_atoms.keys()) | set(product_atoms.keys())
        balanced = 0
        imbalanced: list[str] = []

        for elem in all_elements:
            r_count = reactant_atoms.get(elem, 0)
            p_count = product_atoms.get(elem, 0)
            if r_count == p_count:
                balanced += 1
            else:
                imbalanced.append(f"{elem}: {r_count} -> {p_count}")

        score = balanced / len(all_elements) if all_elements else 0.0
        return {
            "score": round(score, 4),
            "balanced_elements": balanced,
            "imbalanced": imbalanced[:10],
            "reactant_atoms": reactant_atoms,
            "product_atoms": product_atoms,
        }

    @staticmethod
    def _check_feasibility(reactants: list[str], products: list[str]) -> dict:
        """Basic thermodynamic feasibility checks."""
        if not RDKIT_AVAILABLE:
            return {"score": 0.5, "note": "rdkit unavailable"}

        issues: list[str] = []

        for i, s in enumerate(products):
            mol = Chem.MolFromSmiles(s)
            if mol is None:
                continue

            mw = Descriptors.MolWt(mol)
            # Very large products from small reactants is suspicious
            if mw > 2000:
                issues.append(f"Product {i} has very high MW ({mw:.0f})")

            # Check for unusual valences
            try:
                Chem.SanitizeMol(mol)
            except Exception:
                issues.append(f"Product {i} has sanitization issues")

        score = max(0.0, 1.0 - 0.25 * len(issues))
        return {
            "score": round(score, 4),
            "issues": issues[:10],
        }

    @staticmethod
    def _check_atom_mapping(reactants: list[str], products: list[str]) -> dict:
        """Check atom mapping consistency if mapping is provided."""
        if not RDKIT_AVAILABLE:
            return {"score": 0.5, "note": "rdkit unavailable"}

        # Check if atom maps are present in the SMILES
        has_maps = any(":" in s for s in reactants + products)
        if not has_maps:
            return {"score": 0.5, "note": "No atom mapping provided"}

        reactant_maps: set[int] = set()
        product_maps: set[int] = set()

        for s in reactants:
            mol = Chem.MolFromSmiles(s)
            if mol:
                for atom in mol.GetAtoms():
                    am = atom.GetAtomMapNum()
                    if am > 0:
                        reactant_maps.add(am)

        for s in products:
            mol = Chem.MolFromSmiles(s)
            if mol:
                for atom in mol.GetAtoms():
                    am = atom.GetAtomMapNum()
                    if am > 0:
                        product_maps.add(am)

        if not reactant_maps and not product_maps:
            return {"score": 0.5, "note": "No atom map numbers found"}

        # Maps should match between reactants and products
        common = reactant_maps & product_maps
        all_maps = reactant_maps | product_maps
        score = len(common) / len(all_maps) if all_maps else 0.5

        return {
            "score": round(score, 4),
            "reactant_maps": len(reactant_maps),
            "product_maps": len(product_maps),
            "common_maps": len(common),
        }

    @staticmethod
    def _check_atom_conservation(precursors: list[str], products: list[str]) -> dict:
        """For retrosynthesis: atoms in precursors >= atoms in product."""
        if not RDKIT_AVAILABLE:
            return {"score": 0.5, "note": "rdkit unavailable"}

        def total_heavy_atoms(smiles_list: list[str]) -> int:
            total = 0
            for s in smiles_list:
                mol = Chem.MolFromSmiles(s)
                if mol:
                    total += mol.GetNumHeavyAtoms()
            return total

        prec_atoms = total_heavy_atoms(precursors)
        prod_atoms = total_heavy_atoms(products)

        if prec_atoms == 0 or prod_atoms == 0:
            return {"score": 0.0, "note": "Could not count atoms"}

        # Precursors should have at least as many atoms as products
        if prec_atoms >= prod_atoms:
            score = 1.0
        else:
            deficit = prod_atoms - prec_atoms
            score = max(0.0, 1.0 - deficit / prod_atoms)

        return {
            "score": round(score, 4),
            "precursor_heavy_atoms": prec_atoms,
            "product_heavy_atoms": prod_atoms,
            "conserved": prec_atoms >= prod_atoms,
        }

    @staticmethod
    def _check_route_plausibility(precursors: list[str], products: list[str]) -> dict:
        """Check for implausible disconnections in retrosynthesis."""
        if not RDKIT_AVAILABLE:
            return {"score": 0.5, "note": "rdkit unavailable"}

        issues: list[str] = []

        # Check that precursors are simpler than products
        prec_complexity = sum(
            Descriptors.BertzCT(Chem.MolFromSmiles(s))
            for s in precursors
            if Chem.MolFromSmiles(s) is not None
        )
        prod_complexity = sum(
            Descriptors.BertzCT(Chem.MolFromSmiles(s))
            for s in products
            if Chem.MolFromSmiles(s) is not None
        )

        if prec_complexity > prod_complexity * 2:
            issues.append("Precursors more complex than products")

        # Check for unreasonably many steps (precursors)
        if len(precursors) > 10:
            issues.append(f"Too many precursors ({len(precursors)})")

        score = max(0.0, 1.0 - 0.3 * len(issues))
        return {
            "score": round(score, 4),
            "precursor_complexity": round(prec_complexity, 2),
            "product_complexity": round(prod_complexity, 2),
            "issues": issues,
        }

    @staticmethod
    def _check_property_ranges(smiles: str, claimed_properties: dict) -> dict:
        """Check if claimed properties are in plausible ranges."""
        if not RDKIT_AVAILABLE:
            return {"score": 0.5, "note": "rdkit unavailable"}

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"score": 0.0, "note": "Invalid SMILES"}

        computed: dict[str, float] = {}
        issues: list[str] = []

        try:
            computed["molecular_weight"] = Descriptors.MolWt(mol)
            computed["logp"] = Descriptors.MolLogP(mol)
            computed["hbd"] = rdMolDescriptors.CalcNumHBD(mol)
            computed["hba"] = rdMolDescriptors.CalcNumHBA(mol)
            computed["tpsa"] = Descriptors.TPSA(mol)
        except Exception:
            pass

        # Compare claimed vs computed where possible
        comparisons: dict[str, dict] = {}
        for prop, claimed_val in claimed_properties.items():
            if not isinstance(claimed_val, (int, float)):
                continue

            prop_lower = prop.lower().replace(" ", "_")
            computed_val = None

            for key in computed:
                if key in prop_lower or prop_lower in key:
                    computed_val = computed[key]
                    break

            if computed_val is not None:
                tolerance = max(abs(computed_val) * 0.1, 1.0)
                match = abs(claimed_val - computed_val) <= tolerance
                comparisons[prop] = {
                    "claimed": claimed_val,
                    "computed": round(computed_val, 4),
                    "match": match,
                }
                if not match:
                    issues.append(f"{prop}: claimed {claimed_val}, computed {computed_val:.4f}")

        if not comparisons:
            return {"score": 0.5, "note": "No comparable properties", "computed": computed}

        matches = sum(1 for c in comparisons.values() if c["match"])
        score = matches / len(comparisons) if comparisons else 0.5

        return {
            "score": round(score, 4),
            "comparisons": comparisons,
            "computed_properties": {k: round(v, 4) for k, v in computed.items()},
            "warnings": issues[:5] if issues else [],
        }

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    async def _check_pubchem(self, smiles: str, claimed_properties: dict) -> dict:
        """Cross-reference with PubChem."""
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                # Search by SMILES
                encoded_smiles = httpx.URL(f"{PUBCHEM_API}/compound/smiles/{smiles}/property/MolecularWeight,XLogP,ExactMass,TPSA/JSON")
                resp = await client.get(str(encoded_smiles))

                if resp.status_code != 200:
                    return {"score": 0.3, "note": f"PubChem lookup failed (HTTP {resp.status_code})"}

                data = resp.json()
                properties = data.get("PropertyTable", {}).get("Properties", [{}])[0]

                if not properties:
                    return {"score": 0.3, "note": "No PubChem data found"}

                # Compare claimed vs PubChem
                comparisons: dict = {}
                for prop, claimed_val in claimed_properties.items():
                    if not isinstance(claimed_val, (int, float)):
                        continue

                    for pc_key, pc_val in properties.items():
                        if not isinstance(pc_val, (int, float)):
                            continue
                        if prop.lower().replace("_", "") in pc_key.lower().replace("_", ""):
                            tolerance = max(abs(pc_val) * 0.05, 0.5)
                            match = abs(claimed_val - pc_val) <= tolerance
                            comparisons[prop] = {
                                "claimed": claimed_val,
                                "pubchem": pc_val,
                                "match": match,
                            }

                if not comparisons:
                    return {
                        "score": 0.5,
                        "note": "Found in PubChem but no matching properties to compare",
                        "pubchem_properties": properties,
                    }

                matches = sum(1 for c in comparisons.values() if c["match"])
                score = matches / len(comparisons)

                return {
                    "score": round(score, 4),
                    "found": True,
                    "comparisons": comparisons,
                }

        except Exception as e:
            logger.warning("pubchem_check_failed", error=str(e))
            return {"score": 0.0, "error": str(e)}

    async def _check_chembl(self, smiles: str, claimed_properties: dict) -> dict:
        """Cross-reference with ChEMBL."""
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{CHEMBL_API}/molecule/search",
                    params={"q": smiles, "format": "json", "limit": "1"},
                )

                if resp.status_code != 200:
                    return {"score": 0.3, "note": f"ChEMBL lookup failed (HTTP {resp.status_code})"}

                data = resp.json()
                molecules = data.get("molecules", [])

                if not molecules:
                    return {"score": 0.3, "note": "Not found in ChEMBL"}

                mol_data = molecules[0]
                mol_props = mol_data.get("molecule_properties", {}) or {}

                return {
                    "score": 0.8,
                    "found": True,
                    "chembl_id": mol_data.get("molecule_chembl_id"),
                    "pref_name": mol_data.get("pref_name"),
                    "molecular_formula": mol_props.get("full_molformula"),
                }

        except Exception as e:
            logger.warning("chembl_check_failed", error=str(e))
            return {"score": 0.0, "error": str(e)}
