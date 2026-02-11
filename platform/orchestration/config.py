"""Configuration for Research Orchestration Layer."""

from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


class OrchestrationSettings(BaseSettings):
    """Settings for research orchestration."""

    model_config = {"env_prefix": "ORCHESTRATION_", "case_sensitive": False}

    # Workflow Settings
    max_concurrent_workflows: int = Field(
        default=100,
        description="Maximum concurrent research workflows",
    )
    workflow_timeout_hours: int = Field(
        default=24,
        description="Default workflow timeout in hours",
    )
    max_workflow_steps: int = Field(
        default=50,
        description="Maximum steps in a single workflow",
    )

    # Task Settings
    max_task_retries: int = Field(
        default=3,
        description="Maximum retries for failed tasks",
    )
    task_timeout_minutes: int = Field(
        default=60,
        description="Default task timeout in minutes",
    )
    task_priority_levels: int = Field(
        default=5,
        description="Number of priority levels (1=highest)",
    )

    # Claim Routing Settings
    claim_analysis_timeout: int = Field(
        default=30,
        description="Timeout for claim analysis in seconds",
    )
    min_routing_confidence: float = Field(
        default=0.7,
        description="Minimum confidence for automatic routing",
    )

    # Session Settings
    session_ttl_hours: int = Field(
        default=72,
        description="Session time-to-live in hours",
    )
    checkpoint_interval_minutes: int = Field(
        default=5,
        description="Interval between session checkpoints",
    )
    max_sessions_per_agent: int = Field(
        default=10,
        description="Maximum active sessions per agent",
    )

    # Queue Settings
    default_queue: str = Field(
        default="research.default",
        description="Default task queue",
    )
    high_priority_queue: str = Field(
        default="research.priority",
        description="High priority task queue",
    )

    # Resource Limits
    max_memory_per_workflow_gb: int = Field(
        default=32,
        description="Maximum memory per workflow (GB)",
    )
    max_cpu_per_workflow: int = Field(
        default=8,
        description="Maximum CPUs per workflow",
    )

    # Database Settings
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for session storage",
    )
    postgres_url: str = Field(
        default="postgresql://localhost/research_platform",
        description="PostgreSQL URL for persistent storage",
    )


@lru_cache
def get_settings() -> OrchestrationSettings:
    """Get cached orchestration settings."""
    return OrchestrationSettings()


# Research Domains
RESEARCH_DOMAINS = {
    "mathematics": {
        "name": "Mathematics",
        "verification_engine": "math_verifier",
        "queue": "verify.math",
        "keywords": ["proof", "theorem", "lemma", "conjecture", "axiom", "corollary"],
        "file_extensions": [".lean", ".v", ".smt2"],
    },
    "ml_ai": {
        "name": "Machine Learning / AI",
        "verification_engine": "ml_verifier",
        "queue": "verify.ml",
        "keywords": ["model", "training", "accuracy", "benchmark", "dataset", "neural"],
        "file_extensions": [".py", ".ipynb", ".yaml"],
    },
    "computational_biology": {
        "name": "Computational Biology",
        "verification_engine": "compbio_verifier",
        "queue": "verify.compbio",
        "keywords": ["protein", "structure", "folding", "binding", "sequence", "alphafold"],
        "file_extensions": [".pdb", ".fasta", ".cif"],
    },
    "materials_science": {
        "name": "Materials Science",
        "verification_engine": "materials_verifier",
        "queue": "verify.materials",
        "keywords": ["crystal", "lattice", "stability", "energy", "composition", "structure"],
        "file_extensions": [".cif", ".poscar", ".xyz"],
    },
    "bioinformatics": {
        "name": "Bioinformatics",
        "verification_engine": "bioinfo_verifier",
        "queue": "verify.bioinfo",
        "keywords": ["gene", "expression", "variant", "pipeline", "sequencing", "alignment"],
        "file_extensions": [".vcf", ".bam", ".fastq", ".nf", ".smk"],
    },
}

