# Requirement Traceability Matrix

*Adaptive Retail Advertising MVP — living artifact*

**Last updated:** 2026-03-24
**Status:** Initial build — all requirements from TRD mapped; evidence column tracks current test coverage

> This matrix maps every named requirement ID from the Technical Requirements Package
> to the implementation and test evidence that satisfies it.
> Update the Evidence column whenever new tests or implementation artefacts are created.
> A requirement is "verified" only when an automated test or documented acceptance procedure
> exercises it against its stated acceptance criterion.

---

## Legend

| Status | Meaning |
|---|---|
| ✅ Verified | Automated test(s) exist and pass; evidence cited |
| 🔶 Partial | Implementation exists; test coverage incomplete |
| 🔷 Implemented | Code exists; no automated test yet |
| ⬜ Not Started | No implementation or test |
| 🚫 Blocked | Depends on hardware or external prerequisite |

---

## 1. System-Level Requirements (SYS)

| ID | Requirement | Target | Priority | Status | Implementation | Test Evidence |
|---|---|---|---|---|---|---|
| SYS-001 | Playback must remain correct if `SVC-CV` (input-cv) fails | 0 playback impact | MUST | 🔶 Partial | Player has fallback bundle; supervisor restart-ladder covers player; decision-optimizer freezes on CV loss | `tests/integration/test_icd4_e2e.py` — WebSocket e2e; `services/supervisor/tests/test_fault_injection.py::TestFullLadderProgression`; hardware soak pending |
| SYS-002 | CV-derived signals must carry confidence fields | confidence attached to all signals | MUST | ✅ Verified | `cv-observation.schema.json` requires `confidence` [0,1]; audience-state builder enforces; ICD-3 carries `source_quality` | `tests/contract/test_icd2_cv_observation.py` — confidence bounds; `tests/contract/test_icd3_audience_state_signal.py` |
| SYS-003 | State transitions must be explicit and logged | 100% transitions logged | SHOULD | 🔷 Implemented | Supervisor audit log; dashboard-api audit_events table; player state-machine logs transitions | `services/dashboard-api/tests/` — audit event schema; `tests/contract/test_icd6_dashboard_api.py::TestAuditEvent` |
| SYS-004 | All interfaces must be versioned (semver) | semver on all schemas | SHOULD | ✅ Verified | All 8 ICD schemas carry `schema_version` const field | `tests/contract/test_icd1_camera_source.py` — version const; all other ICD contract tests check version field |

---

## 2. Performance Requirements (PERF)

| ID | Requirement | Target | Priority | Status | Implementation | Test Evidence |
|---|---|---|---|---|---|---|
| PERF-001 | Time-to-first-frame from cold power-on | ≤ 60 s | MUST | 🚫 Blocked | Player loads fallback bundle on startup; systemd unit enables auto-start | Acceptance test pending hardware; `services/player/` fallback posture verified in unit tests |
| PERF-002 | Time-to-operational (CV + decision healthy) | ≤ 120 s | SHOULD | 🚫 Blocked | All services expose `/readyz`; supervisor polls health | `tests/integration/test_healthz_smoke.py` — all 5 services respond; timing on hardware pending |
| PERF-003 | Capture → metadata latency p95 | ≤ 150 ms @ 10 FPS | MUST | 🚫 Blocked | input-cv pipeline adds `captured_at` timestamp; ICD-2 carries `window_ms` | Contract: `tests/contract/test_icd2_cv_observation.py::test_window_ms_*`; latency trace pending camera hardware |
| PERF-004 | Decision loop interval | 1 Hz ±10% | SHOULD | 🔷 Implemented | decision-optimizer runs `asyncio` 1 Hz loop | `services/decision-optimizer/tests/` — loop cadence tests; integration timing pending |
| PERF-005 | Creative switch execution time p95 | ≤ 2 s excl. dwell | MUST | 🚫 Blocked | Player state-machine executes `activate_creative` synchronously in stub renderer | `tests/integration/test_icd4_e2e.py` — command round-trip; mpv timing pending hardware |
| PERF-006 | Visible blank/black screen during normal operation | 0 target; ≤ 250 ms hard cap | MUST | 🔷 Implemented | Player never-blank posture: fallback bundle always loaded; `freeze` command holds current creative | Stub renderer tests pass; hardware frame-grab evidence pending |
| PERF-007 | Dashboard API response over VPN p95 | ≤ 1 s | SHOULD | 🔷 Implemented | FastAPI async ORM; `/healthz` responds sub-10 ms in CI | `services/dashboard-api/tests/` — httpx response time checks; VPN-path timing pending deployment |

