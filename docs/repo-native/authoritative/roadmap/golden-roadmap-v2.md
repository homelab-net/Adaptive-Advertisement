# Golden Roadmap V2

Source file: `Adaptive_Retail_Golden_Roadmap_V2.docx`
Import type: curated authoritative extract
Document status in source: authoritative active roadmap; supersedes Roadmap Addendum v1 and Golden Build Plan v1.1 for active execution
Date in source: 2026-03-17

---

## Role

Golden Roadmap V2 is the active execution roadmap for the privacy-first edge adaptive signage MVP. It consolidates the earlier Golden Build Plan v1.1 and Roadmap Addendum v1 into one execution-oriented baseline while preserving those earlier documents only for historical reference.

The roadmap is not a concept document. It is the build, verification, pilot-readiness, and first-sale progression framework.

## Document-control rule carried by source

The highest revision of every project document must be used first. Older versions remain available for historical reference only and do not override newer baselines unless formally re-baselined.

## Executive intent

The roadmap binds execution to:
- the locked service architecture
- the ICD contract surface
- the Technical Requirements Package
- the Verification and Validation Plan

Advancement is controlled by explicit go / no-go criteria and evidence, not by feature-count completion.

## Locked baseline captured by source

### Product position
- privacy-first adaptive digital signage for small retail businesses
- all visual inference remains local to the device
- no raw image persistence
- no raw frame egress
- customer provides the display
- system runs as a smart signage player with local dashboard and optional VPN-based remote support
- product is an ML-assisted decision system, not a pure ML system and not a freeform generative ad engine

### Locked service model
- `input-cv` — camera ingest, detection, tracking, metadata-only output
- `audience-state` — smoothing, confidence handling, stable state publication
- `decision-optimizer` — rules-first state machine, fallback logic, optimization weighting
- `creative` — approved creative assembly, modifier policy enforcement, manifest production
- `player` — always-on playback, fallback playlist, kiosk rendering runtime
- `dashboard-api` — canonical data-model authority, owner/admin control plane, approvals, analytics, system control
- `postgres` — durable local storage for canonical business objects and append-only operational events
- `supervisor` — health checks, restart ladder, maintenance logic, and safe-mode orchestration

### Locked operating rules
- the screen must never go blank
- WAN is not required for runtime operation
- remote administration is via WireGuard only during pilot and early field operation
- adaptive behavior must stay inside approved policy space
- approval remains mandatory by default
- manual override and safe mode shall always exist
- no blind nightly reboot policy is permitted

## Cross-reference alignment matrix distilled from source

| Source | Locked contribution | Execution effect |
| --- | --- | --- |
| Software Selection Directive | best long-term fit, Jetson compatibility, privacy/local-first architecture, clean integration | prevents short-term convenience choices that force rebuilds later |
| Golden Build Plan v1.1 | stack lock, service layout, creative position, reliability law, build order | defines build sequencing and service ownership |
| Roadmap Addendum v1 | adaptive variant policy, dashboard screens, approvals, manual override | defines constrained creative adaptation and operator controls |
| Consolidated ICD v1.0 | ICD-1 through ICD-4 contract surface | locks camera → CV → state → decision → player flow |
| Additional ICD Addendum v1.0 | ICD-5 through ICD-8 plus ICD-NET-1 | locks creative, dashboard, DB, supervisor, and network surfaces |
| TRD | performance, reliability, privacy, resource, deployment, and acceptance thresholds | defines measurable completion criteria |
| V&V Plan | hard gates, test campaigns, pilot and sales-release evidence | defines go / no-go logic and release readiness |

## Phased execution roadmap distilled from source

The roadmap preserves the technical build order from the older Golden Build Plan but aligns each phase to V&V evidence.

