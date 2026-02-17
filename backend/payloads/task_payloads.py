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
    proof_system: str = Field("lean4", pattern=r"^(lean4|coq|isabelle)$")
    proof_code: str = Field(..., min_length=10)
    statement: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    theory_name: str | None = None  # For Isabelle


class MLAIPayload(BaseModel):
    """Extra fields for ML/AI domain results."""
    claim_type: str = Field("benchmark_result", pattern=r"^(benchmark_result|benchmark_live|ml_experiment|architecture)$")
    model_id: str | None = None
    benchmark: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    code_repo: str | None = None
    code_commit: str | None = None
    code: str | None = None  # For architecture claims
    param_count: int | None = None
    sample_size: int = Field(20, ge=5, le=50)  # For benchmark_live


class CompBioPayload(BaseModel):
    """Extra fields for computational biology domain results."""
    claim_type: str = Field(
        "structure_prediction",
        pattern=r"^(structure_prediction|protein_design|binder_design|rna_structure|structure_comparison)$"
    )
    sequence: str | None = None
    designed_sequence: str | None = None
    backbone_pdb: str | None = None
    claimed_structure_pdb: str | None = None
    method: str = "esmfold"
    claimed_plddt: float | None = None
    claimed_ptm: float | None = None
    claimed_sctm: float | None = None
    # RNA structure fields
    rna_sequence: str | None = None
    dot_bracket: str | None = None
    claimed_mfe: float | None = None
    rfam_family: str | None = None
    # Structure comparison fields
    pdb_id_1: str | None = None
    pdb_id_2: str | None = None
    claimed_rmsd: float | None = None
    claimed_tm_score: float | None = None


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


class ChemistryPayload(BaseModel):
    """Extra fields for chemistry domain results."""
    claim_type: str = Field(
        "reaction_mechanism",
        pattern=r"^(reaction_mechanism|molecular_property|retrosynthesis)$",
    )
    smiles: str | None = None
    reactants: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    precursors: list[str] = Field(default_factory=list)
    claimed_properties: dict = Field(default_factory=dict)


class PhysicsPayload(BaseModel):
    """Extra fields for physics domain results."""
    claim_type: str = Field(
        "numerical_simulation",
        pattern=r"^(numerical_simulation|analytical_derivation|dimensional_analysis)$",
    )
    simulation_data: dict = Field(default_factory=dict)
    conservation_quantities: dict = Field(default_factory=dict)
    expression: str | None = None
    lhs: str | None = None
    rhs: str | None = None
    units: dict = Field(default_factory=dict)


class GenomicsPayload(BaseModel):
    """Extra fields for genomics domain results."""
    claim_type: str = Field(
        "variant_annotation",
        pattern=r"^(variant_annotation|gene_expression|gwas_association)$",
    )
    rsid: str | None = None
    gene: str | None = None
    hgvs: str | None = None
    consequence: str | None = None
    clinical_significance: str | None = None
    maf: float | None = None
    dataset_accession: str | None = None
    fold_change: float | None = None
    p_value: float | None = None
    effect_size: float | None = None
    trait: str | None = None


class EpidemiologyPayload(BaseModel):
    """Extra fields for epidemiology domain results."""
    claim_type: str = Field(
        "incidence_rate",
        pattern=r"^(incidence_rate|odds_ratio|survival_analysis)$",
    )
    rate: float | None = None
    denominator: float | None = None
    cases: int | None = None
    contingency_table: list = Field(default_factory=list)
    time_data: list = Field(default_factory=list)
    event_data: list = Field(default_factory=list)
    group_labels: list = Field(default_factory=list)
    hazard_ratio: float | None = None
    odds_ratio: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    median_survival: float | None = None


class SystemsBiologyPayload(BaseModel):
    """Extra fields for systems biology domain results."""
    claim_type: str = Field(
        "pathway_enrichment",
        pattern=r"^(pathway_enrichment|network_topology|flux_balance)$",
    )
    gene_set: list[str] = Field(default_factory=list)
    pathway_id: str | None = None
    protein_ids: list[str] = Field(default_factory=list)
    edges: list = Field(default_factory=list)
    hub_proteins: list[str] = Field(default_factory=list)
    topology_metrics: dict = Field(default_factory=dict)
    stoichiometry_matrix: list = Field(default_factory=list)
    fluxes: list = Field(default_factory=list)
    flux_bounds: list = Field(default_factory=list)
    objective: list = Field(default_factory=list)


class ImmunoinformaticsPayload(BaseModel):
    """Extra fields for immunoinformatics domain results."""
    claim_type: str = Field(
        "epitope_prediction",
        pattern=r"^(epitope_prediction|mhc_binding|bcell_epitope)$",
    )
    peptide: str | None = None
    source_protein: str | None = None
    hla_allele: str | None = None
    binding_affinity: float | None = None
    mhc_class: str = "I"
    classification: str | None = None
    prediction_score: float | None = None
    surface_accessibility: float | None = None
    sequence: str | None = None


class MetabolomicsPayload(BaseModel):
    """Extra fields for metabolomics domain results."""
    claim_type: str = Field(
        "compound_identification",
        pattern=r"^(compound_identification|pathway_mapping|spectral_match)$",
    )
    hmdb_id: str | None = None
    compound_name: str | None = None
    mz: float | None = None
    formula: str | None = None
    inchikey: str | None = None
    kegg_compound_id: str | None = None
    kegg_pathway_id: str | None = None
    enzymes: list[str] = Field(default_factory=list)
    spectrum_peaks: list = Field(default_factory=list)
    precursor_mz: float | None = None
    adduct: str | None = None
    ppm_tolerance: float = 10.0


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
    "chemistry": ChemistryPayload,
    "physics": PhysicsPayload,
    "genomics": GenomicsPayload,
    "epidemiology": EpidemiologyPayload,
    "systems_biology": SystemsBiologyPayload,
    "immunoinformatics": ImmunoinformaticsPayload,
    "metabolomics": MetabolomicsPayload,
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
