"""
Policy engine — rules-first creative selection (MVP).

A policy is a prioritised list of rules. Each rule has conditions over the
audience state signal and nominates a manifest_id. The engine evaluates rules
from highest to lowest priority and returns the first matching manifest_id.

Rules file format (JSON)
------------------------
{
  "schema_version": "1.0.0",
  "min_dwell_ms": 10000,
  "cooldown_ms": 5000,
  "rules": [
    {
      "rule_id": "busy-room",
      "priority": 20,
      "manifest_id": "manifest-busy",
      "conditions": {
        "presence_count_gte": 3,
        "presence_confidence_gte": 0.7
      }
    },
    {
      "rule_id": "attract",
      "priority": 0,
      "manifest_id": "manifest-attract",
      "conditions": {}
    }
  ]
}

Conditions (all optional; absent conditions are not checked)
------------------------------------------------------------
presence_count_gte           int   — presence.count >= value
presence_count_lte           int   — presence.count <= value
presence_count_eq            int   — presence.count == value
presence_confidence_gte      float — presence.confidence >= value
age_group_child_gte          float — demographics.age_group.child >= value
age_group_young_adult_gte    float — demographics.age_group.young_adult >= value
age_group_adult_gte          float — demographics.age_group.adult >= value
age_group_senior_gte         float — demographics.age_group.senior >= value
gender_male_gte              float — demographics.gender.male >= value
gender_female_gte            float — demographics.gender.female >= value
attire_formal_gte            float — demographics.attire.formal >= value
attire_business_casual_gte   float — demographics.attire.business_casual >= value
attire_casual_gte            float — demographics.attire.casual >= value
attire_athletic_gte          float — demographics.attire.athletic >= value
attire_outdoor_technical_gte float — demographics.attire.outdoor_technical >= value
attire_workwear_uniform_gte  float — demographics.attire.workwear_uniform >= value
attire_streetwear_gte        float — demographics.attire.streetwear >= value
attire_luxury_premium_gte    float — demographics.attire.luxury_premium >= value
attire_lounge_comfort_gte    float — demographics.attire.lounge_comfort >= value
attire_smart_occasion_gte    float — demographics.attire.smart_occasion >= value
demographics_suppressed_eq   bool  — state.stability.demographics_suppressed == value
attention_engaged_gte        float — state.attention.engaged >= value
                                     (absent attention block passes silently)
time_hour_gte                int   — UTC hour >= value (0-23)
time_hour_lte                int   — UTC hour <= value (0-23)

Demographic conditions: if demographics_suppressed is True in the signal
and any demographic condition is set, the rule does NOT match (privacy guard).
Attire conditions are subject to the same demographics_suppressed gate.

Attention condition: evaluated independently of demographics_suppressed.
If the signal contains no attention block the gate passes silently (backward
compatible). If the attention block is present and engaged < threshold the
rule does NOT match.

An empty conditions dict {} always matches (catch-all / default rule).
Rules are tried in descending priority order; the first match wins.
If no rule matches, None is returned and the caller should hold current content.
"""
import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

_POLICY_SCHEMA_VERSION = "1.0.0"

_ATTENTION_CONDITION_FIELDS = (
    "attention_engaged_gte",
)

