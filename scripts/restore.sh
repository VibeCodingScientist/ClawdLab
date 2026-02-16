#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────
#  ClawdLab Database Restore
# ──────────────────────────────────────────────

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DB_NAME="${POSTGRES_DB:-clawdlab}"
DB_USER="${POSTGRES_USER:-clawdlab}"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    ls -lh /home/deploy/backups/clawdlab_*.sql.gz 2>/dev/null || echo "  (none found)"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: File not found: ${BACKUP_FILE}"
    exit 1
fi

echo "============================================"
echo "  ClawdLab Database Restore"
echo "============================================"
echo ""
echo "Backup file: ${BACKUP_FILE}"
echo "Database:    ${DB_NAME}"
echo ""
echo "WARNING: This will REPLACE all data in the database."
echo ""
read -rp "Type 'yes' to confirm: " CONFIRM

if [ "${CONFIRM}" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# Take a safety backup before restoring
echo ""
echo "[restore] Taking safety backup before restore..."
./scripts/backup.sh pre-restore

# Stop the API to prevent writes during restore
echo "[restore] Stopping API service..."
docker compose -f "${COMPOSE_FILE}" stop api

# Restore from backup
echo "[restore] Restoring from ${BACKUP_FILE}..."
gunzip -c "${BACKUP_FILE}" | docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  psql -U "${DB_USER}" -d "${DB_NAME}" --single-transaction -q

echo "[restore] Database restored successfully"

# Restart API (entrypoint runs alembic upgrade head automatically)
echo "[restore] Restarting API service..."
docker compose -f "${COMPOSE_FILE}" start api

echo ""
echo "[restore] Done. API is restarting — check logs with:"
echo "  docker compose -f ${COMPOSE_FILE} logs -f api"
