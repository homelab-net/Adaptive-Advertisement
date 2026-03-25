#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# rollback.sh — OS-level appliance rollback to a previous pinned image set
#
# Usage:
#   ./rollback.sh <previous-image-tag>
#
# Example:
#   ./rollback.sh 20260320-stable
#
# Steps executed:
#   1. Stop the compose stack (graceful — allows player to flush state).
#   2. Pull the pinned previous images for all services.
#   3. Run alembic downgrade -1 to reverse the most recent DB migration.
#   4. Restart the stack with the previous images.
#
# Requirements:
#   - docker compose v2 (docker compose, not docker-compose)
#   - alembic installed in the dashboard-api container or virtualenv
#   - COMPOSE_FILE env var, or run from the repo root where compose.yml lives
#
# Safety:
#   - This script does NOT delete the current images — they remain cached
#     and can be re-applied with a fresh deploy.
#   - Alembic downgrade is limited to -1 (one step) to minimise data risk.
#     If you need to roll back further, run alembic downgrade manually.
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${REPO_ROOT}/docker-compose.yml}"

# ---------------------------------------------------------------------------
# Argument check
# ---------------------------------------------------------------------------
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <previous-image-tag>" >&2
    echo "  Example: $0 20260320-stable" >&2
    exit 1
fi

PREVIOUS_TAG="$1"

echo "=== Adaptive Advertisement Rollback ==="
echo "  Target tag    : ${PREVIOUS_TAG}"
echo "  Compose file  : ${COMPOSE_FILE}"
echo "  Repo root     : ${REPO_ROOT}"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Stop the compose stack
# ---------------------------------------------------------------------------
echo "[1/4] Stopping compose stack..."
docker compose -f "${COMPOSE_FILE}" down --timeout 30
echo "      Stack stopped."

# ---------------------------------------------------------------------------
# Step 2: Pull pinned previous images
# ---------------------------------------------------------------------------
echo "[2/4] Pulling previous images (tag=${PREVIOUS_TAG})..."

SERVICES=(
    "player"
    "decision-optimizer"
    "audience-state"
    "input-cv"
    "dashboard-api"
    "creative"
    "supervisor"
)

IMAGE_PREFIX="${IMAGE_PREFIX:-ghcr.io/homelab-net/adaptive-advertisement}"

for svc in "${SERVICES[@]}"; do
    image="${IMAGE_PREFIX}/${svc}:${PREVIOUS_TAG}"
    echo "      Pulling ${image} ..."
    docker pull "${image}" || {
        echo "WARNING: Could not pull ${image} — skipping (may not exist for this tag)" >&2
    }
done

echo "      Image pull complete."

# ---------------------------------------------------------------------------
# Step 3: Alembic downgrade -1 (reverse most recent migration)
# ---------------------------------------------------------------------------
echo "[3/4] Running alembic downgrade -1 ..."

# Run inside the dashboard-api container image at the previous tag
DASHBOARD_IMAGE="${IMAGE_PREFIX}/dashboard-api:${PREVIOUS_TAG}"
DB_URL="${DATABASE_URL:-postgresql+asyncpg://dashboard:dashboard@localhost:5432/dashboard}"

docker run --rm \
    --network host \
    -e "DATABASE_URL=${DB_URL}" \
    "${DASHBOARD_IMAGE}" \
    python -m alembic -c /app/alembic.ini downgrade -1 \
    || {
        echo ""
        echo "ERROR: alembic downgrade failed." >&2
        echo "  The stack has been stopped but the DB has not been downgraded." >&2
        echo "  Investigate the migration state with:" >&2
        echo "    alembic current" >&2
        echo "    alembic history" >&2
        exit 2
    }

echo "      Alembic downgrade complete."

# ---------------------------------------------------------------------------
# Step 4: Start the stack with previous images
# ---------------------------------------------------------------------------
echo "[4/4] Starting stack with previous images (tag=${PREVIOUS_TAG})..."

IMAGE_TAG="${PREVIOUS_TAG}" docker compose -f "${COMPOSE_FILE}" up -d

echo ""
echo "=== Rollback complete ==="
echo "  Running tag   : ${PREVIOUS_TAG}"
echo "  Stack status  :"
docker compose -f "${COMPOSE_FILE}" ps