---

## 3. CV Accuracy Thresholds (CV)

| ID | Requirement | Target | Priority | Status | Implementation | Test Evidence |
|---|---|---|---|---|---|---|
| CV-001 | Presence recall (pilot scenes) | ≥ 0.95 | MUST | 🚫 Blocked | DeepStream driver stub; model qualification pending camera bring-up | Hardware qualification procedure: `docs/authoritative/verification/pilot-validation-protocol-v1.1-csi-local-ingest.md` |
| CV-002 | Presence false positives | ≤ 1 / 10 min | MUST | 🚫 Blocked | Same as CV-001 | Hardware qualification |
| CV-003 | Count MAE (10 s windows) | ≤ 0.6 persons | MUST | 🚫 Blocked | Sliding-window smoothing implemented in audience-state | Hardware qualification |
| CV-004 | Count within ±1 (10 s windows) | ≥ 90% of windows | MUST | 🚫 Blocked | Same smoothing layer | Hardware qualification |
| CV-005 | Tracking ID stability | ≤ 1 ID switch / person / 30 s | SHOULD | 🚫 Blocked | DeepStream tracker config pending | Hardware qualification |
| CV-006 | Low-confidence gating for optional attributes | 100% gated | SHOULD | ✅ Verified | `confidence` field enforced [0,1]; audience-state drops observations below threshold | `tests/contract/test_icd2_cv_observation.py::test_confidence_*`; `tests/integration/test_privacy_audit.py::TestIcd2PrivacyGate` |
| CV-007 | Optional attributes are coarse/probabilistic only | discrete bins + probabilities | CAN | ✅ Verified | ICD-2 schema uses enum + probability fields for optional demographic bins | `tests/contract/test_icd2_cv_observation.py` — additionalProperties, enum enforcement |

---

## 4. Recovery and Resilience Requirements (REC)

| ID | Requirement | Target / Behavior | Priority | Status | Implementation | Test Evidence |
|---|---|---|---|---|---|---|
| REC-001 | CV failure does not interrupt playback | 0 impact | MUST | 🔶 Partial | decision-optimizer freezes on loss of ICD-3 signal; player holds current creative | `services/supervisor/tests/test_fault_injection.py::TestCriticalServiceSafeModeGate` — non-critical escalation does not affect player; integration e2e pending |
| REC-002 | Player crash recovery | ≤ 10 s | MUST | 🔶 Partial | Supervisor restart-ladder targets player first; `failure_threshold: 3` → restart | `services/supervisor/tests/test_fault_injection.py::TestFullLadderProgression`; timing evidence on hardware pending |
| REC-003 | Decision failure freezes stable playlist | player freezes; no switching | MUST | 🔷 Implemented | ICD-4 `freeze` command triggers player hold; decision-optimizer sends freeze on recovery lag | `tests/contract/test_icd4_player_command.py::test_freeze_*`; `tests/integration/test_icd4_e2e.py` |
| REC-004 | Escalation ladder implemented | restart → safe-mode after N failures | MUST | ✅ Verified | Supervisor `RestartManager`: `failure_threshold` → restart; `restart_threshold` → ESCALATED; `boot_loop_threshold` within window → BOOT_LOOP | `services/supervisor/tests/test_fault_injection.py::TestFullLadderProgression`; `test_restart_manager.py` |
| REC-005 | Storage-full protection | never hit 100%; warn at 80%, critical at 90% | MUST | ✅ Verified | `StorageMonitor` polls disk; thresholds 80% warn / 90% critical; supervisor triggers safe mode at critical | `services/supervisor/tests/test_fault_injection.py::TestStorageThresholds`; `test_storage_monitor.py` |
| REC-006 | Boot-loop prevention | safe mode after repeated failures within window | SHOULD | ✅ Verified | `boot_loop_threshold` + `FAST_FAIL_WINDOW_S` timestamp pruning; BOOT_LOOP state → safe mode engagement for critical services | `services/supervisor/tests/test_fault_injection.py::TestFullLadderProgression::test_boot_loop_path`; `test_fault_injection.py::TestTimestampPruning` |

