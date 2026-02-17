"""Computational biology verification: CPU-based structural validation.

Uses Biopython + numpy + DSSP to validate protein structures without GPU
re-prediction.  Checks physical plausibility (Ramachandran, clashes,
sequence–structure match, secondary structure) rather than re-folding.
Also validates RNA structures and protein structure comparisons via API.
"""
import asyncio
import json
import re
import tempfile
import textwrap
import time
from typing import Any
from pathlib import Path

import httpx

from backend.verification.base import (
    VerificationAdapter, VerificationResult, VerificationBadge,
)
from backend.logging_config import get_logger

logger = get_logger(__name__)

COMPBIO_IMAGE = "clawdlab/compbio-cpu:latest"
COMPBIO_TIMEOUT = 300  # 5 min — CPU validation is fast
VALID_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")
VALID_RNA_BASES = set("ACGU")

RFAM_API = "https://rfam.org/family"
RCSB_PDB_API = "https://data.rcsb.org/rest/v1/core/entry"
HTTP_TIMEOUT = 30

# Canonical + wobble base pairs for RNA
CANONICAL_PAIRS = {("A", "U"), ("U", "A"), ("G", "C"), ("C", "G"), ("G", "U"), ("U", "G")}


class CompBioAdapter(VerificationAdapter):
    domain = "computational_biology"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        claim_type = task_result.get("claim_type", "structure_prediction")

        if claim_type == "structure_prediction":
            return await self._verify_structure(task_result)
        elif claim_type == "protein_design":
            return await self._verify_design(task_result)
        elif claim_type == "binder_design":
            return await self._verify_binder(task_result)
        elif claim_type == "rna_structure":
            return await self._verify_rna_structure(task_result)
        elif claim_type == "structure_comparison":
            return await self._verify_structure_comparison(task_result)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    # ------------------------------------------------------------------
    # Structure prediction verification
    # ------------------------------------------------------------------

    async def _verify_structure(self, result: dict) -> VerificationResult:
        """Validate a claimed protein structure using CPU-based checks."""
        start = time.monotonic()

        sequence = result.get("sequence", "")
        if not sequence or not self._valid_sequence(sequence):
            return VerificationResult.fail(self.domain, ["Invalid or missing protein sequence"])

        claimed_pdb = result.get("claimed_structure_pdb")
        if not claimed_pdb:
            return VerificationResult.fail(self.domain, ["No claimed_structure_pdb provided"])

        claimed_plddt = result.get("claimed_plddt")
        claimed_ptm = result.get("claimed_ptm")

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "input.fasta").write_text(f">query\n{sequence}\n")
            Path(tmpdir, "claimed.pdb").write_text(claimed_pdb)
            Path(tmpdir, "params.json").write_text(json.dumps({
                "mode": "structure",
                "claimed_plddt": claimed_plddt,
                "claimed_ptm": claimed_ptm,
            }))
            Path(tmpdir, "verify.py").write_text(self._build_verification_script())

            metrics, error = await self._run_container(tmpdir)

        elapsed = time.monotonic() - start

        if error:
            return VerificationResult.fail(self.domain, [error])

        # Weighted scoring (6 components)
        weights = {
            "parsability": 0.15,
            "ramachandran": 0.25,
            "clashes": 0.20,
            "seq_match": 0.15,
            "dssp": 0.15,
            "metrics_plausibility": 0.10,
        }
        component_scores = metrics.get("component_scores", {})
        score = sum(
            weights.get(k, 0) * component_scores.get(k, 0.0)
            for k in weights
        )
        score = min(1.0, round(score, 4))

        critical_fail = (
            component_scores.get("parsability", 0) < 0.5
            or component_scores.get("clashes", 0) < 0.2
        )
        passed = score >= 0.5 and not critical_fail

        return VerificationResult(
            passed=passed,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details={
                "claim_type": "structure_prediction",
                "sequence_length": len(sequence),
                "component_scores": component_scores,
                "metrics": metrics.get("raw_metrics", {}),
            },
            warnings=metrics.get("warnings", []),
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Protein design verification
    # ------------------------------------------------------------------

    async def _verify_design(self, result: dict) -> VerificationResult:
        """Validate a protein design: sequence validity + backbone quality."""
        start = time.monotonic()

        designed_seq = result.get("designed_sequence", "")
        backbone_pdb = result.get("backbone_pdb")

        if not designed_seq or not self._valid_sequence(designed_seq):
            return VerificationResult.fail(self.domain, ["Invalid designed_sequence"])
        if not backbone_pdb:
            return VerificationResult.fail(self.domain, ["backbone_pdb required for design verification"])

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "sequence.fasta").write_text(f">designed\n{designed_seq}\n")
            Path(tmpdir, "backbone.pdb").write_text(backbone_pdb)
            Path(tmpdir, "params.json").write_text(json.dumps({
                "mode": "design",
            }))
            Path(tmpdir, "verify.py").write_text(self._build_verification_script())

            metrics, error = await self._run_container(tmpdir)

        elapsed = time.monotonic() - start

        if error:
            return VerificationResult.fail(self.domain, [error])

        weights = {
            "seq_validity": 0.10,
            "parsability": 0.15,
            "ramachandran": 0.25,
            "clashes": 0.20,
            "seq_backbone_compat": 0.15,
            "dssp": 0.15,
        }
        component_scores = metrics.get("component_scores", {})
        score = sum(
            weights.get(k, 0) * component_scores.get(k, 0.0)
            for k in weights
        )
        score = min(1.0, round(score, 4))

        critical_fail = (
            component_scores.get("parsability", 0) < 0.5
            or component_scores.get("clashes", 0) < 0.2
        )
        passed = score >= 0.5 and not critical_fail

        return VerificationResult(
            passed=passed,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details={
                "claim_type": "protein_design",
                "sequence_length": len(designed_seq),
                "component_scores": component_scores,
                "metrics": metrics.get("raw_metrics", {}),
            },
            warnings=metrics.get("warnings", []),
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Binder design verification
    # ------------------------------------------------------------------

    async def _verify_binder(self, result: dict) -> VerificationResult:
        """Validate binder design: design checks + interface contacts."""
        start = time.monotonic()

        designed_seq = result.get("designed_sequence", "")
        backbone_pdb = result.get("backbone_pdb")

        if not designed_seq or not self._valid_sequence(designed_seq):
            return VerificationResult.fail(self.domain, ["Invalid designed_sequence"])
        if not backbone_pdb:
            return VerificationResult.fail(self.domain, ["backbone_pdb required for binder verification"])

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "sequence.fasta").write_text(f">designed\n{designed_seq}\n")
            Path(tmpdir, "backbone.pdb").write_text(backbone_pdb)
            Path(tmpdir, "params.json").write_text(json.dumps({
                "mode": "binder",
            }))
            Path(tmpdir, "verify.py").write_text(self._build_verification_script())

            metrics, error = await self._run_container(tmpdir)

        elapsed = time.monotonic() - start

        if error:
            return VerificationResult.fail(self.domain, [error])

        weights = {
            "seq_validity": 0.10,
            "parsability": 0.10,
            "ramachandran": 0.20,
            "clashes": 0.15,
            "seq_backbone_compat": 0.10,
            "dssp": 0.10,
            "interface": 0.25,
        }
        component_scores = metrics.get("component_scores", {})
        score = sum(
            weights.get(k, 0) * component_scores.get(k, 0.0)
            for k in weights
        )
        score = min(1.0, round(score, 4))

        critical_fail = (
            component_scores.get("parsability", 0) < 0.5
            or component_scores.get("interface", 0) < 0.1
        )
        passed = score >= 0.5 and not critical_fail

        return VerificationResult(
            passed=passed,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details={
                "claim_type": "binder_design",
                "sequence_length": len(designed_seq),
                "component_scores": component_scores,
                "metrics": metrics.get("raw_metrics", {}),
            },
            warnings=metrics.get("warnings", []),
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # RNA structure verification (API-based, no Docker)
    # ------------------------------------------------------------------

    async def _verify_rna_structure(self, result: dict) -> VerificationResult:
        """Validate RNA secondary structure claims."""
        start = time.monotonic()

        rna_sequence = result.get("rna_sequence", "")
        dot_bracket = result.get("dot_bracket", "")
        claimed_mfe = result.get("claimed_mfe")
        rfam_family = result.get("rfam_family", "")

        if not rna_sequence:
            return VerificationResult.fail(self.domain, ["rna_sequence required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "rna_structure"}

        # Component 1: sequence_valid (0.15)
        seq_result = self._check_rna_sequence_valid(rna_sequence)
        component_scores["sequence_valid"] = seq_result["score"]
        details["sequence_valid"] = seq_result

        # Component 2: dot_bracket_valid (0.25)
        db_result = self._check_dot_bracket_valid(dot_bracket, rna_sequence)
        component_scores["dot_bracket_valid"] = db_result["score"]
        details["dot_bracket_valid"] = db_result

        # Component 3: base_pairs_valid (0.25)
        bp_result = self._check_base_pairs_valid(rna_sequence, dot_bracket)
        component_scores["base_pairs_valid"] = bp_result["score"]
        details["base_pairs_valid"] = bp_result

        # Component 4: energy_plausible (0.20)
        energy_result = self._check_energy_plausible(rna_sequence, claimed_mfe)
        component_scores["energy_plausible"] = energy_result["score"]
        details["energy_plausible"] = energy_result

        # Component 5: database_match (0.15)
        db_match = await self._check_rfam_match(rfam_family)
        component_scores["database_match"] = db_match["score"]
        details["database_match"] = db_match

        weights = {
            "sequence_valid": 0.15,
            "dot_bracket_valid": 0.25,
            "base_pairs_valid": 0.25,
            "energy_plausible": 0.20,
            "database_match": 0.15,
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
    # Structure comparison verification (API-based, no Docker)
    # ------------------------------------------------------------------

    async def _verify_structure_comparison(self, result: dict) -> VerificationResult:
        """Validate protein structure comparison claims (RMSD, TM-score)."""
        start = time.monotonic()

        pdb_id_1 = result.get("pdb_id_1", "")
        pdb_id_2 = result.get("pdb_id_2", "")
        claimed_rmsd = result.get("claimed_rmsd")
        claimed_tm_score = result.get("claimed_tm_score")
        aligned_residues = result.get("aligned_residues")

        if not pdb_id_1 or not pdb_id_2:
            return VerificationResult.fail(self.domain, ["pdb_id_1 and pdb_id_2 required"])

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"claim_type": "structure_comparison"}

        # Component 1: pdb_ids_valid (0.20)
        pdb_result = await self._check_pdb_ids_valid(pdb_id_1, pdb_id_2)
        component_scores["pdb_ids_valid"] = pdb_result["score"]
        details["pdb_ids_valid"] = pdb_result

        # Component 2: rmsd_plausible (0.25)
        rmsd_result = self._check_rmsd_plausible(claimed_rmsd)
        component_scores["rmsd_plausible"] = rmsd_result["score"]
        details["rmsd_plausible"] = rmsd_result

        # Component 3: alignment_length (0.25)
        align_result = await self._check_alignment_length(
            pdb_id_1, pdb_id_2, aligned_residues,
        )
        component_scores["alignment_length"] = align_result["score"]
        details["alignment_length"] = align_result

        # Component 4: tm_score_plausible (0.30)
        tm_result = self._check_tm_score_plausible(claimed_tm_score, claimed_rmsd)
        component_scores["tm_score_plausible"] = tm_result["score"]
        details["tm_score_plausible"] = tm_result

        weights = {
            "pdb_ids_valid": 0.20,
            "rmsd_plausible": 0.25,
            "alignment_length": 0.25,
            "tm_score_plausible": 0.30,
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
    # RNA structure helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_rna_sequence_valid(seq: str) -> dict:
        upper = seq.upper()
        invalid = [b for b in upper if b not in VALID_RNA_BASES]
        if invalid:
            return {"score": 0.0, "error": f"Invalid bases: {''.join(set(invalid))}", "length": len(upper)}
        return {"score": 1.0, "valid": True, "length": len(upper)}

    @staticmethod
    def _check_dot_bracket_valid(dot_bracket: str, sequence: str) -> dict:
        if not dot_bracket:
            return {"score": 0.5, "note": "No dot-bracket notation provided"}

        if len(dot_bracket) != len(sequence):
            return {
                "score": 0.0,
                "error": f"Length mismatch: sequence={len(sequence)}, dot_bracket={len(dot_bracket)}",
            }

        # Check balanced parentheses
        stack: list[int] = []
        for i, ch in enumerate(dot_bracket):
            if ch == "(":
                stack.append(i)
            elif ch == ")":
                if not stack:
                    return {"score": 0.0, "error": f"Unmatched ')' at position {i}"}
                stack.pop()
            elif ch != ".":
                return {"score": 0.0, "error": f"Invalid character '{ch}' at position {i}"}

        if stack:
            return {"score": 0.0, "error": f"Unmatched '(' at positions {stack[:5]}"}

        n_pairs = dot_bracket.count("(")
        return {"score": 1.0, "valid": True, "n_base_pairs": n_pairs, "length": len(dot_bracket)}

    @staticmethod
    def _check_base_pairs_valid(sequence: str, dot_bracket: str) -> dict:
        if not dot_bracket or not sequence or len(dot_bracket) != len(sequence):
            return {"score": 0.5, "note": "Cannot check base pairs"}

        upper = sequence.upper()
        stack: list[int] = []
        canonical = 0
        non_canonical = 0

        for i, ch in enumerate(dot_bracket):
            if ch == "(":
                stack.append(i)
            elif ch == ")" and stack:
                j = stack.pop()
                pair = (upper[j], upper[i])
                if pair in CANONICAL_PAIRS:
                    canonical += 1
                else:
                    non_canonical += 1

        total = canonical + non_canonical
        if total == 0:
            return {"score": 0.5, "note": "No base pairs"}

        score = canonical / total
        return {
            "score": round(score, 4),
            "canonical": canonical,
            "non_canonical": non_canonical,
            "total_pairs": total,
        }

    @staticmethod
    def _check_energy_plausible(sequence: str, claimed_mfe: float | None) -> dict:
        if claimed_mfe is None:
            return {"score": 0.5, "note": "No MFE claimed"}

        seq_len = len(sequence)
        # Empirical: MFE scales roughly linearly with length
        # Typical range: -0.3 to -1.5 kcal/mol per nucleotide for structured RNAs
        min_expected = -1.5 * seq_len
        max_expected = 0.0  # unfolded

        if min_expected <= claimed_mfe <= max_expected:
            return {"score": 1.0, "plausible": True, "claimed_mfe": claimed_mfe}
        elif claimed_mfe > 0:
            return {"score": 0.0, "error": "Positive MFE is thermodynamically implausible"}
        elif claimed_mfe < min_expected * 2:
            return {"score": 0.2, "note": "MFE unusually low for sequence length"}
        return {"score": 0.5, "note": "MFE borderline", "claimed_mfe": claimed_mfe}

    async def _check_rfam_match(self, rfam_family: str) -> dict:
        if not rfam_family:
            return {"score": 0.5, "note": "No Rfam family ID provided"}

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{RFAM_API}/{rfam_family}",
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "score": 1.0,
                        "found": True,
                        "family_name": data.get("rfam", {}).get("id", rfam_family),
                    }
                return {"score": 0.0, "found": False}
        except Exception as e:
            logger.warning("rfam_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    # ------------------------------------------------------------------
    # Structure comparison helpers
    # ------------------------------------------------------------------

    async def _check_pdb_ids_valid(self, pdb_id_1: str, pdb_id_2: str) -> dict:
        valid = 0
        checked_ids = {}
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                for pdb_id in [pdb_id_1, pdb_id_2]:
                    resp = await client.get(f"{RCSB_PDB_API}/{pdb_id.upper()}")
                    if resp.status_code == 200:
                        valid += 1
                        checked_ids[pdb_id] = True
                    else:
                        checked_ids[pdb_id] = False

            score = valid / 2.0
            return {"score": round(score, 4), "ids": checked_ids}
        except Exception as e:
            logger.warning("pdb_ids_check_failed", error=str(e))
            return {"score": 0.3, "error": str(e)}

    @staticmethod
    def _check_rmsd_plausible(claimed_rmsd: float | None) -> dict:
        if claimed_rmsd is None:
            return {"score": 0.5, "note": "No RMSD claimed"}

        if not isinstance(claimed_rmsd, (int, float)) or claimed_rmsd < 0:
            return {"score": 0.0, "error": "RMSD must be non-negative"}

        # Typical RMSD ranges:
        # 0-2 Å: very similar structures
        # 2-5 Å: same fold, different conformations
        # 5-10 Å: related folds
        # >10 Å: different folds
        if 0 <= claimed_rmsd <= 30:
            return {"score": 1.0, "plausible": True, "rmsd": claimed_rmsd}
        return {"score": 0.2, "plausible": False, "rmsd": claimed_rmsd}

    async def _check_alignment_length(
        self, pdb_id_1: str, pdb_id_2: str, aligned_residues: int | None,
    ) -> dict:
        if aligned_residues is None:
            return {"score": 0.5, "note": "No aligned residues count"}

        try:
            # Fetch polymer entity counts from RCSB
            lengths = []
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                for pdb_id in [pdb_id_1, pdb_id_2]:
                    resp = await client.get(f"{RCSB_PDB_API}/{pdb_id.upper()}")
                    if resp.status_code == 200:
                        data = resp.json()
                        # Get deposited model count or polymer entity count
                        struct = data.get("struct", {})
                        n_res = data.get("rcsb_entry_info", {}).get("deposited_polymer_monomer_count", 0)
                        if n_res:
                            lengths.append(n_res)

            if len(lengths) < 2:
                # Just check plausibility
                if aligned_residues > 0:
                    return {"score": 0.7, "note": "Could not verify against PDB lengths"}
                return {"score": 0.3, "error": "Zero aligned residues"}

            shorter = min(lengths)
            fraction = aligned_residues / shorter if shorter > 0 else 0

            # Alignment should cover reasonable fraction of shorter chain
            if fraction >= 0.5:
                return {"score": 1.0, "fraction": round(fraction, 3), "shorter_chain": shorter}
            elif fraction >= 0.2:
                return {"score": 0.5, "fraction": round(fraction, 3)}
            return {"score": 0.2, "fraction": round(fraction, 3)}

        except Exception as e:
            logger.warning("alignment_length_check_failed", error=str(e))
            return {"score": 0.5, "error": str(e)}

    @staticmethod
    def _check_tm_score_plausible(
        claimed_tm: float | None, claimed_rmsd: float | None,
    ) -> dict:
        if claimed_tm is None:
            return {"score": 0.5, "note": "No TM-score claimed"}

        if not isinstance(claimed_tm, (int, float)):
            return {"score": 0.0, "error": "TM-score must be numeric"}

        if not (0 <= claimed_tm <= 1):
            return {"score": 0.0, "error": f"TM-score {claimed_tm} must be in [0, 1]"}

        # Consistency with RMSD: high TM-score should correlate with low RMSD
        if claimed_rmsd is not None and isinstance(claimed_rmsd, (int, float)):
            # High TM + high RMSD is suspicious
            if claimed_tm > 0.8 and claimed_rmsd > 10:
                return {
                    "score": 0.2,
                    "note": "High TM-score inconsistent with high RMSD",
                    "tm_score": claimed_tm,
                    "rmsd": claimed_rmsd,
                }
            # Low TM + low RMSD is suspicious
            if claimed_tm < 0.3 and claimed_rmsd < 1:
                return {
                    "score": 0.2,
                    "note": "Low TM-score inconsistent with low RMSD",
                    "tm_score": claimed_tm,
                    "rmsd": claimed_rmsd,
                }

        return {"score": 1.0, "plausible": True, "tm_score": claimed_tm}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _valid_sequence(self, seq: str) -> bool:
        return len(seq) > 0 and all(aa.upper() in VALID_AMINO_ACIDS for aa in seq)

    async def _run_container(self, tmpdir: str) -> tuple[dict, str | None]:
        """Run verification script in Docker container. Returns (metrics, error)."""
        cmd = [
            "docker", "run", "--rm",
            "--memory=2g", "--cpus=2",
            "--network=none",
            "-v", f"{tmpdir}:/workspace:ro",
            COMPBIO_IMAGE,
            "python3", "/workspace/verify.py",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=COMPBIO_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return {}, "Verification timed out"

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace")[:500]
            return {}, f"Container failed: {err_msg}"

        try:
            metrics = json.loads(stdout.decode())
        except json.JSONDecodeError:
            return {}, "Failed to parse verification output as JSON"

        return metrics, None

    def _build_verification_script(self) -> str:
        """Generate the Python script that runs inside the container."""
        return textwrap.dedent('''\
            #!/usr/bin/env python3
            """CPU-based protein structure validation.

            Reads params.json for mode + claimed metrics.
            Outputs JSON with component_scores, raw_metrics, warnings.
            """
            import json
            import math
            import sys
            import warnings as _warnings
            from pathlib import Path

            import numpy as np

            _warnings.filterwarnings("ignore")

            # ---- Biopython imports ----
            from Bio.PDB import PDBParser, PPBuilder
            from Bio.PDB.Polypeptide import three_to_one

            THREE_TO_ONE = {
                "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F",
                "GLY": "G", "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L",
                "MET": "M", "ASN": "N", "PRO": "P", "GLN": "Q", "ARG": "R",
                "SER": "S", "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y",
            }
            VALID_AA = set(THREE_TO_ONE.values())

            params = json.loads(Path("/workspace/params.json").read_text())
            mode = params.get("mode", "structure")

            component_scores = {}
            raw_metrics = {}
            warnings_list = []

            # ============================================================
            # Helper: parse PDB and extract basic info
            # ============================================================
            def parse_pdb(pdb_path):
                """Parse PDB, return (structure, residues, atoms) or raise."""
                parser = PDBParser(QUIET=True)
                structure = parser.get_structure("s", pdb_path)
                models = list(structure.get_models())
                if not models:
                    raise ValueError("No models in PDB")
                model = models[0]
                chains = list(model.get_chains())
                if not chains:
                    raise ValueError("No chains in PDB")
                residues = []
                for chain in chains:
                    for res in chain.get_residues():
                        if res.get_id()[0] == " ":  # standard residues only
                            residues.append(res)
                atoms = list(model.get_atoms())
                return structure, model, chains, residues, atoms

            # ============================================================
            # Check 1: PDB parsability + completeness
            # ============================================================
            def check_parsability(pdb_path):
                try:
                    structure, model, chains, residues, atoms = parse_pdb(pdb_path)
                    n_res = len(residues)
                    n_atoms = len(atoms)
                    if n_res == 0:
                        return 0.0, {"n_residues": 0, "n_atoms": 0}
                    # Check backbone completeness (N, CA, C atoms)
                    backbone_complete = 0
                    for res in residues:
                        atom_names = {a.get_name() for a in res.get_atoms()}
                        if {"N", "CA", "C"}.issubset(atom_names):
                            backbone_complete += 1
                    completeness = backbone_complete / n_res
                    score = completeness  # 1.0 if all residues have full backbone
                    return score, {
                        "n_residues": n_res,
                        "n_atoms": n_atoms,
                        "n_chains": len(chains),
                        "backbone_completeness": round(completeness, 3),
                    }
                except Exception as e:
                    return 0.0, {"error": str(e)}

            # ============================================================
            # Check 2: Ramachandran plot quality
            # ============================================================
            def check_ramachandran(pdb_path):
                try:
                    parser = PDBParser(QUIET=True)
                    structure = parser.get_structure("s", pdb_path)
                    ppb = PPBuilder()
                    phi_psi_list = []
                    for pp in ppb.build_peptides(structure):
                        for phi, psi in pp.get_phi_psi_list():
                            if phi is not None and psi is not None:
                                phi_psi_list.append((math.degrees(phi), math.degrees(psi)))

                    if not phi_psi_list:
                        return 0.0, {"n_angles": 0}

                    # Favoured regions (simplified):
                    # Alpha-helix: phi ~ -60, psi ~ -47 (± 30)
                    # Beta-sheet:  phi ~ -120, psi ~ 130 (± 30)
                    # Left-alpha:  phi ~ 60,  psi ~ 40  (± 30)
                    favoured = 0
                    allowed = 0
                    for phi, psi in phi_psi_list:
                        if _in_region(phi, psi, -60, -47, 30):
                            favoured += 1
                        elif _in_region(phi, psi, -120, 130, 30):
                            favoured += 1
                        elif _in_region(phi, psi, 60, 40, 30):
                            favoured += 1
                        elif _in_region(phi, psi, -60, -47, 50):
                            allowed += 1
                        elif _in_region(phi, psi, -120, 130, 50):
                            allowed += 1
                        elif _in_region(phi, psi, 60, 40, 50):
                            allowed += 1

                    n = len(phi_psi_list)
                    frac_favoured = favoured / n
                    frac_allowed = (favoured + allowed) / n

                    # Score: 1.0 if >=90% favoured, linearly down
                    score = min(1.0, frac_favoured / 0.9)

                    return score, {
                        "n_angles": n,
                        "frac_favoured": round(frac_favoured, 3),
                        "frac_allowed": round(frac_allowed, 3),
                    }
                except Exception as e:
                    return 0.0, {"error": str(e)}

            def _in_region(phi, psi, phi_c, psi_c, tol):
                """Check if (phi, psi) is within tol degrees of center."""
                dphi = abs(phi - phi_c)
                dphi = min(dphi, 360 - dphi)  # wrap around
                dpsi = abs(psi - psi_c)
                dpsi = min(dpsi, 360 - dpsi)
                return dphi <= tol and dpsi <= tol

            # ============================================================
            # Check 3: Steric clashes
            # ============================================================
            def check_clashes(pdb_path):
                try:
                    _, model, _, residues, atoms = parse_pdb(pdb_path)
                    if len(atoms) < 2:
                        return 0.0, {"error": "Too few atoms"}

                    # Build array of CA coordinates for inter-residue distances
                    ca_coords = []
                    for res in residues:
                        ca = res["CA"] if "CA" in res else None
                        if ca is not None:
                            ca_coords.append(ca.get_vector().get_array())

                    if len(ca_coords) < 2:
                        return 0.0, {"n_ca": 0}

                    ca_coords = np.array(ca_coords)
                    # Compute pairwise distances
                    diff = ca_coords[:, None, :] - ca_coords[None, :, :]
                    dists = np.sqrt((diff ** 2).sum(axis=-1))

                    # Check for severe clashes (CA-CA < 2.0 Å for non-adjacent)
                    n = len(ca_coords)
                    severe_clashes = 0
                    mild_clashes = 0
                    for i in range(n):
                        for j in range(i + 2, n):  # skip adjacent
                            d = dists[i, j]
                            if d < 2.0:
                                severe_clashes += 1
                            elif d < 3.0:
                                mild_clashes += 1

                    n_pairs = max(1, n * (n - 1) // 2 - (n - 1))
                    clash_frac = (severe_clashes * 3 + mild_clashes) / n_pairs

                    # Score: 1.0 if no clashes, drops with clash fraction
                    score = max(0.0, 1.0 - clash_frac * 50)

                    return score, {
                        "n_ca": n,
                        "severe_clashes": severe_clashes,
                        "mild_clashes": mild_clashes,
                        "clash_fraction": round(clash_frac, 6),
                    }
                except Exception as e:
                    return 0.0, {"error": str(e)}

            # ============================================================
            # Check 4: Sequence–structure match
            # ============================================================
            def check_seq_match(fasta_path, pdb_path):
                try:
                    # Read FASTA sequence
                    lines = Path(fasta_path).read_text().strip().split("\\n")
                    fasta_seq = "".join(l.strip() for l in lines if not l.startswith(">")).upper()

                    # Extract sequence from PDB residues
                    _, _, _, residues, _ = parse_pdb(pdb_path)
                    pdb_seq = ""
                    for res in residues:
                        resname = res.get_resname().strip()
                        aa = THREE_TO_ONE.get(resname, "X")
                        pdb_seq += aa

                    if not fasta_seq or not pdb_seq:
                        return 0.0, {"fasta_len": len(fasta_seq), "pdb_len": len(pdb_seq)}

                    # Simple identity: compare overlapping portion
                    min_len = min(len(fasta_seq), len(pdb_seq))
                    max_len = max(len(fasta_seq), len(pdb_seq))
                    matches = sum(
                        1 for a, b in zip(fasta_seq[:min_len], pdb_seq[:min_len])
                        if a == b
                    )
                    identity = matches / max_len if max_len > 0 else 0

                    # Length ratio penalty
                    len_ratio = min_len / max_len if max_len > 0 else 0

                    score = identity * 0.7 + len_ratio * 0.3

                    return score, {
                        "fasta_len": len(fasta_seq),
                        "pdb_len": len(pdb_seq),
                        "identity": round(identity, 3),
                        "length_ratio": round(len_ratio, 3),
                    }
                except Exception as e:
                    return 0.0, {"error": str(e)}

            # ============================================================
            # Check 5: Secondary structure (DSSP)
            # ============================================================
            def check_dssp(pdb_path):
                try:
                    import subprocess
                    # Try mkdssp (Debian/Ubuntu package name)
                    for dssp_cmd in ["mkdssp", "dssp"]:
                        try:
                            proc = subprocess.run(
                                [dssp_cmd, "-i", pdb_path],
                                capture_output=True, text=True, timeout=60,
                            )
                            if proc.returncode == 0:
                                break
                        except FileNotFoundError:
                            continue
                    else:
                        return 0.5, {"note": "DSSP not available, neutral score"}

                    # Parse DSSP output — count H (helix), E (sheet), others
                    lines = proc.stdout.split("\\n")
                    in_residues = False
                    ss_counts = {"H": 0, "E": 0, "T": 0, "S": 0, "G": 0, "B": 0, "I": 0, " ": 0}
                    total = 0
                    for line in lines:
                        if line.strip().startswith("#"):
                            in_residues = True
                            continue
                        if in_residues and len(line) > 16:
                            ss = line[16] if len(line) > 16 else " "
                            if ss in ss_counts:
                                ss_counts[ss] += 1
                            else:
                                ss_counts[" "] += 1
                            total += 1

                    if total == 0:
                        return 0.5, {"note": "No residues parsed from DSSP"}

                    helix_frac = ss_counts["H"] / total
                    sheet_frac = ss_counts["E"] / total
                    structured_frac = (ss_counts["H"] + ss_counts["E"] + ss_counts["G"] + ss_counts["B"]) / total

                    # A reasonable protein should have some secondary structure
                    # Score based on having a balanced structural content
                    if structured_frac >= 0.3:
                        score = 1.0
                    elif structured_frac >= 0.15:
                        score = 0.7
                    elif structured_frac > 0.0:
                        score = 0.4
                    else:
                        score = 0.2

                    return score, {
                        "helix_fraction": round(helix_frac, 3),
                        "sheet_fraction": round(sheet_frac, 3),
                        "structured_fraction": round(structured_frac, 3),
                        "total_residues": total,
                    }
                except Exception as e:
                    return 0.5, {"note": f"DSSP failed: {e}"}

            # ============================================================
            # Check 6: Claimed metrics plausibility
            # ============================================================
            def check_metrics_plausibility(claimed_plddt, claimed_ptm):
                issues = []
                score = 1.0

                if claimed_plddt is not None:
                    if not (0 <= claimed_plddt <= 100):
                        issues.append(f"pLDDT {claimed_plddt} outside [0,100]")
                        score -= 0.5
                    elif claimed_plddt > 95:
                        issues.append(f"pLDDT {claimed_plddt} suspiciously high")
                        score -= 0.2

                if claimed_ptm is not None:
                    if not (0 <= claimed_ptm <= 1):
                        issues.append(f"pTM {claimed_ptm} outside [0,1]")
                        score -= 0.5
                    elif claimed_ptm > 0.95:
                        issues.append(f"pTM {claimed_ptm} suspiciously high")
                        score -= 0.2

                score = max(0.0, score)

                if claimed_plddt is None and claimed_ptm is None:
                    return 0.5, {"note": "No claimed metrics to check"}

                return score, {"issues": issues}

            # ============================================================
            # Check: Interface contacts (binder mode)
            # ============================================================
            def check_interface(pdb_path):
                try:
                    _, model, chains, _, _ = parse_pdb(pdb_path)
                    chain_list = list(chains)
                    if len(chain_list) < 2:
                        return 0.0, {"error": "Binder PDB must have >= 2 chains"}

                    # Get CA atoms per chain
                    chain_a_cas = []
                    chain_b_cas = []
                    for res in chain_list[0].get_residues():
                        if res.get_id()[0] == " " and "CA" in res:
                            chain_a_cas.append(res["CA"].get_vector().get_array())
                    for res in chain_list[1].get_residues():
                        if res.get_id()[0] == " " and "CA" in res:
                            chain_b_cas.append(res["CA"].get_vector().get_array())

                    if not chain_a_cas or not chain_b_cas:
                        return 0.0, {"error": "Empty chain(s)"}

                    a = np.array(chain_a_cas)
                    b = np.array(chain_b_cas)

                    # Compute inter-chain distances
                    diff = a[:, None, :] - b[None, :, :]
                    dists = np.sqrt((diff ** 2).sum(axis=-1))

                    # Interface residues: any pair within 8 Å
                    contact_mask = dists < 8.0
                    a_contacts = contact_mask.any(axis=1).sum()
                    b_contacts = contact_mask.any(axis=0).sum()
                    total_contacts = int(contact_mask.sum())

                    # Score: need substantial interface
                    min_interface = min(a_contacts, b_contacts)
                    if min_interface >= 10:
                        score = 1.0
                    elif min_interface >= 5:
                        score = 0.7
                    elif min_interface >= 2:
                        score = 0.4
                    else:
                        score = 0.1

                    return score, {
                        "chain_a_contacts": int(a_contacts),
                        "chain_b_contacts": int(b_contacts),
                        "total_contact_pairs": total_contacts,
                        "chain_a_residues": len(chain_a_cas),
                        "chain_b_residues": len(chain_b_cas),
                    }
                except Exception as e:
                    return 0.0, {"error": str(e)}

            # ============================================================
            # Sequence validity check (design/binder modes)
            # ============================================================
            def check_seq_validity(fasta_path):
                try:
                    lines = Path(fasta_path).read_text().strip().split("\\n")
                    seq = "".join(l.strip() for l in lines if not l.startswith(">")).upper()
                    if not seq:
                        return 0.0, {"length": 0}
                    invalid = [aa for aa in seq if aa not in VALID_AA]
                    frac_valid = (len(seq) - len(invalid)) / len(seq)
                    score = 1.0 if frac_valid == 1.0 else frac_valid * 0.5
                    return score, {
                        "length": len(seq),
                        "invalid_residues": len(invalid),
                        "fraction_valid": round(frac_valid, 3),
                    }
                except Exception as e:
                    return 0.0, {"error": str(e)}

            # ============================================================
            # Sequence–backbone compatibility (design/binder modes)
            # ============================================================
            def check_seq_backbone_compat(fasta_path, pdb_path):
                try:
                    lines = Path(fasta_path).read_text().strip().split("\\n")
                    seq = "".join(l.strip() for l in lines if not l.startswith(">")).upper()
                    _, _, _, residues, _ = parse_pdb(pdb_path)
                    n_res = len(residues)
                    n_seq = len(seq)
                    if n_res == 0 or n_seq == 0:
                        return 0.0, {"seq_len": n_seq, "backbone_residues": n_res}
                    ratio = min(n_seq, n_res) / max(n_seq, n_res)
                    score = ratio  # 1.0 if exact match
                    return score, {
                        "seq_len": n_seq,
                        "backbone_residues": n_res,
                        "length_ratio": round(ratio, 3),
                    }
                except Exception as e:
                    return 0.0, {"error": str(e)}

            # ============================================================
            # MAIN
            # ============================================================
            try:
                if mode == "structure":
                    pdb_path = "/workspace/claimed.pdb"
                    fasta_path = "/workspace/input.fasta"

                    s1, m1 = check_parsability(pdb_path)
                    component_scores["parsability"] = s1
                    raw_metrics["parsability"] = m1

                    s2, m2 = check_ramachandran(pdb_path)
                    component_scores["ramachandran"] = s2
                    raw_metrics["ramachandran"] = m2

                    s3, m3 = check_clashes(pdb_path)
                    component_scores["clashes"] = s3
                    raw_metrics["clashes"] = m3

                    s4, m4 = check_seq_match(fasta_path, pdb_path)
                    component_scores["seq_match"] = s4
                    raw_metrics["seq_match"] = m4

                    s5, m5 = check_dssp(pdb_path)
                    component_scores["dssp"] = s5
                    raw_metrics["dssp"] = m5

                    s6, m6 = check_metrics_plausibility(
                        params.get("claimed_plddt"),
                        params.get("claimed_ptm"),
                    )
                    component_scores["metrics_plausibility"] = s6
                    raw_metrics["metrics_plausibility"] = m6

                elif mode == "design":
                    pdb_path = "/workspace/backbone.pdb"
                    fasta_path = "/workspace/sequence.fasta"

                    sv, mv = check_seq_validity(fasta_path)
                    component_scores["seq_validity"] = sv
                    raw_metrics["seq_validity"] = mv

                    s1, m1 = check_parsability(pdb_path)
                    component_scores["parsability"] = s1
                    raw_metrics["parsability"] = m1

                    s2, m2 = check_ramachandran(pdb_path)
                    component_scores["ramachandran"] = s2
                    raw_metrics["ramachandran"] = m2

                    s3, m3 = check_clashes(pdb_path)
                    component_scores["clashes"] = s3
                    raw_metrics["clashes"] = m3

                    sc, mc = check_seq_backbone_compat(fasta_path, pdb_path)
                    component_scores["seq_backbone_compat"] = sc
                    raw_metrics["seq_backbone_compat"] = mc

                    s5, m5 = check_dssp(pdb_path)
                    component_scores["dssp"] = s5
                    raw_metrics["dssp"] = m5

                elif mode == "binder":
                    pdb_path = "/workspace/backbone.pdb"
                    fasta_path = "/workspace/sequence.fasta"

                    sv, mv = check_seq_validity(fasta_path)
                    component_scores["seq_validity"] = sv
                    raw_metrics["seq_validity"] = mv

                    s1, m1 = check_parsability(pdb_path)
                    component_scores["parsability"] = s1
                    raw_metrics["parsability"] = m1

                    s2, m2 = check_ramachandran(pdb_path)
                    component_scores["ramachandran"] = s2
                    raw_metrics["ramachandran"] = m2

                    s3, m3 = check_clashes(pdb_path)
                    component_scores["clashes"] = s3
                    raw_metrics["clashes"] = m3

                    sc, mc = check_seq_backbone_compat(fasta_path, pdb_path)
                    component_scores["seq_backbone_compat"] = sc
                    raw_metrics["seq_backbone_compat"] = mc

                    s5, m5 = check_dssp(pdb_path)
                    component_scores["dssp"] = s5
                    raw_metrics["dssp"] = m5

                    si, mi = check_interface(pdb_path)
                    component_scores["interface"] = si
                    raw_metrics["interface"] = mi

                else:
                    print(json.dumps({"error": f"Unknown mode: {mode}"}))
                    sys.exit(1)

                print(json.dumps({
                    "component_scores": component_scores,
                    "raw_metrics": raw_metrics,
                    "warnings": warnings_list,
                }))
            except Exception as e:
                print(json.dumps({"error": str(e)}))
                sys.exit(1)
        ''')
