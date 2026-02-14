#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────
#  ClawdLab Deploy / Upgrade
# ──────────────────────────────────────────────

COMPOSE_FILE="docker-compose.prod.yml"
MAX_WAIT=60

echo "============================================"
echo "  ClawdLab Deploy / Upgrade"
echo "============================================"
echo ""

# ── 1. Pre-flight checks ─────────────────────

if ! command -v docker &>/dev/null; then
    echo "ERROR: docker is not installed. Please install Docker first."
    echo "       https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo "ERROR: docker compose (v2) is not available."
    echo "       Please install the Docker Compose plugin."
    exit 1
fi

echo "[OK] docker and docker compose detected"

# ── 2. Environment file ──────────────────────

if [ ! -f .env ]; then
    echo ""
    echo "No .env file found. Creating one from .env.example ..."

    if [ -f .env.example ]; then
        cp .env.example .env
    else
        # Create a minimal .env if no example exists
        touch .env
    fi

    # Generate secure secrets
    JWT_SECRET=$(openssl rand -base64 32)
    PG_PASSWORD="clawdlab_prod_$(openssl rand -hex 8)"

    # Write or append secrets
    if grep -q "^JWT_SECRET_KEY=" .env 2>/dev/null; then
        sed -i.bak "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT_SECRET}|" .env && rm -f .env.bak
    else
        echo "JWT_SECRET_KEY=${JWT_SECRET}" >> .env
    fi

    if grep -q "^POSTGRES_PASSWORD=" .env 2>/dev/null; then
        sed -i.bak "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASSWORD}|" .env && rm -f .env.bak
    else
        echo "POSTGRES_PASSWORD=${PG_PASSWORD}" >> .env
    fi

    echo ""
    echo "[OK] .env created with generated secrets."
    echo "     Review and edit .env before continuing if needed:"
    echo "       vi .env"
    echo ""
    read -rp "Press Enter to continue (or Ctrl-C to abort) ..."
fi

echo "[OK] .env file present"

# ── 3. Pull latest code ──────────────────────

echo ""
echo "Pulling latest code from origin/main ..."
git pull origin main
echo "[OK] Code up to date"

# ── 4. Build images ──────────────────────────

echo ""
echo "Building images (pulling latest base images) ..."
docker compose -f "${COMPOSE_FILE}" build --pull
echo "[OK] Images built"

# ── 5. Start / restart services ──────────────

echo ""
echo "Starting services ..."
docker compose -f "${COMPOSE_FILE}" up -d
echo "[OK] Services started"

# ── 6. Wait for health checks ────────────────

echo ""
echo "Waiting for services to become healthy (max ${MAX_WAIT}s) ..."

elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    # Check if the api service is healthy
    api_health=$(docker compose -f "${COMPOSE_FILE}" ps --format json 2>/dev/null \
        | grep -o '"Health":"[^"]*"' \
        | head -n 1 \
        || true)

    # Fallback: check via docker compose ps text output
    if docker compose -f "${COMPOSE_FILE}" ps 2>/dev/null | grep -q "api.*healthy"; then
        echo "[OK] API service is healthy (${elapsed}s)"
        break
    fi

    sleep 3
    elapsed=$((elapsed + 3))
    printf "  ... %ds\n" "$elapsed"
done

if [ $elapsed -ge $MAX_WAIT ]; then
    echo ""
    echo "WARNING: Health check did not pass within ${MAX_WAIT}s."
    echo "         Services may still be starting. Check logs with:"
    echo "           docker compose -f ${COMPOSE_FILE} logs -f api"
fi

# ── 7. Print status ──────────────────────────

echo ""
echo "============================================"
echo "  Deployment complete"
echo "============================================"
echo ""
docker compose -f "${COMPOSE_FILE}" ps
echo ""
echo "ClawdLab is available at: http://localhost"
echo ""
echo "Useful commands:"
echo "  Logs:    docker compose -f ${COMPOSE_FILE} logs -f"
echo "  Stop:    docker compose -f ${COMPOSE_FILE} down"
echo "  Restart: docker compose -f ${COMPOSE_FILE} restart"
echo ""
