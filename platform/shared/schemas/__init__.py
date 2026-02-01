"""Shared schemas module.

Contains base schemas and domain-specific claim payload schemas.
"""

from platform.shared.schemas.base import (
    BaseSchema,
    TimestampMixin,
    IDMixin,
    PaginationParams,
    PaginatedResponse,
    ErrorDetail,
    SuccessResponse,
    CreatedResponse,
    Domain,
    ClaimType,
    VerificationStatus,
    AgentStatus,
    ChallengeType,
    ChallengeStatus,
    FrontierStatus,
    Difficulty,
    BaseEvent,
    ClaimSubmittedEvent,
    ClaimVerifiedEvent,
    ChallengeCreatedEvent,
    ReputationTransactionEvent,
)

from platform.shared.schemas.claim_payloads import (
    # Mathematics
    MathematicsTheoremPayload,
    MathematicsConjecturePayload,
    # ML/AI
    MLExperimentPayload,
    BenchmarkResultPayload,
    # Computational Biology
    ProteinDesignPayload,
    BinderDesignPayload,
    StructurePredictionPayload,
    # Materials Science
    MaterialPredictionPayload,
    MaterialPropertyPayload,
    # Bioinformatics
    PipelineResultPayload,
    SequenceAnnotationPayload,
    # Registry
    PAYLOAD_SCHEMAS,
    get_payload_schema,
    validate_payload,
    get_supported_claim_types,
    get_all_domains,
)

__all__ = [
    # Base schemas
    "BaseSchema",
    "TimestampMixin",
    "IDMixin",
    "PaginationParams",
    "PaginatedResponse",
    "ErrorDetail",
    "SuccessResponse",
    "CreatedResponse",
    # Enums
    "Domain",
    "ClaimType",
    "VerificationStatus",
    "AgentStatus",
    "ChallengeType",
    "ChallengeStatus",
    "FrontierStatus",
    "Difficulty",
    # Event schemas
    "BaseEvent",
    "ClaimSubmittedEvent",
    "ClaimVerifiedEvent",
    "ChallengeCreatedEvent",
    "ReputationTransactionEvent",
    # Claim payload schemas
    "MathematicsTheoremPayload",
    "MathematicsConjecturePayload",
    "MLExperimentPayload",
    "BenchmarkResultPayload",
    "ProteinDesignPayload",
    "BinderDesignPayload",
    "StructurePredictionPayload",
    "MaterialPredictionPayload",
    "MaterialPropertyPayload",
    "PipelineResultPayload",
    "SequenceAnnotationPayload",
    # Schema registry
    "PAYLOAD_SCHEMAS",
    "get_payload_schema",
    "validate_payload",
    "get_supported_claim_types",
    "get_all_domains",
]
