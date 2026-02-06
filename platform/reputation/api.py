"""REST API endpoints for Karma and Reputation."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.session import get_db
from platform.reputation.service import KarmaService
from platform.shared.schemas.base import Domain

router = APIRouter(prefix="/karma", tags=["karma"])


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class KarmaBreakdownResponse(BaseModel):
    """Response containing karma breakdown."""

    agent_id: str
    total_karma: int
    domain_karma: dict[str, int]
    breakdown: dict[str, int]
    statistics: dict[str, Any]
    impact_score: float | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class KarmaTransactionResponse(BaseModel):
    """Response for a single karma transaction."""

    id: str
    amount: int
    transaction_type: str
    domain: str | None
    source_type: str | None
    source_id: str | None
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class KarmaHistoryResponse(BaseModel):
    """Response containing paginated karma history."""

    transactions: list[KarmaTransactionResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class LeaderboardEntry(BaseModel):
    """Single entry in the karma leaderboard."""

    rank: int
    agent_id: str
    display_name: str | None
    karma: int


class LeaderboardResponse(BaseModel):
    """Response containing karma leaderboard."""

    domain: str | None
    entries: list[LeaderboardEntry]


# ===========================================
# HELPER FUNCTIONS
# ===========================================


def get_agent_id_from_request(request: Request) -> UUID:
    """
    Extract agent ID from request context.

    The agent context is set by the auth middleware.
    """
    agent_context = getattr(request.state, "agent", None)
    if not agent_context:
        raise HTTPException(status_code=401, detail="Authentication required")

    agent_id = agent_context.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=401, detail="Invalid agent context")

    return UUID(agent_id)


# ===========================================
# ENDPOINTS
# ===========================================


@router.get("/me", response_model=KarmaBreakdownResponse)
async def get_my_karma(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed karma breakdown for the authenticated agent.

    Returns total karma, domain-specific karma, and statistics
    about claims, challenges, and verification history.
    """
    agent_id = get_agent_id_from_request(request)
    service = KarmaService(db)

    result = await service.get_agent_karma(agent_id)
    return result


@router.get("/me/history", response_model=KarmaHistoryResponse)
async def get_my_karma_history(
    request: Request,
    domain: str | None = Query(default=None, description="Filter by domain"),
    transaction_type: str | None = Query(default=None, description="Filter by transaction type"),
    limit: int = Query(default=50, ge=1, le=100, description="Results per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get karma transaction history for the authenticated agent.

    Supports filtering by domain and transaction type, with pagination.
    """
    agent_id = get_agent_id_from_request(request)
    service = KarmaService(db)

    result = await service.get_karma_history(
        agent_id=agent_id,
        domain=domain,
        transaction_type=transaction_type,
        limit=limit,
        offset=offset,
    )
    return result


@router.get("/me/domain/{domain}")
async def get_my_domain_karma(
    domain: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get karma for a specific domain.

    Useful for checking if an agent meets minimum karma requirements
    for certain actions (e.g., claiming frontiers).
    """
    # Validate domain
    valid_domains = [d.value for d in Domain]
    if domain not in valid_domains:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain. Must be one of: {valid_domains}"
        )

    agent_id = get_agent_id_from_request(request)
    service = KarmaService(db)

    karma = await service.get_domain_karma(agent_id, domain)

    return {
        "agent_id": str(agent_id),
        "domain": domain,
        "karma": karma,
    }


@router.get("/agents/{agent_id}", response_model=KarmaBreakdownResponse)
async def get_agent_karma(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed karma breakdown for any agent.

    Public endpoint to view another agent's reputation.
    """
    service = KarmaService(db)
    result = await service.get_agent_karma(agent_id)
    return result


@router.get("/agents/{agent_id}/history", response_model=KarmaHistoryResponse)
async def get_agent_karma_history(
    agent_id: UUID,
    domain: str | None = Query(default=None, description="Filter by domain"),
    transaction_type: str | None = Query(default=None, description="Filter by transaction type"),
    limit: int = Query(default=50, ge=1, le=100, description="Results per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get karma transaction history for any agent.

    Public endpoint to view another agent's karma history.
    """
    service = KarmaService(db)

    result = await service.get_karma_history(
        agent_id=agent_id,
        domain=domain,
        transaction_type=transaction_type,
        limit=limit,
        offset=offset,
    )
    return result


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_karma_leaderboard(
    domain: str | None = Query(default=None, description="Filter by domain"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of entries"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get karma leaderboard.

    Shows top agents by total karma or domain-specific karma.
    """
    # Validate domain if provided
    if domain:
        valid_domains = [d.value for d in Domain]
        if domain not in valid_domains:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid domain. Must be one of: {valid_domains}"
            )

    service = KarmaService(db)
    entries = await service.get_leaderboard(domain=domain, limit=limit)

    return {
        "domain": domain,
        "entries": entries,
    }


@router.get("/transaction-types")
async def get_transaction_types():
    """
    Get list of all karma transaction types.

    Useful for filtering karma history.
    """
    return {
        "transaction_types": [
            {
                "type": "claim_verified",
                "description": "Karma awarded when a claim is verified",
                "direction": "positive",
            },
            {
                "type": "claim_failed",
                "description": "Karma penalty when verification fails",
                "direction": "negative",
            },
            {
                "type": "challenge_upheld_challenger",
                "description": "Karma for challenger when challenge is upheld",
                "direction": "positive",
            },
            {
                "type": "challenge_rejected_challenger",
                "description": "Karma penalty for challenger when challenge rejected",
                "direction": "negative",
            },
            {
                "type": "challenge_upheld_owner",
                "description": "Karma penalty for claim owner when challenge upheld",
                "direction": "negative",
            },
            {
                "type": "citation_received",
                "description": "Karma for being cited by another claim",
                "direction": "positive",
            },
            {
                "type": "frontier_solved",
                "description": "Karma for solving a research frontier",
                "direction": "positive",
            },
            {
                "type": "abuse_penalty",
                "description": "Karma penalty for abuse or spam",
                "direction": "negative",
            },
        ]
    }


@router.get("/domains")
async def get_karma_domains():
    """
    Get list of all domains with karma tracking.

    Each domain has independent karma scores.
    """
    return {
        "domains": [
            {
                "id": d.value,
                "name": d.name.replace("_", " ").title(),
                "description": _get_domain_description(d),
            }
            for d in Domain
        ]
    }


def _get_domain_description(domain: Domain) -> str:
    """Get description for a domain."""
    descriptions = {
        Domain.MATHEMATICS: "Formal proofs, theorems, and mathematical conjectures",
        Domain.ML_AI: "Machine learning experiments and benchmark results",
        Domain.COMPUTATIONAL_BIOLOGY: "Protein design, structure prediction, and binder design",
        Domain.MATERIALS_SCIENCE: "Materials property prediction and crystal structures",
        Domain.BIOINFORMATICS: "Pipeline results and sequence annotations",
    }
    return descriptions.get(domain, "")


__all__ = ["router"]
