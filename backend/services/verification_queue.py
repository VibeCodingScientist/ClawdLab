"""Redis-backed async verification queue.

Runs as a background asyncio task (one per worker). Jobs are enqueued via
``enqueue()`` which pushes to a Redis LIST. The ``consumer_loop()`` task
pops jobs with BRPOP and runs them through the verification dispatcher,
writing results back to the DB and publishing SSE events.

Distributed semaphores (Redis INCR/DECR) ensure that at most 2 Docker-based
and 4 API-based verification jobs run concurrently across all workers.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from uuid import UUID

from backend.database import get_db_session
from backend.logging_config import get_logger
from backend.models import Task
from backend.redis import get_redis
from backend.services.activity_service import log_activity
from backend.services.reputation_service import award_reputation
from backend.services.signature_service import sign_and_append
from backend.verification.dispatcher import DOCKER_DOMAINS, dispatch_verification, get_adapter, is_docker_domain
from backend.verification.cross_cutting_runner import run_cross_cutting, merge_results

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_QUEUE_DEPTH = 20
DOCKER_SEM_LIMIT = 2
API_SEM_LIMIT = 4
JOB_TTL_SECONDS = 86400  # 24 hours
BRPOP_TIMEOUT = 2  # seconds
MAX_RETRIES = 1
SEM_SAFETY_TTL = 600  # 10 min safety expiry on semaphore keys

# Redis keys
QUEUE_KEY = "verify:queue"
SEM_DOCKER_KEY = "verify:sem:docker"
SEM_API_KEY = "verify:sem:api"

# Background task state
_consumer_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


# ---------------------------------------------------------------------------
# Helpers — distributed semaphore
# ---------------------------------------------------------------------------


def _sem_key(domain: str) -> str:
    return SEM_DOCKER_KEY if domain in DOCKER_DOMAINS else SEM_API_KEY


def _sem_limit(domain: str) -> int:
    return DOCKER_SEM_LIMIT if domain in DOCKER_DOMAINS else API_SEM_LIMIT


async def _acquire_sem(redis, domain: str) -> bool:
    key = _sem_key(domain)
    limit = _sem_limit(domain)
    count = await redis.incr(key)
    if count > limit:
        await redis.decr(key)
        return False
    await redis.expire(key, SEM_SAFETY_TTL)
    return True


async def _release_sem(redis, domain: str) -> None:
    key = _sem_key(domain)
    val = await redis.decr(key)
    # Guard against going negative (e.g. after restart)
    if val < 0:
        await redis.set(key, 0)


# ---------------------------------------------------------------------------
# Job hash helpers
# ---------------------------------------------------------------------------


def _job_key(job_id: str) -> str:
    return f"verify:{job_id}"


async def _set_job(redis, job_id: str, data: dict) -> None:
    key = _job_key(job_id)
    await redis.hset(key, mapping={k: json.dumps(v, default=str) if not isinstance(v, str) else v for k, v in data.items()})
    await redis.expire(key, JOB_TTL_SECONDS)


async def _get_job(redis, job_id: str) -> dict | None:
    key = _job_key(job_id)
    raw = await redis.hgetall(key)
    if not raw:
        return None
    result = {}
    for k, v in raw.items():
        try:
            result[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            result[k] = v
    return result


async def _update_job(redis, job_id: str, updates: dict) -> None:
    key = _job_key(job_id)
    mapping = {k: json.dumps(v, default=str) if not isinstance(v, str) else v for k, v in updates.items()}
    await redis.hset(key, mapping=mapping)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def enqueue(
    task_id: UUID,
    domain: str,
    result: dict,
    metadata: dict,
    agent_id: UUID,
    assigned_to: UUID | None,
    lab_id: UUID,
    lab_slug: str,
) -> str:
    """
    Enqueue a verification job. Returns the job_id.

    Raises:
        RuntimeError: if queue depth >= MAX_QUEUE_DEPTH
    """
    redis = get_redis()

    # Check queue depth
    depth = await redis.llen(QUEUE_KEY)
    if depth >= MAX_QUEUE_DEPTH:
        raise RuntimeError(f"Verification queue full ({depth}/{MAX_QUEUE_DEPTH})")

    job_id = f"vj-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    job_data = {
        "job_id": job_id,
        "task_id": str(task_id),
        "domain": domain,
        "result": result,
        "metadata": metadata,
        "agent_id": str(agent_id),
        "assigned_to": str(assigned_to) if assigned_to else "",
        "lab_id": str(lab_id),
        "lab_slug": lab_slug,
        "status": "pending",
        "attempt": 0,
        "queued_at": now,
        "started_at": "",
        "completed_at": "",
        "score": "",
        "badge": "",
        "passed": "",
        "errors": [],
    }

    await _set_job(redis, job_id, job_data)
    await redis.lpush(QUEUE_KEY, job_id)

    logger.info("verification_enqueued", job_id=job_id, task_id=str(task_id), domain=domain)
    return job_id


async def get_job_status(job_id: str) -> dict | None:
    """Read a job's current state from Redis."""
    redis = get_redis()
    return await _get_job(redis, job_id)


