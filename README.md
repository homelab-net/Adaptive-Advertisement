# Adaptive Advertisement

Privacy-first, local-first adaptive retail signage on Jetson edge hardware.

## What this is

A single-device appliance that runs computer vision inference locally to adapt displayed advertising content in real time based on audience presence — without storing images, identifying individuals, or requiring a cloud connection.

## What this is not

- Not a cloud-dependent platform
- Not an identity or biometric system
- Not a freeform generative ad engine
- Not a raw-camera feed system

## Hard constraints

- Screen never goes blank
- No raw image persistence, no frame egress, no biometric storage
- Playback is a hard dependency; CV, DB, and dashboard are soft dependencies
- Player renders approved creative manifests only
- Manual override and safe mode always available
- WireGuard-only remote administration
- WAN-independent runtime

## Repository structure

```
contracts/          JSON schemas for all service interfaces (ICD-1 through ICD-5)
docs/
  authoritative/    Architecture, ICD, TRD, V&V plan, roadmap, governance
  supporting/       Design rationale, vision, storage guidance, rebaseline notes
  living/           System snapshot (current build state), change resolution matrix
  decisions/        Locked platform decisions (JetPack, MQTT, camera ingest)
```

## Key documents

| Document | Path |
|---|---|
| Active roadmap | `docs/authoritative/roadmap/golden-roadmap-v2.1-csi-local-ingest.md` |
| Interface contracts | `docs/authoritative/icd/consolidated-icd-v1.1-csi-local-ingest.md` |
| Technical requirements | `docs/authoritative/requirements/technical-requirements-package.md` |
| Architecture | `docs/authoritative/architecture/system-architecture-document.md` |
| V&V plan | `docs/authoritative/verification/verification-validation-plan.md` |
| AI governance | `CLAUDE.md` (summary) · `docs/authoritative/governance/coding-ai-governance-charter-v1.0.md` (full) |
| Build state | `docs/living/system-development-snapshot.md` |

## Platform baseline

| Item | Value |
|---|---|
| Hardware | Jetson Orin Nano |
| JetPack | 6.x / L4T 36.x |
| DeepStream | 7.x |
| Camera | CSI / local-device (V4L2) |
| MQTT | Eclipse Mosquitto 2.x |
| Storage | 256 GB NVMe (pilot default) |

## Hardware deployment quickstart (Jetson)

1. Copy the hardware env template:
   - `cp .env.hardware.example .env.hardware`
2. Run preflight checks:
   - `./tools/preflight-hardware.sh`
3. Bring up the stack with hardware overrides:
   - `docker compose -f docker-compose.yml -f docker-compose.hardware.yml --env-file .env.hardware up -d --build`

The `docker-compose.hardware.yml` override enables real camera ingest (`deepstream` + `/dev/video0`) and the `mpv` renderer for on-device playback.
