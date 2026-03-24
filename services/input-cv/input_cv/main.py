"""
input-cv service entrypoint.

Wires config -> pipeline -> observation builder -> publisher -> health tracker.
Runs the supervision loop: open pipeline, read metadata, build observations,
publish, handle faults, reopen with backoff.

The DeepStream driver is imported here and only here, inside a try/except
so the rest of the codebase remains importable without pyds installed.

Environment variables (all required unless marked optional):
  INPUT_CV_CONFIG_PATH   Path to camera-source.json (default: config/camera-source.json)
  MQTT_HOST              MQTT broker host
  MQTT_PORT              MQTT broker port (default: 1883)
  MQTT_CLIENT_ID         MQTT client identifier
  MQTT_USERNAME          (optional) MQTT username
  MQTT_PASSWORD          (optional) MQTT password
  MQTT_TLS               (optional) "true" to enable TLS
  TENANT_ID              Deployment tenant identifier
  SITE_ID                Deployment site identifier
  PIPELINE_ID            Pipeline instance identifier (default: pipeline-01)
  LOG_LEVEL              Python logging level (default: INFO)
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time

from input_cv.config import load_camera_config
from input_cv.health import HealthTracker
from input_cv.observation import ObservationContext, PrivacyViolationError, build_observation
from input_cv.pipeline import DeviceNotFoundError, PipelineReadError
from input_cv.publisher import MqttPublisher
from input_cv.recovery import ReopenLoop


def _configure_logging() -> None:
    from adaptive_shared.log_config import setup_logging
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    setup_logging("input-cv", level)


def _build_pipeline_driver(config):
    """
    Instantiate the pipeline driver selected by INPUT_CV_PIPELINE_BACKEND.

    Backends:
      deepstream (default) — requires pyds + GStreamer on Jetson.
      null                 — NullDriver stub for simulation and CI; no hardware needed.
    """
    backend = os.environ.get("INPUT_CV_PIPELINE_BACKEND", "deepstream").lower()

    if backend == "null":
        from input_cv.pipeline.null_driver import NullDriver  # noqa: PLC0415
        logging.getLogger("input_cv").info(
            "input-cv: using NullDriver simulation backend (INPUT_CV_PIPELINE_BACKEND=null)"
        )
        return NullDriver()

    try:
        from input_cv.pipeline.deepstream_driver import DeepStreamDriver  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "DeepStream Python bindings (pyds) are not installed. "
            "Run inside the nvcr.io DeepStream container on the target Jetson. "
            "Set INPUT_CV_PIPELINE_BACKEND=null to run in simulation mode."
        ) from exc

    return DeepStreamDriver(
        device_path=config.device_path,
        pixel_format=config.pixel_format,
        width=config.width,
        height=config.height,
        fps=config.fps,
        startup_timeout_ms=config.startup_timeout_ms,
        read_timeout_ms=config.read_timeout_ms,
    )


def run(
    config_path: str | None = None,
    *,
    _driver=None,  # injection point for tests
    _publisher=None,  # injection point for tests
) -> None:
    """
    Main service loop.

    Args:
        config_path: override for INPUT_CV_CONFIG_PATH.
        _driver: optional PipelineDriver injection (tests only).
        _publisher: optional Publisher injection (tests only).
    """
    logger = logging.getLogger("input_cv")
    path = config_path or os.environ.get("INPUT_CV_CONFIG_PATH", "config/camera-source.json")

    config = load_camera_config(path)
    logger.info("input-cv: config loaded for camera_id=%s device=%s", config.camera_id, config.device_path)

    if not config.enabled:
        logger.warning("input-cv: camera %s is disabled in config; exiting.", config.camera_id)
        return

    tenant_id = os.environ["TENANT_ID"]
    site_id = os.environ["SITE_ID"]
    pipeline_id = os.environ.get("PIPELINE_ID", "pipeline-01")

    context = ObservationContext(
        tenant_id=tenant_id,
        site_id=site_id,
        camera_id=config.camera_id,
        pipeline_id=pipeline_id,
    )
    obs_topic = f"cv/v1/observations/{tenant_id}/{site_id}/{config.camera_id}"

    health = HealthTracker(camera_id=config.camera_id, pipeline_id=pipeline_id)
    reopen_loop = ReopenLoop(
        health=health,
        initial_backoff_ms=config.reopen.initial_backoff_ms,
        max_backoff_ms=config.reopen.max_backoff_ms,
        reopen_enabled=config.reopen.enabled,
    )

    driver = _driver or _build_pipeline_driver(config)

    publisher = _publisher or MqttPublisher(
        host=os.environ.get("MQTT_HOST", "localhost"),
        port=int(os.environ.get("MQTT_PORT", "1883")),
        client_id=os.environ.get("MQTT_CLIENT_ID", "input-cv-01"),
        username=os.environ.get("MQTT_USERNAME"),
        password=os.environ.get("MQTT_PASSWORD"),
        tls=os.environ.get("MQTT_TLS", "").lower() == "true",
    )

    shutdown = False

    def _handle_signal(sig, frame):
        nonlocal shutdown
        logger.info("input-cv: shutdown signal received.")
        shutdown = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    publisher.connect()
    logger.info("input-cv: MQTT publisher connected; topic=%s", obs_topic)

    try:
        while not shutdown:
            # --- open / reopen loop ---
            opened = False
            while not shutdown:
                try:
                    driver.open()
                    health.mark_device_present()
                    health.mark_pipeline_running()
                    reopen_loop.reset()
                    opened = True
                    logger.info("input-cv: pipeline running on %s", config.device_path)
                    break
                except DeviceNotFoundError as exc:
                    health.mark_device_absent()
                    logger.warning("input-cv: %s", exc)
                    if not reopen_loop.enabled:
                        logger.error("input-cv: reopen disabled; exiting.")
                        return
                    reopen_loop.wait_and_record()

            if not opened or shutdown:
                break

            # --- read / publish loop ---
            while not shutdown:
                try:
                    metadata_list = driver.read_metadata()
                    health.record_frame()

                    for raw_meta in metadata_list:
                        try:
                            obs = build_observation(raw_meta, context)
                            publisher.publish(obs_topic, obs.to_json_bytes())
                        except PrivacyViolationError as exc:
                            logger.critical("input-cv: %s", exc)
                            # Do not publish; do not crash the loop.

                    # Respect the 10 FPS inference cadence from TRD PERF-003.
                    # The DeepStream pipeline already gates output at the configured fps;
                    # a small sleep prevents a tight spin if read_metadata returns empty.
                    if not metadata_list:
                        time.sleep(0.05)

                except PipelineReadError as exc:
                    logger.warning("input-cv: pipeline read error: %s", exc)
                    driver.close()
                    health.mark_device_absent()
                    if not reopen_loop.enabled:
                        logger.error("input-cv: reopen disabled after read error; exiting.")
                        return
                    reopen_loop.wait_and_record()
                    break  # back to open/reopen loop
    finally:
        driver.close()
        publisher.disconnect()
        logger.info("input-cv: service stopped.")


def main() -> None:
    _configure_logging()
    try:
        run()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logging.getLogger("input_cv").critical("input-cv: fatal error: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