# Workflow Templates
WORKFLOW_TEMPLATES = {
    "hypothesis_verification": {
        "name": "Hypothesis Verification",
        "description": "Verify a scientific hypothesis with evidence",
        "steps": [
            "parse_hypothesis",
            "extract_claims",
            "route_claims",
            "verify_claims",
            "aggregate_results",
            "generate_report",
        ],
    },
    "literature_review": {
        "name": "Literature Review",
        "description": "Conduct automated literature review",
        "steps": [
            "define_scope",
            "search_literature",
            "filter_results",
            "extract_claims",
            "synthesize_findings",
            "generate_report",
        ],
    },
    "experiment_reproduction": {
        "name": "Experiment Reproduction",
        "description": "Reproduce experimental results",
        "steps": [
            "parse_experiment",
            "setup_environment",
            "execute_experiment",
            "collect_results",
            "compare_results",
            "generate_report",
        ],
    },
    "claim_verification": {
        "name": "Single Claim Verification",
        "description": "Verify a single scientific claim",
        "steps": [
            "analyze_claim",
            "route_to_verifier",
            "execute_verification",
            "format_result",
        ],
    },
    "multi_domain_research": {
        "name": "Multi-Domain Research",
        "description": "Research spanning multiple domains",
        "steps": [
            "decompose_problem",
            "assign_domains",
            "parallel_research",
            "cross_validate",
            "integrate_findings",
            "generate_report",
        ],
    },
}

# Task Types
TASK_TYPES = {
    "claim_extraction": {
        "name": "Claim Extraction",
        "description": "Extract verifiable claims from text",
        "timeout_minutes": 10,
        "retries": 2,
    },
    "claim_verification": {
        "name": "Claim Verification",
        "description": "Verify a scientific claim",
        "timeout_minutes": 60,
        "retries": 3,
    },
    "literature_search": {
        "name": "Literature Search",
        "description": "Search scientific literature",
        "timeout_minutes": 15,
        "retries": 2,
    },
    "data_analysis": {
        "name": "Data Analysis",
        "description": "Analyze research data",
        "timeout_minutes": 30,
        "retries": 2,
    },
    "report_generation": {
        "name": "Report Generation",
        "description": "Generate research report",
        "timeout_minutes": 15,
        "retries": 1,
    },
    "experiment_execution": {
        "name": "Experiment Execution",
        "description": "Execute computational experiment",
        "timeout_minutes": 120,
        "retries": 2,
    },
}

# Claim Types to Domain Mapping
CLAIM_TYPE_DOMAINS = {
    # Mathematics
    "proof_verification": "mathematics",
    "theorem_claim": "mathematics",
    "formal_verification": "mathematics",
    # ML/AI
    "model_performance": "ml_ai",
    "benchmark_result": "ml_ai",
    "reproducibility_claim": "ml_ai",
    # Computational Biology
    "structure_prediction": "computational_biology",
    "protein_design": "computational_biology",
    "binding_affinity": "computational_biology",
    # Materials Science
    "crystal_structure": "materials_science",
    "stability_claim": "materials_science",
    "property_prediction": "materials_science",
    "novel_material": "materials_science",
    # Bioinformatics
    "de_analysis": "bioinformatics",
    "variant_claim": "bioinformatics",
    "pipeline_result": "bioinformatics",
    "enrichment_claim": "bioinformatics",
    "statistical_claim": "bioinformatics",
}

# Status Values
WORKFLOW_STATUSES = [
    "pending",
    "running",
    "paused",
    "completed",
    "failed",
    "cancelled",
    "timeout",
]

TASK_STATUSES = [
    "pending",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "retrying",
]

CLAIM_STATUSES = [
    "pending",
    "routing",
    "verifying",
    "verified",
    "refuted",
    "inconclusive",
    "error",
]
