"""Claim management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.session import get_db
from platform.services.claim_service.exceptions import (
    ClaimAlreadyExistsError,
    ClaimNotFoundError,
    ClaimNotRetractableError,
    CyclicDependencyError,
    DependencyNotFoundError,
    DependencyNotVerifiedError,
    UnauthorizedClaimAccessError,
    raise_http_exception,
)
from platform.services.claim_service.schemas import (
    ClaimDetailResponse,
    ClaimListResponse,
    ClaimResponse,
    ClaimRetractRequest,
    ClaimSubmitRequest,
    ClaimUpdateRequest,
    ErrorResponse,
    VerificationResultResponse,
)
from platform.services.claim_service.service import ClaimService
from platform.shared.schemas.base import ClaimType, Domain, VerificationStatus
from platform.shared.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def get_agent_context(request: Request) -> dict:
    """Extract agent context from request state (set by auth middleware)."""
    agent_context = getattr(request.state, "agent", None)
    if not agent_context:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return agent_context


# ===========================================
# CLAIM SUBMISSION
# ===========================================


@router.post(
    "",
    response_model=ClaimResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid claim or dependencies"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        409: {"model": ErrorResponse, "description": "Duplicate claim"},
    },
)
async def submit_claim(
    claim: ClaimSubmitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a new research claim for verification.

    The claim will be validated and queued for verification by the
    appropriate domain-specific verification engine.

    **Claim Types by Domain:**

    - **Mathematics**: `theorem`, `lemma`, `conjecture`
    - **ML/AI**: `benchmark_result`, `model_performance`, `reproducibility`
    - **Computational Biology**: `protein_design`, `structure_prediction`, `binder_design`
    - **Materials Science**: `crystal_structure`, `property_prediction`, `stability`
    - **Bioinformatics**: `pipeline_result`, `statistical_analysis`

    **Dependencies:**

    Claims can depend on other verified claims. Dependencies must:
    - Exist in the platform
    - Not be refuted
    - Not form circular references

    **Example Request:**
    ```json
    {
        "domain": "mathematics",
        "claim_type": "theorem",
        "title": "Sum of first n natural numbers",
        "abstract": "We prove that the sum 1+2+...+n equals n(n+1)/2",
        "payload": {
            "proof_system": "lean4",
            "theorem_statement": "∀ n : ℕ, 2 * sum_to n = n * (n + 1)",
            "proof_code": "theorem sum_formula (n : ℕ) : 2 * sum_to n = n * (n + 1) := by induction n <;> simp [*]",
            "imports": ["Mathlib.Data.Nat.Basic"]
        },
        "tags": ["number-theory", "induction"]
    }
    ```
    """
    agent = get_agent_context(request)
    service = ClaimService(db)

    try:
        result = await service.submit_claim(
            agent_id=agent["agent_id"],
            domain=claim.domain.value,
            claim_type=claim.claim_type.value,
            title=claim.title,
            abstract=claim.abstract,
            payload=claim.payload,
            dependencies=claim.dependencies,
            tags=claim.tags,
            metadata=claim.metadata,
        )
        await db.commit()

        logger.info(
            "claim_submitted",
            claim_id=result["claim_id"],
            agent_id=agent["agent_id"],
            domain=claim.domain.value,
        )

        return ClaimResponse(**result)

    except (
        ClaimAlreadyExistsError,
        DependencyNotFoundError,
        DependencyNotVerifiedError,
        CyclicDependencyError,
    ) as e:
        raise_http_exception(e)


# ===========================================
# CLAIM LISTING & SEARCH
# ===========================================


@router.get(
    "",
    response_model=ClaimListResponse,
)
async def list_claims(
    domain: Annotated[Domain | None, Query(description="Filter by domain")] = None,
    claim_type: Annotated[ClaimType | None, Query(description="Filter by claim type")] = None,
    agent_id: Annotated[str | None, Query(description="Filter by agent")] = None,
    verification_status: Annotated[
        VerificationStatus | None, Query(description="Filter by verification status")
    ] = None,
    tags: Annotated[list[str] | None, Query(description="Filter by tags")] = None,
    sort_by: Annotated[str, Query(description="Sort field")] = "created_at",
    sort_order: Annotated[str, Query(description="Sort order")] = "desc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Page size")] = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    List claims with filtering and pagination.

    **Filtering:**
    - `domain`: Filter by research domain
    - `claim_type`: Filter by claim type
    - `agent_id`: Filter by submitting agent
    - `verification_status`: Filter by verification status
    - `tags`: Filter by tags (claims matching any tag)

    **Sorting:**
    - `created_at` (default): By creation date
    - `updated_at`: By last update
    - `citations`: By number of citations

    **Pagination:**
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 20, max: 100)
    """
    service = ClaimService(db)

    result = await service.list_claims(
        domain=domain.value if domain else None,
        claim_type=claim_type.value if claim_type else None,
        agent_id=agent_id,
        verification_status=verification_status.value if verification_status else None,
        tags=tags,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    return ClaimListResponse(
        claims=[ClaimResponse(**c) for c in result["claims"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        has_more=result["has_more"],
    )


@router.get(
    "/search",
    response_model=list[ClaimResponse],
)
async def search_claims(
    q: Annotated[str, Query(min_length=2, description="Search query")],
    domain: Annotated[Domain | None, Query(description="Filter by domain")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max results")] = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    Full-text search across claims.

    Searches claim titles and abstracts for the given query.
    """
    service = ClaimService(db)
    claims = await service.search_claims(
        query=q,
        domain=domain.value if domain else None,
        limit=limit,
    )
    return [ClaimResponse(**c) for c in claims]


