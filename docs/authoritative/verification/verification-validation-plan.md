# Verification and Validation Plan

Source file: `Adaptive_Retail_Advertising_VV_Plan.pdf`
Import type: curated authoritative extract
Document ID in source: `VVP-ADAPTIVE-EDGE-MVP-v1.0`
Date in source: 2026-03-17
Purpose in source: define the complete verification and validation program, close remaining gaps, and establish sales-release criteria once the system passes

---

## Role

This plan converts the architecture, ICDs, roadmap/baseline set, and Technical Requirements Package into a field-ready V&V program.

Its role is not merely to confirm that software works in a lab. It defines the evidence package required to prove that the product is:
- safe to deploy
- stable enough to support
- commercially credible
- ready to enter a paid pilot or first-sale motion

## Sales-release principle carried by source

The system is commercially ready only when it passes:
- technical verification
- pilot validation
- operator usability checks
- privacy audits
- business-value proof against a static baseline using the same approved content library

## Governing basis and scope distilled from source

The V&V plan inherits all locked project constraints and does not redefine architecture.

The source explicitly maps the baseline as follows:
- Golden Build Plan v1.1: locked product definition, privacy boundary, MVP scope, service architecture, phased deployment order, reliability law, pilot experiment requirement, and success metrics
- Roadmap Addendum v1: locked adaptive variant policy, dashboard surface, manual approval requirement, non-bypassable approvals, and operator controls
- Consolidated ICD + Interface Addendum: versioned interface contracts, internal/external exposure rules, metadata-only privacy posture, and supervisor/network requirements
- Technical Requirements Package: measurable performance targets, acceptance tests, availability and reliability thresholds, calibration requirements, deployment constraints, observability requirements, and retention/security expectations

## V&V objectives captured by source

| Objective | Question answered | Primary evidence | Release impact |
| --- | --- | --- | --- |
| Requirement verification | Did the system meet each locked technical requirement? | traceability matrix, automated tests, measured logs | blocks technical release |
| System validation | Does the appliance behave correctly in the target store environment? | pilot scene tests, soak tests, operator walkthroughs | blocks pilot deployment |
| Commercial validation | Does adaptive mode create enough value versus static rotation? | A/B pilot analysis, owner feedback, support burden review | blocks first paid rollout |
| Compliance assurance | Did the system preserve privacy, approvals, and local-first boundaries? | storage audit, egress audit, approval bypass tests, network scans | blocks customer-facing claims |

## Test strategy by level distilled from source

| Level | Purpose | Owner | Entry | Exit |
| --- | --- | --- | --- | --- |
| Unit | verify local logic, schema enforcement, safety rules, approval logic, state-machine transitions | service owner | code complete | all critical unit tests green |
| Contract | verify ICD conformance, versioning, privacy flags, ordering, idempotency, and reject behavior | backend + CV + frontend | schemas frozen | contract suite green on CI |
| Integration | verify services interoperate across camera, CV, audience-state, decision, creative, player, dashboard, DB, and supervisor | system integrator | containers deployable | cross-service scenarios pass |
| System | verify whole-appliance behavior including boot, playback continuity, privacy, recovery, updates, and observability | founder/system owner | stable integrated image | system campaign passes |
| Pilot validation | verify target-store usability and business value against static baseline | founder + pilot customer | system campaign passed | pilot exit criteria achieved |
| Commercial release | verify supportability, documentation, install repeatability, and sales-proof package | founder | pilot validation passed | release board approves first-sale status |

## Requirement traceability highlights from source

The source explicitly marks the following as hard-gate expectations:
- screen must never go blank; fallback behavior must exist
- no raw images, clips, biometric identifiers, or embeddings stored or egressed
- adaptive behavior must stay within approved policy space and manual approval remains mandatory by default
- WAN-independent runtime and remote administration via WireGuard only
- adaptive mode must be compared to static mode using the same approved library
- owner must feel in control; manual override and safe mode must always exist

## Build-phase verification campaigns by deployment sequence

