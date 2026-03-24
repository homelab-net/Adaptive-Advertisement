# Decision: Camera SKU Candidate Selection

**Date:** 2026-03-23
**Status:** Candidate — qualification pending
**Decider:** Founder

---

## Decision

The candidate camera SKU for MVP is:

**Arducam Day and Night Vision IMX477 HQ Camera for Jetson Orin NX**
- Sensor: Sony IMX477, 12 MP
- Interface: CSI (ribbon/MIPI CSI-2)
- Feature: Automatic IR-Cut switching (all-day image, day and night vision)
- Target platform in product name: Jetson Orin NX (same Orin-class connector family as Orin Nano)

---

## Rationale

1. **Interface compatibility** — CSI/MIPI CSI-2 is directly compatible with the locked `source_type: local_v4l2` ingest path (decisions/2026-03-23-csi-local-ingest-founder-direction.md). No RTSP or USB adapter required.

2. **Sensor suitability** — IMX477 (12 MP) provides significant resolution headroom for inference crop windows at a fixed mounting geometry. Oversampling for a 1080p inference path is preferable to tight pixel budgets.

3. **Lighting coverage** — Automatic IR-Cut switching covers mixed-light retail environments (bright daylight near windows, dim interior zones) without manual intervention. Day/night capability supports extended retail hours.

4. **Vendor ecosystem** — Arducam provides Jetson-specific drivers and bring-up documentation for the IMX477 on Orin-class hardware, reducing integration risk relative to generic CSI sensors.

---

## Qualification requirements before pinning as baseline

Per ICD v1.1 Section "Camera qualification implications", this SKU is not baseline-safe until all of the following are verified on target hardware:

| Check | Status |
|---|---|
| Connector and ribbon compatibility with Jetson Orin Nano | Not verified |
| Successful bring-up on target JetPack 6.x / L4T 36.x point release | Not verified |
| Expected field-of-view for pilot mounting geometry | Not verified |
| Mixed-light / low-light pilot-scene suitability | Not verified |
| Stable startup and reopen behavior under appliance conditions | Not verified |
| V4L2 device enumeration at `/dev/video0` (or configured path) | Not verified |
| Capture at configured pixel format (NV12), width, height, and fps | Not verified |

---

## Impact on JetPack point-release pin

The JetPack point release within the locked 6.x / L4T 36.x family will be pinned after this camera SKU completes bring-up verification. Camera driver compatibility is the primary constraint on point-release selection.

---

## Next action

Acquire the camera, connect to the target Jetson Orin Nano, and execute bring-up verification against the checklist above. Record results in this file and update `docs/living/system-development-snapshot.md` when qualification is complete or a blocking issue is found.
