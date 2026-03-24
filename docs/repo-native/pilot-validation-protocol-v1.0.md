# Pilot_Validation_Protocol_v1_0

Source file: `Pilot_Validation_Protocol_v1_0.docx`
Export type: text and simple table extraction from DOCX

---

Pilot Validation Protocol v1.0

Adaptive Retail Advertising MVP
Single-Site Static-vs-Adaptive Pilot

| Document purpose | Define the pilot required to validate technical readiness, commercial signal, and solo-founder supportability before first-sale claims. |
| --- | --- |
| Applies to | Single-camera, single-display, Jetson-class, local-first MVP with rules-first adaptation and approved-only creative policy. |
| Document status | Working implementation baseline following frozen ICD baseline. |
| Primary use | Pilot planning, entry gating, execution control, evidence capture, and closeout reporting. |

Executive Summary

This protocol defines the minimum commercially credible pilot for the privacy-first adaptive signage MVP.

The pilot is intentionally narrow: one site, one appliance, one camera, one customer-provided display, one approved creative library, and a controlled comparison between static mode and adaptive mode.

The goal is not to prove a fully generalized optimization platform. The goal is to prove that the appliance remains privacy-safe and operationally reliable, that adaptive behavior stays inside approved policy space, and that the adaptive mode shows a positive business signal against a static baseline without creating unacceptable support burden.

Pilot success requires all three dimensions below to pass.

| Dimension | What must be proven | Pass interpretation |
| --- | --- | --- |
| Technical validity | Playback continuity, privacy compliance, recovery behavior, operator controls, and bounded runtime performance | No hard blocker remains for pilot use in a real store |
| Commercial validity | Adaptive mode shows a positive directional signal relative to static mode using the same approved content library | System is promising enough to justify broader pilots or first paid deployment |
| Solo-founder viability | Install, support, remote triage, and operator burden remain manageable | Founder can realistically deploy and support the product without unsustainable overhead |

1. Purpose and decision use

This protocol is the control document for pilot entry, pilot execution, evidence capture, and pilot closeout.

It exists to answer one decision question: is the current MVP pilot-ready and commercially credible enough to justify expanded deployment or first-sale packaging?

Anything outside that purpose should be deferred unless it directly improves pilot reliability, privacy, or evidence quality.

2. Locked pilot scope

The pilot must stay inside the locked MVP scope. No mid-pilot broadening is allowed.

Playback is a hard dependency. Computer vision, decisioning, analytics, and remote admin are soft dependencies that must degrade gracefully without blanking the display.

All CV inference remains local. No raw image persistence, no raw video egress, no identity recognition, no cross-visit tracking, and no biometric storage.

| Scope element | Pilot rule |
| --- | --- |
| Site count | One cooperative retail site |
| Display topology | One appliance, one customer-provided display, one camera |
| Runtime posture | Local-first and WAN-independent for normal operation |
| Remote administration | WireGuard-only |
| Decisioning | Rules-first keep/switch/fallback behavior |
| Creative policy | Approved templates, approved assets, approved text elements, bounded modifiers only |
| Failure posture | Freeze or fall back before playback is interrupted |

3. Entry criteria

The pilot shall not start until all entry gates below are satisfied and evidenced.

| Entry gate | Minimum condition | Evidence artifact |
| --- | --- | --- |
| Hard-gate test suite | Boot, controlled switch, CV latency, privacy storage audit, privacy egress audit, fault injection, and update rollback pass | Build verification pack |
| Reliability proving | Sustained run plus restart ladder behavior demonstrated | Reliability campaign report |
| Install readiness | Provisioning flow documented and dry-run performed | Install and provisioning SOP |
| Camera readiness | One camera SKU and one mount pattern qualified | Camera qualification sheet |
| Operator readiness | Core owner workflows can be completed without engineering intervention | Operator acceptance checklist |
| Pilot content readiness | Approved creative library frozen for the pilot window | Creative approval packet |

4. Pilot site profile

Select a site that is representative enough to matter, but not so difficult that the first pilot becomes a stress test rather than a validation exercise.