| Campaign / phase | Scope | Key checks | Pass criteria | Evidence | Gate type |
| --- | --- | --- | --- | --- | --- |
| Phase 0 Platform Baseline | JetPack, Docker, WireGuard, Chromium, boot services | boot to managed runtime; remote admin only via VPN; no public exposure | boot-to-runtime verified; VPN works; WAN not required for playback shell | provisioning checklist + scan report | Build gate |
| Phase 1 Vision Stack | `input-cv` + DeepStream + tracker | stable ingest; no image persistence; camera reconnect; metadata-only output | 24h stable ingest; privacy flags false; reconnect works | CV bring-up log + storage audit | Build gate |
| Phase 2 Audience State | smoothing and confidence logic | stable state transitions; unknown handling; replay consistency | deterministic replay outputs; low-confidence suppression works | replay report | Build gate |
| Phase 3 Player Runtime | React/Vite player + kiosk mode + fallback bundle | always-on display; asset preload; fallback route; no flicker baseline | no blank on controlled switch; fallback renders offline | player validation capture | Build gate |
| Phase 4 Decision Engine | rules-first decisioning | keep/switch/fallback logic; explainability; stale-state handling | decision logs explain every switch; stale inputs rejected | decision trace pack | Build gate |
| Phase 5 Creative Assembly | manifest generation and policy enforcement | approved-only rendering; manifest integrity; cache-miss behavior | unapproved manifest always rejected; cache miss falls back safely | creative conformance report | Build gate |
| Phase 6 DB and Optimizer | event storage, optimizer, metrics | append-only events; cold-start fallback; no DB dependency for playback | DB outage does not blank screen; events replayable | persistence outage test | Build gate |
| Phase 7 Dashboard | owner control plane | asset upload, approvals, analytics, safe-mode controls | approval workflow complete; manual override works | dashboard UAT | Pilot entry gate |
| Phase 8 Reliability Hardening | supervisor, health checks, maintenance | restart ladder, maintenance-window logic, 72h run | 24–72h stable; restart ladder proven | reliability campaign report | Pilot entry gate |

## Core system verification campaigns explicitly named in source

The source builds around hard system drills including:
- boot and startup validation
- controlled switch behavior
- CV latency validation
- privacy storage and privacy egress audits
- fault injection across service boundaries
- update and rollback safety
- static-versus-adaptive commercial comparison

## Validation in target pilot environment distilled from source

The pilot environment described by source is a small, cooperative retail site such as a coffee shop or quick-service environment with:
- one camera
- one display
- moderate traffic
- relatively stable indoor lighting

Validation areas explicitly named by source:
- scene variability: daylight, low light, glare, occlusion, camera jitter
- operator usability: setup, approval workflow, safe mode, analytics check
- commercial signal: static vs adaptive on same content library
- operational fit: open hours, off-hours update window, network interruptions
- supportability: remote diagnosis over WireGuard

## Gap closure items not fully covered by existing TRD

The source explicitly identifies commercial-readiness gaps that need dedicated evidence:
- commercial value threshold not explicitly operationalized → run a pilot A/B protocol with pre-declared metrics and founder debrief → pilot business validation report
- support burden under real pilot conditions → log support tickets, founder time spent, on-site visits avoided, remote resolution rate → support burden ledger
- install repeatability for non-technical customers → execute timed install dry-runs using only install guide and provisioning checklist → installation verification report
- camera SKU and mounting repeatability → validate at least one chosen camera and mounting SOP across multiple installs → camera qualification report
- sales-proof evidence package → assemble a customer-safe proof pack with uptime, privacy, approvals, and pilot uplift summary → sales readiness binder

## Commercial readiness and sales-release gate distilled from source

Passing engineering tests alone is not sufficient for first sale. The system becomes sales-ready only when the following gates pass:

| Gate | Minimum requirement | Evidence required | Decision |
| --- | --- | --- | --- |
| Technical gate | all hard-gate tests pass; no unresolved critical defects | signed V&V summary and failed-test disposition log | pass / hold |
| Privacy gate | no image retention; no frame egress; no approval bypass path; VPN-only admin exposure | privacy + network audit pack | pass / hold |
| Operational gate | 72h stable run; restart ladder proven; install within planned window; remote triage workable | reliability report + install drill + support drill | pass / hold |
| Operator gate | owner can upload, approve, enable, pause, safe-mode, and review analytics without engineering help | UAT signoff + task checklist | pass / hold |
| Commercial gate | adaptive mode shows positive value signal over static mode and customer expresses willingness to continue/pay | pilot business validation report + customer note | pass / hold |

### First-sale rule carried by source

Do not sell the system as an always-improving AI platform until the first pilot proves:
- stable operation
- approval-safe adaptive behavior
- a positive adaptive-versus-static signal using the same approved content library

## Evidence package and deliverables named by source

- V&V summary report with pass/fail status by gate
- traceability matrix mapping every hard requirement to evidence
- boot, switch, fault-injection, privacy, and update drill reports
- 72h soak report with tegrastats/resource graphs and defect log
- pilot validation report with static versus adaptive comparison
- support burden report: time spent, issues encountered, remote resolution rate
- customer-safe sales proof pack: privacy posture, uptime, approval controls, and pilot outcome summary
- install/provisioning checklist and rollback procedure

## Operational use

This document is the controlling release-readiness framework. It is the main source for deciding when build-complete becomes pilot-ready, when pilot-ready becomes pilot-complete, and when pilot-complete becomes sales-ready.
