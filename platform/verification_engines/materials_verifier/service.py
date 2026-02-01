"""Main Materials Science Verification Service."""

from datetime import datetime
from typing import Any

from platform.verification_engines.materials_verifier.base import (
    CrystalStructure,
    EnergyResult,
    MaterialsNoveltyResult,
    MaterialsVerificationResult,
    MCPToolProvider,
    PropertyPrediction,
    StabilityResult,
    VerificationStatus,
)
from platform.verification_engines.materials_verifier.config import (
    MATERIALS_CLAIM_TYPES,
    get_settings,
)
from platform.verification_engines.materials_verifier.materials_project import (
    MaterialsProjectClient,
)
from platform.verification_engines.materials_verifier.mlip_service import MLIPService
from platform.verification_engines.materials_verifier.novelty_checker import (
    MaterialsNoveltyChecker,
)
from platform.verification_engines.materials_verifier.structure_tools import (
    CIFParser,
    StructureValidator,
    SymmetryAnalyzer,
    parse_cif,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class MaterialsVerificationService:
    """
    Main service for Materials Science verification.

    Orchestrates verification of materials science claims using:
    - Crystal structure validation
    - MLIP energy calculations
    - Thermodynamic stability analysis
    - Novelty checking across databases

    MCP-aware: Uses MCP tools when available, falls back to local execution.
    """

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """
        Initialize Materials Verification Service.

        Args:
            tool_provider: MCP tool provider for external tools
        """
        self._tool_provider = tool_provider
        self._cif_parser = CIFParser()
        self._structure_validator = StructureValidator(tool_provider)
        self._symmetry_analyzer = SymmetryAnalyzer(tool_provider)
        self._mlip_service = MLIPService(tool_provider)
        self._mp_client = MaterialsProjectClient(tool_provider)
        self._novelty_checker = MaterialsNoveltyChecker(tool_provider)

    async def verify_claim(
        self,
        claim: dict[str, Any],
    ) -> MaterialsVerificationResult:
        """
        Verify a materials science claim.

        Args:
            claim: Claim dict with:
                - claim_type: Type of claim (structure_prediction, stability_claim, etc.)
                - composition: Chemical formula
                - structure_cif: CIF string (optional)
                - Additional type-specific fields

        Returns:
            MaterialsVerificationResult with verification outcome
        """
        started_at = datetime.utcnow()
        claim_id = claim.get("claim_id", "")
        claim_type = claim.get("claim_type", "")
        tools_used = []

        try:
            # Validate claim type
            if claim_type not in MATERIALS_CLAIM_TYPES:
                return MaterialsVerificationResult(
                    status=VerificationStatus.ERROR,
                    verified=False,
                    message=f"Unknown claim type: {claim_type}",
                    claim_id=claim_id,
                    claim_type=claim_type,
                    error_type="invalid_claim_type",
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            # Route to appropriate verification method
            if claim_type == "structure_prediction":
                result = await self._verify_structure_prediction(claim, tools_used)
            elif claim_type == "stability_claim":
                result = await self._verify_stability_claim(claim, tools_used)
            elif claim_type == "property_prediction":
                result = await self._verify_property_prediction(claim, tools_used)
            elif claim_type == "novel_material":
                result = await self._verify_novel_material(claim, tools_used)
            else:
                result = MaterialsVerificationResult(
                    status=VerificationStatus.ERROR,
                    verified=False,
                    message=f"Unimplemented claim type: {claim_type}",
                    claim_id=claim_id,
                    claim_type=claim_type,
                )

            # Set timestamps and tools
            result.claim_id = claim_id
            result.claim_type = claim_type
            result.started_at = started_at
            result.completed_at = datetime.utcnow()
            result.tools_used = tools_used

            return result

        except Exception as e:
            logger.exception("materials_verification_error", claim_id=claim_id)
            return MaterialsVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message=f"Verification failed: {str(e)}",
                claim_id=claim_id,
                claim_type=claim_type,
                error_type="verification_exception",
                error_details=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
                tools_used=tools_used,
            )

    async def _verify_structure_prediction(
        self,
        claim: dict[str, Any],
        tools_used: list[str],
    ) -> MaterialsVerificationResult:
        """Verify a crystal structure prediction claim."""
        composition = claim.get("composition", "")
        cif_string = claim.get("structure_cif", "")
        claimed_space_group = claim.get("space_group")
        claimed_energy = claim.get("energy_per_atom")

        if not cif_string:
            return MaterialsVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message="CIF structure required for structure prediction verification",
                error_type="missing_structure",
            )

        # Parse CIF
        try:
            structure = parse_cif(cif_string)
            tools_used.append("cif_parser")
        except Exception as e:
            return MaterialsVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message=f"Failed to parse CIF: {str(e)}",
                error_type="cif_parse_error",
                error_details=str(e),
            )

        # Validate structure
        validation = await self._structure_validator.validate_structure(structure)
        tools_used.append("structure_validator")
        structure_valid = validation.get("valid", False)

        if not structure_valid:
            return MaterialsVerificationResult(
                status=VerificationStatus.REFUTED,
                verified=False,
                message=f"Structure validation failed: {validation.get('issues', [])}",
                structure=structure,
                structure_valid=False,
            )

        # Analyze symmetry
        symmetry = await self._symmetry_analyzer.analyze_symmetry(structure)
        tools_used.append("symmetry_analyzer")

        # Compare claimed space group
        if claimed_space_group:
            comparison = await self._symmetry_analyzer.compare_symmetry(
                structure,
                claimed_space_group=claimed_space_group,
            )
            if not comparison.get("symmetry_verified", True):
                return MaterialsVerificationResult(
                    status=VerificationStatus.PARTIAL,
                    verified=False,
                    message=f"Space group mismatch: claimed {claimed_space_group}, "
                            f"found {symmetry.get('space_group_symbol')}",
                    structure=structure,
                    structure_valid=True,
                )

        # Calculate energy
        energy = await self._mlip_service.calculate_energy(structure)
        tools_used.append(f"mlip:{energy.model_used}")

        # Check stability
        stability = await self._mp_client.calculate_stability(
            composition=structure.composition,
            energy_per_atom=energy.energy_per_atom,
        )
        tools_used.append("materials_project")

        # Determine verification status
        if stability.is_stable:
            status = VerificationStatus.VERIFIED
            verified = True
            message = f"Structure verified: stable ({stability.energy_above_hull:.3f} eV above hull)"
        elif stability.is_metastable:
            status = VerificationStatus.PARTIAL
            verified = True
            message = f"Structure metastable: {stability.energy_above_hull:.3f} eV above hull"
        else:
            status = VerificationStatus.REFUTED
            verified = False
            message = f"Structure unstable: {stability.energy_above_hull:.3f} eV above hull"

        return MaterialsVerificationResult(
            status=status,
            verified=verified,
            message=message,
            structure=structure,
            structure_valid=True,
            energy=energy,
            stability=stability,
        )

    async def _verify_stability_claim(
        self,
        claim: dict[str, Any],
        tools_used: list[str],
    ) -> MaterialsVerificationResult:
        """Verify a stability claim."""
        composition = claim.get("composition", "")
        cif_string = claim.get("structure_cif", "")
        claimed_hull_distance = claim.get("energy_above_hull")
        claimed_stability = claim.get("claimed_stable", True)

        if not cif_string:
            return MaterialsVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message="CIF structure required for stability verification",
                error_type="missing_structure",
            )

        # Parse and validate structure
        structure = parse_cif(cif_string)
        tools_used.append("cif_parser")

        validation = await self._structure_validator.validate_structure(structure)
        tools_used.append("structure_validator")

        if not validation.get("valid", False):
            return MaterialsVerificationResult(
                status=VerificationStatus.REFUTED,
                verified=False,
                message=f"Structure invalid: {validation.get('issues', [])}",
                structure=structure,
                structure_valid=False,
            )

        # Calculate energy with ensemble for uncertainty
        energy_results = await self._mlip_service.calculate_with_ensemble(structure)
        tools_used.extend([f"mlip:{m}" for m in energy_results.keys()])

        # Use average energy
        if energy_results:
            avg_energy = sum(r.energy_per_atom for r in energy_results.values()) / len(energy_results)
            primary_energy = list(energy_results.values())[0]
        else:
            return MaterialsVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message="Failed to calculate energy with any model",
                structure=structure,
                structure_valid=True,
                error_type="energy_calculation_failed",
            )

        # Calculate stability against phase diagram
        stability = await self._mp_client.calculate_stability(
            composition=composition or structure.composition,
            energy_per_atom=avg_energy,
        )
        tools_used.append("materials_project")

        # Verify against claimed values
        if claimed_hull_distance is not None:
            hull_match = abs(stability.energy_above_hull - claimed_hull_distance) < 0.05
        else:
            hull_match = True

        stability_match = (stability.is_stable or stability.is_metastable) == claimed_stability

        if hull_match and stability_match:
            status = VerificationStatus.VERIFIED
            verified = True
            message = f"Stability claim verified: {stability.energy_above_hull:.3f} eV above hull"
        elif stability_match:
            status = VerificationStatus.PARTIAL
            verified = True
            message = f"Stability qualitatively correct, hull distance differs: {stability.energy_above_hull:.3f} eV"
        else:
            status = VerificationStatus.REFUTED
            verified = False
            message = f"Stability claim refuted: calculated {stability.energy_above_hull:.3f} eV above hull"

        return MaterialsVerificationResult(
            status=status,
            verified=verified,
            message=message,
            structure=structure,
            structure_valid=True,
            energy=primary_energy,
            stability=stability,
        )

    async def _verify_property_prediction(
        self,
        claim: dict[str, Any],
        tools_used: list[str],
    ) -> MaterialsVerificationResult:
        """Verify a property prediction claim."""
        composition = claim.get("composition", "")
        property_type = claim.get("property_type", "")
        predicted_value = claim.get("predicted_value")
        predicted_unit = claim.get("unit", "")
        cif_string = claim.get("structure_cif")

        # Parse structure if provided
        structure = None
        if cif_string:
            structure = parse_cif(cif_string)
            tools_used.append("cif_parser")

        # Try to find material in Materials Project
        mp_materials = await self._mp_client.search_by_formula(composition, max_results=5)
        tools_used.append("materials_project")

        if not mp_materials:
            return MaterialsVerificationResult(
                status=VerificationStatus.INCONCLUSIVE,
                verified=False,
                message=f"No reference data found for {composition} in Materials Project",
                structure=structure,
                structure_valid=structure is not None,
            )

        # Get reference value for property
        reference_value = None
        for mat in mp_materials:
            if property_type == "band_gap" and mat.band_gap is not None:
                reference_value = mat.band_gap
                break
            elif property_type == "formation_energy":
                reference_value = mat.energy_above_hull
                break

        if reference_value is None:
            return MaterialsVerificationResult(
                status=VerificationStatus.INCONCLUSIVE,
                verified=False,
                message=f"No reference {property_type} data available",
                structure=structure,
                structure_valid=structure is not None,
            )

        # Compare with prediction
        property_prediction = PropertyPrediction(
            property_name=property_type,
            value=predicted_value,
            unit=predicted_unit,
            method="predicted",
        )

        # Allow 20% tolerance
        tolerance = abs(reference_value * 0.2)
        matches = abs(predicted_value - reference_value) <= tolerance

        if matches:
            status = VerificationStatus.VERIFIED
            verified = True
            message = f"Property prediction verified: {predicted_value} vs reference {reference_value:.3f}"
        else:
            status = VerificationStatus.REFUTED
            verified = False
            message = f"Property prediction differs: {predicted_value} vs reference {reference_value:.3f}"

        return MaterialsVerificationResult(
            status=status,
            verified=verified,
            message=message,
            structure=structure,
            structure_valid=structure is not None,
            properties=[property_prediction],
        )

    async def _verify_novel_material(
        self,
        claim: dict[str, Any],
        tools_used: list[str],
    ) -> MaterialsVerificationResult:
        """Verify a novel material discovery claim."""
        cif_string = claim.get("structure_cif", "")

        if not cif_string:
            return MaterialsVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message="CIF structure required for novelty verification",
                error_type="missing_structure",
            )

        # Parse and validate structure
        structure = parse_cif(cif_string)
        tools_used.append("cif_parser")

        validation = await self._structure_validator.validate_structure(structure)
        tools_used.append("structure_validator")

        if not validation.get("valid", False):
            return MaterialsVerificationResult(
                status=VerificationStatus.REFUTED,
                verified=False,
                message=f"Structure invalid: {validation.get('issues', [])}",
                structure=structure,
                structure_valid=False,
            )

        # Check novelty across databases
        novelty = await self._novelty_checker.check_novelty(structure)
        tools_used.extend(["novelty_checker", "materials_project", "aflow", "oqmd"])

        # Calculate energy and stability
        energy = await self._mlip_service.calculate_energy(structure)
        tools_used.append(f"mlip:{energy.model_used}")

        stability = await self._mp_client.calculate_stability(
            composition=structure.composition,
            energy_per_atom=energy.energy_per_atom,
        )

        # Determine verification status
        if novelty.is_novel and stability.is_stable:
            status = VerificationStatus.VERIFIED
            verified = True
            message = f"Novel stable material confirmed: novelty score {novelty.novelty_score:.2f}"
        elif novelty.is_novel and stability.is_metastable:
            status = VerificationStatus.PARTIAL
            verified = True
            message = f"Novel metastable material: novelty {novelty.novelty_score:.2f}, {stability.energy_above_hull:.3f} eV above hull"
        elif novelty.is_novel:
            status = VerificationStatus.PARTIAL
            verified = False
            message = f"Material is novel but unstable: {stability.energy_above_hull:.3f} eV above hull"
        else:
            status = VerificationStatus.REFUTED
            verified = False
            closest = novelty.closest_match
            message = f"Material not novel: similar to {closest.material_id if closest else 'unknown'}"

        return MaterialsVerificationResult(
            status=status,
            verified=verified,
            message=message,
            structure=structure,
            structure_valid=True,
            energy=energy,
            stability=stability,
            novelty=novelty,
        )

    async def verify_structure(
        self,
        cif_string: str,
    ) -> dict[str, Any]:
        """
        Verify a crystal structure.

        Args:
            cif_string: CIF format structure

        Returns:
            Dict with structure validation results
        """
        structure = parse_cif(cif_string)
        validation = await self._structure_validator.validate_structure(structure)
        symmetry = await self._symmetry_analyzer.analyze_symmetry(structure)

        return {
            "structure": structure.to_dict(),
            "validation": validation,
            "symmetry": symmetry,
        }

    async def calculate_energy(
        self,
        cif_string: str,
        model: str | None = None,
    ) -> EnergyResult:
        """
        Calculate energy for a structure.

        Args:
            cif_string: CIF format structure
            model: MLIP model to use

        Returns:
            EnergyResult with calculated energy
        """
        structure = parse_cif(cif_string)
        return await self._mlip_service.calculate_energy(structure, model)

    async def check_stability(
        self,
        cif_string: str,
    ) -> StabilityResult:
        """
        Check thermodynamic stability.

        Args:
            cif_string: CIF format structure

        Returns:
            StabilityResult with stability analysis
        """
        structure = parse_cif(cif_string)
        energy = await self._mlip_service.calculate_energy(structure)

        return await self._mp_client.calculate_stability(
            composition=structure.composition,
            energy_per_atom=energy.energy_per_atom,
        )

    async def check_novelty(
        self,
        cif_string: str,
    ) -> MaterialsNoveltyResult:
        """
        Check material novelty.

        Args:
            cif_string: CIF format structure

        Returns:
            MaterialsNoveltyResult with novelty assessment
        """
        structure = parse_cif(cif_string)
        return await self._novelty_checker.check_novelty(structure)

    def get_available_models(self) -> list[dict[str, Any]]:
        """Get list of available MLIP models."""
        return self._mlip_service.get_available_models()

    def get_claim_types(self) -> dict[str, Any]:
        """Get supported claim types."""
        return MATERIALS_CLAIM_TYPES
