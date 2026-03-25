#!/usr/bin/env bash
# seed-content.sh — First-boot content seeding
#
# PURPOSE
# -------
# Writes the minimum set of approved manifest JSON files required for the
# decision-optimizer's default rules to resolve to real manifest IDs on
# first boot.
#
# The default rules file (services/decision-optimizer/rules/default-rules.json)
# references three manifest IDs:
#   manifest-group    — 3+ viewers, group-mode content
#   manifest-default  — 1+ viewers, standard content
#   manifest-attract  — no audience / attract loop
#
# Without seed manifests, the policy engine resolves a manifest ID, the player
# looks it up in ManifestStore, finds nothing, and silently holds the fallback.
# That is not an error, but it means adaptive selection never activates until a
# manifest is uploaded through the dashboard.
#
# These seed manifests use the built-in fallback asset (fallback-builtin.png)
# as their single creative item.  Replace them with real approved manifests
# via the dashboard once the device is running.
#
# USAGE
# -----
#   # Run once before or after first docker compose up:
#   sudo -E ./seed-content.sh
#
#   # Run with custom manifest output directory:
#   MANIFEST_DIR=/opt/adaptive-ad/data/manifests sudo -E ./seed-content.sh
#
#   # Run with custom approved-by identity:
#   APPROVED_BY="provisioning-script" sudo -E ./seed-content.sh
#
# ENVIRONMENT VARIABLES
# ---------------------
#   MANIFEST_DIR     — where manifest JSON files are written (default: /data/manifests)
#   FALLBACK_ASSET   — asset_id used in seed manifests (default: fallback-builtin)
#   APPROVED_BY      — approved_by field value (default: seed-script)
#   FORCE            — set to "1" to overwrite existing seed manifests

set -euo pipefail

MANIFEST_DIR="${MANIFEST_DIR:-/data/manifests}"
FALLBACK_ASSET="${FALLBACK_ASSET:-fallback-builtin}"
APPROVED_BY="${APPROVED_BY:-seed-script}"
FORCE="${FORCE:-0}"

log()  { echo "[seed-content] $*"; }
die()  { echo "[seed-content] ERROR: $*" >&2; exit 1; }

# Require python3 for JSON generation (avoids jq dependency)
command -v python3 &>/dev/null || die "python3 is required"

APPROVED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

log "Seeding manifests to ${MANIFEST_DIR}"
log "Approved-at: ${APPROVED_AT}"
log "Approved-by: ${APPROVED_BY}"
log "Fallback asset: ${FALLBACK_ASSET}"

install -d -m 755 "${MANIFEST_DIR}"

