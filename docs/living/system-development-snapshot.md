# System / Development Snapshot

*Adaptive Retail Advertising MVP · living execution-state artifact*

**Last updated:** 2026-04-02
**Status:** All services scaffolded and tested; contract test suite (ICD-1 through ICD-8, 310 tests) complete; CI workflow added; integration smoke tests (healthz + ICD-4 e2e) passing; supervisor fault injection tests complete (34 tests); WireGuard provisioning scaffold complete (golden-image ready); requirement traceability matrix added; golden-image hygiene test suite (11 tests) added; input-cv scaffolded with stub pipeline (hardware bring-up pending camera qualification); **full software simulation mode complete** — `docker compose up --build` now runs end-to-end without camera hardware (NullDriver via INPUT_CV_PIPELINE_BACKEND=null, StubRenderer); ICD-2 field name bug fixed; sim-cv-injector tool added; **analytics + adaptive behavior sprint complete** — analytics DB sink (audience_snapshots + play_events + uptime_events), real analytics router, campaign impression tracking, uptime SLO endpoint, demographic + time-of-day policy conditions, runtime rules hot-swap, live manifest reload, play-event MQTT publishing, PII lint runtime tests, OS rollback script; **CRM-003 implemented** — gender demographic dimension (`male`/`female` bins) added end-to-end; **CRM-004 (attention) + CRM-005 (attire) implemented** — full end-to-end implementation of attention engagement metric and 10-bin attire demographic; 521 relevant tests passing

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
| WireGuard / remote admin | **Scaffolded** — `provisioning/wireguard/wg0.conf.template` + `provisioning/scripts/setup-wireguard.sh` + `provisioning/scripts/provision.sh`; golden-image design (zero device-specific values hardcoded) |

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
| ICD-2: input-cv → audience-state | `contracts/audience-state/cv-observation.schema.json` | v1.0 — metadata-only, privacy fields schema-enforced; **CRM-003:** `demographics.gender`; **CRM-004:** root-level `attention` block (engaged/ambient); **CRM-005:** `demographics.attire` (10 bins) |
| ICD-4: decision → player | `contracts/player/player-command.schema.json` | v1.0 — commands, sequence ordering defined |
| ICD-5: creative → player | `contracts/creative/creative-manifest.schema.json` | v1.0 — approval fields required |
| ICD-3: audience-state → decision | `contracts/decision-optimizer/audience-state-signal.schema.json` | v1.0 — smoothed state, stability flags, privacy enforced; **CRM-003:** `state.demographics.gender`; **CRM-004:** `state.attention` (engaged/ambient); **CRM-005:** `state.demographics.attire` (10 bins) |
| ICD-6: dashboard-ui ↔ dashboard-api | `contracts/dashboard-api/` (manifest, campaign, audit-event, system-status schemas) | v1.0 — full REST contract implemented |
| ICD-7: dashboard-api ↔ PostgreSQL | `services/dashboard-api/alembic/` | v1.0 — full async ORM + Alembic migration (SQLAlchemy 2.0) |
| ICD-8: supervisor ↔ managed services | `contracts/supervisor/service-health-report.schema.json` | v1.0 — health report schema; restart-ladder + safe-mode relay implemented |

## 5. Service Status

