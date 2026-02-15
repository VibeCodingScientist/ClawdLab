"""Computational biology verification: CPU-based structural validation.

Uses Biopython + numpy + DSSP to validate protein structures without GPU
re-prediction.  Checks physical plausibility (Ramachandran, clashes,
sequence–structure match, secondary structure) rather than re-folding.
"""
import asyncio
import json
import tempfile
import textwrap
import time
from pathlib import Path

from backend.verification.base import (
    VerificationAdapter, VerificationResult, VerificationBadge,
)
from backend.logging_config import get_logger

logger = get_logger(__name__)

COMPBIO_IMAGE = "clawdlab/compbio-cpu:latest"
COMPBIO_TIMEOUT = 300  # 5 min — CPU validation is fast
VALID_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")


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
