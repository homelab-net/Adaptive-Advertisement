#!/usr/bin/env bash
# preflight-hardware.sh — fail-fast checks before Jetson hardware deployment
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE_BASE="${COMPOSE_BASE:-docker-compose.yml}"
COMPOSE_HW="${COMPOSE_HW:-docker-compose.hardware.yml}"
ENV_FILE="${ENV_FILE:-.env.hardware}"

ok() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*"; }
fail() { echo "[FAIL] $*"; exit 1; }

check_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || fail "required command missing: $cmd"
  ok "command present: $cmd"
}

echo "=== Adaptive Advertisement hardware preflight ==="
echo "repo: ${ROOT_DIR}"
echo "base compose: ${COMPOSE_BASE}"
echo "hardware override: ${COMPOSE_HW}"
echo "env file: ${ENV_FILE}"

check_cmd docker
check_cmd curl

[[ -f "${COMPOSE_BASE}" ]] || fail "missing ${COMPOSE_BASE}"
[[ -f "${COMPOSE_HW}" ]] || fail "missing ${COMPOSE_HW}"
ok "compose files found"

if [[ -f "${ENV_FILE}" ]]; then
  ok "env file found: ${ENV_FILE}"
else
  warn "env file missing: ${ENV_FILE} (copy .env.hardware.example to ${ENV_FILE})"
fi

if [[ -c /dev/video0 ]]; then
  ok "camera device present: /dev/video0"
else
  fail "camera device not found: /dev/video0"
fi

if docker info >/dev/null 2>&1; then
  ok "docker daemon reachable"
else
  fail "docker daemon not reachable"
fi

if docker compose -f "${COMPOSE_BASE}" -f "${COMPOSE_HW}" config >/dev/null; then
  ok "docker compose config resolved"
else
  fail "docker compose config failed"
fi

FREE_GB="$(df -BG / | awk 'NR==2 {gsub("G","",$4); print $4}')"
if [[ -n "${FREE_GB}" && "${FREE_GB}" -ge 20 ]]; then
  ok "disk free on / is ${FREE_GB}G (>=20G)"
else
  fail "insufficient disk free on / (need >=20G)"
fi

if systemctl is-active --quiet wg-quick@wg0; then
  ok "WireGuard interface is active (wg0)"
else
  warn "WireGuard wg0 is not active (acceptable for lab, not for production)"
fi

echo "=== Preflight complete ==="
