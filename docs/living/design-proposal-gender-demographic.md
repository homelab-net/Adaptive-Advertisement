# Design Proposal: Gender Demographic Dimension

*Adaptive Retail Advertising MVP · living design artifact*
*CRM ref: CRM-003 · Approved 2026-04-01 · Status: Open (not yet implemented)*

---

## 1. Overview

Add `gender` as a second coarse-bin probabilistic demographic dimension alongside
`age_group` in the audience-state pipeline. Gender is expressed as two
appearance-based probability bins (`male`, `female`) averaged over the observation
window, following the identical privacy posture as age_group.

Once implemented, operators can assign `male_focus` or `female_focus` audience
tags to manifests. The decision-optimizer will select gender-targeted content when
live audience gender distribution clears the configured threshold and
`demographics_suppressed` is `False`.

---

## 2. Privacy Determination

This determination must be satisfied before any code is merged.

| Requirement | How gender satisfies it |
|---|---|
| PRIV-001 No individual-level data | Gender stored as window-aggregate probability distribution only; no per-person rows |
| PRIV-002 No tracking identifiers | Gender snapshots carry no `message_id`, `session_id`, or `person_id` |
| PRIV-003 No biometric templates | Bins are coarse visual appearance classifications, not face embeddings; `contains_face_embeddings: false` contract flag continues to hold |
| PRIV-004 Suppression gate | `demographics_suppressed = True` in ICD-3 blocks ALL gender conditions in policy evaluation, identically to age_group |
| PRIV-005 No egress of suppressed data | `audience_sink.py` sets `gender_*` DB columns to NULL when `demographics_suppressed = True`; privacy audit test verifies this |
| Locked invariant: no identity recognition | Gender is not used to identify or re-identify any individual across visits or windows |

**Conclusion:** gender addition is privacy-compliant under the existing baseline.
No baseline invariant is broken.

---

## 3. Gender Bin Definition

| Bin key | Meaning |
|---|---|
| `male` | Probability that the visual appearance of the observed audience is predominantly male-presenting |
| `female` | Probability that the visual appearance of the observed audience is predominantly female-presenting |

- Values are floats in `[0.0, 1.0]`.
- Both bins together approximate a distribution summing to ~1.0 (same as age_group bins).
- Bins are produced by the CV pipeline (DeepStream gender classification model or stub).
- In simulation / null-driver mode, the stub emits `{"male": 0.5, "female": 0.5}` when demographics are present.
- A three-bin extension (`non_binary`) is deferred pending CV model support; the schema is designed to accept it later without breaking changes.

---

## 4. Contract Changes

### 4.1 ICD-2 — `contracts/audience-state/cv-observation.schema.json`

Current `demographics` block contains `age_group`, `dwell_estimate_ms`, `suppressed`.

**Add** a `gender` object as a sibling to `age_group`:

```json
"gender": {
  "description": "Coarse appearance-based gender distribution over the observation window. Values are probabilities. Not derived from face embeddings.",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "male":   { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "female": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
  }
}
```

**Schema version:** remains `"1.0.0"` — `demographics` is optional and `gender`
is optional within `demographics`. No existing valid message is rejected.

**File:** `contracts/audience-state/cv-observation.schema.json`
**Location:** inside `properties.demographics.properties`, after the `age_group` block (line ~113).

---

### 4.2 ICD-3 — `contracts/decision-optimizer/audience-state-signal.schema.json`

Mirror the ICD-2 change. Current `state.demographics` contains `age_group`,
`dwell_estimate_ms`, `suppressed`.

**Add** the same `gender` object inside `properties.state.properties.demographics.properties`
(after `age_group`, around line ~124):

```json
"gender": {
  "description": "Smoothed coarse appearance-based gender distribution. Values are probabilities. Suppressed when demographics_suppressed is true.",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "male":   { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "female": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
  }
}
```

**Schema version:** remains `"1.0.0"` for same backward-compatibility reason.

**File:** `contracts/decision-optimizer/audience-state-signal.schema.json`

---

## 5. Service Changes

### 5.1 input-cv

**File:** `services/input-cv/input_cv/observation/models.py`

The `ObservationDemographics` model (or equivalent demographics dict field on
`CvObservation`) must accept an optional `gender` key containing `male` and
`female` float values.

Exact change depends on current model structure. Locate the demographics
Pydantic model and add:

```python
gender: Optional[dict[str, float]] = None
# keys: "male", "female" — each float in [0.0, 1.0]
```

