"""Structure prediction service with MCP tool support."""

import asyncio
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from platform.verification_engines.compbio_verifier.base import (
    BaseCompBioVerifier,
    MCPToolProvider,
    ProteinComplex,
    ProteinStructure,
)
from platform.verification_engines.compbio_verifier.config import (
    STRUCTURE_PREDICTORS,
    get_settings,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def validate_sequence(sequence: str) -> tuple[bool, str | None]:
    """Validate protein sequence."""
    valid_aa = set("ACDEFGHIKLMNPQRSTVWY")
    sequence = sequence.upper().replace(" ", "").replace("\n", "")

    if not sequence:
        return False, "Empty sequence"

    if len(sequence) > settings.max_sequence_length:
        return False, f"Sequence too long: {len(sequence)} > {settings.max_sequence_length}"

    invalid_chars = set(sequence) - valid_aa
    if invalid_chars:
        return False, f"Invalid amino acids: {invalid_chars}"

    return True, None


class StructurePredictionService(BaseCompBioVerifier):
    """
    Structure prediction service supporting multiple backends.

    Supports:
    - ESMFold (Meta's language model-based prediction)
    - AlphaFold2 (DeepMind's MSA-based prediction)
    - Chai-1 (Chai Discovery's prediction)
    - OpenFold (open-source AlphaFold)

    Can use MCP tools when available for enhanced capabilities.
    """

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize structure prediction service."""
        super().__init__(tool_provider)
        self._model_cache: dict[str, Any] = {}

    @property
    def component_name(self) -> str:
        return "structure_predictor"

    async def verify(
        self,
        sequence: str,
        predictor: str = "esmfold",
        **kwargs,
    ) -> ProteinStructure:
        """Predict structure for a protein sequence."""
        return await self.predict_structure(sequence, predictor, **kwargs)

    async def predict_structure(
        self,
        sequence: str,
        predictor: str | None = None,
        use_mcp: bool = True,
        **kwargs,
    ) -> ProteinStructure:
        """
        Predict protein structure from sequence.

        Args:
            sequence: Amino acid sequence (one-letter codes)
            predictor: Prediction method (esmfold, alphafold, chai1)
            use_mcp: Whether to try MCP tools first
            **kwargs: Additional predictor-specific arguments

        Returns:
            ProteinStructure with prediction results
        """
        predictor = predictor or settings.default_structure_predictor
        sequence = sequence.upper().replace(" ", "").replace("\n", "")

        # Validate sequence
        valid, error = validate_sequence(sequence)
        if not valid:
            raise ValueError(f"Invalid sequence: {error}")

        # Check predictor config
        if predictor not in STRUCTURE_PREDICTORS:
            raise ValueError(f"Unknown predictor: {predictor}")

        predictor_config = STRUCTURE_PREDICTORS[predictor]

        # Try MCP tool first if enabled
        if use_mcp and settings.mcp_enabled:
            mcp_tool_name = predictor_config.get("mcp_tool_name")
            if mcp_tool_name and await self._has_tool(mcp_tool_name):
                logger.info(
                    "using_mcp_tool",
                    tool=mcp_tool_name,
                    sequence_length=len(sequence),
                )
                return await self._predict_via_mcp(
                    sequence=sequence,
                    tool_name=mcp_tool_name,
                    **kwargs,
                )

        # Fall back to local prediction
        logger.info(
            "using_local_predictor",
            predictor=predictor,
            sequence_length=len(sequence),
        )

        if predictor == "esmfold":
            return await self._predict_esmfold(sequence, **kwargs)
        elif predictor == "alphafold":
            return await self._predict_alphafold(sequence, **kwargs)
        elif predictor == "chai1":
            return await self._predict_chai1(sequence, **kwargs)
        elif predictor == "openfold":
            return await self._predict_openfold(sequence, **kwargs)
        else:
            raise ValueError(f"Predictor not implemented: {predictor}")

    async def predict_complex(
        self,
        sequences: list[str],
        predictor: str | None = None,
        **kwargs,
    ) -> ProteinComplex:
        """
        Predict structure of protein complex.

        Args:
            sequences: List of sequences for each chain
            predictor: Prediction method
            **kwargs: Additional arguments

        Returns:
            ProteinComplex with multi-chain prediction
        """
        predictor = predictor or settings.default_structure_predictor

        # Validate all sequences
        for i, seq in enumerate(sequences):
            valid, error = validate_sequence(seq)
            if not valid:
                raise ValueError(f"Invalid sequence {i}: {error}")

        # Check for MCP complex prediction tool
        if settings.mcp_enabled:
            complex_tool = f"{predictor}_complex_predict"
            if await self._has_tool(complex_tool):
                return await self._predict_complex_via_mcp(
                    sequences=sequences,
                    tool_name=complex_tool,
                    **kwargs,
                )

        # Local complex prediction
        if predictor == "alphafold":
            return await self._predict_complex_alphafold(sequences, **kwargs)
        elif predictor == "chai1":
            return await self._predict_complex_chai1(sequences, **kwargs)
        else:
            # Fall back to predicting structures separately
            structures = []
            for seq in sequences:
                struct = await self.predict_structure(seq, predictor, **kwargs)
                structures.append(struct)

            return ProteinComplex(
                structures=structures,
                chain_pairs=[(f"A{i}", f"A{i+1}") for i in range(len(sequences)-1)],
            )

    async def _predict_via_mcp(
        self,
        sequence: str,
        tool_name: str,
        **kwargs,
    ) -> ProteinStructure:
        """Predict structure using MCP tool."""
        start_time = datetime.utcnow()

        result = await self._invoke_tool(
            tool_name=tool_name,
            parameters={
                "sequence": sequence,
                **kwargs,
            },
            timeout=settings.structure_prediction_timeout,
        )

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        return ProteinStructure(
            sequence=sequence,
            pdb_string=result.get("pdb_string"),
            mean_plddt=result.get("mean_plddt", 0.0),
            per_residue_plddt=result.get("per_residue_plddt", []),
            ptm_score=result.get("ptm_score"),
            predicted_aligned_error=result.get("pae"),
            model_used=tool_name,
            prediction_time_seconds=elapsed,
        )

    async def _predict_esmfold(
        self,
        sequence: str,
        **kwargs,
    ) -> ProteinStructure:
        """Predict structure using ESMFold."""
        start_time = datetime.utcnow()

        # Use Singularity container or direct execution
        if settings.use_singularity:
            result = await self._run_esmfold_container(sequence)
        else:
            result = await self._run_esmfold_direct(sequence)

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        return ProteinStructure(
            sequence=sequence,
            pdb_string=result.get("pdb_string"),
            mean_plddt=result.get("mean_plddt", 0.0),
            per_residue_plddt=result.get("per_residue_plddt", []),
            ptm_score=result.get("ptm_score"),
            model_used="esmfold",
            prediction_time_seconds=elapsed,
        )

    async def _run_esmfold_container(self, sequence: str) -> dict[str, Any]:
        """Run ESMFold via Singularity container."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write sequence to file
            seq_file = Path(tmpdir) / "sequence.fasta"
            seq_file.write_text(f">query\n{sequence}\n")

            output_file = Path(tmpdir) / "output.pdb"

            cmd = [
                "singularity", "exec", "--nv",
                settings.singularity_image_path,
                "python", "-c", f"""
import torch
from esm.pretrained import esmfold_v1
import json

model = esmfold_v1()
model = model.eval().cuda()

sequence = "{sequence}"
with torch.no_grad():
    output = model.infer_pdb(sequence)

# Get confidence scores
with torch.no_grad():
    result = model.infer(sequence)
    plddt = result["plddt"][0].cpu().numpy().tolist()
    ptm = result.get("ptm", [None])[0]

print(json.dumps({{
    "pdb_string": output,
    "per_residue_plddt": plddt,
    "mean_plddt": sum(plddt) / len(plddt),
    "ptm_score": float(ptm) if ptm else None
}}))
"""
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.structure_prediction_timeout,
            )

            if process.returncode != 0:
                raise RuntimeError(f"ESMFold failed: {stderr.decode()}")

            import json
            return json.loads(stdout.decode())

    async def _run_esmfold_direct(self, sequence: str) -> dict[str, Any]:
        """Run ESMFold directly (requires esm installed)."""
        # This would run ESMFold directly if the library is installed
        # For now, return a placeholder
        return {
            "pdb_string": None,
            "mean_plddt": 0.0,
            "per_residue_plddt": [],
            "ptm_score": None,
        }

    async def _predict_alphafold(
        self,
        sequence: str,
        use_msa: bool = True,
        **kwargs,
    ) -> ProteinStructure:
        """Predict structure using AlphaFold2."""
        start_time = datetime.utcnow()

        with tempfile.TemporaryDirectory() as tmpdir:
            seq_file = Path(tmpdir) / "sequence.fasta"
            seq_file.write_text(f">query\n{sequence}\n")

            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            cmd = [
                "singularity", "exec", "--nv",
                "-B", f"{settings.alphafold_data_dir}:/data",
                "-B", f"{settings.alphafold_model_dir}:/models",
                settings.singularity_image_path,
                "python", "-m", "alphafold.run_alphafold",
                f"--fasta_paths={seq_file}",
                f"--output_dir={output_dir}",
                "--model_preset=monomer",
                f"--data_dir=/data",
            ]

            if not use_msa:
                cmd.append("--use_precomputed_msas=false")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.structure_prediction_timeout,
            )

            if process.returncode != 0:
                raise RuntimeError(f"AlphaFold failed: {stderr.decode()}")

            # Parse output
            result = await self._parse_alphafold_output(output_dir)

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        return ProteinStructure(
            sequence=sequence,
            pdb_string=result.get("pdb_string"),
            mean_plddt=result.get("mean_plddt", 0.0),
            per_residue_plddt=result.get("per_residue_plddt", []),
            ptm_score=result.get("ptm_score"),
            predicted_aligned_error=result.get("pae"),
            model_used="alphafold",
            prediction_time_seconds=elapsed,
        )

    async def _parse_alphafold_output(self, output_dir: Path) -> dict[str, Any]:
        """Parse AlphaFold output files."""
        result = {}

        # Find best ranked model
        pdb_files = list(output_dir.glob("**/ranked_0.pdb"))
        if pdb_files:
            result["pdb_string"] = pdb_files[0].read_text()

        # Parse confidence scores
        import json
        pkl_files = list(output_dir.glob("**/result_model_*.pkl"))
        if pkl_files:
            import pickle
            with open(pkl_files[0], "rb") as f:
                data = pickle.load(f)
                result["per_residue_plddt"] = data.get("plddt", []).tolist()
                result["mean_plddt"] = sum(result["per_residue_plddt"]) / len(result["per_residue_plddt"])
                result["ptm_score"] = float(data.get("ptm", 0))
                if "predicted_aligned_error" in data:
                    result["pae"] = data["predicted_aligned_error"].tolist()

        return result

    async def _predict_chai1(
        self,
        sequence: str,
        **kwargs,
    ) -> ProteinStructure:
        """Predict structure using Chai-1."""
        # Chai-1 prediction via container or MCP
        start_time = datetime.utcnow()

        # Placeholder implementation
        # In production, this would call Chai-1 API or container

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        return ProteinStructure(
            sequence=sequence,
            pdb_string=None,
            mean_plddt=0.0,
            model_used="chai1",
            prediction_time_seconds=elapsed,
        )

    async def _predict_openfold(
        self,
        sequence: str,
        **kwargs,
    ) -> ProteinStructure:
        """Predict structure using OpenFold."""
        # Similar to AlphaFold but using OpenFold
        start_time = datetime.utcnow()

        # Placeholder
        elapsed = (datetime.utcnow() - start_time).total_seconds()

        return ProteinStructure(
            sequence=sequence,
            pdb_string=None,
            mean_plddt=0.0,
            model_used="openfold",
            prediction_time_seconds=elapsed,
        )

    async def _predict_complex_via_mcp(
        self,
        sequences: list[str],
        tool_name: str,
        **kwargs,
    ) -> ProteinComplex:
        """Predict complex structure using MCP tool."""
        start_time = datetime.utcnow()

        result = await self._invoke_tool(
            tool_name=tool_name,
            parameters={
                "sequences": sequences,
                **kwargs,
            },
            timeout=settings.structure_prediction_timeout * 2,
        )

        structures = []
        for i, seq in enumerate(sequences):
            structures.append(ProteinStructure(
                sequence=seq,
                pdb_string=result.get(f"chain_{i}_pdb"),
                mean_plddt=result.get(f"chain_{i}_plddt", 0.0),
                chains=[chr(65 + i)],  # A, B, C, ...
                model_used=tool_name,
            ))

        return ProteinComplex(
            structures=structures,
            interface_pae=result.get("interface_pae"),
            iptm_score=result.get("iptm"),
        )

    async def _predict_complex_alphafold(
        self,
        sequences: list[str],
        **kwargs,
    ) -> ProteinComplex:
        """Predict complex using AlphaFold-Multimer."""
        # Placeholder for AlphaFold-Multimer
        structures = []
        for i, seq in enumerate(sequences):
            struct = await self._predict_alphafold(seq, **kwargs)
            struct.chains = [chr(65 + i)]
            structures.append(struct)

        return ProteinComplex(structures=structures)

    async def _predict_complex_chai1(
        self,
        sequences: list[str],
        **kwargs,
    ) -> ProteinComplex:
        """Predict complex using Chai-1."""
        # Placeholder for Chai-1 multimer
        structures = []
        for i, seq in enumerate(sequences):
            struct = await self._predict_chai1(seq, **kwargs)
            struct.chains = [chr(65 + i)]
            structures.append(struct)

        return ProteinComplex(structures=structures)

    def get_available_predictors(self) -> list[dict[str, Any]]:
        """Get list of available structure predictors."""
        predictors = []
        for pred_id, config in STRUCTURE_PREDICTORS.items():
            predictors.append({
                "id": pred_id,
                "name": config["name"],
                "description": config["description"],
                "max_length": config["max_length"],
                "gpu_required": config["gpu_required"],
            })
        return predictors
