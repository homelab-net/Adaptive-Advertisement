# CI Health Delta Analysis — 2026-03-26

## Scope and limitations

- Repository analyzed: local branch `work` only.
- `git show-ref` exposes no additional local/remote branches in this clone, so "all branches" in this environment resolves to one branch.
- CI-equivalent package installation for Python 3.11 could not be fully reproduced due package index/proxy restrictions in this environment; results below include both hard failures and environment constraints.

## Branch and history scan

### Branch inventory

- Local heads: `work`
- Remote heads/tags: none present in this clone

### Recent merge/fix pattern (chronological signal)

From commit history:

- 2026-03-24: rapid feature expansion and CI scaffolding (`feat` heavy day).
- 2026-03-25: high merge density and repeated CI/test fixes.
- 2026-03-26: merge `#16` followed by additional CI fix commits.

Commit density summary extracted from `git log --all`:

- 2026-03-23: 44 commits (`feat`: 2, `fix`: 0)
- 2026-03-24: 29 commits (`feat`: 13, `fix`: 5)
- 2026-03-25: 19 commits (`feat`: 5, `fix`: 4)
- 2026-03-26: 3 commits (`feat`: 0, `fix`: 2)

Interpretation: development pace accelerated rapidly, then shifted into a fix/merge stabilization cycle. This is a classic signature of an unstable integration window rather than a fully healthy steady-state baseline.

## Validation checks run (updated after fix verification)

### 1) Contract test layer

Command:

- `python -m pytest tests/contract/ -q`

Result:

- **PASS** — 310 passed.

Implication:

- Interface schema conformance remains healthy at the contract layer.

### 2) Integration test layer (repo-root suite)

Command:

- `PYTHONPATH=services/shared:services/audience-state:services/decision-optimizer:services/input-cv:services/player:services/creative:services/supervisor pytest tests/integration -q`

Result before fix:

- **FAIL** — 69 passed, 1 failed.
- Failing test: `tests/integration/test_log_pii_lint.py::TestRuntimeLogPIILint::test_audience_sink_privacy_gate_logs_no_pii`
- Error mode: `ImportError: attempted relative import with no known parent package` while loading `services/dashboard-api/dashboard_api/audience_sink.py`.

Fix applied:

- `services/dashboard-api/dashboard_api/audience_sink.py`
  - switched relative imports to absolute `dashboard_api.*` imports
  - removed flag-value details from privacy violation logs to satisfy PII runtime lint patterns

Result after fix:

- **PASS** — 70 passed, 0 failed (`pytest tests/integration -q` with service paths in `PYTHONPATH`).

Implication:

- The previously deterministic integration failure is resolved in this environment.

### 3) Full repo test layer (contract + integration + hygiene-style root run)

Command:

- `PYTHONPATH=services/shared:services/audience-state:services/decision-optimizer:services/input-cv:services/player:services/creative:services/supervisor:services/dashboard-api pytest tests -q`

Result:

- **PASS** — 391 passed.

Implication:

- With explicit local import pathing, the downstream test surface under `tests/` is currently green.

### 4) CI-like unit matrix reproduction

Attempted commands (Python 3.11 + editable installs), aligned to `.github/workflows/ci.yml`:

- `pip install -e services/shared`
- per-service editable installs + `pytest tests/`

Result:

- **BLOCKED BY ENVIRONMENT** — package index access/proxy prevented required dependency resolution in this environment.

Implication:

- Remaining downstream risk appears environment-driven (dependency/index access and interpreter provisioning), not the previously observed import/PII-lint bug.

## Point-of-departure (delta anchor)

A practical stability anchor appears to be **2026-03-24** around commits that explicitly report broad green testing (e.g., `c3e822c` message: "816 tests total, 0 failures").

Potential departure window for current instability:

- **2026-03-25**, when analytics/live/dashboard changes and subsequent CI-fix commits were merged repeatedly (including new `dashboard-api` sink behavior and related test updates).

## Health verdict

**Current stack status in this environment: functionally healthy at the repository test layer.**

- Strength: contract layer is solid (310/310).
- Strength: integration + root tests are green after the `audience_sink` import/logging fix.
- Remaining risk: CI parity is still not fully reproducible here due package index/proxy constraints and Python 3.11 setup friction.
- Process signal: recent history still shows sustained fix-after-merge churn, so stabilization discipline remains important.

## Recommended next delta steps

1. Re-run full CI matrix in a clean Python 3.11 environment with unrestricted package access.
2. Confirm compose-smoke and dashboard-api postgres migration jobs are green post-fix.
3. Establish a new "green anchor" commit once contract + unit matrix + integration + compose smoke are all passing.
