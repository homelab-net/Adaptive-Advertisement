# Target End-State Vision v1.0

Source file: `Adaptive_Retail_Target_End_State_Vision_v1_0.txt`
Import type: curated repo-native digest from source
Authority: supporting only; does not expand MVP scope or override active baselines

---

## Role

This document captures the intended **post-MVP end state** so the MVP foundation is built on the correct long-term architecture. It is directional and architectural, not an authorization to widen the current MVP.

## Governing boundary

The source explicitly preserves the existing control order:
- highest-revision roadmap, ICDs, TRD, V&V plan, and pilot protocol remain authoritative
- MVP execution, pilot gating, and release claims are still governed by those active baselines
- this vision document is for long-term fit and design alignment only

## End-state product statement

The target product is a **privacy-first, local-first adaptive signage appliance and fleet platform** that improves approved advertising through:
- local audience-aware delivery
- controlled experimentation
- aggregate business metrics
- human-governed optimization

It is explicitly **not** intended to become:
- a freeform generative ad engine
- a cloud-required runtime adtech platform
- an identity-based targeting system
- a raw-camera exposure product

## Permanent non-negotiable constraints

The source keeps the following rules permanent across MVP and final product:
- all CV inference remains local
- no raw image persistence
- no raw frame or video egress
- no identity recognition, biometric storage, or cross-visit tracking
- playback is a hard dependency; CV, analytics, DB, dashboard, and WAN are soft dependencies
- the screen must never go blank
- manual override and safe mode must always exist
- adaptive behavior must remain inside approved policy space
- the player may render only approved manifests
- WAN is not required for runtime
- remote administration remains VPN-only unless formally revised later
- recovery follows restart-ladder logic; blind nightly reboot posture remains prohibited

## End-state functional intent

### 1. Audience-aware delivery
The future system should use metadata-only local audience-state signals to influence which approved creative assembly is shown, while preserving:
- confidence-gated switching
- freeze-on-uncertainty behavior
- graceful degradation when state is weak, stale, or unavailable

### 2. Structured creative assembly
The product should remain a **structured creative system**, not a freeform generator. The source positions the long-term design around:
- approved templates
- approved assets
- approved text elements
- approved variant groups
- bounded style and emphasis modifiers
- deterministic render manifests suitable for offline-safe playback

### 3. Controlled A/B testing and experimentation
The vision includes disciplined experimentation inside approved policy space, such as:
- static-vs-adaptive comparison using the same approved creative library
- controlled variant-family comparisons
- documented experiment windows and conditions
- aggregate local metrics for evaluation
- promotion or reweighting decisions based on measured outcomes

### 4. Measured self-optimization
The intended optimization target is not synthesis from scratch. It is:

> selecting and weighting the best-performing approved combination of creative components for a given audience-state context using local aggregate performance signals and bounded experimentation

Future optimization surfaces named in the source include:
- template choice
- headline/body/offer/CTA variants
- approved style or color modifiers
- hold time and switch timing
- rotation weight
- context-conditioned campaign eligibility

### 5. Human-governed control plane
The end state remains operator-controlled. The source expects:
- upload, review, and approval workflows
- manual approval as the default runtime gate
- pause/resume/restrict controls for adaptive behavior
- safe mode and fallback playlist control
- clear owner-facing analytics and status
- no approval bypass path

### 6. Business-usable analytics
The source explicitly rejects an ML-lab UI. Analytics should remain aggregate, explainable, and commercially useful, covering:
- impressions and exposure opportunity counts
- dwell / attention-direction proxies
- static-vs-adaptive comparisons
- variant-family trends
- campaign and site-level summaries
- uptime and support-burden reporting
- explainable reason codes and decision-trace summaries

### 7. Reliability and fallback behavior
The end state is described as an appliance, not a demo. Reliability expectations include:
- always-on playback
- offline-safe local asset cache and fallback bundle
- no visible blank-screen behavior in normal operation
- commercially acceptable switch smoothness
- player-first recovery before device reboot
- freeze or fallback behavior when CV, decisioning, creative, DB, dashboard, or network layers degrade

### 8. Local-first appliance runtime
The source keeps the product fundamentally usable as an in-store appliance:
- local dashboard
- local storage
- local decisioning
- local analytics persistence
- local playback continuity during WAN outages
- optional VPN-based remote administration

### 9. Fleet and multi-site growth
The source allows additive future growth above the local appliance runtime, including:
- multi-location campaign coordination
- cross-store performance comparison
- fleet health visibility
- site, tenant, and device-level rollups
- promotion of approved winning variant families across sites
- staged update and rollout rings

The source is explicit that these features must remain **additive** and must not become a runtime dependency for the in-store appliance.

## Maturity path described in source

The target optimization posture is staged in four steps:
1. rules-first adaptive delivery
2. controlled pilot experimentation
3. bounded optimizer assistance
4. continuous bounded improvement

This sequencing is useful because it reinforces that the product should mature through measured, explainable progression rather than jump directly to opaque optimization.

## Architectural implications for MVP foundation

The source implies the MVP should already assume:
- stable service boundaries
- versioned interface contracts
- canonical business objects
- approved-only creative pipelines
- explainable decisions and audit trails
- local-first durability and fallback behavior
- later fleet growth as an additive layer, not a rewrite trigger

## Practical design value

This source is most useful as a **long-term fit filter**. It helps evaluate whether a proposed MVP implementation choice:
- preserves privacy and appliance reliability
- keeps structured creative and approval governance intact
- supports future experimentation and bounded optimization
- avoids choosing a short-term convenience that would force a future rebuild

## Repository note

This repo-native file is a curated digest rather than a line-for-line copy. The uploaded source text remains the higher-fidelity reference for exact wording.