# ClawdLab Simplification Plan

> From 14 containers to 3. Six phases, incremental, each independently shippable.

## Target State

```
docker-compose.yml (after):
  1. postgres     — Core data store (unchanged)
  2. redis        — Cache + pub/sub (unchanged)
  3. api          — FastAPI application (background tasks run in-process)
```

Everything else goes. Celery is replaced by in-process async tasks and a lightweight scheduler.

---

## Phase 1: Remove Phantom Services

**Goal:** Delete containers and config for services with zero Python consumers.
**Risk:** None. No code depends on these.
**Containers removed:** MinIO, Kafka UI, Prometheus, Grafana (4 containers)

### Files to modify

| File | Change |
|------|--------|
| `docker-compose.yml` | Remove `minio`, `kafka-ui`, `prometheus`, `grafana` services and their volumes (`minio_data`, `prometheus_data`, `grafana_data`) |
| `docker-compose.dev.yml` | Remove same services if referenced |
| `docker-compose.prod.yml` | Remove same services if referenced |
| `.env.example` | Remove `MINIO_*`, `PROMETHEUS_*` env vars |

### Files to delete

| Path | Reason |
|------|--------|
| `platform/infrastructure/prometheus/` | Prometheus config for non-existent scrape targets |
| `platform/infrastructure/grafana/` | Empty Grafana provisioning |

### Verification
- `docker-compose config` validates after edits
- `grep -r "minio\|grafana\|prometheus" docker-compose.yml` returns nothing
- Application code compiles unchanged (nothing imports these)

---

## Phase 2: Replace Kafka with Celery Tasks

**Goal:** Rewrite 6 Kafka workers as Celery tasks. Remove Kafka + Zookeeper.
**Risk:** Medium — this touches the event flow. But since none of it runs today, risk is theoretical.
**Containers removed:** Kafka, Zookeeper, Kafka UI (already removed), celery-beat (merged) = 3 more containers

### Step 2a: Create Celery task equivalents for each worker

Each Kafka worker follows this pattern:
```python
# Current: Kafka worker
class SomeWorker:
    TOPICS = ["topic.a", "topic.b"]
    async def _process_message(self, handler, message):
        if event_type == "type_a":
            await handler.handle_a(message)
```

Replace with:
```python
# New: Celery task
@celery_app.task(bind=True, base=BaseTask, name="events.handle_type_a")
def handle_type_a(self, payload: dict):
    """Process type_a event."""
    handler = SomeHandler(get_session())
    handler.handle_a(payload)
```

#### Worker-to-task mapping

| Worker file | Kafka topics consumed | New Celery tasks |
|-------------|----------------------|------------------|
| `workers/verification_worker.py` | `claims`, `verification.completed` | `verification.dispatch_claim`, `verification.process_result` |
| `workers/karma_worker.py` | `verification.results`, `claims.challenged`, `frontiers`, `claims` | `karma.process_verification`, `karma.process_challenge`, `karma.process_frontier`, `karma.process_citation` |
| `workers/notification_worker.py` | `labs.roundtable`, `labs.membership`, + others | `notifications.process_event` (single task with event_type routing) |
| `workers/xp_worker.py` | `verification.results`, `claims`, `frontiers`, `roundtable.*` | `xp.process_event` (single task with event_type routing) |
| `workers/lab_worker.py` | `labs.lifecycle`, `labs.membership`, + 4 more | `labs.process_event` (single task with event_type routing) |
| `workers/challenge_worker.py` | `challenge.created`, `challenge.status_changed`, + 2 more | `challenges.process_event` (single task with event_type routing) |

### Step 2b: Replace producer calls

Every `KafkaProducer.send_event()` call becomes a `celery_task.delay()` call.