| Characteristic | Target profile |
| --- | --- |
| Business type | Small retail / coffee / quick-service environment with cooperative owner |
| Traffic | Moderate and recurring foot traffic |
| Lighting | Mostly stable indoor lighting with some realistic glare, shadow, and occlusion |
| Network | Local LAN available; WAN interruptions tolerated |
| Operator posture | Owner willing to provide short structured feedback during pilot |
| Display role | Display is a real signage endpoint rather than a lab monitor |

5. Experimental design

Use a within-site comparison with the same approved content library in both conditions.

| Condition | Description | Rule |
| --- | --- | --- |
| Static mode | Fixed approved rotation with no audience-responsive switching | Baseline for comparison |
| Adaptive mode | Same approved library, but runtime switching allowed inside approved policy rules | Only switching policy changes; library stays constant |

Recommended pilot sequence:

| Stage | Duration | Purpose |
| --- | --- | --- |
| Day 0 | Install / calibration day | Verify optics, privacy, handoff, and fallback behavior |
| Days 1–7 | Static baseline | Establish baseline operational and business signal |
| Days 8–21 | Adaptive window | Compare adaptive behavior against the static baseline |
| Days 22–23 | Closeout | Collect owner feedback, export evidence, finalize report |

Pilot control rules:

• No interface or schema drift during the pilot window.

• No new adaptive feature classes introduced mid-pilot.

• No approval bypass path.

• Any content change must be documented and operator-approved.

• If confidence is weak or state is unstable, suppress adaptation and preserve stable playback.

6. Metrics and pass criteria

Metrics should stay minimal, decision-useful, and aligned to go/no-go questions.

6.1 Hard operational metrics

| Metric | Target / standard | Why it exists |
| --- | --- | --- |
| Playback availability | Target at or above 99.5% during pilot window | Appliance credibility |
| Visible blank events | None outside allowed controlled-switch threshold | Playback continuity |
| Controlled switch blank time | No visible blank above 250 ms | User-visible smoothness |
| Player recovery | Playback resumes within 10 s after player crash | Reliability |
| Capture-to-metadata latency | p95 at or below 150 ms at target cadence | Real-time responsiveness |
| Privacy violations | Zero retained imagery and zero raw frame egress | Core product rule |
| Approval bypass events | Zero | Governance discipline |
| WAN dependence | No runtime failure caused solely by WAN loss | Local-first requirement |

6.2 Commercial signal metrics

| Metric | Decision standard |
| --- | --- |
| Dwell / attention direction | Adaptive should show a positive directional change versus static |
| Owner trust | No reduction in perceived control or explainability |
| Operator acceptance | Owner can pause adaptation, enter safe mode, resume, and review status without engineering help |
| Support burden | Support effort remains acceptable for solo-founder operation |

6.3 Evidence-only metrics

| Metric | Use |
| --- | --- |
| GPU / CPU / RAM budget | Verify sustainable operation on target hardware |
| Thermal headroom | Confirm adaptation degrades before playback |
| Restart count | Expose hidden instability |
| Time to acknowledge / restore | Quantify supportability |
| Remote resolution rate | Measure real utility of WireGuard-only remote admin |

7. Data collection and retention boundary

The pilot must collect enough evidence to support decisions while remaining inside the privacy boundary.

| Data type | Allowed | Notes |
| --- | --- | --- |
| Raw frames / clips | No | Must not be stored or exported |
| Metadata observations | Yes | Structured, versioned, privacy-safe only |
| Audience-state summaries | Yes | Used for decisioning and analysis |
| Decision and playback events | Yes | Retain for audit and comparison |
| Fault / maintenance events | Yes | Operational troubleshooting and proof |
| Owner feedback | Yes | Structured survey and debrief |
| Support log | Yes | Required to assess commercial viability |

8. Operator interaction protocol

The pilot must prove that the owner can operate the system safely and understandably.