Privacy enforcement: `gender` must not appear in `_BANNED_KEYS` (it is not a
biometric identifier). If any privacy-negative test scans for banned keys, verify
`"gender"` is not in the ban list (it should not be; banned keys are
`"image"`, `"frame_url"`, `"embedding"`, `"face_"` prefixed fields, etc.).

**File:** `services/input-cv/input_cv/observation/builder.py`

Extract gender bins from the raw pipeline metadata dict when available:

```python
raw_gender = pipeline_meta.get("gender")  # {"male": 0.6, "female": 0.4} or None
if raw_gender is not None:
    demographics["gender"] = {
        "male":   float(raw_gender.get("male", 0.0)),
        "female": float(raw_gender.get("female", 0.0)),
    }
```

In the null/stub driver, emit `{"male": 0.5, "female": 0.5}` when demographics
are present (mirrors the age_group stub pattern).

---

### 5.2 audience-state

**File:** `services/audience-state/audience_state/observation_store.py`

`compute_demographics()` currently averages `age_group` bins across the window
(lines ~150–171). Extend to also average `gender` bins using the identical
suppression logic:

```python
# After the existing age_group block:

gender_bins = ["male", "female"]
smoothed_gender: dict[str, float] = {}
for bin_name in gender_bins:
    values = [
        o.data["demographics"].get("gender", {}).get(bin_name)
        for o in obs_with_demog
    ]
    if any(v is None for v in values):
        # Gender bin absent in at least one observation → suppress all demographics
        return {"suppressed": True}
    smoothed_gender[bin_name] = round(sum(values) / len(values), 4)

result["gender"] = smoothed_gender
```

**Critical:** the suppression decision is holistic — if gender bins are absent
from any observation in the window, the entire demographics block is suppressed
(same rule as age_group today). This maintains the privacy guard that a partial
signal cannot leak a demographic condition.

**File:** `services/audience-state/audience_state/signal_publisher.py`

No structural change needed if the publisher serializes the full `demographics`
dict returned by `compute_demographics()`. Verify that the serialized ICD-3
message includes the `gender` key when present. Add an assertion in
`_validate_outbound()` if one exists.

---

### 5.3 decision-optimizer

**File:** `services/decision-optimizer/decision_optimizer/policy.py`

**Step 1 — Extend `_DEMOGRAPHIC_CONDITION_FIELDS`** (line ~66):

```python
_DEMOGRAPHIC_CONDITION_FIELDS = (
    "age_group_child_gte",
    "age_group_young_adult_gte",
    "age_group_adult_gte",
    "age_group_senior_gte",
    "gender_male_gte",       # NEW
    "gender_female_gte",     # NEW
)
```

**Step 2 — Add fields to `Rule` dataclass** (after line ~93, in the
demographic conditions block):

```python
# Gender conditions (ignored when demographics_suppressed)
gender_male_gte: Optional[float] = None
gender_female_gte: Optional[float] = None
```

**Step 3 — Extend `Rule.matches()`** (after the age_group evaluation block,
~line 159, before the time-of-day block):

```python
gender: dict = (
    signal.get("state", {})
    .get("demographics", {})
    .get("gender", {})
)
if self.gender_male_gte is not None:
    if float(gender.get("male", 0.0)) < self.gender_male_gte:
        return False
if self.gender_female_gte is not None:
    if float(gender.get("female", 0.0)) < self.gender_female_gte:
        return False
```

Note: no separate privacy guard needed here — the existing `if suppressed: return False`
block at line ~141 already gates all demographic conditions when
`demographics_suppressed` is `True`. The new gender fields are inside the same
`_has_demographic_condition()` check via `_DEMOGRAPHIC_CONDITION_FIELDS`.

**Step 4 — Extend `load_policy()`** (inside the `Rule(...)` constructor call,
~line 275):

```python
gender_male_gte=cond.get("gender_male_gte"),
gender_female_gte=cond.get("gender_female_gte"),
```

**Step 5 — Update module docstring** (conditions table, ~line 45):

```
gender_male_gte              float — demographics.gender.male >= value
gender_female_gte            float — demographics.gender.female >= value
```

---

### 5.4 dashboard-api

#### 5.4.1 ORM Model

**File:** `services/dashboard-api/dashboard_api/models.py`

Add two nullable float columns to `AudienceSnapshot` (after line ~286,
after the `age_group_senior` column):

```python
# Coarse gender bins — NULL when demographics_suppressed=True
gender_male: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
gender_female: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
```

Update the class docstring to mention gender columns.

#### 5.4.2 Alembic Migration

**File:** `services/dashboard-api/alembic/versions/0003_add_gender_demographics.py` *(new file)*

