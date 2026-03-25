"""
Observation consumer — ICD-2 cv-observation ingestion and validation.

Mirrors the pattern from decision-optimizer/signal_consumer.py:
- Validates incoming MQTT payloads against cv-observation.schema.json
- Enforces privacy hard-contract flags (const: false — schema catches violations)
- Deduplicates by message_id
- Feeds valid observations into an ObservationWindow

I/O separation
--------------
This class is free of MQTT client code. process(raw) is called externally
(main.py or tests). This makes it fully unit-testable without a broker.

Privacy note
------------
The cv-observation schema enforces privacy.contains_images/contains_frame_urls/
contains_face_embeddings as const:false. jsonschema validation is the primary
gate. Nothing is logged or persisted beyond the sliding window.
"""
import json
import logging
from pathlib import Path
from typing import Optional

import jsonschema

from . import config
from .observation_store import ObservationWindow

log = logging.getLogger(__name__)

_SCHEMA_PATH = (
    Path(config.CONTRACT_DIR) / "audience-state" / "cv-observation.schema.json"
)
_MAX_SEEN_IDS = 5_000


def _load_cv_observation_schema() -> dict:
    with open(_SCHEMA_PATH) as f:
        return json.load(f)


class ObservationConsumer:
    """
    Validates ICD-2 messages and feeds them into an ObservationWindow.
    Construct with the window that should receive accepted observations.
    """

    def __init__(self, window: ObservationWindow) -> None:
        self._window = window
        schema = _load_cv_observation_schema()
        self._validator = jsonschema.Draft202012Validator(schema)
        self._seen_ids: dict[str, bool] = {}
        self._total_received: int = 0
        self._total_rejected: int = 0

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def process(self, raw: bytes | str) -> bool:
        """
        Parse, validate, deduplicate, and store one raw MQTT payload.
        Returns True if accepted, False if rejected.
        """
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            log.error("observation rejected: invalid JSON: %s", exc)
            self._total_rejected += 1
            return False

        err = self._validate(msg)
        if err:
            log.error("observation rejected: schema: %s", err)
            self._total_rejected += 1
            return False

        message_id: str = msg["message_id"]
        if message_id in self._seen_ids:
            log.debug("observation deduplicated: message_id=%s", message_id)
            return False

        self._record_id(message_id)
        self._window.add(msg)
        self._total_received += 1
        log.debug(
            "observation accepted: message_id=%s frame_seq=%d count=%d conf=%.2f",
            message_id,
            msg.get("frame_seq", -1),
            msg["counts"]["present"],
            msg["counts"]["confidence"],
        )
        return True

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def status(self) -> dict:
        return {
            "total_received": self._total_received,
            "total_rejected": self._total_rejected,
            "observations_in_window": self._window.observation_count(),
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _validate(self, msg: dict) -> Optional[str]:
        errors = list(self._validator.iter_errors(msg))
        if not errors:
            return None
        return "; ".join(e.message for e in errors[:3])

    def _record_id(self, message_id: str) -> None:
        self._seen_ids[message_id] = True
        if len(self._seen_ids) > _MAX_SEEN_IDS:
            keep = list(self._seen_ids.keys())[_MAX_SEEN_IDS // 2:]
            self._seen_ids = {k: True for k in keep}
