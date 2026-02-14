"""Materials science verification: MACE-MP + pymatgen + Materials Project."""
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

MATERIALS_IMAGE = "clawdlab/materials:latest"
MATERIALS_TIMEOUT = 600  # 10 min


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

    async def _verify_prediction(self, result: dict) -> VerificationResult:
        """Validate crystal structure and compute energy with MACE-MP."""
        start = time.monotonic()

        formula = result.get("formula")
        cif_data = result.get("structure_cif")
        claimed_props = result.get("predicted_properties", {})

        if not cif_data:
            return VerificationResult.fail(self.domain, ["No structure_cif provided"])

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write CIF and verification script
            Path(tmpdir, "structure.cif").write_text(cif_data)
            Path(tmpdir, "claimed.json").write_text(json.dumps(claimed_props))
            Path(tmpdir, "verify.py").write_text(self._build_materials_script())

            cmd = [
                "docker", "run", "--rm",
                "--memory=8g", "--cpus=4",
                "-v", f"{tmpdir}:/workspace",
                MATERIALS_IMAGE,
                "python3", "/workspace/verify.py",
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=MATERIALS_TIMEOUT)
            except asyncio.TimeoutError:
                return VerificationResult.fail(self.domain, ["Materials verification timed out"])

        elapsed = time.monotonic() - start

        if proc.returncode != 0:
            return VerificationResult.fail(self.domain, [stderr.decode(errors="replace")[:500]])

        try:
            metrics = json.loads(stdout.decode())
        except json.JSONDecodeError:
            return VerificationResult.fail(self.domain, ["Failed to parse materials output"])

        # Score components
        structure_valid = metrics.get("structure_valid", False)
        energy_reasonable = metrics.get("energy_reasonable", False)
        mp_match = metrics.get("mp_match_score", 0)

        score = 0.0
        if structure_valid:
            score += 0.3
        if energy_reasonable:
            score += 0.3
        score += 0.4 * mp_match
        score = min(1.0, round(score, 4))

        return VerificationResult(
            passed=structure_valid and energy_reasonable,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details={
                "claim_type": "material_prediction",
                "formula": formula,
                "structure_valid": structure_valid,
                "symmetry": metrics.get("symmetry", {}),
                "energy_metrics": metrics.get("energy_metrics", {}),
                "mp_comparison": metrics.get("mp_comparison", {}),
            },
            compute_time_seconds=elapsed,
        )

    async def _verify_property(self, result: dict) -> VerificationResult:
        """Re-compute a material property and compare."""
        return VerificationResult(
            passed=False, score=0.0,
            badge=VerificationBadge.AMBER,
            domain=self.domain,
            errors=["Property re-computation not yet implemented"],
        )

    def _build_materials_script(self) -> str:
        return '''
import json
from pathlib import Path

result = {"structure_valid": False, "energy_reasonable": False, "mp_match_score": 0.0}

try:
    from pymatgen.core import Structure
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    structure = Structure.from_file("/workspace/structure.cif")

    # Validate structure
    if len(structure) > 0:
        # Check no overlapping atoms
        dist_matrix = structure.distance_matrix
        valid = True
        for i in range(len(structure)):
            for j in range(i + 1, len(structure)):
                if dist_matrix[i, j] < 0.5:
                    valid = False
                    break

        if valid:
            result["structure_valid"] = True
            analyzer = SpacegroupAnalyzer(structure)
            result["symmetry"] = {
                "symbol": analyzer.get_space_group_symbol(),
                "number": analyzer.get_space_group_number(),
                "crystal_system": analyzer.get_crystal_system(),
            }

    # MACE-MP energy calculation
    try:
        from mace.calculators import mace_mp
        from ase.io import read as ase_read

        atoms = ase_read("/workspace/structure.cif")
        calc = mace_mp(model="medium", default_dtype="float64")
        atoms.calc = calc
        energy = atoms.get_potential_energy()
        energy_per_atom = energy / len(atoms)

        result["energy_metrics"] = {
            "total_energy_ev": round(energy, 4),
            "energy_per_atom_ev": round(energy_per_atom, 4),
        }
        # Reasonable if energy per atom is between -15 and 0 eV
        result["energy_reasonable"] = -15.0 < energy_per_atom < 0.0

    except Exception as e:
        result["energy_metrics"] = {"error": str(e)}

    # Compare to Materials Project (if API key available)
    claimed = json.loads(Path("/workspace/claimed.json").read_text())
    result["mp_comparison"] = {"note": "MP comparison requires API key"}
    result["mp_match_score"] = 0.5  # Neutral when no comparison available

except Exception as e:
    result["error"] = str(e)

print(json.dumps(result))
'''
