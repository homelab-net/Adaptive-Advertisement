"""
OBS-001 + PRIV-004 combined: structured log format validation and PII scan.

TestJsonLogFormat  — OBS-001
    Validates that setup_logging() / _JsonFormatter produces correct
    JSON-per-line output with all required fields: ts, level, svc, logger, msg.

TestPiiSourceScan  — PRIV-004
    Static analysis: scans all non-test service Python sources for log calls
    that could emit frame data, person identifiers, or raw base64 blobs.
    This is a compile-time gate; it does not require running services.
"""
from __future__ import annotations

import io
import json
import logging
import re
from pathlib import Path

import pytest

from adaptive_shared.log_config import _JsonFormatter


# ── Helpers ──────────────────────────────────────────────────────────────────

def _capture_json_records(service_name: str, fn) -> list[dict]:
    """
    Run fn() while capturing output from a named test logger via _JsonFormatter.
    Returns list of parsed JSON log records.
    """
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(_JsonFormatter(service_name))

    logger = logging.getLogger("_test_capture_isolated")
    orig_handlers = logger.handlers[:]
    orig_level = logger.level
    orig_propagate = logger.propagate
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    try:
        fn()
    finally:
        logger.handlers = orig_handlers
        logger.setLevel(orig_level)
        logger.propagate = orig_propagate

    records = []
    for line in buf.getvalue().splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


# ── OBS-001: Structured log format ───────────────────────────────────────────

class TestJsonLogFormat:
    """Verify _JsonFormatter produces spec-compliant output."""

    def test_required_fields_present(self) -> None:
        log = logging.getLogger("_test_capture_isolated")
        records = _capture_json_records("test-svc", lambda: log.info("hello world"))
        assert records, "No log records captured"
        r = records[0]
        for field in ("ts", "level", "svc", "logger", "msg"):
            assert field in r, f"Missing required field '{field}' in: {r}"

    def test_service_name_in_svc_field(self) -> None:
        log = logging.getLogger("_test_capture_isolated")
        records = _capture_json_records("my-service", lambda: log.info("x"))
        assert records[0]["svc"] == "my-service"

    def test_timestamp_iso8601_with_ms(self) -> None:
        log = logging.getLogger("_test_capture_isolated")
        records = _capture_json_records("ts-svc", lambda: log.info("x"))
        ts = records[0]["ts"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", ts), (
            f"Timestamp does not match YYYY-MM-DDTHH:MM:SS.mmmZ: {ts!r}"
        )

    def test_level_field_uppercase(self) -> None:
        log = logging.getLogger("_test_capture_isolated")
        records = _capture_json_records("lvl-svc", lambda: log.warning("warn msg"))
        assert records[0]["level"] == "WARNING"

    def test_extra_fields_included(self) -> None:
        log = logging.getLogger("_test_capture_isolated")
        records = _capture_json_records(
            "extra-svc",
            lambda: log.info("msg", extra={"manifest_id": "m-001", "count": 5}),
        )
        r = records[0]
        assert r.get("manifest_id") == "m-001"
        assert r.get("count") == 5

    def test_standard_logrecord_attrs_not_leaked(self) -> None:
        """Standard LogRecord instance attributes must not appear as top-level JSON keys."""
        log = logging.getLogger("_test_capture_isolated")
        records = _capture_json_records("leak-svc", lambda: log.info("msg"))
        r = records[0]
        leaked = {
            "pathname", "filename", "lineno", "funcName",
            "thread", "threadName", "processName", "relativeCreated",
            "msecs", "args", "levelno",
        } & set(r.keys())
        assert not leaked, f"Standard LogRecord attrs leaked into JSON output: {leaked}"

    def test_exception_serialised_in_msg(self) -> None:
        log = logging.getLogger("_test_capture_isolated")

        def _emit() -> None:
            try:
                raise ValueError("something went wrong")
            except ValueError:
                log.error("operation failed", exc_info=True)

        records = _capture_json_records("exc-svc", _emit)
        assert len(records) == 1
        msg = records[0]["msg"]
        assert "ValueError" in msg
        assert "something went wrong" in msg

    def test_non_serialisable_extra_becomes_string(self) -> None:
        log = logging.getLogger("_test_capture_isolated")

        class _Unserializable:
            def __repr__(self) -> str:
                return "<Unserializable>"

        records = _capture_json_records(
            "serial-svc",
            lambda: log.info("msg", extra={"obj": _Unserializable()}),
        )
        assert records[0].get("obj") == "<Unserializable>"

    @pytest.mark.parametrize("svc_name", [
        "input-cv", "audience-state", "decision-optimizer",
        "player", "creative", "supervisor", "dashboard-api",
    ])
    def test_all_service_names_round_trip(self, svc_name: str) -> None:
        """Each service name must survive JSON serialisation unchanged."""
        log = logging.getLogger("_test_capture_isolated")
        records = _capture_json_records(svc_name, lambda: log.info("startup"))
        assert records, f"No records for svc={svc_name!r}"
        assert records[0]["svc"] == svc_name


