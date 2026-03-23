# Technical Requirements Package

Source file: `Technical Requirements Package for a Privacy-First CV-Driven Adaptive Display Edge Appliance.pdf`
Import type: curated authoritative extract
Document status in source: complete, testable requirements package for a Jetson-class privacy-first edge appliance

---

## Role

This package defines the measurable requirements baseline for a Jetson-class edge appliance that:
- continuously plays digital content
- adapts content selection using on-device computer-vision signals
- enforces privacy-first constraints
- preserves appliance-grade availability, stability, and recoverability

The source is explicitly positioned as a complete, testable requirements package rather than a conceptual wishlist.

## Included specification families named by source

The source says the package includes:
- a Technical Requirements Document (TRD)
- Availability and Reliability specification
- System Validation and Test Plan
- CV Model Performance and Calibration specification
- Resource and Thermal Budget specification
- Deployment and Provisioning specification
- Observability and Debugging specification
- Data Retention and Privacy Enforcement specification
- Security and Access Control specification

## Recommended defaults called out by source

These defaults are framed as adjustable, chosen for predictability and operational simplicity in a solo-founder appliance model.

| Area | Recommended default |
| --- | --- |
| Playback availability SLO (pilot) | 99.5% monthly rolling |
| CV inference cadence | 10 FPS inference, 1 Hz decision loop |
| CV latency | p95 ≤ 150 ms (capture → metadata at 10 FPS) |
| UX stability | dwell ≥ 10 s, cooldown ≥ 5 s, freeze-on-uncertainty |
| Player crash recovery | ≤ 10 s to resume playback |
| Resource budgets | GPU p95 ≤ 85%, CPU p95 ≤ 80%, RAM headroom ≥ 25% |
| Thermal | ≥ 10°C headroom below slowdown threshold under typical operation |

## System context and assumptions carried by source

The requirements package assumes:
- no cloud runtime dependency; playback and adaptation must continue without WAN
- WAN/VPN is allowed for administration and updates
- privacy-first posture: raw frames must not persist and raw video must not egress
- Jetson-class hardware with power/thermal posture grounded in Jetson documentation

## Primary appliance invariant

The source states the defining appliance invariant explicitly:

> playback must be correct and stable even when CV is degraded or offline

This is what the source says distinguishes an appliance from a demo.

## Logical subsystems named by source

The source identifies a reference logical decomposition:
- `SVC-CAPTURE` — camera ingest
- `SVC-CV` — inference
- `SVC-SIGNAL` — smoothing and confidence gating
- `SVC-DECIDE` — policy engine
- `SVC-PLAYER` — playback, caching, switching
- `SVC-LOCALDB` — aggregates and audit logs
- `SVC-ADMIN` — VPN-only admin UI/API
- `SVC-UPDATER` — signed update and rollback

## System and interface requirements distilled from source

The measurable requirements matrix begins with system-level rules such as:

| ID | Requirement | Default target | Acceptance framing | Priority |
| --- | --- | --- | --- | --- |
| SYS-001 | Playback must remain correct if `SVC-CV` fails | 0 playback impact | kill CV; playback uninterrupted | MUST |
| SYS-002 | CV-derived signals must be probabilistic | confidence attached | logs show confidence fields for all signals | MUST |
| SYS-003 | State transitions must be explicit and logged | 100% transitions | audit logs replay state machine | SHOULD |
| SYS-004 | Interfaces must be versioned | semver | contract tests pass with pinned versions | SHOULD |

## Performance targets distilled from source

| ID | Requirement | Default target | Acceptance framing | Priority |
| --- | --- | --- | --- | --- |
| PERF-001 | Time-to-first-frame from power-on | ≤ 60 s | cold boot to stable rendered content in 60 s or less | MUST |
| PERF-002 | Time-to-operational (CV + decision healthy) | ≤ 120 s | health endpoints ready within 120 s | SHOULD |
| PERF-003 | Capture → metadata latency (p95) | ≤ 150 ms @ 10 FPS | timestamp tracing proves p95 target | MUST |
| PERF-004 | Decision loop interval | 1 Hz ±10% | trace shows consistent cadence | SHOULD |
| PERF-005 | Switch execution time (p95) | ≤ 2 s excluding dwell | instrumented switch tests | MUST |
| PERF-006 | Visible blank/black screen during normal operation | 0 target; ≤ 250 ms hard cap | video/frame-grab shows no blank above cap | MUST |
| PERF-007 | Dashboard action response over VPN (p95) | ≤ 1 s | scripted UI/API tests | SHOULD |

The source explicitly uses operator-perceived timing thresholds to justify dashboard responsiveness expectations.

## CV accuracy thresholds distilled from source

The source treats CV as scenario-dependent and requires confidence-gated, representative-scene validation.

| ID | Requirement | Default target | Acceptance framing | Priority |
| --- | --- | --- | --- | --- |
| CV-001 | Presence recall (pilot scenes) | ≥ 0.95 | labeled dataset recall at or above 0.95 | MUST |
| CV-002 | Presence false positives | ≤ 1 / 10 min | false-positive rate on labeled data | MUST |
| CV-003 | Count MAE (10 s windows) | ≤ 0.6 persons | windowed MAE threshold | MUST |
| CV-004 | Count within ±1 (10 s windows) | ≥ 0.90 | at least 90% of windows within ±1 | MUST |
| CV-005 | Tracking ID stability | ≤ 1 ID switch / person / 30 s | tracking stability metric reported | SHOULD |
| CV-006 | Low-confidence gating for optional attributes | 100% gated | replay proves suppression below threshold | SHOULD |
| CV-007 | Optional attributes are coarse and probabilistic only | discrete bins | schema enforces bins + probabilities | CAN |

