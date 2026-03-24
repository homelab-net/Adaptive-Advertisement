# Founder Direction — CSI / Local-Device Ingest Rebaseline

Date: 2026-03-23
Status: approved founder direction; requires formal document rebaseline to become active authoritative baseline
Scope: MVP single-camera ingest path and closely related pilot hardware defaults

---

## Decision summary

The MVP single-camera ingest direction is now set to:

> **CSI / local-device ingest is the rebaseline path for the MVP.**

This means the project should move away from the earlier RTSP / IP-camera assumption for the single-camera Jetson appliance and formalize local-device ingest as the intended active baseline.

This note records direction and implementation posture. It does **not** by itself replace the active authoritative ICD / roadmap / pilot documents. Those documents must still be revised and merged.

## Why this direction is being locked

The direction is consistent with the existing CSI rebaseline delta logic already preserved in the repository:
- the single on-board Ethernet port is better reserved for local router / LAN connectivity
- an RTSP-over-Ethernet camera path adds avoidable hardware, installation complexity, and support burden
- local-device ingest is a better fit for the smallest commercially useful single-camera MVP appliance
- the change remains compatible with the broader architecture posture because the architecture baseline already allows local-device ingest options at a higher level

## Founder hardware posture associated with this direction

### 1. Camera path
- **Lock direction:** CSI / local-device camera ingest for the MVP
- **Immediate implication:** do not continue treating RTSP / IP-camera ingest as the practical MVP path
- **Formal next step:** revise the authoritative documents so the repo no longer carries the old RTSP baseline and new CSI direction in parallel

### 2. NVMe storage default
- **Pilot default:** 256 GB NVMe
- **Reason:** safer pilot headroom without drifting into unnecessary overbuild; consistent with bounded local retention, rollback, asset cache, and operational comfort

### 3. Small local screen posture
- **7-inch HDMI screen:** optional bench / service accessory only
- **Not part of core deployed signage runtime:** customer-provided display remains the real signage endpoint
- **Constraint:** do not let a service screen complicate the appliance BOM or deployed display strategy

## Camera qualification posture

The CSI/local-device direction is locked, but the exact camera SKU still requires qualification on the actual Jetson target and deployment shape.

Before a specific CSI camera SKU is treated as fully baseline-safe, verify at minimum:
- exact connector and cable compatibility with the target Orin platform
- bring-up reliability on the JetPack / L4T version intended for shipment
- lens / field-of-view fit for actual retail mounting geometry
- low-light and mixed-light behavior in realistic pilot scenes
- startup and recovery behavior under appliance conditions

## Required formal rebaseline work

This founder direction should be absorbed into the authoritative corpus through the following revisions:

1. **Consolidated ICD**
   - replace RTSP/IP-camera ingest assumptions with local-device CSI / V4L2-style assumptions
   - revise configuration schema examples and validation expectations accordingly

2. **Golden Roadmap**
   - revise the MVP hardware/input baseline to CSI / local-device ingest
   - ensure build order, bring-up, and pilot assumptions align to local-device camera hardware

3. **Pilot Validation Protocol**
   - revise camera qualification, install, and pilot validation steps to the actual CSI/local-device path

## Repository interpretation rule

Until those formal revisions are merged:
- this decision note should be treated as approved founder direction
- the earlier RTSP baseline should be treated as superseded in practice for MVP planning
- the authoritative documents remain formally unrevised and therefore still need explicit update work

## Execution guidance

Use this direction to guide:
- BOM and pilot hardware selection
- repo skeleton and service scaffolding assumptions
- camera bring-up and validation planning
- upcoming document rebaseline work

Do **not** use this note as a shortcut to skip the formal ICD / roadmap / pilot-document revision process.
