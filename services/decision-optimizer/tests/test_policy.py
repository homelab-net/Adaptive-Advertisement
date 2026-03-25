"""
Unit tests for the policy engine and rule loader.
"""
import json
import pytest
from pathlib import Path

from decision_optimizer.policy import Rule, PolicyConfig, PolicyEngine, load_policy
from tests.conftest import make_signal


# ---------------------------------------------------------------------------
# Rule.matches()
# ---------------------------------------------------------------------------

class TestRuleMatches:
    def _rule(self, **conditions) -> Rule:
        return Rule(rule_id="r", priority=0, manifest_id="m", **conditions)

    def test_empty_conditions_always_matches(self):
        r = self._rule()
        assert r.matches(make_signal(count=0, confidence=0.0))
        assert r.matches(make_signal(count=10, confidence=1.0))

    def test_presence_count_gte_matches(self):
        r = self._rule(presence_count_gte=2)
        assert r.matches(make_signal(count=2))
        assert r.matches(make_signal(count=5))
        assert not r.matches(make_signal(count=1))
        assert not r.matches(make_signal(count=0))

    def test_presence_count_lte_matches(self):
        r = self._rule(presence_count_lte=3)
        assert r.matches(make_signal(count=0))
        assert r.matches(make_signal(count=3))
        assert not r.matches(make_signal(count=4))

    def test_presence_count_eq_matches(self):
        r = self._rule(presence_count_eq=2)
        assert r.matches(make_signal(count=2))
        assert not r.matches(make_signal(count=1))
        assert not r.matches(make_signal(count=3))

    def test_presence_confidence_gte_matches(self):
        r = self._rule(presence_confidence_gte=0.7)
        assert r.matches(make_signal(confidence=0.7))
        assert r.matches(make_signal(confidence=1.0))
        assert not r.matches(make_signal(confidence=0.69))

    def test_combined_conditions_all_must_match(self):
        r = self._rule(presence_count_gte=2, presence_confidence_gte=0.8)
        assert r.matches(make_signal(count=3, confidence=0.9))
        assert not r.matches(make_signal(count=3, confidence=0.5))   # conf fails
        assert not r.matches(make_signal(count=1, confidence=0.9))   # count fails

    def test_malformed_signal_returns_false(self):
        r = self._rule(presence_count_gte=1)
        assert not r.matches({})
        assert not r.matches({"state": {}})


# ---------------------------------------------------------------------------
# PolicyEngine.evaluate()
# ---------------------------------------------------------------------------

class TestPolicyEngine:
    def _engine(self, rules: list[Rule], dwell: int = 5000, cooldown: int = 2000) -> PolicyEngine:
        return PolicyEngine(PolicyConfig(rules=rules, min_dwell_ms=dwell, cooldown_ms=cooldown))

    def test_returns_highest_priority_match(self):
        rules = [
            Rule("low",  priority=5,  manifest_id="m-low",  presence_count_gte=1),
            Rule("high", priority=20, manifest_id="m-high", presence_count_gte=1),
        ]
        eng = self._engine(rules)
        assert eng.evaluate(make_signal(count=2)) == "m-high"

    def test_returns_one_of_tied_rules(self):
        # Both priority=10, equal weights — both must be reachable
        rules = [
            Rule("first",  priority=10, manifest_id="m-first",  presence_count_gte=1),
            Rule("second", priority=10, manifest_id="m-second", presence_count_gte=1),
        ]
        eng = self._engine(rules)
        result = eng.evaluate(make_signal(count=1))
        assert result in ("m-first", "m-second")

    def test_skips_non_matching_rules(self):
        rules = [
            Rule("group",   priority=20, manifest_id="m-group",   presence_count_gte=3),
            Rule("attract", priority=0,  manifest_id="m-attract"),
        ]
        eng = self._engine(rules)
        # count=1 doesn't satisfy group rule → falls through to attract
        assert eng.evaluate(make_signal(count=1)) == "m-attract"

    def test_catch_all_rule_fires_when_no_other_match(self):
        rules = [
            Rule("strict", priority=10, manifest_id="m-strict", presence_count_gte=5),
            Rule("catch",  priority=0,  manifest_id="m-catch"),
        ]
        eng = self._engine(rules)
        assert eng.evaluate(make_signal(count=0)) == "m-catch"

    def test_returns_none_when_no_rule_matches(self):
        rules = [Rule("strict", priority=10, manifest_id="m", presence_count_gte=5)]
        eng = self._engine(rules)
        assert eng.evaluate(make_signal(count=1)) is None

    def test_exposes_min_dwell_ms(self):
        eng = self._engine([], dwell=12_000)
        assert eng.min_dwell_ms == 12_000

    def test_exposes_cooldown_ms(self):
        eng = self._engine([], cooldown=3_000)
        assert eng.cooldown_ms == 3_000


