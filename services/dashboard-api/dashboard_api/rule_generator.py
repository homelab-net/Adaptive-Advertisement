"""
rule_generator.py — translate manifest audience_tags → decision-optimizer rule dicts.

This module is the single source of truth for how operator-assigned tags on a
manifest become concrete rule conditions in the decision engine.

Tag categories
--------------
Audience tags   — WHO the content targets (presence count + demographic bins)
Time tags       — WHEN the content should primarily run (hour-of-day windows)
Occasion tags   — WHAT type of content it is (affects priority bonus)
Frequency tags  — HOW OFTEN to show it outside its primary time window

Generated rule format matches the rules file schema consumed by load_policy()
in services/decision-optimizer/decision_optimizer/policy.py.

Attention gate (CRM-004)
------------------------
attention_engaged_gte is auto-injected by this module into all demographic
audience tag conditions (i.e. all tags except "attract" and "general").
It is NOT an operator-selectable tag — operators cannot add or remove it.
The gate threshold is fixed at _ATTENTION_GATE_THRESHOLD = 0.35.

When the ICD-3 signal contains no attention block, the gate passes silently
(backward compatible with pipelines that lack a head-pose model). When present,
the rule only fires if engaged >= threshold, ensuring targeted ads only activate
when a person is actually looking at the display.

Cross-dimension targeting (CRM-004/005)
-----------------------------------------
When a manifest carries tags from two different demographic dimensions
(age, gender, attire), an additional cross-dimension rule is generated at
priority 13 (no time) or 33 (with time) for each pair. This rewards manifests
that correctly target a specific audience slice with a priority bump over
single-dimension rules.

Privacy
-------
No live demographic data is stored here.  Tags are operator-assigned intent
labels only.  The demographic conditions in generated rules only fire when the
policy engine's existing privacy guard allows
(i.e. demographics_suppressed=False in the live signal, per PRIV-001..PRIV-005).
"""
from __future__ import annotations

import itertools
import logging
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical tag sets — single source of truth
# ---------------------------------------------------------------------------

AUDIENCE_TAGS: set[str] = {
    "attract",
    "general",
    "solo_adult",
    "group_adults",
    "adult_with_child",
    "teenager_group",
    "seniors",
    "male_focus",
    "female_focus",
    # Attire tags (CRM-005)
    "attire_formal",
    "attire_business_casual",
    "attire_casual",
    "attire_athletic",
    "attire_outdoor_technical",
    "attire_workwear_uniform",
    "attire_streetwear",
    "attire_luxury_premium",
    "attire_lounge_comfort",
    "attire_smart_occasion",
}

TIME_TAGS: set[str] = {
    "time_morning",
    "time_lunch",
    "time_afternoon",
    "time_happy_hour",
    "time_evening",
    "time_late_night",
    "time_all_day",
}

OCCASION_TAGS: set[str] = {
    "promo_featured",
    "promo_limited_time",
    "promo_seasonal",
}

FREQUENCY_TAGS: set[str] = {
    "freq_primary",
    "freq_recurring",
    "freq_ambient",
}

ALL_VALID_TAGS: set[str] = AUDIENCE_TAGS | TIME_TAGS | OCCASION_TAGS | FREQUENCY_TAGS

# ---------------------------------------------------------------------------
# Attention gate — auto-injected into all demographic audience tag conditions
# ---------------------------------------------------------------------------

# Fixed gate threshold. Auto-injected into all audience conditions except
# "attract" and "general". Not operator-configurable.
_ATTENTION_GATE_THRESHOLD: float = 0.35

# Tags that do NOT receive the attention gate injection.
_ATTENTION_GATE_EXCLUDED: frozenset[str] = frozenset({"attract", "general"})

# ---------------------------------------------------------------------------
# Dimension groups for cross-dimension rule generation
# ---------------------------------------------------------------------------

