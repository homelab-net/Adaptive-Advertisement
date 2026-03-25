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


# ── PRIV-004 runtime: captured log PII scan ───────────────────────────────────

# Patterns that must never appear in any log line at runtime
_RUNTIME_PII_PATTERNS = [
    re.compile(r"face_embedding", re.IGNORECASE),
    re.compile(r"frame_data", re.IGNORECASE),
    re.compile(r"contains_images.*true", re.IGNORECASE),
    re.compile(r"contains_frame_urls.*true", re.IGNORECASE),
    re.compile(r"contains_face_embeddings.*true", re.IGNORECASE),
    # Long base64-like blobs: 40+ consecutive base64 chars
    re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),
]


class _CaptureHandler(logging.Handler):
    """Logging handler that accumulates all log records."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


def _check_lines_for_pii(lines: list[str]) -> list[str]:
    """Return list of violation descriptions, empty if clean."""
    violations = []
    for line in lines:
        for pattern in _RUNTIME_PII_PATTERNS:
            if pattern.search(line):
                violations.append(f"pattern={pattern.pattern!r} line={line!r}")
    return violations


def _install_capture(root_logger: logging.Logger) -> _CaptureHandler:
    handler = _CaptureHandler()
    root_logger.addHandler(handler)
    return handler


def _remove_capture(root_logger: logging.Logger, handler: _CaptureHandler) -> None:
    root_logger.removeHandler(handler)


class TestRuntimeLogPIILint:
    """
    PRIV-004 runtime gate: exercise code paths and assert no PII appears
    in captured log output.
    """

    def test_policy_engine_logs_no_pii(self) -> None:
        """PolicyEngine.evaluate() must not log any PII."""
        import sys
        sys.path.insert(0, str(_SERVICES_ROOT / "decision-optimizer"))
        from decision_optimizer.policy import Rule, PolicyConfig, PolicyEngine

        root = logging.getLogger()
        handler = _install_capture(root)
        try:
            rules = [
                Rule("r1", priority=10, manifest_id="m-promo",
                     presence_count_gte=1),
                Rule("r2", priority=0, manifest_id="m-attract"),
            ]
            eng = PolicyEngine(PolicyConfig(rules=rules))
            signal = {
                "schema_version": "1.0.0",
                "state": {
                    "presence": {"count": 2, "confidence": 0.9},
                    "stability": {
                        "state_stable": True,
                        "freeze_decision": False,
                        "demographics_suppressed": True,
                    },
                    "demographics": {},
                },
                "source_quality": {"signal_age_ms": 100, "pipeline_degraded": False},
                "privacy": {
                    "contains_images": False,
                    "contains_frame_urls": False,
                    "contains_face_embeddings": False,
                },
            }
            result = eng.evaluate(signal)
            assert result == "m-promo"
        finally:
            _remove_capture(root, handler)

        violations = _check_lines_for_pii(handler.lines)
        assert not violations, (
            "PII detected in PolicyEngine log output:\n" + "\n".join(violations)
        )

    def test_audience_sink_privacy_gate_logs_no_pii(self) -> None:
        """
        Audience sink privacy violation log message must not echo the PII value
        (only the flag names, not contents).
        """
        import sys
        sys.path.insert(0, str(_SERVICES_ROOT / "dashboard-api"))

        # We can test _parse_snapshot directly without DB
        import importlib.util
        import unittest.mock

        root = logging.getLogger()
        handler = _install_capture(root)
        try:
            # Craft a payload that triggers the privacy gate
            import json as _json
            bad_payload = _json.dumps({
                "schema_version": "1.0.0",
                "produced_at": "2026-01-01T00:00:00Z",
                "state": {
                    "presence": {"count": 1, "confidence": 0.9},
                    "stability": {"state_stable": True},
                },
                "source_quality": {"pipeline_degraded": False},
                "privacy": {
                    "contains_images": True,       # <-- violation
                    "contains_frame_urls": False,
                    "contains_face_embeddings": False,
                },
            }).encode()

            # Import and call _parse_snapshot
            spec2 = importlib.util.spec_from_file_location(
                "dashboard_api.audience_sink",
                _SERVICES_ROOT / "dashboard-api" / "dashboard_api" / "audience_sink.py",
            )
            mod = importlib.util.module_from_spec(spec2)
            mod.__package__ = "dashboard_api"
            # Patch out imports that require DB
            with unittest.mock.patch.dict("sys.modules", {
                "dashboard_api.config": unittest.mock.MagicMock(
                    settings=unittest.mock.MagicMock(
                        mqtt_audience_state_topic="test",
                        mqtt_broker_host="localhost",
                        mqtt_broker_port=1883,
                    )
                ),
                "dashboard_api.db": unittest.mock.MagicMock(),
                "dashboard_api.models": unittest.mock.MagicMock(),
                "aiomqtt": unittest.mock.MagicMock(),
            }):
                spec2.loader.exec_module(mod)
                result = mod._parse_snapshot(bad_payload)

            assert result is None, "Privacy-violating payload should return None"
        finally:
            _remove_capture(root, handler)

        violations = _check_lines_for_pii(handler.lines)
        assert not violations, (
            "PII detected in audience_sink log output:\n" + "\n".join(violations)
        )