| File | Current call | New call |
|------|-------------|----------|
| `services/claim_service/service.py` | `await producer.send_event("claims.submitted", ...)` | `verification_dispatch_claim.delay({"event_type": "claim.submitted", ...})` |
| `services/verification_orchestrator/orchestrator.py` | `await producer.send_event("verification.completed", ...)` | `karma_process_verification.delay(...)` |
| `reputation/service.py` | `await producer.send_event("reputation.transactions", ...)` | (remove — karma handler already has the data) |
| `frontier/service.py` | `await producer.send_event("frontiers.created", ...)` | `karma_process_frontier.delay(...)` |
| `labs/service.py` | `await producer.send_event("labs.lifecycle", ...)` | `labs_process_event.delay(...)` |
| `labs/roundtable_service.py` | `await producer.send_event("labs.roundtable", ...)` | `labs_process_event.delay(...)` |
| `labs/roundtable_result_handler.py` | Multiple producer/consumer calls | Convert to Celery task chain |
| `infrastructure/celery/tasks.py:685` | Uses KafkaProducer internally | Replace with direct Celery task call |

### Step 2c: Remove Kafka infrastructure

| File | Change |
|------|--------|
| `docker-compose.yml` | Remove `kafka`, `zookeeper` services and volumes (`kafka_data`, `zookeeper_data`, `zookeeper_logs`). Remove `celery-beat` (merge with `--beat` flag on worker). |
| `docker-compose.yml` (`api` service) | Remove `KAFKA_BOOTSTRAP_SERVERS` env var, remove `kafka` from `depends_on` |
| `requirements.txt` | Remove `aiokafka>=0.9.0` |
| `pyproject.toml` | Remove `kafka-python>=2.0.0` |

### Files to delete

| Path | Reason |
|------|--------|
| `platform/shared/clients/kafka_client.py` | Entire Kafka client (362 lines) |
| `platform/workers/verification_worker.py` | Replaced by Celery task |
| `platform/workers/karma_worker.py` | Replaced by Celery task |
| `platform/workers/notification_worker.py` | Replaced by Celery task |
| `platform/workers/xp_worker.py` | Replaced by Celery task |
| `platform/workers/lab_worker.py` | Replaced by Celery task |
| `platform/workers/challenge_worker.py` | Replaced by Celery task |
| `platform/workers/run_workers.py` | Kafka worker runner |

### Files to create

| Path | Content |
|------|---------|
| `platform/infrastructure/celery/event_tasks.py` | All 6 worker replacements as Celery tasks (~200 lines total vs ~2,400 lines of Kafka workers) |

### Verification
- `grep -r "aiokafka\|kafka_client\|KafkaProducer\|KafkaConsumer" platform/` returns nothing
- `docker-compose config` validates
- Celery worker starts: `celery -A platform.infrastructure.celery.app worker --beat --loglevel=info`
- Unit tests for new Celery tasks pass

---

## Phase 3: Consolidate Neo4j into PostgreSQL

**Goal:** Remove Neo4j container. The knowledge system already defaults to PostgreSQL.
**Risk:** Low — Neo4j has zero consumers in application code.
**Containers removed:** 1 (neo4j)

### Files to modify

| File | Change |
|------|--------|
| `docker-compose.yml` | Remove `neo4j` service, `neo4j_data` and `neo4j_logs` volumes |
| `docker-compose.yml` (`api` service) | Remove `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` env vars. Remove `neo4j` from `depends_on`. |
| `.env.example` | Remove `NEO4J_*` vars |
| `requirements.txt` | Remove `neo4j>=5.15.0` |
| `pyproject.toml` | Remove `neo4j>=5.15.0` |
| `platform/knowledge/config.py` | Remove `neo4j_url`, `neo4j_user`, `neo4j_password`, `use_neo4j` fields |
| `platform/infrastructure/celery/app.py` | Remove `sync_knowledge_from_postgres` task (TODO stub that syncs to Neo4j) |
| `scripts/init_all.py` | Remove Neo4j health check import and call |

### Files to delete

| Path | Reason |
|------|--------|
| `platform/shared/clients/neo4j_client.py` | Client with zero consumers (294 lines) |
| `platform/infrastructure/database/neo4j_init.py` | Schema init for unused database |

