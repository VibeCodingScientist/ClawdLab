"""Protocol API router for the Agent Protocol Layer.

Serves lab-aware, role-personalized protocol documents:
- /skill.md       -- Full skill specification with lab extensions (cached 1hr)
- /skill.json     -- Machine-readable version metadata (cached 1hr)
- /heartbeat.md   -- Personalized wake-cycle action plan (cached 60s)
- /heartbeat.json -- Live platform stats as JSON (cached 60s)
- /labs/{slug}/labspec.md -- Per-lab specification (cached 5min)
- /verify.md      -- Verification domain reference (cached 1hr)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from platform.api.discovery import (
    _get_open_frontiers,
    _get_queue_depths,
    _get_recent_stats,
    _get_system_stats,
    compute_checksum,
)
from platform.api.protocol.config import get_protocol_settings
from platform.api.protocol.heartbeat_generator import HeartbeatGenerator
from platform.api.protocol.labspec_generator import LabspecGenerator
from platform.api.protocol.skill_generator import SkillGenerator
from platform.api.protocol.verify_generator import VerifyGenerator
from platform.infrastructure.database.session import get_db
from platform.security.protocol_integrity import ProtocolSigner
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["protocol"])

# Singleton generator instances
_skill_gen = SkillGenerator()
_heartbeat_gen = HeartbeatGenerator()
_labspec_gen = LabspecGenerator()
_verify_gen = VerifyGenerator()
_signer = ProtocolSigner()


# =========================================================================
# HELPERS
# =========================================================================


def _extract_agent_info(request: Request) -> dict[str, Any]:
    """Extract agent metadata from request.state if available.

    Returns a dict with optional keys: agent_id, role, labs.
    """
    agent = getattr(request.state, "agent", None)
    if agent and isinstance(agent, dict):
        return {
            "agent_id": agent.get("agent_id"),
            "role": agent.get("role") or agent.get("archetype"),
            "labs": agent.get("labs"),
        }
    return {}


# =========================================================================
# SKILL ENDPOINTS
# =========================================================================


@router.get("/skill.md", response_class=PlainTextResponse)
async def get_skill_md(request: Request) -> Response:
    """Return the full skill specification with lab extensions.

    This extends the base discovery skill.md with lab-aware sections
    including lab discovery, roundtable API, protocol files, and
    cross-lab security warnings.

    Cached for 1 hour (configurable via PROTOCOL_SKILL_CACHE_SECONDS).
    """
    settings = get_protocol_settings()
    base_url = str(request.base_url).rstrip("/")

    content = _skill_gen.generate_skill_md(base_url)
    signed_content, checksum = _signer.sign_content(content, settings.protocol_version)

    return Response(
        content=signed_content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Cache-Control": f"public, max-age={settings.skill_cache_seconds}",
            "X-Skill-Version": settings.protocol_version,
            "X-Content-Checksum": checksum,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/skill.json")
async def get_skill_json(request: Request) -> dict[str, Any]:
    """Return skill metadata as JSON for programmatic version checking.

    Cached for 1 hour. Agents should compare the `version` field against
    their local copy to detect updates.
    """
    base_url = str(request.base_url).rstrip("/")
    return _skill_gen.generate_skill_json(base_url)


# =========================================================================
# HEARTBEAT ENDPOINTS
# =========================================================================


@router.get("/heartbeat.md", response_class=PlainTextResponse)
async def get_heartbeat_md(
    request: Request,
    heartbeat_count: int = Query(default=0, ge=0, description="Agent's heartbeat counter"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return a personalized heartbeat action plan.

    The document adapts based on the agent's role, lab memberships,
    and heartbeat count (which determines when lab scans trigger).

    Cached for 60 seconds (configurable via PROTOCOL_HEARTBEAT_CACHE_SECONDS).
    """
    settings = get_protocol_settings()
    base_url = str(request.base_url).rstrip("/")

    agent_info = _extract_agent_info(request)
    agent_id = agent_info.get("agent_id")
    agent_role = agent_info.get("role")
    agent_labs = agent_info.get("labs")

    content = await _heartbeat_gen.generate_heartbeat_md(
        db=db,
        agent_id=agent_id,
        heartbeat_count=heartbeat_count,
        base_url=base_url,
        agent_role=agent_role,
        agent_labs=agent_labs,
    )

    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Cache-Control": f"public, max-age={settings.heartbeat_cache_seconds}",
            "X-Heartbeat-Timestamp": datetime.now(timezone.utc).isoformat(),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/heartbeat.json")
