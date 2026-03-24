"""
Signal consumer — ICD-3 audience-state signal ingestion.

Responsibilities
----------------
- Validate incoming MQTT payloads against audience-state-signal.schema.json
- Enforce privacy hard-contract flags (all must be false — schema const)
- Deduplicate by message_id
- Maintain the latest valid signal and its wall-clock receipt time
- Expose signal_age_ms() for staleness detection by the decision loop

I/O separation
--------------
This class is free of MQTT client code. It exposes a single process(raw) method
that is called by whoever holds the MQTT connection (main.py or tests).
This makes it fully testable without a broker.

Privacy note
------------
The ICD-3 schema enforces privacy.contains_images/contains_frame_urls/
contains_face_embeddings as const:false. Schema validation is the primary gate.
The consumer does not log or persist signal payloads.
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional

import jsonschema

from . import config

log = logging.getLogger(__name__)

_SCHEMA_PATH = (
    Path(config.CONTRACT_DIR)
    / "decision-optimizer"
    / "audience-state-signal.schema.json"
)

# Cap on how many message_ids to remember for deduplication
_MAX_SEEN_IDS = 5_000


def _load_signal_schema() -> dict:
    with open(_SCHEMA_PATH) as f:
        return json.load(f)


class SignalConsumer:
    """
    Stateful signal store. Thread-safe for reads from a single asyncio event loop.
    """

    def __init__(self) -> None:
        self._schema = _load_signal_schema()
        self._validator = jsonschema.Draft202012Validator(self._schema)
        self._latest: Optional[dict] = None
        self._latest_received_at: Optional[float] = None   # monotonic
        self._seen_ids: dict[str, bool] = {}               # ordered for pruning
        self._total_received: int = 0
        self._total_rejected: int = 0

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def process(self, raw: bytes | str) -> bool:
        """
        Parse, validate, deduplicate, and store one raw MQTT payload.
        Returns True if the signal was accepted, False if rejected.
        Called from the MQTT message callback (main.py).
        """
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            log.error("signal rejected: invalid JSON: %s", exc)
            self._total_rejected += 1
            return False

        err = self._validate(msg)
        if err:
            log.error("signal rejected: schema validation: %s", err)
            self._total_rejected += 1
            return False

        message_id: str = msg["message_id"]
        if message_id in self._seen_ids:
            log.debug("signal deduplicated: message_id=%s", message_id)
            return False

        self._record_id(message_id)
        self._latest = msg
        self._latest_received_at = time.monotonic()
        self._total_received += 1
        log.debug(
            "signal accepted: message_id=%s presence_count=%d confidence=%.2f",
            message_id,
            msg["state"]["presence"]["count"],
            msg["state"]["presence"]["confidence"],
        )
        return True

    # ------------------------------------------------------------------
    # Read-only access for decision loop
    # ------------------------------------------------------------------

    @property
    def latest_signal(self) -> Optional[dict]:
        """The most recently accepted signal, or None if none received yet."""
        return self._latest

    def signal_age_ms(self) -> Optional[int]:
        """
        Milliseconds since the most recent signal was received (monotonic).
        Returns None if no signal has ever been received.
        """
        if self._latest_received_at is None:
            return None
        return int((time.monotonic() - self._latest_received_at) * 1000)

    def status(self) -> dict:
        age = self.signal_age_ms()
        return {
            "latest_message_id": (
                self._latest["message_id"] if self._latest else None
            ),
            "signal_age_ms": age,
            "total_received": self._total_received,
            "total_rejected": self._total_rejected,
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
