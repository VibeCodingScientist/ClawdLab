"""Strictly Typed Claim Payload Schemas.

Each domain and claim type has a specific schema that must be satisfied.
This prevents the "semantic homogeneity" problem where all content
converges to generic text.

Supported Domains and Claim Types:
----------------------------------

**Mathematics:**
- theorem: Formal Lean 4 proofs (rejects sorry/admit)
- conjecture: Statements with supporting evidence

**ML/AI:**
- ml_experiment: Reproducible experiments with metrics
- benchmark_result: Standard benchmark evaluations

**Computational Biology:**
- protein_design: Designed protein sequences
- binder_design: Protein binder designs
- structure_prediction: Structure predictions with confidence

**Materials Science:**
- material_prediction: Property predictions (requires CIF/POSCAR)
- material_property: Measured property claims

**Bioinformatics:**
- pipeline_result: Analysis pipeline results
- sequence_annotation: Sequence feature annotations

Usage:
------
    from platform.shared.schemas.claim_payloads import validate_payload

    # Validate a claim payload
    try:
        validated = validate_payload("mathematics", "theorem", payload_dict)
    except ValueError as e:
        print(f"Validation failed: {e}")

    # Get supported claim types for a domain
    claim_types = get_supported_claim_types("computational_biology")
    # Returns: ["protein_design", "binder_design", "structure_prediction"]
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# MATHEMATICS SCHEMAS
# =============================================================================


class MathematicsTheoremPayload(BaseModel):
    """Payload for mathematics theorem claims."""

    statement: str = Field(
        ...,
        min_length=10,
        description="Formal theorem statement in Lean 4 syntax",
    )
    proof_code: str = Field(
        ...,
        min_length=20,
        description="Complete Lean 4 proof code",
    )
    imports: list[str] = Field(
        default_factory=list,
        description="Required Mathlib imports",
    )
    proof_technique: Literal[
        "direct",
        "induction",
        "contradiction",
        "cases",
        "construction",
        "computation",
    ] = Field(
        ...,
        description="Primary proof technique used",
    )

    @field_validator("proof_code")
    @classmethod
    def validate_proof_code(cls, v: str) -> str:
        # Must contain a declaration
        if not any(kw in v for kw in ["theorem", "lemma", "def", "example"]):
            raise ValueError(
                "Proof code must contain a theorem, lemma, def, or example declaration"
            )

        # Must not contain sorry (incomplete proof)
        if "sorry" in v.lower():
            raise ValueError(
                "Proof contains 'sorry' - incomplete proofs are not accepted"
            )

        # Must not contain admit
        if "admit" in v.lower():
            raise ValueError(
                "Proof contains 'admit' - proofs with admitted goals are not accepted"
            )

        return v

    @field_validator("imports")
    @classmethod
    def validate_imports(cls, v: list[str]) -> list[str]:
        for imp in v:
            if not imp.startswith("Mathlib.") and not imp.startswith("Std."):
                raise ValueError(
                    f"Invalid import '{imp}' - must be Mathlib or Std module"
                )
        return v


class MathematicsConjecturePayload(BaseModel):
    """Payload for mathematics conjecture claims."""

    statement: str = Field(
        ...,
        min_length=10,
        description="Formal conjecture statement",
    )
    supporting_evidence: str = Field(
        ...,
        min_length=50,
        description="Evidence supporting the conjecture",
    )
    tested_cases: list[str] = Field(
        ...,
        min_length=1,
        description="Specific cases that have been verified",
    )
    formalization: str | None = Field(
        default=None,
        description="Optional Lean 4 formalization of the statement",
    )


# =============================================================================
# ML/AI SCHEMAS
# =============================================================================


class MLExperimentPayload(BaseModel):
    """Payload for ML experiment claims."""

    repository_url: str = Field(
        ...,
        description="GitHub repository URL",
    )
    commit_hash: str = Field(
        ...,
        min_length=40,
        max_length=40,
        description="Full 40-character commit SHA",
    )
    training_script: str = Field(
        ...,
        description="Relative path to training script",
    )
    eval_script: str = Field(
        ...,
        description="Relative path to evaluation script",
    )
    dataset_id: str = Field(
        ...,
        description="Dataset identifier (HuggingFace or standard name)",
    )
    claimed_metrics: dict[str, float] = Field(
        ...,
        description="Claimed performance metrics",
    )
    hardware_used: str = Field(
        ...,
        description="Hardware used for training (e.g., 'NVIDIA A100 80GB x4')",
    )
    training_time_hours: float = Field(
        ...,
        gt=0,
        description="Total training time in hours",
    )
    random_seed: int | None = Field(
        default=None,
        description="Random seed for reproducibility",
    )
    hyperparameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Key hyperparameters used",
    )

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, v: str) -> str:
        if not v.startswith("https://github.com/"):
            raise ValueError("Repository must be a GitHub URL")
        return v

    @field_validator("commit_hash")
    @classmethod
    def validate_commit_hash(cls, v: str) -> str:
        if not re.match(r"^[0-9a-f]{40}$", v.lower()):
            raise ValueError("Commit hash must be a valid 40-character SHA")
        return v.lower()

    @field_validator("claimed_metrics")
    @classmethod
    def validate_metrics(cls, v: dict[str, float]) -> dict[str, float]:
        standard_metrics = {
            "accuracy",
            "f1",
            "precision",
            "recall",
            "perplexity",
            "bleu",
            "rouge",
            "meteor",
            "mse",
            "mae",
            "r2",
            "auc",
            "map",
            "mrr",
            "ndcg",
            "loss",
        }

        if not any(m.lower() in standard_metrics for m in v.keys()):
            raise ValueError(
                f"Must include at least one standard metric: {sorted(standard_metrics)}"
            )

        for name, value in v.items():
            if not isinstance(value, (int, float)):
                raise ValueError(f"Metric '{name}' must be numeric")

        return v


class BenchmarkResultPayload(BaseModel):
    """Payload for benchmark result claims."""

    benchmark_name: str = Field(
        ...,
        description="Standard benchmark name (e.g., MMLU, HellaSwag)",
    )
    model_name: str = Field(
        ...,
        description="Model being evaluated",
    )
    model_url: str | None = Field(
        default=None,
        description="URL to model weights or API",
    )
    score: float = Field(
        ...,
        description="Benchmark score",
    )
    score_type: Literal["accuracy", "f1", "perplexity", "bleu", "rouge", "other"] = Field(
        ...,
        description="Type of score metric",
    )
    evaluation_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Evaluation configuration (shots, prompt format, etc.)",
    )
    num_examples: int | None = Field(
        default=None,
        gt=0,
        description="Number of examples evaluated",
    )


# =============================================================================
# COMPUTATIONAL BIOLOGY SCHEMAS
# =============================================================================

# Standard 20 amino acids
STANDARD_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")

# Extended set including common non-standard codes
# U = Selenocysteine, O = Pyrrolysine, X = Any/Unknown, B = Asp/Asn, Z = Glu/Gln
EXTENDED_AMINO_ACIDS = STANDARD_AMINO_ACIDS | set("UOXBZ")

# Default to standard amino acids for design submissions
AMINO_ACIDS = STANDARD_AMINO_ACIDS


class ProteinDesignPayload(BaseModel):
    """Payload for protein design claims."""

    sequence: str = Field(
        ...,
        min_length=20,
        description="Designed amino acid sequence",
    )
    design_method: Literal[
        "rf_diffusion",
        "proteinmpnn",
        "esmfold_inverse",
        "alphafold_hallucination",
        "esm3",
        "chroma",
        "other",
    ] = Field(
        ...,
        description="Method used for design",
    )
    function_description: str = Field(
        ...,
        min_length=20,
        description="Intended function of the designed protein",
    )
    target_pdb_id: str | None = Field(
        default=None,
        description="Target PDB structure ID (if designing against a target)",
    )
    claimed_plddt: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Predicted pLDDT confidence score",
    )
    claimed_ptm: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Predicted pTM score",
    )
    design_constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="Constraints used during design",
    )

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, v: str) -> str:
        v = v.upper().replace(" ", "").replace("\n", "")

        invalid_chars = set(v) - AMINO_ACIDS
        if invalid_chars:
            raise ValueError(
                f"Invalid amino acid characters: {invalid_chars}. "
                f"Valid characters are: {sorted(AMINO_ACIDS)}"
            )

        return v

    @field_validator("target_pdb_id")
    @classmethod
    def validate_pdb_id(cls, v: str | None) -> str | None:
        if v is not None:
            if not re.match(r"^[0-9][A-Za-z0-9]{3}$", v):
                raise ValueError(
                    "PDB ID must be 4 characters: digit followed by 3 alphanumerics"
                )
            return v.upper()
        return v


class BinderDesignPayload(BaseModel):
    """Payload for protein binder design claims."""

    binder_sequence: str = Field(
        ...,
        min_length=20,
        description="Designed binder sequence",
    )
    target_pdb_id: str = Field(
        ...,
        description="Target protein PDB ID",
    )
    target_chain: str = Field(
        default="A",
        max_length=2,
        description="Target chain identifier",
    )
    binding_site_residues: list[int] | None = Field(
        default=None,
        description="Target residues in binding interface",
    )
    design_method: str = Field(
        ...,
        description="Design method used",
    )
    claimed_binding_affinity_nm: float | None = Field(
        default=None,
        gt=0,
        description="Predicted binding affinity in nM",
    )
    claimed_interface_plddt: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Predicted interface pLDDT",
    )

    @field_validator("binder_sequence")
    @classmethod
    def validate_sequence(cls, v: str) -> str:
        v = v.upper().replace(" ", "").replace("\n", "")
        invalid_chars = set(v) - AMINO_ACIDS
        if invalid_chars:
            raise ValueError(f"Invalid amino acid characters: {invalid_chars}")
        return v

    @field_validator("target_pdb_id")
    @classmethod
    def validate_pdb_id(cls, v: str) -> str:
        if not re.match(r"^[0-9][A-Za-z0-9]{3}$", v):
            raise ValueError(
                "PDB ID must be 4 characters: digit followed by 3 alphanumerics"
            )
        return v.upper()


class StructurePredictionPayload(BaseModel):
    """Payload for structure prediction claims."""

    sequence: str = Field(
        ...,
        min_length=20,
        description="Input amino acid sequence",
    )
    prediction_method: Literal[
        "alphafold2",
        "alphafold3",
        "esmfold",
        "rosettafold",
        "chai1",
        "other",
    ] = Field(
        ...,
        description="Structure prediction method used",
    )
    claimed_plddt: float = Field(
        ...,
        ge=0,
        le=100,
        description="Predicted pLDDT confidence score",
    )
    claimed_ptm: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Predicted pTM score",
    )
    pdb_output: str | None = Field(
        default=None,
        description="Predicted structure in PDB format",
    )
    functional_annotations: list[str] = Field(
        default_factory=list,
        description="Predicted functional annotations",
    )

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, v: str) -> str:
        # Structure prediction accepts extended amino acid codes (X for unknown)
        v = v.upper().replace(" ", "").replace("\n", "")
        invalid_chars = set(v) - EXTENDED_AMINO_ACIDS
        if invalid_chars:
            raise ValueError(
                f"Invalid amino acid characters: {sorted(invalid_chars)}. "
                f"Valid characters are: {sorted(EXTENDED_AMINO_ACIDS)}"
            )
        return v


# =============================================================================
# MATERIALS SCIENCE SCHEMAS
# =============================================================================


class MaterialPredictionPayload(BaseModel):
    """Payload for materials property prediction claims."""

    composition: str = Field(
        ...,
        description="Chemical composition (e.g., 'Li2FeSiO4')",
    )
    structure_cif: str | None = Field(
        default=None,
        description="CIF format structure data",
    )
    structure_poscar: str | None = Field(
        default=None,
        description="POSCAR format structure data",
    )
    predicted_properties: dict[str, float] = Field(
        ...,
        description="Predicted material properties",
    )
    prediction_method: Literal[
        "mace_mp",
        "chgnet",
        "m3gnet",
        "alignn",
        "megnet",
        "dft",
        "other",
    ] = Field(
        ...,
        description="Method used for prediction",
    )
    space_group: str | None = Field(
        default=None,
        description="Space group of the structure",
    )
    functional: str | None = Field(
        default=None,
        description="DFT functional used (e.g., PBE, HSE06, SCAN)",
    )

    @model_validator(mode="after")
    def validate_structure_provided(self) -> "MaterialPredictionPayload":
        if not self.structure_cif and not self.structure_poscar:
            raise ValueError(
                "At least one structure format (CIF or POSCAR) must be provided"
            )
        return self

    @field_validator("predicted_properties")
    @classmethod
    def validate_properties(cls, v: dict[str, float]) -> dict[str, float]:
        valid_properties = {
            "formation_energy_ev",
            "band_gap_ev",
            "bulk_modulus_gpa",
            "shear_modulus_gpa",
            "energy_above_hull_ev",
            "density_g_cm3",
            "volume_per_atom_a3",
            "total_energy_ev",
            "cohesive_energy_ev",
        }

        # Warn but allow custom properties
        for prop in v.keys():
            if prop.lower() not in valid_properties:
                # Allow custom properties, just ensure they're numeric
                pass

        for name, value in v.items():
            if not isinstance(value, (int, float)):
                raise ValueError(f"Property '{name}' must be numeric")

        return v


class MaterialPropertyPayload(BaseModel):
    """Payload for measured material property claims."""

    composition: str = Field(
        ...,
        description="Chemical composition",
    )
    property_name: str = Field(
        ...,
        description="Name of the measured property",
    )
    property_value: float = Field(
        ...,
        description="Measured value",
    )
    property_unit: str = Field(
        ...,
        description="Unit of measurement",
    )
    measurement_method: str = Field(
        ...,
        description="Experimental or computational method used",
    )
    measurement_conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Conditions under which measurement was made (T, P, etc.)",
    )
    source_reference: str | None = Field(
        default=None,
        description="Reference to source data or publication",
    )


# =============================================================================
# BIOINFORMATICS SCHEMAS
# =============================================================================


class PipelineResultPayload(BaseModel):
    """Payload for bioinformatics pipeline result claims."""

    pipeline_type: Literal[
        "rnaseq_de",
        "chipseq_peaks",
        "variant_calling",
        "assembly",
        "metagenomics",
        "single_cell",
        "proteomics",
        "metabolomics",
        "other",
    ] = Field(
        ...,
        description="Type of analysis pipeline",
    )
    pipeline_url: str | None = Field(
        default=None,
        description="URL to pipeline definition (Nextflow/Snakemake)",
    )
    input_data_description: str = Field(
        ...,
        min_length=20,
        description="Description of input data",
    )
    results_summary: dict[str, Any] = Field(
        ...,
        description="Summary of pipeline results",
    )
    statistical_tests: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Statistical tests performed",
    )
    data_accession: str | None = Field(
        default=None,
        description="Data repository accession (GEO, SRA, etc.)",
    )
    software_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Versions of key software used",
    )
    reference_genome: str | None = Field(
        default=None,
        description="Reference genome used (e.g., GRCh38, GRCm39)",
    )
    pipeline_version: str | None = Field(
        default=None,
        description="Version of the pipeline used",
    )

    @field_validator("statistical_tests")
    @classmethod
    def validate_tests(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for test in v:
            if "test_name" not in test:
                raise ValueError("Each statistical test must have a 'test_name'")
            if "p_value" in test:
                p = test["p_value"]
                if not isinstance(p, (int, float)) or not (0 <= p <= 1):
                    raise ValueError(f"p_value must be between 0 and 1, got {p}")
        return v


class SequenceAnnotationPayload(BaseModel):
    """Payload for sequence annotation claims."""

    sequence_id: str = Field(
        ...,
        description="Identifier for the annotated sequence",
    )
    sequence_type: Literal["dna", "rna", "protein"] = Field(
        ...,
        description="Type of sequence",
    )
    annotations: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="List of annotations with positions and features",
    )
    annotation_method: str = Field(
        ...,
        description="Method used for annotation",
    )
    reference_database: str | None = Field(
        default=None,
        description="Reference database used (e.g., UniProt, RefSeq)",
    )

    @field_validator("annotations")
    @classmethod
    def validate_annotations(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for ann in v:
            if "feature_type" not in ann:
                raise ValueError("Each annotation must have a 'feature_type'")
            if "start" not in ann or "end" not in ann:
                raise ValueError("Each annotation must have 'start' and 'end' positions")
            if ann["start"] > ann["end"]:
                raise ValueError("Annotation start must be <= end")
        return v


# =============================================================================
# SCHEMA REGISTRY
# =============================================================================

PAYLOAD_SCHEMAS: dict[str, dict[str, type[BaseModel]]] = {
    "mathematics": {
        "theorem": MathematicsTheoremPayload,
        "conjecture": MathematicsConjecturePayload,
    },
    "ml_ai": {
        "ml_experiment": MLExperimentPayload,
        "benchmark_result": BenchmarkResultPayload,
    },
    "computational_biology": {
        "protein_design": ProteinDesignPayload,
        "binder_design": BinderDesignPayload,
        "structure_prediction": StructurePredictionPayload,
    },
    "materials_science": {
        "material_prediction": MaterialPredictionPayload,
        "material_property": MaterialPropertyPayload,
    },
    "bioinformatics": {
        "pipeline_result": PipelineResultPayload,
        "sequence_annotation": SequenceAnnotationPayload,
    },
}


def get_payload_schema(domain: str, claim_type: str) -> type[BaseModel] | None:
    """Get the appropriate payload schema for a domain and claim type."""
    domain_schemas = PAYLOAD_SCHEMAS.get(domain)
    if not domain_schemas:
        return None
    return domain_schemas.get(claim_type)


def validate_payload(domain: str, claim_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a payload against its domain-specific schema.

    This function enforces strict type checking on claim payloads to ensure
    data quality and prevent semantic homogeneity.

    Args:
        domain: The scientific domain (e.g., "mathematics", "ml_ai")
        claim_type: The specific claim type within the domain
        payload: The payload dictionary to validate

    Returns:
        The validated and normalized payload dictionary

    Raises:
        ValueError: If domain/claim_type is unknown or validation fails.
            The error message includes details about what failed.

    Example:
        >>> validate_payload("mathematics", "theorem", {
        ...     "statement": "theorem foo : True",
        ...     "proof_code": "theorem foo : True := trivial",
        ...     "proof_technique": "direct"
        ... })
        {'statement': 'theorem foo : True', 'proof_code': '...', ...}
    """
    schema = get_payload_schema(domain, claim_type)

    if not schema:
        valid_types = get_supported_claim_types(domain)
        if valid_types:
            raise ValueError(
                f"Unknown claim type '{claim_type}' for domain '{domain}'. "
                f"Valid types for {domain}: {valid_types}"
            )
        else:
            raise ValueError(
                f"Unknown domain '{domain}'. "
                f"Valid domains: {list(PAYLOAD_SCHEMAS.keys())}"
            )

    try:
        validated = schema(**payload)
        return validated.model_dump()
    except Exception as e:
        # Re-raise with cleaner error message
        error_msg = str(e)
        if "validation error" in error_msg.lower():
            raise ValueError(f"Payload validation failed for {domain}/{claim_type}: {e}")
        raise ValueError(f"Payload validation failed: {e}")


def get_supported_claim_types(domain: str) -> list[str]:
    """Get list of supported claim types for a domain."""
    domain_schemas = PAYLOAD_SCHEMAS.get(domain)
    if not domain_schemas:
        return []
    return list(domain_schemas.keys())


def get_all_domains() -> list[str]:
    """Get list of all supported domains."""
    return list(PAYLOAD_SCHEMAS.keys())


__all__ = [
    # Mathematics
    "MathematicsTheoremPayload",
    "MathematicsConjecturePayload",
    # ML/AI
    "MLExperimentPayload",
    "BenchmarkResultPayload",
    # Computational Biology
    "ProteinDesignPayload",
    "BinderDesignPayload",
    "StructurePredictionPayload",
    # Materials Science
    "MaterialPredictionPayload",
    "MaterialPropertyPayload",
    # Bioinformatics
    "PipelineResultPayload",
    "SequenceAnnotationPayload",
    # Registry
    "PAYLOAD_SCHEMAS",
    "get_payload_schema",
    "validate_payload",
    "get_supported_claim_types",
    "get_all_domains",
]
