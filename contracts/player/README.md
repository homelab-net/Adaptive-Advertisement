# player Contract Stubs

This folder contains code-facing contract artifacts for the `player` service.

## ICD reference

ICD-4: Decision Engine → Player (consolidated-icd-v1.0.md)
ICD-5: Creative Service ↔ Player (interface-addendum-v1.0.md)

Transport: WebSocket (low-latency push from decision-optimizer to player).

## Current contents

- `player-command.schema.json` — MVP command message delivered from `decision-optimizer` to `player`

## Ordering and idempotency rules

- Player must track `sequence_number` and refuse to apply commands with a lower sequence number than the last applied command.
- Player must deduplicate commands by `command_id` — a command seen more than once must be treated as already-applied.
- These rules apply across reconnects.

## Hard appliance rules

- Screen must never go blank. The player must maintain a fallback bundle that renders without any upstream dependency.
- Blank/black screen during normal operation: 0 target, ≤ 250 ms hard cap (PERF-006).
- Player crash recovery: ≤ 10 s to resume playback (REC-002, PERF-001).
- `freeze` and `safe_mode` commands must not cause a blank screen.

## Command types

| `command_type`    | Effect |
|---|---|
| `activate_creative` | Switch to the referenced approved manifest, respecting `min_dwell_ms` and `cooldown_ms` |
| `freeze`            | Hold current creative; stop accepting `activate_creative` until connection restores or freeze is lifted |
| `safe_mode`         | Switch to static fallback bundle; ignore `activate_creative` until `clear_safe_mode` received |
| `clear_safe_mode`   | Resume normal command processing |

## Expected follow-on work

- creative manifest contract (ICD-5): `contracts/creative/creative-manifest.schema.json`
- WebSocket session and reconnect protocol documentation
- player acknowledgment message schema
- example command fixture files
- schema validation tests
- typed command model in player code
- fallback bundle specification
