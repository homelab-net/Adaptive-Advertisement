# System / Development Snapshot

*Adaptive Retail Advertising MVP · living execution-state artifact*

**Use.** This document records actual build and environment state for parallel human and AI contributors. Agents shall read it before work begins and update it after any material implementation, integration, validation, or environment change.

> **Purpose**  
> Govern AI-assisted software implementation for the privacy-first adaptive retail advertising MVP. The governance charter acts as both a human-readable implementation constitution and a pseudo-system prompt for coding agents.

## Update Rules

- Mark states precisely: `Not Started`, `Scaffolded`, `Implemented`, `Integrated`, `Verified`, `Blocked`, or `Deferred`.
- Do not mark anything `Verified` without evidence.
- If the snapshot conflicts with the active formal baseline, log the issue in the Change Resolution Matrix rather than silently reconciling it.

## 1. Authoritative Document Baseline

| Item | Current status / notes |
|---|---|
| Current roadmap / golden plan |  |
| Current ICD baseline |  |
| Current TRD / requirements baseline |  |
| Current V&V baseline |  |

## 2. Environment and Appliance State

| Item | Current status / notes |
|---|---|
| Target hardware SKU |  |
| JetPack / OS version |  |
| Container runtime / compose status |  |
| Camera setup |  |
| Display setup |  |
| WireGuard / remote admin status |  |

## 3. Repo and Workspace Status

| Item | Current status / notes |
|---|---|
| Primary repo / branch |  |
| Active workstreams |  |
| Pending merges / review items |  |
| Known local-only changes |  |

## 4. Service Status

| Item | Current status / notes |
|---|---|
| input-cv |  |
| audience-state |  |
| decision-optimizer |  |
| creative |  |
| player |  |
| dashboard-api |  |
| postgres |  |
| supervisor |  |

## 5. Interface and Data Contract Status

| Item | Current status / notes |
|---|---|
| CV -> audience-state |  |
| audience-state -> decision-optimizer |  |
| decision -> creative / player |  |
| dashboard-api -> postgres |  |

## 6. Verification Status

| Item | Current status / notes |
|---|---|
| Latest unit test state |  |
| Latest contract test state |  |
| Latest integration test state |  |
| Latest system / recovery evidence |  |

## 7. Current Blockers and Open Risks

| Item | Current status / notes |
|---|---|
| Blocker 1 |  |
