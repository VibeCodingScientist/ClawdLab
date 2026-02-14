"""Computational biology verification: AlphaFold/ESMFold structure prediction."""
import asyncio
import json
import tempfile
import time
from pathlib import Path

from backend.verification.base import (
    VerificationAdapter, VerificationResult, VerificationBadge,
)
from backend.logging_config import get_logger

logger = get_logger(__name__)

COMPBIO_IMAGE = "clawdlab/compbio:latest"
COMPBIO_TIMEOUT = 1800  # 30 min (AlphaFold can be slow)
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

    async def _verify_structure(self, result: dict) -> VerificationResult:
        """Re-predict protein structure and compare to claimed."""
        start = time.monotonic()

        sequence = result.get("sequence", "")
        if not sequence or not self._valid_sequence(sequence):
            return VerificationResult.fail(self.domain, ["Invalid or missing protein sequence"])

        method = result.get("method", "esmfold")  # ESMFold is faster default
        claimed_pdb = result.get("claimed_structure_pdb")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write sequence FASTA
            fasta_path = Path(tmpdir) / "input.fasta"
            fasta_path.write_text(f">query\n{sequence}\n")

            # Write verification script
            script = self._build_prediction_script(method, claimed_pdb is not None)
            script_path = Path(tmpdir) / "verify.py"
            script_path.write_text(script)

            if claimed_pdb:
                claimed_path = Path(tmpdir) / "claimed.pdb"
                claimed_path.write_text(claimed_pdb)

            # Run in container
            cmd = [
                "docker", "run", "--rm",
                "--gpus", "all",
                "--memory=16g",
                "-v", f"{tmpdir}:/workspace",
                COMPBIO_IMAGE,
                "python3", "/workspace/verify.py",
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=COMPBIO_TIMEOUT)
            except asyncio.TimeoutError:
                return VerificationResult.fail(self.domain, ["Structure prediction timed out"])

        elapsed = time.monotonic() - start

        if proc.returncode != 0:
            return VerificationResult.fail(self.domain, [
                f"Prediction failed: {stderr.decode(errors='replace')[:500]}"
            ])

        try:
            metrics = json.loads(stdout.decode())
        except json.JSONDecodeError:
            return VerificationResult.fail(self.domain, ["Failed to parse prediction output"])

        # Score: pLDDT (50%) + pTM (30%) + TM-score vs claimed (20%)
        plddt = metrics.get("plddt_mean", 0) / 100.0
        ptm = metrics.get("ptm", 0)
        tm_score = metrics.get("tm_score_vs_claimed", 0) if claimed_pdb else 0

        score = plddt * 0.5 + ptm * 0.3
        if claimed_pdb:
            score += (1.0 if tm_score >= 0.5 else tm_score) * 0.2
        else:
            score = score / 0.8  # Rescale if no comparison

        score = min(1.0, round(score, 4))

        return VerificationResult(
            passed=plddt >= 0.7 and ptm >= 0.5,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details={
                "claim_type": "structure_prediction",
                "method": method,
                "plddt_mean": metrics.get("plddt_mean"),
                "ptm": ptm,
                "tm_score_vs_claimed": tm_score if claimed_pdb else None,
                "sequence_length": len(sequence),
            },
            compute_time_seconds=elapsed,
        )

    async def _verify_design(self, result: dict) -> VerificationResult:
        """Verify protein design via self-consistency (ProteinMPNN -> fold -> scTM)."""
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
            Path(tmpdir, "verify_design.py").write_text(self._build_design_script())

            cmd = [
                "docker", "run", "--rm", "--gpus", "all", "--memory=16g",
                "-v", f"{tmpdir}:/workspace", COMPBIO_IMAGE,
                "python3", "/workspace/verify_design.py",
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=COMPBIO_TIMEOUT)
            except asyncio.TimeoutError:
                return VerificationResult.fail(self.domain, ["Design verification timed out"])

        elapsed = time.monotonic() - start

        if proc.returncode != 0:
            return VerificationResult.fail(self.domain, [stderr.decode(errors="replace")[:500]])

        try:
            metrics = json.loads(stdout.decode())
        except json.JSONDecodeError:
            return VerificationResult.fail(self.domain, ["Failed to parse design output"])

        sctm = metrics.get("sctm", 0)
        plddt = metrics.get("plddt_mean", 0) / 100.0

        score = sctm * 0.5 + plddt * 0.5
        score = min(1.0, round(score, 4))

        return VerificationResult(
            passed=sctm >= 0.7,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details={
                "claim_type": "protein_design",
                "sctm": sctm,
                "plddt_mean": metrics.get("plddt_mean"),
                "sequence_length": len(designed_seq),
            },
            compute_time_seconds=elapsed,
        )

    async def _verify_binder(self, result: dict) -> VerificationResult:
        """Verify binder design: predict complex, check interface quality."""
        return VerificationResult(
            passed=False, score=0.0,
            badge=VerificationBadge.RED,
            domain=self.domain,
            errors=["Binder verification not yet implemented -- use protein_design"],
        )

    def _valid_sequence(self, seq: str) -> bool:
        return len(seq) > 0 and all(aa.upper() in VALID_AMINO_ACIDS for aa in seq)

    def _build_prediction_script(self, method: str, has_claimed: bool) -> str:
        """Generate Python script that runs inside the container."""
        return f'''
import json
import sys
sys.path.insert(0, "/opt")

method = "{method}"
has_claimed = {has_claimed}

if method == "esmfold":
    import torch
    from esm.pretrained import esmfold_v1
    model = esmfold_v1()
    model = model.eval().cuda()
    with open("/workspace/input.fasta") as f:
        lines = f.readlines()
        sequence = "".join(l.strip() for l in lines[1:])
    with torch.no_grad():
        output = model.infer_pdb(sequence)
    plddt_mean = model.infer(sequence)["plddt"].mean().item()
    ptm = model.infer(sequence)["ptm"].item()
else:
    # AlphaFold -- heavier, requires MSA
    plddt_mean = 0
    ptm = 0

result = {{"plddt_mean": round(plddt_mean, 2), "ptm": round(ptm, 4)}}

if has_claimed:
    try:
        from tmtools import tm_align
        result["tm_score_vs_claimed"] = 0.0  # placeholder
    except ImportError:
        result["tm_score_vs_claimed"] = None

print(json.dumps(result))
'''

    def _build_design_script(self) -> str:
        return '''
import json
# 1. Fold designed sequence with ESMFold
# 2. TM-align folded vs backbone.pdb -> scTM
# 3. Output metrics
result = {"sctm": 0.0, "plddt_mean": 0.0}
print(json.dumps(result))
'''
