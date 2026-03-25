"""
Privacy audit integration tests — ICD-2 → ICD-3 pipeline.

These tests satisfy the V&V plan's "privacy storage audit" and "privacy egress
audit" requirements at the integration level. They exercise the full chain:

  input-cv observation bytes  (ICD-2)
        │  ObservationConsumer.process()  (schema validation + privacy gating)
        ▼
  ObservationWindow  (smoothing)
        │  SignalPublisher.build_signal()  (ICD-3 construction + self-validation)
        ▼
  audience-state-signal bytes  (ICD-3)

All components run in-process. No MQTT broker, no hardware.

Invariants verified
-------------------
1. Privacy flags (contains_images, contains_frame_urls, contains_face_embeddings)
   are False in every ICD-3 signal that comes out of the pipeline.
2. The serialized ICD-3 bytes contain no banned key strings from
   input_cv.observation.models.BANNED_METADATA_KEYS.
3. ICD-2 observations with any privacy flag set to True are rejected by
   ObservationConsumer before they can reach the window.
4. The ICD-3 signal passes outbound schema validation
   (audience-state-signal.schema.json).
5. A pipeline that has only received ICD-2 privacy-violations emits no
   ICD-3 signal (window stays empty, build_signal returns None).
6. Demographics from ICD-2 observations are averaged into ICD-3 without
   leaking per-person identifiers or banned keys.
"""
from __future__ import annotations

import json
import re

import pytest

# audience-state
from audience_state.observation_store import ObservationWindow
from audience_state.observation_consumer import ObservationConsumer
from audience_state.signal_publisher import SignalPublisher


# ---------------------------------------------------------------------------
# Shared banned-key list (imported from input-cv; also the egress audit target)
# ---------------------------------------------------------------------------

# Import separately so this test has no hard dependency on input-cv running
try:
    from input_cv.observation.models import BANNED_METADATA_KEYS
