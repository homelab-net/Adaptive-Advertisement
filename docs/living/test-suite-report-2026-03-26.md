# Full Test Suite Report — 2026-03-26

Date run: 2026-03-26 (UTC)
Repository: `Adaptive-Advertisement`

## Commands executed

1. `pytest -q`
2. `PYTHONPATH=services/shared pytest -q tests`
3. `for d in services/audience-state/tests services/creative/tests services/dashboard-api/tests services/decision-optimizer/tests services/input-cv/tests services/player/tests services/supervisor/tests; do ...; done`

## Overall outcome

- Full suite did **not** pass in this environment.
- Multiple service and integration suites pass, but there are 3 blocking failures (1 assertion/import behavior issue + 2 missing test dependencies).

## Passing suites

- `tests` with `PYTHONPATH=services/shared`: 390 passed.
- `services/audience-state/tests`: 76 passed.
- `services/creative/tests`: 51 passed.
- `services/decision-optimizer/tests`: 105 passed.
- `services/player/tests`: 110 passed.
- `services/supervisor/tests`: 78 passed.

## Failures and likely causes

### 1) Integration failure in root `tests` suite

- Failing test:
  - `tests/integration/test_log_pii_lint.py::TestRuntimeLogPIILint::test_audience_sink_privacy_gate_logs_no_pii`
- Observed error:
  - `ImportError: attempted relative import with no known parent package`
  - Triggered while loading `services/dashboard-api/dashboard_api/audience_sink.py` via `importlib.util.spec_from_file_location` under module name `audience_sink_mod`.

#### Likely cause

The test dynamically loads `audience_sink.py` as a standalone module instead of as part of the `dashboard_api` package namespace. Since `audience_sink.py` uses relative imports (`from .config import settings`), import resolution fails without a package context.

#### Upstream effects

- Any test harness that imports package files out-of-package (file path loader + non-package module name) will be brittle against relative imports.
- Refactors that increase package-relative imports will increase breakage risk in similar tests.

#### Downstream effects

- Integration privacy-lint gate reports red even though most runtime behavior remains testable.
- CI signal quality is reduced: developers may misclassify this as an application regression rather than a test harness import-context issue.

---

### 2) Missing dependency for dashboard-api tests

- Failing suite:
  - `services/dashboard-api/tests`
- Observed error:
  - `ModuleNotFoundError: No module named 'httpx'`
  - Raised from `services/dashboard-api/tests/conftest.py` import of `ASGITransport, AsyncClient`.

#### Likely cause

The environment is missing dashboard-api test/runtime dev dependency `httpx` (or dependencies were not installed for that service profile before running pytest).

#### Upstream effects

- Environment/bootstrap scripts may not install per-service test extras consistently.
- Developer onboarding friction increases due to hidden implicit dependencies.

#### Downstream effects

- Entire dashboard-api unit/integration coverage is unavailable, including routes and DB-related validations.
- Regressions in dashboard API endpoints can ship undetected if this gap persists in CI/local validation.

---

### 3) Missing dependency for input-cv tests

- Failing suite:
  - `services/input-cv/tests`
- Observed error:
  - `ModuleNotFoundError: No module named 'freezegun'`
  - Raised during collection of `services/input-cv/tests/unit/test_health_tracker.py`.

#### Likely cause

The environment is missing `freezegun`, required by health-tracker timing tests.

#### Upstream effects

- `requirements-dev.txt` / dependency synchronization may be incomplete in the active environment.
- Time-dependent behavior tests become silently unvalidated when dev dependencies are partial.

#### Downstream effects

- Health timing/backoff or stale-status logic regressions may not be caught.
- Operational reliability signals (startup/degraded timing semantics) may drift from contract expectations.

## Notes

- Running root `pytest -q` without `PYTHONPATH=services/shared` also produced import-collection errors for `adaptive_shared`; this is an environment/path bootstrap issue.
- Dashboard UI has no configured `test` script in `services/dashboard-ui/package.json`, so no frontend automated test suite was run as part of this report.

## Suggested remediation order

1. Standardize test environment bootstrap:
   - Ensure `PYTHONPATH` includes `services/shared` (or install `adaptive_shared` as editable package).
2. Install missing per-service dev dependencies:
   - dashboard-api: include `httpx` in active test env.
   - input-cv: include `freezegun` in active test env.
3. Fix fragile integration test import strategy:
   - Load `dashboard_api.audience_sink` through package import path, or patch test to provide package context when using spec-based loading.