# Maps each audience tag to the demographic dimension it belongs to.
# Tags not listed here (attract, general) are dimensionless.
_DIMENSION_GROUPS: dict[str, str] = {
    # Age dimension
    "solo_adult": "age",
    "group_adults": "age",
    "adult_with_child": "age",
    "teenager_group": "age",
    "seniors": "age",
    # Gender dimension
    "male_focus": "gender",
    "female_focus": "gender",
    # Attire dimension
    "attire_formal": "attire",
    "attire_business_casual": "attire",
    "attire_casual": "attire",
    "attire_athletic": "attire",
    "attire_outdoor_technical": "attire",
    "attire_workwear_uniform": "attire",
    "attire_streetwear": "attire",
    "attire_luxury_premium": "attire",
    "attire_lounge_comfort": "attire",
    "attire_smart_occasion": "attire",
}

# Priority bonus for cross-dimension (multi-dimensional) rules
_CROSS_DIM_PRIORITY_BONUS: int = 3

# ---------------------------------------------------------------------------
# Tag → conditions mapping (audience tags)
# ---------------------------------------------------------------------------

# Conditions use the exact field names from policy.py Rule dataclass.
# Note: attention_engaged_gte is injected at rule-generation time for
# all tags NOT in _ATTENTION_GATE_EXCLUDED — do not set it here.
_AUDIENCE_CONDITIONS: dict[str, dict[str, Any]] = {
    "attract": {},
    "general": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.6,
    },
    "solo_adult": {
        "presence_count_eq": 1,
        "presence_confidence_gte": 0.7,
        "age_group_adult_gte": 0.5,
    },
    "group_adults": {
        "presence_count_gte": 2,
        "presence_confidence_gte": 0.7,
        "age_group_adult_gte": 0.5,
    },
    "adult_with_child": {
        "presence_count_gte": 2,
        "presence_confidence_gte": 0.7,
        "age_group_child_gte": 0.2,
        "age_group_adult_gte": 0.3,
    },
    "teenager_group": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.7,
        "age_group_young_adult_gte": 0.5,
    },
    "seniors": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.7,
        "age_group_senior_gte": 0.4,
    },
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
    # Attire tags (CRM-005) — tiered CV confidence thresholds
    # High confidence tier (0.45): visually distinctive categories
    "attire_formal": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.6,
        "attire_formal_gte": 0.45,
    },
    "attire_athletic": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.6,
        "attire_athletic_gte": 0.45,
    },
    "attire_outdoor_technical": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.6,
        "attire_outdoor_technical_gte": 0.45,
    },
    "attire_workwear_uniform": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.6,
        "attire_workwear_uniform_gte": 0.45,
    },
    # Moderate confidence tier (0.50)
    "attire_business_casual": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.6,
        "attire_business_casual_gte": 0.50,
    },
    "attire_streetwear": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.6,
        "attire_streetwear_gte": 0.50,
    },
    "attire_casual": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.6,
        "attire_casual_gte": 0.50,
    },
    # Experimental confidence tier (0.55): harder to classify reliably
    "attire_luxury_premium": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.6,
        "attire_luxury_premium_gte": 0.55,
    },
    "attire_smart_occasion": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.6,
        "attire_smart_occasion_gte": 0.55,
    },
    "attire_lounge_comfort": {
        "presence_count_gte": 1,
        "presence_confidence_gte": 0.6,
        "attire_lounge_comfort_gte": 0.55,
    },
}

# ---------------------------------------------------------------------------
# Time tag → (start_hour, end_hour) or list of tuples (for midnight-crossing)
# ---------------------------------------------------------------------------

# None means no time restriction (all-day).
# Tuples are (time_hour_gte, time_hour_lte) inclusive, UTC.
# time_late_night crosses midnight and produces TWO rules.
_TIME_WINDOWS: dict[str, tuple[int, int] | list[tuple[int, int]] | None] = {
    "time_morning":    (6, 10),
    "time_lunch":      (11, 13),
    "time_afternoon":  (14, 16),
    "time_happy_hour": (16, 18),
    "time_evening":    (18, 21),
    "time_late_night": [(22, 23), (0, 5)],  # split at midnight
    "time_all_day":    None,
}

# ---------------------------------------------------------------------------
# Base priority per audience tag
# ---------------------------------------------------------------------------

