# CRM-002 — RTSP / IP-Camera Baseline to CSI / Local-Device Ingest Rebaseline

Date: 2026-03-23
Status: Approved
Owner: Founder
Driver / Type: architecture correction / implementation-fit rebaseline

---

## Summary

The MVP single-camera ingest path is approved to move from the earlier RTSP / IP-camera baseline to **CSI / local-device ingest** on the Jetson appliance.

## Rationale

The original RTSP/IP-camera posture is no longer the best fit for the locked MVP because:
- the single on-board Ethernet port is better reserved for local router / LAN connectivity
- RTSP camera transport adds unnecessary hardware, setup complexity, and support burden
- local-device ingest is better aligned to the smallest commercially useful single-device appliance
- the broader architecture baseline already allows local-device ingest without requiring a full architectural rewrite

## Baseline references affected

- Consolidated ICD v1.0
- Golden Roadmap V2
- Pilot Validation Protocol v1.0
- CSI Camera Rebaseline CRM Delta Pack v1.1
- Founder Direction — CSI / Local-Device Ingest Rebaseline

## Options considered

### Option A — keep RTSP / IP-camera baseline
Rejected for MVP because it preserves avoidable hardware and installation overhead.

### Option B — rebaseline to CSI / local-device ingest
Approved because it better matches MVP hardware simplicity, supportability, and appliance fit.

## Implementation impact

### Services / config
- `input-cv` configuration and validation must move from RTSP-centric fields to local-device fields
- CI fixtures and sample configs must be updated accordingly
- startup and recovery logic must use local-device reopen semantics

### Pilot hardware assumptions
- camera path = CSI/local-device
- pilot NVMe default = 256 GB
- 7-inch HDMI screen remains optional bench / service accessory only

### Validation impact
- add missing-device, permission-failure, and reopen-behavior validation
- remove RTSP endpoint configuration as MVP pilot requirement

## Required document updates

- Consolidated ICD → v1.1 CSI/local ingest revision
- Golden Roadmap → v2.1 CSI/local ingest revision
- Pilot Validation Protocol → v1.1 CSI/local ingest revision

## Required test updates

- config-schema tests for local-device source object
- invalid `device_path` tests
- device permission failure tests
- local-device startup failure tests
- reopen / recovery tests
- updated bring-up and pilot qualification fixtures

## Disposition

Approved founder direction recorded and formal rebaseline package initiated.

## Folded Into Rev

Pending merge of:
- consolidated-icd-v1.1-csi-local-ingest.md
- golden-roadmap-v2.1-csi-local-ingest.md
- pilot-validation-protocol-v1.1-csi-local-ingest.md
