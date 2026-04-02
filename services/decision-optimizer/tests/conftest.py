"""
Shared fixtures for the decision-optimizer test suite.
"""
import json
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Minimal valid ICD-3 audience-state signal
# ---------------------------------------------------------------------------

def make_signal(
    count: int = 1,
    confidence: float = 0.9,
    freeze_decision: bool = False,
    state_stable: bool = True,
    pipeline_degraded: bool = False,
    message_id: str = "msg-1",
    demographics: dict | None = None,
    demographics_suppressed: bool = True,
    attention: dict | None = None,
) -> dict:
    stability: dict = {
        "state_stable": state_stable,
        "freeze_decision": freeze_decision,
        "demographics_suppressed": demographics_suppressed,
    }
    state: dict = {
        "presence": {"count": count, "confidence": confidence},
        "stability": stability,
    }
    if demographics is not None:
        # Inject suppressed flag so policy.py can read it from the demographics block
        state["demographics"] = {"suppressed": demographics_suppressed, **demographics}
    elif not demographics_suppressed:
        # No explicit demographics dict but suppressed=False: create a minimal block
        # so the policy gate passes and demographic conditions can be evaluated.
        state["demographics"] = {"suppressed": False}

    if attention is not None:
        state["attention"] = attention

    return {
        "schema_version": "1.0.0",
        "message_type": "audience_state_signal",
        "message_id": message_id,
        "produced_at": "2026-01-01T00:00:00Z",
        "tenant_id": "tenant-01",
        "site_id": "site-01",
        "camera_id": "cam-01",
        "state": state,
        "source_quality": {
            "signal_age_ms": 100,
            "pipeline_degraded": pipeline_degraded,
        },
        "privacy": {
            "contains_images": False,
            "contains_frame_urls": False,
            "contains_face_embeddings": False,
        },
    }


@pytest.fixture()
def valid_signal() -> dict:
    return make_signal()


@pytest.fixture()
def rules_file(tmp_path: Path) -> str:
    """Write a minimal rules file to a temp path and return its path."""
    rules = {
        "schema_version": "1.0.0",
        "min_dwell_ms": 5000,
        "cooldown_ms": 2000,
        "rules": [
            {
                "rule_id": "group",
                "priority": 20,
                "manifest_id": "manifest-group",
                "conditions": {"presence_count_gte": 3, "presence_confidence_gte": 0.7},
            },
            {
                "rule_id": "single",
                "priority": 10,
                "manifest_id": "manifest-single",
                "conditions": {"presence_count_gte": 1, "presence_confidence_gte": 0.7},
            },
            {
                "rule_id": "attract",
                "priority": 0,
                "manifest_id": "manifest-attract",
                "conditions": {},
            },
        ],
    }
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(rules))
    return str(path)
