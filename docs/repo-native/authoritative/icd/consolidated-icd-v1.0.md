# Consolidated ICD v1.0

Source file: `Consolidated Interface Control Document v1.0 for DeepStream, FastAPI, and React.pdf`
Import type: curated authoritative extract
Document ID in source: `ICD-CONSO-EDGESIGNAGE`
Version in source: `v1.0`
Status in source: production-ready baseline with explicitly tracked TBDs
Date in source: 2026-03-16

---

## Role

This consolidated Interface Control Document defines four implementable, testable, versioned interfaces for the edge-first pipeline:
- camera → CV inference
- CV inference → audience state
- audience state → decisioning
- decisioning → player activation

The document is intended to be production-ready in the sense that engineers can implement against it without inventing missing contract details.

## Primary purpose carried by source

The source emphasizes exact message schemas, authentication patterns, failure semantics, idempotency and ordering rules, and testing/monitoring requirements, all under a strict privacy boundary.

## Hard privacy rule carried by source

A non-negotiable constraint is privacy-by-contract:
- metadata messages must not contain images
- metadata messages must not contain frame URLs
- metadata messages must not contain base64 blobs
- metadata messages must not contain face embeddings or other reversible biometric templates

The source makes this a schema-enforced rule, not a best-effort implementation preference.

## Scope and exclusions

### In scope
- ICD-1 Camera → CV Pipeline
- ICD-2 CV Pipeline → Audience-State Service
- ICD-3 Audience-State Service → Decision Engine
- ICD-4 Decision Engine → Player

### Explicitly out of scope
- model architecture, training, or evaluation targets
- creative asset system interfaces except identifiers passed to the player
- full network topology, IAM-provider selection, and exact OAuth flows beyond bearer-token semantics
- storage schema and retention rules, except what must be logged or monitored by contract

## Architecture context distilled from source

The ICD assumes that the high-level architecture boundaries are already fixed by the roadmap/build plan:
- edge CV on Jetson using DeepStream
- backend services using FastAPI-style service boundaries
- a player UI/control plane using React

Its job is to freeze inter-service contracts so implementation can proceed in parallel without schema drift.

## Relevant components named by source

- Camera: IP camera(s) streaming using RTSP
- CV Pipeline: DeepStream on Jetson consuming stream, performing inference/tracking, and emitting metadata only
- Audience-State Service: subscribes to CV metadata and aggregates/smooths it into audience state
- Decision Engine: evaluates latest audience state plus policy constraints and produces player-facing commands
- Player: maintains a WebSocket connection, applies strict ordering/idempotency rules client-side, and acknowledges applied commands

## Assumptions and tracked TBDs

The source explicitly tracks rather than invents:
- end-to-end latency targets are illustrative defaults unless validated against the roadmap/build plan and real deployments
- scale assumptions such as number of cameras/sites/concurrency are unspecified
- decision-policy semantics beyond “activate creative X for duration Y under constraints” remain intentionally abstracted
- token issuer/JWKS/rotation policy is unspecified even though JWT/bearer validation format is described
- exact MQTT broker implementation is left as a deployment choice so long as it is consistent with MQTT v5.0 semantics

## ICD-1 Camera → CV Pipeline

### Purpose
Deliver a continuous video stream from camera to the edge CV pipeline for inference.

### Actors and transport in source
- Producer: Camera (RTSP server)
- Consumer: DeepStream pipeline (RTSP client)
- Transport: RTSP 2.0 for session control

### Canonical endpoint model
The source defines RTSP URL form as the canonical endpoint, including credential-bearing forms when required.

### Contracted configuration object
The source defines a JSON Schema for camera source configuration with core required fields:
- `schema_version`
- `camera_id`
- `rtsp_url`
- `enabled`

Additional configuration includes:
- `transport_preference`
- `connect_timeout_ms`
- `read_timeout_ms`
- `reconnect.enabled`
- `reconnect.initial_backoff_ms`
- `reconnect.max_backoff_ms`

### Key semantics carried by source
- `camera_id` is a stable identifier used across downstream messages and must be unique within a site/tenant
- `rtsp_url` is authoritative and must be treated as a secret when it embeds credentials
- downstream metadata must include a monotonic `frame_seq` per camera for ordering/gap detection
- timestamps must be UTC RFC 3339

### Failure and recovery posture
The source names these major failure classes:
- authentication failure
- RTSP session negotiation failure
- stream stalls / read timeout
- jitter / packet loss / decoder errors
- timestamp drift

Required recovery behavior includes exponential backoff reconnect and graceful degradation by emitting camera-offline health state downstream.

## ICD-2 CV Pipeline → Audience-State Service

