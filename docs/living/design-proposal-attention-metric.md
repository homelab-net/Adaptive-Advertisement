# Design Proposal — Attention Metric (CRM-004)

**Status:** Approved 2026-04-02 (not yet implemented)

---

## Summary

Attention is a CV-derived head-pose probability metric that estimates whether the observed audience is gazing toward the display. It drives the attract→targeted ad transition and provides a campaign engagement quality signal. Unlike demographic dimensions, attention is a behavioral metric: it captures real-time engagement state rather than audience composition. It flows through ICD-2 at the observation root and through ICD-3 as `state.attention`, and it is evaluated by the policy engine independently of the demographics suppression gate.

---

## Privacy Analysis

**Behavioral, not demographic.** Attention is derived from head-pose estimation — the angular orientation of heads in the camera frame relative to the display axis. It produces a single aggregate probability across the observation window. No face recognition is performed. No individual is identified, tracked between frames, or associated with a session identifier.

**Aggregate window-level only.** The attention value published on ICD-3 is a smoothed scalar computed over the current observation window (e.g., a rolling 3–5 second buffer). It is not a per-person value and is not disaggregated. No per-person record is written or retained.

**No face recognition, no identity.** Head-pose estimation operates on bounding-box crops and skeletal key-point geometry. No face embeddings are computed or stored. The `contains_face_embeddings: false` contract flag continues to apply.

**Separate from `demographics_suppressed` gate.** Attention is not a member of the demographics block and is not suppressed when `demographics_suppressed=True`. The policy engine evaluates `_ATTENTION_CONDITION_FIELDS` in a separate block before the demographics block. This is intentional: attention is an engagement signal, not a personal characteristic. Operators who disable demographic inference still benefit from the attract→targeted gate.

**Camera placement constraint.** Accurate head-pose gaze estimation requires the camera to be mounted close to the display center-axis. A misconfigured camera (e.g., mounted 90° off-axis) would produce systematically incorrect attention scores, potentially either always-high or always-low. The `attention_camera_angle_validated` deployment gate (see Deployment Constraint section) protects against this.

---

## Signal Structure

### ICD-2 — CV Observation (`cv-observation.schema.json`)

Attention is added at the observation root, not inside the `demographics` block:

```
attention: {
  engaged: <float 0.0–1.0>,   # fraction of observed heads oriented toward display
  ambient: <float 0.0–1.0>    # fraction oriented away or indeterminate
}
```

Both fields sum to approximately 1.0 but may not sum exactly due to the indeterminate fraction being absorbed into `ambient`. `engaged` is the operative field consumed by downstream services. The block is optional (omitted when the camera angle has not been validated or when head-pose models are unavailable).

### ICD-3 — Audience State Signal (`audience-state-signal.schema.json`)

Attention surfaces under `state.attention`:

```
state: {
  ...existing fields...,
  attention: {
    engaged: <float 0.0–1.0>,
    window_seconds: <int>     # smoothing window used (e.g., 5)
  }
}
```

The `window_seconds` field allows downstream consumers to understand the temporal resolution of the signal. `state.attention` is omitted entirely when `attention_camera_angle_validated=False` in the device configuration.

---

## Attention Gate Design

### Pre-filter vs. priority design

The attention gate is implemented as a **pre-filter condition**, not a priority modifier. When a rule contains an `attention_engaged_gte` condition, the rule is skipped entirely if the current `state.attention.engaged` is below the threshold. This is distinct from demographic conditions, which affect which rules fire but not whether the rule is eligible.

The pre-filter design was selected over a continuous priority modifier (CRM-004 option 3) because:

- Binary gates produce predictable, auditable transitions. An operator can reason: "the ad switches when the audience is looking."
- A continuous modifier would require re-tuning priority scales across all existing rules.
- The attract→targeted transition is an on/off transition by design; fractional priority interpolation would not add value for v1.

### Absent attention = pass (backward compatibility)

If `state.attention` is absent from the ICD-3 signal (e.g., `attention_camera_angle_validated=False`, or the device is running a model that does not emit attention), any `attention_engaged_gte` condition in a rule **silently passes**. This preserves backward compatibility: existing deployments without validated camera angles continue to operate under demographic-only logic without modification.

### Auto-injection by `rule_generator`

