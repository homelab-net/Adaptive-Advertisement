# Platform Decision — JetPack Version

Date: 2026-03-23
Status: approved; active for MVP implementation
Scope: Jetson platform baseline, OS, DeepStream version, and container base image line

---

## Decision summary

> **JetPack 6.x (L4T 36.x) is the active MVP platform baseline.**

DeepStream 7.x is the corresponding CV pipeline version.

The exact point release (6.0, 6.1, 6.2, etc.) shall be pinned after camera SKU qualification confirms bring-up stability on the target Jetson Orin Nano. Until that pin is confirmed, all `Dockerfile` base images and CI fixtures shall target the JetPack 6.x / L4T 36.x line.

## Why this version is being locked

- JetPack 6.x is the current supported release for Jetson Orin Nano hardware.
- L4T 36.x provides an Ubuntu 22.04 userspace with a longer support window than the prior 20.04-based JetPack 5.x line.
- DeepStream 7.x is the current release aligned to JetPack 6.x and supports the local V4L2/CSI ingest path required by the approved MVP direction.
- Choosing the current supported line avoids a known platform migration mid-project, consistent with the software selection directive's "correct long-term foundations" principle.

## What is not locked yet

- Exact point release within JetPack 6.x: to be pinned after camera SKU qualification. The bring-up check must confirm that the chosen CSI camera operates correctly on the specific L4T point release before it is written into `Dockerfile` base image tags and provisioning scripts.
- Power mode: `nvpmodel` profile selection (10W / 15W / performance) is a deployment configuration item, not a baseline lock. Requirements are defined in the TRD (THRM-001 through THRM-004).

## Implications for implementation

- All container `FROM` lines targeting the DeepStream or Jetson runtime must use JetPack 6.x / L4T 36.x compatible base images.
- CI fixtures that require Jetson-specific runtimes should document their JetPack 6.x dependency explicitly.
- The camera qualification checklist must record the exact JetPack point release used during qualification.
- If camera bring-up reveals a regression in a specific point release, a new decision note should record the pinned version and rationale.

## Relationship to other decisions

- Camera SKU qualification (open): JetPack point release pin depends on this.
- MQTT broker: independent of JetPack version; see `2026-03-23-mqtt-broker.md`.