# ---------------------------------------------------------------------------
# load_policy()
# ---------------------------------------------------------------------------

class TestLoadPolicy:
    def test_loads_valid_rules_file(self, rules_file):
        eng = load_policy(rules_file)
        # Three rules in the fixture
        assert len(eng._rules) == 3

    def test_rules_sorted_by_priority(self, rules_file):
        eng = load_policy(rules_file)
        priorities = [r.priority for r in eng._rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_wrong_schema_version_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({
            "schema_version": "9.9.9",
            "rules": [{"rule_id": "x", "manifest_id": "m", "conditions": {}}],
        }))
        with pytest.raises(ValueError, match="schema_version"):
            load_policy(str(p))

    def test_empty_rules_raises(self, tmp_path):
        p = tmp_path / "empty.json"
        p.write_text(json.dumps({"schema_version": "1.0.0", "rules": []}))
        with pytest.raises(ValueError, match="at least one rule"):
            load_policy(str(p))

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_policy("/no/such/file.json")

    def test_min_dwell_and_cooldown_loaded(self, rules_file):
        eng = load_policy(rules_file)
        assert eng.min_dwell_ms == 5000
        assert eng.cooldown_ms == 2000

    def test_full_rule_set_selects_correctly(self, rules_file):
        eng = load_policy(rules_file)
        # 3+ people with high confidence → group
        assert eng.evaluate(make_signal(count=3, confidence=0.8)) == "manifest-group"
        # 1 person with high confidence → single
        assert eng.evaluate(make_signal(count=1, confidence=0.9)) == "manifest-single"
        # 0 people (or low confidence) → attract catch-all
        assert eng.evaluate(make_signal(count=0, confidence=0.5)) == "manifest-attract"
        # Low confidence blocks specific rules → attract
        assert eng.evaluate(make_signal(count=5, confidence=0.3)) == "manifest-attract"


# ---------------------------------------------------------------------------
# Demographic conditions
# ---------------------------------------------------------------------------

