# creative Contract Stubs

This folder contains code-facing contract artifacts for the `creative` service.

## ICD reference

ICD-5: Creative Service ↔ Player (interface-addendum-v1.0.md)

## Current contents

- `creative-manifest.schema.json` — approved creative manifest produced by `creative` and consumed by `player`

## Approved-only rendering rule

The player must never render a manifest that has not been approved. This is a hard project rule inherited from the governance baseline:

- Unapproved manifests must be rejected without blanking playback.
- Cache-miss or invalid-manifest conditions must fall back to the static fallback bundle, not blank the screen.
- The `approved_by` and `approved_at` fields are required and must be validated before rendering.

## Relationship to player commands

`creative-manifest.schema.json` defines the manifest object.
`contracts/player/player-command.schema.json` defines how the decision engine tells the player which manifest to activate (`activate_creative.manifest_id`).

The player receives manifests out-of-band (pre-fetched or pushed) and commands in-band over WebSocket. The `manifest_id` in a player command must resolve to a manifest the player already holds.

## Expected follow-on work

- asset reference and caching contract
- manifest delivery / pre-fetch protocol documentation
- approval workflow documentation (dashboard → creative → player)
- example manifest fixture files
- schema validation tests
- typed manifest model in creative and player code
- cache-miss and invalid-manifest fallback tests
