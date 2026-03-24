# dashboard-api contracts

ICD-6: Dashboard Frontend ↔ Dashboard API
ICD-7: Dashboard API ↔ PostgreSQL

These schemas define the canonical business objects exchanged by the dashboard
control plane.  They are distinct from the real-time CV pipeline contracts
(ICD-2/3/4/5) — this side of the system is operator-facing, persistence-backed,
and approval-gated.

| Schema | Purpose | ICD |
|---|---|---|
| `manifest-record.schema.json` | Manifest business object (create/response) | ICD-6 |
| `campaign-record.schema.json` | Campaign business object | ICD-6 |
| `system-status.schema.json` | Aggregated system health response | ICD-6 |
| `audit-event.schema.json` | Append-only audit event record | ICD-7 |

## Manifest approval state machine

```
draft ──approve──▶ approved ──enable──▶ enabled
  ▲                   │                    │
  │        reject     │      disable       │
  │◀──────────────────┘        │           │
  │                            ▼           │
  │                         disabled ──enable──▶ enabled
  │
  └── any state ──archive──▶ archived
```

Rules enforced by `dashboard-api` business logic (non-bypassable):
- `enable` requires status = `approved` or `disabled`
- `approve` requires status = `draft` or `rejected`
- `archived` is terminal — no transitions out
