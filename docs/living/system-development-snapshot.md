# System / Development Snapshot

*Adaptive Retail Advertising MVP · living execution-state artifact*

**Last updated:** 2026-03-23
**Status:** Pre-implementation — documentation and contract baseline complete; services not yet started

> Agents must read this document before starting work and update it after any material change. If this snapshot conflicts with an authoritative baseline document, log the conflict in the Change Resolution Matrix rather than silently reconciling it.

---

## 1. Authoritative Document Baseline

| Item | Current status / notes |
|---|---|
| Active roadmap | `golden-roadmap-v2.1-csi-local-ingest.md` — CSI rebaseline is the active direction; supersedes v2.0 for all ingest-path decisions |
| Active ICD | `consolidated-icd-v1.1-csi-local-ingest.md` + `interface-addendum-v1.0.md` — CSI/V4L2 replaces RTSP in ICD-1 |
| TRD | `technical-requirements-package.md` — present and active |
| V&V plan | `verification-validation-plan.md` — present and active |
| Pilot protocol | `pilot-validation-protocol-v1.1-csi-local-ingest.md` — CSI revision active |
| Governance | `coding-ai-governance-charter-v1.0.md` — active; `CLAUDE.md` is the agent-facing summary |
| Software selection | `governance/software-selection-directive.txt` — foundational; active |

## 2. Platform Baseline (locked decisions)

| Item | Status / value |
|---|---|
| Hardware SKU | Jetson Orin Nano / Orin-class; exact final deploy SKU to be frozen after camera qualification |
| JetPack / L4T | **Locked: JetPack 6.x / L4T 36.x** — see `decisions/2026-03-23-jetpack-version.md` |
| DeepStream | 7.x (aligned to JetPack 6.x) |
| Camera ingest | **Locked: CSI / local-device (V4L2)** — see `decisions/2026-03-23-csi-local-ingest-founder-direction.md` |
| Camera SKU | Not qualified — exact SKU and bring-up on target Jetson not yet verified |
| JetPack point release | Not pinned — depends on camera SKU qualification result |
| MQTT broker | **Locked: Eclipse Mosquitto 2.x** — see `decisions/2026-03-23-mqtt-broker.md` |
| Storage | 256 GB NVMe pilot default |
| Display | Customer-provided display is the deployed runtime endpoint; 7-inch HDMI is bench/service accessory only |
| Container runtime | Not Started |
| WireGuard / remote admin | Direction locked; implementation Not Started |

## 3. Repo and Workspace Status

| Item | Current status / notes |
|---|---|
| Primary repo | `homelab-net/Adaptive-Advertisement` |
| Active branch | `claude/project-overview-A7Vqt` |
| Baseline alignment | CSI rebaseline documents present; repo structure overhauled 2026-03-23; `docs/repo-native/` intermediate layer removed |
| Pending merges | None blocking implementation |
| Open PRs on remote | pr2 through pr6 on remote origin; all content absorbed into working branch |

## 4. Contract Status

| Contract | File | Status |
|---|---|---|
| ICD-1: camera → input-cv | `contracts/input-cv/camera-source.schema.json` | v1.1 — CSI/V4L2 fields defined |
| ICD-2: input-cv → audience-state | `contracts/audience-state/cv-observation.schema.json` | v1.0 — metadata-only, privacy fields schema-enforced |
| ICD-4: decision → player | `contracts/player/player-command.schema.json` | v1.0 — commands, sequence ordering defined |
| ICD-5: creative → player | `contracts/creative/creative-manifest.schema.json` | v1.0 — approval fields required |
| ICD-3: audience-state → decision | Defined in ICD v1.1 doc | No code-facing schema stub yet |
| ICD-6/7/8: dashboard, postgres, supervisor | Defined in interface addendum | No code-facing schema stubs yet |

## 5. Service Status

| Service | Status | Notes |
|---|---|---|
| input-cv | Not Started | Requires CSI/V4L2 bring-up; `camera-source.schema.json` v1.1 is the config contract |
| audience-state | Not Started | MQTT subscriber; ICD-2 contract defined |
| decision-optimizer | Not Started | Rules-first for MVP; ICD-3 interface defined in ICD docs |
| creative | Not Started | Approved-manifest authority; ICD-5 contract defined |
| player | Not Started | **Hard dependency — first-priority service to scaffold**; screen-never-blank rule governs all fallback logic |
| dashboard-api | Not Started | Canonical business-logic write authority |
| postgres | Not Started | Local storage; schema migrations required |
| supervisor | Not Started | Restart-ladder and safe-mode logic |

## 6. Verification Status

| Item | Status |
|---|---|
| Unit tests | Not Started |
| Contract tests | Not Started |
| Integration tests | Not Started |
| System / recovery evidence | Not Started |

## 7. Current Blockers and Open Risks

| Risk | Status |
|---|---|
| Camera SKU qualification | Open — exact CSI camera SKU and bring-up on target Jetson not verified; blocks JetPack point-release pin |
| Player not yet scaffolded | Open — player is the hard dependency; implementation should start here |
| ICD-3 no code-facing schema | Open — audience-state → decision-optimizer schema stub not yet created |
| ICD-6/7/8 no code-facing schemas | Open — dashboard, postgres, supervisor interface stubs not yet created |

## 8. Immediate Next Actions

1. Scaffold `player` service with screen-never-blank fallback posture (hard dependency).
2. Create ICD-3 code-facing schema stub (`audience-state` → `decision-optimizer`).
3. Acquire and qualify camera SKU on target Jetson Orin Nano hardware.
4. Pin JetPack point release after camera qualification result.
5. Scaffold `input-cv` after camera qualification confirms device bring-up.
