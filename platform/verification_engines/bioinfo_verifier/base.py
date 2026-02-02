"""Base classes and data structures for Bioinformatics verification."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from platform.verification_engines.compbio_verifier.base import (
    HybridToolProvider,
    LocalToolProvider,
    MCPToolInfo,
    MCPToolProvider,
)


class VerificationStatus(Enum):
    """Status of bioinformatics verification."""

    VERIFIED = "verified"
    REFUTED = "refuted"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"
    PENDING = "pending"


class PipelineStatus(Enum):
    """Status of pipeline execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class StatisticalSignificance(Enum):
    """Statistical significance classification."""

    SIGNIFICANT = "significant"
    NOT_SIGNIFICANT = "not_significant"
    MARGINAL = "marginal"
    UNDERPOWERED = "underpowered"


# ===========================================
# PIPELINE DATA CLASSES
# ===========================================


@dataclass
class PipelineConfig:
    """Configuration for a bioinformatics pipeline."""

    engine: str  # nextflow, snakemake, wdl
    workflow_url: str  # Git URL or path
    version: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    profiles: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    resume: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "workflow_url": self.workflow_url,
            "version": self.version,
            "parameters": self.parameters,
            "profiles": self.profiles,
            "config_files": self.config_files,
            "resume": self.resume,
        }


@dataclass
class PipelineOutput:
    """Output from a pipeline execution."""

    name: str
    path: str
    file_type: str
    size_bytes: int | None = None
    checksum: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "file_type": self.file_type,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "metadata": self.metadata,
        }


@dataclass
class PipelineResult:
    """Result of pipeline execution."""

    status: PipelineStatus
    exit_code: int
    outputs: list[PipelineOutput] = field(default_factory=list)
    logs: str = ""
    execution_time_seconds: float = 0.0
    resource_usage: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    work_dir: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "exit_code": self.exit_code,
            "outputs": [o.to_dict() for o in self.outputs],
            "execution_time_seconds": self.execution_time_seconds,
            "resource_usage": self.resource_usage,
            "error_message": self.error_message,
        }


# ===========================================
# STATISTICAL DATA CLASSES
# ===========================================


@dataclass
class StatisticalTest:
    """Result of a statistical test."""

    test_name: str
    test_statistic: float
    pvalue: float
    adjusted_pvalue: float | None = None
    effect_size: float | None = None
    confidence_interval: tuple[float, float] | None = None
    sample_sizes: list[int] = field(default_factory=list)
    method: str = ""
    alternative: str = "two-sided"  # two-sided, greater, less

    @property
    def is_significant(self) -> bool:
        """Check if test is significant at 0.05 level."""
        return self.pvalue < 0.05

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_name": self.test_name,
            "test_statistic": self.test_statistic,
            "pvalue": self.pvalue,
            "adjusted_pvalue": self.adjusted_pvalue,
            "effect_size": self.effect_size,
            "confidence_interval": list(self.confidence_interval) if self.confidence_interval else None,
            "sample_sizes": self.sample_sizes,
            "method": self.method,
            "alternative": self.alternative,
            "is_significant": self.is_significant,
        }


@dataclass
class MultipleTestingCorrection:
    """Result of multiple testing correction."""

    method: str  # bonferroni, bh, by, holm
    original_pvalues: list[float]
    adjusted_pvalues: list[float]
    alpha: float = 0.05
    num_significant: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "alpha": self.alpha,
            "num_tests": len(self.original_pvalues),
            "num_significant": self.num_significant,
        }


@dataclass
class StatisticalValidation:
    """Result of statistical validation."""

    valid: bool
    significance: StatisticalSignificance
    tests: list[StatisticalTest] = field(default_factory=list)
    corrections: list[MultipleTestingCorrection] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    power: float | None = None
    sample_size_adequate: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "significance": self.significance.value,
            "tests": [t.to_dict() for t in self.tests],
            "issues": self.issues,
            "warnings": self.warnings,
            "power": self.power,
            "sample_size_adequate": self.sample_size_adequate,
        }


# ===========================================
# SEQUENCE DATA CLASSES
# ===========================================


@dataclass
class SequenceInfo:
    """Information about a sequence."""

    sequence_id: str
    length: int
    sequence_type: str  # dna, rna, protein
    gc_content: float | None = None
    description: str = ""
    source_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence_id": self.sequence_id,
            "length": self.length,
            "sequence_type": self.sequence_type,
            "gc_content": self.gc_content,
            "description": self.description,
        }


@dataclass
class AlignmentResult:
    """Result of sequence alignment."""

    query_id: str
    subject_id: str
    identity: float
    coverage: float
    evalue: float | None = None
    bit_score: float | None = None
    alignment_length: int = 0
    mismatches: int = 0
    gaps: int = 0
    query_start: int = 0
    query_end: int = 0
    subject_start: int = 0
    subject_end: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "subject_id": self.subject_id,
            "identity": self.identity,
            "coverage": self.coverage,
            "evalue": self.evalue,
            "bit_score": self.bit_score,
            "alignment_length": self.alignment_length,
            "mismatches": self.mismatches,
            "gaps": self.gaps,
        }


@dataclass
class VariantCall:
    """A genomic variant call."""

    chrom: str
    pos: int
    ref: str
    alt: str
    quality: float
    filter_status: str = "PASS"
    genotype: str | None = None
    read_depth: int | None = None
    allele_frequency: float | None = None
    annotations: dict[str, Any] = field(default_factory=dict)

    @property
    def variant_id(self) -> str:
        return f"{self.chrom}:{self.pos}:{self.ref}>{self.alt}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "chrom": self.chrom,
            "pos": self.pos,
            "ref": self.ref,
            "alt": self.alt,
            "quality": self.quality,
            "filter_status": self.filter_status,
            "genotype": self.genotype,
            "read_depth": self.read_depth,
            "allele_frequency": self.allele_frequency,
        }