---

## 5. Privacy Requirements (PRIV)

| ID | Requirement | Rule | Priority | Status | Implementation | Test Evidence |
|---|---|---|---|---|---|---|
| PRIV-001 | No raw imagery retained on device | zero persistence | MUST | ✅ Verified | input-cv: no frame write path; DeepStream driver produces metadata only; ICD-2 schema bans image fields | `tests/integration/test_privacy_audit.py::TestIcd2PrivacyGate` — `contains_images: true` rejected |
| PRIV-002 | No raw video egress | zero frame egress | MUST | ✅ Verified | No network path for frames exists in any service; ICD-2 `contains_frame_urls` const false | `tests/integration/test_privacy_audit.py::TestEgressAudit` — base64/URL scan of serialized payloads |
| PRIV-003 | No biometric storage or cross-visit tracking | zero storage | MUST | ✅ Verified | ICD-2 `contains_face_embeddings` const false; input-cv `PrivacyViolationError` on banned keys; no identity schema field | `tests/integration/test_privacy_audit.py::TestIcd2PrivacyGate`; `tests/contract/test_icd2_cv_observation.py::test_privacy_flags_*` |
| PRIV-004 | Logs are PII-safe; no images or embeddings | log lint passes | SHOULD | 🔶 Partial | Banned-key scan implemented; services use structured metadata logging | `tests/integration/test_privacy_audit.py::TestEgressAudit::test_banned_keys_not_in_serialized_payload`; full log-file scan not yet automated |
| PRIV-005 | Memory/swap posture defined | swap disabled or encrypted | SHOULD | 🔷 Implemented | `provision.sh` does not enable swap; policy documented in governance charter | Acceptance test (swap audit) pending hardware deployment |
| PRIV-006 | Admin actions auditable | 100% logged | SHOULD | ✅ Verified | dashboard-api: every manifest, campaign, safe-mode change writes to `audit_events`; 15 event_type values | `tests/contract/test_icd6_dashboard_api.py::TestAuditEventSchema` — all 15 event types; `services/dashboard-api/tests/` — ORM write tests |

---

## 6. Observability Requirements (OBS)

| ID | Requirement | Target | Status | Implementation | Test Evidence |
|---|---|---|---|---|---|
| OBS-001 | Structured logs for all services | JSON lines with required fields | 🔶 Partial | All services use Python `logging`; structured formatting and required fields not yet enforced via schema | Log format tests pending |
| OBS-002 | Health endpoints on all services | `/healthz` + `/readyz` | ✅ Verified | All 5 managed services + supervisor expose `/healthz` and `/readyz` | `tests/integration/test_healthz_smoke.py` — 21 tests, all services pass (5 services × 2 paths + supervisor + creative) |
| OBS-003 | Metrics exposure | local scrape endpoint | ⬜ Not Started | No Prometheus/metrics endpoint implemented yet | — |
| OBS-004 | Remote debug limits (no open SSH) | WireGuard VPN only | 🔷 Implemented | SSH restricted to wg0 interface via iptables in `wg0.conf.template` PreUp; `provision.sh` SSH hardening config | `provisioning/scripts/setup-wireguard.sh` — iptables rules; acceptance: LAN scan pending |

---

## 7. Provisioning Requirements (PROV)

| ID | Requirement | Target | Status | Implementation | Test Evidence |
|---|---|---|---|---|---|
| PROV-001 | First-boot provisioning bounded | ≤ 10 min | 🔷 Implemented | `provisioning/scripts/provision.sh` — idempotent; all steps bounded; Docker pull is longest step | Timed dry-run on target hardware pending |
| PROV-002 | Device identity unique and persistent | persists over reboot | 🔷 Implemented | WireGuard private key written to `/etc/wireguard/wg0.conf` (600 root); VPN IP assigned per-device via env | Reboot persistence test pending deployment |
| PROV-003 | VPN-only admin endpoints | LAN/WAN scan fails | 🔷 Implemented | `setup-wireguard.sh` iptables: blocks SSH port from non-wg0; Mosquitto binds to 127.0.0.1 only | Security scan acceptance test pending deployment |
| PROV-004 | Rollback procedure tested | `AT-UPDATE` acceptance test passes | ⬜ Not Started | Alembic downgrade tested in CI (`test_postgres_migration.py`); full OS-level rollback not yet implemented | `services/dashboard-api/tests/test_postgres_migration.py::test_downgrade_removes_all_tables` |