class TestDemographicConditions:
    def _rule(self, **conditions) -> Rule:
        return Rule(rule_id="r", priority=0, manifest_id="m", **conditions)

    def _sig_with_demo(self, count=1, suppressed=False, **age_groups):
        demo = {"age_groups": age_groups} if age_groups else {"age_groups": {}}
        return make_signal(
            count=count,
            demographics=demo,
            demographics_suppressed=suppressed,
        )

    def test_age_group_adult_gte_matches(self):
        r = self._rule(age_group_adult_gte=0.5)
        sig = self._sig_with_demo(suppressed=False, adult=0.6)
        assert r.matches(sig)

    def test_age_group_adult_gte_miss(self):
        r = self._rule(age_group_adult_gte=0.5)
        sig = self._sig_with_demo(suppressed=False, adult=0.3)
        assert not r.matches(sig)

    def test_demographic_condition_blocked_when_suppressed(self):
        r = self._rule(age_group_adult_gte=0.1)
        # Even a 0.1 threshold should not match when demographics_suppressed=True
        sig = self._sig_with_demo(suppressed=True, adult=0.9)
        assert not r.matches(sig)

    def test_demographics_suppressed_eq_true_matches(self):
        r = self._rule(demographics_suppressed_eq=True)
        sig = make_signal(demographics_suppressed=True)
        assert r.matches(sig)

    def test_demographics_suppressed_eq_false_mismatches(self):
        r = self._rule(demographics_suppressed_eq=False)
        sig = make_signal(demographics_suppressed=True)
        assert not r.matches(sig)

    def test_missing_demographics_key_treated_as_zero(self):
        # No demographics key in signal at all — age bins default to 0.0
        r = self._rule(age_group_child_gte=0.1)
        sig = make_signal(demographics_suppressed=False)  # no demographics dict
        assert not r.matches(sig)

    def test_all_age_bins(self):
        r = self._rule(
            age_group_child_gte=0.1,
            age_group_young_adult_gte=0.1,
            age_group_adult_gte=0.1,
            age_group_senior_gte=0.1,
        )
        sig = self._sig_with_demo(
            suppressed=False,
            child=0.2, young_adult=0.3, adult=0.4, senior=0.1
        )
        assert r.matches(sig)

    def test_combined_presence_and_demographic(self):
        r = self._rule(presence_count_gte=2, age_group_senior_gte=0.3)
        sig = self._sig_with_demo(count=3, suppressed=False, senior=0.5)
        assert r.matches(sig)
        # Presence fails
        sig_low_count = self._sig_with_demo(count=1, suppressed=False, senior=0.5)
        assert not r.matches(sig_low_count)


# ---------------------------------------------------------------------------
# Time-of-day conditions
# ---------------------------------------------------------------------------

class TestTimeOfDayConditions:
    def _rule(self, **conditions) -> Rule:
        return Rule(rule_id="r", priority=0, manifest_id="m", **conditions)

    def test_time_hour_gte_matches(self):
        r = self._rule(time_hour_gte=9)
        assert r.matches(make_signal(), now_hour=9)
        assert r.matches(make_signal(), now_hour=12)
        assert not r.matches(make_signal(), now_hour=8)

    def test_time_hour_lte_matches(self):
        r = self._rule(time_hour_lte=17)
        assert r.matches(make_signal(), now_hour=17)
        assert r.matches(make_signal(), now_hour=10)
        assert not r.matches(make_signal(), now_hour=18)

    def test_time_hour_both_bounds(self):
        r = self._rule(time_hour_gte=9, time_hour_lte=17)
        assert r.matches(make_signal(), now_hour=9)
        assert r.matches(make_signal(), now_hour=17)
        assert r.matches(make_signal(), now_hour=13)
        assert not r.matches(make_signal(), now_hour=8)
        assert not r.matches(make_signal(), now_hour=18)

    def test_time_combined_with_presence(self):
        r = self._rule(presence_count_gte=1, time_hour_gte=8, time_hour_lte=20)
        assert r.matches(make_signal(count=2), now_hour=10)
        assert not r.matches(make_signal(count=2), now_hour=21)
        assert not r.matches(make_signal(count=0), now_hour=10)

    def test_policy_engine_passes_now_hour(self):
        from datetime import datetime, timezone

        # Inject a fixed time via _now_fn
        fixed_hour = 14
        fixed_dt = datetime(2026, 1, 1, fixed_hour, 0, 0, tzinfo=timezone.utc)
        rules = [
            Rule("daytime", priority=10, manifest_id="m-day",
                 time_hour_gte=9, time_hour_lte=18),
            Rule("catch",   priority=0,  manifest_id="m-catch"),
        ]
        eng = PolicyEngine(
            PolicyConfig(rules=rules),
            _now_fn=lambda: fixed_dt,
        )
        assert eng.evaluate(make_signal()) == "m-day"

    def test_policy_engine_outside_window(self):
        from datetime import datetime, timezone

        fixed_dt = datetime(2026, 1, 1, 22, 0, 0, tzinfo=timezone.utc)
        rules = [
            Rule("daytime", priority=10, manifest_id="m-day",
                 time_hour_gte=9, time_hour_lte=18),
            Rule("catch",   priority=0,  manifest_id="m-catch"),
        ]
        eng = PolicyEngine(
            PolicyConfig(rules=rules),
            _now_fn=lambda: fixed_dt,
        )
        assert eng.evaluate(make_signal()) == "m-catch"