| Service | Status | Notes |
|---|---|---|
| input-cv | Scaffolded | `services/input-cv/` — config loader (ICD-1 schema-validated, Pydantic), observation model + builder (privacy-negative: banned keys raise PrivacyViolationError), ICD-2 MQTT publisher (paho-mqtt, MQTTv5, QoS 1), null pipeline driver (stub), DeepStream driver stub, recovery/backoff, health tracker, 81 unit tests passing; **simulation mode: INPUT_CV_PIPELINE_BACKEND=null wired in docker-compose.yml** (default); ICD-2 serialization field names corrected (present/confidence/frames_processed/frames_dropped); DeepStream hardware bring-up pending camera qualification |
| audience-state | Scaffolded | `services/audience-state/` — sliding-window smoothing (ObservationWindow with injectable clock), ICD-2 MQTT consumer with schema validation + privacy enforcement, ICD-3 outbound publisher with self-validation before publish; **CRM-004:** `compute_attention()` (engaged/ambient averaging, independent of demographics gate); **CRM-005:** attire smoothing in `compute_demographics()` (10 bins, optional per obs); 77 unit tests passing |
| decision-optimizer | Implemented | `services/decision-optimizer/` — 1 Hz decision loop, rules-first policy engine (JSON config), ICD-3 MQTT signal consumer (aiomqtt), ICD-4 WebSocket server (player gateway); demographic conditions (age_group_*, gender_*, demographics_suppressed_eq), time-of-day, runtime policy hot-swap; **CRM-004:** `attention_engaged_gte` condition (absent→silent pass); **CRM-005:** 10 `attire_*_gte` conditions; fixed `age_group` key (was `age_groups`); 104 policy unit tests passing |
| creative | Scaffolded | `services/creative/` — ManifestStore (schema validation, approval enforcement, expiry with injectable clock), HTTP API (GET /manifests/{id} with 200/403/404/410, GET /manifests list, /healthz, /readyz), 3 seed manifests (attract/default/group), 46 unit + API tests passing |
| player | Implemented | `services/player/` — state machine, command handler (ICD-4), manifest store (ICD-5), stub + mpv renderer, fallback bundle, health endpoints, 61→67+ unit tests passing; RENDERER_BACKEND=stub for CI; mpv wiring complete pending hardware bring-up; **new:** ManifestStore.reload() (full-replace semantics, 60s background loop), PlayEventPublisher (fire-and-forget MQTT on activate_creative) |
| dashboard-api | Implemented | `services/dashboard-api/` — FastAPI, SQLAlchemy 2.0 async ORM, Alembic migrations; full manifest approval state machine, campaigns, assets, safe-mode, audit events; analytics DB sinks, real analytics endpoints, POST /api/v1/policy/reload relay; **CRM-003:** migration 0004 (gender columns), audience_sink gender parsing, rule_generator male_focus/female_focus; **CRM-004:** migration 0005 (attention_engaged on AudienceSnapshot, attention_at_trigger on PlayEvent), play_event_sink nearest-snapshot lookup, avg_attention_engaged in summary, avg_attention_at_trigger in campaign analytics; **CRM-005:** migration 0005 (10 attire_* columns), audience_sink attire parsing, rule_generator 10 attire tags + tiered thresholds; rule_generator cross-dim pair rules (_DIMENSION_GROUPS, _CROSS_DIM_PRIORITY_BONUS=3); attention gate auto-injection (0.35) into all non-attract/general audience conditions; 250 tests passing |
| dashboard-ui | Scaffolded | `services/dashboard-ui/` — React 18 + Vite + TypeScript SPA; Screenly-inspired design (zinc-900 sidebar, emerald accent); shadcn/ui + Tailwind; 6 pages (System, Manifests, Campaigns, Analytics, Events, Settings); nginx Docker image with /api/* reverse-proxy; build verified (369 kB JS) |
| postgres | Not Started | Local storage; schema migrations ready in dashboard-api (Alembic) |
| supervisor | Scaffolded | `services/supervisor/` — health-probe loop (all 5 services), restart-ladder (REC-004/006), safe-mode relay dashboard-api→player (ICD-8), storage monitor (REC-005), /healthz /readyz /status endpoints; 40 tests passing |

## 6. Verification Status

| Item | Status |
|---|---|
| Unit tests | In Progress — 450+ tests passing total: input-cv (81), player (67+), decision-optimizer (80+), audience-state (63), creative (46), dashboard-api (65+), supervisor (74); new: test_manifest_store_reload.py (6), test_policy.py expanded (+26 demographic/time/reload tests), test_analytics.py (20) |
| Contract tests | Complete — 310 tests passing: ICD-1 (38), ICD-2 (46), ICD-3 (44), ICD-4 (42), ICD-5 (38), ICD-6 (82), ICD-8 (20); `tests/contract/` |
| Integration tests | In Progress — 55+ tests passing: healthz smoke (21) + ICD-4 e2e WebSocket (9) + privacy audit ICD-2→ICD-3 (20) + PII lint runtime (5+); `tests/integration/` |
| Hygiene tests | Complete — 11 tests passing: `tests/test_no_hardcoded_values.py`; golden-image gate (no secrets, no placeholder tokens, no routable IPs, Pydantic Settings env-override verified) |
| Traceability matrix | Complete — `docs/living/traceability-matrix.md`; all SYS/PERF/CV/REC/PRIV/OBS/PROV/THRM/ICD requirements mapped with status and evidence |
| CI | Complete — `.github/workflows/ci.yml`: contract tests + unit test matrix (7 services) + postgres migration job + integration tests + hygiene gate; triggers on push and PR |
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
9. ~~Resolve CRM-002 (ICD-4 freeze/unfreeze ambiguity)~~ — Done. `activate_creative`-as-unfreeze; schema description updated; CRM-002 closed.
10. ~~Postgres bring-up~~ — Done. `test_postgres_migration.py` (8 tests); CI postgres job with postgres:16.
11. ~~Privacy / egress audit test pass~~ — Done (`tests/integration/test_privacy_audit.py`). 20 tests: ICD-2 privacy gate, ICD-3 privacy flag enforcement, egress audit (banned-key + base64 + URL inspection in serialized bytes), schema conformance, stability/freeze propagation.
12. ~~Supervisor fault injection / stress tests~~ — Done (`services/supervisor/tests/test_fault_injection.py`). 34 tests: restart ladder, safe mode gate, recovery, simultaneous failures, storage thresholds, safe-mode independence, timestamp pruning.
13. ~~WireGuard provisioning scaffold~~ — Done. `provisioning/wireguard/wg0.conf.template` + `provisioning/scripts/setup-wireguard.sh` + `provisioning/scripts/provision.sh`; golden-image design; zero device-specific hardcoded values.
14. ~~Requirement traceability matrix~~ — Done. `docs/living/traceability-matrix.md`; all requirements mapped.
15. ~~Golden-image hygiene test~~ — Done. `tests/test_no_hardcoded_values.py` (11 tests); CI hygiene gate added.
16. ~~Software simulation mode~~ — Done. `INPUT_CV_PIPELINE_BACKEND=null` wired in docker-compose.yml; ICD-2 field name bug fixed; `tools/sim-cv-injector.py` added; `docker compose up --build` now runs full pipeline without camera.
17. **Implement CRM-003 — gender demographic dimension** — see `docs/living/design-proposal-gender-demographic.md` for full spec. Phases: P0 contracts → P1 input-cv → P2 audience-state → P3 decision-optimizer → P4 dashboard-api (migration 0003 + sink + rule_generator) → P5 integration tests → P6 regression → P7 docs update.
18. Acquire and qualify Arducam IMX477 HQ camera on target Jetson Orin Nano hardware (see `decisions/2026-03-23-camera-sku-candidate.md`).
18. Pin JetPack point release after camera qualification result.
19. On Jetson pilot deploy: set `RENDERER_BACKEND=mpv` and remove `INPUT_CV_PIPELINE_BACKEND=null` + uncomment `/dev/video0` device in docker-compose.yml.
20. Add Prometheus `/metrics` endpoint to each service (OBS-003 gap).
21. ~~Automate log PII lint test~~ — Done. `tests/integration/test_log_pii_lint.py` extended: static source scan + runtime log capture (PolicyEngine + audience_sink privacy gate).
22. ~~Analytics DB sink (audience_snapshots)~~ — Done. `audience_sink.py` + `play_event_sink.py` + `uptime_sink.py`; Alembic migration `0002_analytics_tables.py`.
23. ~~Real analytics endpoints~~ — Done. `routers/analytics.py` rewritten: summary/play-events/campaigns/{id}/summary/uptime (live DB queries).
24. ~~Policy: demographic + time-of-day conditions~~ — Done. `policy.py` updated; `test_policy.py` expanded +26 tests.
25. ~~Runtime rules hot-swap~~ — Done. `health.py` POST /api/v1/rules/reload; `decision_loop.py` reload_policy(); `routers/system.py` relay endpoint.
26. ~~Live manifest reload in player~~ — Done. `ManifestStore.reload()` + `_manifest_reload_loop()` background task.
27. ~~Play-event publishing~~ — Done. `play_event_publisher.py` (fire-and-forget MQTT); wired in `command_handler.py` + `main.py`.
28. ~~OS rollback script~~ — Done. `provisioning/scripts/rollback.sh`.
29. Acquire and qualify Arducam IMX477 HQ camera on target Jetson Orin Nano hardware.
30. Pin JetPack point release after camera qualification result.
31. On Jetson pilot deploy: set `RENDERER_BACKEND=mpv` and remove `INPUT_CV_PIPELINE_BACKEND=null`.
32. Add Prometheus `/metrics` endpoint to each service (OBS-003 gap).