_DEMOGRAPHIC_CONDITION_FIELDS = (
    "age_group_child_gte",
    "age_group_young_adult_gte",
    "age_group_adult_gte",
    "age_group_senior_gte",
    "gender_male_gte",
    "gender_female_gte",
    "attire_formal_gte",
    "attire_business_casual_gte",
    "attire_casual_gte",
    "attire_athletic_gte",
    "attire_outdoor_technical_gte",
    "attire_workwear_uniform_gte",
    "attire_streetwear_gte",
    "attire_luxury_premium_gte",
    "attire_lounge_comfort_gte",
    "attire_smart_occasion_gte",
)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    priority: int
    manifest_id: str
    # Selection weight — used for weighted random selection when multiple rules
    # match at the same priority tier.  Default 1.0 gives equal probability.
    # Values < 1.0 (e.g. 0.3 for reminder rules) make a rule fire less often
    # than equally-prioritised peers when competing at the same priority level.
    weight: float = 1.0
    # Presence conditions
    presence_count_gte: Optional[int] = None
    presence_count_lte: Optional[int] = None
    presence_count_eq: Optional[int] = None
    presence_confidence_gte: Optional[float] = None
    # Demographic conditions (ignored when demographics_suppressed)
    age_group_child_gte: Optional[float] = None
    age_group_young_adult_gte: Optional[float] = None
    age_group_adult_gte: Optional[float] = None
    age_group_senior_gte: Optional[float] = None
    gender_male_gte: Optional[float] = None
    gender_female_gte: Optional[float] = None
    attire_formal_gte: Optional[float] = None
    attire_business_casual_gte: Optional[float] = None
    attire_casual_gte: Optional[float] = None
    attire_athletic_gte: Optional[float] = None
    attire_outdoor_technical_gte: Optional[float] = None
    attire_workwear_uniform_gte: Optional[float] = None
    attire_streetwear_gte: Optional[float] = None
    attire_luxury_premium_gte: Optional[float] = None
    attire_lounge_comfort_gte: Optional[float] = None
    attire_smart_occasion_gte: Optional[float] = None
    demographics_suppressed_eq: Optional[bool] = None
    # Attention condition (behavioral — not gated by demographics_suppressed)
    attention_engaged_gte: Optional[float] = None
    # Time-of-day conditions (UTC hour, inclusive bounds)
    time_hour_gte: Optional[int] = None
    time_hour_lte: Optional[int] = None

    def _has_demographic_condition(self) -> bool:
        return any(
            getattr(self, f) is not None for f in _DEMOGRAPHIC_CONDITION_FIELDS
        )

    def matches(self, signal: dict, now_hour: int = -1) -> bool:
        """
        Return True if all conditions in this rule are satisfied by the signal.
        A rule with no conditions always matches.

        now_hour: UTC hour (0-23).  If -1 (default), derived from datetime.now(utc).
        """
        try:
            count: int = signal["state"]["presence"]["count"]
            confidence: float = signal["state"]["presence"]["confidence"]
        except (KeyError, TypeError):
            log.warning("rule %s: malformed signal — skipping", self.rule_id)
            return False

        # --- Presence conditions ---
        if self.presence_count_gte is not None and count < self.presence_count_gte:
            return False
        if self.presence_count_lte is not None and count > self.presence_count_lte:
            return False
        if self.presence_count_eq is not None and count != self.presence_count_eq:
            return False
        if self.presence_confidence_gte is not None and confidence < self.presence_confidence_gte:
            return False

        # --- Attention condition (behavioral; absent → silent pass) ---
        if self.attention_engaged_gte is not None:
            attn_block = signal.get("state", {}).get("attention")
            if attn_block is not None:
                engaged = attn_block.get("engaged")
                if engaged is not None and float(engaged) < self.attention_engaged_gte:
                    return False

        # --- demographics_suppressed_eq condition ---
        demographics_block: dict = signal.get("state", {}).get("demographics", {}) or {}
        suppressed: bool = bool(demographics_block.get("suppressed", True))
        if self.demographics_suppressed_eq is not None:
            if suppressed != self.demographics_suppressed_eq:
                return False

        # --- Demographic conditions ---
        if self._has_demographic_condition():
            # Privacy guard: if suppressed, demographic conditions cannot be evaluated
            if suppressed:
                return False
            age_group: dict = demographics_block.get("age_group", {})
            if self.age_group_child_gte is not None:
                if float(age_group.get("child", 0.0)) < self.age_group_child_gte:
                    return False
            if self.age_group_young_adult_gte is not None:
                if float(age_group.get("young_adult", 0.0)) < self.age_group_young_adult_gte:
                    return False
            if self.age_group_adult_gte is not None:
                if float(age_group.get("adult", 0.0)) < self.age_group_adult_gte:
                    return False
            if self.age_group_senior_gte is not None:
                if float(age_group.get("senior", 0.0)) < self.age_group_senior_gte:
                    return False

            gender: dict = demographics_block.get("gender", {})
            if self.gender_male_gte is not None:
                if float(gender.get("male", 0.0)) < self.gender_male_gte:
                    return False
            if self.gender_female_gte is not None:
                if float(gender.get("female", 0.0)) < self.gender_female_gte:
                    return False

            attire: dict = demographics_block.get("attire", {})
            if self.attire_formal_gte is not None:
                if float(attire.get("formal", 0.0)) < self.attire_formal_gte:
                    return False
            if self.attire_business_casual_gte is not None:
                if float(attire.get("business_casual", 0.0)) < self.attire_business_casual_gte:
                    return False
            if self.attire_casual_gte is not None:
                if float(attire.get("casual", 0.0)) < self.attire_casual_gte:
                    return False
            if self.attire_athletic_gte is not None:
                if float(attire.get("athletic", 0.0)) < self.attire_athletic_gte:
                    return False
            if self.attire_outdoor_technical_gte is not None:
                if float(attire.get("outdoor_technical", 0.0)) < self.attire_outdoor_technical_gte:
                    return False
            if self.attire_workwear_uniform_gte is not None:
                if float(attire.get("workwear_uniform", 0.0)) < self.attire_workwear_uniform_gte:
                    return False
            if self.attire_streetwear_gte is not None:
                if float(attire.get("streetwear", 0.0)) < self.attire_streetwear_gte:
                    return False
            if self.attire_luxury_premium_gte is not None:
                if float(attire.get("luxury_premium", 0.0)) < self.attire_luxury_premium_gte:
                    return False
            if self.attire_lounge_comfort_gte is not None:
                if float(attire.get("lounge_comfort", 0.0)) < self.attire_lounge_comfort_gte:
                    return False
            if self.attire_smart_occasion_gte is not None:
                if float(attire.get("smart_occasion", 0.0)) < self.attire_smart_occasion_gte:
                    return False

        # --- Time-of-day conditions ---
        if self.time_hour_gte is not None or self.time_hour_lte is not None:
            hour = now_hour if now_hour >= 0 else datetime.now(timezone.utc).hour
            if self.time_hour_gte is not None and hour < self.time_hour_gte:
                return False
            if self.time_hour_lte is not None and hour > self.time_hour_lte:
                return False

        return True