# ---------------------------------------------------------------------------
# validate_manifest <path>
# Inline structural validation against ICD-5 required fields.
# Does not require jsonschema to be installed.
# ---------------------------------------------------------------------------
validate_manifest() {
    local out="$1"
    python3 - "$out" <<'PYEOF'
import json, sys

path = sys.argv[1]
try:
    with open(path) as f:
        m = json.load(f)
except json.JSONDecodeError as e:
    print(f"[seed-content] ERROR: invalid JSON in {path}: {e}", file=sys.stderr)
    sys.exit(1)

# ICD-5 / creative-manifest.schema.json required fields
required_top = ["schema_version", "manifest_id", "approved_at", "approved_by", "items"]
for field in required_top:
    if field not in m:
        print(f"[seed-content] ERROR: missing required field '{field}' in {path}", file=sys.stderr)
        sys.exit(1)

if m["schema_version"] != "1.0.0":
    print(f"[seed-content] ERROR: schema_version must be '1.0.0', got {m['schema_version']!r}", file=sys.stderr)
    sys.exit(1)

if not isinstance(m["items"], list) or len(m["items"]) < 1:
    print(f"[seed-content] ERROR: items must be a non-empty array in {path}", file=sys.stderr)
    sys.exit(1)

required_item = ["item_id", "asset_id", "asset_type", "duration_ms"]
for i, item in enumerate(m["items"]):
    for field in required_item:
        if field not in item:
            print(f"[seed-content] ERROR: items[{i}] missing '{field}' in {path}", file=sys.stderr)
            sys.exit(1)
    if item["asset_type"] not in ("image", "video", "html"):
        print(f"[seed-content] ERROR: items[{i}].asset_type invalid: {item['asset_type']!r}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(item["duration_ms"], int) or item["duration_ms"] < 1000:
        print(f"[seed-content] ERROR: items[{i}].duration_ms must be int >= 1000", file=sys.stderr)
        sys.exit(1)

print(f"[seed-content] Schema OK: {path}")
PYEOF
}

# ---------------------------------------------------------------------------
# write_manifest <manifest_id> <description>
# ---------------------------------------------------------------------------
write_manifest() {
    local manifest_id="$1"
    local description="$2"
    local out="${MANIFEST_DIR}/${manifest_id}.json"

    if [[ -f "${out}" && "${FORCE}" != "1" ]]; then
        log "Exists (skip): ${out}"
        return
    fi

    python3 - <<PYEOF
import json, sys
manifest = {
    "schema_version": "1.0.0",
    "manifest_id": "${manifest_id}",
    "approved_at": "${APPROVED_AT}",
    "approved_by": "${APPROVED_BY}",
    "items": [
        {
            "item_id": "${manifest_id}-item-1",
            "asset_id": "${FALLBACK_ASSET}",
            "asset_type": "image",
            "duration_ms": 10000,
            "loop": False
        }
    ],
    "policy": {
        "min_dwell_ms": 10000,
        "cooldown_ms": 5000,
        "allow_interruption": True
    }
}
with open("${out}", "w") as f:
    json.dump(manifest, f, indent=2)
print("[seed-content] Written: ${out}")
PYEOF
    validate_manifest "${out}"
}

# ---------------------------------------------------------------------------
# Seed the three manifests referenced by default-rules.json
# ---------------------------------------------------------------------------
write_manifest "manifest-attract"  "Attract loop — no audience / low confidence"
write_manifest "manifest-default"  "Default — 1+ viewers with sufficient confidence"
write_manifest "manifest-group"    "Group mode — 3+ viewers, high confidence"

# ---------------------------------------------------------------------------
# Copy fallback asset to asset cache so the player can resolve the asset_id
# ---------------------------------------------------------------------------
ASSET_CACHE="${ASSET_CACHE_DIR:-/data/assets}"
BUILTIN_SRC="${FALLBACK_BUNDLE_PATH:-/app/fallback_bundle}/fallback-builtin.png"
BUILTIN_DEST="${ASSET_CACHE}/${FALLBACK_ASSET}"

install -d -m 755 "${ASSET_CACHE}"

if [[ -f "${BUILTIN_SRC}" ]]; then
    if [[ ! -f "${BUILTIN_DEST}" || "${FORCE}" == "1" ]]; then
        cp "${BUILTIN_SRC}" "${BUILTIN_DEST}"
        log "Copied fallback asset: ${BUILTIN_SRC} → ${BUILTIN_DEST}"
    else
        log "Exists (skip): ${BUILTIN_DEST}"
    fi
else
    log "WARNING: fallback-builtin.png not found at ${BUILTIN_SRC}"
    log "         Run this script inside the player container, or set FALLBACK_BUNDLE_PATH."
    log "         Manifests were written but asset_id '${FALLBACK_ASSET}' will not resolve"
    log "         until the asset file is present at ${BUILTIN_DEST}"
fi

log ""
log "Seed content ready. Manifests written:"
ls -1 "${MANIFEST_DIR}/"*.json 2>/dev/null || log "  (none found — check MANIFEST_DIR)"
log ""
log "Next steps:"
log "  1. Start the application: docker compose up -d"
log "  2. Upload real creative assets via the dashboard."
log "  3. Approve manifests via the dashboard to replace these seed manifests."
log "  4. The player will switch to approved manifests automatically within one decision loop."
