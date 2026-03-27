# Full Test Suite Report — 2026-03-27

## Scope

Complete suite run across:

1. Root repository tests (`tests/`)
2. Service test suites:
   - `services/input-cv/tests`
   - `services/audience-state/tests`
   - `services/decision-optimizer/tests`
   - `services/player/tests`
   - `services/creative/tests`
   - `services/supervisor/tests`
   - `services/dashboard-api/tests`

Environment used for all runs:

- `PYTHONPATH=/workspace/Adaptive-Advertisement/services/shared:/workspace/Adaptive-Advertisement/services/audience-state:/workspace/Adaptive-Advertisement/services/decision-optimizer:/workspace/Adaptive-Advertisement/services/input-cv:/workspace/Adaptive-Advertisement/services/player:/workspace/Adaptive-Advertisement/services/creative:/workspace/Adaptive-Advertisement/services/supervisor:/workspace/Adaptive-Advertisement/services/dashboard-api`
- `RENDERER_BACKEND=stub`

## Results

| Suite | Command | Result |
|---|---|---:|
| Root tests | `pytest tests -q` | 391 passed |
| input-cv | `cd services/input-cv && pytest tests -q` | 101 passed, 1 warning |
| audience-state | `cd services/audience-state && pytest tests -q` | 76 passed |
| decision-optimizer | `cd services/decision-optimizer && pytest tests -q` | 105 passed |
| player | `cd services/player && pytest tests -q` | 110 passed |
| creative | `cd services/creative && pytest tests -q` | 51 passed |
| supervisor | `cd services/supervisor && pytest tests -q` | 78 passed |
| dashboard-api | `cd services/dashboard-api && pytest tests -q` | 51 passed, 35 skipped |

## Aggregate totals

- **Passed:** 963
- **Skipped:** 35
- **Failed:** 0
- **Errors:** 0

## Notes

- Dashboard-api skips are expected in this constrained environment when optional local test dependencies (`httpx`, `aiosqlite`) are not installed; CI runners install these deps and execute the full dashboard-api suite.
- No failing tests were observed across the executed complete suite.