@dataclass
class PolicyConfig:
    rules: list[Rule]           # sorted descending by priority at load time
    min_dwell_ms: int = 10_000
    cooldown_ms: int = 5_000


class PolicyEngine:
    """
    Stateless rule evaluator. Construct once from a PolicyConfig.
    evaluate() can be called on every decision tick without side effects.
    """

    def __init__(
        self,
        config: PolicyConfig,
        _now_fn: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._config = config
        self._now_fn = _now_fn or (lambda: datetime.now(timezone.utc))
        # Pre-sort rules highest priority first (stable sort preserves file order on tie)
        self._rules = sorted(config.rules, key=lambda r: r.priority, reverse=True)
        log.info(
            "policy engine ready: %d rule(s) min_dwell_ms=%d cooldown_ms=%d",
            len(self._rules),
            config.min_dwell_ms,
            config.cooldown_ms,
        )

    @property
    def min_dwell_ms(self) -> int:
        return self._config.min_dwell_ms

    @property
    def cooldown_ms(self) -> int:
        return self._config.cooldown_ms

    def evaluate(self, signal: dict) -> Optional[str]:
        """
        Evaluate the signal against all rules and return the selected manifest_id.

        Selection logic:
        1. Collect all matching rules.
        2. Find the highest priority among them.
        3. Filter to only rules at that top priority (the "tier").
        4. If the tier contains one rule, return it directly (no change in behaviour
           vs. the previous first-match implementation).
        5. If the tier contains multiple rules, perform weighted random selection
           using each rule's weight field.  This enables "sporadic" display:
           a reminder rule with weight=0.3 competing against a weight=1.0 rule
           fires roughly 23% of the time (0.3 / 1.3), giving organic variation
           without requiring a separate scheduling mechanism.

        Returns None if no rule matches — caller should hold current content.
        """
        now_hour = self._now_fn().hour
        matching = [r for r in self._rules if r.matches(signal, now_hour=now_hour)]
        if not matching:
            log.debug("policy: no rule matched — holding current content")
            return None

        top_priority = matching[0].priority  # _rules pre-sorted descending
        top_tier = [r for r in matching if r.priority == top_priority]

        if len(top_tier) == 1:
            chosen = top_tier[0]
        else:
            chosen = random.choices(top_tier, weights=[r.weight for r in top_tier], k=1)[0]

        log.debug(
            "policy match: rule=%s manifest=%s priority=%d weight=%.2f tier_size=%d",
            chosen.rule_id, chosen.manifest_id, chosen.priority, chosen.weight, len(top_tier),
        )
        return chosen.manifest_id


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_policy(rules_file: str) -> PolicyEngine:
    """
    Load a PolicyConfig from a JSON rules file and return a PolicyEngine.
    Raises ValueError if the file is malformed or has an unsupported schema version.
    """
    path = Path(rules_file)
    with open(path) as f:
        data = json.load(f)

    version = data.get("schema_version")
    if version != _POLICY_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported rules file schema_version={version!r}; "
            f"expected {_POLICY_SCHEMA_VERSION!r}"
        )

    raw_rules = data.get("rules", [])
    if not raw_rules:
        raise ValueError("Rules file must contain at least one rule.")

    rules: list[Rule] = []
    for r in raw_rules:
        cond = r.get("conditions", {})
        rules.append(Rule(
            rule_id=r["rule_id"],
            priority=int(r.get("priority", 0)),
            manifest_id=r["manifest_id"],
            weight=float(r.get("weight", 1.0)),
            presence_count_gte=cond.get("presence_count_gte"),
            presence_count_lte=cond.get("presence_count_lte"),
            presence_count_eq=cond.get("presence_count_eq"),
            presence_confidence_gte=cond.get("presence_confidence_gte"),
            age_group_child_gte=cond.get("age_group_child_gte"),
            age_group_young_adult_gte=cond.get("age_group_young_adult_gte"),
            age_group_adult_gte=cond.get("age_group_adult_gte"),
            age_group_senior_gte=cond.get("age_group_senior_gte"),
            gender_male_gte=cond.get("gender_male_gte"),
            gender_female_gte=cond.get("gender_female_gte"),
            attire_formal_gte=cond.get("attire_formal_gte"),
            attire_business_casual_gte=cond.get("attire_business_casual_gte"),
            attire_casual_gte=cond.get("attire_casual_gte"),
            attire_athletic_gte=cond.get("attire_athletic_gte"),
            attire_outdoor_technical_gte=cond.get("attire_outdoor_technical_gte"),
            attire_workwear_uniform_gte=cond.get("attire_workwear_uniform_gte"),
            attire_streetwear_gte=cond.get("attire_streetwear_gte"),
            attire_luxury_premium_gte=cond.get("attire_luxury_premium_gte"),
            attire_lounge_comfort_gte=cond.get("attire_lounge_comfort_gte"),
            attire_smart_occasion_gte=cond.get("attire_smart_occasion_gte"),
            demographics_suppressed_eq=cond.get("demographics_suppressed_eq"),
            attention_engaged_gte=cond.get("attention_engaged_gte"),
            time_hour_gte=cond.get("time_hour_gte"),
            time_hour_lte=cond.get("time_hour_lte"),
        ))

    config = PolicyConfig(
        rules=rules,
        min_dwell_ms=int(data.get("min_dwell_ms", 10_000)),
        cooldown_ms=int(data.get("cooldown_ms", 5_000)),
    )
    log.info("loaded policy from %s: %d rule(s)", path.name, len(rules))
    return PolicyEngine(config)
