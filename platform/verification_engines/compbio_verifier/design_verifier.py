"""Protein design verification with quality metrics."""

from datetime import datetime
from typing import Any

from platform.verification_engines.compbio_verifier.base import (
    BaseCompBioVerifier,
    DesignResult,
    MCPToolProvider,
    ProteinStructure,
    VerificationStatus,
)
from platform.verification_engines.compbio_verifier.config import get_settings
from platform.verification_engines.compbio_verifier.structure_predictor import (
    StructurePredictionService,
    validate_sequence,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def calculate_sequence_recovery(seq1: str, seq2: str) -> float:
    """Calculate sequence identity between two sequences."""
    if len(seq1) != len(seq2):
        # Align sequences if different lengths
        min_len = min(len(seq1), len(seq2))
        seq1 = seq1[:min_len]
        seq2 = seq2[:min_len]

    if not seq1:
        return 0.0

    matches = sum(1 for a, b in zip(seq1, seq2) if a == b)
    return matches / len(seq1)


class ProteinDesignVerifier(BaseCompBioVerifier):
    """
    Verifies protein design claims.

    Performs:
    - Structure prediction of designed sequence
    - Quality assessment (pLDDT, pTM)
    - Self-consistency check (inverse folding)
    - Designability assessment
    """

    def __init__(
        self,
        tool_provider: MCPToolProvider | None = None,
        structure_predictor: StructurePredictionService | None = None,
    ):
        """Initialize design verifier."""
        super().__init__(tool_provider)
        self._structure_predictor = structure_predictor or StructurePredictionService(tool_provider)

    @property
    def component_name(self) -> str:
        return "design_verifier"

    async def verify(
        self,
        designed_sequence: str,
        target_structure_pdb: str | None = None,
        original_sequence: str | None = None,
        design_method: str | None = None,
        **kwargs,
    ) -> DesignResult:
        """
        Verify a protein design.

        Args:
            designed_sequence: The designed amino acid sequence
            target_structure_pdb: Optional target structure PDB string
            original_sequence: Original sequence if redesigning
            design_method: Method used for design
            **kwargs: Additional arguments

        Returns:
            DesignResult with verification metrics
        """
        # Validate sequence
        valid, error = validate_sequence(designed_sequence)
        if not valid:
            raise ValueError(f"Invalid designed sequence: {error}")

        logger.info(
            "design_verification_started",
            sequence_length=len(designed_sequence),
            has_target=target_structure_pdb is not None,
        )

        # Step 1: Predict structure of designed sequence
        predicted_structure = await self._structure_predictor.predict_structure(
            sequence=designed_sequence,
            predictor=kwargs.get("predictor", "esmfold"),
        )

        # Step 2: Check quality thresholds
        quality_passed = self._check_quality_thresholds(predicted_structure)

        # Step 3: Self-consistency check
        self_consistency = None
        if settings.min_sequence_recovery > 0:
            self_consistency = await self._check_self_consistency(
                designed_sequence=designed_sequence,
                predicted_structure=predicted_structure,
            )

        # Step 4: Calculate sequence recovery if original provided
        sequence_recovery = None
        if original_sequence:
            sequence_recovery = calculate_sequence_recovery(
                original_sequence, designed_sequence
            )

        result = DesignResult(
            designed_sequence=designed_sequence,
            original_sequence=original_sequence,
            structure=predicted_structure,
            sequence_recovery=sequence_recovery,
            self_consistency_score=self_consistency,
            design_method=design_method or "unknown",
        )

        logger.info(
            "design_verification_completed",
            mean_plddt=predicted_structure.mean_plddt,
            quality_passed=quality_passed,
            self_consistency=self_consistency,
        )

        return result

    def _check_quality_thresholds(self, structure: ProteinStructure) -> bool:
        """Check if structure meets quality thresholds."""
        # Check pLDDT
        if structure.mean_plddt < settings.min_plddt_threshold:
            return False

        # Check pTM if available
        if structure.ptm_score is not None:
            if structure.ptm_score < settings.min_ptm_threshold:
                return False

        return True

    async def _check_self_consistency(
        self,
        designed_sequence: str,
        predicted_structure: ProteinStructure,
    ) -> float:
        """
        Check self-consistency of design via inverse folding.

        Uses ProteinMPNN or similar to predict sequence from structure,
        then compares with original designed sequence.
        """
        # Check for MCP inverse folding tool
        if await self._has_tool("proteinmpnn_design"):
            result = await self._invoke_tool(
                tool_name="proteinmpnn_design",
                parameters={
                    "pdb_string": predicted_structure.pdb_string,
                    "num_samples": 1,
                    "temperature": 0.1,
                },
            )

            recovered_sequence = result.get("sequences", [[""])[0]
            return calculate_sequence_recovery(designed_sequence, recovered_sequence)

        # Fall back to local implementation
        return await self._run_proteinmpnn_selfconsistency(
            designed_sequence, predicted_structure
        )

    async def _run_proteinmpnn_selfconsistency(
        self,
        designed_sequence: str,
        structure: ProteinStructure,
    ) -> float:
        """Run ProteinMPNN self-consistency check locally."""
        if not structure.pdb_string:
            return 0.0

        # This would run ProteinMPNN via container
        # For now, return a placeholder
        # In production, this runs ProteinMPNN and compares sequences

        return 0.0

    async def verify_designability(
        self,
        sequence: str,
        num_samples: int = 4,
        predictor: str = "esmfold",
    ) -> dict[str, Any]:
        """
        Assess designability of a protein sequence.

        Runs multiple structure predictions and checks consistency.

        Args:
            sequence: Protein sequence to assess
            num_samples: Number of prediction samples
            predictor: Structure prediction method

        Returns:
            Designability assessment results
        """
        structures = []

        for i in range(num_samples):
            struct = await self._structure_predictor.predict_structure(
                sequence=sequence,
                predictor=predictor,
            )
            structures.append(struct)

        # Calculate metrics
        mean_plddt_values = [s.mean_plddt for s in structures]
        ptm_values = [s.ptm_score for s in structures if s.ptm_score]

        avg_plddt = sum(mean_plddt_values) / len(mean_plddt_values)
        plddt_std = (
            sum((x - avg_plddt) ** 2 for x in mean_plddt_values) / len(mean_plddt_values)
        ) ** 0.5

        avg_ptm = sum(ptm_values) / len(ptm_values) if ptm_values else None

        # Designability score (higher is better)
        designability_score = avg_plddt / 100.0  # Normalize to 0-1

        # Consistency check (low std is better)
        consistency = 1.0 - min(plddt_std / 20.0, 1.0)

        return {
            "designability_score": designability_score,
            "consistency_score": consistency,
            "avg_plddt": avg_plddt,
            "plddt_std": plddt_std,
            "avg_ptm": avg_ptm,
            "num_samples": num_samples,
            "all_structures": [s.to_dict() for s in structures],
        }


class DesignMetricsCalculator:
    """Calculates various design quality metrics."""

    @staticmethod
    def calculate_hydrophobicity(sequence: str) -> float:
        """Calculate Kyte-Doolittle hydrophobicity."""
        # Kyte-Doolittle scale
        kd_scale = {
            'A': 1.8, 'R': -4.5, 'N': -3.5, 'D': -3.5, 'C': 2.5,
            'Q': -3.5, 'E': -3.5, 'G': -0.4, 'H': -3.2, 'I': 4.5,
            'L': 3.8, 'K': -3.9, 'M': 1.9, 'F': 2.8, 'P': -1.6,
            'S': -0.8, 'T': -0.7, 'W': -0.9, 'Y': -1.3, 'V': 4.2,
        }

        total = sum(kd_scale.get(aa, 0) for aa in sequence.upper())
        return total / len(sequence) if sequence else 0.0

    @staticmethod
    def calculate_charge(sequence: str, ph: float = 7.0) -> float:
        """Calculate net charge at given pH."""
        # Simplified charge calculation
        pos_aa = set("RKH")
        neg_aa = set("DE")

        pos_count = sum(1 for aa in sequence.upper() if aa in pos_aa)
        neg_count = sum(1 for aa in sequence.upper() if aa in neg_aa)

        return pos_count - neg_count

    @staticmethod
    def calculate_instability_index(sequence: str) -> float:
        """
        Calculate instability index.

        Values > 40 suggest unstable proteins.
        """
        # Instability weights (simplified)
        dipeptide_weights = {
            ('A', 'A'): 1.0, ('A', 'W'): 1.0,
            # ... full table would have all 400 combinations
        }

        if len(sequence) < 2:
            return 0.0

        total = 0.0
        for i in range(len(sequence) - 1):
            dipeptide = (sequence[i].upper(), sequence[i+1].upper())
            total += dipeptide_weights.get(dipeptide, 1.0)

        return (10.0 / len(sequence)) * total

    @staticmethod
    def calculate_secondary_structure_propensity(sequence: str) -> dict[str, float]:
        """Estimate secondary structure propensities."""
        # Chou-Fasman propensities (simplified)
        helix_formers = set("AELM")
        sheet_formers = set("VIYW")
        turn_formers = set("GNPS")

        seq = sequence.upper()
        n = len(seq)

        helix = sum(1 for aa in seq if aa in helix_formers) / n if n else 0
        sheet = sum(1 for aa in seq if aa in sheet_formers) / n if n else 0
        turn = sum(1 for aa in seq if aa in turn_formers) / n if n else 0

        return {
            "helix_propensity": helix,
            "sheet_propensity": sheet,
            "turn_propensity": turn,
            "coil_propensity": 1.0 - helix - sheet - turn,
        }

    @staticmethod
    def assess_design_quality(
        structure: ProteinStructure,
        self_consistency: float | None = None,
    ) -> dict[str, Any]:
        """
        Comprehensive design quality assessment.

        Args:
            structure: Predicted structure
            self_consistency: Self-consistency score if available

        Returns:
            Quality assessment dictionary
        """
        # Quality tier based on pLDDT
        if structure.mean_plddt >= 90:
            quality_tier = "excellent"
        elif structure.mean_plddt >= 70:
            quality_tier = "good"
        elif structure.mean_plddt >= 50:
            quality_tier = "moderate"
        else:
            quality_tier = "poor"

        # Confidence regions
        if structure.per_residue_plddt:
            high_conf = sum(1 for p in structure.per_residue_plddt if p >= 90)
            confident = sum(1 for p in structure.per_residue_plddt if 70 <= p < 90)
            low_conf = sum(1 for p in structure.per_residue_plddt if 50 <= p < 70)
            very_low = sum(1 for p in structure.per_residue_plddt if p < 50)
            n = len(structure.per_residue_plddt)

            confidence_distribution = {
                "very_high": high_conf / n,
                "confident": confident / n,
                "low": low_conf / n,
                "very_low": very_low / n,
            }
        else:
            confidence_distribution = None

        # Overall assessment
        passed_thresholds = (
            structure.mean_plddt >= settings.min_plddt_threshold and
            (structure.ptm_score is None or structure.ptm_score >= settings.min_ptm_threshold) and
            (self_consistency is None or self_consistency >= settings.min_sequence_recovery)
        )

        return {
            "quality_tier": quality_tier,
            "mean_plddt": structure.mean_plddt,
            "ptm_score": structure.ptm_score,
            "self_consistency": self_consistency,
            "confidence_distribution": confidence_distribution,
            "passed_thresholds": passed_thresholds,
            "recommendations": _generate_recommendations(structure, self_consistency),
        }


def _generate_recommendations(
    structure: ProteinStructure,
    self_consistency: float | None,
) -> list[str]:
    """Generate recommendations for improving design."""
    recommendations = []

    if structure.mean_plddt < 70:
        recommendations.append(
            "Low confidence prediction. Consider redesigning flexible regions."
        )

    if structure.ptm_score and structure.ptm_score < 0.5:
        recommendations.append(
            "Low pTM score suggests uncertain domain arrangement."
        )

    if self_consistency is not None and self_consistency < 0.3:
        recommendations.append(
            "Low self-consistency. Structure may not be designable with this sequence."
        )

    if structure.per_residue_plddt:
        low_conf_regions = []
        in_low_region = False
        start = 0

        for i, p in enumerate(structure.per_residue_plddt):
            if p < 50 and not in_low_region:
                start = i
                in_low_region = True
            elif p >= 50 and in_low_region:
                if i - start >= 5:
                    low_conf_regions.append((start, i))
                in_low_region = False

        if low_conf_regions:
            regions_str = ", ".join([f"{s}-{e}" for s, e in low_conf_regions[:3]])
            recommendations.append(
                f"Low confidence regions: residues {regions_str}. Consider redesigning."
            )

    return recommendations if recommendations else ["Design passes quality checks."]
