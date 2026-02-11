"""Periodic background tasks.

Replaces Celery Beat scheduled tasks. Each function is a no-arg async
coroutine registered with the PeriodicScheduler in ``platform.main``.

Most tasks are still TODO stubs — they were TODO stubs in the original
Celery app.py too.  The signatures are kept so the scheduler has something
to call; real implementations can be filled in later.
"""

from __future__ import annotations

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


async def system_health_check() -> None:
    """Run platform-wide health check."""
    try:
        from platform.monitoring.service import get_monitoring_service
        monitoring = get_monitoring_service()
        status = await monitoring.get_system_status()
        logger.debug("health_check_ok", status=status.get("health", {}).get("status"))
    except Exception as e:
        logger.error("health_check_failed", error=str(e))


async def update_reputation_aggregates() -> None:
    """Recompute reputation aggregates (TODO: implement)."""
    logger.debug("periodic_update_reputation_aggregates")


async def update_leaderboards() -> None:
    """Refresh cached leaderboard rankings (TODO: implement)."""
    logger.debug("periodic_update_leaderboards")


async def update_experience_leaderboards() -> None:
    """Refresh experience/XP leaderboard rankings (TODO: implement)."""
    logger.debug("periodic_update_experience_leaderboards")


async def check_stale_verifications() -> None:
    """Find and timeout stale verification jobs (TODO: implement)."""
    logger.debug("periodic_check_stale_verifications")


async def cleanup_expired_tokens() -> None:
    """Remove expired auth tokens (TODO: implement)."""
    logger.debug("periodic_cleanup_expired_tokens")


async def check_frontier_expirations() -> None:
    """Expire unclaimed research frontiers past their deadline (TODO: implement)."""
    logger.debug("periodic_check_frontier_expirations")


async def cleanup_old_compute_jobs() -> None:
    """Purge old compute job records (TODO: implement)."""
    logger.debug("periodic_cleanup_old_compute_jobs")


async def generate_daily_stats() -> None:
    """Generate daily analytics snapshot (TODO: implement)."""
    logger.debug("periodic_generate_daily_stats")


async def detect_stuck_agents() -> None:
    """Find agents that appear stuck and flag them (TODO: implement)."""
    logger.debug("periodic_detect_stuck_agents")


async def sprint_auto_transition() -> None:
    """Auto-transition sprints that have reached their end date (TODO: implement)."""
    logger.debug("periodic_sprint_auto_transition")


async def challenge_scheduler_tick() -> None:
    """Advance challenge lifecycle — start pending, close expired (TODO: implement)."""
    logger.debug("periodic_challenge_scheduler_tick")


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