async def queue_depth() -> int:
    """Return current queue depth."""
    redis = get_redis()
    return await redis.llen(QUEUE_KEY)


async def get_semaphore_counts() -> tuple[int, int]:
    """Return (docker_count, api_count)."""
    redis = get_redis()
    docker_raw = await redis.get(SEM_DOCKER_KEY)
    api_raw = await redis.get(SEM_API_KEY)
    return int(docker_raw or 0), int(api_raw or 0)


# ---------------------------------------------------------------------------
# Job processing
# ---------------------------------------------------------------------------


async def _process_job(job_data: dict) -> None:
    """Execute verification and write results to DB."""
    job_id = job_data["job_id"]
    domain = job_data["domain"]
    task_id_str = job_data["task_id"]
    task_result = job_data["result"]
    task_metadata = job_data["metadata"]
    agent_id_str = job_data["agent_id"]
    assigned_to_str = job_data.get("assigned_to", "")
    lab_id_str = job_data["lab_id"]
    lab_slug = job_data["lab_slug"]
    attempt = int(job_data.get("attempt", 0))

    redis = get_redis()
    now = datetime.now(timezone.utc).isoformat()

    # Acquire distributed semaphore
    acquired = False
    for _ in range(30):  # wait up to 60s for a slot
        acquired = await _acquire_sem(redis, domain)
        if acquired:
            break
        await asyncio.sleep(2)

    if not acquired:
        logger.warning("verification_sem_timeout", job_id=job_id, domain=domain)
        await _update_job(redis, job_id, {"status": "failed", "errors": ["Semaphore timeout"], "completed_at": now})
        return

    try:
        await _update_job(redis, job_id, {"status": "running", "started_at": now})

        # Check if the specific adapter/claim-type needs Docker
        adapter = get_adapter(domain)
        needs_docker = is_docker_domain(domain)
        if adapter and hasattr(adapter, "requires_docker_for"):
            needs_docker = adapter.requires_docker_for(task_result)

        # Run the domain adapter
        vresult = await dispatch_verification(domain, task_result, task_metadata)

        # Run cross-cutting verifiers and merge results
        cc_results = await run_cross_cutting(task_result, task_metadata)
        if cc_results:
            vresult = merge_results(vresult, cc_results)

        completed_at = datetime.now(timezone.utc)
        completed_at_iso = completed_at.isoformat()

        # Update Redis job
        await _update_job(redis, job_id, {
            "status": "completed",
            "score": vresult.score,
            "badge": vresult.badge.value,
            "passed": vresult.passed,
            "errors": vresult.errors,
            "completed_at": completed_at_iso,
        })

        # Write to DB
        task_id = UUID(task_id_str)
        agent_id = UUID(agent_id_str)
        lab_id = UUID(lab_id_str)

        async with get_db_session() as db:
            from sqlalchemy import select
            task_row = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
            if task_row is None:
                logger.error("verification_task_not_found", job_id=job_id, task_id=task_id_str)
                return

            task_row.verification_score = vresult.score
            task_row.verification_badge = vresult.badge.value
            task_row.verification_result = {
                "passed": vresult.passed,
                "score": vresult.score,
                "badge": vresult.badge.value,
                "domain": vresult.domain,
                "details": vresult.details,
                "errors": vresult.errors,
                "warnings": vresult.warnings,
                "compute_time_seconds": vresult.compute_time_seconds,
            }
            task_row.verification_status = "completed"
            task_row.verification_started_at = datetime.fromisoformat(now)
            task_row.verification_completed_at = completed_at

            await sign_and_append(
                db, "task", task_id, "verification", agent_id,
                {"score": vresult.score, "badge": vresult.badge.value, "passed": vresult.passed, "domain": vresult.domain},
            )

            # Award vRep
            new_level = None
            assigned_to_uuid = UUID(assigned_to_str) if assigned_to_str else None
            if vresult.passed and assigned_to_uuid:
                vrep_award = vresult.score * 20
                new_level = await award_reputation(
                    db, assigned_to_uuid, "vrep", vrep_award,
                    "verification_passed", task_id=task_id, lab_id=lab_id,
                    domain=domain,
                )

            # Log activity
            badge_emoji = {"green": "\U0001f7e2", "amber": "\U0001f7e1", "red": "\U0001f534"}.get(vresult.badge.value, "")
            await log_activity(
                db, redis, lab_id, lab_slug, "task_verified",
                f"{badge_emoji} Verification {vresult.badge.value}: {task_metadata.get('title', '')} (score: {vresult.score})",
                agent_id=agent_id, task_id=task_id,
            )

            if new_level is not None:
                await log_activity(
                    db, redis, lab_id, lab_slug, "agent_level_up",
                    f"Agent reached Level {new_level}",
                    agent_id=assigned_to_uuid,
                )

            await db.commit()

        logger.info("verification_job_completed", job_id=job_id, score=vresult.score, badge=vresult.badge.value)

    except Exception as exc:
        logger.exception("verification_job_failed", job_id=job_id)
        error_msg = str(exc)
        failed_at = datetime.now(timezone.utc).isoformat()

        # Retry on transient failure
        if attempt < MAX_RETRIES and _is_transient(exc):
            logger.info("verification_job_retrying", job_id=job_id, attempt=attempt + 1)
            await _update_job(redis, job_id, {"status": "pending", "attempt": attempt + 1})
            await redis.lpush(QUEUE_KEY, job_id)
        else:
            await _update_job(redis, job_id, {
                "status": "failed",
                "errors": [error_msg],
                "completed_at": failed_at,
            })
            # Mark task as failed in DB
            try:
                async with get_db_session() as db:
                    from sqlalchemy import select
                    task_row = (await db.execute(select(Task).where(Task.id == UUID(task_id_str)))).scalar_one_or_none()
                    if task_row:
                        task_row.verification_status = "failed"
                        task_row.verification_completed_at = datetime.now(timezone.utc)
                        await db.commit()
            except Exception:
                logger.exception("verification_db_update_failed", job_id=job_id)
    finally:
        await _release_sem(redis, domain)


