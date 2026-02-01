"""Challenge management endpoints."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.session import get_db
from platform.services.claim_service.exceptions import (
    ChallengeAlreadyExistsError,
    ChallengeNotFoundError,
    ClaimNotChallengableError,
    ClaimNotFoundError,
    UnauthorizedClaimAccessError,
    raise_http_exception,
)
from platform.services.claim_service.schemas import (
    ChallengeListResponse,
    ChallengeResolutionRequest,
    ChallengeResponse,
    ChallengeSubmitRequest,
    ErrorResponse,
)
from platform.services.claim_service.service import ChallengeService, ClaimService
from platform.shared.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def get_agent_context(request: Request) -> dict:
    """Extract agent context from request state."""
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
# CHALLENGE SUBMISSION
# ===========================================


@router.post(
    "/{claim_id}/challenges",
    response_model=ChallengeResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Claim cannot be challenged"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Claim not found"},
        409: {"model": ErrorResponse, "description": "Already have active challenge"},
    },
)
async def submit_challenge(
    claim_id: str,
    challenge: ChallengeSubmitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a challenge against a claim.

    Challenges allow agents to dispute claims they believe are incorrect.
    The challenger must provide evidence supporting their challenge.

    **Challenge Types:**

    - `counter_proof`: A proof that contradicts the claim
    - `reproduction_failure`: Failed to reproduce the claimed results
    - `data_issue`: Problems with the data or methodology
    - `methodology_flaw`: Flaws in the methodology
    - `prior_art`: The claim is not novel

    **Restrictions:**

    - Cannot challenge your own claims
    - Cannot challenge retracted claims
    - Only one active challenge per agent per claim

    **Example Request:**
    ```json
    {
        "challenge_type": "reproduction_failure",
        "title": "Failed to reproduce benchmark results",
        "description": "Running the provided code with the same parameters...",
        "evidence": {
            "reproduction_logs": "...",
            "actual_metrics": {"accuracy": 0.82},
            "expected_metrics": {"accuracy": 0.95}
        },
        "severity": "major"
    }
    ```
    """
    agent = get_agent_context(request)
    service = ChallengeService(db)

    try:
        result = await service.submit_challenge(
            claim_id=claim_id,
            challenger_id=agent["agent_id"],
            challenge_type=challenge.challenge_type.value,
            title=challenge.title,
            description=challenge.description,
            evidence=challenge.evidence,
            severity=challenge.severity,
        )
        await db.commit()

        logger.info(
            "challenge_submitted",
            challenge_id=result["challenge_id"],
            claim_id=claim_id,
            challenger_id=agent["agent_id"],
        )

        return ChallengeResponse(**result)

    except ClaimNotFoundError as e:
        raise_http_exception(e)
    except ClaimNotChallengableError as e:
        raise_http_exception(e)
    except ChallengeAlreadyExistsError as e:
        raise_http_exception(e)


# ===========================================
# CHALLENGE LISTING
# ===========================================


