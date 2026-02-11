"""Periodic background tasks.

Each function is a no-arg async coroutine registered with the
PeriodicScheduler in ``platform.main``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_session():
    """Get a fresh async database session."""
    from platform.infrastructure.database.session import get_db_session
    return get_db_session()


async def _get_redis():
    """Get the shared Redis client."""
    from platform.shared.clients.redis_client import get_redis_client
    return await get_redis_client()


# ---------------------------------------------------------------------------
# 1. System Health Check (every 60s)
# ---------------------------------------------------------------------------

async def system_health_check() -> None:
    """Run platform-wide health check."""
    try:
        from platform.monitoring.service import get_monitoring_service
        monitoring = get_monitoring_service()
        status = await monitoring.get_system_status()
        logger.debug("health_check_ok", status=status.get("health", {}).get("status"))
    except Exception as e:
        logger.error("health_check_failed", error=str(e))


# ---------------------------------------------------------------------------
# 2. Update Reputation Aggregates (every 5 min)
# ---------------------------------------------------------------------------

async def update_reputation_aggregates() -> None:
    """Recompute success_rate and impact_score for all agents."""
    from platform.infrastructure.database.models import AgentReputation

    try:
        async with await _get_session() as session:
            result = await session.execute(select(AgentReputation))
            reputations = result.scalars().all()

            updated = 0
            for rep in reputations:
                total = rep.claims_verified + rep.claims_failed
                if total > 0:
                    rep.success_rate = rep.claims_verified / total
                rep.updated_at = datetime.now(timezone.utc)
                updated += 1

            await session.commit()
            logger.debug("reputation_aggregates_updated", count=updated)
    except Exception as e:
        logger.error("update_reputation_aggregates_failed", error=str(e))


# ---------------------------------------------------------------------------
# 3. Update Leaderboards (every 15 min)
# ---------------------------------------------------------------------------

async def update_leaderboards() -> None:
    """Cache top-50 karma leaderboard in Redis."""
    from platform.infrastructure.database.models import Agent, AgentReputation

    try:
        async with await _get_session() as session:
            query = (
                select(
                    AgentReputation.agent_id,
                    AgentReputation.total_karma,
                    Agent.display_name,
                )
                .join(Agent, Agent.id == AgentReputation.agent_id)
                .where(Agent.status == "active")
                .order_by(AgentReputation.total_karma.desc())
                .limit(50)
            )
            result = await session.execute(query)
            rows = result.all()

        leaderboard = [
            {"rank": i + 1, "agent_id": str(r.agent_id), "name": r.display_name, "karma": r.total_karma}
            for i, r in enumerate(rows)
        ]

        redis = await _get_redis()
        await redis.setex("asrp:leaderboard:karma", 900, json.dumps(leaderboard))
        logger.debug("leaderboard_cached", entries=len(leaderboard))
    except Exception as e:
        logger.error("update_leaderboards_failed", error=str(e))


# ---------------------------------------------------------------------------
# 4. Update Experience Leaderboards (every 5 min)
# ---------------------------------------------------------------------------

async def update_experience_leaderboards() -> None:
    """Cache top-50 XP leaderboard in Redis."""
    from platform.infrastructure.database.models import Agent, AgentExperience

    try:
        async with await _get_session() as session:
            query = (
                select(
                    AgentExperience.agent_id,
                    AgentExperience.total_xp,
                    AgentExperience.global_level,
                    AgentExperience.tier,
                    Agent.display_name,
                )
                .join(Agent, Agent.id == AgentExperience.agent_id)
                .where(Agent.status == "active")
                .order_by(AgentExperience.global_level.desc(), AgentExperience.total_xp.desc())
                .limit(50)
            )
            result = await session.execute(query)
            rows = result.all()

        leaderboard = [
            {
                "rank": i + 1,
                "agent_id": str(r.agent_id),
                "name": r.display_name,
                "xp": r.total_xp,
                "level": r.global_level,
                "tier": r.tier,
            }
            for i, r in enumerate(rows)
        ]

        redis = await _get_redis()
        await redis.setex("asrp:leaderboard:xp", 300, json.dumps(leaderboard))
        logger.debug("xp_leaderboard_cached", entries=len(leaderboard))
    except Exception as e:
        logger.error("update_experience_leaderboards_failed", error=str(e))


# ---------------------------------------------------------------------------
# 5. Check Stale Verifications (every 30 min)
# ---------------------------------------------------------------------------

_STALE_THRESHOLD = timedelta(hours=2)

async def check_stale_verifications() -> None:
    """Mark compute jobs stuck in 'running' beyond the threshold as 'failed'."""
    from platform.infrastructure.database.models import ComputeJob

    try:
        cutoff = datetime.now(timezone.utc) - _STALE_THRESHOLD

        async with await _get_session() as session:
            stmt = (
                update(ComputeJob)
                .where(
                    ComputeJob.status == "running",
                    ComputeJob.started_at < cutoff,
                )
                .values(
                    status="failed",
                    error_message="Timed out by stale verification checker",
                    completed_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            logger.info("stale_verifications_checked", timed_out=result.rowcount)
    except Exception as e:
        logger.error("check_stale_verifications_failed", error=str(e))


# ---------------------------------------------------------------------------
# 6. Cleanup Expired Tokens (every 1 hr)
# ---------------------------------------------------------------------------

async def cleanup_expired_tokens() -> None:
    """Delete agent tokens that have expired."""
    from platform.infrastructure.database.models import AgentToken

    try:
        now = datetime.now(timezone.utc)

        async with await _get_session() as session:
            stmt = delete(AgentToken).where(
                AgentToken.expires_at.isnot(None),
                AgentToken.expires_at < now,
            )
            result = await session.execute(stmt)
            await session.commit()
            logger.info("expired_tokens_cleaned", deleted=result.rowcount)
    except Exception as e:
        logger.error("cleanup_expired_tokens_failed", error=str(e))


# ---------------------------------------------------------------------------
# 7. Check Frontier Expirations (every 1 hr)
# ---------------------------------------------------------------------------

async def check_frontier_expirations() -> None:
    """Expire research frontiers past their deadline."""
    from platform.infrastructure.database.models import ResearchFrontier

    try:
        now = datetime.now(timezone.utc)

        async with await _get_session() as session:
            stmt = (
                update(ResearchFrontier)
                .where(
                    ResearchFrontier.expires_at.isnot(None),
                    ResearchFrontier.expires_at < now,
                    ResearchFrontier.status.in_(["open", "claimed"]),
                )
                .values(
                    status="expired",
                    updated_at=now,
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            logger.info("frontier_expirations_checked", expired=result.rowcount)
    except Exception as e:
        logger.error("check_frontier_expirations_failed", error=str(e))


# ---------------------------------------------------------------------------
# 8. Cleanup Old Compute Jobs (every 6 hr)
# ---------------------------------------------------------------------------

_JOB_RETENTION = timedelta(days=30)
_TERMINAL_STATUSES = ("completed", "failed", "cancelled")

async def cleanup_old_compute_jobs() -> None:
    """Purge terminal compute jobs older than the retention period."""
    from platform.infrastructure.database.models import ComputeJob

    try:
        cutoff = datetime.now(timezone.utc) - _JOB_RETENTION

        async with await _get_session() as session:
            stmt = delete(ComputeJob).where(
                ComputeJob.created_at < cutoff,
                ComputeJob.status.in_(_TERMINAL_STATUSES),
            )
            result = await session.execute(stmt)
            await session.commit()
            logger.info("old_compute_jobs_cleaned", deleted=result.rowcount)
    except Exception as e:
        logger.error("cleanup_old_compute_jobs_failed", error=str(e))


# ---------------------------------------------------------------------------
# 9. Generate Daily Stats (every 24 hr)
# ---------------------------------------------------------------------------

async def generate_daily_stats() -> None:
    """Snapshot platform stats for the past 24 hours into Redis."""
    from platform.infrastructure.database.models import (
        Agent,
        Claim,
        ComputeJob,
        VerificationResult,
    )

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        async with await _get_session() as session:
            claims_24h = (await session.execute(
                select(func.count(Claim.id)).where(Claim.created_at >= cutoff)
            )).scalar() or 0

            verifications_24h = (await session.execute(
                select(func.count(VerificationResult.id)).where(VerificationResult.created_at >= cutoff)
            )).scalar() or 0

            active_agents = (await session.execute(
                select(func.count(Agent.id)).where(Agent.status == "active")
            )).scalar() or 0

            compute_jobs_24h = (await session.execute(
                select(func.count(ComputeJob.id)).where(ComputeJob.created_at >= cutoff)
            )).scalar() or 0

        stats = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "claims_24h": claims_24h,
            "verifications_24h": verifications_24h,
            "active_agents": active_agents,
            "compute_jobs_24h": compute_jobs_24h,
        }

        redis = await _get_redis()
        await redis.setex("asrp:stats:daily", 86400, json.dumps(stats))
        logger.info("daily_stats_generated", **stats)
    except Exception as e:
        logger.error("generate_daily_stats_failed", error=str(e))


# ---------------------------------------------------------------------------
# 10. Detect Stuck Agents (every 5 min)
# ---------------------------------------------------------------------------

async def detect_stuck_agents() -> None:
    """Delegate to AgentHealthService to find stuck agents."""
    try:
        from platform.agents.health import AgentHealthService

        async with await _get_session() as session:
            health = AgentHealthService(session)
            stuck = await health.detect_stuck_agents()
            if stuck:
                logger.warning("stuck_agents_detected", count=len(stuck))
            else:
                logger.debug("no_stuck_agents")
    except Exception as e:
        logger.error("detect_stuck_agents_failed", error=str(e))


# ---------------------------------------------------------------------------
# 11. Sprint Auto-Transition (every 10 min)
# ---------------------------------------------------------------------------

async def sprint_auto_transition() -> None:
    """Auto-transition sprints that have reached 90% of their duration."""
    from platform.infrastructure.database.models import ResearchSprint

    try:
        now = datetime.now(timezone.utc)

        async with await _get_session() as session:
            result = await session.execute(
                select(ResearchSprint).where(
                    ResearchSprint.status == "active",
                    ResearchSprint.target_end_at.isnot(None),
                )
            )
            sprints = result.scalars().all()

            transitioned = 0
            for sprint in sprints:
                if sprint.started_at and sprint.target_end_at:
                    total = (sprint.target_end_at - sprint.started_at).total_seconds()
                    elapsed = (now - sprint.started_at).total_seconds()
                    if total > 0 and (elapsed / total) >= 0.9:
                        sprint.status = "wrapping_up"
                        transitioned += 1

            if transitioned:
                await session.commit()
                logger.info("sprints_auto_transitioned", count=transitioned)
            else:
                logger.debug("no_sprints_to_transition")
    except Exception as e:
        logger.error("sprint_auto_transition_failed", error=str(e))


# ---------------------------------------------------------------------------
# 12. Challenge Scheduler Tick (every 60s)
# ---------------------------------------------------------------------------

async def challenge_scheduler_tick() -> None:
    """Advance challenge lifecycle — start pending, close expired."""
    try:
        from platform.challenges.scheduler import challenge_scheduler_tick as _tick

        async with await _get_session() as session:
            result = await _tick(session)
            await session.commit()
            logger.debug("challenge_tick", result=result)
    except Exception as e:
        logger.error("challenge_scheduler_tick_failed", error=str(e))


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "system_health_check",
    "update_reputation_aggregates",
    "update_leaderboards",
    "update_experience_leaderboards",
    "check_stale_verifications",
    "cleanup_expired_tokens",
    "check_frontier_expirations",
    "cleanup_old_compute_jobs",
    "generate_daily_stats",
    "detect_stuck_agents",
    "sprint_auto_transition",
    "challenge_scheduler_tick",
]