---

## 8. Thermal Requirements (THRM)

| ID | Requirement | Target | Status | Implementation | Test Evidence |
|---|---|---|---|---|---|
| THRM-001 | Thermal degradation reduces CV before playback | CV FPS drops first; playback unaffected | 🚫 Blocked | Architecture: CV is a separate service; supervisor de-prioritises it below player | Hardware thermal soak test pending |
| THRM-002 | Protect state: freeze adaptation on thermal stress | freeze signal sent | 🚫 Blocked | `freeze` ICD-4 command path exists; thermal trigger not yet wired to supervisor | — |
| THRM-003 | `tegrastats` sampling during soak | 1 sample / 5 s logged | 🚫 Blocked | Not implemented; pending hardware | — |
| THRM-004 | Power profiles (10W / 15W / perf) | set/get works | 🚫 Blocked | Not implemented; pending hardware | — |

---

## 9. Interface Contract Status (ICD)

| Interface | Schema | Contract Tests | Status |
|---|---|---|---|
| ICD-1: camera → input-cv | `contracts/input-cv/camera-source.schema.json` v1.1 | 38 tests | ✅ |
| ICD-2: input-cv → audience-state | `contracts/audience-state/cv-observation.schema.json` v1.0 | 46 tests | ✅ |
| ICD-3: audience-state → decision | `contracts/decision-optimizer/audience-state-signal.schema.json` v1.0 | 44 tests | ✅ |
| ICD-4: decision → player | `contracts/player/player-command.schema.json` v1.0 | 42 tests | ✅ |
| ICD-5: creative → player | `contracts/creative/creative-manifest.schema.json` v1.0 | 38 tests | ✅ |
| ICD-6: dashboard-ui ↔ dashboard-api | `contracts/dashboard-api/` (4 schemas) v1.0 | 82 tests | ✅ |
| ICD-7: dashboard-api ↔ PostgreSQL | Alembic migrations | 8 tests (postgres job) | ✅ |
| ICD-8: supervisor ↔ managed services | `contracts/supervisor/service-health-report.schema.json` v1.0 | 20 tests | ✅ |

**Total contract tests: 310 passing**

---

## 10. Open Gaps and Actions

| Gap | Requirement(s) | Action | Owner |
|---|---|---|---|
| CV accuracy unverified | CV-001 through CV-005 | Camera qualification + pilot-scene dataset labeling | Hardware milestone |
| Hardware timing evidence missing | PERF-001, PERF-002, PERF-003, PERF-005 | Timed cold-boot / switch trace on Jetson | Hardware milestone |
| Metrics endpoint not implemented | OBS-003 | Add Prometheus `/metrics` endpoint to each service | Next sprint |
| Log PII lint not automated | PRIV-004 | Add `test_log_pii_lint.py` in integration suite | Next sprint |
| THRM thermal wiring | THRM-001 through THRM-004 | `tegrastats` integration; thermal → freeze signal | Hardware milestone |
| OS-level rollback | PROV-004 | A/B partition or OTA rollback procedure | Future sprint |
| PROV-001 timed dry-run | PROV-001 | Run `provision.sh` with timer on target Jetson | Hardware milestone |

---

## 11. Test Count Summary

| Suite | Location | Count | Status |
|---|---|---|---|
| Contract (ICD 1–8) | `tests/contract/` | 310 | ✅ All passing |
| Unit — input-cv | `services/input-cv/tests/` | 81 | ✅ All passing |
| Unit — audience-state | `services/audience-state/tests/` | 63 | ✅ All passing |
| Unit — decision-optimizer | `services/decision-optimizer/tests/` | 54 | ✅ All passing |
| Unit — player | `services/player/tests/` | 61 | ✅ All passing |
| Unit — creative | `services/creative/tests/` | 46 | ✅ All passing |
| Unit — dashboard-api | `services/dashboard-api/tests/` | 43 | ✅ All passing |
| Unit — supervisor | `services/supervisor/tests/` | 74 | ✅ All passing (40 original + 34 fault injection) |
| Integration | `tests/integration/` | 50 | ✅ All passing |
| Postgres migrations | `services/dashboard-api/tests/test_postgres_migration.py` | 8 | ✅ Pass in CI (postgres job) |
| **Total** | | **790** | ✅ |