```python
"""Add gender columns to audience_snapshots.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audience_snapshots",
        sa.Column("gender_male", sa.Float, nullable=True),
    )
    op.add_column(
        "audience_snapshots",
        sa.Column("gender_female", sa.Float, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audience_snapshots", "gender_female")
    op.drop_column("audience_snapshots", "gender_male")
```

The migration is backward-compatible: existing rows receive `NULL` in both columns.
Downgrade drops the columns cleanly.

#### 5.4.3 Analytics Sink

**File:** `services/dashboard-api/dashboard_api/audience_sink.py`

In `_parse_snapshot()` (or equivalent row-building function), extract gender bins
and map to NULL when suppressed:

```python
gender_bins: dict = {}
if not demographics_suppressed:
    gender_bins = demographics.get("gender", {})

return AudienceSnapshot(
    # ... existing fields unchanged ...
    gender_male=gender_bins.get("male") if gender_bins else None,
    gender_female=gender_bins.get("female") if gender_bins else None,
)
```

#### 5.4.4 Rule Generator

**File:** `services/dashboard-api/dashboard_api/rule_generator.py`

**Step 1 — Add two tags to `AUDIENCE_TAGS`** (line ~35):

```python
AUDIENCE_TAGS: set[str] = {
    "attract",
    "general",
    "solo_adult",
    "group_adults",
    "adult_with_child",
    "teenager_group",
    "seniors",
    "male_focus",    # NEW
    "female_focus",  # NEW
}
```

**Step 2 — Add entries to `_AUDIENCE_CONDITIONS`** (after the `seniors` entry,
~line 105):

```python
"male_focus": {
    "presence_count_gte": 1,
    "presence_confidence_gte": 0.6,
    "gender_male_gte": 0.55,
},
"female_focus": {
    "presence_count_gte": 1,
    "presence_confidence_gte": 0.6,
    "gender_female_gte": 0.55,
},
```

Threshold of 0.55 is consistent with a simple majority signal — content activates
when the audience appears more than 55% male or female. Operators can override
via custom rules.

---

### 5.5 Services with no changes required

| Service | Reason |
|---|---|
| player | Consumes ICD-4 player-command only; no demographic data |
| creative | Manages manifests; demographic targeting is decision-optimizer concern |
| supervisor | Health monitoring only; no demographic awareness |
| dashboard-ui | Tag display is data-driven from `ALL_VALID_TAGS`; new tags appear automatically once rule_generator is updated |

---

## 6. Default Rules File

**File:** `services/decision-optimizer/rules/default-rules.json`

Add two optional example rules demonstrating gender conditions. These are
low-priority rules that do not interfere with existing defaults:

```json
{
  "rule_id": "gender-male-focus",
  "priority": 12,
  "manifest_id": "manifest-attract",
  "conditions": {
    "presence_count_gte": 1,
    "presence_confidence_gte": 0.6,
    "gender_male_gte": 0.55
  }
},
{
  "rule_id": "gender-female-focus",
  "priority": 11,
  "manifest_id": "manifest-attract",
  "conditions": {
    "presence_count_gte": 1,
    "presence_confidence_gte": 0.6,
    "gender_female_gte": 0.55
  }
}
```

Both reference `manifest-attract` as a stand-in. Operators replace `manifest_id`
with their actual gender-targeted content. These rules are informational examples
only — they produce the same output as the attract rule and are superseded by any
higher-priority rule.

---

## 7. Test Expansion Requirements

All 450+ existing tests must remain passing. The following new test methods are
required before the change can be marked Implemented.

### 7.1 Contract tests

**`tests/contract/test_icd2_cv_observation.py`** (+4 methods)

| Method | What it verifies |
|---|---|
| `test_demographics_with_gender_bins_valid` | Message with `demographics.gender.male` and `demographics.gender.female` in [0,1] passes schema validation |
| `test_demographics_gender_bins_out_of_range_rejected` | `gender.male = 1.5` fails schema validation |
| `test_demographics_gender_without_age_group_valid` | `demographics` with only `gender` (no `age_group`) is still valid (both optional) |
| `test_demographics_gender_extra_property_rejected` | `gender.unknown_bin` fails schema (`additionalProperties: false`) |

**`tests/contract/test_icd3_audience_state_signal.py`** (+3 methods)

| Method | What it verifies |
|---|---|
| `test_state_demographics_with_gender_valid` | ICD-3 message with `state.demographics.gender` passes schema validation |
| `test_state_demographics_gender_out_of_range_rejected` | `gender.female = -0.1` fails schema validation |
| `test_state_demographics_gender_extra_property_rejected` | `gender.extra` fails schema (`additionalProperties: false`) |