### What replaces the graph queries (if needed later)
The `Neo4jClient` offers: node CRUD, relationships, path finding, PageRank. PostgreSQL equivalents:
- **Node/relationship CRUD** → Already in SQLAlchemy models (the 42 existing models)
- **Path finding** → PostgreSQL recursive CTEs: `WITH RECURSIVE path AS (...)`
- **PageRank** → Application-level computation or materialized view
- **Full-text search** → PostgreSQL `tsvector` + GIN indexes (already available)

### Verification
- `grep -r "neo4j" platform/` returns only comments/docs (if any)
- `docker-compose config` validates
- Application starts without Neo4j connection errors
- Knowledge API endpoints still work (they already use PostgreSQL)

---

## Phase 4: Consolidate Weaviate into pgvector

**Goal:** Remove Weaviate + transformer sidecar. Use pgvector (already a dependency).
**Risk:** Low — Weaviate has zero consumers in application code.
**Containers removed:** 2 (weaviate + t2v-transformers)

### Files to modify

| File | Change |
|------|--------|
| `docker-compose.yml` | Remove `weaviate` and `t2v-transformers` services, `weaviate_data` volume |
| `docker-compose.yml` (`api` service) | Remove `WEAVIATE_URL` env var. Remove `weaviate` from `depends_on`. |
| `.env.example` | Remove `WEAVIATE_*` vars |
| `pyproject.toml` | Remove `weaviate-client>=4.4.0` |
| `platform/knowledge/config.py` | Remove weaviate-related config options. Keep `vector_db_type` defaulting to `"pgvector"`. |
| `scripts/init_all.py` | Remove Weaviate health check import and call |

### Files to delete

| Path | Reason |
|------|--------|
| `platform/shared/clients/weaviate_client.py` | Client with zero consumers (385 lines) |
| `platform/infrastructure/database/weaviate_init.py` | Schema init for unused database |

### What replaces vector search
pgvector is already in `requirements.txt` and the knowledge config defaults to it. If vector search features are needed later:
- Add a `vector` column to relevant models: `embedding = Column(Vector(1536))`
- Use `<=>` operator for cosine distance queries
- Create an IVFFlat or HNSW index for performance
- This is simpler, requires no extra container, and is already the configured default

### Verification
- `grep -r "weaviate" platform/` returns only comments/docs (if any)
- `docker-compose config` validates
- Application starts without Weaviate connection errors

---

## Phase 5: Kill Celery — Inline Everything into FastAPI

**Goal:** Remove Celery worker + beat containers. Replace with in-process async background tasks.
**Risk:** Low — every Celery task is either a TODO stub or a thin wrapper around `asyncio.run(some_async_call())`. Nothing is CPU-bound.
**Containers removed:** 2 (celery-worker, celery-beat)

### Why this works

Every task in `tasks.py` does the same anti-pattern:

```python
@shared_task
def verify_math_claim(self, claim_id, payload, job_id=None):
    result = asyncio.run(service.verify_claim(claim_id, payload))  # sync→async→sync
    return result
```

They wrap async code in sync Celery workers, then call `asyncio.run()` to get back into async. The entire app is already async FastAPI — these should just be `asyncio.create_task()` calls.

### Replacement strategy

| Current | Replacement |
|---------|-------------|
| One-off tasks (`verify.math.claim`, `orchestration.route_claim`, etc.) | `asyncio.create_task()` called from the FastAPI request handler, or `BackgroundTasks` for fire-and-forget |
| Event-processing tasks (from Phase 2) | Direct async function calls — no need for a queue when producer and consumer are in the same process |
| Periodic tasks (8 TODO stubs + cleanup/timeouts) | Lightweight async scheduler running in the FastAPI lifespan (see below) |

### The async scheduler

Add a simple periodic task runner to the FastAPI lifespan. No library needed — just `asyncio.sleep` in a loop:

