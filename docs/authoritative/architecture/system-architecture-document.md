# System Architecture Document

Source file: `System Architecture Document for a Privacy-First Edge CV Ad Platform on Jetson.pdf`
Import type: curated authoritative extract
Document role in source: architecture baseline for explicit system boundaries, trust boundaries, and data-retention boundaries

---

## Role

The System Architecture Document exists to freeze the architectural boundaries of the privacy-first edge adaptive signage system so that downstream documents such as ICDs, requirements, operations, and testing can be written once and remain stable.

The source explicitly frames the SAD as an architecture description with explicit stakeholders, concerns, and views rather than a loose diagram-plus-prose document.

## Core architectural purpose carried by source

The architecture document is used to define:
- service boundaries
- trust boundaries
- deployment boundaries
- data-retention boundaries
- fault and recovery boundaries

Its main job is to answer what is inside the system and how parts interact, at a level that enables independent implementation and integration.

## Privacy-first architecture law distilled from source

The strongest architectural rule in the source is that privacy must be engineered as an enforceable system property, not treated as an after-the-fact policy statement.

That means, in practical terms:
- pixels may exist only transiently during processing
- retention sinks that would persist raw frames must be excluded or disabled
- logs and message schemas must be data-minimizing
- metadata must be the only durable and egress-eligible form of audience information

The source also warns that silent retention risks are real in video pipelines and must be explicitly designed out.

## Unspecified items intentionally left open by source

The source explicitly leaves some platform choices open at the architecture level, including:
- specific Jetson module variant
- camera interface type (CSI / USB / RTSP)
- whether the decision engine is strictly on-device or partially split with a remote control plane
- exact player implementation choice
- exact network environment

This is important because the architecture document is supposed to define stable boundaries without prematurely locking every deployment detail.

## Architecture views implied by source

The source organizes the system around a professional SAD posture resembling:
- context view
- building-block / service decomposition view
- runtime interaction view
- deployment view
- cross-cutting concerns view
- risk / assumptions view

## Core logical system decomposition carried by source

The system is described as an edge appliance composed of:
- camera ingest and CV inference on Jetson-class hardware
- an audience-state / smoothing layer that transforms raw CV observations into stable state
- a decision layer that applies rules and bounded optimization to approved creative choices
- a player layer that renders approved manifests and preserves always-on playback
- a local dashboard / API and durable local storage layer
- a supervision / recovery layer that keeps the appliance alive through faults

## Hard architectural invariants reinforced by source

The architecture document reinforces the same non-negotiable invariants visible elsewhere in the baseline:
- local-first operation
- privacy-first metadata-only posture
- no raw image retention
- no raw frame or video egress
- no identity recognition or biometric storage
- playback as a hard dependency
- degraded CV or back-office services must not blank the display
- operational recoverability as a core architecture concern

## Trust-boundary posture distilled from source

The source distinguishes among several types of boundaries:
- camera / raw-pixel processing boundary
- intra-device service boundary
- local dashboard and administration boundary
- remote support / control-plane boundary
- durable storage boundary

The purpose is to keep privileged access, sensitive data, and failure domains clearly separated rather than implicitly blended.

## Data-retention and data-movement posture

The architecture document frames data handling around where data may exist and for how long.

### Allowed posture
- transient pixels in RAM / GPU memory during inference
- metadata-only outputs for durable state, eventing, and analytics
- bounded local storage of business objects, append-only events, and operational telemetry

### Forbidden or tightly constrained posture
- raw frame persistence
- raw video egress
- reversible biometric artifacts
- architecture that makes remote services mandatory for runtime operation

## Deployment posture carried by source

The source positions the system as an edge appliance on Jetson with a deployment model that supports:
- on-device or edge-adjacent CV runtime
- local-first playback and decisioning
- local or edge-local control plane surfaces
- deployment documentation that can later map cleanly to Docker/Jetson operational reality

The architecture document also anticipates a deployment view that cleanly separates in-store runtime from any optional remote support or management plane.

## Runtime interaction model distilled from source

The architectural runtime shape implied by the source is:
1. camera frames are ingested locally
2. CV pipeline performs inference / tracking
3. only metadata is emitted downstream
4. metadata is smoothed into stable audience state
5. decision logic evaluates latest stable state and policy constraints
6. player receives commands or manifests and continues rendering approved content
7. supervision monitors health and applies restart / recovery ladder logic when required

## Cross-cutting concerns explicitly emphasized by source

### Privacy
Privacy is a system property and must be reflected in service interfaces, storage choices, log policy, and deployment configuration.

### Reliability
Reliability is not limited to process uptime. It includes graceful degradation, explicit fallback behavior, and appliance-style recoverability.

### Maintainability
The source favors architecture views and boundaries that let downstream documents stay stable and let implementation proceed in parallel.

### Verification readiness
The architecture must be concrete enough that ICDs, requirements, and test plans can be derived without ambiguity.

## Failure-mode posture distilled from source

The architecture document treats failure behavior as part of architecture, not only an operations concern.

Key architectural expectations implied by source:
- CV failure should degrade adaptation, not playback
- downstream message and state boundaries should make stale / missing input explicit
- player continuity should be protected even when other services are unhealthy
- recovery mechanisms should be designed in at the architecture level, not bolted on later

## Why this document matters relative to other baselines

- the roadmap controls execution sequence and gate logic
- the ICDs control interface contracts
- the requirements package controls measurable thresholds
- the V&V plan controls evidence and release readiness
- the architecture document controls the *shape* of the system those documents sit on

This is why it is foundational even when it leaves some implementation details intentionally unspecified.

## Practical implementation meaning

For repo and code work, this architecture document should be treated as the authoritative reason to preserve:
- modular service boundaries
- metadata-only CV interfaces
- local-first runtime independence
- trust-boundary clarity
- fallback-first appliance behavior
- deployment separation between runtime plane and optional support plane

## Authority and delta note

This extract represents the current architecture baseline. Later camera-interface re-baselining can change specific ICD assumptions without necessarily requiring a full SAD rewrite, so long as the higher-level boundary model remains intact.
