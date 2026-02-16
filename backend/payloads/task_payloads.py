"""Structured validation for task results by type and domain."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ------------------------------------------
# GENERIC TASK TYPE PAYLOADS (domain-agnostic)
# ------------------------------------------

class LiteratureReviewResult(BaseModel):
    """Result of a scout's literature review."""
    papers: list[dict] = Field(..., min_length=1, description="List of {title, authors, url, year, abstract}")
    summary: str = Field(..., min_length=50)
    key_findings: list[str] = Field(default_factory=list)
    gaps_identified: list[str] = Field(default_factory=list)


class Artifact(BaseModel):
    """Rich artifact reference (e.g. from BIOS analysis tasks)."""
    id: str | None = None
    name: str
    path: str
    type: str = "FILE"
    description: str | None = None


class AnalysisResult(BaseModel):
    """Result of a research analyst's analysis task."""
    methodology: str = Field(..., min_length=20)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str | Artifact] = Field(default_factory=list, description="URLs, references, or rich artifact objects")
    code_snippet: str | None = None
    raw_data: dict | None = None


class CritiqueResult(BaseModel):
    """Result of a skeptical theorist's critique."""
    target_task_id: UUID
    issues: list[str] = Field(..., min_length=1)
    severity: str = Field(..., pattern=r"^(minor|major|critical)$")
    alternative_approach: str | None = None
    evidence: list[str] = Field(default_factory=list)


class SynthesisResult(BaseModel):
    """Result of a synthesizer's synthesis task."""
    document: str = Field(..., min_length=100, description="Markdown synthesis document")
    sources: list[UUID] = Field(..., min_length=1, description="Task IDs incorporated")
    conclusions: list[str] = Field(default_factory=list)


class DeepResearchResult(BaseModel):
    """Result of a deep research task."""
    methodology: str = Field(..., min_length=20)
    findings: str = Field(..., min_length=100)
    data: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str | Artifact] = Field(default_factory=list, description="URLs, references, or rich artifact objects")


# ------------------------------------------
# DOMAIN-SPECIFIC VERIFICATION PAYLOADS
# ------------------------------------------

class MathematicsPayload(BaseModel):
    """Extra fields for mathematics domain results that are verifiable."""
    claim_type: str = Field("theorem", pattern=r"^(theorem|conjecture)$")
    proof_code: str = Field(..., min_length=10)
    statement: str | None = None
    dependencies: list[str] = Field(default_factory=list)


class MLAIPayload(BaseModel):
    """Extra fields for ML/AI domain results."""
    claim_type: str = Field("benchmark_result", pattern=r"^(benchmark_result|ml_experiment|architecture)$")
    model_id: str | None = None
    benchmark: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    code_repo: str | None = None
    code_commit: str | None = None
    code: str | None = None  # For architecture claims
    param_count: int | None = None


class CompBioPayload(BaseModel):
    """Extra fields for computational biology domain results."""
    claim_type: str = Field(
        "structure_prediction",
        pattern=r"^(structure_prediction|protein_design|binder_design)$"
    )
    sequence: str | None = None
    designed_sequence: str | None = None
    backbone_pdb: str | None = None
    claimed_structure_pdb: str | None = None
    method: str = "esmfold"
    claimed_plddt: float | None = None
    claimed_ptm: float | None = None
    claimed_sctm: float | None = None


class MaterialsSciencePayload(BaseModel):
    """Extra fields for materials science domain results."""
    claim_type: str = Field(
        "material_prediction",
        pattern=r"^(material_prediction|material_property)$"
    )
    formula: str | None = None
    structure_cif: str | None = None
    predicted_properties: dict = Field(default_factory=dict)
    computation_method: str = "mace_mp"
    materials_project_id: str | None = None


class BioinformaticsPayload(BaseModel):
    """Extra fields for bioinformatics domain results."""
    claim_type: str = Field(
        "pipeline_result",
        pattern=r"^(pipeline_result|sequence_annotation|statistical_claim)$"
    )
    pipeline_source: str | None = None
    pipeline_commit: str | None = None
    pipeline_name: str | None = None
    parameters: dict = Field(default_factory=dict)
    input_datasets: list[dict] = Field(default_factory=list)
    output_checksums: dict[str, str] = Field(default_factory=dict)
    results_summary: dict = Field(default_factory=dict)
    statistical_claims: list[dict] = Field(default_factory=list)
    sequence: str | None = None
    annotation_method: str | None = None
    annotations: list[dict] = Field(default_factory=list)


# ------------------------------------------
# VALIDATION DISPATCHER
# ------------------------------------------

# Map: task_type -> Pydantic model for the base result structure
TASK_TYPE_MODELS: dict[str, type[BaseModel]] = {
    "literature_review": LiteratureReviewResult,
    "analysis": AnalysisResult,
    "critique": CritiqueResult,
    "synthesis": SynthesisResult,
    "deep_research": DeepResearchResult,
}

# Map: domain -> Pydantic model for domain-specific verifiable fields
DOMAIN_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "mathematics": MathematicsPayload,
    "ml_ai": MLAIPayload,
    "computational_biology": CompBioPayload,
    "materials_science": MaterialsSciencePayload,
    "bioinformatics": BioinformaticsPayload,
}


def validate_task_result(
    task_type: str,
    domain: str,
    result: dict,
    strict: bool = False,
) -> tuple[bool, list[str]]:
    """
    Validate a task result against its expected schema.

    Returns (valid, errors).
    If strict=False, missing domain fields are warnings not errors.
    """
    errors: list[str] = []

    # 1. Validate task_type structure
    model = TASK_TYPE_MODELS.get(task_type)
    if model:
        try:
            model.model_validate(result)
        except Exception as e:
            errors.append(f"Task type validation failed: {e}")

    # 2. Validate domain-specific fields (if present)
    domain_model = DOMAIN_PAYLOAD_MODELS.get(domain)
    if domain_model and (strict or any(k in result for k in domain_model.model_fields)):
        try:
            domain_model.model_validate(result)
        except Exception as e:
            if strict:
                errors.append(f"Domain payload validation failed: {e}")
            # Non-strict: domain fields are optional enrichment

    return (len(errors) == 0, errors)
