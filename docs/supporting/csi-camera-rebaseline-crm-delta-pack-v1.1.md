# CSI Camera Rebaseline CRM Delta Pack v1.1

Source file: `Adaptive_Retail_CSI_Rebaseline_CRM_Delta_Pack_v1_1.txt`
Import type: curated repo-native digest from source
Authority: supporting change-control artifact only; not itself an active authoritative baseline

---

## Role

This source records a structured **change-control delta pack** for re-baselining the MVP single-camera pilot from an RTSP/IP-camera ingest path to **CSI/local-device ingest** on the Jetson appliance.

It does **not** by itself replace the active authoritative documents. Instead, it defines the deltas that would need to be absorbed into later formal revisions.

## Why the change exists

The source states that the previous ICD baseline assumed:
- an RTSP IP camera as producer
- DeepStream consuming an RTSP stream
- `rtsp_url` as the core camera configuration field

The change rationale is that for the locked MVP single-device, single-camera appliance:
- the single on-board Ethernet port is better reserved for local router / LAN connectivity
- preserving an RTSP-over-Ethernet camera path would add unnecessary network hardware, cost, installation complexity, and support burden
- a direct local camera path is already within the broader system-architecture envelope
- CSI/local-device ingest is a better fit for the smallest commercially useful MVP

## Core decision recorded in source

> The MVP single-camera pilot baseline changes from RTSP IP-camera ingest to CSI/local-device ingest on the Jetson appliance.

This is described as a **major interface baseline update**, not a minor implementation note.

## Documents the source says must be revised

The delta pack identifies three authoritative documents that would need formal revision to absorb the change:
1. Consolidated ICD v1.0 → v1.1
2. Golden Roadmap V2 → v2.1
3. Pilot Validation Protocol v1.0 → v1.1

It explicitly does **not** require a full SAD rewrite because the architecture document already contemplated local-device ingest options at a broader level.

## Main contract changes captured by the source

### 1. Camera component framing changes
The source replaces the implied MVP camera model of:
- IP camera streaming over RTSP

with:
- a single local camera connected directly to the Jetson through the approved MVP hardware interface
- currently CSI, surfaced to the ingest pipeline as a local video device

### 2. ICD-1 transport and endpoint model changes
The source changes ICD-1 from:
- camera as RTSP server
- DeepStream as RTSP client
- RTSP URL as canonical endpoint form

to:
- local camera device presented by host OS
- DeepStream as local-device client
- local device path and capture parameters, for example `/dev/video0`

### 3. Camera configuration schema changes
A central source delta is the config-schema rewrite from an RTSP-centric shape to a local-device shape.

The old model revolved around fields such as:
- `rtsp_url`
- transport preference
- connect timeout
- reconnect semantics

The new source model revolves around fields such as:
- `source_type`
- `device_path`
- `pixel_format`
- `width`
- `height`
- `fps`
- `startup_timeout_ms`
- `read_timeout_ms`
- `reopen` semantics for local-device recovery

This is a meaningful contract shift because it changes both service configuration and deployment assumptions.

### 4. Example object and operational assumptions
The source also changes the example baseline configuration from an IP-camera URL example to a local-device example using:
- `source_type: local_v4l2`
- `device_path: /dev/video0`
- explicit local capture parameters

This matters because examples are part of how future contributors infer the real baseline.

## Downstream implementation effects named in source

The source identifies several concrete follow-on impacts:
- input-cv configuration loader and validation logic must change
- deployment tooling must provision local-device parameters instead of network camera secrets/URLs
- startup checks must validate local device path, permissions, pixel format, fps, and startup ordering
- reconnect semantics become reopen semantics appropriate to local-device recovery
- bring-up and CI fixtures must be updated accordingly

## Test and conformance work implied by source

The delta pack repeatedly names conformance updates that would need to accompany re-baselining, including:
- local-device ingest validation tests
- JSON schema tests for required fields and invalid configurations
- missing-device and startup failure tests
- device-path existence and permissions checks
- updated example fixtures in config validation and CI assets

This is important because the source treats the change as a contract and verification issue, not merely a hardware swap.

## Governance significance

The strongest governance point in the source is that this change cannot be implemented as a silent drift from the frozen baseline. The source explicitly ties the change to:
- versioned contract updates
- roadmap updates
- pilot-document updates
- conformance testing

That aligns with the project rule that interface changes must be re-baselined rather than smuggled into implementation.

## Practical repository value

This source is useful because it captures the exact *reasoning and scope* of a likely near-term re-baseline:
- lower hardware/support burden
- better appliance fit for a one-camera MVP
- preservation of privacy and local-first behavior
- requirement for formal document updates before implementation is treated as baseline-compliant

## Recommended use in repo

Use this source as:
- change-control context
- rationale for upcoming contract revisions
- a checklist of what must change when ICD v1.1 / roadmap v2.1 / pilot protocol v1.1 are created

Do **not** use it as proof that the active baseline has already changed unless and until those formal revisions are merged.

## Repository note

This repo-native file is a curated digest rather than a line-for-line copy. The uploaded source text remains the higher-fidelity reference for exact wording.