# ── PRIV-004: PII source scan ─────────────────────────────────────────────────

_SERVICES_ROOT = Path(__file__).parent.parent.parent / "services"

# Patterns indicating PII could be emitted through log calls
_FRAME_LOG_RE = re.compile(
    r"log\.\w+\s*\(.*(?:raw_frame|pixel_data|frame_bytes|image_data)",
    re.IGNORECASE,
)
_PERSON_LOG_RE = re.compile(
    r"log\.\w+\s*\(.*(?:face_id\s*=|person_id\s*=|biometric\s*=)",
    re.IGNORECASE,
)
_BASE64_ENCODE_LOG_RE = re.compile(
    r"log\.\w+\s*\(.*(?:base64\.b64encode|\.encode\(.base64.\)|to_base64)",
    re.IGNORECASE,
)


def _service_python_sources() -> list[Path]:
    """All non-test Python source files across all services."""
    sources: list[Path] = []
    for svc_dir in sorted(_SERVICES_ROOT.iterdir()):
        if not svc_dir.is_dir():
            continue
        for py_file in svc_dir.rglob("*.py"):
            # Skip test directories and the DeepStream driver (ARM64-only)
            if any(part in {"tests", "test"} for part in py_file.parts):
                continue
            if "deepstream_driver" in py_file.name:
                continue
            sources.append(py_file)
    return sources


class TestPiiSourceScan:
    """Static analysis: service source must not contain PII-leaking log calls."""

    def test_no_raw_frame_data_logged(self) -> None:
        violations: list[str] = []
        for path in _service_python_sources():
            for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                if _FRAME_LOG_RE.search(line):
                    violations.append(
                        f"{path.relative_to(_SERVICES_ROOT)}:{i}: {line.strip()}"
                    )
        assert not violations, (
            "Raw frame data in log call detected (PRIV-001 violation):\n"
            + "\n".join(violations)
        )

    def test_no_person_identifier_logged(self) -> None:
        violations: list[str] = []
        for path in _service_python_sources():
            for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                if _PERSON_LOG_RE.search(line):
                    violations.append(
                        f"{path.relative_to(_SERVICES_ROOT)}:{i}: {line.strip()}"
                    )
        assert not violations, (
            "Person identifier in log call detected (PRIV-002 violation):\n"
            + "\n".join(violations)
        )

    def test_no_base64_encoding_in_log_calls(self) -> None:
        violations: list[str] = []
        for path in _service_python_sources():
            for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                if _BASE64_ENCODE_LOG_RE.search(line):
                    violations.append(
                        f"{path.relative_to(_SERVICES_ROOT)}:{i}: {line.strip()}"
                    )
        assert not violations, (
            "base64 encoding inside log call detected (potential frame egress):\n"
            + "\n".join(violations)
        )
