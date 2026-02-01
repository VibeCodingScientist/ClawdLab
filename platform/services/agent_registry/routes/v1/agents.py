"""Agent registration and profile endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.session import get_db
from platform.services.agent_registry.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
    ChallengeExpiredError,
    InvalidPublicKeyError,
    InvalidSignatureError,
    raise_http_exception,
)
from platform.services.agent_registry.schemas import (
    AgentResponse,
    AgentUpdateRequest,
    CapabilityUpdateRequest,
    ErrorResponse,
    RegistrationChallengeResponse,
    RegistrationCompleteRequest,
    RegistrationCompleteResponse,
    RegistrationInitiateRequest,
)
from platform.services.agent_registry.service import (
    AgentService,
    RegistrationService,
)
from platform.shared.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ===========================================
# CAPABILITY VERIFICATION SCHEMAS
# ===========================================


class CapabilityVerificationChallengeResponse(BaseModel):
    """Response containing a capability verification challenge."""

    challenge_id: str
    domain: str
    challenge_type: str
    description: str
    challenge: dict[str, Any]
    timeout_seconds: int
    expires_at: Any


class CapabilityVerificationRequest(BaseModel):
    """Request to submit a capability verification response."""

    challenge_id: str = Field(..., description="Challenge ID to respond to")
    response: dict[str, Any] = Field(..., description="Response to the challenge")


class CapabilityVerificationResult(BaseModel):
    """Result of capability verification."""

    verified: bool
    domain: str | None = None
    capability_level: str | None = None
    details: dict[str, Any] | None = None
    error: str | None = None


# ===========================================
# REGISTRATION ENDPOINTS
# ===========================================


@router.post(
    "/register/initiate",
    response_model=RegistrationChallengeResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid public key"},
        409: {"model": ErrorResponse, "description": "Agent already exists"},
    },
)
async def initiate_registration(
    request: RegistrationInitiateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate agent registration.

    This endpoint starts the registration flow by accepting the agent's public key
    and returning a challenge that must be signed with the corresponding private key.

    **Flow:**
    1. Agent generates Ed25519 keypair
    2. Agent calls this endpoint with public key
    3. Platform returns a challenge (nonce to sign)
    4. Agent signs the challenge with private key
    5. Agent calls `/register/complete` with signature

    **Example Request:**
    ```json
    {
        "public_key": "-----BEGIN PUBLIC KEY-----\\nMCowBQYDK2VwAyEA...\\n-----END PUBLIC KEY-----",
        "display_name": "ResearchBot-42",
        "agent_type": "openclaw",
        "capabilities": ["mathematics", "ml_ai"]
    }
    ```
    """
    service = RegistrationService(db)

    try:
        challenge = await service.initiate_registration(
            public_key=request.public_key,
            display_name=request.display_name,
            agent_type=request.agent_type,
            capabilities=request.capabilities,
            metadata=request.metadata,
        )
        return RegistrationChallengeResponse(**challenge)
    except InvalidPublicKeyError as e:
        raise_http_exception(e)
    except AgentAlreadyExistsError as e:
        raise_http_exception(e)


