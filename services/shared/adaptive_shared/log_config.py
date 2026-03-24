"""
adaptive_shared.log_config — structured JSON logging for all services (OBS-001).

Usage (call once at the top of each service's main.py, before any other imports
that use logging):

    from adaptive_shared.log_config import setup_logging
    setup_logging("player", "INFO")

Output format (one JSON object per line):
    {"ts":"2026-03-24T10:00:00.123Z","level":"INFO","svc":"player","logger":"player.main","msg":"player started"}

No third-party dependencies. Uses only Python stdlib.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


# All standard LogRecord instance attribute names — excluded from the JSON output.
# Only application-level `extra={}` keys will appear as additional fields.
_STANDARD_LOG_ATTRS: frozenset[str] = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
})


class _JsonFormatter(logging.Formatter):
    """Formats each log record as a single JSON line."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._svc = service_name

    def format(self, record: logging.LogRecord) -> str:
        # Format exception info into the message if present
        msg = record.getMessage()
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            msg = f"{msg}\n{record.exc_text}"

        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z",
            "level": record.levelname,
            "svc": self._svc,
            "logger": record.name,
            "msg": msg,
        }

        # Include application-level extra fields attached to the record.
        # All standard LogRecord instance attributes are excluded.
        for key, val in record.__dict__.items():
            if key in _STANDARD_LOG_ATTRS or key.startswith("_"):
                continue
            try:
                json.dumps(val)  # only include JSON-serialisable extras
                payload[key] = val
            except (TypeError, ValueError):
                payload[key] = str(val)

        return json.dumps(payload, ensure_ascii=False)


def setup_logging(service_name: str, level: str = "INFO") -> None:
    """
    Configure root logger with JSON output to stdout.

    Call once at process startup, before any other logging calls.
    Idempotent: calling a second time with the same args is a no-op.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()

    # Idempotent guard: skip if already configured with our formatter
    if root.handlers:
        for handler in root.handlers:
            if isinstance(getattr(handler, "formatter", None), _JsonFormatter):
                return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter(service_name))
    handler.setLevel(numeric_level)

    root.setLevel(numeric_level)
    root.handlers.clear()
    root.addHandler(handler)
