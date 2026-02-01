"""Celery application instance."""

from celery import Celery

from platform.infrastructure.celery import config

# Create Celery app
celery_app = Celery("asrp")

# Load configuration from config module
celery_app.config_from_object(config)

# Auto-discover tasks from all verification engines and services
celery_app.autodiscover_tasks([
    "platform.verification_engines.math_verifier",
    "platform.verification_engines.ml_verifier",
    "platform.verification_engines.compbio_verifier",
    "platform.verification_engines.materials_verifier",
    "platform.verification_engines.bioinfo_verifier",
    "platform.services.reputation_service",
    "platform.services.knowledge_graph_service",
    "platform.services.notification_service",
])


# ===========================================
# BASE TASK CLASS
# ===========================================


class BaseTask(celery_app.Task):
    """Base task class with common functionality."""

    abstract = True
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        from platform.shared.utils.logging import get_logger

        logger = get_logger(__name__)
        logger.error(
            "celery_task_failed",
            task_name=self.name,
            task_id=task_id,
            error=str(exc),
            args=args,
            kwargs=kwargs,
        )

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        from platform.shared.utils.logging import get_logger

        logger = get_logger(__name__)
        logger.info(
            "celery_task_succeeded",
            task_name=self.name,
            task_id=task_id,
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        from platform.shared.utils.logging import get_logger

        logger = get_logger(__name__)
        logger.warning(
            "celery_task_retry",
            task_name=self.name,
            task_id=task_id,
            error=str(exc),
            retry_count=self.request.retries,
        )


# ===========================================
# SYSTEM TASKS
# ===========================================


@celery_app.task(bind=True, base=BaseTask, name="system.health_check")
def system_health_check(self):
    """Periodic health check task."""
    from platform.shared.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.debug("system_health_check_running")
    return {"status": "healthy"}


# ===========================================
# VERIFICATION TASKS (Stubs)
# ===========================================


@celery_app.task(bind=True, base=BaseTask, name="verification.check_stale")
def check_stale_verifications(self):
    """Check for stale verification jobs."""
    from platform.shared.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info("checking_stale_verifications")
    # TODO: Implement stale verification check
    return {"checked": 0, "requeued": 0}


# ===========================================
# REPUTATION TASKS (Stubs)
# ===========================================


@celery_app.task(bind=True, base=BaseTask, name="reputation.update_aggregates")
def update_reputation_aggregates(self):
    """Update reputation aggregate statistics."""
    from platform.shared.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info("updating_reputation_aggregates")
    # TODO: Implement reputation aggregate update
    return {"updated": 0}


@celery_app.task(bind=True, base=BaseTask, name="reputation.update_leaderboards")
def update_leaderboards(self):
    """Update global and domain leaderboards."""
    from platform.shared.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info("updating_leaderboards")
    # TODO: Implement leaderboard update
    return {"updated": 0}


# ===========================================
# KNOWLEDGE GRAPH TASKS (Stubs)
# ===========================================


@celery_app.task(bind=True, base=BaseTask, name="knowledge.sync_from_postgres")
def sync_knowledge_from_postgres(self):
    """Sync knowledge graph from PostgreSQL."""
    from platform.shared.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info("syncing_knowledge_graph")
    # TODO: Implement PostgreSQL to Neo4j sync
    return {"synced": 0}


# ===========================================
# CLEANUP TASKS (Stubs)
# ===========================================


@celery_app.task(bind=True, base=BaseTask, name="cleanup.expired_tokens")
def cleanup_expired_tokens(self):
    """Clean up expired authentication tokens."""
    from platform.shared.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info("cleaning_expired_tokens")
    # TODO: Implement token cleanup
    return {"deleted": 0}


@celery_app.task(bind=True, base=BaseTask, name="cleanup.old_compute_jobs")
def cleanup_old_compute_jobs(self):
    """Clean up old compute job records."""
    from platform.shared.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info("cleaning_old_compute_jobs")
    # TODO: Implement compute job cleanup
    return {"deleted": 0}


# ===========================================
# FRONTIER TASKS (Stubs)
# ===========================================


@celery_app.task(bind=True, base=BaseTask, name="frontiers.check_expirations")
def check_frontier_expirations(self):
    """Check and expire unclaimed frontiers."""
    from platform.shared.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info("checking_frontier_expirations")
    # TODO: Implement frontier expiration check
    return {"expired": 0}


# ===========================================
# ANALYTICS TASKS (Stubs)
# ===========================================


@celery_app.task(bind=True, base=BaseTask, name="analytics.generate_daily_stats")
def generate_daily_stats(self):
    """Generate daily platform statistics."""
    from platform.shared.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info("generating_daily_stats")
    # TODO: Implement daily stats generation
    return {"generated": True}