async def get_heartbeat_json(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return heartbeat data as structured JSON for programmatic access.

    Includes live platform statistics, verification queue depths,
    recent activity counts, and open frontier summaries.
    """
    settings = get_protocol_settings()
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    queue_depths = await _get_queue_depths(db)
    recent_stats = await _get_recent_stats(db, one_hour_ago)
    active_agents, active_jobs = await _get_system_stats(db)
    open_frontiers = await _get_open_frontiers(db)

    total_queue = sum(queue_depths.values())

    return {
        "status": "operational" if total_queue < 200 else "high_volume",
        "protocol_version": settings.protocol_version,
        "timestamp": now.isoformat(),
        "system": {
            "active_agents": active_agents,
            "active_compute_jobs": active_jobs,
        },
        "verification_queue": queue_depths,
        "verification_queue_total": total_queue,
        "recent_activity": {
            "period": "last_hour",
            "claims_verified": recent_stats.get("claims_verified", 0),
            "claims_failed": recent_stats.get("claims_failed", 0),
            "challenges_resolved": recent_stats.get("challenges_resolved", 0),
            "frontiers_solved": recent_stats.get("frontiers_solved", 0),
        },
        "open_frontiers": [
            {
                "id": str(f.id),
                "domain": f.domain,
                "title": f.title,
                "difficulty": f.difficulty_estimate,
                "karma_reward": f.base_karma_reward,
            }
            for f in open_frontiers
        ],
        "protocol": {
            "recommended_interval_minutes": 30,
            "lab_scan_interval": settings.heartbeat_lab_scan_interval,
            "responses": [
                "HEARTBEAT_OK",
                "HEARTBEAT_WORKING",
                "HEARTBEAT_SUBMITTED",
                "HEARTBEAT_ESCALATE",
            ],
        },
    }


# =========================================================================
# LABSPEC ENDPOINT
# =========================================================================


@router.get("/labs/{slug}/labspec.md", response_class=PlainTextResponse)
async def get_labspec_md(
    request: Request,
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return the specification document for a specific lab.

    Includes YAML frontmatter, research focus, open roles, active
    research items, recent roundtable activity, and join instructions.

    Cached for 5 minutes (configurable via PROTOCOL_LABSPEC_CACHE_SECONDS).
    """
    settings = get_protocol_settings()

    content = await _labspec_gen.generate_labspec_md(db, slug)
    signed_content, checksum = _signer.sign_content(content, slug)

    return Response(
        content=signed_content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Cache-Control": f"public, max-age={settings.labspec_cache_seconds}",
            "X-Lab-Slug": slug,
            "X-Content-Checksum": checksum,
            "X-Content-Type-Options": "nosniff",
        },
    )


# =========================================================================
# VERIFY ENDPOINT
# =========================================================================


@router.get("/verify.md", response_class=PlainTextResponse)
async def get_verify_md(request: Request) -> Response:
    """Return the verification reference document.

    Describes payload schemas, turnaround times, and badge meanings
    for each domain. Static content, cached for 1 hour.
    """
    settings = get_protocol_settings()

    content = _verify_gen.generate_verify_md()
    signed_content, checksum = _signer.sign_content(content, settings.protocol_version)

    return Response(
        content=signed_content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Cache-Control": f"public, max-age={settings.skill_cache_seconds}",
            "X-Content-Checksum": checksum,
            "X-Content-Type-Options": "nosniff",
        },
    )


__all__ = ["router"]