The source also provides illustrative inference-FPS tradeoffs:
- 5 FPS for lower GPU/thermal use
- 10 FPS as the default balance
- 15 FPS for faster response at higher thermal cost

## UX stability constraints distilled from source

The source explicitly says the goal is **no flicker** and that this must be enforced through:
- dwell
- cooldown
- hysteresis
- freeze-on-uncertainty

This aligns directly with the roadmap and player-reliability posture.

## Resource and thermal budget rules highlighted in source

The source requires continuous monitoring using `tegrastats` and power-mode handling using `nvpmodel`.

Representative requirements captured in the source include:

| ID | Requirement | Default target | Acceptance framing |
| --- | --- | --- | --- |
| THRM-001 | Thermal degrade reduces compute before playback | ≥ 50% FPS reduction | induced-heat test shows degrade of CV first |
| THRM-002 | Protect state freezes adaptation | yes | induced-heat test shows freeze |
| THRM-003 | `tegrastats` sampling | 1 sample / 5 s | logs exist for soak duration |
| THRM-004 | Power profiles implemented | 10W / 15W / perf presets | set/get works |

Core principle carried by source: when thermals are stressed, reduce CV or freeze adaptation before risking playback continuity.

## Failure modes and recovery ladder distilled from source

The source uses explicit self-healing and supervision logic.

Key recovery requirements include:

| ID | Requirement | Default target / behavior | Acceptance framing | Priority |
| --- | --- | --- | --- | --- |
| REC-001 | CV failure does not interrupt playback | 0 impact | kill CV; playback continues | MUST |
| REC-002 | Player crash recovery | ≤ 10 s | kill player; measure restore time | MUST |
| REC-003 | Decision failure freezes stable playlist | freeze | kill decision service; no switching | MUST |
| REC-004 | Escalation ladder implemented | restart → reboot after N | fault injection proves ladder | MUST |
| REC-005 | Storage-full protection | never hit 100% | disk-fill simulation | MUST |
| REC-006 | Boot-loop prevention | safe mode after repeated fails | simulated boot failure | SHOULD |

The ladder described by source follows this general pattern:
- if CV fails, freeze adaptation and keep playlist stable
- if decision fails, freeze last stable decision
- if player fails, restart player first
- only escalate to reboot after player-first recovery attempts fail
- fall through to safe mode when broader recovery fails

## Deployment, provisioning, update, and rollback posture

The source explicitly ties robust updating to:
- redundancy / atomicity
- authenticity of update artifacts
- VPN-only admin plane via WireGuard

Representative provisioning requirements captured by source:

| ID | Requirement | Default target / rule | Acceptance framing |
| --- | --- | --- | --- |
| PROV-001 | First-boot provisioning is bounded | ≤ 10 min | timed dry-run |
| PROV-002 | Device identity is unique and persistent | yes | persists over reboot |
| PROV-003 | VPN-only endpoints | yes | scan from LAN/WAN fails |
| PROV-004 | Rollback procedure tested | yes | `AT-UPDATE` passes |

## Observability and debugging posture

The source treats observability as a first-class operational requirement.

Representative requirements include:

| ID | Requirement | Default target | Acceptance framing |
| --- | --- | --- | --- |
| OBS-001 | Structured logs for all services | JSON lines | log inspection shows required fields |
| OBS-002 | Health endpoints | `/healthz` + `/readyz` | curl checks succeed |
| OBS-003 | Metrics exposure | local endpoint | scrape works |
| OBS-004 | Remote debug limits | no open SSH by default | security audit passes |

The source explicitly frames logs as operational/security records and requires searchable, structured fields.

## Data retention and privacy enforcement posture

The source treats video as potentially personal data and emphasizes minimization.

Representative privacy requirements highlighted in source include:
- no raw imagery retained
- logs must be PII-safe and contain no images or embeddings
- memory/swap posture should be defined to prevent disk leakage
- administrative actions should be auditable

One example captured in the source:
- `PRIV-004` — logs are PII-safe; no images/embeddings; log lint tests pass
- `PRIV-005` — memory/swap posture defined; swap disabled or encrypted preferred
- `PRIV-006` — admin actions auditable; 100% logged

## Security and access-control posture

The requirements package repeatedly reinforces:
- VPN-only administrative exposure
- auditability
- avoidance of broad remote debug exposure
- security scans and access-control verification as part of acceptance

## Acceptance-test orientation

The source is tightly coupled to acceptance testing rather than passive specification. Requirements are written with:
- rationale
- acceptance criteria
- implementation notes
- explicit priority levels

This makes the document directly usable for traceability into the V&V plan and pilot readiness decisions.

## Operational meaning for implementation

This package is the main measurable-completion baseline for:
- startup and recovery performance
- latency and switching behavior
- CV thresholding posture
- thermal and resource budgets
- provisioning and rollback discipline
- observability and privacy enforcement

If the roadmap says *what must exist*, this package says *what measurable thresholds must be met*.
