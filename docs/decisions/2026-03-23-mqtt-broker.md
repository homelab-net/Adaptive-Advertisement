# Platform Decision — MQTT Broker

Date: 2026-03-23
Status: approved; active for MVP implementation
Scope: MQTT broker selection for ICD-2 (input-cv → audience-state) transport

---

## Decision summary

> **Eclipse Mosquitto 2.x is the active MVP MQTT broker.**

Mosquitto runs as a sidecar container in the appliance Compose stack, on-device, with no cloud broker dependency.

## Why Mosquitto is selected

- MQTT v5.0 support: Mosquitto 2.0+ implements MQTT v5.0, which is required by ICD-2 for compatibility with DeepStream's `Gst-nvmsgbroker` plugin.
- Minimal resource footprint: Mosquitto is a C-based daemon with negligible CPU and RAM overhead, appropriate for the shared resource budget of a single Jetson Orin Nano appliance.
- Docker/Compose fit: the official `eclipse-mosquitto` image is small, well-maintained, and straightforward to configure with mounted config and password files.
- TLS and authentication: Mosquitto 2.x supports TLS listener configuration and both password-file and certificate-based client authentication, satisfying the ICD-2 security posture.
- DeepStream ecosystem alignment: Mosquitto is the broker used in the majority of DeepStream MQTT reference implementations, reducing integration risk for `Gst-nvmsgbroker` configuration.
- Solo-founder maintainability: Mosquitto configuration is simple, well-documented, and debuggable with standard MQTT tooling (`mosquitto_pub`, `mosquitto_sub`, `mqttui`).

## Alternatives considered

| Broker | Disposition |
|---|---|
| EMQX | Avoid for MVP. Clustering-oriented, Java/Erlang-based, significant resource overhead. Violates "smallest correct foundations" principle for a single-device appliance. |
| HiveMQ Community | Acceptable alternative if Mosquitto proves insufficient. Java-based; resource cost is not warranted for single-device MVP. |
| NanoMQ | Acceptable alternative. Rust-based edge MQTT broker with v5.0 support. Less tooling ecosystem than Mosquitto; would require more integration validation effort. |

## Deployment posture

- Mosquitto runs as a named container in the appliance Docker Compose stack.
- Listens on localhost / intra-container network only. Not exposed to LAN or WAN.
- TLS required for production. Password-file or mTLS client authentication required; anonymous access disabled.
- Credentials mounted as runtime secrets, not baked into the container image.
- Topic namespace follows ICD-2: `cv/v1/observations/{tenant_id}/{site_id}/{camera_id}` and `cv/v1/health/{tenant_id}/{site_id}/{pipeline_id}`.

## What is not locked by this decision

- Mosquitto point release: pin to the latest stable 2.x release at container image build time; document in `docker-compose.yml` or image pinning file.
- ACL rules: per-service topic authorization rules are a configuration item; structure must follow ICD-2 authorization posture (CV publishers publish only within their tenant/site scope).
- QoS per topic: observations use QoS 1; health telemetry may use QoS 0 or 1 per deployment configuration.

## Implications for implementation

- `input-cv` service: configure `Gst-nvmsgbroker` to publish to the local Mosquitto broker using the ICD-2 topic namespace.
- `audience-state` service: subscribe to `cv/v1/observations/#` scoped to tenant/site; implement deduplication by `message_id` and ordering by `frame_seq` per the `cv-observation.schema.json` contract.
- Compose stack: add `mosquitto` service with config and password-file volumes; ensure it starts before `input-cv` and `audience-state`.
- Contract tests: use `mosquitto_pub` / a test MQTT client to publish fixture messages and assert `audience-state` consumer behavior.

## Relationship to other decisions

- JetPack version: independent; see `2026-03-23-jetpack-version.md`.
- ICD-2 contract: `contracts/audience-state/cv-observation.schema.json`.
