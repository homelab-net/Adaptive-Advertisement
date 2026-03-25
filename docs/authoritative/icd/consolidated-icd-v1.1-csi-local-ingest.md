# Consolidated ICD v1.1 — CSI / Local-Device Ingest Revision

Supersedes in scope: `consolidated-icd-v1.0.md` for the MVP single-camera ingest path
Source basis: v1.0 authoritative extract + CSI rebaseline delta pack + founder direction note
Status: active intended authoritative revision for MVP once merged
Date: 2026-03-23

---

## Revision purpose

This revision formalizes the MVP ingest-path rebaseline from RTSP / IP-camera assumptions to **CSI / local-device ingest** on the Jetson appliance.

It updates the camera-facing portion of the ICD so the single-camera MVP no longer carries both:
- old RTSP/IP-camera assumptions
- new CSI/local-device direction

In this revision, the active MVP path is:

> **single local camera presented by host OS and consumed by `input-cv` through a local-device interface**

## Scope of change

### Changed
- ICD-1 camera → CV ingest assumptions
- camera source configuration schema
- startup and recovery semantics for ingest
- camera qualification and validation implications

### Unchanged
- downstream privacy posture remains metadata-only
- ICD-2, ICD-3, and ICD-4 remain materially unchanged in principle
- no change to privacy constraints, approval boundaries, or playback-hard-dependency law

## Revised ICD-1 role

### Producer / consumer model
**Before**
- Producer: RTSP/IP camera
- Consumer: DeepStream as RTSP client

**Now**
- Producer: local camera device connected directly to Jetson
- Consumer: `input-cv` / DeepStream local-device client

### Canonical endpoint model
**Before**
- `rtsp_url`

**Now**
- `device_path`, for example `/dev/video0`

## Revised source configuration contract

The single-camera MVP source configuration is now modeled as a local-device source object.

### Required fields
- `schema_version`
- `camera_id`
- `source_type`
- `device_path`
- `enabled`
- `pixel_format`
- `width`
- `height`
- `fps`

### Recommended fields
- `startup_timeout_ms`
- `read_timeout_ms`
- `reopen.enabled`
- `reopen.initial_backoff_ms`
- `reopen.max_backoff_ms`
- `notes`

### Removed RTSP-centric fields from MVP baseline
- `rtsp_url`
- RTSP transport preference
- network-camera authentication assumptions
- network reconnect semantics framed around remote stream negotiation

## Normative example object

```json
{
  "schema_version": "1.1.0",
  "camera_id": "front_entry_cam_01",
  "source_type": "local_v4l2",
  "device_path": "/dev/video0",
  "enabled": true,
  "pixel_format": "NV12",
  "width": 1920,
  "height": 1080,
  "fps": 30,
  "startup_timeout_ms": 10000,
  "read_timeout_ms": 3000,
  "reopen": {
    "enabled": true,
    "initial_backoff_ms": 500,
    "max_backoff_ms": 10000
  }
}
```

## Revised startup semantics

At startup, `input-cv` shall:
1. validate that the configured `device_path` exists
2. validate required permissions for camera access
3. validate requested capture parameters against the local device
4. attempt pipeline initialization within `startup_timeout_ms`
5. emit explicit health state if local-device initialization fails

If startup fails, playback shall remain available through fallback / static behavior.

## Revised recovery semantics

RTSP reconnect logic is replaced in the MVP baseline by **local-device reopen semantics**.

When local-device capture fails, `input-cv` shall:
- classify the fault as local-device ingest degraded
- attempt bounded reopen using configured backoff
- preserve downstream health signaling
- avoid causing player interruption

If reopen attempts fail, adaptation shall degrade / freeze while playback remains stable.

## Health and fault expectations

`input-cv` health for the local-device path shall include at minimum:
- device present / absent state
- last successful frame timestamp
- last successful pipeline start timestamp
- reopen-attempt count
- current capture parameters
- degraded / unavailable classification

## Privacy posture

This revision does **not** weaken privacy boundaries.

All downstream contract rules remain unchanged:
- no images in durable or egressed metadata messages
- no frame URLs
- no base64 blobs
- no face embeddings or reversible biometric templates

The ingest-path rebaseline changes *how frames are acquired*, not *what is allowed to persist or leave the device*.

## Camera qualification implications

A camera SKU shall not be treated as baseline-safe until the following are verified on the target Jetson platform:
- connector and ribbon compatibility
- successful bring-up on intended JetPack / L4T version
- expected field-of-view for pilot mounting geometry
- mixed-light / low-light pilot-scene suitability
- stable startup and reopen behavior under appliance conditions

## Conformance and test implications

This revision requires at minimum:
- schema validation tests for required local-device fields
- invalid configuration tests for missing `device_path`, invalid dimensions, invalid fps, and unsupported pixel format
- missing-device startup tests
- permission-failure tests
- reopen-behavior tests
- updated bring-up fixtures and sample config assets

## Repository interpretation rule

For the MVP single-camera path, this revision supersedes RTSP/IP-camera assumptions in practice.
Downstream implementation shall use the local-device ingest contract unless and until a later revision changes it.