def _is_transient(exc: Exception) -> bool:
    """Check if an exception is likely transient (timeout, connection error)."""
    transient_types = (TimeoutError, ConnectionError, OSError)
    return isinstance(exc, transient_types)


# ---------------------------------------------------------------------------
# Consumer loop
# ---------------------------------------------------------------------------


async def consumer_loop(stop_event: asyncio.Event) -> None:
    """Background loop: pop jobs from Redis queue and process them."""
    logger.info("verification_queue_started")

    while not stop_event.is_set():
        try:
            redis = get_redis()
            # BRPOP returns (key, value) or None on timeout
            result = await redis.brpop(QUEUE_KEY, timeout=BRPOP_TIMEOUT)
            if result is None:
                continue

            _, job_id = result
            job_data = await _get_job(redis, job_id)
            if job_data is None:
                logger.warning("verification_job_expired", job_id=job_id)
                continue

            await _process_job(job_data)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("verification_consumer_error")
            await asyncio.sleep(1)

    logger.info("verification_queue_stopped")


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


async def start_queue() -> None:
    """Start the verification consumer as a background task."""
    global _consumer_task, _stop_event
    _stop_event = asyncio.Event()
    _consumer_task = asyncio.create_task(consumer_loop(_stop_event))
    logger.info("verification_queue_started")


async def stop_queue() -> None:
    """Stop the verification consumer gracefully."""
    global _consumer_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
    _consumer_task = None
    _stop_event = None
    logger.info("verification_queue_stopped")
