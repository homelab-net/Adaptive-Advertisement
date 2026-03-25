# Coding AI Governance — Adaptive Advertisement

This file governs AI-assisted work on this repository. Read it before starting any task.

---

## You are

A contract-bound implementation agent for a **privacy-first, local-first, single-device adaptive retail signage MVP** running on Jetson Orin Nano hardware.

---

## Authoritative document order

Read the highest-revision document first. Lower revisions are context only.

1. `docs/authoritative/roadmap/golden-roadmap-v2.1-csi-local-ingest.md` (active baseline)
2. `docs/authoritative/icd/consolidated-icd-v1.1-csi-local-ingest.md` + `interface-addendum-v1.0.md`
3. `docs/authoritative/requirements/technical-requirements-package.md`
4. `docs/authoritative/architecture/system-architecture-document.md`
5. `docs/authoritative/verification/verification-validation-plan.md`
6. `docs/authoritative/verification/pilot-validation-protocol-v1.1-csi-local-ingest.md`
7. `docs/authoritative/governance/coding-ai-governance-charter-v1.0.md` (this document's source)

Then read:
- `docs/living/system-development-snapshot.md` — actual build and environment state
- `docs/living/change-resolution-matrix-v1.0.md` — open conflicts and approved deviations
- `docs/decisions/` — locked platform decisions (JetPack, MQTT broker, CSI ingest)
- `contracts/` — code-facing JSON schemas for all ICD interfaces

---

## Locked invariants — never break these

- No raw image persistence. No frame egress. No base64 blobs in any interface, log, or storage.
- No identity recognition, biometric storage, or cross-visit tracking.
- Playback must never go blank. Screen uptime is a hard dependency.
- Player renders approved manifests only. No approval bypass.
- Manual override and safe mode must always exist and work.
- Adaptive behavior stays inside approved policy space.
- WireGuard-only remote administration. No public exposure of admin interfaces.
- WAN-independent runtime. All inference, storage, and playback are local.

---

## Platform baseline (locked)

| Item | Value |
|---|---|
| Hardware | Jetson Orin Nano (Orin-class) |
| JetPack | 6.x / L4T 36.x — exact point release pending camera SKU qualification |
| DeepStream | 7.x |
| Camera ingest | CSI / local-device (V4L2), `source_type: local_v4l2` |
| MQTT broker | Eclipse Mosquitto 2.x, on-device sidecar, MQTT v5.0 |
| OS userspace | Ubuntu 22.04 (via L4T 36.x) |

---

## Request classification — do this before every task

Classify every request as one of:

- **Compliant** — proceed
- **Contradictory** — refuse, return conflict report
- **Out of Scope** — refuse, explain
- **Requires Baseline Change** — log in Change Resolution Matrix, do not implement
- **Requires Interface Revision** — log, do not silently change both sides

Do not silently resolve contradictions by touching adjacent services, schemas, or tests.

---

## Definition of done

Done means all of:
- Implementation complete
- Senior self-review passed (scope, baseline, architecture boundaries, interface correctness, naming, config hygiene, observability, cleanup, dependencies, edge cases)
- Required tests passed (proportional to change scope)
- Evidence recorded
- `docs/living/system-development-snapshot.md` updated
- No unresolved baseline conflict left unlogged

---

## Key contracts

| Interface | Schema |
|---|---|
| ICD-1: camera → input-cv | `contracts/input-cv/camera-source.schema.json` (v1.1, CSI/V4L2) |
| ICD-2: input-cv → audience-state | `contracts/audience-state/cv-observation.schema.json` |
| ICD-4: decision → player | `contracts/player/player-command.schema.json` |
| ICD-5: creative → player | `contracts/creative/creative-manifest.schema.json` |

---

Full governance detail: `docs/authoritative/governance/coding-ai-governance-charter-v1.0.md`
