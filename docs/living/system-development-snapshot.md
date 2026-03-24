# System / Development Snapshot

*Adaptive Retail Advertising MVP · living execution-state artifact*

**Last updated:** 2026-03-24
**Status:** All services scaffolded and tested; contract test suite (ICD-1 through ICD-8, 310 tests) complete; CI workflow added; integration smoke tests (healthz + ICD-4 e2e) passing; input-cv scaffolded with stub pipeline (hardware bring-up pending camera qualification)

> Agents must read this document before starting work and update it after any material change. If this snapshot conflicts with an authoritative baseline document, log the conflict in the Change Resolution Matrix rather than silently reconciling it.

---

## 1. Authoritative Document Baseline

| Item | Current status / notes |
|---|---|
| Active roadmap | `golden-roadmap-v2.1-csi-local-ingest.md` — CSI rebaseline is the active direction; supersedes v2.0 for all ingest-path decisions |
| Active ICD | `consolidated-icd-v1.1-csi-local-ingest.md` + `interface-addendum-v1.0.md` — CSI/V4L2 replaces RTSP in ICD-1 |
| TRD | `technical-requirements-package.md` — present and active |
| V&V plan | `verification-validation-plan.md` — present and active |
| Pilot protocol | `pilot-validation-protocol-v1.1-csi-local-ingest.md` — CSI revision active |
| Governance | `coding-ai-governance-charter-v1.0.md` — active; `CLAUDE.md` is the agent-facing summary |
| Software selection | `governance/software-selection-directive.txt` — foundational; active |

## 2. Platform Baseline (locked decisions)

| Item | Status / value |
|---|---|
| Hardware SKU | Jetson Orin Nano / Orin-class; exact final deploy SKU to be frozen after camera qualification |
| JetPack / L4T | **Locked: JetPack 6.x / L4T 36.x** — see `decisions/2026-03-23-jetpack-version.md` |
| DeepStream | 7.x (aligned to JetPack 6.x) |
| Camera ingest | **Locked: CSI / local-device (V4L2)** — see `decisions/2026-03-23-csi-local-ingest-founder-direction.md` |
| Camera SKU | **Candidate selected:** Arducam IMX477 HQ (CSI, 12 MP, auto IR-cut) — see `decisions/2026-03-23-camera-sku-candidate.md`; bring-up qualification pending |
| JetPack point release | Not pinned — depends on camera SKU qualification result |
| MQTT broker | **Locked: Eclipse Mosquitto 2.x** — see `decisions/2026-03-23-mqtt-broker.md` |
| Storage | 256 GB NVMe pilot default |
| Display | Customer-provided display is the deployed runtime endpoint; 7-inch HDMI is bench/service accessory only |
| Container runtime | Not Started (docker-compose.yml exists; full `docker compose up --build` needs target hardware or CI with Docker) |
| WireGuard / remote admin | Direction locked; implementation Not Started |

## 3. Repo and Workspace Status

| Item | Current status / notes |
|---|---|
| Primary repo | `homelab-net/Adaptive-Advertisement` |
| Active branch | `claude/project-overview-A7Vqt` |
| Baseline alignment | CSI rebaseline documents present; repo structure overhauled 2026-03-23; `docs/repo-native/` intermediate layer removed |
| Pending merges | None blocking implementation |
| Open PRs on remote | pr2 through pr6 on remote origin; all content absorbed into working branch |

## 4. Contract Status

| Contract | File | Status |
|---|---|---|
| ICD-1: camera → input-cv | `contracts/input-cv/camera-source.schema.json` | v1.1 — CSI/V4L2 fields defined |
| ICD-2: input-cv → audience-state | `contracts/audience-state/cv-observation.schema.json` | v1.0 — metadata-only, privacy fields schema-enforced |
| ICD-4: decision → player | `contracts/player/player-command.schema.json` | v1.0 — commands, sequence ordering defined |
| ICD-5: creative → player | `contracts/creative/creative-manifest.schema.json` | v1.0 — approval fields required |
| ICD-3: audience-state → decision | `contracts/decision-optimizer/audience-state-signal.schema.json` | v1.0 — smoothed state, stability flags, privacy enforced |
| ICD-6: dashboard-ui ↔ dashboard-api | `contracts/dashboard-api/` (manifest, campaign, audit-event, system-status schemas) | v1.0 — full REST contract implemented |
| ICD-7: dashboard-api ↔ PostgreSQL | `services/dashboard-api/alembic/` | v1.0 — full async ORM + Alembic migration (SQLAlchemy 2.0) |
| ICD-8: supervisor ↔ managed services | `contracts/supervisor/service-health-report.schema.json` | v1.0 — health report schema; restart-ladder + safe-mode relay implemented |

## 5. Service Status

