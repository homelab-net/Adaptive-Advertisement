# Pilot Validation Protocol v1.1 — CSI / Local-Device Ingest Revision

Supersedes in scope: `pilot-validation-protocol-v1.0.md` for MVP camera qualification, install, and ingest validation
Source basis: pilot protocol v1.0 export + CSI rebaseline delta pack + founder direction note
Status: active intended authoritative revision for MVP once merged
Date: 2026-03-23

---

## Revision purpose

This revision aligns pilot execution with the active MVP rebaseline path:

> **single-camera pilot ingest shall use CSI / local-device camera input on the Jetson appliance**

The protocol is updated so camera bring-up, pilot install checks, and field validation reflect the local-device ingest path rather than RTSP / IP-camera transport.

## What changes in this revision

### Removed as MVP pilot assumptions
- RTSP endpoint setup and credential validation
- network camera discovery
- camera transport jitter analysis as a primary ingest risk
- pilot dependence on LAN camera reachability

### Added / emphasized
- local device-path validation, for example `/dev/video0`
- local connector / ribbon / mount qualification
- startup failure behavior when local camera is absent or misconfigured
- bounded reopen behavior for local-device ingest faults
- field-of-view and mixed-light checks on the actual local camera hardware

## Revised pilot entry criteria

The pilot shall not start until the following local-camera conditions are evidenced.

| Entry gate | Minimum condition | Evidence artifact |
| --- | --- | --- |
| Camera hardware qualification | chosen CSI/local camera SKU physically fits target Jetson and intended mount path | camera qualification sheet |
| Local-device bring-up | configured `device_path` discovered and opens successfully on target Jetson image | bring-up log |
| Parameter validation | intended width/height/fps/pixel-format accepted by target camera stack | capture validation log |
| Missing-device behavior | absent or disconnected camera does not interrupt playback; adaptation degrades safely | fault-injection result |
| Reopen behavior | ingest recovers or degrades safely under local camera fault | reopen drill report |
| Privacy posture | no raw imagery retained or exported from local ingest path | privacy audit pack |

## Revised install / provisioning expectations

On-site or pilot-prep install shall include:
1. verify physical camera mount and connector seating
2. verify ribbon / local-device cable integrity and strain relief
3. verify local device enumeration on the target Jetson
4. verify configured `device_path`
5. verify expected capture parameters
6. verify field-of-view against intended traffic zone
7. verify mixed-light / glare behavior in the actual mounting position

## Revised camera SKU and mount qualification sheet

The camera qualification record shall now include at minimum:
- camera make / model / SKU
- interface type (`CSI` / local-device class)
- ribbon / connector / adapter details if any
- target device path on Jetson
- lens and field-of-view
- mount type and mounting geometry
- lighting notes
- glare / reflection notes
- startup success on intended JetPack / L4T version
- reopen / recovery result
- pass / fail against pilot scene classes

## Revised experimental-control rule

The ingest-path change is not to be treated as a pilot variable.

During the pilot window:
- camera hardware path is fixed
- ingest configuration is fixed
- no ad hoc swap back to RTSP / IP-camera path is allowed
- if ingest instability is discovered, resolve via documented local-device qualification or mark the pilot blocked

## Revised hard operational metrics

The core operational metrics remain unchanged in principle, but local-device ingest adds specific checks.

| Metric | Target / standard | Why it exists |
| --- | --- | --- |
| Playback availability | target at or above 99.5% during pilot window | appliance credibility |
| Visible blank events | none outside allowed controlled-switch threshold | playback continuity |
| Controlled switch blank time | no visible blank above 250 ms | smoothness |
| Player recovery | playback resumes within 10 s after player crash | reliability |
| Capture-to-metadata latency | p95 at or below 150 ms at target cadence | real-time responsiveness |
| Local camera startup | startup succeeds within configured window or degrades safely | ingest resilience |
| Local camera reopen | bounded retries with safe degrade if unrecovered | ingest resilience |
| Privacy violations | zero retained imagery and zero raw frame egress | core product rule |

## Revised failure-handling posture

### Local camera missing at startup
Required behavior:
- playback remains available
- adaptation remains disabled / frozen
- system exposes ingest-degraded health state
- no boot-loop or player disruption is introduced

### Local camera disconnect / read failure
Required behavior:
- bounded reopen attempts
- health state updated
- no display blanking
- supervisor may classify local ingest degraded, but player continuity remains protected

## Revised validation scenarios

The pilot validation set shall include local-device-specific drills:
- invalid `device_path`
- device permission failure
- camera absent at boot
- camera available but unsupported capture format
- ribbon reseat / reconnect recovery test where safe to perform
- mixed-light and glare qualification on installed mount geometry

## Revised appendices

### Appendix A — Install and Provisioning Checklist
Add explicit local-device checks:
- camera physically seated
- ribbon / local cable routed and strain-relieved
- device enumerates correctly
- configured `device_path` matches observed state
- capture parameters validated

### Appendix B — Camera SKU and Mount Qualification Sheet
Replace RTSP-style assumptions with local-device details and recovery results.

### Appendix C — Support Burden Ledger
Track whether issues are:
- camera hardware / connector
- local-device enumeration
- capture parameter mismatch
- mount / field-of-view issue
- lighting suitability issue

## Repository interpretation rule

After merge, this revision should be treated as the controlling pilot protocol for the MVP single-camera ingest path.
