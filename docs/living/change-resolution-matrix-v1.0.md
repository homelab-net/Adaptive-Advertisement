# Change Resolution Matrix

*Adaptive Retail Advertising MVP · living governance artifact*

**Use.** This document is a living interim ledger between formal document revisions. Agents shall read it before work that may touch scope, architecture, contracts, persistence, privacy, reliability, or validation posture, and shall update it when a material conflict or approved change occurs.

> **Purpose**  
> Govern AI-assisted software implementation for the privacy-first adaptive retail advertising MVP. The governance charter acts as both a human-readable implementation constitution and a pseudo-system prompt for coding agents.

## Operating Instructions

- Create a new entry for any contradiction, ambiguity, implementation-discovered issue, approved enhancement request, or rejected out-of-scope proposal.
- Do not silently code around conflicts. Log them first, then route according to disposition.
- Once a formal project document revision absorbs the change, mark the entry as folded into that revision and close it.

### Status Vocabulary

| Status | Meaning |
|---|---|
| Open | Logged but not yet dispositioned |
| Needs Clarification | Awaiting founder or document-owner clarification |
| Approved | Change accepted and implementation authorized |
| Rejected | Will not be implemented under current baseline |
| Implemented | Code/config change completed but not yet folded into formal revision |
| Folded into Rev | Absorbed into a later authoritative document revision |

## Matrix

| Change ID | Date | Driver / Type | Summary | Affected Artifacts | Disposition | Owner | Status | Folded Into Rev |
|---|---|---|---|---|---|---|---|---|
| CRM-001 |  |  | Template placeholder entry. Replace when first real change is logged. |  |  |  | Open |  |
| CRM-002 | 2026-03-23 | Implementation discovery / Interface ambiguity | ICD-4 player-command schema defines `freeze` command but no corresponding `unfreeze` command. Command description says "stop accepting switch commands until unfrozen" but no unfreezing mechanism exists in the four-command enum. Player scaffold implements pragmatic decision: `activate_creative` in FROZEN state is accepted and lifts the freeze. This is the only recovery path available without a schema change. | `contracts/player/player-command.schema.json`, `services/player/player/state.py` | **Approved** — confirmed `activate_creative`-as-unfreeze is the intended mechanism. Rationale: (1) `freeze` reason codes (`cv_degraded`, `decision_degraded`, `thermal_protection`) all describe transient degradation that resolves when the decision engine can produce a new activation; (2) a separate `unfreeze` command would create a two-step race window (unfrozen but no target manifest) with no never-blank benefit; (3) `activate_creative` semantics ("here is the next creative to play") implicitly confirm the freeze condition has cleared. ICD-4 schema description updated to make this explicit. No new command needed. | Agent | Implemented | ICD-4 schema description updated 2026-03-24 |
| CRM-003 | 2026-04-01 | Enhancement / Scope request — founder-directed | Add `gender` as a second coarse-bin probabilistic demographic dimension alongside `age_group` in ICD-2, ICD-3, the decision-optimizer policy engine, dashboard-api rule generator, analytics DB sink, and test suite. Gender is represented as two appearance-based probabilistic bins (`male`, `female`), following the identical privacy posture as age_group: aggregate-only, no per-person identifiers, suppressed when confidence is below gating threshold. Full design, file-by-file change map, and acceptance criteria recorded in `docs/living/design-proposal-gender-demographic.md`. | `contracts/audience-state/cv-observation.schema.json`, `contracts/decision-optimizer/audience-state-signal.schema.json`, `services/input-cv/input_cv/observation/models.py`, `services/input-cv/input_cv/observation/builder.py`, `services/audience-state/audience_state/observation_store.py`, `services/audience-state/audience_state/signal_publisher.py`, `services/decision-optimizer/decision_optimizer/policy.py`, `services/decision-optimizer/rules/default-rules.json`, `services/dashboard-api/dashboard_api/models.py`, `services/dashboard-api/dashboard_api/audience_sink.py`, `services/dashboard-api/dashboard_api/rule_generator.py`, `services/dashboard-api/alembic/versions/0003_add_gender_demographics.py` (new), `tests/contract/test_icd2_cv_observation.py`, `tests/contract/test_icd3_audience_state_signal.py`, `tests/integration/test_privacy_audit.py`, `tests/integration/test_log_pii_lint.py`, plus per-service unit test files | **Approved** — founder-directed scope expansion 2026-04-01. Privacy posture unchanged: `demographics_suppressed` gate applies to gender identically to age_group; no face embeddings; no per-person identifiers; coarse bins only. | Founder / Agent | Open | — |