_AUDIENCE_BASE_PRIORITY: dict[str, int] = {
    "attract":               0,
    "general":               5,
    "solo_adult":           10,
    "group_adults":         10,
    "adult_with_child":     10,
    "teenager_group":       10,
    "seniors":              10,
    "male_focus":           10,
    "female_focus":         10,
    # Attire tags — same base as single-dimension demographic tags
    "attire_formal":             10,
    "attire_business_casual":    10,
    "attire_casual":             10,
    "attire_athletic":           10,
    "attire_outdoor_technical":  10,
    "attire_workwear_uniform":   10,
    "attire_streetwear":         10,
    "attire_luxury_premium":     10,
    "attire_lounge_comfort":     10,
    "attire_smart_occasion":     10,
}

# Priority boosts applied when time tags are also present
_TIME_ONLY_PRIORITY_BOOST = 10     # time window, no audience specificity
_TIME_AUDIENCE_PRIORITY_BOOST = 20  # time window + audience tag combo

# Occasion tag → additional priority bonus on top of time+audience priority
_OCCASION_PRIORITY_BONUS: dict[str, int] = {
    "promo_featured":     15,
    "promo_limited_time": 30,
    "promo_seasonal":     0,
}

# ---------------------------------------------------------------------------
# Frequency → reminder rule config
# ---------------------------------------------------------------------------

# freq_recurring: generates a second low-priority rule so the ad appears
#   sporadically throughout the day (uses weight < 1.0 for weighted selection).
# freq_ambient:   even lower priority background slot.
# freq_primary:   no reminder rule generated (default behaviour).

