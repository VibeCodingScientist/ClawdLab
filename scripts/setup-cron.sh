#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────
#  ClawdLab Cron Setup for Automated Backups
# ──────────────────────────────────────────────

REPO_DIR="${1:-/home/deploy/ClawdLab}"
CRON_MARKER="# clawdlab-backup"

if [ ! -f "${REPO_DIR}/scripts/backup.sh" ]; then
    echo "ERROR: backup.sh not found at ${REPO_DIR}/scripts/backup.sh"
    echo "Usage: $0 [repo_directory]"
    exit 1
fi

# Check if already installed
if crontab -l 2>/dev/null | grep -q "${CRON_MARKER}"; then
    echo "[cron] Backup cron already installed — skipping"
    crontab -l | grep "${CRON_MARKER}"
    exit 0
fi

# Build the cron line — every 6 hours, source .env for DB credentials
CRON_LINE="0 */6 * * * cd ${REPO_DIR} && set -a && . .env && set +a && ./scripts/backup.sh scheduled >> /home/deploy/backups/cron.log 2>&1 ${CRON_MARKER}"

# Append to existing crontab
(crontab -l 2>/dev/null; echo "${CRON_LINE}") | crontab -

echo "[cron] Installed backup cron (every 6 hours):"
crontab -l | grep "${CRON_MARKER}"
echo ""
echo "[cron] Logs will be written to /home/deploy/backups/cron.log"
