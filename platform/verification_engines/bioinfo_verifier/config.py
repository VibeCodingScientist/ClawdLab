"""Configuration for Bioinformatics verification engine."""

from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


class BioinfoVerifierSettings(BaseSettings):
    """Settings for bioinformatics verification engine."""

    model_config = {"env_prefix": "BIOINFO_VERIFIER_", "case_sensitive": False}

    # MCP Tool Provider Settings
    mcp_enabled: bool = Field(default=True, description="Enable MCP tool discovery")
    prefer_mcp_tools: bool = Field(default=True, description="Prefer MCP tools over local")

    # Pipeline Settings
    default_pipeline_engine: str = Field(
        default="nextflow",
        description="Default pipeline engine (nextflow, snakemake)",
    )
    pipeline_timeout: int = Field(
        default=7200,
        description="Pipeline execution timeout in seconds",
    )
    max_parallel_jobs: int = Field(
        default=4,
        description="Maximum parallel jobs in pipeline",
    )

    # Nextflow Settings
    nextflow_version: str = Field(
        default="23.10.0",
        description="Nextflow version to use",
    )
    nextflow_config_path: str = Field(
        default="/config/nextflow.config",
        description="Path to Nextflow configuration",
    )

    # Snakemake Settings
    snakemake_version: str = Field(
        default="8.0.0",
        description="Snakemake version to use",
    )

    # Statistical Thresholds
    pvalue_threshold: float = Field(
        default=0.05,
        description="Default p-value significance threshold",
    )
    fdr_threshold: float = Field(
        default=0.1,
        description="Default FDR threshold for multiple testing",
    )
    min_effect_size: float = Field(
        default=0.5,
        description="Minimum absolute log2 fold change",
    )
    min_samples_per_group: int = Field(
        default=3,
        description="Minimum samples per group for statistical tests",
    )

    # Sequence Analysis Settings
    min_sequence_length: int = Field(
        default=50,
        description="Minimum sequence length for analysis",
    )
    max_sequence_length: int = Field(
        default=10000000,
        description="Maximum sequence length",
    )
    alignment_identity_threshold: float = Field(
        default=0.9,
        description="Minimum alignment identity",
    )
    coverage_threshold: float = Field(
        default=0.8,
        description="Minimum alignment coverage",
    )

    # Variant Calling Settings
    min_variant_quality: float = Field(
        default=30.0,
        description="Minimum variant quality score",
    )
    min_read_depth: int = Field(
        default=10,
        description="Minimum read depth for variant calls",
    )
    min_allele_frequency: float = Field(
        default=0.1,
        description="Minimum allele frequency threshold",
    )

    # RNA-seq Settings
    min_counts_per_gene: int = Field(
        default=10,
        description="Minimum total counts per gene",
    )
    min_samples_detected: int = Field(
        default=2,
        description="Minimum samples where gene must be detected",
    )
    normalization_method: str = Field(
        default="TMM",
        description="RNA-seq normalization method (TMM, RLE, upperquartile)",
    )

    # Resource Limits
    max_memory_gb: int = Field(
        default=64,
        description="Maximum memory per task (GB)",
    )
    max_cpus: int = Field(
        default=16,
        description="Maximum CPUs per task",
    )
    max_storage_gb: int = Field(
        default=500,
        description="Maximum storage per job (GB)",
    )

    # Container Settings
    singularity_image_path: str = Field(
        default="/containers/bioinfo-verifier.sif",
        description="Path to Singularity image",
    )
    use_singularity: bool = Field(
        default=True,
        description="Use Singularity container for execution",
    )

    # External Database Settings
    ensembl_rest_endpoint: str = Field(
        default="https://rest.ensembl.org",
        description="Ensembl REST API endpoint",
    )
    ncbi_eutils_endpoint: str = Field(
        default="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        description="NCBI E-utilities endpoint",
    )
    uniprot_endpoint: str = Field(
        default="https://rest.uniprot.org",
        description="UniProt API endpoint",
    )


@lru_cache
def get_settings() -> BioinfoVerifierSettings:
    """Get cached Bioinformatics verifier settings."""
    return BioinfoVerifierSettings()


# Pipeline Types
PIPELINE_TYPES = {
    "nextflow": {
        "name": "Nextflow",
        "description": "Nextflow workflow engine",
        "config_extension": ".nf",
        "mcp_tool_name": "nextflow_run",
    },
    "snakemake": {
        "name": "Snakemake",
        "description": "Snakemake workflow engine",
        "config_extension": ".smk",
        "mcp_tool_name": "snakemake_run",
    },
    "wdl": {
        "name": "WDL/Cromwell",
        "description": "Workflow Description Language",
        "config_extension": ".wdl",
        "mcp_tool_name": "cromwell_run",
    },
}

