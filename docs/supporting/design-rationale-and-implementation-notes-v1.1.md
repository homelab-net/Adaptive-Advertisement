# Design Rationale and Implementation Notes v1.1

Source file: `Adaptive_Retail_Design_Rationale_and_Implementation_Notes_v1_1.txt`
Import type: curated repo-native digest from source
Authority: supporting only; does not override roadmap, ICDs, TRD, V&V, or other authoritative baselines

---

## Role

This source preserves selected, high-value implementation rationale extracted from prior project chat so it is not lost between formal revisions. It is explicitly a **supporting reference** and should be consulted only after the active formal baseline.

## Why this source matters

The source narrows preserved chat-derived material to items that materially affect:
- build and deployment posture
- privacy and dashboard exposure boundaries
- remote support workflow
- appliance operability and support burden

It explicitly rejects exploratory business, pricing, speculative packaging, and unvalidated technical estimates as governing input.

## Most important preserved rationales

### 1. Golden-image deployment posture
The source preserves the rationale that cloning a known-good appliance image is the preferred scaling posture for field deployment because it reduces configuration drift and founder support burden.

Implication for repository work:
- provisioning, commissioning, and update logic should assume a reproducible appliance image model
- future ops documentation should include a formal golden-image / commissioning SOP

### 2. DHCP-by-default local networking
The source records DHCP-by-default as the practical local-network assumption for cloned devices so multiple deployments do not collide on static LAN settings.

Implication:
- deployment automation and install docs should default to DHCP unless a customer-specific exception is deliberately configured

### 3. First-boot provisioning requirement
A critical note in the source is that cloned devices must not share identity-bearing material. On first boot or commissioning, each appliance must generate or receive unique device-specific identity such as:
- hostname
- SSH keys
- WireGuard identity
- other per-device secrets

Implication:
- commissioning is not optional ceremony; it is a core appliance security requirement

### 4. VPN-only remote support workflow
The source clarifies the intended support path:
- the device initiates outbound VPN connectivity
- the operator joins the same private network
- support occurs over SSH or tunneled dashboard access
- inbound public exposure at the client site is avoided

Implication:
- remote support docs and implementation should keep the runtime path separate from support infrastructure
- WAN assistance may exist, but must not become a runtime dependency

### 5. No raw-feed dashboard posture
The source reinforces the privacy claim by preserving the rationale that operators and clients should not see raw live video through the dashboard. The web layer should receive only approved metadata or anonymized diagnostic imagery rather than a raw camera stream.

Implication:
- dashboard design must remain privacy-protective by construction
- any diagnostic imagery needs explicit constraint and justification

### 6. Local dashboard authentication requirement
The source treats LAN-reachable dashboard access without authentication as unacceptable, especially on shared or weakly segmented local networks.

Implication:
- local-only does not mean anonymous
- dashboard security baselines and deployment notes should require authentication for any LAN-exposed UI

### 7. Local hostname discovery convention
The source preserves the rationale for a predictable local discovery pattern such as mDNS/hostname-based reachability so installers and support personnel do not have to memorize changing IP addresses.

Implication:
- commissioning docs should standardize a hostname-based discovery approach where feasible

### 8. HTTPS-by-default local dashboard posture
Even for local-only access, the source favors encrypted transport by default, with a pragmatic MVP stance that self-signed local certificates may be acceptable if documented clearly.

Implication:
- dashboard deployment and commissioning guidance should account for local certificate handling, not plain HTTP by default

### 9. Open-network exposure warning
The source records the operational warning that placing the appliance on an open or poorly segmented guest network materially increases risk, even when runtime remains local-first.

Implication:
- operator handoff and install checklists should warn against insecure network placement

### 10. VPS role clarification
The source clarifies that any VPS or relay component is support infrastructure only and not part of the client-facing adaptive runtime path.

Implication:
- architecture and support material should keep support-plane infrastructure clearly separated from the mandatory in-store runtime plane

## High-value principles preserved verbatim in substance

The source explicitly preserves several strong guidance statements that remain useful for implementation review:
- playback remains the hard dependency
- golden-image cloning is acceptable, but identity-bearing material must be unique per device
- local client-site networking should assume DHCP unless explicitly configured otherwise
- remote administration should assume outbound device connectivity and VPN-only operator access rather than open inbound ports
- dashboard visibility should remain limited to approved diagnostic views and aggregate metadata
- any LAN-exposed dashboard must require authentication
- local access UX should favor a consistent hostname-based discovery pattern where practical
- remote support infrastructure must remain outside the mandatory runtime dependency path

## What the source explicitly does not promote

The source is also valuable because it clearly excludes non-governing material from prior chat history, including:
- exploratory pricing tiers and ROI projections
- speculative product packaging
- unvalidated performance or memory calculations
- rhetorical or persuasive conversational framing

That exclusion boundary helps keep the repo from turning informal exploration into accidental baseline.

## Recommended follow-on document actions named by source

The source recommends future formalization work in these areas:
1. a golden-image / commissioning SOP
2. a remote-support workflow note for WireGuard-only access
3. a dashboard privacy constraint stating that only anonymized diagnostic imagery and approved metadata may be surfaced outside the CV runtime
4. a small threat-considerations appendix distinguishing UI exposure risk from privileged insider risk
5. an explicit local dashboard access-control requirement
6. install / commissioning guidance for hostname discovery, certificate handling, and open-network warnings

## Practical repository value

This source is useful as a **rationale bridge** between formal baselines and implementation details that are clearly directionally locked but not yet fully absorbed into authoritative documents. It helps explain *why* the project is leaning toward:
- image-based deployment and commissioning discipline
- authentication even on local networks
- privacy-preserving dashboard design
- VPN-only remote support posture
- separation of runtime plane and support plane

## Repository note

This repo-native file is a curated digest rather than a line-for-line copy. The uploaded source text remains the higher-fidelity reference for exact wording.