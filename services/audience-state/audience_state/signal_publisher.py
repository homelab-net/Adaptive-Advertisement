"""
Signal publisher — builds and publishes ICD-3 audience-state-signal messages.

Responsibilities
----------------
- Query ObservationWindow for current smoothed state
- Build a well-formed audience-state-signal dict (ICD-3)
- Validate the outgoing signal against audience-state-signal.schema.json
  BEFORE publishing — this is the outbound privacy and contract gate
- Publish the validated signal to the MQTT broker

Privacy gate
------------
The privacy block is hardcoded to false in build_signal(). The schema validator
enforces this as a secondary check. No image data from upstream observations
is forwarded — only aggregated numeric attributes appear in the outbound signal.

Schema self-validation
----------------------
build_signal() validates the constructed signal before returning it. If the
signal fails validation (which would indicate a bug in this service), it returns
None and logs an error rather than publishing a non-conformant message.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import jsonschema

from . import config
from .observation_store import ObservationWindow

log = logging.getLogger(__name__)

_SIGNAL_SCHEMA_PATH = (
    Path(config.CONTRACT_DIR)
    / "decision-optimizer"
    / "audience-state-signal.schema.json"
)


def _load_signal_schema() -> dict:
    with open(_SIGNAL_SCHEMA_PATH) as f:
        return json.load(f)


class SignalPublisher:
    """
    Builds ICD-3 signals from the observation window and publishes them.
    The MQTT client is passed into publish() rather than held as state so
    tests can exercise build_signal() without any MQTT dependency.
    """

    def __init__(self) -> None:
        schema = _load_signal_schema()
        self._validator = jsonschema.Draft202012Validator(schema)
        self._published: int = 0
        self._validation_failures: int = 0

    # ------------------------------------------------------------------
    # Signal construction
    # ------------------------------------------------------------------

    def build_signal(self, window: ObservationWindow) -> Optional[dict]:
        """
        Build a validated ICD-3 audience-state-signal dict from the current
        window state. Returns None if the window is empty or the constructed
        signal fails schema validation (indicates a bug — logged as error).
        """
        state = window.compute_state()
        if state is None:
            log.debug("build_signal: window empty — no signal to publish")
            return None

        age_ms = window.newest_observation_age_ms() or 0

        signal: dict = {
            "schema_version": "1.0.0",
            "message_type": "audience_state_signal",
            "message_id": str(uuid.uuid4()),
            "produced_at": _utc_now(),
            "tenant_id": config.TENANT_ID,
            "site_id": config.SITE_ID,
            "camera_id": config.CAMERA_ID,
            "state": state,
            "source_quality": {
                "signal_age_ms": age_ms,
                "pipeline_degraded": window.any_pipeline_degraded(),
                "observations_dropped": 0,
            },
            # Privacy hard contract — always false; never forwarded from upstream
            "privacy": {
                "contains_images": False,
                "contains_frame_urls": False,
                "contains_face_embeddings": False,
            },
        }

        # Include demographics if available (optional ICD-3 field)
        demog = window.compute_demographics()
        if demog is not None:
            signal["state"]["demographics"] = demog

        # Self-validate before returning
        errors = list(self._validator.iter_errors(signal))
        if errors:
            self._validation_failures += 1
            log.error(
                "build_signal: outbound signal failed ICD-3 schema validation "
                "(BUG in signal_publisher): %s",
                errors[0].message,
            )
            return None

        return signal

    # ------------------------------------------------------------------
    # MQTT publish
    # ------------------------------------------------------------------

    async def publish(self, client, signal: dict) -> bool:
        """
        Publish a pre-validated signal dict via the aiomqtt client.
        Returns True on success.
        """
        try:
            await client.publish(
                config.MQTT_AUDIENCE_STATE_TOPIC,
                json.dumps(signal),
            )
            self._published += 1
            log.debug(
                "published ICD-3 signal: message_id=%s count=%d conf=%.2f freeze=%s",
                signal["message_id"],
                signal["state"]["presence"]["count"],
                signal["state"]["presence"]["confidence"],
                signal["state"]["stability"]["freeze_decision"],
            )
            return True
        except Exception as exc:
            log.error("publish failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def status(self) -> dict:
        return {
            "published": self._published,
            "validation_failures": self._validation_failures,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
