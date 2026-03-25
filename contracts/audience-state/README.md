# audience-state Contract Stubs

This folder contains code-facing contract artifacts for the `audience-state` service.

## ICD reference

ICD-2: CV Pipeline → Audience-State Service (consolidated-icd-v1.0.md)

Transport: MQTT v5.0 over TCP, TLS required in production.

Topic namespace: `cv/v1/observations/{tenant_id}/{site_id}/{camera_id}`

QoS: 1 (at-least-once; consumers must deduplicate by `message_id`).

## Current contents

- `cv-observation.schema.json` — MVP observation message published by `input-cv` and consumed by `audience-state`

## Ordering and idempotency rules

- Consumers must deduplicate by `message_id`.
- Consumers must handle out-of-order delivery using `frame_seq`.
- Strict ordering across reconnects is not assumed; application-layer ordering applies.

## Privacy contract

The `privacy` block fields (`contains_images`, `contains_frame_urls`, `contains_face_embeddings`) are schema-enforced `const: false`. A message that sets any of these to `true` is a contract violation and must be rejected.

## Expected follow-on work

- MQTT topic and broker configuration documentation
- example observation fixture file
- schema validation tests
- typed message model in service code
- smoothing and confidence-gating logic
- audience-state output schema (ICD-3 audience-state → decision-optimizer)
