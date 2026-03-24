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
presence_count_gte       int   — presence.count >= value
presence_count_lte       int   — presence.count <= value
presence_count_eq        int   — presence.count == value
presence_confidence_gte  float — presence.confidence >= value

An empty conditions dict {} always matches (catch-all / default rule).
Rules are tried in descending priority order; the first match wins.
If no rule matches, None is returned and the caller should hold current content.

Design note: demographic conditions are out of scope for the MVP scaffold.
They can be added here without touching any other module.
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_POLICY_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    priority: int
    manifest_id: str
    # Parsed condition values (None = condition not set)
    presence_count_gte: Optional[int] = None
    presence_count_lte: Optional[int] = None
    presence_count_eq: Optional[int] = None
    presence_confidence_gte: Optional[float] = None

    def matches(self, signal: dict) -> bool:
        """
        Return True if all conditions in this rule are satisfied by the signal.
        A rule with no conditions always matches.
        """
        try:
            count: int = signal["state"]["presence"]["count"]
            confidence: float = signal["state"]["presence"]["confidence"]
        except (KeyError, TypeError):
            log.warning("rule %s: malformed signal — skipping", self.rule_id)
            return False

        if self.presence_count_gte is not None and count < self.presence_count_gte:
            return False
        if self.presence_count_lte is not None and count > self.presence_count_lte:
            return False
        if self.presence_count_eq is not None and count != self.presence_count_eq:
            return False
        if self.presence_confidence_gte is not None and confidence < self.presence_confidence_gte:
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

    def __init__(self, config: PolicyConfig) -> None:
        self._config = config
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
        Evaluate the signal against all rules.
        Returns the manifest_id of the first matching rule, or None if no rule matches.
        None means the caller should hold current content.
        """
        for rule in self._rules:
            if rule.matches(signal):
                log.debug(
                    "policy match: rule=%s manifest=%s", rule.rule_id, rule.manifest_id
                )
                return rule.manifest_id
        log.debug("policy: no rule matched — holding current content")
        return None


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
            presence_count_gte=cond.get("presence_count_gte"),
            presence_count_lte=cond.get("presence_count_lte"),
            presence_count_eq=cond.get("presence_count_eq"),
            presence_confidence_gte=cond.get("presence_confidence_gte"),
        ))

    config = PolicyConfig(
        rules=rules,
        min_dwell_ms=int(data.get("min_dwell_ms", 10_000)),
        cooldown_ms=int(data.get("cooldown_ms", 5_000)),
    )
    log.info("loaded policy from %s: %d rule(s)", path.name, len(rules))
    return PolicyEngine(config)