| Task | Success standard |
| --- | --- |
| Approve creative for pilot use | Completed without engineering assistance |
| Pause adaptation | Successful on first attempt |
| Enter safe mode | Successful on first attempt |
| Resume normal mode | Successful after safe-mode use |
| Review summary analytics | Owner can explain what the summary means in practical business terms |
| Report issue | Remote triage path works and is understood |

9. Failure handling during pilot

Field behavior must follow the appliance recovery law, not ad hoc operator improvisation.

| Failure class | Required behavior |
| --- | --- |
| CV degraded or unavailable | Freeze adaptation and continue stable playlist or fallback rotation |
| Decision engine degraded | Freeze last stable decision and continue playback |
| Player process failure | Recover player before considering broader restart actions |
| Dashboard / DB / API degraded | Playback remains unaffected wherever possible |
| Repeated unrecovered failure | Escalate through restart ladder, then safe mode if required |
| Maintenance policy | No blind nightly reboot policy |

10. Pilot exit criteria

| Exit criterion | Required state |
| --- | --- |
| Static-vs-adaptive report | Complete |
| Support burden review | Complete |
| Customer feedback capture | Complete |
| Hard privacy or playback blocker | None unresolved |
| Owner acceptance record | Complete |
| Customer-safe proof pack | Assembled |

Appendix A. Install and Provisioning Checklist

Use this as the on-site execution sheet for each pilot install.

| Category | Required checks | Result / notes |
| --- | --- | --- |
| Physical | Display connected, appliance secured, camera mounted, power stable |  |
| Network | LAN connected, WireGuard reachable, no public exposure |  |
| Runtime | Boot to managed runtime, fallback path active |  |
| Privacy | Storage audit clean, egress policy clean |  |
| Calibration | Pilot scene checks completed |  |
| Operator handoff | Pause, safe mode, resume, status, and approvals demonstrated |  |

Appendix B. Camera SKU and Mount Qualification Sheet

| Field | Value / notes |
| --- | --- |
| Camera make / model / SKU |  |
| Lens / field of view |  |
| Mount type |  |
| Mount height |  |
| Mount angle |  |
| Distance to traffic zone |  |
| Lighting notes |  |
| Glare / reflection notes |  |
| Calibration configuration hash |  |
| Pass / fail against pilot scene classes |  |

Appendix C. Support Burden Ledger

| Field | Purpose |
| --- | --- |
| Date / time | Traceability |
| Issue class | Install / operator / CV / player / network / content / update |
| Detection source | Owner report, alert, or founder observation |
| Resolution mode | Remote, operator self-fix, or on-site |
| Time to acknowledge | Support burden |
| Time to restore | MTTR and usability |
| Root cause | Product gap visibility |
| Preventable? | Prioritization input |
| Pilot impact | Commercial viability |

Appendix D. Operator Acceptance Checklist

| Workflow | Pass standard | Pass / fail | Notes |
| --- | --- | --- | --- |
| View current status | Owner can identify whether system is healthy |  |  |
| Pause adaptation | Action completes successfully |  |  |
| Enter safe mode | Action completes successfully |  |  |
| Resume normal mode | Action completes successfully |  |  |
| Review analytics summary | Owner understands the summary at a business level |  |  |
| Request help | Owner understands support path |  |  |

Appendix E. Customer-Safe Proof Pack Outline

| Section | Contents |
| --- | --- |
| System summary | One-page description of the appliance and deployment scope |
| Privacy summary | Metadata-only CV, no raw imagery stored or exported |
| Reliability summary | Playback continuity, recovery evidence, and pilot uptime summary |
| Operator control summary | Approval workflow, manual override, and safe-mode behavior |
| Pilot outcome summary | Static-vs-adaptive comparison using the same approved library |
| Supportability summary | Support burden, remote triage viability, and lessons learned |

Document Control Notes

This protocol is intended to be revised only when pilot scope, evidence requirements, or acceptance criteria materially change.

Minor operational notes, issue logs, and closeout observations should be maintained in attached appendices or run records rather than by widening the core pilot document.

During implementation, this document should remain the controlling reference for pilot readiness and closeout.