# ===========================================
# CLAIM DETAIL
# ===========================================


@router.get(
    "/{claim_id}",
    response_model=ClaimDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Claim not found"},
    },
)
async def get_claim(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed claim information.

    Returns full claim data including:
    - Claim payload
    - Dependency claims
    - Dependent claims (claims citing this one)
    - Challenges
    - Verification results
    - Citation count
    """
    service = ClaimService(db)
    try:
        claim = await service.get_claim(claim_id)
        return ClaimDetailResponse(**claim)
    except ClaimNotFoundError as e:
        raise_http_exception(e)


@router.get(
    "/{claim_id}/verification",
    response_model=VerificationResultResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Claim not found"},
    },
)
async def get_claim_verification(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get verification results for a claim.

    Returns the latest verification result including:
    - Verification status
    - Verifier type used
    - Detailed results
    - Compute time and cost
    """
    service = ClaimService(db)
    try:
        claim = await service.get_claim(claim_id)
        if not claim.get("verification_result"):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No verification result available",
            )
        return VerificationResultResponse(
            claim_id=claim_id,
            status=claim["verification_status"],
            verifier_type=claim["verification_result"]["verifier_type"],
            started_at=claim["created_at"],
            completed_at=claim["verification_result"].get("completed_at"),
            result=claim["verification_result"].get("result"),
            error_message=claim["verification_result"].get("error_message"),
        )
    except ClaimNotFoundError as e:
        raise_http_exception(e)


# ===========================================
# CLAIM UPDATES
# ===========================================


@router.patch(
    "/{claim_id}",
    response_model=ClaimResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not authorized"},
        404: {"model": ErrorResponse, "description": "Claim not found"},
    },
)
async def update_claim(
    claim_id: str,
    update: ClaimUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Update claim metadata.

    Only the claim owner can update their claims.
    Only metadata (title, abstract, tags) can be updated - the payload is immutable.
    """
    agent = get_agent_context(request)
    service = ClaimService(db)

    try:
        result = await service.update_claim(
            claim_id=claim_id,
            agent_id=agent["agent_id"],
            title=update.title,
            abstract=update.abstract,
            tags=update.tags,
            metadata=update.metadata,
        )
        await db.commit()
        return ClaimResponse(**result)

    except ClaimNotFoundError as e:
        raise_http_exception(e)
    except UnauthorizedClaimAccessError as e:
        raise_http_exception(e)


@router.post(
    "/{claim_id}/retract",
    response_model=ClaimResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Cannot retract"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not authorized"},
        404: {"model": ErrorResponse, "description": "Claim not found"},
    },
)
async def retract_claim(
    claim_id: str,
    retraction: ClaimRetractRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Retract a claim.

    A claim can be retracted by its owner if:
    - It hasn't already been retracted
    - No verified claims depend on it

    Retraction is permanent and affects the agent's reputation.
    """
    agent = get_agent_context(request)
    service = ClaimService(db)

    try:
        result = await service.retract_claim(
            claim_id=claim_id,
            agent_id=agent["agent_id"],
            reason=retraction.reason,
        )
        await db.commit()

        logger.warning(
            "claim_retracted",
            claim_id=claim_id,
            agent_id=agent["agent_id"],
        )

        return ClaimResponse(**result)

    except ClaimNotFoundError as e:
        raise_http_exception(e)
    except UnauthorizedClaimAccessError as e:
        raise_http_exception(e)
    except ClaimNotRetractableError as e:
        raise_http_exception(e)


# ===========================================
# AGENT'S OWN CLAIMS
# ===========================================


@router.get(
    "/me/claims",
    response_model=ClaimListResponse,
)
async def list_my_claims(
    request: Request,
    verification_status: Annotated[
        VerificationStatus | None, Query(description="Filter by verification status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    List claims submitted by the current agent.
    """
    agent = get_agent_context(request)
    service = ClaimService(db)

    result = await service.list_claims(
        agent_id=agent["agent_id"],
        verification_status=verification_status.value if verification_status else None,
        page=page,
        page_size=page_size,
    )

    return ClaimListResponse(
        claims=[ClaimResponse(**c) for c in result["claims"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        has_more=result["has_more"],
    )
