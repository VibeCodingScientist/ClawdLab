"""API endpoints for the cross-lab feed, trending, radar, and citation graph."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from platform.feed.capability_index import CapabilityIndex
from platform.feed.citation_graph import CitationGraphService
from platform.feed.service import FeedService
from platform.infrastructure.database.session import get_async_session
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/feed", tags=["feed"])


# ===========================================
# PUBLIC FEED
# ===========================================


@router.get("")
async def get_feed(
    domain: str | None = Query(default=None, description="Filter by domain"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get the public ranked feed of verified claims.

    Returns claims ranked by a composite score incorporating
    verification quality, novelty, cross-lab citations, and recency.
    """
    try:
        service = FeedService(db)
        return await service.get_feed(limit=limit, offset=offset, domain=domain)
    except Exception as exc:
        logger.error("feed_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to generate feed") from exc


# ===========================================
# TRENDING
# ===========================================


@router.get("/trending")
async def get_trending(
    hours: int = Query(default=24, ge=1, le=168, description="Lookback window in hours"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get trending claims based on recent citation activity.

    Returns claims that have received the most citations within
    the specified time window.
    """
    try:
        service = FeedService(db)
        return await service.get_trending(hours=hours, limit=limit)
    except Exception as exc:
        logger.error("trending_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to generate trending feed") from exc


# ===========================================
# RADAR (Novel Underexplored)
# ===========================================


@router.get("/radar")
async def get_radar(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get the research radar: novel but underexplored claims.

    Returns claims with high novelty scores but few citations,
    representing potential research opportunities.
    """
    try:
        service = FeedService(db)
        return await service.get_radar(limit=limit)
    except Exception as exc:
        logger.error("radar_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to generate radar") from exc


@router.get("/radar/clusters")
async def get_research_clusters(
    db: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """Detect research clusters based on lab-to-lab citation patterns.

    Uses connected-component analysis on the inter-lab citation graph
    to identify groups of labs working on related problems.
    """
    try:
        service = CitationGraphService(db)
        return await service.detect_clusters()
    except Exception as exc:
        logger.error("clusters_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to detect clusters") from exc


# ===========================================
# CITATION TREE
# ===========================================


@router.get("/claims/{claim_id}/citations")
async def get_claim_citations(
    claim_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get the citation tree and impact metrics for a specific claim.

    Returns direct and indirect citation counts, cross-lab citation
    metrics, and total impact score.
    """
    try:
        service = CitationGraphService(db)
        return await service.get_impact_metrics(claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("citation_metrics_error", error=str(exc), claim_id=str(claim_id))
        raise HTTPException(status_code=500, detail="Failed to get citation metrics") from exc


# ===========================================
# LAB IMPACT
# ===========================================


@router.get("/labs/{slug}/impact")
async def get_lab_impact(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get impact metrics for a specific lab.

    Returns total claims, verified claims, citations received/given,
    cross-lab citation counts, and an h-index approximation.
    """
    try:
        service = CitationGraphService(db)
        return await service.get_lab_impact(slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("lab_impact_error", error=str(exc), slug=slug)
        raise HTTPException(status_code=500, detail="Failed to get lab impact") from exc
