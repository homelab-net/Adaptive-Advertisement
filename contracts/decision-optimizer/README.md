# decision-optimizer Contract Stubs

This folder contains code-facing contract artifacts for the `decision-optimizer` service.

## ICD reference

ICD-3: Audience-State Service → Decision-Optimizer (consolidated-icd-v1.1 + interface-addendum-v1.0)

Transport: MQTT v5.0 over TCP, TLS required in production.

Topic namespace: `audience/v1/state/{tenant_id}/{site_id}/{camera_id}`

QoS: 1 (at-least-once; consumers must deduplicate by `message_id`).

## Current contents

- `audience-state-signal.schema.json` — smoothed, confidence-gated audience state signal published by `audience-state` and consumed by `decision-optimizer`

## Ordering and idempotency rules

- Consumers must deduplicate by `message_id`.
- Consumers must respect `state.stability.freeze_decision`. When `true`, the decision-optimizer must hold its current selection and not switch content.
- State signals are emitted at the decision loop cadence (default: 1 Hz per TRD PERF-004). Consumers must handle gaps gracefully.

## Decision-loop behavior contract

The `state.stability.freeze_decision` flag encodes policy constraints (dwell minimum, cooldown, low-confidence hold) in the audience-state layer so the decision-optimizer does not need to re-implement them. The optimizer must honor this flag.

When `source_quality.pipeline_degraded` is `true` or `source_quality.signal_age_ms` exceeds the configured staleness threshold, the decision-optimizer must treat the signal as stale and hold current content rather than switching.

## Privacy contract

The `privacy` block fields (`contains_images`, `contains_frame_urls`, `contains_face_embeddings`) are schema-enforced `const: false`. This mirrors the ICD-2 privacy contract. A message that sets any of these to `true` is a contract violation and must be rejected.

## Expected follow-on work

- MQTT topic and broker configuration documentation
- example audience-state-signal fixture file
- schema validation tests
- typed message model in service code
- decision-optimizer rules engine implementation (rules-first for MVP)
- integration tests: freeze_decision honored, stale signal hold behavior
