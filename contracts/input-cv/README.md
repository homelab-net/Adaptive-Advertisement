# input-cv Contract Stubs

This folder contains code-facing contract artifacts for the `input-cv` service.

## Current contents

- `camera-source.schema.json` — MVP CSI/local-device camera source configuration schema

## Usage rule

Codex and other contributors should treat this schema as the starting contract for MVP local-device ingest.

Do not reintroduce RTSP-specific fields into the MVP single-camera config path unless a later formal baseline revision explicitly restores that support.

## Expected follow-on work

- example config file
- schema validation tests
- typed settings model in service code
- startup validation logic
- reopen / recovery behavior tests