# ===========================================
# DIFFERENTIAL EXPRESSION DATA CLASSES
# ===========================================


@dataclass
class DEGene:
    """Differentially expressed gene."""

    gene_id: str
    gene_name: str | None = None
    log2_fold_change: float = 0.0
    pvalue: float = 1.0
    adjusted_pvalue: float = 1.0
    base_mean: float = 0.0
    lfcse: float | None = None  # Log fold change standard error

    @property
    def is_significant(self) -> bool:
        return self.adjusted_pvalue < 0.05 and abs(self.log2_fold_change) > 0.5

    @property
    def regulation(self) -> str:
        if not self.is_significant:
            return "not_significant"
        return "up" if self.log2_fold_change > 0 else "down"

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_id": self.gene_id,
            "gene_name": self.gene_name,
            "log2_fold_change": self.log2_fold_change,
            "pvalue": self.pvalue,
            "adjusted_pvalue": self.adjusted_pvalue,
            "base_mean": self.base_mean,
            "is_significant": self.is_significant,
            "regulation": self.regulation,
        }


@dataclass
class DEResult:
    """Result of differential expression analysis."""

    method: str  # deseq2, edger, limma
    contrast: str  # e.g., "treatment_vs_control"
    genes: list[DEGene] = field(default_factory=list)
    num_tested: int = 0
    num_significant: int = 0
    num_up: int = 0
    num_down: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "contrast": self.contrast,
            "num_tested": self.num_tested,
            "num_significant": self.num_significant,
            "num_up": self.num_up,
            "num_down": self.num_down,
            "genes": [g.to_dict() for g in self.genes[:100]],  # Top 100
        }


@dataclass
class EnrichmentTerm:
    """Enriched term from gene set analysis."""

    term_id: str
    term_name: str
    database: str  # GO, KEGG, Reactome
    pvalue: float
    adjusted_pvalue: float
    fold_enrichment: float = 0.0
    gene_count: int = 0
    background_count: int = 0
    genes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "term_id": self.term_id,
            "term_name": self.term_name,
            "database": self.database,
            "pvalue": self.pvalue,
            "adjusted_pvalue": self.adjusted_pvalue,
            "fold_enrichment": self.fold_enrichment,
            "gene_count": self.gene_count,
            "genes": self.genes,
        }


# ===========================================
# VERIFICATION RESULT
# ===========================================


@dataclass
class BioinfoVerificationResult:
    """Complete result of bioinformatics verification."""

    status: VerificationStatus
    verified: bool
    message: str
    claim_id: str = ""
    claim_type: str = ""

    # Pipeline results
    pipeline_result: PipelineResult | None = None

    # Statistical validation
    statistical_validation: StatisticalValidation | None = None

    # Differential expression
    de_result: DEResult | None = None
    de_validated: bool = False

    # Sequence analysis
    alignment_results: list[AlignmentResult] = field(default_factory=list)
    variant_calls: list[VariantCall] = field(default_factory=list)

    # Enrichment
    enrichment_terms: list[EnrichmentTerm] = field(default_factory=list)

    # Timestamps
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Error details
    error_type: str | None = None
    error_details: str | None = None

    # MCP tool usage
    tools_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "verified": self.verified,
            "message": self.message,
            "claim_id": self.claim_id,
            "claim_type": self.claim_type,
            "pipeline_result": self.pipeline_result.to_dict() if self.pipeline_result else None,
            "statistical_validation": self.statistical_validation.to_dict() if self.statistical_validation else None,
            "de_result": self.de_result.to_dict() if self.de_result else None,
            "de_validated": self.de_validated,
            "alignment_results": [a.to_dict() for a in self.alignment_results],
            "variant_calls": [v.to_dict() for v in self.variant_calls[:100]],
            "enrichment_terms": [e.to_dict() for e in self.enrichment_terms],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_type": self.error_type,
            "error_details": self.error_details,
            "tools_used": self.tools_used,
        }


# ===========================================
# BASE VERIFIER CLASS
# ===========================================


class BaseBioinfoVerifier(ABC):
    """Abstract base class for Bioinformatics verification components."""

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """
        Initialize verifier with optional MCP tool provider.

        Args:
            tool_provider: MCP tool provider for external tool access
        """
        self._tool_provider = tool_provider or LocalToolProvider()

    @property
    @abstractmethod
    def component_name(self) -> str:
        """Name of this verification component."""
        pass

    @abstractmethod
    async def verify(self, *args, **kwargs) -> Any:
        """Perform verification and return result."""
        pass

    async def _invoke_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Invoke a tool via the tool provider."""
        return await self._tool_provider.invoke_tool(tool_name, parameters, timeout)

    async def _has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available."""
        return await self._tool_provider.has_tool(tool_name)


# Re-export MCP classes for convenience
__all__ = [
    "MCPToolProvider",
    "MCPToolInfo",
    "LocalToolProvider",
    "HybridToolProvider",
    "BaseBioinfoVerifier",
    "VerificationStatus",
    "PipelineStatus",
    "StatisticalSignificance",
    "PipelineConfig",
    "PipelineOutput",
    "PipelineResult",
    "StatisticalTest",
    "MultipleTestingCorrection",
    "StatisticalValidation",
    "SequenceInfo",
    "AlignmentResult",
    "VariantCall",
    "DEGene",
    "DEResult",
    "EnrichmentTerm",
    "BioinfoVerificationResult",
]
