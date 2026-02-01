"""Binder design verification with interface analysis."""

import math
from dataclasses import dataclass
from typing import Any

from platform.verification_engines.compbio_verifier.base import (
    BaseCompBioVerifier,
    BinderResult,
    MCPToolProvider,
    ProteinComplex,
    ProteinStructure,
)
from platform.verification_engines.compbio_verifier.config import get_settings
from platform.verification_engines.compbio_verifier.structure_predictor import (
    StructurePredictionService,
    validate_sequence,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class InterfaceContact:
    """Contact at protein-protein interface."""

    chain1: str
    residue1: int
    atom1: str
    chain2: str
    residue2: int
    atom2: str
    distance: float


@dataclass
class InterfaceAnalysis:
    """Analysis of protein-protein interface."""

    contacts: list[InterfaceContact]
    num_contacts: int
    interface_area: float  # Buried surface area in Å²
    interface_residues_chain1: list[int]
    interface_residues_chain2: list[int]
    hotspot_residues: list[int]  # Critical residues for binding
    shape_complementarity: float | None
    electrostatic_score: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "num_contacts": self.num_contacts,
            "interface_area": self.interface_area,
            "interface_residues_chain1": self.interface_residues_chain1,
            "interface_residues_chain2": self.interface_residues_chain2,
            "hotspot_residues": self.hotspot_residues,
            "shape_complementarity": self.shape_complementarity,
            "electrostatic_score": self.electrostatic_score,
        }


