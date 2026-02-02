"""Main Bioinformatics Verification Service."""

from datetime import datetime
from typing import Any

from platform.verification_engines.bioinfo_verifier.base import (
    BioinfoVerificationResult,
    MCPToolProvider,
    PipelineConfig,
    VerificationStatus,
)
from platform.verification_engines.bioinfo_verifier.config import (
    ANALYSIS_TYPES,
    BIOINFO_CLAIM_TYPES,
    get_settings,
)
from platform.verification_engines.bioinfo_verifier.de_validator import DEValidator
from platform.verification_engines.bioinfo_verifier.pipeline_runner import PipelineRunner
from platform.verification_engines.bioinfo_verifier.sequence_tools import SequenceAnalyzer
from platform.verification_engines.bioinfo_verifier.stats_validator import (
    StatisticalValidator,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class BioinfoVerificationService:
    """
    Main service for Bioinformatics verification.

    Orchestrates verification of bioinformatics claims using:
    - Pipeline execution (Nextflow, Snakemake)
    - Statistical validation
    - Sequence analysis
    - Differential expression validation

    MCP-aware: Uses MCP tools when available, falls back to local execution.
    """

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """
        Initialize Bioinformatics Verification Service.

        Args:
            tool_provider: MCP tool provider for external tools
        """
        self._tool_provider = tool_provider
        self._pipeline_runner = PipelineRunner(tool_provider)
        self._stats_validator = StatisticalValidator(tool_provider)
        self._sequence_analyzer = SequenceAnalyzer(tool_provider)
        self._de_validator = DEValidator(tool_provider)

    async def verify_claim(
        self,
        claim: dict[str, Any],
    ) -> BioinfoVerificationResult:
        """
        Verify a bioinformatics claim.

        Args:
            claim: Claim dict with:
                - claim_type: Type of claim (de_analysis, variant_claim, etc.)
                - Additional type-specific fields

        Returns:
            BioinfoVerificationResult with verification outcome
        """
        started_at = datetime.utcnow()
        claim_id = claim.get("claim_id", "")
        claim_type = claim.get("claim_type", "")
        tools_used = []

        try:
            # Validate claim type
            if claim_type not in BIOINFO_CLAIM_TYPES:
                return BioinfoVerificationResult(
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
            if claim_type == "de_analysis":
                result = await self._verify_de_claim(claim, tools_used)
            elif claim_type == "variant_claim":
                result = await self._verify_variant_claim(claim, tools_used)
            elif claim_type == "pipeline_result":
                result = await self._verify_pipeline_result(claim, tools_used)
            elif claim_type == "enrichment_claim":
                result = await self._verify_enrichment_claim(claim, tools_used)
            elif claim_type == "statistical_claim":
                result = await self._verify_statistical_claim(claim, tools_used)
            else:
                result = BioinfoVerificationResult(
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
            logger.exception("bioinfo_verification_error", claim_id=claim_id)
            return BioinfoVerificationResult(
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

    async def _verify_de_claim(
        self,
        claim: dict[str, Any],
        tools_used: list[str],
    ) -> BioinfoVerificationResult:
        """Verify a differential expression claim."""
        gene_list = claim.get("gene_list", [])
        conditions = claim.get("conditions", {})
        method = claim.get("method", "deseq2")
        pvalues = claim.get("pvalues", [])
        fold_changes = claim.get("fold_changes", [])
        counts_file = claim.get("counts_file")

        if not gene_list:
            return BioinfoVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message="Gene list required for DE verification",
                error_type="missing_genes",
            )

        # Build gene results from provided data
        genes = []
        for i, gene in enumerate(gene_list):
            gene_data = {
                "gene_id": gene if isinstance(gene, str) else gene.get("gene_id", ""),
            }
            if isinstance(gene, dict):
                gene_data.update(gene)
            if i < len(pvalues):
                gene_data["pvalue"] = pvalues[i]
            if i < len(fold_changes):
                gene_data["log2_fold_change"] = fold_changes[i]
            genes.append(gene_data)

        # Validate the DE result
        validation = await self._de_validator.validate_de_result({
            "genes": genes,
            "method": method,
            "contrast": f"{conditions.get('treatment', 'A')}_vs_{conditions.get('control', 'B')}",
        })
        tools_used.append("de_validator")

        # If counts file provided, try to reproduce
        if counts_file and conditions:
            reproduced = await self._de_validator.reproduce_de_analysis(
                counts_file=counts_file,
                sample_info=conditions.get("sample_info", {}),
                design=conditions.get("design", "~condition"),
                contrast=conditions.get("contrast", "condition"),
                method=method,
            )
            tools_used.append(f"de_analysis:{method}")

            if reproduced:
                # Compare results
                from platform.verification_engines.bioinfo_verifier.base import DEGene, DEResult

                original_genes = [
                    DEGene(
                        gene_id=g.get("gene_id", ""),
                        log2_fold_change=g.get("log2_fold_change", 0),
                        pvalue=g.get("pvalue", 1),
                        adjusted_pvalue=g.get("adjusted_pvalue", 1),
                    )
                    for g in genes
                ]
                original = DEResult(
                    method=method,
                    contrast="original",
                    genes=original_genes,
                    num_tested=len(original_genes),
                    num_significant=len([g for g in original_genes if g.is_significant]),
                    num_up=len([g for g in original_genes if g.is_significant and g.log2_fold_change > 0]),
                    num_down=len([g for g in original_genes if g.is_significant and g.log2_fold_change < 0]),
                )

                comparison = await self._de_validator.compare_de_results(original, reproduced)

                if comparison.get("concordant", False):
                    status = VerificationStatus.VERIFIED
                    verified = True
                    message = f"DE analysis reproduced successfully (concordance: {comparison['significance_concordance']:.2f})"
                else:
                    status = VerificationStatus.REFUTED
                    verified = False
                    message = f"DE results not reproducible (concordance: {comparison['significance_concordance']:.2f})"

                return BioinfoVerificationResult(
                    status=status,
                    verified=verified,
                    message=message,
                    de_result=reproduced,
                    de_validated=comparison.get("concordant", False),
                )

        # Return based on validation only
        if validation.get("valid", False):
            status = VerificationStatus.PARTIAL
            verified = True
            message = "DE statistics validated, but could not reproduce analysis"
        else:
            status = VerificationStatus.REFUTED
            verified = False
            message = f"DE validation failed: {validation.get('issues', [])}"

        return BioinfoVerificationResult(
            status=status,
            verified=verified,
            message=message,
            de_validated=validation.get("valid", False),
        )

    async def _verify_variant_claim(
        self,
        claim: dict[str, Any],
        tools_used: list[str],
    ) -> BioinfoVerificationResult:
        """Verify a variant calling claim."""
        variants = claim.get("variants", [])
        vcf_file = claim.get("vcf_file")
        caller = claim.get("caller", "")

        if not variants and not vcf_file:
            return BioinfoVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message="Variants or VCF file required",
                error_type="missing_variants",
            )

        # Parse VCF if provided
        if vcf_file:
            try:
                analysis = await self._sequence_analyzer.analyze_sequences(
                    open(vcf_file).read(),
                    format_type="vcf",
                )
                tools_used.append("vcf_parser")
            except Exception as e:
                return BioinfoVerificationResult(
                    status=VerificationStatus.ERROR,
                    verified=False,
                    message=f"Failed to parse VCF: {str(e)}",
                    error_type="vcf_parse_error",
                )
        else:
            # Build variant calls from provided data
            from platform.verification_engines.bioinfo_verifier.base import VariantCall

            variant_calls = [
                VariantCall(
                    chrom=v.get("chrom", ""),
                    pos=v.get("pos", 0),
                    ref=v.get("ref", ""),
                    alt=v.get("alt", ""),
                    quality=v.get("quality", 0),
                    filter_status=v.get("filter", "PASS"),
                    read_depth=v.get("depth"),
                    allele_frequency=v.get("af"),
                )
                for v in variants
            ]

            # Validate variants
            validation = await self._sequence_analyzer.validate_variants(variant_calls)
            tools_used.append("variant_validator")

            if validation.get("valid", False):
                status = VerificationStatus.VERIFIED
                verified = True
                message = f"Variants validated: {validation['passed_variants']}/{validation['total_variants']} passed"
            else:
                status = VerificationStatus.REFUTED
                verified = False
                message = f"Variant validation failed: {validation.get('issues', [])}"

            return BioinfoVerificationResult(
                status=status,
                verified=verified,
                message=message,
                variant_calls=variant_calls,
            )

        return BioinfoVerificationResult(
            status=VerificationStatus.PARTIAL,
            verified=True,
            message="VCF parsed successfully",
        )

    async def _verify_pipeline_result(
        self,
        claim: dict[str, Any],
        tools_used: list[str],
    ) -> BioinfoVerificationResult:
        """Verify a pipeline execution result."""
        pipeline_url = claim.get("pipeline_url", "")
        outputs = claim.get("outputs", [])
        config = claim.get("config", {})
        parameters = claim.get("parameters", {})

        if not pipeline_url:
            return BioinfoVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message="Pipeline URL required",
                error_type="missing_pipeline",
            )

        # Determine pipeline engine
        engine = "nextflow"  # Default
        if pipeline_url.endswith(".smk") or "snakemake" in pipeline_url.lower():
            engine = "snakemake"

        # Create pipeline config
        pipeline_config = PipelineConfig(
            engine=engine,
            workflow_url=pipeline_url,
            version=config.get("version"),
            parameters=parameters,
            profiles=config.get("profiles", []),
        )

        # Validate workflow
        validation = await self._pipeline_runner.validate_workflow(pipeline_config)
        tools_used.append("pipeline_validator")

        if not validation.get("valid", False):
            return BioinfoVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message=f"Pipeline validation failed: {validation.get('issues', [])}",
                error_type="pipeline_invalid",
            )

        # Run pipeline for reproduction
        result = await self._pipeline_runner.run_pipeline(pipeline_config)
        tools_used.append(f"pipeline_runner:{engine}")

        from platform.verification_engines.bioinfo_verifier.base import PipelineStatus

        if result.status == PipelineStatus.COMPLETED:
            # Compare outputs
            output_match = self._compare_outputs(outputs, result.outputs)

            if output_match:
                status = VerificationStatus.VERIFIED
                verified = True
                message = "Pipeline reproduced successfully"
            else:
                status = VerificationStatus.PARTIAL
                verified = True
                message = "Pipeline completed but outputs differ"
        else:
            status = VerificationStatus.REFUTED
            verified = False
            message = f"Pipeline failed: {result.error_message}"

        return BioinfoVerificationResult(
            status=status,
            verified=verified,
            message=message,
            pipeline_result=result,
        )

    async def _verify_enrichment_claim(
        self,
        claim: dict[str, Any],
        tools_used: list[str],
    ) -> BioinfoVerificationResult:
        """Verify a gene set enrichment claim."""
        enriched_terms = claim.get("enriched_terms", [])
        gene_list = claim.get("gene_list", [])
        background = claim.get("background", [])
        database = claim.get("database", "GO")
        pvalues = claim.get("pvalues", [])

        if not enriched_terms:
            return BioinfoVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message="Enriched terms required",
                error_type="missing_terms",
            )

        # Build enrichment terms
        from platform.verification_engines.bioinfo_verifier.base import EnrichmentTerm

        terms = []
        for i, term in enumerate(enriched_terms):
            if isinstance(term, str):
                term_data = {"term_id": term, "term_name": term}
            else:
                term_data = term

            pvalue = pvalues[i] if i < len(pvalues) else term_data.get("pvalue", 0.05)

            terms.append(EnrichmentTerm(
                term_id=term_data.get("term_id", ""),
                term_name=term_data.get("term_name", ""),
                database=database,
                pvalue=pvalue,
                adjusted_pvalue=term_data.get("adjusted_pvalue", pvalue),
                fold_enrichment=term_data.get("fold_enrichment", 1.0),
                gene_count=term_data.get("gene_count", len(gene_list)),
                genes=gene_list[:10],  # First 10 genes
            ))

        # Validate statistics
        all_pvalues = [t.pvalue for t in terms]
        correction = await self._stats_validator.apply_multiple_testing_correction(
            all_pvalues,
            method="bh",
        )
        tools_used.append("stats_validator")

        # Check if claimed significant terms remain significant after correction
        still_significant = correction.num_significant
        claimed_significant = sum(1 for t in terms if t.adjusted_pvalue < settings.fdr_threshold)

        if still_significant >= claimed_significant * 0.8:
            status = VerificationStatus.VERIFIED
            verified = True
            message = f"Enrichment validated: {still_significant} terms significant after correction"
        elif still_significant > 0:
            status = VerificationStatus.PARTIAL
            verified = True
            message = f"Partial validation: {still_significant}/{claimed_significant} terms remain significant"
        else:
            status = VerificationStatus.REFUTED
            verified = False
            message = "No terms remain significant after multiple testing correction"

        return BioinfoVerificationResult(
            status=status,
            verified=verified,
            message=message,
            enrichment_terms=terms,
        )

    async def _verify_statistical_claim(
        self,
        claim: dict[str, Any],
        tools_used: list[str],
    ) -> BioinfoVerificationResult:
        """Verify a general statistical claim."""
        test_type = claim.get("test_type", "")
        pvalue = claim.get("pvalue")
        test_statistic = claim.get("test_statistic")
        effect_size = claim.get("effect_size")
        sample_sizes = claim.get("sample_sizes", [])

        if pvalue is None:
            return BioinfoVerificationResult(
                status=VerificationStatus.ERROR,
                verified=False,
                message="P-value required for statistical claim",
                error_type="missing_pvalue",
            )

        # Validate the statistical claim
        validation = await self._stats_validator.validate_statistical_claim({
            "test_type": test_type,
            "pvalue": pvalue,
            "test_statistic": test_statistic,
            "effect_size": effect_size,
            "sample_sizes": sample_sizes,
        })
        tools_used.append("stats_validator")

        from platform.verification_engines.bioinfo_verifier.base import StatisticalSignificance

        if validation.valid:
            if validation.significance == StatisticalSignificance.SIGNIFICANT:
                status = VerificationStatus.VERIFIED
                verified = True
                message = "Statistical claim validated: significant result"
            elif validation.significance == StatisticalSignificance.MARGINAL:
                status = VerificationStatus.PARTIAL
                verified = True
                message = "Statistical claim partially validated: marginally significant"
            elif validation.significance == StatisticalSignificance.UNDERPOWERED:
                status = VerificationStatus.PARTIAL
                verified = True
                message = f"Statistical claim underpowered (power: {validation.power:.2f})"
            else:
                status = VerificationStatus.VERIFIED
                verified = True
                message = "Statistical claim validated: not significant"
        else:
            status = VerificationStatus.REFUTED
            verified = False
            message = f"Statistical claim invalid: {validation.issues}"

        return BioinfoVerificationResult(
            status=status,
            verified=verified,
            message=message,
            statistical_validation=validation,
        )

    def _compare_outputs(
        self,
        expected: list[dict[str, Any]],
        actual: list,
    ) -> bool:
        """Compare expected and actual pipeline outputs."""
        if not expected:
            return True  # No expected outputs to compare

        expected_names = {e.get("name", e.get("path", "")) for e in expected}
        actual_names = {o.name for o in actual}

        # Check if all expected outputs are present
        return expected_names <= actual_names

    def get_supported_analysis_types(self) -> dict[str, Any]:
        """Get supported analysis types."""
        return ANALYSIS_TYPES

    def get_supported_claim_types(self) -> dict[str, Any]:
        """Get supported claim types."""
        return BIOINFO_CLAIM_TYPES


def get_bioinfo_verification_service(
    tool_provider: MCPToolProvider | None = None,
) -> BioinfoVerificationService:
    """Factory function to get BioinfoVerificationService."""
    return BioinfoVerificationService(tool_provider)
