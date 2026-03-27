#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY_PATH="services/shared:services/audience-state:services/decision-optimizer:services/input-cv:services/player:services/creative:services/supervisor:services/dashboard-api"

run_check() {
  local name="$1"
  local required="$2"
  shift 2

  echo "\n== $name =="
  if "$@"; then
    echo "[PASS] $name"
    return 0
  fi

  if [[ "$required" == "required" ]]; then
    echo "[FAIL] $name (required blocker)"
    return 1
  fi

  echo "[WARN] $name (optional/high-signal but skippable in constrained env)"
  return 0
}

# Critical checks: should block merge if failing.
run_check "contract-tests" required env PYTHONPATH="$PY_PATH" pytest tests/contract -q
run_check "integration-tests" required env PYTHONPATH="$PY_PATH" pytest tests/integration -q
run_check "repo-test-suite" required env PYTHONPATH="$PY_PATH" pytest -q

# Optional in local/dev triage only (still recommended in CI infra):
if command -v docker >/dev/null 2>&1; then
  run_check "compose-smoke-config" optional docker compose config >/dev/null
else
  echo "\n== compose-smoke-config =="
  echo "[WARN] docker not found; compose smoke cannot run locally here."
fi

echo "\nCI triage run complete."
