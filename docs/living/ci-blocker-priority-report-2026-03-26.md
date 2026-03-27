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

## Why this used to pass, then regressed after dashboard integrations

Short answer: both the **test surface area** and the **dashboard runtime code paths** changed quickly across 2026-03-24 → 2026-03-25.

Timeline summary:

1. `2026-03-24` established the earlier "green anchor" period and introduced CI layers in phases (contract, integration/privacy, hygiene, compose smoke).
2. `2026-03-25` added dashboard analytics sinks and new runtime-lint coverage for those sinks (`audience_sink` included).
3. That same feature wave introduced two defects in the new path:
   - import semantics incompatible with module-file loading in the lint harness
   - privacy log tokens/value detail tripping the runtime PII patterns
4. Result: historical runs could be green before this code path existed, while newer runs failed once both the new feature and stricter runtime-lint checks were active.

This pattern is a real regression from feature expansion + stricter test coverage, not random CI flakiness.

## Critical/high-priority closure tasks (actionable)

### P0 (must be green to avoid runtime or policy break)

1. Keep required CI gates hard-blocking on merge:
   - contract tests
   - unit matrix
   - integration tests
   - dashboard migration tests
   - hygiene tests
2. Ensure `dashboard-api` sinks remain privacy-safe under runtime lint (already fixed for `audience_sink`; keep as regression guard).

### P1 (close quickly; deployment risk)

1. Compose smoke must pass in real CI runners (Docker-enabled); treat local Docker absence as non-code warning only.
2. Add release checklist item: when dashboard features add sink/background tasks, run integration + runtime-lint subset before merge.

## Repro commands executed in this environment

- `PYTHONPATH=services/shared:services/audience-state:services/decision-optimizer:services/input-cv:services/player:services/creative:services/supervisor:services/dashboard-api pytest tests/contract -q`
- `PYTHONPATH=services/shared:services/audience-state:services/decision-optimizer:services/input-cv:services/player:services/creative:services/supervisor:services/dashboard-api pytest tests/integration -q`
- `PYTHONPATH=services/shared:services/audience-state:services/decision-optimizer:services/input-cv:services/player:services/creative:services/supervisor:services/dashboard-api pytest -q`

All three passed locally here after the blocker fix.