| Service | Status | Notes |
|---|---|---|
| input-cv | Scaffolded | `services/input-cv/` — config loader (ICD-1 schema-validated, Pydantic), observation model + builder (privacy-negative: banned keys raise PrivacyViolationError), ICD-2 MQTT publisher (paho-mqtt, MQTTv5, QoS 1), null pipeline driver (stub), DeepStream driver stub, recovery/backoff, health tracker, 81 unit tests passing; V4L2 device open blocked on hardware |
| audience-state | Scaffolded | `services/audience-state/` — sliding-window smoothing (ObservationWindow with injectable clock), ICD-2 MQTT consumer with schema validation + privacy enforcement, ICD-3 outbound publisher with self-validation before publish, 63 unit tests passing |
| decision-optimizer | Scaffolded | `services/decision-optimizer/` — 1 Hz decision loop, rules-first policy engine (JSON config), ICD-3 MQTT signal consumer (aiomqtt), ICD-4 WebSocket server (player gateway), 54 unit tests passing |
| creative | Scaffolded | `services/creative/` — ManifestStore (schema validation, approval enforcement, expiry with injectable clock), HTTP API (GET /manifests/{id} with 200/403/404/410, GET /manifests list, /healthz, /readyz), 3 seed manifests (attract/default/group), 46 unit + API tests passing |
| player | Scaffolded | `services/player/` — state machine, command handler (ICD-4), manifest store (ICD-5), stub + mpv renderer, fallback bundle, health endpoints, 61 unit tests passing; RENDERER_BACKEND=stub for CI; mpv wiring complete pending hardware bring-up |
| dashboard-api | Scaffolded | `services/dashboard-api/` — FastAPI, SQLAlchemy 2.0 async ORM, Alembic migrations; full manifest approval state machine (draft→approved→enabled/disabled/archived), campaigns, assets, safe-mode, audit events, analytics scaffold; 43 tests passing (SQLite/aiosqlite in CI) |
| dashboard-ui | Scaffolded | `services/dashboard-ui/` — React 18 + Vite + TypeScript SPA; Screenly-inspired design (zinc-900 sidebar, emerald accent); shadcn/ui + Tailwind; 6 pages (System, Manifests, Campaigns, Analytics, Events, Settings); nginx Docker image with /api/* reverse-proxy; build verified (369 kB JS) |
| postgres | Not Started | Local storage; schema migrations ready in dashboard-api (Alembic) |
| supervisor | Scaffolded | `services/supervisor/` — health-probe loop (all 5 services), restart-ladder (REC-004/006), safe-mode relay dashboard-api→player (ICD-8), storage monitor (REC-005), /healthz /readyz /status endpoints; 40 tests passing |

## 6. Verification Status

| Item | Status |
|---|---|
| Unit tests | In Progress — 388 tests passing total: input-cv (81), player (61), decision-optimizer (54), audience-state (63), creative (46), dashboard-api (43), supervisor (40) |
| Contract tests | Complete — 310 tests passing: ICD-1 (38), ICD-2 (46), ICD-3 (44), ICD-4 (42), ICD-5 (38), ICD-6 (82), ICD-8 (20); `tests/contract/` |
| Integration tests | In Progress — 50 tests passing: healthz smoke (21) + ICD-4 e2e WebSocket (9) + privacy audit ICD-2→ICD-3 (20); `tests/integration/` |
| CI | Complete — `.github/workflows/ci.yml`: contract tests job + per-service unit test matrix (7 services) + integration test job; triggers on push and PR |
| System / recovery evidence | Not Started |

## 7. Current Blockers and Open Risks

| Risk | Status |
|---|---|
| Camera SKU qualification | Open — Arducam IMX477 HQ selected as candidate; bring-up on target Jetson not yet verified; blocks JetPack point-release pin |
| Player not yet scaffolded | **Closed** — player scaffolded 2026-03-23; see `services/player/` |
| ICD-3 no code-facing schema | **Closed** — `contracts/decision-optimizer/audience-state-signal.schema.json` v1.0 created 2026-03-23 |
| ICD-6/7 no code — dashboard, postgres | **Closed** — dashboard-api (FastAPI + SQLAlchemy 2.0) and dashboard-ui (React/Vite) scaffolded 2026-03-24 |
| ICD-8 no code — supervisor | **Closed** — supervisor scaffolded 2026-03-24; restart-ladder, safe-mode relay, storage monitor implemented |

## 8. Immediate Next Actions

1. ~~Scaffold `player` service with screen-never-blank fallback posture~~ — Done (`services/player/`). CRM-002 logged for freeze/unfreeze schema ambiguity.
2. ~~Create ICD-3 code-facing schema stub~~ — Done (`contracts/decision-optimizer/audience-state-signal.schema.json` v1.0).
3. ~~Scaffold `dashboard-api` (ICD-6/7)~~ — Done (`services/dashboard-api/`). Full manifest state machine, campaigns, assets, safe-mode, audit log, 43 tests.
4. ~~Scaffold `dashboard-ui` (ICD-6 client)~~ — Done (`services/dashboard-ui/`). React/Vite SPA, 6 pages, nginx Docker image, build verified.
5. ~~Scaffold `supervisor` service (ICD-8)~~ — Done. Restart-ladder, safe-mode relay, storage monitor, 40 tests.
6. ~~Scaffold `input-cv` service~~ — Done (`services/input-cv/`). Config loader, observation model, privacy enforcement, null/DeepStream drivers, MQTT publisher, 81 tests. V4L2 device open pending hardware.
7. ~~Write contract test suite (ICD-1 through ICD-8)~~ — Done (`tests/contract/`). 310 tests; privacy invariants, required fields, additionalProperties, enum/pattern/bounds all covered.
8. ~~Add CI workflow~~ — Done (`.github/workflows/ci.yml`). Contract + per-service unit + integration jobs; triggers on push/PR.
9. Resolve CRM-002 (ICD-4 freeze/unfreeze ambiguity) — schema or service change needed.
10. Postgres bring-up: run `alembic upgrade head` against a real postgres instance; add postgres-backed pytest fixture to dashboard-api tests.
11. ~~Privacy / egress audit test pass~~ — Done (`tests/integration/test_privacy_audit.py`). 20 tests: ICD-2 privacy gate, ICD-3 privacy flag enforcement, egress audit (banned-key + base64 + URL inspection in serialized bytes), schema conformance, stability/freeze propagation.
12. Acquire and qualify Arducam IMX477 HQ camera on target Jetson Orin Nano hardware (see `decisions/2026-03-23-camera-sku-candidate.md`).
13. Pin JetPack point release after camera qualification result.
14. Run full `docker compose up --build` on target hardware or CI to validate inter-service network connectivity end-to-end.