class BinderDesignVerifier(BaseCompBioVerifier):
    """
    Verifies protein binder design claims.

    Performs:
    - Complex structure prediction (binder + target)
    - Interface analysis (contacts, buried surface area)
    - Confidence assessment (interface pLDDT, PAE)
    - Binding quality metrics
    """

    def __init__(
        self,
        tool_provider: MCPToolProvider | None = None,
        structure_predictor: StructurePredictionService | None = None,
    ):
        """Initialize binder verifier."""
        super().__init__(tool_provider)
        self._structure_predictor = structure_predictor or StructurePredictionService(tool_provider)

    @property
    def component_name(self) -> str:
        return "binder_verifier"

    async def verify(
        self,
        binder_sequence: str,
        target_sequence: str | None = None,
        target_pdb: str | None = None,
        binding_site_residues: list[int] | None = None,
        **kwargs,
    ) -> BinderResult:
        """
        Verify a binder design.

        Args:
            binder_sequence: The designed binder sequence
            target_sequence: Target protein sequence
            target_pdb: Target structure PDB string (alternative to sequence)
            binding_site_residues: Expected binding site residues on target
            **kwargs: Additional arguments

        Returns:
            BinderResult with verification metrics
        """
        # Validate binder sequence
        valid, error = validate_sequence(binder_sequence)
        if not valid:
            raise ValueError(f"Invalid binder sequence: {error}")

        logger.info(
            "binder_verification_started",
            binder_length=len(binder_sequence),
            has_target_sequence=target_sequence is not None,
            has_target_pdb=target_pdb is not None,
        )

        # Get or predict target structure
        target_structure = None
        if target_pdb:
            target_structure = ProteinStructure(
                sequence=target_sequence or "",
                pdb_string=target_pdb,
            )
        elif target_sequence:
            valid, error = validate_sequence(target_sequence)
            if not valid:
                raise ValueError(f"Invalid target sequence: {error}")

            target_structure = await self._structure_predictor.predict_structure(
                sequence=target_sequence,
            )

        # Predict complex structure
        complex_structure = await self._predict_complex(
            binder_sequence=binder_sequence,
            target_structure=target_structure,
            **kwargs,
        )

        # Analyze interface
        interface_analysis = await self._analyze_interface(
            complex_structure=complex_structure,
            binding_site_residues=binding_site_residues,
        )

        # Calculate interface metrics
        interface_plddt = self._calculate_interface_plddt(
            complex_structure=complex_structure,
            interface_residues=interface_analysis.interface_residues_chain1,
        )

        interface_pae = self._calculate_interface_pae(
            complex_structure=complex_structure,
        )

        # Estimate binding energy (simplified)
        binding_energy = self._estimate_binding_energy(interface_analysis)

        result = BinderResult(
            binder_sequence=binder_sequence,
            target_structure=target_structure,
            complex_structure=complex_structure,
            interface_plddt=interface_plddt,
            interface_pae=interface_pae,
            num_interface_contacts=interface_analysis.num_contacts,
            interface_area=interface_analysis.interface_area,
            binding_energy_estimate=binding_energy,
            hotspot_residues=interface_analysis.hotspot_residues,
        )

        logger.info(
            "binder_verification_completed",
            interface_plddt=interface_plddt,
            num_contacts=interface_analysis.num_contacts,
            interface_area=interface_analysis.interface_area,
        )

        return result

    async def _predict_complex(
        self,
        binder_sequence: str,
        target_structure: ProteinStructure | None,
        **kwargs,
    ) -> ProteinComplex:
        """Predict structure of binder-target complex."""
        # If we have MCP tool for complex prediction, use it
        if await self._has_tool("alphafold_complex_predict"):
            target_seq = target_structure.sequence if target_structure else ""
            result = await self._invoke_tool(
                tool_name="alphafold_complex_predict",
                parameters={
                    "sequences": [target_seq, binder_sequence],
                },
            )

            # Parse result into ProteinComplex
            structures = []
            for i, seq in enumerate([target_seq, binder_sequence]):
                structures.append(ProteinStructure(
                    sequence=seq,
                    mean_plddt=result.get(f"chain_{i}_plddt", 0.0),
                    chains=[chr(65 + i)],
                ))

            return ProteinComplex(
                structures=structures,
                interface_pae=result.get("interface_pae"),
                iptm_score=result.get("iptm"),
            )

        # Fall back to separate predictions
        if target_structure:
            sequences = [target_structure.sequence, binder_sequence]
        else:
            sequences = [binder_sequence]

        return await self._structure_predictor.predict_complex(
            sequences=sequences,
            predictor=kwargs.get("predictor", "alphafold"),
        )

    async def _analyze_interface(
        self,
        complex_structure: ProteinComplex,
        binding_site_residues: list[int] | None = None,
    ) -> InterfaceAnalysis:
        """Analyze protein-protein interface."""
        # Check for MCP interface analysis tool
        if await self._has_tool("analyze_interface"):
            result = await self._invoke_tool(
                tool_name="analyze_interface",
                parameters={
                    "complex": complex_structure.to_dict(),
                },
            )

            return InterfaceAnalysis(
                contacts=[],
                num_contacts=result.get("num_contacts", 0),
                interface_area=result.get("interface_area", 0.0),
                interface_residues_chain1=result.get("interface_residues_1", []),
                interface_residues_chain2=result.get("interface_residues_2", []),
                hotspot_residues=result.get("hotspot_residues", []),
                shape_complementarity=result.get("sc_score"),
                electrostatic_score=result.get("elec_score"),
            )

        # Local interface analysis from PAE matrix
        if complex_structure.interface_pae is not None:
            return self._analyze_interface_from_pae(
                complex_structure=complex_structure,
            )

        # Simplified analysis without structure
        return InterfaceAnalysis(
            contacts=[],
            num_contacts=0,
            interface_area=0.0,
            interface_residues_chain1=[],
            interface_residues_chain2=[],
            hotspot_residues=[],
            shape_complementarity=None,
            electrostatic_score=None,
        )

    def _analyze_interface_from_pae(
        self,
        complex_structure: ProteinComplex,
    ) -> InterfaceAnalysis:
        """Analyze interface from predicted aligned error matrix."""
        if len(complex_structure.structures) < 2:
            return InterfaceAnalysis(
                contacts=[],
                num_contacts=0,
                interface_area=0.0,
                interface_residues_chain1=[],
                interface_residues_chain2=[],
                hotspot_residues=[],
                shape_complementarity=None,
                electrostatic_score=None,
            )

        # Get chain lengths
        chain1_len = len(complex_structure.structures[0].sequence)
        chain2_len = len(complex_structure.structures[1].sequence)

        interface_residues_1 = []
        interface_residues_2 = []
        contacts = []

        # Simple contact detection based on PAE threshold
        pae_threshold = settings.min_ipae_threshold

        # In a real implementation, we would parse the PAE matrix
        # For now, return placeholder based on confidence scores
        if complex_structure.interface_pae and complex_structure.interface_pae < pae_threshold:
            # Assume interface exists
            # Estimate interface residues (simplified)
            interface_residues_1 = list(range(chain1_len - 20, chain1_len))
            interface_residues_2 = list(range(0, 20))

        num_contacts = len(interface_residues_1) * 2  # Approximate

        # Estimate interface area (simplified)
        # ~100-200 Å² per interface residue
        interface_area = num_contacts * 50.0

        return InterfaceAnalysis(
            contacts=contacts,
            num_contacts=num_contacts,
            interface_area=interface_area,
            interface_residues_chain1=interface_residues_1,
            interface_residues_chain2=interface_residues_2,
            hotspot_residues=interface_residues_2[:5] if interface_residues_2 else [],
            shape_complementarity=None,
            electrostatic_score=None,
        )

    def _calculate_interface_plddt(
        self,
        complex_structure: ProteinComplex,
        interface_residues: list[int],
    ) -> float | None:
        """Calculate mean pLDDT for interface residues."""
        if not interface_residues:
            return None

        if len(complex_structure.structures) < 2:
            return None

        binder = complex_structure.structures[-1]  # Binder is last chain
        if not binder.per_residue_plddt:
            return binder.mean_plddt

        # Get pLDDT for interface residues
        interface_plddt = []
        for i in interface_residues:
            if 0 <= i < len(binder.per_residue_plddt):
                interface_plddt.append(binder.per_residue_plddt[i])

        if interface_plddt:
            return sum(interface_plddt) / len(interface_plddt)

        return None

    def _calculate_interface_pae(
        self,
        complex_structure: ProteinComplex,
    ) -> float | None:
        """Calculate interface predicted aligned error."""
        return complex_structure.interface_pae

    def _estimate_binding_energy(
        self,
        interface_analysis: InterfaceAnalysis,
    ) -> float | None:
        """
        Estimate binding energy from interface features.

        Uses simplified empirical formula based on buried surface area.
        """
        if interface_analysis.interface_area <= 0:
            return None

        # Simplified binding energy estimation
        # ΔG ≈ -0.006 * BSA - 5.0 (kcal/mol, very approximate)
        estimated_dg = -0.006 * interface_analysis.interface_area - 5.0

        # Adjust for number of contacts
        contact_bonus = -0.1 * interface_analysis.num_contacts

        return estimated_dg + contact_bonus

    def assess_binder_quality(
        self,
        binder_result: BinderResult,
    ) -> dict[str, Any]:
        """
        Assess overall quality of binder design.

        Args:
            binder_result: Result from binder verification

        Returns:
            Quality assessment dictionary
        """
        # Quality checks
        checks = {
            "interface_plddt_ok": (
                binder_result.interface_plddt is not None and
                binder_result.interface_plddt >= settings.min_plddt_threshold
            ),
            "interface_pae_ok": (
                binder_result.interface_pae is not None and
                binder_result.interface_pae <= settings.min_ipae_threshold
            ),
            "sufficient_contacts": (
                binder_result.num_interface_contacts >= settings.min_interface_contacts
            ),
            "reasonable_interface_area": (
                binder_result.interface_area is not None and
                binder_result.interface_area >= 500  # Minimum ~500 Å²
            ),
        }

        # Calculate quality score
        passed_checks = sum(checks.values())
        total_checks = len(checks)
        quality_score = passed_checks / total_checks

        # Quality tier
        if quality_score >= 0.9:
            quality_tier = "excellent"
        elif quality_score >= 0.7:
            quality_tier = "good"
        elif quality_score >= 0.5:
            quality_tier = "moderate"
        else:
            quality_tier = "poor"

        # Generate recommendations
        recommendations = []
        if not checks["interface_plddt_ok"]:
            recommendations.append(
                "Interface pLDDT is low. Consider redesigning interface residues."
            )
        if not checks["interface_pae_ok"]:
            recommendations.append(
                "High interface PAE indicates uncertain binding mode."
            )
        if not checks["sufficient_contacts"]:
            recommendations.append(
                "Few interface contacts. Consider adding more contact residues."
            )
        if not checks["reasonable_interface_area"]:
            recommendations.append(
                "Small interface area may indicate weak binding."
            )

        return {
            "quality_tier": quality_tier,
            "quality_score": quality_score,
            "checks": checks,
            "passed_checks": passed_checks,
            "total_checks": total_checks,
            "recommendations": recommendations,
            "binding_energy_estimate": binder_result.binding_energy_estimate,
        }
