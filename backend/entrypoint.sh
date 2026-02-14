#!/bin/bash
set -e

echo "=== ClawdLab API — Entrypoint ==="

# Wait for Postgres to be ready (belt-and-suspenders alongside healthcheck)
echo "Waiting for database..."
for i in $(seq 1 30); do
    if python -c "
import asyncio, asyncpg, os
async def check():
    url = os.environ.get('DATABASE_URL', '').replace('+asyncpg', '')
    conn = await asyncpg.connect(url)
    await conn.close()
asyncio.run(check())
" 2>/dev/null; then
        echo "Database is ready."
        break
    fi
    echo "  Attempt $i/30 — waiting 2s..."
    sleep 2
done

# Run Alembic migrations
echo "Running database migrations..."
cd /app
alembic -c backend/alembic.ini upgrade head
echo "Migrations complete."

# Execute the CMD (uvicorn)
echo "Starting application..."
exec "$@"
