"""Main computational biology verification service."""

from datetime import datetime
from typing import Any

from platform.verification_engines.compbio_verifier.base import (
    CompBioVerificationResult,
    HybridToolProvider,
    MCPToolProvider,
    VerificationStatus,
)
from platform.verification_engines.compbio_verifier.binder_verifier import BinderDesignVerifier
from platform.verification_engines.compbio_verifier.config import COMPBIO_CLAIM_TYPES, get_settings
from platform.verification_engines.compbio_verifier.databases import DatabaseManager
from platform.verification_engines.compbio_verifier.design_verifier import (
    DesignMetricsCalculator,
    ProteinDesignVerifier,
)
from platform.verification_engines.compbio_verifier.novelty_checker import ProteinNoveltyChecker
from platform.verification_engines.compbio_verifier.structure_predictor import (
    StructurePredictionService,
    validate_sequence,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class CompBioVerificationService:
    """
    Main service for computational biology verification.

    Orchestrates verification across:
    - Structure prediction (ESMFold, AlphaFold, Chai-1)
    - Protein design verification (pLDDT, pTM, designability)
    - Binder design verification (interface analysis)
    - Novelty checking (BLAST, Foldseek)

    Supports MCP tool integration for enhanced capabilities.
    """

    def __init__(self, mcp_provider: MCPToolProvider | None = None):
        """
        Initialize the CompBio verification service.

        Args:
            mcp_provider: Optional MCP tool provider for external tool access
        """
        # Set up hybrid tool provider (MCP + local fallback)
        self._tool_provider = HybridToolProvider(
            mcp_provider=mcp_provider,
            prefer_mcp=settings.prefer_mcp_tools,
        )

        # Initialize components
        self.structure_predictor = StructurePredictionService(self._tool_provider)
        self.design_verifier = ProteinDesignVerifier(
            self._tool_provider, self.structure_predictor
        )
        self.binder_verifier = BinderDesignVerifier(
            self._tool_provider, self.structure_predictor
        )
        self.novelty_checker = ProteinNoveltyChecker(self._tool_provider)
        self.database_manager = DatabaseManager(self._tool_provider)
        self.metrics_calculator = DesignMetricsCalculator()

    async def verify_claim(
        self,
        claim_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Verify a computational biology claim.

        This is the main entry point called by the Celery task.

        Args:
            claim_id: ID of the claim being verified
            payload: Claim payload containing:
                - claim_type: Type of claim (protein_structure, protein_design, etc.)
                - sequence: Protein sequence
                - target_structure: Target structure for design claims
                - design_sequence: Designed sequence
                - check_novelty: Whether to check novelty

        Returns:
            Verification result dictionary
        """
        started_at = datetime.utcnow()

        # Extract claim type
        claim_type = payload.get("claim_type", "protein_structure")
        sequence = payload.get("sequence", "")

        logger.info(
            "compbio_verification_started",
            claim_id=claim_id,
            claim_type=claim_type,
            sequence_length=len(sequence),
        )

        result = CompBioVerificationResult(
            status=VerificationStatus.PENDING,
            verified=False,
            message="Verification in progress",
            claim_id=claim_id,
            claim_type=claim_type,
            started_at=started_at,
        )

        try:
            # Validate claim type
            if claim_type not in COMPBIO_CLAIM_TYPES:
                result.status = VerificationStatus.ERROR
                result.message = f"Unsupported claim type: {claim_type}"
                result.error_type = "validation_error"
                result.completed_at = datetime.utcnow()
                return result.to_dict()

            # Route to appropriate verifier
            if claim_type == "protein_structure":
                result = await self._verify_structure(claim_id, payload, started_at)

            elif claim_type == "protein_design":
                result = await self._verify_design(claim_id, payload, started_at)

            elif claim_type == "binder_design":
                result = await self._verify_binder(claim_id, payload, started_at)

            elif claim_type == "complex_prediction":
                result = await self._verify_complex(claim_id, payload, started_at)

            else:
                result.status = VerificationStatus.ERROR
                result.message = f"Claim type not implemented: {claim_type}"
                result.error_type = "not_implemented"

            # Check novelty if requested
            if payload.get("check_novelty", False) and result.verified:
                novelty = await self._check_novelty(payload, result)
                result.novelty = novelty

            result.completed_at = datetime.utcnow()

            logger.info(
                "compbio_verification_completed",
                claim_id=claim_id,
                verified=result.verified,
                status=result.status.value,
            )

            return result.to_dict()

        except Exception as e:
            logger.exception(
                "compbio_verification_error",
                claim_id=claim_id,
                error=str(e),
            )

            result.status = VerificationStatus.ERROR
            result.verified = False
            result.message = f"Verification failed: {str(e)}"
            result.error_type = "internal_error"
            result.error_details = str(e)
            result.completed_at = datetime.utcnow()

            return result.to_dict()

    async def _verify_structure(
        self,
        claim_id: str,
        payload: dict[str, Any],
        started_at: datetime,
    ) -> CompBioVerificationResult:
        """Verify structure prediction claim."""
        sequence = payload.get("sequence", "")
        predictor = payload.get("predictor", "esmfold")
        claimed_plddt = payload.get("claimed_plddt")
        claimed_ptm = payload.get("claimed_ptm")

        # Validate sequence
        valid, error = validate_sequence(sequence)
        if not valid:
            return CompBioVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message=f"Invalid sequence: {error}",
                claim_id=claim_id,
                claim_type="protein_structure",
                error_type="validation_error",
                started_at=started_at,
            )

        # Predict structure
        structure = await self.structure_predictor.predict_structure(
            sequence=sequence,
            predictor=predictor,
        )

        # Check quality thresholds
        plddt_ok = structure.mean_plddt >= settings.min_plddt_threshold
        ptm_ok = structure.ptm_score is None or structure.ptm_score >= settings.min_ptm_threshold

        # Check claimed values if provided
        claimed_ok = True
        if claimed_plddt is not None:
            # Allow 5% tolerance
            claimed_ok = claimed_ok and abs(structure.mean_plddt - claimed_plddt) < claimed_plddt * 0.05

        if claimed_ptm is not None and structure.ptm_score is not None:
            claimed_ok = claimed_ok and abs(structure.ptm_score - claimed_ptm) < 0.05

        verified = plddt_ok and ptm_ok and claimed_ok

        return CompBioVerificationResult(
            status=VerificationStatus.VERIFIED if verified else VerificationStatus.REFUTED,
            verified=verified,
            message="Structure prediction verified" if verified else "Structure quality below threshold",
            claim_id=claim_id,
            claim_type="protein_structure",
            structure=structure,
            mean_plddt=structure.mean_plddt,
            ptm_score=structure.ptm_score,
            tools_used=[predictor],
            started_at=started_at,
        )

    async def _verify_design(
        self,
        claim_id: str,
        payload: dict[str, Any],
        started_at: datetime,
    ) -> CompBioVerificationResult:
        """Verify protein design claim."""
        designed_sequence = payload.get("design_sequence", "")
        target_structure = payload.get("target_structure")
        original_sequence = payload.get("original_sequence")
        design_method = payload.get("design_method")

        # Verify design
        design_result = await self.design_verifier.verify(
            designed_sequence=designed_sequence,
            target_structure_pdb=target_structure,
            original_sequence=original_sequence,
            design_method=design_method,
        )

        # Assess quality
        structure = design_result.structure
        if structure:
            quality = self.metrics_calculator.assess_design_quality(
                structure=structure,
                self_consistency=design_result.self_consistency_score,
            )
            passed = quality.get("passed_thresholds", False)
        else:
            passed = False

        return CompBioVerificationResult(
            status=VerificationStatus.VERIFIED if passed else VerificationStatus.REFUTED,
            verified=passed,
            message="Design verified" if passed else "Design quality below threshold",
            claim_id=claim_id,
            claim_type="protein_design",
            structure=structure,
            design_result=design_result,
            mean_plddt=structure.mean_plddt if structure else None,
            ptm_score=structure.ptm_score if structure else None,
            sequence_recovery=design_result.sequence_recovery,
            tools_used=[design_method or "unknown"],
            started_at=started_at,
        )

    async def _verify_binder(
        self,
        claim_id: str,
        payload: dict[str, Any],
        started_at: datetime,
    ) -> CompBioVerificationResult:
        """Verify binder design claim."""
        binder_sequence = payload.get("binder_sequence", "")
        target_sequence = payload.get("target_sequence")
        target_pdb = payload.get("target_structure")
        binding_site = payload.get("binding_site_residues")

        # Verify binder
        binder_result = await self.binder_verifier.verify(
            binder_sequence=binder_sequence,
            target_sequence=target_sequence,
            target_pdb=target_pdb,
            binding_site_residues=binding_site,
        )

        # Assess quality
        quality = self.binder_verifier.assess_binder_quality(binder_result)
        passed = quality.get("quality_score", 0) >= 0.5

        return CompBioVerificationResult(
            status=VerificationStatus.VERIFIED if passed else VerificationStatus.REFUTED,
            verified=passed,
            message="Binder verified" if passed else "Binder quality below threshold",
            claim_id=claim_id,
            claim_type="binder_design",
            complex_structure=binder_result.complex_structure,
            binder_result=binder_result,
            mean_plddt=binder_result.interface_plddt,
            tools_used=["alphafold_multimer"],
            started_at=started_at,
        )

    async def _verify_complex(
        self,
        claim_id: str,
        payload: dict[str, Any],
        started_at: datetime,
    ) -> CompBioVerificationResult:
        """Verify complex structure prediction claim."""
        sequences = payload.get("sequences", [])
        claimed_iptm = payload.get("claimed_iptm")

        if len(sequences) < 2:
            return CompBioVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message="Complex prediction requires at least 2 sequences",
                claim_id=claim_id,
                claim_type="complex_prediction",
                error_type="validation_error",
                started_at=started_at,
            )

        # Predict complex
        complex_struct = await self.structure_predictor.predict_complex(
            sequences=sequences,
            predictor=payload.get("predictor", "alphafold"),
        )

        # Check quality
        iptm_ok = complex_struct.iptm_score is None or complex_struct.iptm_score >= 0.5
        interface_pae_ok = complex_struct.interface_pae is None or complex_struct.interface_pae <= 10.0

        verified = iptm_ok and interface_pae_ok

        # Check claimed values
        if claimed_iptm and complex_struct.iptm_score:
            if abs(complex_struct.iptm_score - claimed_iptm) > 0.1:
                verified = False

        return CompBioVerificationResult(
            status=VerificationStatus.VERIFIED if verified else VerificationStatus.REFUTED,
            verified=verified,
            message="Complex prediction verified" if verified else "Complex quality below threshold",
            claim_id=claim_id,
            claim_type="complex_prediction",
            complex_structure=complex_struct,
            ptm_score=complex_struct.iptm_score,
            tools_used=["alphafold_multimer"],
            started_at=started_at,
        )

    async def _check_novelty(
        self,
        payload: dict[str, Any],
        result: CompBioVerificationResult,
    ) -> Any:
        """Check novelty of verified protein."""
        sequence = payload.get("sequence") or payload.get("design_sequence", "")
        structure = result.structure

        return await self.novelty_checker.check_novelty(
            sequence=sequence,
            structure=structure,
            check_sequence=True,
            check_structure=structure is not None and structure.pdb_string is not None,
        )

    async def verify_quick(
        self,
        sequence: str,
        predictor: str = "esmfold",
    ) -> dict[str, Any]:
        """Quick structure verification without full pipeline."""
        return await self.verify_claim(
            claim_id="quick-verify",
            payload={
                "claim_type": "protein_structure",
                "sequence": sequence,
                "predictor": predictor,
            },
        )

    def get_supported_claim_types(self) -> list[dict[str, Any]]:
        """Get list of supported claim types."""
        return [
            {
                "id": claim_id,
                "name": info["name"],
                "description": info["description"],
                "required_fields": info["required_fields"],
                "optional_fields": info["optional_fields"],
            }
            for claim_id, info in COMPBIO_CLAIM_TYPES.items()
        ]

    async def discover_mcp_tools(self) -> list[dict[str, Any]]:
        """Discover available MCP tools."""
        tools = await self._tool_provider.discover_tools()
        return [t.to_dict() for t in tools]


# Singleton instance
_service_instance: CompBioVerificationService | None = None


def get_compbio_verification_service() -> CompBioVerificationService:
    """Get or create the CompBio verification service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = CompBioVerificationService()
    return _service_instance
