# Additional Interface Control Document + Network Interface Addendum v1.0

Source file: `adaptive_retail_interface_addendum_v1_0.pdf`
Import type: curated authoritative extract
Document ID in source: `ICD-ADDL-NET-EDGESIGNAGE`
Version in source: `v1.0`
Status in source: authoritative addendum for MVP implementation
Date in source: 2026-03-17

---

## Role

This addendum extends the original consolidated ICD so the MVP has a complete contract surface across the remaining services and the device-network boundary.

The source explicitly says it formalizes:
- ICD-5 Creative Service ↔ Player
- ICD-6 Dashboard Frontend ↔ Dashboard API
- ICD-7 Dashboard API ↔ PostgreSQL
- ICD-8 Supervisor ↔ Managed Services
- ICD-NET-1 Orin device LAN/WAN networking interface

Its role is to complete the MVP interface baseline so implementation can proceed without schema drift or hidden coupling.

## Governing basis carried by source

The addendum inherits the locked architectural direction from the project baseline and does not define a new system model.

The source says it is aligned to:
- the Golden Build Plan
- the Roadmap Addendum / active roadmap direction
- the Software Selection Directive
- the prior consolidated ICD
- the System Architecture Document

## Main contribution of the addendum

If the original consolidated ICD locked the camera → CV → audience-state → decision → player half of the system, this addendum locks the remaining surfaces needed to make the appliance complete:
- creative manifest production and player consumption
- dashboard UI and API control behavior
- canonical write path into local PostgreSQL
- supervisor health/restart/safe-mode orchestration
- LAN/WAN exposure and VPN-only remote administration posture

## ICD-5 Creative Service ↔ Player

### Purpose
Define how approved creative manifests and asset references are delivered to the player while preserving the approved-only rendering rule.

### Architectural meaning
This interface exists so the player does not invent creative structure at runtime. The player renders only approved manifests assembled by the creative service within policy constraints.

### Core contract expectations implied by source
- manifest-driven rendering rather than freeform generation
- player receives approved manifest objects and asset references, not raw policy logic
- invalid, missing, or unapproved manifests must be rejectable without blanking playback
- cache miss or invalid-manifest behavior must fall back safely
- creative-service output remains bounded by approval policy and modifier rules

## ICD-6 Dashboard Frontend ↔ Dashboard API

### Purpose
Define the owner/operator control-plane contract for approvals, system status, analytics, safe mode, and campaign control.

### Behavioral expectations carried by source
The dashboard surface is not an ML-lab UI. It is an owner-facing appliance control plane.

The interface must support workflows such as:
- asset upload / campaign management
- approval and enablement flows
- safe mode and manual override
- analytics summary access
- status and health visibility

### Control posture
The source baseline requires:
- approval-safe behavior by default
- non-bypassable approval workflow
- operator controls that keep the owner in charge
- clarity and explainability rather than opaque automation

## ICD-7 Dashboard API ↔ PostgreSQL

### Purpose
Define the canonical persistence contract for business objects and operational events.

### Architectural meaning
This interface is how the project preserves canonical write authority and avoids ad hoc persistence paths.

### Core database posture implied by source
- `dashboard-api` is the canonical business-logic authority for MVP write flows
- PostgreSQL stores durable local business objects and append-only operational events
- schema evolution must be versioned and migration-based
- persistence behavior must support auditability and replay where required
- playback must not become DB-hard-dependent

## ICD-8 Supervisor ↔ Managed Services

### Purpose
Define the appliance supervision contract for health checks, restart ladder behavior, maintenance logic, and safe-mode orchestration.

### Runtime meaning
The supervisor is not a generic monitoring extra. It is a core appliance service responsible for bounded recovery.

### Core behaviors aligned with source
- health checks across managed services
- restart-ladder logic rather than blind rebooting
- maintenance-window behavior
- safe-mode orchestration when broader recovery cannot restore normal operation
- preserving playback or stable fallback behavior through partial-service failure

## ICD-NET-1 Orin device LAN/WAN networking interface

### Purpose
Formalize the device’s network exposure rules and administrative access posture.

### Core posture carried by source
- LAN/WAN exposure must be explicit and bounded
- remote administration is VPN-first / WireGuard-only for MVP and early field operation
- WAN is not required for runtime playback
- public exposure should be blocked by default
- device-network rules are part of the interface baseline, not just an ops afterthought

## Cross-cutting rules reinforced by addendum

### Complete contract surface
The source makes clear that without these interfaces, implementation would risk hidden coupling between creative, player, dashboard, DB, supervisor, and network behavior.

### Approved-only rendering
The player renders approved manifests only. This reinforces the project rule that adaptive behavior must remain inside approved policy space.

### Canonical write authority
The addendum is one of the main baseline documents that supports keeping `dashboard-api` as canonical write authority into the durable store.

### Appliance recovery posture
Supervisor and networking interfaces are treated as first-class contract surfaces because appliance reliability depends on them.

## Practical use for implementation

This addendum should be used as the active source for:
- creative manifest / player rendering boundaries
- dashboard UI/API workflow boundaries
- dashboard-api ↔ postgres write authority and schema discipline
- supervisor health, restart, and safe-mode behavior
- Orin LAN/WAN exposure and VPN-only remote administration rules

## Relationship to the consolidated ICD

The addendum does not replace the original ICD. It completes it.

Together, the consolidated ICD plus this addendum form the authoritative MVP interface baseline for:
- CV-side contracts
- player-side contracts
- dashboard-side contracts
- persistence-side contracts
- supervision-side contracts
- network exposure rules
