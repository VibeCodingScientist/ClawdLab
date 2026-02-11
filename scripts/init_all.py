#!/usr/bin/env python3
"""
Initialize all platform infrastructure.

This script initializes:
1. PostgreSQL schema (via Alembic migrations)
2. Neo4j schema (constraints and indexes)
3. Weaviate schema (collections)
4. Seed data

Usage:
    python scripts/init_all.py
    python scripts/init_all.py --skip-seed
    python scripts/init_all.py --reset  # WARNING: Destroys all data!
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

# Add platform to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from platform.shared.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def run_alembic_migrations() -> bool:
    """Run Alembic database migrations."""
    logger.info("running_alembic_migrations")
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=Path(__file__).parent.parent / "platform" / "infrastructure" / "database",
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error("alembic_migration_failed", stderr=result.stderr)
            return False
        logger.info("alembic_migrations_complete")
        return True
    except FileNotFoundError:
        logger.warning("alembic_not_found_skipping")
        return True


async def init_neo4j() -> bool:
    """Initialize Neo4j schema."""
    logger.info("initializing_neo4j")
    try:
        from platform.infrastructure.database.neo4j_init import (
            initialize_neo4j_schema,
            verify_neo4j_schema,
        )
        from platform.shared.clients.neo4j_client import close_driver

        await initialize_neo4j_schema()
        status = await verify_neo4j_schema()
        await close_driver()

        logger.info("neo4j_initialized", **status)
        return status["status"] == "healthy"
    except Exception as e:
        logger.error("neo4j_init_failed", error=str(e))
        return False


def init_weaviate() -> bool:
    """Initialize Weaviate schema."""
    logger.info("initializing_weaviate")
    try:
        from platform.infrastructure.database.weaviate_init import (
            initialize_weaviate_schema,
            verify_weaviate_schema,
        )
        from platform.shared.clients.weaviate_client import close_client

        initialize_weaviate_schema()
        status = verify_weaviate_schema()
        close_client()

        logger.info("weaviate_initialized", **status)
        return status["status"] == "healthy"
    except Exception as e:
        logger.error("weaviate_init_failed", error=str(e))
        return False


async def seed_database() -> bool:
    """Seed the database with initial data."""
    logger.info("seeding_database")
    try:
        from platform.infrastructure.database.seed_data import (
            seed_system_agent,
            seed_frontiers,
            verify_seed_data,
        )
        from platform.infrastructure.database.session import init_db, close_db

        await init_db()
        await seed_system_agent()
        await seed_frontiers()
        status = await verify_seed_data()
        await close_db()

        logger.info("database_seeded", **status)
        return status["status"] == "healthy"
    except Exception as e:
        logger.error("seed_failed", error=str(e))
        return False


async def health_check() -> dict:
    """Check health of all services."""
    from platform.shared.clients.redis_client import health_check as redis_health
    from platform.shared.clients.neo4j_client import health_check as neo4j_health
    from platform.shared.clients.weaviate_client import health_check as weaviate_health

    results = {
        "redis": await redis_health(),
        "neo4j": await neo4j_health(),
        "weaviate": weaviate_health(),
    }

    return results


async def main(skip_seed: bool = False, reset: bool = False) -> int:
    """Main initialization function."""
    configure_logging(level="INFO", json_format=False)

    logger.info("platform_initialization_starting")

    if reset:
        logger.warning("reset_mode_enabled_this_will_destroy_data")
        # TODO: Implement reset logic
        logger.error("reset_not_implemented")
        return 1

    # Check service health first
    logger.info("checking_service_health")
    health = await health_check()
    logger.info("health_check_results", **health)

    unhealthy = [k for k, v in health.items() if not v]
    if unhealthy:
        logger.error("unhealthy_services", services=unhealthy)
        logger.info("hint_start_services_with_docker_compose_up")
        return 1

    # Initialize all components
    results = {}

    # PostgreSQL
    results["postgres"] = await run_alembic_migrations()

    # Neo4j
    results["neo4j"] = await init_neo4j()

    # Weaviate
    results["weaviate"] = init_weaviate()

    # Seed data
    if not skip_seed:
        results["seed"] = await seed_database()
    else:
        logger.info("skipping_seed_data")
        results["seed"] = True

    # Summary
    logger.info("initialization_results", **results)

    failed = [k for k, v in results.items() if not v]
    if failed:
        logger.error("initialization_failed", failed_components=failed)
        return 1

    logger.info("platform_initialization_complete")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize platform infrastructure")
    parser.add_argument("--skip-seed", action="store_true", help="Skip seeding database")
    parser.add_argument("--reset", action="store_true", help="Reset all data (DANGEROUS)")
    args = parser.parse_args()

    exit_code = asyncio.run(main(skip_seed=args.skip_seed, reset=args.reset))
    sys.exit(exit_code)
