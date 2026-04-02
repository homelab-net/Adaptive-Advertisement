"""
Tests for the rule_generator module.

Covers:
- Tag taxonomy completeness
- Audience tag → conditions mapping (one rule per tag)
- Time tag → conditions mapping (one rule per time window; two for late_night)
- Time × audience combinations and priority arithmetic
- Occasion tag priority bonuses
- Frequency: freq_recurring and freq_ambient add reminder rules
- build_rules_file: fallback injection, tiebreak, schema version
- Edge cases: no tags, unknown tags rejected by schema, duplicate tags
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dashboard_api.rule_generator import (
    generate_rules_for_manifest,
    build_rules_file,
    ALL_VALID_TAGS,
    AUDIENCE_TAGS,
    TIME_TAGS,
    OCCASION_TAGS,
    FREQUENCY_TAGS,
    _AUDIENCE_CONDITIONS,
    _TIME_WINDOWS,
    _AUDIENCE_BASE_PRIORITY,
    _FREQ_REMINDER,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _manifest(manifest_id: str, tags: list[str]) -> SimpleNamespace:
    """Minimal manifest-like object accepted by generate_rules_for_manifest."""
    return SimpleNamespace(manifest_id=manifest_id, audience_tags=tags)


def _rule_by_id(rules: list[dict], rule_id_fragment: str) -> dict:
    """Return first rule whose rule_id contains the given fragment."""
    for r in rules:
        if rule_id_fragment in r["rule_id"]:
            return r
    raise KeyError(f"No rule matching fragment {rule_id_fragment!r} in {[r['rule_id'] for r in rules]}")


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

class TestTaxonomy:
    def test_all_valid_tags_is_union_of_categories(self):
        assert ALL_VALID_TAGS == AUDIENCE_TAGS | TIME_TAGS | OCCASION_TAGS | FREQUENCY_TAGS

    def test_categories_are_disjoint(self):
        assert AUDIENCE_TAGS.isdisjoint(TIME_TAGS)
        assert AUDIENCE_TAGS.isdisjoint(OCCASION_TAGS)
        assert AUDIENCE_TAGS.isdisjoint(FREQUENCY_TAGS)
        assert TIME_TAGS.isdisjoint(OCCASION_TAGS)
        assert TIME_TAGS.isdisjoint(FREQUENCY_TAGS)
        assert OCCASION_TAGS.isdisjoint(FREQUENCY_TAGS)

    def test_all_audience_tags_have_conditions(self):
        for tag in AUDIENCE_TAGS:
            assert tag in _AUDIENCE_CONDITIONS, f"Missing conditions for audience tag: {tag}"

    def test_all_audience_tags_have_base_priority(self):
        for tag in AUDIENCE_TAGS:
            assert tag in _AUDIENCE_BASE_PRIORITY, f"Missing priority for audience tag: {tag}"

    def test_all_time_tags_have_windows(self):
        for tag in TIME_TAGS:
            assert tag in _TIME_WINDOWS, f"Missing time window for time tag: {tag}"

    def test_attract_has_empty_conditions(self):
        assert _AUDIENCE_CONDITIONS["attract"] == {}

    def test_attract_priority_is_zero(self):
        assert _AUDIENCE_BASE_PRIORITY["attract"] == 0

    def test_general_priority_is_five(self):
        assert _AUDIENCE_BASE_PRIORITY["general"] == 5


# ---------------------------------------------------------------------------
# generate_rules_for_manifest — no tags
# ---------------------------------------------------------------------------

class TestNoTags:
    def test_empty_tags_returns_empty_list(self):
        m = _manifest("m1", [])
        assert generate_rules_for_manifest(m) == []

    def test_none_tags_returns_empty_list(self):
        m = SimpleNamespace(manifest_id="m1", audience_tags=None)
        assert generate_rules_for_manifest(m) == []


# ---------------------------------------------------------------------------
# generate_rules_for_manifest — audience tags only (no time)
# ---------------------------------------------------------------------------

class TestAudienceTagsOnly:
    def test_attract_generates_one_rule_empty_conditions(self):
        rules = generate_rules_for_manifest(_manifest("m", ["attract"]))
        assert len(rules) == 1
        assert rules[0]["conditions"] == {}
        assert rules[0]["manifest_id"] == "m"

    def test_general_generates_presence_conditions(self):
        rules = generate_rules_for_manifest(_manifest("m", ["general"]))
        assert len(rules) == 1
        cond = rules[0]["conditions"]
        assert cond["presence_count_gte"] == 1
        assert cond["presence_confidence_gte"] == 0.6

    def test_solo_adult_generates_eq_count_and_demographic(self):
        rules = generate_rules_for_manifest(_manifest("m", ["solo_adult"]))
        assert len(rules) == 1
        cond = rules[0]["conditions"]
        assert cond["presence_count_eq"] == 1
        assert cond["age_group_adult_gte"] == 0.5

    def test_adult_with_child_requires_both_bins(self):
        rules = generate_rules_for_manifest(_manifest("m", ["adult_with_child"]))
        assert len(rules) == 1
        cond = rules[0]["conditions"]
        assert cond["age_group_child_gte"] == 0.2
        assert cond["age_group_adult_gte"] == 0.3
        assert cond["presence_count_gte"] == 2

    def test_teenager_group_uses_young_adult_bin(self):
        rules = generate_rules_for_manifest(_manifest("m", ["teenager_group"]))
        cond = rules[0]["conditions"]
        assert cond["age_group_young_adult_gte"] == 0.5

    def test_seniors_uses_senior_bin(self):
        rules = generate_rules_for_manifest(_manifest("m", ["seniors"]))
        cond = rules[0]["conditions"]
        assert cond["age_group_senior_gte"] == 0.4

    def test_multiple_audience_tags_generate_multiple_rules(self):
        rules = generate_rules_for_manifest(_manifest("m", ["solo_adult", "group_adults"]))
        assert len(rules) == 2

    def test_audience_only_priority_equals_base_priority(self):
        rules = generate_rules_for_manifest(_manifest("m", ["group_adults"]))
        assert rules[0]["priority"] == _AUDIENCE_BASE_PRIORITY["group_adults"]

    def test_rule_id_includes_manifest_id_and_tag(self):
        rules = generate_rules_for_manifest(_manifest("my-manifest", ["seniors"]))
        assert "my-manifest" in rules[0]["rule_id"]
        assert "seniors" in rules[0]["rule_id"]

    def test_default_weight_is_one(self):
        rules = generate_rules_for_manifest(_manifest("m", ["general"]))
        assert rules[0]["weight"] == 1.0


# ---------------------------------------------------------------------------
# generate_rules_for_manifest — time tags
# ---------------------------------------------------------------------------

class TestTimeTags:
    def test_time_happy_hour_sets_hour_bounds(self):
        rules = generate_rules_for_manifest(_manifest("m", ["time_happy_hour"]))
        assert len(rules) == 1
        cond = rules[0]["conditions"]
        assert cond["time_hour_gte"] == 16
        assert cond["time_hour_lte"] == 18

    def test_time_all_day_no_hour_conditions(self):
        rules = generate_rules_for_manifest(_manifest("m", ["time_all_day"]))
        assert len(rules) == 1
        cond = rules[0]["conditions"]
        assert "time_hour_gte" not in cond
        assert "time_hour_lte" not in cond

    def test_time_late_night_generates_two_rules(self):
        """time_late_night crosses midnight — must produce two rules."""
        rules = generate_rules_for_manifest(_manifest("m", ["time_late_night"]))
        assert len(rules) == 2
        hours = {(r["conditions"]["time_hour_gte"], r["conditions"]["time_hour_lte"]) for r in rules}
        assert (22, 23) in hours
        assert (0, 5) in hours

    def test_time_tag_no_audience_gets_basic_presence_condition(self):
        rules = generate_rules_for_manifest(_manifest("m", ["time_morning"]))
        cond = rules[0]["conditions"]
        assert cond["presence_count_gte"] == 1
        assert cond["presence_confidence_gte"] == 0.6
        assert "time_hour_gte" in cond

    def test_time_tag_no_audience_priority_is_time_only_boost(self):
        from dashboard_api.rule_generator import _TIME_ONLY_PRIORITY_BOOST
        rules = generate_rules_for_manifest(_manifest("m", ["time_morning"]))
        assert rules[0]["priority"] == _TIME_ONLY_PRIORITY_BOOST


# ---------------------------------------------------------------------------
# generate_rules_for_manifest — time × audience combos
# ---------------------------------------------------------------------------

class TestTimeAudienceCombinations:
    def test_time_and_audience_combine_into_one_rule(self):
        rules = generate_rules_for_manifest(_manifest("m", ["time_happy_hour", "adult_with_child"]))
        assert len(rules) == 1
        cond = rules[0]["conditions"]
        assert cond["time_hour_gte"] == 16
        assert cond["time_hour_lte"] == 18
        assert cond["age_group_child_gte"] == 0.2

    def test_two_audience_tags_with_time_produce_two_rules(self):
        rules = generate_rules_for_manifest(_manifest("m", ["time_happy_hour", "solo_adult", "group_adults"]))
        assert len(rules) == 2

    def test_time_audience_priority_higher_than_audience_only(self):
        from dashboard_api.rule_generator import _TIME_AUDIENCE_PRIORITY_BOOST
        rules_time_aud = generate_rules_for_manifest(_manifest("m", ["time_morning", "general"]))
        rules_aud_only = generate_rules_for_manifest(_manifest("m", ["general"]))
        assert rules_time_aud[0]["priority"] > rules_aud_only[0]["priority"]
        assert rules_time_aud[0]["priority"] == _AUDIENCE_BASE_PRIORITY["general"] + _TIME_AUDIENCE_PRIORITY_BOOST

    def test_late_night_with_audience_produces_two_rules(self):
        rules = generate_rules_for_manifest(_manifest("m", ["time_late_night", "general"]))
        assert len(rules) == 2
        for r in rules:
            assert r["conditions"]["age_group_senior_gte"] if "age_group_senior_gte" in r["conditions"] else True
            assert "time_hour_gte" in r["conditions"]


# ---------------------------------------------------------------------------
# generate_rules_for_manifest — occasion tags
# ---------------------------------------------------------------------------

class TestOccasionTags:
    def test_promo_featured_adds_priority_bonus(self):
        from dashboard_api.rule_generator import _OCCASION_PRIORITY_BONUS
        base_rules = generate_rules_for_manifest(_manifest("m", ["general"]))
        promo_rules = generate_rules_for_manifest(_manifest("m", ["general", "promo_featured"]))
        diff = promo_rules[0]["priority"] - base_rules[0]["priority"]
        assert diff == _OCCASION_PRIORITY_BONUS["promo_featured"]

    def test_promo_limited_time_higher_bonus_than_featured(self):
        from dashboard_api.rule_generator import _OCCASION_PRIORITY_BONUS
        assert _OCCASION_PRIORITY_BONUS["promo_limited_time"] > _OCCASION_PRIORITY_BONUS["promo_featured"]

    def test_promo_seasonal_no_priority_bonus(self):
        from dashboard_api.rule_generator import _OCCASION_PRIORITY_BONUS
        assert _OCCASION_PRIORITY_BONUS["promo_seasonal"] == 0
        base_rules = generate_rules_for_manifest(_manifest("m", ["general"]))
        seasonal_rules = generate_rules_for_manifest(_manifest("m", ["general", "promo_seasonal"]))
        assert base_rules[0]["priority"] == seasonal_rules[0]["priority"]

    def test_limited_time_with_happy_hour_and_audience_has_highest_priority(self):
        rules = generate_rules_for_manifest(
            _manifest("m", ["time_happy_hour", "adult_with_child", "promo_limited_time"])
        )
        from dashboard_api.rule_generator import _OCCASION_PRIORITY_BONUS, _TIME_AUDIENCE_PRIORITY_BOOST
        expected = (
            _AUDIENCE_BASE_PRIORITY["adult_with_child"]
            + _TIME_AUDIENCE_PRIORITY_BOOST
            + _OCCASION_PRIORITY_BONUS["promo_limited_time"]
        )
        assert rules[0]["priority"] == expected


# ---------------------------------------------------------------------------
# generate_rules_for_manifest — frequency tags
# ---------------------------------------------------------------------------

class TestFrequencyTags:
    def test_freq_primary_no_reminder_rule(self):
        rules = generate_rules_for_manifest(_manifest("m", ["general", "freq_primary"]))
        # freq_primary should NOT add a reminder rule
        reminder_rules = [r for r in rules if "reminder" in r["rule_id"]]
        assert reminder_rules == []

    def test_no_freq_tag_no_reminder_rule(self):
        """Default (no freq tag) behaves like freq_primary — no reminder."""
        rules = generate_rules_for_manifest(_manifest("m", ["general"]))
        reminder_rules = [r for r in rules if "reminder" in r["rule_id"]]
        assert reminder_rules == []

    def test_freq_recurring_adds_reminder_rule(self):
        rules = generate_rules_for_manifest(_manifest("m", ["time_happy_hour", "general", "freq_recurring"]))
        reminder_rules = [r for r in rules if "reminder" in r["rule_id"]]
        assert len(reminder_rules) == 1

    def test_freq_recurring_reminder_priority_is_seven(self):
        rules = generate_rules_for_manifest(_manifest("m", ["time_happy_hour", "freq_recurring"]))
        reminder = next(r for r in rules if "reminder" in r["rule_id"])
        assert reminder["priority"] == _FREQ_REMINDER["freq_recurring"]["priority"]

    def test_freq_recurring_reminder_weight_less_than_one(self):
        rules = generate_rules_for_manifest(_manifest("m", ["time_morning", "freq_recurring"]))
        reminder = next(r for r in rules if "reminder" in r["rule_id"])
        assert reminder["weight"] < 1.0
        assert reminder["weight"] == _FREQ_REMINDER["freq_recurring"]["weight"]

    def test_freq_ambient_adds_reminder_rule_lower_priority(self):
        rules = generate_rules_for_manifest(_manifest("m", ["general", "freq_ambient"]))
        reminder_rules = [r for r in rules if "reminder" in r["rule_id"]]
        assert len(reminder_rules) == 1
        assert reminder_rules[0]["priority"] == _FREQ_REMINDER["freq_ambient"]["priority"]
        assert reminder_rules[0]["weight"] == _FREQ_REMINDER["freq_ambient"]["weight"]

    def test_freq_ambient_priority_below_general(self):
        from dashboard_api.rule_generator import _AUDIENCE_BASE_PRIORITY
        ambient_reminder_priority = _FREQ_REMINDER["freq_ambient"]["priority"]
        assert ambient_reminder_priority < _AUDIENCE_BASE_PRIORITY["general"]

    def test_freq_recurring_reminder_has_presence_condition(self):
        rules = generate_rules_for_manifest(_manifest("m", ["time_evening", "freq_recurring"]))
        reminder = next(r for r in rules if "reminder" in r["rule_id"])
        assert reminder["conditions"]["presence_count_gte"] == 1

    def test_no_reminder_generated_when_no_primary_rules(self):
        """If generate_rules_for_manifest returns [] (no tags), no reminder either."""
        rules = generate_rules_for_manifest(_manifest("m", []))
        assert rules == []


# ---------------------------------------------------------------------------
# build_rules_file
# ---------------------------------------------------------------------------

class TestBuildRulesFile:
    def test_schema_version_is_correct(self):
        m = _manifest("m", ["attract"])
        result = build_rules_file([m])
        assert result["schema_version"] == "1.0.0"

    def test_min_dwell_and_cooldown_propagated(self):
        m = _manifest("m", ["attract"])
        result = build_rules_file([m], min_dwell_ms=15_000, cooldown_ms=3_000)
        assert result["min_dwell_ms"] == 15_000
        assert result["cooldown_ms"] == 3_000

    def test_rules_from_all_enabled_manifests_combined(self):
        m1 = _manifest("m1", ["attract"])
        m2 = _manifest("m2", ["general"])
        result = build_rules_file([m1, m2])
        manifest_ids = {r["manifest_id"] for r in result["rules"]}
        assert "m1" in manifest_ids
        assert "m2" in manifest_ids

    def test_safety_fallback_injected_when_no_attract(self):
        """If no manifest has attract tag (empty conditions), fallback is injected."""
        m = _manifest("m", ["solo_adult"])  # no attract/empty conditions
        result = build_rules_file([m])
        fallback_rules = [r for r in result["rules"] if r.get("conditions") == {}]
        assert len(fallback_rules) >= 1

    def test_no_fallback_injected_when_attract_present(self):
        """Attract tag produces empty conditions — fallback should NOT be duplicated."""
        m = _manifest("m", ["attract"])
        result = build_rules_file([m])
        # The attract rule itself is the catch-all
        empty_rules = [r for r in result["rules"] if r.get("conditions") == {}]
        fallback_rules = [r for r in empty_rules if r["rule_id"] == "autogen-safety-fallback"]
        assert fallback_rules == []

    def test_fallback_points_to_first_enabled_manifest(self):
        m1 = _manifest("first-manifest", ["solo_adult"])
        m2 = _manifest("second-manifest", ["group_adults"])
        result = build_rules_file([m1, m2])
        fallback = next(r for r in result["rules"] if r["rule_id"] == "autogen-safety-fallback")
        assert fallback["manifest_id"] == "first-manifest"

    def test_empty_enabled_list_fallback_stub(self):
        result = build_rules_file([])
        fallback = next(r for r in result["rules"] if r["rule_id"] == "autogen-safety-fallback")
        assert fallback["manifest_id"] == "manifest-attract"

    def test_tiebreak_index_present_on_rules(self):
        m1 = _manifest("m1", ["general"])
        m2 = _manifest("m2", ["general"])
        result = build_rules_file([m1, m2])
        tiebreaks = [r.get("_tiebreak_index") for r in result["rules"] if "_tiebreak_index" in r]
        assert len(tiebreaks) >= 2

    def test_generated_rules_file_loadable_by_policy_engine(self, tmp_path: Path):
        """
        The output of build_rules_file must be valid input to load_policy().
        This is the integration test between rule_generator and policy.py.
        """
        import sys, os
        # Add decision-optimizer to path for import
        optimizer_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "decision-optimizer"
        )
        sys.path.insert(0, os.path.abspath(optimizer_path))
        try:
            from decision_optimizer.policy import load_policy
        except ImportError:
            pytest.skip("decision-optimizer not importable from this test environment")

        m1 = _manifest("manifest-attract", ["attract"])
        m2 = _manifest("manifest-group",   ["group_adults", "time_happy_hour"])
        m3 = _manifest("manifest-promo",   ["adult_with_child", "time_happy_hour", "promo_limited_time", "freq_recurring"])
        rules_dict = build_rules_file([m1, m2, m3])

        rules_file = tmp_path / "generated.json"
        rules_file.write_text(json.dumps(rules_dict))

        eng = load_policy(str(rules_file))
        assert eng is not None
        assert len(eng._rules) > 0


# ---------------------------------------------------------------------------
# Gender audience tags (CRM-003)
# ---------------------------------------------------------------------------

class TestGenderAudienceTags:
    def test_male_focus_in_audience_tags(self):
        assert "male_focus" in AUDIENCE_TAGS

    def test_female_focus_in_audience_tags(self):
        assert "female_focus" in AUDIENCE_TAGS

    def test_male_focus_generates_gender_male_gte_condition(self):
        rules = generate_rules_for_manifest(_manifest("m", ["male_focus"]))
        assert len(rules) == 1
        cond = rules[0]["conditions"]
        assert "gender_male_gte" in cond
        assert cond["gender_male_gte"] == pytest.approx(0.55)
        assert cond["presence_count_gte"] == 1

    def test_female_focus_generates_gender_female_gte_condition(self):
        rules = generate_rules_for_manifest(_manifest("m", ["female_focus"]))
        assert len(rules) == 1
        cond = rules[0]["conditions"]
        assert "gender_female_gte" in cond
        assert cond["gender_female_gte"] == pytest.approx(0.55)
        assert cond["presence_count_gte"] == 1

    def test_gender_tags_have_conditions_entry(self):
        assert "male_focus" in _AUDIENCE_CONDITIONS
        assert "female_focus" in _AUDIENCE_CONDITIONS

    def test_gender_tags_have_base_priority(self):
        assert "male_focus" in _AUDIENCE_BASE_PRIORITY
        assert "female_focus" in _AUDIENCE_BASE_PRIORITY


# ---------------------------------------------------------------------------
# Attention gate auto-injection (CRM-004)
# ---------------------------------------------------------------------------

class TestAttentionGate:
    def test_demographic_tags_get_attention_gate_injected(self):
        """All demographic audience tags (not attract/general) get attention_engaged_gte."""
        from dashboard_api.rule_generator import _ATTENTION_GATE_THRESHOLD, _ATTENTION_GATE_EXCLUDED
        demographic_tags = [
            t for t in AUDIENCE_TAGS if t not in _ATTENTION_GATE_EXCLUDED
        ]
        for tag in demographic_tags:
            rules = generate_rules_for_manifest(_manifest("m", [tag]))
            for r in rules:
                if "reminder" not in r["rule_id"]:
                    assert "attention_engaged_gte" in r["conditions"], \
                        f"attention_engaged_gte not injected for tag {tag!r}"
                    assert r["conditions"]["attention_engaged_gte"] == pytest.approx(_ATTENTION_GATE_THRESHOLD)

    def test_attract_does_not_get_attention_gate(self):
        rules = generate_rules_for_manifest(_manifest("m", ["attract"]))
        assert "attention_engaged_gte" not in rules[0]["conditions"]

    def test_general_does_not_get_attention_gate(self):
        rules = generate_rules_for_manifest(_manifest("m", ["general"]))
        assert "attention_engaged_gte" not in rules[0]["conditions"]

    def test_reminder_rule_does_not_get_attention_gate(self):
        rules = generate_rules_for_manifest(_manifest("m", ["solo_adult", "freq_recurring"]))
        reminder = next(r for r in rules if "reminder" in r["rule_id"])
        assert "attention_engaged_gte" not in reminder["conditions"]

    def test_attention_gate_threshold_value(self):
        from dashboard_api.rule_generator import _ATTENTION_GATE_THRESHOLD
        assert _ATTENTION_GATE_THRESHOLD == pytest.approx(0.35)


# ---------------------------------------------------------------------------
# Attire audience tags (CRM-005)
# ---------------------------------------------------------------------------

class TestAttireTags:
    _ATTIRE_TAGS = [
        "attire_formal", "attire_business_casual", "attire_casual", "attire_athletic",
        "attire_outdoor_technical", "attire_workwear_uniform", "attire_streetwear",
        "attire_luxury_premium", "attire_lounge_comfort", "attire_smart_occasion",
    ]

    def test_all_attire_tags_in_audience_tags(self):
        for tag in self._ATTIRE_TAGS:
            assert tag in AUDIENCE_TAGS, f"{tag} missing from AUDIENCE_TAGS"

    def test_all_attire_tags_have_conditions(self):
        for tag in self._ATTIRE_TAGS:
            assert tag in _AUDIENCE_CONDITIONS, f"{tag} missing from _AUDIENCE_CONDITIONS"

    def test_all_attire_tags_have_base_priority(self):
        for tag in self._ATTIRE_TAGS:
            assert tag in _AUDIENCE_BASE_PRIORITY, f"{tag} missing from _AUDIENCE_BASE_PRIORITY"

    def test_attire_athletic_generates_attire_athletic_gte_condition(self):
        rules = generate_rules_for_manifest(_manifest("m", ["attire_athletic"]))
        assert len(rules) == 1
        cond = rules[0]["conditions"]
        assert "attire_athletic_gte" in cond
        assert cond["attire_athletic_gte"] == pytest.approx(0.45)

    def test_high_confidence_tier_threshold_045(self):
        for tag in ["attire_formal", "attire_athletic", "attire_outdoor_technical", "attire_workwear_uniform"]:
            cond = _AUDIENCE_CONDITIONS[tag]
            field = f"attire_{tag.replace('attire_', '')}_gte"
            assert cond[field] == pytest.approx(0.45), f"Expected 0.45 for {tag}"

    def test_moderate_confidence_tier_threshold_050(self):
        for tag in ["attire_business_casual", "attire_streetwear", "attire_casual"]:
            cond = _AUDIENCE_CONDITIONS[tag]
            field = f"attire_{tag.replace('attire_', '')}_gte"
            assert cond[field] == pytest.approx(0.50), f"Expected 0.50 for {tag}"

    def test_experimental_confidence_tier_threshold_055(self):
        for tag in ["attire_luxury_premium", "attire_smart_occasion", "attire_lounge_comfort"]:
            cond = _AUDIENCE_CONDITIONS[tag]
            field = f"attire_{tag.replace('attire_', '')}_gte"
            assert cond[field] == pytest.approx(0.55), f"Expected 0.55 for {tag}"

    def test_attire_with_time_tag_generates_rule(self):
        rules = generate_rules_for_manifest(_manifest("m", ["time_happy_hour", "attire_athletic"]))
        assert any("attire_athletic" in r["rule_id"] for r in rules)
        rule = next(r for r in rules if "attire_athletic" in r["rule_id"])
        assert rule["conditions"]["time_hour_gte"] == 16
        assert rule["conditions"]["time_hour_lte"] == 18
        assert "attire_athletic_gte" in rule["conditions"]

    def test_attire_tag_gets_attention_gate(self):
        from dashboard_api.rule_generator import _ATTENTION_GATE_THRESHOLD
        rules = generate_rules_for_manifest(_manifest("m", ["attire_formal"]))
        assert len(rules) == 1
        assert rules[0]["conditions"]["attention_engaged_gte"] == pytest.approx(_ATTENTION_GATE_THRESHOLD)


# ---------------------------------------------------------------------------
# Cross-dimension rules (CRM-004/005 joint targeting)
# ---------------------------------------------------------------------------

class TestCrossDimRules:
    def test_no_cross_dim_for_single_tag(self):
        """Single audience tag generates no cross-dim rule."""
        rules = generate_rules_for_manifest(_manifest("m", ["male_focus"]))
        cross_rules = [r for r in rules if "+" in r["rule_id"]]
        assert cross_rules == []

    def test_no_cross_dim_for_same_dimension_tags(self):
        """Two tags in same dimension (both age) generate no cross-dim rule."""
        rules = generate_rules_for_manifest(_manifest("m", ["solo_adult", "group_adults"]))
        cross_rules = [r for r in rules if "+" in r["rule_id"]]
        assert cross_rules == []

    def test_cross_dim_generated_for_age_and_gender(self):
        """One age tag + one gender tag should produce a cross-dim rule."""
        rules = generate_rules_for_manifest(_manifest("m", ["solo_adult", "male_focus"]))
        cross_rules = [r for r in rules if "+" in r["rule_id"]]
        assert len(cross_rules) == 1

    def test_cross_dim_generated_for_age_and_attire(self):
        rules = generate_rules_for_manifest(_manifest("m", ["seniors", "attire_formal"]))
        cross_rules = [r for r in rules if "+" in r["rule_id"]]
        assert len(cross_rules) == 1

    def test_cross_dim_generated_for_gender_and_attire(self):
        rules = generate_rules_for_manifest(_manifest("m", ["female_focus", "attire_athletic"]))
        cross_rules = [r for r in rules if "+" in r["rule_id"]]
        assert len(cross_rules) == 1

    def test_cross_dim_priority_higher_than_single_dim(self):
        from dashboard_api.rule_generator import _CROSS_DIM_PRIORITY_BONUS
        rules = generate_rules_for_manifest(_manifest("m", ["solo_adult", "male_focus"]))
        single_rules = [r for r in rules if "+" not in r["rule_id"]]
        cross_rules = [r for r in rules if "+" in r["rule_id"]]
        assert cross_rules
        cross_priority = cross_rules[0]["priority"]
        max_single_priority = max(r["priority"] for r in single_rules)
        assert cross_priority == max_single_priority + _CROSS_DIM_PRIORITY_BONUS

    def test_cross_dim_merges_conditions(self):
        """Cross-dim rule should have conditions from both constituent tags."""
        rules = generate_rules_for_manifest(_manifest("m", ["male_focus", "attire_athletic"]))
        cross_rules = [r for r in rules if "+" in r["rule_id"]]
        assert len(cross_rules) == 1
        cond = cross_rules[0]["conditions"]
        assert "gender_male_gte" in cond
        assert "attire_athletic_gte" in cond

    def test_cross_dim_has_attention_gate(self):
        from dashboard_api.rule_generator import _ATTENTION_GATE_THRESHOLD
        rules = generate_rules_for_manifest(_manifest("m", ["solo_adult", "attire_formal"]))
        cross_rules = [r for r in rules if "+" in r["rule_id"]]
        assert cross_rules
        assert cross_rules[0]["conditions"]["attention_engaged_gte"] == pytest.approx(_ATTENTION_GATE_THRESHOLD)

    def test_cross_dim_with_time_tag(self):
        rules = generate_rules_for_manifest(_manifest("m", ["time_happy_hour", "male_focus", "attire_athletic"]))
        cross_rules = [r for r in rules if "+" in r["rule_id"]]
        assert len(cross_rules) == 1
        cond = cross_rules[0]["conditions"]
        assert cond["time_hour_gte"] == 16
        assert cond["time_hour_lte"] == 18

    def test_three_cross_dim_tags_generate_three_pairs(self):
        """age + gender + attire: three different-dimension pairs → 3 cross-dim rules."""
        rules = generate_rules_for_manifest(_manifest("m", ["solo_adult", "male_focus", "attire_formal"]))
        cross_rules = [r for r in rules if "+" in r["rule_id"]]
        assert len(cross_rules) == 3