## Detailed Entries

### CRM-003 — Gender Demographic Dimension

| Field | Detail |
|---|---|
| **Change driver** | Enhancement / Scope request — founder-directed 2026-04-01 |
| **Rationale** | Operators need gender as an additional audience-targeting dimension to enable demographic-segmented ad delivery (e.g., show male-skewed content when audience is predominantly male). Gender follows the identical coarse-bin probabilistic design as age_group and inherits all existing privacy guards. |
| **Baseline references** | Technical-requirements-package.md §CV-006 (optional coarse attributes, probabilistic only); §PRIV-001..PRIV-005 (no per-person data, no biometric templates, suppression gate); consolidated-icd-v1.1 §ICD-2 and §ICD-3 demographics block; governance charter §Locked invariants |
| **Options considered** | (1) Two-bin: `male` / `female` — matches standard CV model outputs, minimal schema complexity, consistent with existing coarse-bin philosophy. *Selected.* (2) Three-bin: `male` / `female` / `non_binary` — more inclusive but no current CV model produces a reliable `non_binary` probability at retail-signage distances; deferred. (3) Skip gender entirely — not acceptable per founder direction. |
| **Privacy determination** | Gender bins are appearance-based visual classification probabilities only. They are: aggregate over the observation window (not per-person), coarse (two bins, no sub-categories), suppressed when `demographics_suppressed=True`, not stored with any message_id or session identifier, and never logged at individual level. `contains_face_embeddings: false` contract flag continues to apply — gender is not derived from face embeddings. Consistent with PRIV-001..PRIV-005. |
| **Implementation impact** | See `docs/living/design-proposal-gender-demographic.md` for full file-by-file map. In summary: 2 contract schemas, 4 services (input-cv, audience-state, decision-optimizer, dashboard-api), 1 new Alembic migration, 2 new audience targeting tags (`male_focus`, `female_focus`), 2 new policy condition fields (`gender_male_gte`, `gender_female_gte`), and ~32 new test methods across 10 test files. |
| **Required doc updates** | `docs/living/system-development-snapshot.md` (contract status table, service notes), `docs/authoritative/icd/consolidated-icd-v1.1-csi-local-ingest.md` §ICD-2 and §ICD-3 demographic block descriptions (fold into v1.2 or v2.0 ICD revision) |
| **Required test updates** | Contract: `test_icd2_cv_observation.py` (+4 methods), `test_icd3_audience_state_signal.py` (+3 methods). Unit: `test_observation_model.py` (+3), `test_observation_store.py` (+3), `test_signal_publisher.py` (+1), `test_policy.py` (+6), `test_rule_generator.py` (+3), `test_analytics.py` (+2). Integration: `test_privacy_audit.py` (+2), `test_log_pii_lint.py` (+1). All 450+ existing tests must remain passing. |

---

## Detailed Entry Template

| Field | Entry guidance |
|---|---|
| Change driver | Bug, implementation discovery, scope request, architecture correction, privacy issue, reliability issue, validation finding, or ops need. |
| Rationale | Why the change or rejection is being considered. |
| Baseline references | Exact documents / sections that control or conflict. |
| Options considered | Brief alternatives evaluated. |
| Implementation impact | Services, files, tests, and operational behavior affected. |
| Required doc updates | Which future formal revisions must absorb the change. |
| Required test updates | Contract, integration, privacy-negative, or system evidence that must be refreshed. |
