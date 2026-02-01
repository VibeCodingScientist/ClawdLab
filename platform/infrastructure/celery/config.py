"""Celery configuration for the platform."""

import os
from datetime import timedelta
from kombu import Exchange, Queue


class CeleryConfig:
    """Celery configuration class."""

    # ===========================================
    # BROKER AND BACKEND
    # ===========================================

    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    # ===========================================
    # SERIALIZATION
    # ===========================================

    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]
    timezone = "UTC"
    enable_utc = True

    # ===========================================
    # TASK EXECUTION
    # ===========================================

    task_acks_late = True
    task_reject_on_worker_lost = True
    worker_prefetch_multiplier = 1

    # Result expiration
    result_expires = 86400  # 24 hours

    # Task time limits
    task_time_limit = 3600  # 1 hour hard limit
    task_soft_time_limit = 3300  # 55 minutes soft limit

    # Retry configuration
    task_default_retry_delay = 60  # 1 minute
    task_max_retries = 3

    # ===========================================
    # EXCHANGES
    # ===========================================

    default_exchange = Exchange("default", type="direct")
    verification_exchange = Exchange("verification", type="direct")
    priority_exchange = Exchange("priority", type="direct")
    background_exchange = Exchange("background", type="direct")

    # ===========================================
    # QUEUES
    # ===========================================

    task_queues = (
        # Default queue
        Queue("default", default_exchange, routing_key="default"),
        # Verification queues by domain
        Queue("verify.math", verification_exchange, routing_key="verify.math"),
        Queue("verify.ml", verification_exchange, routing_key="verify.ml"),
        Queue("verify.compbio", verification_exchange, routing_key="verify.compbio"),
        Queue("verify.materials", verification_exchange, routing_key="verify.materials"),
        Queue("verify.bioinfo", verification_exchange, routing_key="verify.bioinfo"),
        # GPU-specific queues
        Queue("verify.gpu.a100", verification_exchange, routing_key="verify.gpu.a100"),
        Queue("verify.gpu.h100", verification_exchange, routing_key="verify.gpu.h100"),
        # Priority queues for challenges
        Queue("priority.high", priority_exchange, routing_key="priority.high"),
        Queue("priority.critical", priority_exchange, routing_key="priority.critical"),
        # Background tasks
        Queue("background.reputation", background_exchange, routing_key="background.reputation"),
        Queue("background.knowledge", background_exchange, routing_key="background.knowledge"),
        Queue("background.cleanup", background_exchange, routing_key="background.cleanup"),
        Queue("background.sync", background_exchange, routing_key="background.sync"),
        Queue("background.notifications", background_exchange, routing_key="background.notifications"),
    )

    task_default_queue = "default"

    # ===========================================
    # TASK ROUTING
    # ===========================================

    task_routes = {
        # Verification tasks
        "verification.math.*": {"queue": "verify.math"},
        "verification.ml.*": {"queue": "verify.ml"},
        "verification.compbio.*": {"queue": "verify.compbio"},
        "verification.materials.*": {"queue": "verify.materials"},
        "verification.bioinfo.*": {"queue": "verify.bioinfo"},
        # GPU-intensive tasks
        "verification.*.gpu_required": {"queue": "verify.gpu.a100"},
        "verification.ml.train_model": {"queue": "verify.gpu.h100"},
        "verification.compbio.alphafold": {"queue": "verify.gpu.a100"},
        "verification.compbio.chai1": {"queue": "verify.gpu.a100"},
        # Priority tasks
        "challenges.*": {"queue": "priority.high"},
        "challenges.security.*": {"queue": "priority.critical"},
        # Background tasks
        "reputation.*": {"queue": "background.reputation"},
        "knowledge.*": {"queue": "background.knowledge"},
        "cleanup.*": {"queue": "background.cleanup"},
        "sync.*": {"queue": "background.sync"},
        "notifications.*": {"queue": "background.notifications"},
    }

    # ===========================================
    # RATE LIMITING
    # ===========================================

    task_annotations = {
        "verification.*": {"rate_limit": "100/m"},
        "challenges.*": {"rate_limit": "50/m"},
        "notifications.*": {"rate_limit": "1000/m"},
    }

    # ===========================================
    # BEAT SCHEDULE (Periodic Tasks)
    # ===========================================

    beat_schedule = {
        "update-reputation-aggregates": {
            "task": "reputation.update_aggregates",
            "schedule": timedelta(minutes=5),
        },
        "sync-knowledge-graph": {
            "task": "knowledge.sync_from_postgres",
            "schedule": timedelta(minutes=10),
        },
        "cleanup-expired-tokens": {
            "task": "cleanup.expired_tokens",
            "schedule": timedelta(hours=1),
        },
        "cleanup-old-compute-jobs": {
            "task": "cleanup.old_compute_jobs",
            "schedule": timedelta(hours=6),
        },
        "update-leaderboards": {
            "task": "reputation.update_leaderboards",
            "schedule": timedelta(minutes=15),
        },
        "check-stale-verifications": {
            "task": "verification.check_stale",
            "schedule": timedelta(minutes=30),
        },
        "expire-unclaimed-frontiers": {
            "task": "frontiers.check_expirations",
            "schedule": timedelta(hours=1),
        },
        "generate-daily-stats": {
            "task": "analytics.generate_daily_stats",
            "schedule": {
                "hour": 0,
                "minute": 5,
            },
        },
        "health-check": {
            "task": "system.health_check",
            "schedule": timedelta(minutes=1),
        },
        "update-experience-leaderboards": {
            "task": "experience.update_leaderboards",
            "schedule": timedelta(minutes=5),
        },
        "detect-stuck-agents": {
            "task": "agents.detect_stuck",
            "schedule": timedelta(minutes=5),
        },
        "sprint-auto-transition": {
            "task": "agents.sprint_auto_transition",
            "schedule": timedelta(minutes=10),
        },
        "challenge-scheduler-tick": {
            "task": "challenges.scheduler_tick",
            "schedule": timedelta(seconds=60),
        },
    }

    # ===========================================
    # WORKER SETTINGS
    # ===========================================

    worker_send_task_events = True
    task_send_sent_event = True

    # Concurrency
    worker_concurrency = int(os.getenv("CELERY_WORKER_CONCURRENCY", "4"))

    # Logging
    worker_hijack_root_logger = False


# Export config as module-level variables for Celery
broker_url = CeleryConfig.broker_url
result_backend = CeleryConfig.result_backend
task_serializer = CeleryConfig.task_serializer
result_serializer = CeleryConfig.result_serializer
accept_content = CeleryConfig.accept_content
timezone = CeleryConfig.timezone
enable_utc = CeleryConfig.enable_utc
task_queues = CeleryConfig.task_queues
task_routes = CeleryConfig.task_routes
task_annotations = CeleryConfig.task_annotations
beat_schedule = CeleryConfig.beat_schedule