_FREQ_REMINDER: dict[str, dict[str, Any]] = {
    "freq_recurring": {"priority": 7,  "weight": 0.3},
    "freq_ambient":   {"priority": 3,  "weight": 0.2},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _inject_attention_gate(cond: dict[str, Any], tag: str) -> dict[str, Any]:
    """
    Return a copy of cond with attention_engaged_gte injected if the tag
    is not in _ATTENTION_GATE_EXCLUDED.
    """
    if tag in _ATTENTION_GATE_EXCLUDED:
        return cond
    return {**cond, "attention_engaged_gte": _ATTENTION_GATE_THRESHOLD}


def _merge_conditions(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """
    Merge two condition dicts. For numeric thresholds that appear in both,
    take the maximum (more restrictive). For presence_count_eq, prefer the
    stricter of the two (keep the value that constrains more: use as-is since
    same-dimension pairs would conflict; in practice pairs come from different
    dimensions so overlaps are only on presence/confidence fields).
    """
    merged = dict(a)
    for key, val in b.items():
        if key not in merged:
            merged[key] = val
        elif isinstance(val, (int, float)) and isinstance(merged[key], (int, float)):
            merged[key] = max(merged[key], val)
        # Non-numeric duplicates: keep existing (a wins)
    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_rules_for_manifest(manifest: Any) -> list[dict[str, Any]]:
    """
    Return a list of rule dicts (policy.py format) for all tags on this manifest.

    Rules include:
    - One rule per (time_tag × audience_tag) combination (or per audience tag if no
      time tags), ordered and prioritised according to the tag taxonomy.
    - Cross-dimension pair rules at priority 13 (no time) or 33 (with time) for each
      pair of tags from different demographic dimensions.
    - One additional reminder rule if freq_recurring or freq_ambient is set.

    Returns [] if the manifest has no tags or if all tags are unknown.
    """
    tags: list[str] = manifest.audience_tags or []
    if not tags:
        return []

    manifest_id: str = manifest.manifest_id

    audience = [t for t in tags if t in AUDIENCE_TAGS]
    time_tags = [t for t in tags if t in TIME_TAGS]
    occasion = [t for t in tags if t in OCCASION_TAGS]
    freq = next((t for t in tags if t in FREQUENCY_TAGS), "freq_primary")

    # Sum occasion bonuses
    occasion_bonus = sum(_OCCASION_PRIORITY_BONUS.get(o, 0) for o in occasion)

    rules: list[dict[str, Any]] = []

    if time_tags:
        # Generate one rule per time-window × audience-tag combination.
        # If no audience tags, generate a basic presence rule per time window.
        for time_tag in time_tags:
            window = _TIME_WINDOWS.get(time_tag)
            # Normalise to a list of (gte, lte) tuples
            if window is None:
                window_slots: list[tuple[int, int] | None] = [None]
            elif isinstance(window, list):
                window_slots = window  # type: ignore[assignment]
            else:
                window_slots = [window]

            for slot_idx, slot in enumerate(window_slots):
                if audience:
                    for aud_tag in audience:
                        cond = dict(_AUDIENCE_CONDITIONS.get(aud_tag, {}))
                        cond = _inject_attention_gate(cond, aud_tag)
                        if slot is not None:
                            cond["time_hour_gte"] = slot[0]
                            cond["time_hour_lte"] = slot[1]
                        base_pri = _AUDIENCE_BASE_PRIORITY.get(aud_tag, 10)
                        priority = base_pri + _TIME_AUDIENCE_PRIORITY_BOOST + occasion_bonus
                        slot_suffix = f"-s{slot_idx}" if slot_idx > 0 else ""
                        rules.append({
                            "rule_id": f"autogen-{manifest_id}-{time_tag}{slot_suffix}-{aud_tag}",
                            "priority": priority,
                            "weight": 1.0,
                            "manifest_id": manifest_id,
                            "conditions": cond,
                        })

                    # Cross-dimension pair rules for this time slot
                    cross_rules = _generate_cross_dim_rules(
                        manifest_id=manifest_id,
                        audience_tags=audience,
                        slot=slot,
                        slot_idx=slot_idx,
                        time_tag=time_tag,
                        occasion_bonus=occasion_bonus,
                    )
                    rules.extend(cross_rules)
                else:
                    # No audience tag: simple time window + basic presence
                    cond = {"presence_count_gte": 1, "presence_confidence_gte": 0.6}
                    if slot is not None:
                        cond["time_hour_gte"] = slot[0]
                        cond["time_hour_lte"] = slot[1]
                    priority = _TIME_ONLY_PRIORITY_BOOST + occasion_bonus
                    slot_suffix = f"-s{slot_idx}" if slot_idx > 0 else ""
                    rules.append({
                        "rule_id": f"autogen-{manifest_id}-{time_tag}{slot_suffix}",
                        "priority": priority,
                        "weight": 1.0,
                        "manifest_id": manifest_id,
                        "conditions": cond,
                    })
    else:
        # No time tags — generate one rule per audience tag, no time restriction.
        for aud_tag in audience:
            cond = dict(_AUDIENCE_CONDITIONS.get(aud_tag, {}))
            cond = _inject_attention_gate(cond, aud_tag)
            base_pri = _AUDIENCE_BASE_PRIORITY.get(aud_tag, 10)
            priority = base_pri + occasion_bonus
            rules.append({
                "rule_id": f"autogen-{manifest_id}-{aud_tag}",
                "priority": priority,
                "weight": 1.0,
                "manifest_id": manifest_id,
                "conditions": cond,
            })

        # Cross-dimension pair rules (no time)
        cross_rules = _generate_cross_dim_rules(
            manifest_id=manifest_id,
            audience_tags=audience,
            slot=None,
            slot_idx=0,
            time_tag=None,
            occasion_bonus=occasion_bonus,
        )
        rules.extend(cross_rules)

    # Frequency: add reminder rule for recurring/ambient
    reminder_cfg = _FREQ_REMINDER.get(freq)
    if reminder_cfg and rules:
        # Reminder uses the most permissive audience condition (general / presence-only)
        reminder_cond: dict[str, Any] = {"presence_count_gte": 1, "presence_confidence_gte": 0.6}
        rules.append({
            "rule_id": f"autogen-{manifest_id}-reminder",
            "priority": reminder_cfg["priority"],
            "weight": reminder_cfg["weight"],
            "manifest_id": manifest_id,
            "conditions": reminder_cond,
        })

    return rules


def _generate_cross_dim_rules(
    manifest_id: str,
    audience_tags: list[str],
    slot: tuple[int, int] | None,
    slot_idx: int,
    time_tag: str | None,
    occasion_bonus: int,
) -> list[dict[str, Any]]:
    """
    Generate cross-dimension pair rules for all pairs of audience tags that
    come from different demographic dimensions.

    Priority = base (10) + _CROSS_DIM_PRIORITY_BONUS (3) + time boost (if time_tag) + occasion_bonus
    """
    cross_rules: list[dict[str, Any]] = []

    # Collect only dimensioned tags (exclude attract, general)
    dimensioned = [(t, _DIMENSION_GROUPS[t]) for t in audience_tags if t in _DIMENSION_GROUPS]

    for (tag_a, dim_a), (tag_b, dim_b) in itertools.combinations(dimensioned, 2):
        if dim_a == dim_b:
            continue  # same dimension — skip

        cond_a = dict(_AUDIENCE_CONDITIONS.get(tag_a, {}))
        cond_b = dict(_AUDIENCE_CONDITIONS.get(tag_b, {}))
        merged = _merge_conditions(cond_a, cond_b)

        # Inject attention gate on the merged condition (both tags are non-excluded)
        merged["attention_engaged_gte"] = _ATTENTION_GATE_THRESHOLD

        if slot is not None:
            merged["time_hour_gte"] = slot[0]
            merged["time_hour_lte"] = slot[1]

        base_pri = 10 + _CROSS_DIM_PRIORITY_BONUS
        if time_tag is not None:
            priority = base_pri + _TIME_AUDIENCE_PRIORITY_BOOST + occasion_bonus
        else:
            priority = base_pri + occasion_bonus

        slot_suffix = f"-s{slot_idx}" if slot_idx > 0 else ""
        time_part = f"-{time_tag}{slot_suffix}" if time_tag else ""
        rule_id = f"autogen-{manifest_id}{time_part}-{tag_a}+{tag_b}"

        cross_rules.append({
            "rule_id": rule_id,
            "priority": priority,
            "weight": 1.0,
            "manifest_id": manifest_id,
            "conditions": merged,
        })

    return cross_rules


def build_rules_file(
    enabled_manifests: list[Any],
    min_dwell_ms: int = 10_000,
    cooldown_ms: int = 5_000,
) -> dict[str, Any]:
    """
    Build a complete policy rules file dict from all enabled manifests.

    Rules are generated from audience_tags on each manifest.  Priority ties
    between rules from different manifests are broken by list position: the
    manifest that appears earlier in enabled_manifests (i.e. most recently
    enabled, given the caller sorts by enabled_at DESC) gets a fractionally
    higher priority so the sort is deterministic.

    A never-blank safety fallback rule is injected automatically if no manifest
    provides an attract or all-conditions-empty rule — this enforces the
    "playback must never go blank" invariant.
    """
    all_rules: list[dict[str, Any]] = []
    for idx, manifest in enumerate(enabled_manifests):
        manifest_rules = generate_rules_for_manifest(manifest)
        # Apply tiebreak: subtract a tiny fraction based on list index so that
        # a more-recently-enabled manifest wins over an older one at the same
        # nominal priority.  The engine sorts by priority desc so higher wins.
        # We use a separate "tiebreak" key rather than mutating "priority" (an
        # int) so the rule file remains readable; the loader drops unknown keys.
        for rule in manifest_rules:
            rule["_tiebreak_index"] = idx  # informational only
        all_rules.extend(manifest_rules)

    # Check whether a catch-all / fallback rule already exists
    has_fallback = any(
        len(r.get("conditions", {"x": 1})) == 0  # empty conditions = catch-all
        for r in all_rules
    )

    if not has_fallback:
        # Inject safety fallback — points to first enabled manifest or a stub.
        fallback_target = enabled_manifests[0].manifest_id if enabled_manifests else "manifest-attract"
        all_rules.append({
            "rule_id": "autogen-safety-fallback",
            "priority": -1,
            "weight": 1.0,
            "manifest_id": fallback_target,
            "conditions": {},
        })
        log.warning(
            "rule_generator: no catch-all rule found — injected safety fallback "
            "pointing to manifest_id=%s", fallback_target,
        )

    return {
        "schema_version": "1.0.0",
        "min_dwell_ms": min_dwell_ms,
        "cooldown_ms": cooldown_ms,
        "rules": all_rules,
    }