# Analysis Types
ANALYSIS_TYPES = {
    "differential_expression": {
        "name": "Differential Expression",
        "description": "RNA-seq differential expression analysis",
        "required_fields": ["counts_matrix", "sample_groups"],
        "optional_fields": ["design_formula", "contrasts", "normalization"],
    },
    "variant_calling": {
        "name": "Variant Calling",
        "description": "Genomic variant detection",
        "required_fields": ["alignment_file", "reference_genome"],
        "optional_fields": ["intervals", "known_variants", "caller"],
    },
    "alignment_validation": {
        "name": "Alignment Validation",
        "description": "Sequence alignment quality assessment",
        "required_fields": ["alignment_file"],
        "optional_fields": ["reference", "expected_identity"],
    },
    "enrichment_analysis": {
        "name": "Enrichment Analysis",
        "description": "Gene set/pathway enrichment",
        "required_fields": ["gene_list", "background"],
        "optional_fields": ["database", "method", "cutoff"],
    },
    "metagenomics": {
        "name": "Metagenomics",
        "description": "Metagenomic profiling",
        "required_fields": ["sequence_files"],
        "optional_fields": ["database", "taxonomy_level", "min_abundance"],
    },
    "chip_seq": {
        "name": "ChIP-seq Analysis",
        "description": "ChIP-seq peak calling and analysis",
        "required_fields": ["treatment_file", "control_file"],
        "optional_fields": ["peak_caller", "genome", "fdr"],
    },
}

# Statistical Methods
STATISTICAL_METHODS = {
    "deseq2": {
        "name": "DESeq2",
        "description": "Differential expression with DESeq2",
        "r_package": "DESeq2",
    },
    "edger": {
        "name": "edgeR",
        "description": "Differential expression with edgeR",
        "r_package": "edgeR",
    },
    "limma": {
        "name": "limma-voom",
        "description": "Linear models for microarray/RNA-seq",
        "r_package": "limma",
    },
    "wilcoxon": {
        "name": "Wilcoxon",
        "description": "Non-parametric test",
        "type": "non_parametric",
    },
    "fisher": {
        "name": "Fisher's Exact",
        "description": "Enrichment test",
        "type": "categorical",
    },
}

# File Formats
SEQUENCE_FORMATS = {
    "fasta": {
        "extensions": [".fa", ".fasta", ".fna", ".faa"],
        "compressed": [".gz", ".bz2"],
    },
    "fastq": {
        "extensions": [".fq", ".fastq"],
        "compressed": [".gz", ".bz2"],
    },
    "bam": {
        "extensions": [".bam"],
        "index_extension": ".bai",
    },
    "cram": {
        "extensions": [".cram"],
        "index_extension": ".crai",
    },
    "vcf": {
        "extensions": [".vcf"],
        "compressed": [".gz"],
        "index_extension": ".tbi",
    },
    "bed": {
        "extensions": [".bed"],
        "compressed": [".gz"],
    },
    "gff": {
        "extensions": [".gff", ".gff3", ".gtf"],
        "compressed": [".gz"],
    },
}

# Claim Types
BIOINFO_CLAIM_TYPES = {
    "de_analysis": {
        "name": "Differential Expression Claim",
        "description": "Claims about differentially expressed genes",
        "required_fields": ["gene_list", "conditions", "method"],
        "optional_fields": ["counts_file", "pvalues", "fold_changes"],
    },
    "variant_claim": {
        "name": "Variant Claim",
        "description": "Claims about identified variants",
        "required_fields": ["variants", "sample_id"],
        "optional_fields": ["vcf_file", "caller", "quality_metrics"],
    },
    "pipeline_result": {
        "name": "Pipeline Result",
        "description": "Claims from bioinformatics pipeline",
        "required_fields": ["pipeline_url", "outputs"],
        "optional_fields": ["config", "version", "parameters"],
    },
    "enrichment_claim": {
        "name": "Enrichment Claim",
        "description": "Gene set enrichment claims",
        "required_fields": ["enriched_terms", "gene_list"],
        "optional_fields": ["background", "database", "pvalues"],
    },
    "statistical_claim": {
        "name": "Statistical Claim",
        "description": "General statistical claims",
        "required_fields": ["test_type", "pvalue", "test_statistic"],
        "optional_fields": ["effect_size", "sample_sizes", "confidence_interval"],
    },
}