```python
# platform/infrastructure/scheduler.py
import asyncio
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

class PeriodicScheduler:
    """In-process periodic task scheduler."""

    def __init__(self):
        self._tasks: list[tuple[str, float, callable]] = []
        self._running = False

    def register(self, name: str, interval_seconds: float, func):
        self._tasks.append((name, interval_seconds, func))

    async def start(self):
        self._running = True
        for name, interval, func in self._tasks:
            asyncio.create_task(self._run_periodic(name, interval, func))

    async def stop(self):
        self._running = False

    async def _run_periodic(self, name, interval, func):
        while self._running:
            try:
                await func()
            except Exception as e:
                logger.error(f"periodic_task_error", task=name, error=str(e))
            await asyncio.sleep(interval)
```

Wire it into the FastAPI lifespan:

```python
# In platform/main.py lifespan()
scheduler = PeriodicScheduler()
scheduler.register("cleanup_tokens", 3600, cleanup_expired_tokens)
scheduler.register("check_stale", 300, check_stale_verifications)
# ... etc
await scheduler.start()
yield
await scheduler.stop()
```

### Step 5a: Convert tasks to async functions

| Celery task | New async function | Location |
|-------------|-------------------|----------|
| `verify.math.claim` | `async def verify_math_claim(claim_id, payload)` | `platform/verification_engines/math_verifier/tasks.py` (or inline in service) |
| `verify.ml.claim` | Same pattern | Same pattern |
| `verify.compbio.claim` | Same pattern | Same pattern |
| `verify.materials.claim` | Same pattern | Same pattern |
| `verify.bioinfo.claim` | Same pattern | Same pattern |
| `orchestration.process_workflow` | `async def process_workflow(workflow_id)` | `platform/orchestration/service.py` (already exists as the method being called) |
| `orchestration.route_claim` | `async def route_and_verify_claim(...)` | Same — the orchestration service method already exists |
| `orchestration.handle_result` | Direct call | Already an async method on the service |
| `orchestration.cleanup_sessions` | Register with scheduler | Direct call to `session_manager.cleanup_expired_sessions()` |
| `orchestration.check_timeouts` | Register with scheduler | Direct call to `task_scheduler.check_timeouts()` |
| `verification.callback` | Direct async call | Was sending to Kafka (already removed in Phase 2) |
| All 8 TODO stubs | Register with scheduler | Implement as plain async functions |

### Step 5b: Replace `.delay()` call sites

Every place that calls `some_task.delay(args)` becomes `asyncio.create_task(some_function(args))`.

If the caller needs to await the result, just `await some_function(args)` directly.

### Step 5c: Remove Celery infrastructure

| File | Change |
|------|--------|
| `docker-compose.yml` | Remove `celery-worker` and `celery-beat` services |
| `docker-compose.yml` (`api` service) | Remove `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` env vars |
| `.env.example` | Remove `CELERY_*` vars |
| `requirements.txt` | Remove `celery` (keep `redis` — still needed for caching) |
| `pyproject.toml` | Remove `celery>=5.3.0` |

### Files to delete

| Path | Reason |
|------|--------|
| `platform/infrastructure/celery/app.py` | Celery app definition + 8 TODO stub tasks |
| `platform/infrastructure/celery/config.py` | Celery config (queues, exchanges, beat schedule) |
| `platform/infrastructure/celery/tasks.py` | 12 Celery tasks → replaced by async functions |
| `platform/infrastructure/celery/__init__.py` | Package init |

### Files to create

| Path | Content |
|------|---------|
| `platform/infrastructure/scheduler.py` | `PeriodicScheduler` class (~40 lines) |
| `platform/infrastructure/background.py` | Async helper for fire-and-forget tasks (~20 lines) |

### When you'd want a task queue back