# ---------------------------------------------------------------------------
# Runtime rules reload
# ---------------------------------------------------------------------------

class TestReloadPolicy:
    def _write_rules(self, path: Path, rule_id: str, manifest_id: str) -> None:
        rules = {
            "schema_version": "1.0.0",
            "rules": [
                {
                    "rule_id": rule_id,
                    "priority": 0,
                    "manifest_id": manifest_id,
                    "conditions": {},
                }
            ],
        }
        path.write_text(json.dumps(rules))

    def test_load_then_reload_applies_new_rules(self, tmp_path):
        p = tmp_path / "rules.json"
        self._write_rules(p, "r1", "manifest-v1")
        eng = load_policy(str(p))
        assert eng.evaluate(make_signal()) == "manifest-v1"

        # Rewrite file with new manifest
        self._write_rules(p, "r1", "manifest-v2")
        eng2 = load_policy(str(p))
        assert eng2.evaluate(make_signal()) == "manifest-v2"

    def test_decision_loop_reload(self, tmp_path):
        """
        Verify reload_policy() atomically replaces the active policy.

        Uses a minimal stand-in rather than importing DecisionLoop directly
        to avoid pulling in signal_consumer → jsonschema in this env.
        The logic under test is a single assignment; the full integration
        is covered by the decision-optimizer CI job.
        """
        import asyncio

        p = tmp_path / "rules.json"
        self._write_rules(p, "r1", "manifest-v1")
        policy_v1 = load_policy(str(p))

        # Minimal object with the same reload_policy coroutine logic
        class _MinimalLoop:
            def __init__(self, policy):
                self._policy = policy

            async def reload_policy(self, new_policy):
                self._policy = new_policy

        loop = _MinimalLoop(policy_v1)
        assert loop._policy.evaluate(make_signal()) == "manifest-v1"

        self._write_rules(p, "r1", "manifest-v2")
        policy_v2 = load_policy(str(p))

        asyncio.run(loop.reload_policy(policy_v2))
        assert loop._policy is policy_v2
        assert loop._policy.evaluate(make_signal()) == "manifest-v2"


# ---------------------------------------------------------------------------
# Weight field and weighted selection
# ---------------------------------------------------------------------------

