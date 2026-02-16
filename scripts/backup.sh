#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────
#  ClawdLab Database Backup
# ──────────────────────────────────────────────

BACKUP_DIR="/home/deploy/backups"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DB_NAME="${POSTGRES_DB:-clawdlab}"
DB_USER="${POSTGRES_USER:-clawdlab}"
RETENTION_DAYS=7
LABEL="${1:-scheduled}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="clawdlab_${TIMESTAMP}_${LABEL}.sql.gz"

mkdir -p "${BACKUP_DIR}"
echo "[backup] Starting: ${FILENAME}"

docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  pg_dump -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists | gzip > "${BACKUP_DIR}/${FILENAME}"

# Verify file is not empty / corrupt (must be > 100 bytes)
FILESIZE=$(stat --printf="%s" "${BACKUP_DIR}/${FILENAME}" 2>/dev/null || stat -f%z "${BACKUP_DIR}/${FILENAME}")
if [ "${FILESIZE}" -lt 100 ]; then
    echo "[backup] ERROR: backup file too small (${FILESIZE} bytes) — likely failed"
    rm -f "${BACKUP_DIR}/${FILENAME}"
    exit 1
fi

echo "[backup] OK: ${BACKUP_DIR}/${FILENAME} (${FILESIZE} bytes)"

# Rotate old backups
find "${BACKUP_DIR}" -name "clawdlab_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
echo "[backup] Rotated backups older than ${RETENTION_DAYS} days"
