"""Machine Learning Interatomic Potential (MLIP) service."""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from platform.verification_engines.materials_verifier.base import (
    BaseMaterialsVerifier,
    CrystalStructure,
    EnergyResult,
    MCPToolProvider,
)
from platform.verification_engines.materials_verifier.config import (
    MLIP_MODELS,
    get_settings,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class MLIPService(BaseMaterialsVerifier):
    """
    Machine Learning Interatomic Potential service.

    Supports multiple MLIP models:
    - MACE-MP: High-accuracy foundation model from Cambridge
    - CHGNet: Charge-informed GNN from Berkeley
    - M3GNet: Materials 3-body Graph Network

    Can use MCP tools when available for enhanced capabilities.
    """

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize MLIP service."""
        super().__init__(tool_provider)
        self._model_cache: dict[str, Any] = {}

    @property
    def component_name(self) -> str:
        return "mlip_service"

    async def verify(
        self,
        structure: CrystalStructure,
        model: str | None = None,
    ) -> EnergyResult:
        """Calculate energy for a crystal structure."""
        return await self.calculate_energy(structure, model)

    async def calculate_energy(
        self,
        structure: CrystalStructure,
        model: str | None = None,
        calculate_forces: bool = False,
        calculate_stress: bool = False,
    ) -> EnergyResult:
        """
        Calculate total energy using MLIP.

        Args:
            structure: Crystal structure to evaluate
            model: MLIP model to use (mace-mp-0, chgnet, m3gnet)
            calculate_forces: Whether to calculate atomic forces
            calculate_stress: Whether to calculate stress tensor

        Returns:
            EnergyResult with energy and optional forces/stress
        """
        model = model or settings.default_mlip_model

        if model not in MLIP_MODELS:
            raise ValueError(f"Unknown MLIP model: {model}")

        model_config = MLIP_MODELS[model]

        logger.info(
            "mlip_calculation_started",
            model=model,
            composition=structure.composition,
            num_atoms=structure.num_atoms,
        )

        # Try MCP tool first
        if settings.mcp_enabled:
            mcp_tool_name = model_config.get("mcp_tool_name")
            if mcp_tool_name and await self._has_tool(mcp_tool_name):
                return await self._calculate_via_mcp(
                    structure=structure,
                    tool_name=mcp_tool_name,
                    calculate_forces=calculate_forces,
                    calculate_stress=calculate_stress,
                )

        # Fall back to local calculation
        if model.startswith("mace"):
            return await self._calculate_mace(
                structure, calculate_forces, calculate_stress
            )
        elif model == "chgnet":
            return await self._calculate_chgnet(
                structure, calculate_forces, calculate_stress
            )
        elif model == "m3gnet":
            return await self._calculate_m3gnet(
                structure, calculate_forces, calculate_stress
            )
        else:
            raise ValueError(f"Model not implemented: {model}")

    async def _calculate_via_mcp(
        self,
        structure: CrystalStructure,
        tool_name: str,
        calculate_forces: bool,
        calculate_stress: bool,
    ) -> EnergyResult:
        """Calculate energy using MCP tool."""
        start_time = datetime.utcnow()

        result = await self._invoke_tool(
            tool_name=tool_name,
            parameters={
                "cif_string": structure.cif_string,
                "composition": structure.composition,
                "calculate_forces": calculate_forces,
                "calculate_stress": calculate_stress,
            },
            timeout=settings.energy_calculation_timeout,
        )

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        return EnergyResult(
            total_energy=result.get("total_energy", 0.0),
            energy_per_atom=result.get("energy_per_atom", 0.0),
            forces=result.get("forces") if calculate_forces else None,
            stress=result.get("stress") if calculate_stress else None,
            model_used=tool_name,
            calculation_time_seconds=elapsed,
        )

    async def _calculate_mace(
        self,
        structure: CrystalStructure,
        calculate_forces: bool,
        calculate_stress: bool,
    ) -> EnergyResult:
        """Calculate energy using MACE."""
        start_time = datetime.utcnow()

        if not structure.cif_string:
            raise ValueError("CIF string required for MACE calculation")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write CIF file
            cif_path = Path(tmpdir) / "structure.cif"
            cif_path.write_text(structure.cif_string)

            # Build MACE calculation script
            script = f"""
import json
from ase.io import read
from mace.calculators import mace_mp

# Load structure
atoms = read("{cif_path}")

# Set up MACE calculator
calc = mace_mp(
    model="{settings.mace_model_path}",
    device="{settings.mlip_device}",
    dispersion={str(settings.mace_dispersion_correction).lower()},
)
atoms.calc = calc

# Calculate energy
energy = atoms.get_potential_energy()
energy_per_atom = energy / len(atoms)

result = {{
    "total_energy": float(energy),
    "energy_per_atom": float(energy_per_atom),
}}

if {calculate_forces}:
    forces = atoms.get_forces().tolist()
    result["forces"] = forces

if {calculate_stress}:
    stress = atoms.get_stress().tolist()
    result["stress"] = stress

print(json.dumps(result))
"""
            script_path = Path(tmpdir) / "calculate.py"
            script_path.write_text(script)

            # Run calculation
            if settings.use_singularity:
                cmd = [
                    "singularity", "exec", "--nv",
                    settings.singularity_image_path,
                    "python", str(script_path),
                ]
            else:
                cmd = ["python", str(script_path)]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.energy_calculation_timeout,
            )

            if process.returncode != 0:
                raise RuntimeError(f"MACE calculation failed: {stderr.decode()}")

            import json
            result = json.loads(stdout.decode())

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        return EnergyResult(
            total_energy=result["total_energy"],
            energy_per_atom=result["energy_per_atom"],
            forces=result.get("forces"),
            stress=result.get("stress"),
            model_used="mace-mp-0",
            calculation_time_seconds=elapsed,
        )

    async def _calculate_chgnet(
        self,
        structure: CrystalStructure,
        calculate_forces: bool,
        calculate_stress: bool,
    ) -> EnergyResult:
        """Calculate energy using CHGNet."""
        start_time = datetime.utcnow()

        if not structure.cif_string:
            raise ValueError("CIF string required for CHGNet calculation")

        with tempfile.TemporaryDirectory() as tmpdir:
            cif_path = Path(tmpdir) / "structure.cif"
            cif_path.write_text(structure.cif_string)

            script = f"""
import json
from pymatgen.core import Structure
from chgnet.model import CHGNet
from chgnet.model.model import CHGNetCalculator

# Load structure
structure = Structure.from_file("{cif_path}")

# Set up CHGNet
chgnet = CHGNet.load()
calc = CHGNetCalculator(chgnet)

# Convert to ASE
from pymatgen.io.ase import AseAtomsAdaptor
atoms = AseAtomsAdaptor.get_atoms(structure)
atoms.calc = calc

# Calculate
energy = atoms.get_potential_energy()
energy_per_atom = energy / len(atoms)

result = {{
    "total_energy": float(energy),
    "energy_per_atom": float(energy_per_atom),
}}

if {calculate_forces}:
    result["forces"] = atoms.get_forces().tolist()

if {calculate_stress}:
    result["stress"] = atoms.get_stress().tolist()

print(json.dumps(result))
"""
            script_path = Path(tmpdir) / "calculate.py"
            script_path.write_text(script)

            if settings.use_singularity:
                cmd = [
                    "singularity", "exec", "--nv",
                    settings.singularity_image_path,
                    "python", str(script_path),
                ]
            else:
                cmd = ["python", str(script_path)]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.energy_calculation_timeout,
            )

            if process.returncode != 0:
                raise RuntimeError(f"CHGNet calculation failed: {stderr.decode()}")

            import json
            result = json.loads(stdout.decode())

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        return EnergyResult(
            total_energy=result["total_energy"],
            energy_per_atom=result["energy_per_atom"],
            forces=result.get("forces"),
            stress=result.get("stress"),
            model_used="chgnet",
            calculation_time_seconds=elapsed,
        )

    async def _calculate_m3gnet(
        self,
        structure: CrystalStructure,
        calculate_forces: bool,
        calculate_stress: bool,
    ) -> EnergyResult:
        """Calculate energy using M3GNet."""
        start_time = datetime.utcnow()

        if not structure.cif_string:
            raise ValueError("CIF string required for M3GNet calculation")

        with tempfile.TemporaryDirectory() as tmpdir:
            cif_path = Path(tmpdir) / "structure.cif"
            cif_path.write_text(structure.cif_string)

            script = f"""
import json
from pymatgen.core import Structure
from m3gnet.models import M3GNet, Potential
from m3gnet.models import M3GNetCalculator

# Load structure
structure = Structure.from_file("{cif_path}")

# Set up M3GNet
potential = Potential(M3GNet.load())
calc = M3GNetCalculator(potential=potential)

# Convert to ASE
from pymatgen.io.ase import AseAtomsAdaptor
atoms = AseAtomsAdaptor.get_atoms(structure)
atoms.calc = calc

# Calculate
energy = atoms.get_potential_energy()
energy_per_atom = energy / len(atoms)

result = {{
    "total_energy": float(energy),
    "energy_per_atom": float(energy_per_atom),
}}

if {calculate_forces}:
    result["forces"] = atoms.get_forces().tolist()

if {calculate_stress}:
    result["stress"] = atoms.get_stress().tolist()

print(json.dumps(result))
"""
            script_path = Path(tmpdir) / "calculate.py"
            script_path.write_text(script)

            if settings.use_singularity:
                cmd = [
                    "singularity", "exec", "--nv",
                    settings.singularity_image_path,
                    "python", str(script_path),
                ]
            else:
                cmd = ["python", str(script_path)]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.energy_calculation_timeout,
            )

            if process.returncode != 0:
                raise RuntimeError(f"M3GNet calculation failed: {stderr.decode()}")

            import json
            result = json.loads(stdout.decode())

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        return EnergyResult(
            total_energy=result["total_energy"],
            energy_per_atom=result["energy_per_atom"],
            forces=result.get("forces"),
            stress=result.get("stress"),
            model_used="m3gnet",
            calculation_time_seconds=elapsed,
        )

    async def calculate_with_ensemble(
        self,
        structure: CrystalStructure,
        models: list[str] | None = None,
    ) -> dict[str, EnergyResult]:
        """
        Calculate energy with multiple models for uncertainty estimation.

        Args:
            structure: Crystal structure
            models: List of models to use (default: all available)

        Returns:
            Dict mapping model name to EnergyResult
        """
        models = models or list(MLIP_MODELS.keys())
        results = {}

        # Run calculations in parallel
        tasks = []
        for model in models:
            tasks.append(self.calculate_energy(structure, model))

        calculated = await asyncio.gather(*tasks, return_exceptions=True)

        for model, result in zip(models, calculated):
            if isinstance(result, Exception):
                logger.warning(f"Model {model} failed: {result}")
            else:
                results[model] = result

        return results

    def get_available_models(self) -> list[dict[str, Any]]:
        """Get list of available MLIP models."""
        return [
            {
                "id": model_id,
                "name": config["name"],
                "description": config["description"],
                "accuracy": config["accuracy"],
                "speed": config["speed"],
            }
            for model_id, config in MLIP_MODELS.items()
        ]