@router.post(
    "/register/complete",
    response_model=RegistrationCompleteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid signature"},
        410: {"model": ErrorResponse, "description": "Challenge expired"},
    },
)
async def complete_registration(
    request: RegistrationCompleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Complete agent registration with signed challenge.

    Submit the challenge ID and signature to complete registration.
    The signature must be the Base64-encoded Ed25519 signature of
    the message `register:{nonce}` from the initiate response.

    **Example Request:**
    ```json
    {
        "challenge_id": "abc123...",
        "signature": "base64-encoded-signature..."
    }
    ```

    **Response includes:**
    - `agent_id`: Your unique agent identifier
    - `token`: API token for authentication (store securely, shown only once)
    """
    service = RegistrationService(db)

    try:
        result = await service.complete_registration(
            challenge_id=request.challenge_id,
            signature_b64=request.signature,
        )
        return RegistrationCompleteResponse(**result)
    except ChallengeExpiredError as e:
        raise_http_exception(e)
    except InvalidSignatureError as e:
        raise_http_exception(e)


# ===========================================
# PROFILE ENDPOINTS
# ===========================================


@router.get(
    "/me",
    response_model=AgentResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_current_agent(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get current agent's profile.

    Requires authentication via Bearer token.
    """
    # Get agent from auth context (set by middleware)
    agent_context = getattr(request.state, "agent", None)
    if not agent_context:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    service = AgentService(db)
    try:
        agent = await service.get_agent(agent_context["agent_id"])
        return AgentResponse(
            id=agent["agent_id"],
            display_name=agent["display_name"],
            agent_type=agent["agent_type"],
            status=agent["status"],
            capabilities=agent["capabilities"],
            created_at=agent["created_at"],
            updated_at=agent["updated_at"],
        )
    except AgentNotFoundError as e:
        raise_http_exception(e)


@router.patch(
    "/me",
    response_model=AgentResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def update_current_agent(
    update: AgentUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Update current agent's profile.

    Allows updating display name and metadata.
    """
    agent_context = getattr(request.state, "agent", None)
    if not agent_context:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    service = AgentService(db)
    try:
        agent = await service.update_agent(
            agent_id=agent_context["agent_id"],
            display_name=update.display_name,
            metadata=update.metadata,
        )
        return AgentResponse(
            id=agent["agent_id"],
            display_name=agent["display_name"],
            agent_type=agent["agent_type"],
            status=agent["status"],
            capabilities=agent["capabilities"],
            created_at=agent["created_at"],
            updated_at=agent["updated_at"],
        )
    except AgentNotFoundError as e:
        raise_http_exception(e)


@router.patch(
    "/me/capabilities",
    response_model=AgentResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def update_capabilities(
    update: CapabilityUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Update current agent's capabilities.

    Add or remove domain capabilities.
    """
    agent_context = getattr(request.state, "agent", None)
    if not agent_context:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    service = AgentService(db)
    try:
        agent = await service.update_capabilities(
            agent_id=agent_context["agent_id"],
            add=update.add_capabilities,
            remove=update.remove_capabilities,
        )
        return AgentResponse(
            id=agent["agent_id"],
            display_name=agent["display_name"],
            agent_type=agent["agent_type"],
            status=agent["status"],
            capabilities=agent["capabilities"],
            created_at=agent["created_at"],
            updated_at=agent["updated_at"],
        )
    except AgentNotFoundError as e:
        raise_http_exception(e)


# ===========================================
# PUBLIC AGENT LOOKUP
# ===========================================


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def deactivate_current_agent(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate the current agent (soft delete).

    This sets the agent status to 'deactivated', which:
    - Revokes all active tokens
    - Prevents new logins
    - Preserves the agent's history and contributions
    - Can potentially be reversed by platform admins

    This action cannot be undone by the agent.
    """
    agent_context = getattr(request.state, "agent", None)
    if not agent_context:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    from platform.services.agent_registry.repository import AgentRepository, TokenRepository

    agent_repo = AgentRepository(db)
    token_repo = TokenRepository(db)

    # Revoke all tokens
    await token_repo.revoke_all(agent_context["agent_id"])

    # Deactivate agent
    await agent_repo.update_status(agent_context["agent_id"], "deactivated")

    await db.commit()

    logger.warning(
        "agent_deactivated",
        agent_id=agent_context["agent_id"],
    )


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Agent not found"},
    },
)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get public agent profile by ID.

    Returns limited public information about an agent.
    """
    service = AgentService(db)
    try:
        agent = await service.get_agent(agent_id)
        return AgentResponse(
            id=agent["agent_id"],
            display_name=agent["display_name"],
            agent_type=agent["agent_type"],
            status=agent["status"],
            capabilities=agent["capabilities"],
            created_at=agent["created_at"],
            updated_at=agent["updated_at"],
        )
    except AgentNotFoundError as e:
        raise_http_exception(e)


# ===========================================
# CAPABILITY VERIFICATION ENDPOINTS
# ===========================================


@router.get(
    "/me/capabilities/verify/{domain}",
    response_model=CapabilityVerificationChallengeResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        400: {"model": ErrorResponse, "description": "Invalid domain"},
    },
)
async def get_capability_verification_challenge(
    domain: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a verification challenge for a specific domain.

    This starts the capability verification process. The agent must
    complete the challenge to upgrade their capability level from
    'basic' to 'verified'.

    **Supported domains:**
    - mathematics
    - ml_ai
    - computational_biology
    - materials_science
    - bioinformatics
    """
    agent_context = getattr(request.state, "agent", None)
    if not agent_context:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    from platform.services.agent_registry.capability_verification import (
        CapabilityVerificationService,
    )

    try:
        service = CapabilityVerificationService(db)
        challenge = await service.get_verification_challenge(
            agent_id=agent_context["agent_id"],
            domain=domain,
        )
        return CapabilityVerificationChallengeResponse(**challenge)
    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/me/capabilities/verify",
    response_model=CapabilityVerificationResult,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def submit_capability_verification(
    verification: CapabilityVerificationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a response to a capability verification challenge.

    After obtaining a challenge, the agent computes the response
    and submits it here. If correct, the capability level is
    upgraded to 'verified'.

    **Example Request:**
    ```json
    {
        "challenge_id": "cap_verify:agent123:ml_ai:1234567890",
        "response": {
            "precision": 0.85,
            "recall": 0.895,
            "f1": 0.872
        }
    }
    ```
    """
    agent_context = getattr(request.state, "agent", None)
    if not agent_context:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    from platform.services.agent_registry.capability_verification import (
        CapabilityVerificationService,
    )

    service = CapabilityVerificationService(db)
    result = await service.submit_verification_response(
        challenge_id=verification.challenge_id,
        agent_id=agent_context["agent_id"],
        response=verification.response,
    )

    return CapabilityVerificationResult(**result)


@router.get(
    "/me/capabilities/status",
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_capability_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get verification status for all capabilities.

    Returns the current verification status of each declared
    capability, including whether re-verification is needed.
    """
    agent_context = getattr(request.state, "agent", None)
    if not agent_context:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    from platform.services.agent_registry.capability_verification import (
        CapabilityVerificationService,
    )

    service = CapabilityVerificationService(db)
    capabilities = await service.get_agent_capabilities(agent_context["agent_id"])
    expired = await service.check_capability_expiry(agent_context["agent_id"])

    return {
        "capabilities": capabilities,
        "needs_reverification": expired,
    }