### Purpose
Publish privacy-preserving CV-derived telemetry from DeepStream to the backend for aggregation into audience state.

### Actors and transport in source
- Producers: DeepStream pipeline instances on Jetson
- Consumers: Audience-State subscriber(s)
- Transport: MQTT v5.0 over TCP, with TLS wherever possible

### Why MQTT is selected
The source explicitly ties this to:
- DeepStream support for transforming metadata to JSON via `Gst-nvmsgconv`
- DeepStream support for publishing payloads using `Gst-nvmsgbroker`
- MQTT’s one-to-many pub/sub suitability for telemetry streams

### Normative topic namespace named by source
- `cv/v1/observations/{tenant_id}/{site_id}/{camera_id}`
- `cv/v1/health/{tenant_id}/{site_id}/{pipeline_id}`
- optional `cv/v1/acks/{tenant_id}/{site_id}/{pipeline_id}`

### QoS posture
- observations: QoS 1, duplicates possible
- health: QoS 0 acceptable if loss is tolerable, QoS 1 otherwise

### Authentication / authorization posture
The source requires TLS and one chosen client-identity method such as:
- mTLS with per-device certificates
- username/password with short-lived tokens

Authorization rules are scoped so CV publishers only publish and optionally subscribe within their tenant/site scope.

### CvObservation schema distilled from source
The normative observation schema requires fields including:
- `schema_version`
- `message_type`
- `message_id`
- `produced_at`
- `tenant_id`
- `site_id`
- `camera_id`
- `pipeline_id`
- `frame_seq`
- `window_ms`
- `counts`
- `demographics`
- `quality`
- `privacy`

Important semantic rules carried by source:
- `message_id` is required for deduplication under QoS 1
- `produced_at` is RFC 3339 UTC
- `frame_seq` is monotonic per camera
- `counts` are per-window, not per-identity tracking
- `demographics` are aggregated distributions only and must not contain per-person identifiers
- `privacy.contains_images`, `privacy.contains_frame_urls`, and `privacy.contains_face_embeddings` are hard-false contract flags

### Ordering and idempotency rules
The source explicitly requires:
- deduplication by `message_id`
- handling of out-of-order delivery using `frame_seq`
- application-layer ordering because strict ordering across reconnects is not assumed
- consumer idempotency keyed by tenant/site/camera/message identity

## ICD-3 Audience-State Service → Decision Engine

### Purpose
Provide a stable, versioned audience-state contract for decision evaluation and optional streaming updates.

### Transport and endpoints named by source
- HTTPS using RFC 9110 semantics and modern TLS baseline
- `POST /v1/decision/evaluate`
- `GET /v1/decision/health`

### Auth posture
Bearer-token semantics through the HTTP `Authorization: Bearer <token>` header.

### Contract role
The audience-state interface is intended to be the stabilizing layer between noisy CV observations and rules-first decisioning. It exists so the decision engine acts on smoothed, versioned state rather than raw CV event jitter.

## ICD-4 Decision Engine → Player

### Purpose
Deliver player-facing command streams with low-latency push semantics while preserving ordering and idempotency.

### Transport selection named by source
WebSocket is selected as the low-latency command path.

### Contract expectations
The source positions the player as a strict client of decision commands, requiring:
- ordering enforcement
- idempotent handling
- acknowledgment behavior
- safe command application under reconnects or transient disruption

## Cross-cutting rules distilled from source

### Protocol and data standards
The source anchors contracts to widely used standards such as:
- RTSP 2.0
- MQTT v5.0
- HTTP semantics
- WebSocket
- JSON / JSON Schema
- RFC 3339 timestamps

### Security and privacy requirements
The ICD makes security and privacy part of the contract surface, not an optional downstream implementation note.

### Monitoring, metrics, and logging requirements
The source treats monitoring, metrics, and logging as part of contract completeness, ensuring implementations expose enough evidence to validate conformance and diagnose faults.

### Deployment notes for Docker and Jetson
The source explicitly calls out:
- NVIDIA runtime requirements for Jetson containerized DeepStream deployments
- preference for Jetson-appropriate DeepStream container images
- treating broker credentials and camera credentials as mounted runtime secrets, not baked into images

## Practical implementation use

This ICD is the core contract surface for the first half of the locked service model. It is the primary anti-drift document for:
- camera ingest assumptions
- metadata payload shape
- smoothing input expectations
- decision request semantics
- player command behavior

## Authority and delta note

This extract reflects the active v1.0 ICD. The separate CSI rebaseline delta pack indicates a likely future ICD v1.1 for the single-camera MVP, but that pack is not itself the controlling ICD until formally merged.
