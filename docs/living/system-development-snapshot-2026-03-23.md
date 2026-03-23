# System / Development Snapshot — 2026-03-23 Codex Handoff

Status: current working snapshot for AI and human contributors

---

## 1. Authoritative Document Baseline

| Item | Current status / notes |
|---|---|
| Current roadmap / golden plan | `golden-roadmap-v2.md` is current merged baseline in repo-native form; `golden-roadmap-v2.1-csi-local-ingest.md` is pending as active rebaseline revision in PR #6 |
| Current ICD baseline | `consolidated-icd-v1.0.md` is current merged baseline in repo-native form; `consolidated-icd-v1.1-csi-local-ingest.md` is pending as active rebaseline revision in PR #6 |
| Current TRD / requirements baseline | `technical-requirements-package.md` repo-native authoritative extract present |
| Current V&V baseline | `verification-validation-plan.md` repo-native authoritative extract present |
| Current pilot baseline | `pilot-validation-protocol-v1.0.md` current export present; `pilot-validation-protocol-v1.1-csi-local-ingest.md` pending in PR #6 |
| Current governance baseline | coding AI governance charter extract present; CRM-002 opened for CSI rebaseline |

## 2. Environment and Appliance State

| Item | Current status / notes |
|---|---|
| Target hardware SKU | Jetson Orin Nano / Orin-class single-device appliance target; exact final deploy SKU still to be frozen |
| Storage default | 256 GB NVMe pilot default |
| Camera setup | CSI / local-device ingest is approved founder direction; exact camera SKU still requires qualification on target Jetson |
| Display setup | customer-provided display is the deployed runtime endpoint; 7-inch HDMI screen is optional bench / service accessory only |
| JetPack / OS version | Not Started / not yet frozen in snapshot |
| Container runtime / compose status | Not Started |
| WireGuard / remote admin status | Direction locked; implementation state Not Started |

## 3. Repo and Workspace Status

| Item | Current status / notes |
|---|---|
| Primary repo | `homelab-net/Adaptive-Advertisement` |
| Active branch stack | PR #1 docs structure, PR #2 repo-native exports, PR #3 supporting digests, PR #4 authoritative extracts, PR #5 founder CSI direction, PR #6 formal CSI rebaseline package |
| Pending merges / review items | Merge PR stack in order if accepted; PR #6 is the key baseline-alignment PR before implementation |
| Known local-only changes | None recorded in repo snapshot |

## 4. Service Status

| Item | Current status / notes |
|---|---|
| input-cv | Not Started; CSI/local-device config schema and bring-up contract now required |
| audience-state | Not Started |
| decision-optimizer | Not Started |
| creative | Not Started |
| player | Not Started; still the hard dependency and should be prioritized early |
| dashboard-api | Not Started |
| postgres | Not Started |
| supervisor | Not Started |

## 5. Interface and Data Contract Status

| Item | Current status / notes |
|---|---|
| Camera -> input-cv | v1.0 RTSP-style baseline exists; v1.1 CSI/local-device revision pending in PR #6 |
| input-cv -> audience-state | metadata-only direction locked; code-facing schema work still needed |
| audience-state -> decision-optimizer | repo-native authoritative extract present; implementation not started |
| decision -> creative / player | repo-native authoritative extracts present; implementation not started |
| dashboard-api -> postgres | repo-native authoritative extracts present; implementation not started |

## 6. Verification Status

| Item | Current status / notes |
|---|---|
| Latest unit test state | Not Started |
| Latest contract test state | Not Started |
| Latest integration test state | Not Started |
| Latest system / recovery evidence | Not Started |

## 7. Current Blockers and Open Risks

| Item | Current status / notes |
|---|---|
| Baseline split risk | Until PR #6 is merged, repo still carries older RTSP baseline and newer CSI direction in parallel |
| Camera qualification risk | exact CSI camera SKU and bring-up behavior on target Jetson not yet verified |
| Config drift risk | code-facing `input-cv` schema must be created before implementation to prevent Codex inventing contract fields |
| Execution sequencing risk | implementation should not begin from CV-only enthusiasm; player/fallback hard dependency still governs appliance posture |

## 8. Immediate Next Actions for Codex

1. Read governance charter, current authoritative extracts, CRM-002, and this snapshot.
2. Treat CSI/local-device ingest as the intended implementation direction.
3. Do not silently modify baseline assumptions outside PR #6.
4. Create code-facing config schema and contract tests for `input-cv` local-device ingest.
5. Scaffold implementation in a way that preserves player/fallback hard-dependency rules.