| Phase | Primary scope | In-scope services | Definition of done | Gate | Primary evidence |
| --- | --- | --- | --- | --- | --- |
| 0 | Platform baseline | JetPack, Docker, Compose, WireGuard, Chromium | boot-to-managed-runtime verified; VPN-only admin path works; public exposure blocked; base image reproducible | Build gate | provisioning checklist, network scan, boot log |
| 1 | Vision stack | `input-cv` | stable ingest; metadata-only output; no image persistence; camera reconnect proven | Build gate | CV bring-up log, storage audit |
| 2 | Audience state | `audience-state` | replay-deterministic smoothing; low-confidence suppression; unknown handling stable | Build gate | replay report |
| 3 | Player runtime | `player` | always-on display, kiosk path, fallback bundle, controlled switch behavior acceptable | Build gate | player validation capture |
| 4 | Decision engine | `decision-optimizer` | rules-first keep/switch/fallback logic; stale-state handling; explainable decisions | Build gate | decision trace pack |
| 5 | Creative assembly | `creative` | approved-only rendering; manifest integrity; safe fallback on cache miss or invalid manifest | Build gate | creative conformance report |
| 6 | DB and optimizer | `postgres`, optimizer elements | append-only event flow; cold-start-safe fallback; DB outage does not blank screen | Build gate | persistence outage test |
| 7 | Dashboard | `dashboard-api` + owner control plane | approvals, asset upload, analytics, safe-mode controls, manual override | Pilot entry gate | dashboard UAT |
| 8 | Reliability hardening | `supervisor` and full appliance posture | restart ladder proven; maintenance logic bounded; 24–72h stable run | Pilot entry gate | reliability campaign report |

## Gate framework captured by source

The governing progression model for pilot and first-sale readiness is:

| Gate | Minimum requirement | Required evidence | Decision use |
| --- | --- | --- | --- |
| Technical gate | all hard-gate tests pass; no unresolved critical defects | signed V&V summary, failed-test disposition log | blocks pilot and release |
| Privacy gate | no image retention; no frame egress; no approval bypass; VPN-only admin exposure | privacy audit pack + network audit pack | blocks pilot and release |
| Operational gate | 72h stable run; restart ladder proven; install and remote triage workable | reliability report + install drill + support drill | blocks first paid rollout |
| Operator gate | owner can upload, approve, enable, pause, safe-mode, and review analytics without engineering help | UAT signoff + operator task checklist | blocks customer deployment |
| Commercial gate | adaptive mode shows positive value signal over static with acceptable support burden | pilot business validation report + customer note | blocks first sale |

### Hard test set named in source
- `AT-BOOT` — cold boot to first frame and operational state
- `AT-SWITCH` — controlled switching with no visible blank above allowed threshold and no flicker
- `AT-CV-LAT` — capture-to-metadata latency at target cadence
- `AT-CV-ACC` — pilot-scene recall, false positive rate, and count accuracy thresholds
- `AT-SOAK-72H` — long-duration stability, resource budgets, and thermal behavior
- `AT-FAULT` — fault injection across CV, decision, player, DB, and supervisor ladder
- `AT-PRIV-STORE` / `AT-PRIV-EGRESS` — privacy storage and egress audits
- `AT-UPDATE` — signed update acceptance, rollback, and no unrecoverable state
- `AT-STATIC-VS-ADAPTIVE` — business-value comparison against static mode using the same approved content library

## Milestones and release logic distilled from source

| Milestone | Entry condition | Exit criteria | Primary artifact |
| --- | --- | --- | --- |
| Integrated system complete | all major services run on target hardware | all build-phase verification campaigns complete | build verification pack |
| Pilot-ready | integrated system complete | all hard technical, privacy, and network gates pass; operator UAT ready | pilot entry memo |
| Pilot complete | pilot-ready and customer site active | static-vs-adaptive report complete; support burden reviewed; customer feedback collected | pilot closeout report |
| Sales-ready | pilot complete | all commercial gates pass; no unresolved release blockers remain | sales release memo |

## First-sale rule carried by source

The system shall not be represented or sold as an always-improving AI platform until the first pilot proves:
- stable operation
- approval-safe adaptive behavior
- a positive adaptive-versus-static signal using the same approved content library

## Immediate-use implementation checklist captured by source

The source explicitly directs execution to:
1. freeze the current ICD baseline and generate conformance tests for each interface before service-level divergence occurs
2. build the platform baseline image and Docker Compose stack with health checks, deterministic startup order, and VPN-only admin posture
3. implement metadata-only CV output and privacy-negative tests before downstream analytics or optimization work proceeds
4. stand up the player fallback path before enabling live adaptive switching
5. implement dashboard approval workflow before enabling any adaptive text or color runtime eligibility
6. generate SQLAlchemy models and migrations consistent with canonical write authority through `dashboard-api`
7. implement supervisor health probes and restart ladder controls before beginning 72h soak testing
8. write the pilot protocol for static-vs-adaptive comparison before field deployment so business validation remains disciplined

## Authority and delta note

This extract reflects the active v2.0 roadmap. The separate CSI rebaseline delta pack indicates a likely future v2.1 update, but that delta pack is not itself the authoritative roadmap until formally merged.