---

### 7.2 Unit tests — input-cv

**`services/input-cv/tests/unit/test_observation_model.py`** (+3 methods)

| Method | What it verifies |
|---|---|
| `test_demographics_gender_field_accepted` | `ObservationDemographics` (or equivalent) accepts valid `{"male": 0.6, "female": 0.4}` gender dict |
| `test_demographics_gender_none_is_optional` | `gender=None` produces valid observation (field is optional) |
| `test_demographics_gender_invalid_type_rejected` | `gender={"male": "high"}` raises `ValidationError` |

**`services/input-cv/tests/unit/test_privacy_negative.py`** (+1 method)

| Method | What it verifies |
|---|---|
| `test_gender_bins_not_in_banned_keys` | `"gender"` is not in `_BANNED_KEYS`; a valid gender dict does not trigger `PrivacyViolationError` |

---

### 7.3 Unit tests — audience-state

**`services/audience-state/tests/test_observation_store.py`** (+3 methods)

| Method | What it verifies |
|---|---|
| `test_compute_demographics_smooths_gender_bins` | With 3 observations each carrying `gender: {male: 0.6, female: 0.4}`, `compute_demographics()` returns `gender: {male: 0.6, female: 0.4}` |
| `test_gender_missing_from_one_observation_suppresses` | If one of three observations lacks `gender`, `compute_demographics()` returns `{"suppressed": True}` |
| `test_gender_smoothing_averages_correctly` | With `[{male:0.8,female:0.2}, {male:0.6,female:0.4}]`, result is `{male:0.7, female:0.3}` |

**`services/audience-state/tests/test_signal_publisher.py`** (+1 method)

| Method | What it verifies |
|---|---|
| `test_published_signal_includes_gender_when_present` | ICD-3 message dict produced by publisher contains `state.demographics.gender` when compute_demographics returns gender data |

---

### 7.4 Unit tests — decision-optimizer

**`services/decision-optimizer/tests/test_policy.py`** (+6 methods)

| Method | What it verifies |
|---|---|
| `test_gender_male_gte_matches_when_threshold_met` | Rule with `gender_male_gte=0.5` matches signal with `gender.male=0.7` |
| `test_gender_male_gte_no_match_when_below_threshold` | Rule with `gender_male_gte=0.5` does NOT match signal with `gender.male=0.3` |
| `test_gender_female_gte_matches_when_threshold_met` | Rule with `gender_female_gte=0.5` matches signal with `gender.female=0.6` |
| `test_gender_condition_blocked_when_demographics_suppressed` | Rule with `gender_male_gte=0.5` does NOT match when `demographics_suppressed=True`, even if `gender.male=0.9` in signal |
| `test_gender_and_age_combined_conditions_both_must_pass` | Rule with `age_group_adult_gte=0.5` AND `gender_female_gte=0.5` only matches when both conditions are met |
| `test_load_policy_parses_gender_conditions_from_json` | `load_policy()` correctly populates `Rule.gender_male_gte` and `Rule.gender_female_gte` from JSON conditions dict |

---

### 7.5 Unit tests — dashboard-api

**`services/dashboard-api/tests/test_rule_generator.py`** (+3 methods)

| Method | What it verifies |
|---|---|
| `test_male_focus_tag_in_audience_tags` | `"male_focus"` is in `AUDIENCE_TAGS` and `ALL_VALID_TAGS` |
| `test_female_focus_tag_in_audience_tags` | `"female_focus"` is in `AUDIENCE_TAGS` and `ALL_VALID_TAGS` |
| `test_male_focus_generates_gender_male_gte_condition` | `generate_rules(manifest_id, ["male_focus"], ...)` produces a rule dict containing `"gender_male_gte": 0.55` in conditions |

**`services/dashboard-api/tests/test_analytics.py`** (+2 methods)

| Method | What it verifies |
|---|---|
| `test_audience_snapshot_persists_gender_columns` | `_parse_snapshot()` sets `gender_male` and `gender_female` from ICD-3 `demographics.gender` when not suppressed |
| `test_gender_columns_null_when_demographics_suppressed` | `_parse_snapshot()` sets `gender_male=None`, `gender_female=None` when `demographics_suppressed=True` |

---

### 7.6 Integration tests

**`tests/integration/test_privacy_audit.py`** (+2 methods)

| Method | What it verifies |
|---|---|
| `test_gender_data_absent_from_egress_audit_when_suppressed` | Serialized ICD-3 bytes contain no `gender` key when `demographics_suppressed=True` in the emitted signal |
| `test_gender_bins_not_flagged_as_biometric_by_egress_scan` | Egress audit scanner does not classify `"male"` / `"female"` float bin values as biometric identifiers (they are probabilities, not embeddings) |

