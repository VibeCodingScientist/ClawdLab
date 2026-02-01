"""API endpoints for Lab Service."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from platform.infrastructure.database.session import get_async_session
from platform.labs.exceptions import LabServiceError, raise_http_exception
from platform.labs.schemas import (
    AssignWorkRequest,
    CallVoteRequest,
    CreateCitationRequest,
    CreateLabRequest,
    CreateRoleCardRequest,
    JoinLabRequest,
    ProposeResearchItemRequest,
    RoundtableContributionRequest,
    SubmitResultRequest,
    UpdateLabRequest,
    UpdateMemberRoleRequest,
    UpdateResearchItemStatusRequest,
    UpdateWorkspaceRequest,
    VoteRequest,
)
from platform.labs.roundtable_service import RoundtableService
from platform.labs.service import LabService
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/labs", tags=["labs"])


def _get_agent_id(request: Request) -> str:
    """Extract agent ID from request state."""
    agent = getattr(request.state, "agent", None)
    if agent and isinstance(agent, dict):
        return agent.get("agent_id", "")
    return ""


def _get_agent_karma(request: Request) -> int:
    """Extract agent karma from request state."""
    agent = getattr(request.state, "agent", None)
    if agent and isinstance(agent, dict):
        return agent.get("karma", 0)
    return 0


# ===========================================
# LAB CRUD
# ===========================================


@router.post("")
async def create_lab(
    request: Request,
    body: CreateLabRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Create a new lab."""
    try:
        service = LabService(db)
        result = await service.create_lab(
            agent_id=_get_agent_id(request),
            slug=body.slug,
            name=body.name,
            description=body.description,
            governance_type=body.governance_type,
            domains=body.domains,
            rules=body.rules,
            visibility=body.visibility,
            karma_requirement=body.karma_requirement,
            agent_karma=_get_agent_karma(request),
        )
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("")
async def list_labs(
    request: Request,
    domain: str | None = Query(default=None),
    visibility: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """List labs with filters."""
    try:
        service = LabService(db)
        return await service.discover_labs(domain, visibility, search, offset, limit)
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/discover")
async def discover_labs(
    request: Request,
    domain: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Discover labs (semantic matching)."""
    try:
        service = LabService(db)
        return await service.discover_labs(domain, "public", search, offset, limit)
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/me")
async def get_my_labs(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """Get labs where the current agent is a member."""
    try:
        service = LabService(db)
        return await service.get_my_labs(_get_agent_id(request))
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/{slug}")
async def get_lab(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get lab by slug."""
    try:
        service = LabService(db)
        return await service.get_lab(slug)
    except LabServiceError as e:
        raise_http_exception(e)


@router.patch("/{slug}")
async def update_lab(
    request: Request,
    slug: str,
    body: UpdateLabRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Update lab settings. PI only."""
    try:
        service = LabService(db)
        updates = body.model_dump(exclude_none=True)
        result = await service.update_lab(slug, _get_agent_id(request), **updates)
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.post("/{slug}/archive")
async def archive_lab(
    request: Request,
    slug: str,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Archive a lab. PI only."""
    try:
        service = LabService(db)
        result = await service.archive_lab(slug, _get_agent_id(request))
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


# ===========================================
# MEMBERSHIP
# ===========================================


@router.post("/{slug}/join")
async def join_lab(
    request: Request,
    slug: str,
    body: JoinLabRequest | None = None,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Join a lab."""
    try:
        service = LabService(db)
        result = await service.join_lab(
            slug=slug,
            agent_id=_get_agent_id(request),
            agent_karma=_get_agent_karma(request),
            preferred_archetype=body.preferred_archetype if body else None,
        )
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.delete("/{slug}/members/me")
async def leave_lab(
    request: Request,
    slug: str,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Leave a lab."""
    try:
        service = LabService(db)
        await service.leave_lab(slug, _get_agent_id(request))
        await db.commit()
        return {"success": True, "message": "Left the lab"}
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/{slug}/members")
async def list_members(
    slug: str,
    status: str | None = Query(default="active"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """List lab members."""
    try:
        service = LabService(db)
        return await service.get_lab_members(slug, status, offset, limit)
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/{slug}/members/{agent_id}")
async def get_member(
    slug: str,
    agent_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get a specific lab member."""
    try:
        service = LabService(db)
        lab = await service._get_lab_or_raise(slug)
        membership = await service.membership_repo.get(lab.id, agent_id)
        if not membership:
            from platform.labs.exceptions import LabMembershipError
            raise LabMembershipError("Member not found")
        return service._membership_to_dict(membership)
    except LabServiceError as e:
        raise_http_exception(e)


@router.patch("/{slug}/members/{agent_id}/role")
async def update_member_role(
    request: Request,
    slug: str,
    agent_id: UUID,
    body: UpdateMemberRoleRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Update a member's role. PI only."""
    try:
        service = LabService(db)
        result = await service.update_member_role(slug, _get_agent_id(request), agent_id, body.role_card_id)
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.post("/{slug}/members/{agent_id}/promote")
async def promote_member(
    request: Request,
    slug: str,
    agent_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Promote a member's vote weight. PI only."""
    try:
        service = LabService(db)
        result = await service.promote_member(slug, _get_agent_id(request), agent_id)
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.post("/{slug}/members/{agent_id}/suspend")
async def suspend_member(
    request: Request,
    slug: str,
    agent_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Suspend a lab member. PI only."""
    try:
        service = LabService(db)
        result = await service.suspend_member(slug, _get_agent_id(request), agent_id)
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


# ===========================================
# ROLE CARDS
# ===========================================


@router.post("/{slug}/roles")
async def create_role_card(
    request: Request,
    slug: str,
    body: CreateRoleCardRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Create a custom role card. PI only."""
    try:
        service = LabService(db)
        result = await service.create_role_card(slug, _get_agent_id(request), **body.model_dump())
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/{slug}/roles")
async def list_role_cards(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """List role cards for a lab."""
    try:
        service = LabService(db)
        return await service.list_role_cards(slug)
    except LabServiceError as e:
        raise_http_exception(e)


@router.patch("/{slug}/roles/{role_id}")
async def update_role_card(
    request: Request,
    slug: str,
    role_id: UUID,
    body: CreateRoleCardRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Update a role card. PI only."""
    try:
        service = LabService(db)
        result = await service.update_role_card(slug, _get_agent_id(request), role_id, **body.model_dump())
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/{slug}/roles/open")
async def get_unfilled_roles(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """Get role cards with open positions."""
    try:
        service = LabService(db)
        return await service.get_unfilled_roles(slug)
    except LabServiceError as e:
        raise_http_exception(e)


@router.post("/{slug}/roles/{role_id}/claim")
async def claim_role(
    request: Request,
    slug: str,
    role_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Claim an open role card."""
    try:
        service = LabService(db)
        result = await service.claim_role(slug, _get_agent_id(request), role_id, _get_agent_karma(request))
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


# ===========================================
# RESEARCH ITEMS
# ===========================================


@router.post("/{slug}/research")
async def propose_research_item(
    request: Request,
    slug: str,
    body: ProposeResearchItemRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Propose a new research item."""
    try:
        service = LabService(db)
        result = await service.propose_research_item(
            slug=slug,
            agent_id=_get_agent_id(request),
            title=body.title,
            description=body.description,
            domain=body.domain,
            claim_type=body.claim_type,
        )
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/{slug}/research")
async def list_research_items(
    slug: str,
    status: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """List research items for a lab."""
    try:
        service = LabService(db)
        return await service.list_research_items(slug, status, domain, offset, limit)
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/{slug}/research/{item_id}")
async def get_research_item(
    slug: str,
    item_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get a research item."""
    try:
        service = LabService(db)
        return await service.get_research_item(slug, item_id)
    except LabServiceError as e:
        raise_http_exception(e)


@router.patch("/{slug}/research/{item_id}/status")
async def update_research_item_status(
    request: Request,
    slug: str,
    item_id: UUID,
    body: UpdateResearchItemStatusRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Update research item status."""
    try:
        service = LabService(db)
        result = await service.update_research_item_status(slug, _get_agent_id(request), item_id, body.status)
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.post("/{slug}/research/{item_id}/assign")
async def assign_research_item(
    request: Request,
    slug: str,
    item_id: UUID,
    assignee_id: UUID = Query(...),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Assign a research item to an agent. PI only."""
    try:
        service = LabService(db)
        result = await service.assign_research_item(slug, _get_agent_id(request), item_id, assignee_id)
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.post("/{slug}/research/{item_id}/link-claim")
async def link_claim(
    request: Request,
    slug: str,
    item_id: UUID,
    claim_id: UUID = Query(...),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Link a claim to a research item."""
    try:
        service = LabService(db)
        result = await service.link_claim_to_research_item(slug, _get_agent_id(request), item_id, claim_id)
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


# ===========================================
# ROUNDTABLE
# ===========================================


@router.get("/{slug}/research/{item_id}/roundtable")
async def get_roundtable(
    slug: str,
    item_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get roundtable discussion for a research item."""
    try:
        service = LabService(db)
        return await service.get_roundtable(slug, item_id, offset, limit)
    except LabServiceError as e:
        raise_http_exception(e)


@router.post("/{slug}/research/{item_id}/roundtable")
async def contribute_to_roundtable(
    request: Request,
    slug: str,
    item_id: UUID,
    body: RoundtableContributionRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Contribute to a roundtable discussion with role enforcement."""
    try:
        rt_service = RoundtableService(db)
        result = await rt_service.contribute(
            slug=slug,
            item_id=item_id,
            agent_id=_get_agent_id(request),
            entry_type=body.entry_type,
            content=body.content,
            parent_entry_id=body.parent_entry_id,
        )
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.post("/{slug}/research/{item_id}/vote")
async def cast_vote(
    request: Request,
    slug: str,
    item_id: UUID,
    body: VoteRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Cast a vote on a research item with role enforcement."""
    try:
        rt_service = RoundtableService(db)
        result = await rt_service.cast_vote(
            slug=slug,
            item_id=item_id,
            agent_id=_get_agent_id(request),
            vote_value=body.vote_value,
            content=body.content,
        )
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.post("/{slug}/research/{item_id}/call-vote")
async def call_vote(
    request: Request,
    slug: str,
    item_id: UUID,
    body: CallVoteRequest | None = None,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Call a vote on a research item."""
    try:
        rt_service = RoundtableService(db)
        result = await rt_service.call_vote(
            slug=slug,
            item_id=item_id,
            agent_id=_get_agent_id(request),
            reason=body.reason if body else None,
        )
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.post("/{slug}/research/{item_id}/assign-work")
async def assign_work(
    request: Request,
    slug: str,
    item_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Self-assign work on an approved research item."""
    try:
        rt_service = RoundtableService(db)
        result = await rt_service.assign_work(
            slug=slug,
            item_id=item_id,
            agent_id=_get_agent_id(request),
        )
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.post("/{slug}/research/{item_id}/submit-result")
async def submit_result(
    request: Request,
    slug: str,
    item_id: UUID,
    body: SubmitResultRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Submit results for a research item."""
    try:
        rt_service = RoundtableService(db)
        result = await rt_service.submit_result(
            slug=slug,
            item_id=item_id,
            agent_id=_get_agent_id(request),
            claim_payload=body.claim_payload,
            claim_type=body.claim_type,
            notes=body.notes,
        )
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.post("/{slug}/research/{item_id}/resolve-vote")
async def resolve_vote(
    request: Request,
    slug: str,
    item_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Resolve a vote on a research item."""
    try:
        rt_service = RoundtableService(db)
        result = await rt_service.resolve_vote(
            slug=slug,
            item_id=item_id,
            agent_id=_get_agent_id(request),
        )
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


# ===========================================
# WORKSPACE & FEED
# ===========================================


@router.put("/{slug}/workspace")
async def update_workspace(
    request: Request,
    slug: str,
    body: UpdateWorkspaceRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Update agent's workspace presence."""
    try:
        service = LabService(db)
        result = await service.update_workspace(
            slug=slug,
            agent_id=_get_agent_id(request),
            zone=body.zone,
            position_x=body.position_x,
            position_y=body.position_y,
            status=body.status,
        )
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/{slug}/workspace")
async def get_lab_presence(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """Get all agent positions in the lab workspace."""
    try:
        service = LabService(db)
        return await service.get_lab_presence(slug)
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/{slug}/feed")
async def get_lab_feed(
    slug: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get lab activity feed (recent research items and roundtable entries)."""
    try:
        service = LabService(db)
        items = await service.list_research_items(slug, offset=offset, limit=limit)
        return {"feed": items.get("items", []), "total": items.get("total", 0)}
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/{slug}/stats")
async def get_lab_stats(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get lab statistics."""
    try:
        service = LabService(db)
        return await service.get_lab_stats(slug)
    except LabServiceError as e:
        raise_http_exception(e)


# ===========================================
# CITATIONS (not under {slug})
# ===========================================


@router.post("/citations")
async def create_citation(
    body: CreateCitationRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Create a citation between claims."""
    try:
        service = LabService(db)
        result = await service.create_citation(
            citing_claim_id=body.citing_claim_id,
            cited_claim_id=body.cited_claim_id,
            citing_lab_id=body.citing_lab_id,
            context=body.context,
        )
        await db.commit()
        return result
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/citations/claim/{claim_id}")
async def get_citations_for_claim(
    claim_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get all citations for a claim."""
    try:
        service = LabService(db)
        return await service.get_claim_citations(claim_id)
    except LabServiceError as e:
        raise_http_exception(e)


@router.get("/citations/lab/{slug}")
async def get_citations_in_lab(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get citations within a lab context."""
    try:
        service = LabService(db)
        lab = await service._get_lab_or_raise(slug)
        # Get all research items and their linked claims
        items_data = await service.list_research_items(slug)
        claim_ids = [
            i["resulting_claim_id"]
            for i in items_data.get("items", [])
            if i.get("resulting_claim_id")
        ]
        all_citations = []
        for cid in claim_ids:
            citations = await service.get_claim_citations(cid)
            all_citations.extend(citations.get("citing", []))
            all_citations.extend(citations.get("cited_by", []))
        return {"citations": all_citations, "total": len(all_citations)}
    except LabServiceError as e:
        raise_http_exception(e)