The rule_generator module auto-injects an `attention_engaged_gte` condition into every rule generated for a **demographic audience tag** (i.e., tags in the age, gender, and attire dimension groups). The injected threshold is:

```python
_ATTENTION_GATE_THRESHOLD = 0.35
```

This threshold is not user-configurable and is not exposed as a manifest tag. The rationale: 0.35 is a permissive gate — it requires that at least 35% of the observed audience heads are oriented toward the display before demographic targeting fires. This prevents demographic rules from activating on pure passersby.

Attract-mode and general-audience rules (tags not in any dimension group) do **not** receive the auto-injected gate. The attract→attract transition should not require engagement; only the attract→targeted transition does.

### Sliding window stability (anti-flicker)

The `compute_attention()` method in audience-state applies a rolling average over a configurable window (default 5 seconds) before publishing. This prevents rapid oscillation between engaged/not-engaged states caused by transient head turns, which would produce visible ad-switching flicker on the display.

---

## Analytics

### `PlayEvent.attention_at_trigger`

A new column `attention_at_trigger` (float, nullable) is added to the `PlayEvent` ORM model. When a play event is recorded, the dashboard-api `play_event_sink` queries the `AudienceSnapshot` table for the nearest snapshot within a 5-second window of the event timestamp. If a matching snapshot exists, `attention_engaged` from that snapshot is written to `attention_at_trigger`. If no matching snapshot is found within the window, the column is null.

This provides a per-play-event record of audience engagement quality at the moment an ad was triggered, enabling post-hoc analysis of whether targeted ads are firing on genuinely engaged audiences.

### `avg_attention_at_trigger` on `CampaignAnalyticsOut`

The campaign analytics endpoint aggregates `attention_at_trigger` across all play events for a given campaign within the query window and returns `avg_attention_at_trigger` (float, nullable). This field is null if no play events for the campaign have a non-null `attention_at_trigger`. Operators use this to compare engagement quality across campaigns and time windows.

---

## Deployment Constraint

### `attention_camera_angle_validated` configuration flag

The device configuration (environment variable or config file) includes:

```
ATTENTION_CAMERA_ANGLE_VALIDATED=true|false  (default: false)
```

When `false`:
- `input-cv` does not emit the `attention` block on ICD-2 observations.
- `audience-state` does not compute or publish `state.attention` on ICD-3.
- All `attention_engaged_gte` conditions in policy rules silently pass.
- `PlayEvent.attention_at_trigger` is always null.

When `true`, the operator has certified that the camera is mounted within **±30° of the display center-axis** (the horizontal angle between the camera optical axis and the perpendicular to the display face). Outside this angular range, head-pose gaze estimation becomes unreliable: a head facing the camera is no longer well-correlated with a head facing the display.

This flag must be set explicitly by the deployment operator after physically verifying camera placement. It is not set automatically by any software component.

---

## Acceptance Criteria

- [ ] ICD-2 schema (`cv-observation.schema.json`) includes optional `attention` block at root with `engaged` and `ambient` float fields, `additionalProperties: false`.
- [ ] ICD-3 schema (`audience-state-signal.schema.json`) includes optional `state.attention` object with `engaged` float and `window_seconds` integer.
- [ ] `input-cv` service defines `ObservationAttention` model and builder extraction logic; emits attention block only when `attention_camera_angle_validated=True`.
- [ ] `audience-state` service implements `compute_attention()` with rolling-window smoothing and includes `state.attention` in published ICD-3 signal when validated.
- [ ] Policy engine evaluates `_ATTENTION_CONDITION_FIELDS` in a separate block that is independent of `demographics_suppressed`; absent attention silently passes.
- [ ] `rule_generator` auto-injects `attention_engaged_gte: 0.35` into all rules generated for demographic audience tags; attract/general tags are not modified.
- [ ] `AudienceSnapshot` ORM model has `attention_engaged` nullable float column; Alembic migration 0004 creates it.
- [ ] `PlayEvent` ORM model has `attention_at_trigger` nullable float column; `play_event_sink` populates it from nearest snapshot within 5 seconds.
- [ ] Campaign analytics endpoint returns `avg_attention_at_trigger` (nullable float) aggregated across play events in the query window.
- [ ] Integration test confirms that with `attention_camera_angle_validated=False`, no attention data appears in any published signal, all `attention_engaged_gte` conditions pass, and `attention_at_trigger` is null on all play events.