**`tests/integration/test_log_pii_lint.py`** (+1 method)

| Method | What it verifies |
|---|---|
| `test_gender_probability_values_not_flagged_as_pii` | Runtime log capture confirms gender bin float values (e.g., `0.6`) are not matched by any PII-detection pattern in the linter |

---

### 7.7 Migration test

**`tests/test_postgres_migration.py`** — existing file, extend existing migration
test pattern (+1 method or extend existing):

| Method | What it verifies |
|---|---|
| `test_migration_0003_adds_gender_columns` | After running migration `0003`, `audience_snapshots` table has `gender_male` and `gender_female` nullable float columns; downgrade removes them cleanly |

---

## 8. Implementation Order

Execute phases in sequence. Each phase must pass its tests before the next begins.

| Phase | Actions | Gate |
|---|---|---|
| **P0 — Contracts** | Update `cv-observation.schema.json` and `audience-state-signal.schema.json` | 7 new contract tests pass; 0 existing contract tests regress |
| **P1 — input-cv** | Update `models.py` and `builder.py`; extend stub driver | 4 new input-cv unit tests pass |
| **P2 — audience-state** | Extend `compute_demographics()` and verify publisher serialization | 4 new audience-state unit tests pass |
| **P3 — decision-optimizer** | Extend `_DEMOGRAPHIC_CONDITION_FIELDS`, `Rule`, `matches()`, `load_policy()`, and module docstring; update `default-rules.json` | 6 new policy unit tests pass |
| **P4 — dashboard-api** | Create migration `0003`, update `AudienceSnapshot`, update `audience_sink.py`, update `rule_generator.py` | New migration test pass; 5 new dashboard-api unit tests pass |
| **P5 — Integration + privacy** | Extend `test_privacy_audit.py` and `test_log_pii_lint.py` | 3 new integration tests pass |
| **P6 — Regression** | Full `pytest` run across all services and test suites | All 482+ tests pass (450+ existing + ~32 new) |
| **P7 — Docs** | Update `system-development-snapshot.md`; mark CRM-003 Implemented | Snapshot current; CRM entry closed |

---

## 9. Acceptance Criteria

The change is **Done** when all of the following are true:

- [ ] `cv-observation.schema.json` contains `demographics.gender` with `male` and `female` float properties, `additionalProperties: false`
- [ ] `audience-state-signal.schema.json` contains `state.demographics.gender` with identical structure
- [ ] `Rule` dataclass has `gender_male_gte` and `gender_female_gte` optional float fields
- [ ] `_DEMOGRAPHIC_CONDITION_FIELDS` includes both gender fields
- [ ] `Rule.matches()` evaluates gender conditions with suppression guard
- [ ] `load_policy()` parses gender conditions from JSON
- [ ] `compute_demographics()` smooths gender bins; suppresses if any observation lacks them
- [ ] `AudienceSnapshot` has `gender_male` and `gender_female` nullable float columns
- [ ] Alembic migration `0003` creates those columns and downgrade removes them
- [ ] `audience_sink.py` writes `NULL` for gender columns when `demographics_suppressed=True`
- [ ] `AUDIENCE_TAGS` contains `"male_focus"` and `"female_focus"`
- [ ] `_AUDIENCE_CONDITIONS` maps both tags to `gender_*_gte` conditions at threshold 0.55
- [ ] All 32 new test methods listed in §7 pass
- [ ] All 450+ pre-existing tests pass (zero regression)
- [ ] Privacy audit test confirms gender not present in serialized bytes when suppressed
- [ ] `system-development-snapshot.md` updated
- [ ] CRM-003 status set to `Implemented`

---

## 10. Out-of-Scope Items

The following are explicitly deferred and must NOT be included in this change:

- Three-bin gender (`non_binary`) — deferred pending CV model support
- Per-manifest gender targeting in `creative-manifest.schema.json` — manifests remain demographic-agnostic content containers
- Gender analytics aggregation in dashboard analytics endpoint responses — existing summary endpoint returns presence + age; gender aggregate endpoint is a future enhancement
- Multi-camera gender fusion — gender remains per-camera signal, consistent with age_group
- UI changes to dashboard-ui for gender tag display — tags are rendered dynamically from `ALL_VALID_TAGS`; no template changes needed
- Formal ICD revision (v1.2) — fold into next scheduled ICD revision, not this sprint

---

*Document status: Draft — approved for implementation per CRM-003.*
*Author: Agent / Founder direction 2026-04-01.*
