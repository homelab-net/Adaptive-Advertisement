# CI Blocker Priority Report — 2026-03-26

## Executive summary

Current codebase status after the `audience_sink` fixes:

- Critical test gates are passing in this environment when run with explicit service `PYTHONPATH`.
- The previously failing integration blocker (`test_log_pii_lint` for `audience_sink`) is now resolved.
- Remaining observed failures are environment/tooling constraints (package index proxy, missing Docker binary), not code correctness regressions.

## Required vs skippable checks

The CI workflow (`.github/workflows/ci.yml`) defines all jobs as hard jobs, but from an operational risk standpoint:

### Required now (must pass before merge)

1. Contract tests (`tests/contract`)
2. Service unit tests matrix
3. Integration tests (`tests/integration`)
4. Dashboard API PostgreSQL migration test
5. Hygiene tests (`tests/test_no_hardcoded_values.py`)

Reason: these validate API compatibility, runtime behavior, data model migrations, and privacy/security gates.

### High-signal but conditionally skippable in local triage only

1. Compose smoke test

Reason: this validates container orchestration and runtime wiring, but local environments often lack Docker. In GitHub CI it should still be treated as required for release readiness.

## False-flag assessment

### Previously observed failure: `audience_sink` import/PII-lint

- **Status**: Not a false flag. It was a real defect.
- **Root cause**:
  - Relative imports failed under module-file loading used by a runtime lint test harness.
  - Privacy warning log emitted value-bearing tokens matching PII lint regex rules.
- **Fix**:
  - Absolute `dashboard_api.*` imports.
  - Generic privacy-violation warning message without sensitive tokens/values.

### Current local failures from package installs

- **Status**: False flag for code quality; environment artifact.
- **Root cause**: package index/proxy restrictions prevented dependency installs (e.g., `freezegun`) and Docker unavailable in this container.
- **Impact on production stack**: none directly; these do not imply runtime logic breakage.

## Break-the-stack risk assessment

### Critical/high risk (will break stack behavior)

- Contract/unit/integration failures: **Yes**, these indicate broken service behavior or interface mismatch.
- Dashboard API migration failures: **Yes**, DB lifecycle break risk.

### Moderate risk

- Compose smoke failures: **Potentially yes** for deployability, service wiring, health checks.

### Low risk / non-stack-breaking

- Local inability to install optional test tools due mirror/proxy restrictions.

## Path to full green CI

1. Keep the `audience_sink` fix set (already merged in this branch).
2. Execute the exact GitHub workflow on Python 3.11 runner with unrestricted package access.
3. If compose-smoke remains red, inspect failing service health endpoint logs and pin to service-level defects.
4. Gate merges on required checks listed above.

## Repro commands executed in this environment

- `PYTHONPATH=services/shared:services/audience-state:services/decision-optimizer:services/input-cv:services/player:services/creative:services/supervisor:services/dashboard-api pytest tests/contract -q`
- `PYTHONPATH=services/shared:services/audience-state:services/decision-optimizer:services/input-cv:services/player:services/creative:services/supervisor:services/dashboard-api pytest tests/integration -q`
- `PYTHONPATH=services/shared:services/audience-state:services/decision-optimizer:services/input-cv:services/player:services/creative:services/supervisor:services/dashboard-api pytest -q`

All three passed locally here after the blocker fix.
