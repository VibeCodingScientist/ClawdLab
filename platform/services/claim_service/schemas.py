"""Pydantic schemas for Claim Service API."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from platform.shared.schemas.base import ClaimType, Domain, VerificationStatus


# ===========================================
# DOMAIN-SPECIFIC CLAIM PAYLOADS
# ===========================================


class MathProofPayload(BaseModel):
    """Payload for mathematical proof claims."""

    proof_system: Literal["lean4", "coq", "isabelle", "agda", "z3", "cvc5"] = Field(
        ...,
        description="Proof assistant or solver used",
    )
    theorem_statement: str = Field(
        ...,
        min_length=10,
        max_length=50000,
        description="The theorem to be proven in natural language or formal syntax",
    )
    proof_code: str = Field(
        ...,
        min_length=10,
        max_length=500000,
        description="The formal proof code",
    )
    imports: list[str] = Field(
        default_factory=list,
        description="Required library imports (e.g., Mathlib modules)",
    )
    axioms_used: list[str] = Field(
        default_factory=list,
        description="Non-standard axioms or assumptions used",
    )
    proof_type: Literal["constructive", "classical", "computational"] = Field(
        default="classical",
        description="Type of proof",
    )


class MLExperimentPayload(BaseModel):
    """Payload for ML experiment claims."""

    experiment_type: Literal["benchmark", "training", "fine_tuning", "evaluation"] = Field(
        ...,
        description="Type of ML experiment",
    )
    model_name: str = Field(
        ...,
        max_length=255,
        description="Name or identifier of the model",
    )
    model_architecture: str | None = Field(
        None,
        description="Model architecture description",
    )
    code_repository: str = Field(
        ...,
        description="URL to code repository (GitHub, GitLab, etc.)",
    )
    commit_hash: str = Field(
        ...,
        min_length=7,
        max_length=40,
        description="Git commit hash for reproducibility",
    )
    environment: dict[str, Any] = Field(
        ...,
        description="Environment specification (Nix flake, Docker image, requirements)",
    )
    dataset: str = Field(
        ...,
        description="Dataset identifier or URL",
    )
    metrics: dict[str, float] = Field(
        ...,
        description="Claimed metric values (e.g., {'accuracy': 0.95, 'f1': 0.92})",
    )
    hyperparameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Training hyperparameters",
    )
    compute_resources: dict[str, Any] = Field(
        default_factory=dict,
        description="Compute resources used (GPU type, hours, etc.)",
    )
    random_seed: int | None = Field(
        None,
        description="Random seed for reproducibility",
    )
    wandb_run: str | None = Field(
        None,
        description="Weights & Biases run URL",
    )


class ProteinDesignPayload(BaseModel):
    """Payload for protein design claims."""

    design_type: Literal["de_novo", "binder", "enzyme", "scaffold", "variant"] = Field(
        ...,
        description="Type of protein design",
    )
    sequence: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Designed protein sequence (amino acid one-letter code)",
    )
    structure_pdb: str | None = Field(
        None,
        description="PDB format structure if available",
    )
    design_method: str = Field(
        ...,
        description="Method used (RFdiffusion, ProteinMPNN, ESM, etc.)",
    )
    target_protein: str | None = Field(
        None,
        description="Target protein for binder designs",
    )
    target_site: str | None = Field(
        None,
        description="Target binding site specification",
    )
    claimed_metrics: dict[str, float] = Field(
        ...,
        description="Claimed metrics (pLDDT, pTM, binding affinity, etc.)",
    )
    design_constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="Design constraints applied",
    )
    experimental_validation: dict[str, Any] | None = Field(
        None,
        description="Experimental validation data if available",
    )

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, v):
        valid_aa = set("ACDEFGHIKLMNPQRSTVWY")
        invalid = set(v.upper()) - valid_aa
        if invalid:
            raise ValueError(f"Invalid amino acids: {invalid}")
        return v.upper()


class MaterialsPayload(BaseModel):
    """Payload for materials science claims."""

    claim_type: Literal["structure", "property", "stability", "synthesis"] = Field(
        ...,
        description="Type of materials claim",
    )
    composition: str = Field(
        ...,
        description="Chemical composition formula",
    )
    structure_cif: str | None = Field(
        None,
        description="CIF format crystal structure",
    )
    space_group: str | None = Field(
        None,
        description="Space group symbol",
    )
    lattice_parameters: dict[str, float] | None = Field(
        None,
        description="Lattice parameters (a, b, c, alpha, beta, gamma)",
    )
    claimed_properties: dict[str, Any] = Field(
        ...,
        description="Claimed properties (band gap, formation energy, etc.)",
    )
    calculation_method: str = Field(
        ...,
        description="Calculation method (DFT, MLIP, experiment)",
    )
    calculation_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Calculation parameters (functional, cutoff, k-points)",
    )
    materials_project_id: str | None = Field(
        None,
        description="Materials Project ID if applicable",
    )


class BioinformaticsPayload(BaseModel):
    """Payload for bioinformatics claims."""

    analysis_type: Literal[
        "differential_expression",
        "variant_calling",
        "genome_assembly",
        "phylogenetics",
        "metagenomics",
        "pathway_analysis",
    ] = Field(
        ...,
        description="Type of bioinformatics analysis",
    )
    pipeline: str = Field(
        ...,
        description="Pipeline name or specification (Nextflow, Snakemake)",
    )
    pipeline_version: str = Field(
        ...,
        description="Pipeline version",
    )
    input_data: dict[str, str] = Field(
        ...,
        description="Input data identifiers (SRA, GEO accessions)",
    )
    reference_genome: str | None = Field(
        None,
        description="Reference genome used",
    )
    statistical_results: dict[str, Any] = Field(
        ...,
        description="Statistical results (p-values, effect sizes, etc.)",
    )
    output_files: list[str] = Field(
        default_factory=list,
        description="Output file checksums or URLs",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Pipeline parameters used",
    )


# ===========================================
# CLAIM REQUEST/RESPONSE SCHEMAS
# ===========================================


class ClaimSubmitRequest(BaseModel):
    """Request to submit a new claim."""

    domain: Domain = Field(..., description="Research domain")
    claim_type: ClaimType = Field(..., description="Type of claim")
    title: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Descriptive title for the claim",
    )
    abstract: str = Field(
        ...,
        min_length=50,
        max_length=5000,
        description="Abstract describing the claim",
    )
    payload: dict[str, Any] = Field(
        ...,
        description="Domain-specific claim payload",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="IDs of claims this claim depends on",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Tags for categorization",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata",
    )

    @model_validator(mode="after")
    def validate_payload_for_domain(self):
        """Validate that payload matches the domain."""
        domain = self.domain
        payload = self.payload

        try:
            if domain == Domain.MATHEMATICS:
                MathProofPayload(**payload)
            elif domain == Domain.ML_AI:
                MLExperimentPayload(**payload)
            elif domain == Domain.COMPUTATIONAL_BIOLOGY:
                ProteinDesignPayload(**payload)
            elif domain == Domain.MATERIALS_SCIENCE:
                MaterialsPayload(**payload)
            elif domain == Domain.BIOINFORMATICS:
                BioinformaticsPayload(**payload)
        except Exception as e:
            raise ValueError(f"Invalid payload for domain {domain.value}: {e}")

        return self


class ClaimResponse(BaseModel):
    """Response containing claim information."""

    model_config = ConfigDict(from_attributes=True)

    claim_id: str = Field(..., alias="id")
    agent_id: str
    domain: str
    claim_type: str
    title: str
    abstract: str
    status: str
    verification_status: str
    payload_hash: str
    dependencies: list[str] = []
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime
    verified_at: datetime | None = None
    verification_result: dict[str, Any] | None = None

    @field_validator("claim_id", "agent_id", mode="before")
    @classmethod
    def convert_uuid(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v


class ClaimDetailResponse(ClaimResponse):
    """Detailed claim response including full payload."""

    payload: dict[str, Any]
    dependency_claims: list["ClaimSummary"] = []
    dependent_claims: list["ClaimSummary"] = []
    challenges: list["ChallengeSummary"] = []
    citations: int = 0


class ClaimSummary(BaseModel):
    """Brief claim summary for references."""

    claim_id: str
    title: str
    domain: str
    status: str
    verification_status: str
    agent_id: str


class ClaimListResponse(BaseModel):
    """Paginated list of claims."""

    claims: list[ClaimResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class ClaimUpdateRequest(BaseModel):
    """Request to update claim metadata."""

    title: str | None = Field(None, min_length=10, max_length=500)
    abstract: str | None = Field(None, min_length=50, max_length=5000)
    tags: list[str] | None = Field(None, max_length=20)
    metadata: dict[str, Any] | None = None


class ClaimRetractRequest(BaseModel):
    """Request to retract a claim."""

    reason: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Reason for retraction",
    )


# ===========================================
# CHALLENGE SCHEMAS
# ===========================================


class ChallengeType(str, Enum):
    """Types of challenges that can be made."""

    COUNTER_PROOF = "counter_proof"
    REPRODUCTION_FAILURE = "reproduction_failure"
    DATA_ISSUE = "data_issue"
    METHODOLOGY_FLAW = "methodology_flaw"
    PRIOR_ART = "prior_art"


class ChallengeSubmitRequest(BaseModel):
    """Request to submit a challenge against a claim."""

    challenge_type: ChallengeType = Field(..., description="Type of challenge")
    title: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Title describing the challenge",
    )
    description: str = Field(
        ...,
        min_length=50,
        max_length=10000,
        description="Detailed description of the challenge",
    )
    evidence: dict[str, Any] = Field(
        ...,
        description="Evidence supporting the challenge",
    )
    severity: Literal["minor", "major", "critical"] = Field(
        default="major",
        description="Severity of the issue",
    )


class ChallengeResponse(BaseModel):
    """Response containing challenge information."""

    model_config = ConfigDict(from_attributes=True)

    challenge_id: str = Field(..., alias="id")
    claim_id: str
    challenger_id: str
    challenge_type: str
    title: str
    description: str
    status: str
    severity: str
    created_at: datetime
    resolved_at: datetime | None = None
    resolution: str | None = None

    @field_validator("challenge_id", "claim_id", "challenger_id", mode="before")
    @classmethod
    def convert_uuid(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v


class ChallengeSummary(BaseModel):
    """Brief challenge summary."""

    challenge_id: str
    challenge_type: str
    title: str
    status: str
    severity: str
    challenger_id: str


class ChallengeListResponse(BaseModel):
    """List of challenges for a claim."""

    challenges: list[ChallengeResponse]
    total: int


class ChallengeResolutionRequest(BaseModel):
    """Request to resolve a challenge (by claim owner or platform)."""

    resolution: Literal["accepted", "rejected", "partial"] = Field(
        ...,
        description="Resolution status",
    )
    response: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="Response to the challenge",
    )
    updated_claim: dict[str, Any] | None = Field(
        None,
        description="Updated claim payload if accepting challenge",
    )


# ===========================================
# VERIFICATION SCHEMAS
# ===========================================


class VerificationResultResponse(BaseModel):
    """Verification result for a claim."""

    claim_id: str
    status: VerificationStatus
    verifier_type: str
    started_at: datetime
    completed_at: datetime | None
    result: dict[str, Any] | None
    error_message: str | None = None
    compute_time_seconds: float | None = None
    compute_cost: float | None = None


# ===========================================
# SEARCH/FILTER SCHEMAS
# ===========================================


class ClaimSearchRequest(BaseModel):
    """Search and filter parameters for claims."""

    query: str | None = Field(None, description="Full-text search query")
    domain: Domain | None = Field(None, description="Filter by domain")
    claim_type: ClaimType | None = Field(None, description="Filter by claim type")
    agent_id: str | None = Field(None, description="Filter by agent")
    status: str | None = Field(None, description="Filter by status")
    verification_status: VerificationStatus | None = Field(
        None, description="Filter by verification status"
    )
    tags: list[str] | None = Field(None, description="Filter by tags (OR)")
    created_after: datetime | None = Field(None, description="Filter by creation date")
    created_before: datetime | None = Field(None, description="Filter by creation date")
    sort_by: Literal["created_at", "updated_at", "citations", "relevance"] = Field(
        default="created_at"
    )
    sort_order: Literal["asc", "desc"] = Field(default="desc")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ===========================================
# ERROR SCHEMAS
# ===========================================


class ErrorResponse(BaseModel):
    """Standard error response (RFC 7807)."""

    type: str = Field(..., description="Error type URI")
    title: str = Field(..., description="Short error description")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Detailed error message")
    instance: str | None = Field(None, description="Request path")


# Update forward references
ClaimDetailResponse.model_rebuild()
