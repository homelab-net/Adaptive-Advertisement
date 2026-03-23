# Golden Roadmap V2.1 — CSI / Local-Device Ingest Revision

Supersedes in scope: `golden-roadmap-v2.md` for the MVP single-camera ingest and pilot hardware baseline
Source basis: active roadmap v2.0 + CSI rebaseline delta pack + founder direction note
Status: active intended authoritative revision for MVP once merged
Date: 2026-03-23

---

## Revision purpose

This revision aligns the execution roadmap with the now-approved MVP hardware direction:

> **CSI / local-device ingest is the active MVP rebaseline path.**

The roadmap is updated so build order, hardware assumptions, pilot preparation, and validation no longer implicitly depend on RTSP / IP-camera ingest for the single-camera appliance.

## Revised MVP hardware posture

### Camera
- single local camera connected directly to Jetson through approved local interface
- MVP planning assumption: CSI/local-device ingest
- RTSP/IP-camera ingest is no longer the practical MVP baseline

### Storage
- pilot default: 256 GB NVMe
- rationale: safer pilot headroom for bounded local retention, rollback artifact, asset cache, and operational comfort without unnecessary overbuild

### Small local screen
- 7-inch HDMI-class screen may be used as optional bench / service accessory only
- not part of the core deployed signage runtime
- customer-provided display remains the real signage endpoint

## Revised build and bring-up order

The roadmap phases remain structurally the same, but the camera and early bring-up assumptions are revised.

### Updated platform / bring-up posture
1. Jetson platform baseline
2. CSI / local camera bring-up and qualification
3. local-device `input-cv` pipeline bring-up
4. metadata-only output validation
5. player fallback path verification
6. downstream audience-state and decision integrations

### Immediate implication
Do not spend implementation effort on RTSP/IP-camera setup as the MVP path when building service scaffolding, config models, or validation fixtures.

## Revised early-phase expectations

### Phase 0 Platform Baseline
Unchanged in principle:
- JetPack / OS baseline
- Docker / Compose runtime
- Chromium / kiosk posture
- WireGuard-only admin path
- reproducible image / provisioning posture

### Phase 1 Vision Stack — revised expectation
`input-cv` phase is now evaluated against:
- local-device discovery and validation
- CSI/local camera bring-up stability
- metadata-only output
- no image persistence
- local-device reopen behavior

Artifacts should reflect local-device ingest rather than RTSP stream negotiation.

## Revised pilot preparation assumptions

Pilot preparation shall assume:
- local camera physically mounted to appliance/display solution
- local device-path validation on target Jetson
- lens / field-of-view alignment for real retail placement
- mixed-light and low-light checks on local camera hardware

Remove assumptions that pilot readiness depends on:
- RTSP endpoint configuration
- network camera credentials
- LAN camera discovery
- network jitter behavior for camera transport

## Revised execution rule for contributors

Until a later formal revision changes it, contributors shall treat the following as the working MVP truth:
- camera ingest path = CSI / local-device
- storage default = 256 GB NVMe for pilot builds
- small 7-inch screen = optional service accessory only

## Required downstream alignment

This roadmap revision expects alignment in:
1. ICD revision for local-device camera configuration and startup/reopen semantics
2. pilot protocol revision for camera qualification and local-device validation steps
3. input-cv service scaffolding, config schema, and CI fixtures
4. BOM and appliance bring-up documentation

## Milestone / gate impact

### Technical gate
Now includes proof of:
- local-device camera qualification on target Jetson
- stable local ingest startup
- local-device reopen behavior
- metadata-only output from local ingest path

### Pilot entry gate
Now includes proof of:
- camera mount and local cable/connector suitability
- field-of-view fit for pilot scene
- mixed-light and low-light qualification

### Commercial gate
Unchanged in principle. Static-vs-adaptive value proof still governs first-sale claims.

## Scope and non-scope reminder

This revision changes ingest-path assumptions only. It does **not** expand scope into:
- multi-camera fusion
- cloud-dependent runtime
- freeform generative ad creation
- public remote administration

## Repository interpretation rule

After merge, this revision should be treated as the controlling roadmap baseline for MVP single-camera ingest and related pilot hardware defaults.