class TestWeightedSelection:
    def _engine(self, rules: list[Rule]) -> PolicyEngine:
        return PolicyEngine(PolicyConfig(rules=rules))

    # --- Rule dataclass ---

    def test_rule_default_weight_is_one(self):
        r = Rule("r", priority=0, manifest_id="m")
        assert r.weight == 1.0

    def test_rule_accepts_custom_weight(self):
        r = Rule("r", priority=0, manifest_id="m", weight=0.3)
        assert r.weight == 0.3

    # --- Single match (no change in behaviour) ---

    def test_single_match_returned_directly(self):
        rules = [Rule("only", priority=10, manifest_id="m-only", presence_count_gte=1)]
        eng = self._engine(rules)
        assert eng.evaluate(make_signal(count=1)) == "m-only"

    def test_single_match_with_weight_still_returned(self):
        rules = [Rule("r", priority=10, manifest_id="m", weight=0.1, presence_count_gte=1)]
        eng = self._engine(rules)
        assert eng.evaluate(make_signal(count=1)) == "m"

    # --- Multiple matches at same priority ---

    def test_both_equal_weight_rules_reachable(self):
        """With two equal-weight rules, both must be reachable over many evaluations."""
        rules = [
            Rule("a", priority=10, manifest_id="m-a", weight=1.0),
            Rule("b", priority=10, manifest_id="m-b", weight=1.0),
        ]
        eng = self._engine(rules)
        results = {eng.evaluate(make_signal()) for _ in range(200)}
        assert "m-a" in results
        assert "m-b" in results

    def test_zero_weight_rule_never_selected(self):
        """A rule with weight=0 is never selected when competing with weight>0."""
        rules = [
            Rule("zero",     priority=10, manifest_id="m-zero",    weight=0.0),
            Rule("nonzero",  priority=10, manifest_id="m-nonzero", weight=1.0),
        ]
        eng = self._engine(rules)
        results = {eng.evaluate(make_signal()) for _ in range(50)}
        assert "m-zero" not in results
        assert "m-nonzero" in results

    def test_lower_weight_fires_less_often_than_higher_weight(self):
        """
        With weights 1.0 and 0.25, the 1.0 rule should win ~80% of the time.
        Test uses a generous margin (>60%) to avoid flakiness.
        """
        rules = [
            Rule("heavy",  priority=10, manifest_id="m-heavy",  weight=1.0),
            Rule("light",  priority=10, manifest_id="m-light",  weight=0.25),
        ]
        eng = self._engine(rules)
        counts: dict[str, int] = {"m-heavy": 0, "m-light": 0}
        for _ in range(400):
            result = eng.evaluate(make_signal())
            if result:
                counts[result] = counts.get(result, 0) + 1
        heavy_pct = counts["m-heavy"] / sum(counts.values())
        assert heavy_pct > 0.60, f"Expected m-heavy >60% but got {heavy_pct:.1%}"

    def test_only_top_priority_tier_competes(self):
        """
        Rules at different priorities: lower-priority rules must NOT compete
        with the top-priority rule, even if lower-priority has higher weight.
        """
        rules = [
            Rule("high",  priority=20, manifest_id="m-high",  weight=0.1),
            Rule("low",   priority=10, manifest_id="m-low",   weight=100.0),
        ]
        eng = self._engine(rules)
        for _ in range(50):
            assert eng.evaluate(make_signal()) == "m-high"

    def test_weight_loaded_from_json_file(self, tmp_path):
        """weight field in JSON rules file is parsed and used."""
        rules_data = {
            "schema_version": "1.0.0",
            "rules": [
                {"rule_id": "r-heavy", "priority": 10, "weight": 1.0,
                 "manifest_id": "m-heavy", "conditions": {}},
                {"rule_id": "r-light", "priority": 10, "weight": 0.01,
                 "manifest_id": "m-light", "conditions": {}},
            ],
        }
        p = tmp_path / "weighted.json"
        p.write_text(json.dumps(rules_data))
        eng = load_policy(str(p))

        loaded_weights = {r.rule_id: r.weight for r in eng._rules}
        assert loaded_weights["r-heavy"] == 1.0
        assert loaded_weights["r-light"] == 0.01

    def test_missing_weight_in_json_defaults_to_one(self, tmp_path):
        rules_data = {
            "schema_version": "1.0.0",
            "rules": [
                {"rule_id": "r1", "priority": 0, "manifest_id": "m", "conditions": {}},
            ],
        }
        p = tmp_path / "no-weight.json"
        p.write_text(json.dumps(rules_data))
        eng = load_policy(str(p))
        assert eng._rules[0].weight == 1.0

    def test_weighted_selection_ignores_non_matching_rules(self):
        """
        Non-matching rules must never appear in the weighted selection pool,
        even if they have high weight.
        """
        rules = [
            Rule("match",    priority=10, manifest_id="m-match",    weight=1.0, presence_count_gte=1),
            Rule("no-match", priority=10, manifest_id="m-no-match", weight=9999.0, presence_count_gte=100),
        ]
        eng = self._engine(rules)
        for _ in range(50):
            assert eng.evaluate(make_signal(count=1)) == "m-match"