@router.get(
    "/{claim_id}/challenges",
    response_model=ChallengeListResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Claim not found"},
    },
)
async def list_claim_challenges(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    List all challenges for a claim.

    Returns all challenges (open, resolved, rejected) ordered by creation date.
    """
    service = ChallengeService(db)

    try:
        result = await service.list_challenges(claim_id)
        return ChallengeListResponse(
            challenges=[ChallengeResponse(**c) for c in result["challenges"]],
            total=result["total"],
        )
    except ClaimNotFoundError as e:
        raise_http_exception(e)


@router.get(
    "/{claim_id}/challenges/{challenge_id}",
    response_model=ChallengeResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Challenge not found"},
    },
)
async def get_challenge(
    claim_id: str,
    challenge_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed challenge information.
    """
    service = ChallengeService(db)

    try:
        result = await service.get_challenge(challenge_id)
        if result["claim_id"] != claim_id:
            raise ChallengeNotFoundError(challenge_id)
        return ChallengeResponse(**result)
    except ChallengeNotFoundError as e:
        raise_http_exception(e)


# ===========================================
# CHALLENGE RESOLUTION
# ===========================================


@router.post(
    "/{claim_id}/challenges/{challenge_id}/resolve",
    response_model=ChallengeResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not authorized"},
        404: {"model": ErrorResponse, "description": "Challenge not found"},
    },
)
async def resolve_challenge(
    claim_id: str,
    challenge_id: str,
    resolution: ChallengeResolutionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Resolve a challenge.

    Only the claim owner can resolve challenges against their claims.

    **Resolution Types:**

    - `accepted`: The challenge is valid, claim will be re-verified or retracted
    - `rejected`: The challenge is invalid, no action needed
    - `partial`: The challenge is partially valid, claim may be updated

    **Example Request:**
    ```json
    {
        "resolution": "accepted",
        "response": "The challenger correctly identified an error in our methodology...",
        "updated_claim": null
    }
    ```
    """
    agent = get_agent_context(request)
    service = ChallengeService(db)

    try:
        result = await service.resolve_challenge(
            challenge_id=challenge_id,
            resolver_id=agent["agent_id"],
            resolution=resolution.resolution,
            response=resolution.response,
        )
        await db.commit()

        logger.info(
            "challenge_resolved",
            challenge_id=challenge_id,
            resolution=resolution.resolution,
        )

        return ChallengeResponse(**result)

    except ChallengeNotFoundError as e:
        raise_http_exception(e)
    except UnauthorizedClaimAccessError as e:
        raise_http_exception(e)


# ===========================================
# AGENT'S CHALLENGES
# ===========================================


@router.get(
    "/me/challenges",
    response_model=ChallengeListResponse,
)
async def list_my_challenges(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    List challenges submitted by the current agent.
    """
    agent = get_agent_context(request)

    # Query challenges by challenger_id
    from platform.services.claim_service.repository import ChallengeRepository
    from sqlalchemy import select
    from platform.infrastructure.database.models import Challenge

    repo = ChallengeRepository(db)

    query = (
        select(Challenge)
        .where(Challenge.challenger_id == agent["agent_id"])
        .order_by(Challenge.created_at.desc())
    )
    result = await db.execute(query)
    challenges = list(result.scalars().all())

    return ChallengeListResponse(
        challenges=[
            ChallengeResponse(
                challenge_id=str(c.id),
                claim_id=str(c.claim_id),
                challenger_id=str(c.challenger_id),
                challenge_type=c.challenge_type,
                title=c.title,
                description=c.description,
                status=c.status,
                severity=c.severity,
                created_at=c.created_at,
                resolved_at=c.resolved_at,
                resolution=c.resolution,
            )
            for c in challenges
        ],
        total=len(challenges),
    )


@router.get(
    "/me/claims/challenges",
    response_model=ChallengeListResponse,
)
async def list_challenges_against_my_claims(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    List all challenges against the current agent's claims.

    Useful for claim owners to see challenges they need to respond to.
    """
    agent = get_agent_context(request)

    from sqlalchemy import select
    from platform.infrastructure.database.models import Challenge, Claim

    # Get challenges where the claim belongs to this agent
    query = (
        select(Challenge)
        .join(Claim, Challenge.claim_id == Claim.id)
        .where(Claim.agent_id == agent["agent_id"])
        .order_by(Challenge.created_at.desc())
    )
    result = await db.execute(query)
    challenges = list(result.scalars().all())

    return ChallengeListResponse(
        challenges=[
            ChallengeResponse(
                challenge_id=str(c.id),
                claim_id=str(c.claim_id),
                challenger_id=str(c.challenger_id),
                challenge_type=c.challenge_type,
                title=c.title,
                description=c.description,
                status=c.status,
                severity=c.severity,
                created_at=c.created_at,
                resolved_at=c.resolved_at,
                resolution=c.resolution,
            )
            for c in challenges
        ],
        total=len(challenges),
    )
