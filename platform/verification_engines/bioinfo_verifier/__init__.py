"""Bioinformatics Verification Engine.

This module provides verification of bioinformatics claims including:
- Pipeline execution (Nextflow, Snakemake)
- Statistical validation (p-values, effect sizes, multiple testing)
- Sequence analysis (FASTA/FASTQ, alignment, variants)
- Differential expression (DESeq2, edgeR, limma)

The engine is MCP-aware and can integrate with external tools via
the Model Context Protocol for enhanced capabilities.
"""

from platform.verification_engines.bioinfo_verifier.base import (
    AlignmentResult,
    BaseBioinfoVerifier,
    BioinfoVerificationResult,
    DEGene,
    DEResult,
    EnrichmentTerm,
    HybridToolProvider,
    LocalToolProvider,
    MCPToolInfo,
    MCPToolProvider,
    MultipleTestingCorrection,
    PipelineConfig,
    PipelineOutput,
    PipelineResult,
    PipelineStatus,
    SequenceInfo,
    StatisticalSignificance,
    StatisticalTest,
    StatisticalValidation,
    VariantCall,
    VerificationStatus,
)
from platform.verification_engines.bioinfo_verifier.config import (
    ANALYSIS_TYPES,
    BIOINFO_CLAIM_TYPES,
    PIPELINE_TYPES,
    SEQUENCE_FORMATS,
    STATISTICAL_METHODS,
    get_settings,
)
from platform.verification_engines.bioinfo_verifier.de_validator import DEValidator
from platform.verification_engines.bioinfo_verifier.pipeline_runner import PipelineRunner
from platform.verification_engines.bioinfo_verifier.sequence_tools import (
    FastaParser,
    FastqParser,
    SequenceAnalyzer,
    VCFParser,
)
from platform.verification_engines.bioinfo_verifier.service import (
    BioinfoVerificationService,
    get_bioinfo_verification_service,
)
from platform.verification_engines.bioinfo_verifier.stats_validator import (
    StatisticalValidator,
)

__all__ = [
    # Config
    "get_settings",
    "PIPELINE_TYPES",
    "ANALYSIS_TYPES",
    "STATISTICAL_METHODS",
    "SEQUENCE_FORMATS",
    "BIOINFO_CLAIM_TYPES",
    # MCP
    "MCPToolProvider",
    "MCPToolInfo",
    "LocalToolProvider",
    "HybridToolProvider",
    # Base classes
    "BaseBioinfoVerifier",
    "VerificationStatus",
    "PipelineStatus",
    "StatisticalSignificance",
    # Pipeline data classes
    "PipelineConfig",
    "PipelineOutput",
    "PipelineResult",
    # Statistical data classes
    "StatisticalTest",
    "MultipleTestingCorrection",
    "StatisticalValidation",
    # Sequence data classes
    "SequenceInfo",
    "AlignmentResult",
    "VariantCall",
    # DE data classes
    "DEGene",
    "DEResult",
    "EnrichmentTerm",
    # Result class
    "BioinfoVerificationResult",
    # Services
    "BioinfoVerificationService",
    "get_bioinfo_verification_service",
    "PipelineRunner",
    "StatisticalValidator",
    "SequenceAnalyzer",
    "DEValidator",
    # Parsers
    "FastaParser",
    "FastqParser",
    "VCFParser",
]