except ImportError:
    # Fallback: define the same set manually — must stay in sync with models.py
    BANNED_METADATA_KEYS: frozenset[str] = frozenset({
        "frame", "image", "pixels", "pixel", "base64", "embedding", "embeddings",
        "face", "faces", "raw", "blob", "jpeg", "png", "thumbnail", "snapshot",
        "frame_url", "video", "clip",
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_window() -> ObservationWindow:
    return ObservationWindow(
        window_ms=5000,
        min_stability_observations=3,
        confidence_freeze_threshold=0.5,
    )


def _make_consumer(window: ObservationWindow) -> ObservationConsumer:
    return ObservationConsumer(window)


def _make_observation(
    count: int = 2,
    confidence: float = 0.9,
    message_id: str = "obs-1",
    pipeline_degraded: bool = False,
) -> dict:
    return {
        "schema_version": "1.0.0",
        "message_type": "cv_observation",
        "message_id": message_id,
        "produced_at": "2026-03-24T10:00:00Z",
        "tenant_id": "tenant-01",
        "site_id": "site-01",
        "camera_id": "cam-01",
        "pipeline_id": "pipeline-01",
        "frame_seq": 1,
        "window_ms": 500,
        "counts": {"present": count, "confidence": confidence},
        "quality": {
            "frames_processed": 15,
            "frames_dropped": 0,
            "pipeline_degraded": pipeline_degraded,
        },
        "privacy": {
            "contains_images": False,
            "contains_frame_urls": False,
            "contains_face_embeddings": False,
        },
    }


def _raw(obs: dict) -> bytes:
    return json.dumps(obs).encode()


def _build_pipeline_with_n_obs(n: int = 5) -> tuple[SignalPublisher, ObservationWindow]:
    """Feed n valid observations into a window and return (publisher, window)."""
    window = _make_window()
    consumer = _make_consumer(window)
    for i in range(n):
        obs = _make_observation(message_id=f"obs-{i}", count=i % 3 + 1)
        assert consumer.process(_raw(obs)) is True, f"obs-{i} should be accepted"
    return SignalPublisher(), window


def _has_banned_key_in_bytes(payload_bytes: bytes) -> list[str]:
    """
    Return a list of any banned key strings found inside the payload bytes.

    Checks both as exact JSON keys ('"key":') and as bare word boundaries to
    catch any accidental embedding in string values.
    """
    text = payload_bytes.decode("utf-8")
    found = []
    for key in BANNED_METADATA_KEYS:
        # Check as a JSON object key
        if f'"{key}"' in text:
            found.append(key)
        # Check as a standalone word (catches embedded values like base64 data)
        if re.search(rf"\b{re.escape(key)}\b", text):
            found.append(key)
    return list(set(found))


# ---------------------------------------------------------------------------
# Privacy flag enforcement (ICD-2 input gate)
# ---------------------------------------------------------------------------

class TestIcd2PrivacyGate:
    """ObservationConsumer must reject any observation with a True privacy flag."""

    def test_contains_images_true_rejected(self):
        window = _make_window()
        consumer = _make_consumer(window)
        bad = _make_observation()
        bad["privacy"]["contains_images"] = True
        assert consumer.process(_raw(bad)) is False
        assert window.observation_count() == 0

    def test_contains_frame_urls_true_rejected(self):
        window = _make_window()
        consumer = _make_consumer(window)
        bad = _make_observation()
        bad["privacy"]["contains_frame_urls"] = True
        assert consumer.process(_raw(bad)) is False
        assert window.observation_count() == 0

    def test_contains_face_embeddings_true_rejected(self):
        window = _make_window()
        consumer = _make_consumer(window)
        bad = _make_observation()
        bad["privacy"]["contains_face_embeddings"] = True
        assert consumer.process(_raw(bad)) is False
        assert window.observation_count() == 0

    def test_all_three_true_rejected(self):
        window = _make_window()
        consumer = _make_consumer(window)
        bad = _make_observation()
        bad["privacy"]["contains_images"] = True
        bad["privacy"]["contains_frame_urls"] = True
        bad["privacy"]["contains_face_embeddings"] = True
        assert consumer.process(_raw(bad)) is False
        assert window.observation_count() == 0

    def test_pipeline_of_only_violations_produces_no_signal(self):
        """If all ICD-2 inputs are rejected, build_signal returns None."""
        window = _make_window()
        consumer = _make_consumer(window)
        for i in range(5):
            bad = _make_observation(message_id=f"bad-{i}")
            bad["privacy"]["contains_images"] = True
            consumer.process(_raw(bad))
        publisher = SignalPublisher()
        signal = publisher.build_signal(window)
        assert signal is None, "No valid observations → no signal must be emitted"

    def test_mixed_valid_and_violations_only_valid_counted(self):
        """Privacy-violating observations are blocked; valid ones still populate window."""
        window = _make_window()
        consumer = _make_consumer(window)
        # 3 valid
        for i in range(3):
            consumer.process(_raw(_make_observation(message_id=f"ok-{i}")))
        # 2 violations
        for i in range(2):
            bad = _make_observation(message_id=f"bad-{i}")
            bad["privacy"]["contains_images"] = True
            consumer.process(_raw(bad))
        assert window.observation_count() == 3


# ---------------------------------------------------------------------------
# ICD-3 signal privacy flag enforcement
# ---------------------------------------------------------------------------

class TestIcd3PrivacyFlags:
    """Privacy flags in the ICD-3 signal must always be False."""

    def test_privacy_flags_false_in_output_signal(self):
        publisher, window = _build_pipeline_with_n_obs(5)
        signal = publisher.build_signal(window)
        assert signal is not None
        priv = signal["privacy"]
        assert priv["contains_images"] is False
        assert priv["contains_frame_urls"] is False
        assert priv["contains_face_embeddings"] is False

    def test_privacy_flags_false_with_demographics(self):
        """Even with demographic data in the window, privacy flags stay False."""
        window = _make_window()
        consumer = _make_consumer(window)
        for i in range(4):
            obs = _make_observation(message_id=f"obs-{i}", confidence=0.95)
            obs["demographics"] = {
                "age_group": {
                    "child": 0.05, "young_adult": 0.4,
                    "adult": 0.45, "senior": 0.1,
                },
                "dwell_estimate_ms": 2000,
            }
            consumer.process(_raw(obs))
        publisher = SignalPublisher()
        signal = publisher.build_signal(window)
        assert signal is not None
        priv = signal["privacy"]
        assert priv["contains_images"] is False
        assert priv["contains_frame_urls"] is False
        assert priv["contains_face_embeddings"] is False

    def test_privacy_flags_false_with_pipeline_degraded(self):
        """Degraded pipeline state does not affect privacy flags."""
        window = _make_window()
        consumer = _make_consumer(window)
        for i in range(3):
            obs = _make_observation(message_id=f"obs-{i}", pipeline_degraded=True)
            consumer.process(_raw(obs))
        publisher = SignalPublisher()
        signal = publisher.build_signal(window)
        assert signal is not None
        assert signal["privacy"]["contains_images"] is False


# ---------------------------------------------------------------------------
# Egress audit — banned key inspection in serialized bytes
# ---------------------------------------------------------------------------

class TestEgressAudit:
    """
    The serialized ICD-3 payload bytes must contain no banned keys.

    This is the egress audit: verify that no raw-image metadata, embedding
    keys, or frame references survive the ICD-2 → ICD-3 transformation.
    """

    def test_serialized_signal_contains_no_banned_keys(self):
        publisher, window = _build_pipeline_with_n_obs(5)
        signal = publisher.build_signal(window)
        assert signal is not None
        payload_bytes = json.dumps(signal).encode("utf-8")
        found = _has_banned_key_in_bytes(payload_bytes)
        assert not found, (
            f"Banned keys found in ICD-3 egress payload: {found}\n"
            f"Payload: {payload_bytes.decode()}"
        )

    def test_serialized_signal_with_demographics_no_banned_keys(self):
        """Demographic data in ICD-3 must also be free of banned keys."""
        window = _make_window()
        consumer = _make_consumer(window)
        for i in range(4):
            obs = _make_observation(message_id=f"obs-{i}", confidence=0.95)
            obs["demographics"] = {
                "age_group": {
                    "child": 0.05, "young_adult": 0.4,
                    "adult": 0.45, "senior": 0.1,
                },
                "dwell_estimate_ms": 3000,
            }
            consumer.process(_raw(obs))
        publisher = SignalPublisher()
        signal = publisher.build_signal(window)
        assert signal is not None
        payload_bytes = json.dumps(signal).encode("utf-8")
        found = _has_banned_key_in_bytes(payload_bytes)
        assert not found, f"Banned keys found in demographic ICD-3 egress: {found}"

    def test_no_base64_pattern_in_egress(self):
        """No base64-like string appears in the ICD-3 payload."""
        publisher, window = _build_pipeline_with_n_obs(5)
        signal = publisher.build_signal(window)
        assert signal is not None
        payload_text = json.dumps(signal)
        # Base64 blocks: 40+ chars of alphanumeric + / + = padding
        base64_pattern = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
        match = base64_pattern.search(payload_text)
        assert match is None, (
            f"Possible base64 blob found in ICD-3 egress: {match.group()!r}"
        )

    def test_no_url_like_image_references_in_egress(self):
        """No http(s) or file:// image URLs appear in the ICD-3 payload."""
        publisher, window = _build_pipeline_with_n_obs(5)
        signal = publisher.build_signal(window)
        assert signal is not None
        payload_text = json.dumps(signal)
        url_patterns = [
            r"https?://",
            r"file://",
            r"data:image/",
            r"rtsp://",
        ]
        for pattern in url_patterns:
            match = re.search(pattern, payload_text)
            assert match is None, (
                f"URL-like pattern '{pattern}' found in ICD-3 egress: {match.group()!r}"
            )


# ---------------------------------------------------------------------------
# Schema conformance — ICD-3 self-validation
# ---------------------------------------------------------------------------

class TestIcd3SchemaConformance:
    """
    The ICD-3 signal produced by build_signal must pass the JSON schema
    (audience-state-signal.schema.json v1.0). This is also tested in the
    contract suite; here we verify it at the integration level with real
    pipeline data.
    """

    def test_signal_schema_conforms(self):
        import jsonschema
        from pathlib import Path

        schema_path = (
            Path(__file__).resolve().parents[2]
            / "contracts" / "decision-optimizer" / "audience-state-signal.schema.json"
        )
        schema = json.loads(schema_path.read_text())
        validator = jsonschema.Draft202012Validator(schema)

        publisher, window = _build_pipeline_with_n_obs(5)
        signal = publisher.build_signal(window)
        assert signal is not None

        errors = list(validator.iter_errors(signal))
        assert not errors, (
            "ICD-3 signal from real pipeline failed schema validation:\n"
            + "\n".join(f"  [{e.json_path}] {e.message}" for e in errors)
        )

    def test_all_required_fields_present(self):
        publisher, window = _build_pipeline_with_n_obs(5)
        signal = publisher.build_signal(window)
        assert signal is not None

        required = [
            "schema_version", "message_type", "message_id", "produced_at",
            "tenant_id", "site_id", "camera_id", "state", "source_quality", "privacy",
        ]
        for field in required:
            assert field in signal, f"Required ICD-3 field missing: {field}"
        assert "presence" in signal["state"]
        assert "stability" in signal["state"]


# ---------------------------------------------------------------------------
# Pipeline-level stability and freeze propagation
# ---------------------------------------------------------------------------

class TestStabilityAndFreeze:
    """Freeze and stability flags propagate correctly through the pipeline."""

    def test_empty_window_produces_no_signal(self):
        window = _make_window()
        publisher = SignalPublisher()
        assert publisher.build_signal(window) is None

    def test_below_stability_threshold_freezes(self):
        """With fewer observations than min_stability, freeze_decision=True."""
        window = _make_window()
        consumer = _make_consumer(window)
        # Add only 1 obs; threshold is 3
        consumer.process(_raw(_make_observation()))
        publisher = SignalPublisher()
        signal = publisher.build_signal(window)
        assert signal is not None
        assert signal["state"]["stability"]["freeze_decision"] is True
        assert signal["state"]["stability"]["state_stable"] is False

    def test_at_stability_threshold_state_stable(self):
        """At min_stability_observations=3, state_stable becomes True."""
        window = _make_window()
        consumer = _make_consumer(window)
        for i in range(3):
            consumer.process(_raw(_make_observation(
                message_id=f"obs-{i}", confidence=0.9
            )))
        publisher = SignalPublisher()
        signal = publisher.build_signal(window)
        assert signal is not None
        assert signal["state"]["stability"]["state_stable"] is True

    def test_low_confidence_triggers_freeze(self):
        """Below confidence threshold, freeze_decision=True even if stable."""
        window = _make_window()
        consumer = _make_consumer(window)
        for i in range(5):
            consumer.process(_raw(_make_observation(
                message_id=f"obs-{i}", confidence=0.3  # below 0.5 threshold
            )))
        publisher = SignalPublisher()
        signal = publisher.build_signal(window)
        assert signal is not None
        assert signal["state"]["stability"]["freeze_decision"] is True

    def test_pipeline_degraded_propagates_to_signal(self):
        """pipeline_degraded=True in ICD-2 appears in source_quality of ICD-3."""
        window = _make_window()
        consumer = _make_consumer(window)
        for i in range(3):
            consumer.process(_raw(_make_observation(
                message_id=f"obs-{i}", pipeline_degraded=True
            )))
        publisher = SignalPublisher()
        signal = publisher.build_signal(window)
        assert signal is not None
        assert signal["source_quality"]["pipeline_degraded"] is True