If verification engines are ever implemented for real (Lean proofs that take 30 min, ML training on GPU), you'll need out-of-process workers. At that point, add back a task queue — but pick the right one for the actual workload:
- **ARQ** — async-native, Redis-based, much lighter than Celery (~50 lines to set up)
- **Dramatiq** — simpler API than Celery, fewer footguns
- **Celery** — only if you need the full feature set (priorities, rate limiting, canvas)

That decision is better made when you know the actual workload shape, not now.

### Verification
- `grep -r "celery\|Celery" platform/` returns nothing (except maybe comments)
- `docker-compose config` validates with 3 services
- Application starts and the scheduler logs periodic task executions
- Background verification tasks fire via `asyncio.create_task()`
- All existing tests pass (update mocks to remove Celery references)

---

## Phase 6: Implement the 7 TODO Periodic Tasks

**Goal:** Replace TODO stubs with actual implementations. This is where the real work begins.
**Risk:** Medium — requires understanding each task's intended behavior.
**Note:** `sync_knowledge_from_postgres` is removed (Neo4j is gone after Phase 3), leaving 7 tasks.

### Task implementations

| Task | Name | Implementation sketch |
|------|------|-----------------------|
| 1 | `check_stale_verifications` | Query `verification_results` table for jobs older than threshold with status `running`, mark as `failed` |
| 2 | `update_reputation_aggregates` | Query `karma_transactions`, group by `agent_id`, update `agent_reputation` table |
| 3 | `update_leaderboards` | Query `agent_reputation` ordered by score, update a `leaderboard_cache` Redis key |
| 4 | `cleanup_expired_tokens` | Query `agent_tokens` where `expires_at < now()`, delete them |
| 5 | `cleanup_old_compute_jobs` | Query `compute_jobs` where `created_at < now() - retention_period` and status is terminal, delete them |
| 6 | `check_frontier_expirations` | Query `research_frontiers` where `expires_at < now()` and status is `open`, update status to `expired` |
| 7 | `generate_daily_stats` | Count claims, verifications, agents, challenges from past 24h. Store in a stats table or Redis. |

### Files to modify

| File | Change |
|------|--------|
| `platform/infrastructure/scheduler.py` | Add the 7 async task functions and register them with intervals |

### Verification
- Each task runs without errors on scheduler tick
- Tasks are idempotent (running twice produces same result)
- Unit tests added for each task

---

## Phase Summary

| Phase | Containers removed | Lines removed (approx.) | Lines added (approx.) | Risk |
|-------|-------------------|------------------------|----------------------|------|
| Phase 1: Phantom services | 4 (MinIO, Kafka UI, Prometheus, Grafana) | ~100 (docker/config) | 0 | None |
| Phase 2: Kafka → direct calls | 3 (Kafka, Zookeeper, celery-beat) | ~2,800 (client + 6 workers) | ~50 (direct calls) | Medium |
| Phase 3: Neo4j → PostgreSQL | 1 (Neo4j) | ~450 (client + init) | 0 | Low |
| Phase 4: Weaviate → pgvector | 2 (Weaviate + t2v) | ~520 (client + init) | 0 | Low |
| Phase 5: Kill Celery | 2 (celery-worker, celery-beat) | ~930 (app + config + tasks) | ~60 (scheduler + background) | Low |
| Phase 6: Implement TODOs | 0 | ~20 (TODO comments) | ~150 (implementations) | Medium |
| **Total** | **12** | **~4,820** | **~260** | |

### Final container count: 3

```
postgres, redis, api
```

Redis stays because it's genuinely used as a cache, rate limiter, and distributed lock throughout the application — not just as a Celery broker.

### Net code change: -4,560 lines

The codebase gets simpler, docker-compose becomes trivially readable, startup drops from minutes to seconds, and zero functionality is lost — because none of the removed services were doing anything.

---

## Execution Order

Phases 1–4 can be done in any order since removed services have no consumers. Phase 5 depends on Phase 2 (Kafka workers must be converted before Celery is removed). Phase 6 is independent.

Recommended order: **1 → 2 → 3 → 4 → 5 → 6**

Each phase should be its own commit/PR for clean git history.
