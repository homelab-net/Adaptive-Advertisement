#!/usr/bin/env python3
"""
sim-cv-injector — Adaptive Advertisement simulation tool.

Publishes synthetic ICD-2 cv-observation messages to the MQTT broker so the
full audience-state → decision-optimizer → player pipeline can be exercised
without a camera or the input-cv service running.

Usage:
    python tools/sim-cv-injector.py [OPTIONS]

Options:
    --scenario  attract | single | group  (default: single)
    --rate      Observations per second   (default: 1.0)
    --count     Stop after N observations; 0 = run forever  (default: 0)
    --host      MQTT broker host          (default: 127.0.0.1)
    --port      MQTT broker port          (default: 1883)
    --tenant    Tenant ID                 (default: default-tenant)
    --site      Site ID                   (default: site-01)
    --camera    Camera ID                 (default: cam-main-01)

Environment overrides (override CLI defaults):
    MQTT_HOST, MQTT_PORT, TENANT_ID, SITE_ID

Scenarios:
    attract  — 0 people present; triggers attract-loop manifest
    single   — 1 person, confidence 0.85; triggers default manifest
    group    — 4 people, confidence 0.90; triggers group manifest

Requires: paho-mqtt >= 1.6  (pip install paho-mqtt)

Privacy: all privacy flags are hardcoded False per ICD-2 contract.
         No pixel data, frame URLs, or embeddings are generated.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
import uuid
from datetime import datetime, timezone

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt not installed. Run: pip install paho-mqtt", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("sim-cv-injector")

# Canned scenario parameters
SCENARIOS: dict[str, dict] = {
    "attract": {
        "present": 0,
        "confidence": 0.50,
        "description": "no audience — attract loop",
    },
    "single": {
        "present": 1,
        "confidence": 0.85,
        "description": "1 person — default creative",
    },
    "group": {
        "present": 4,
        "confidence": 0.90,
        "description": "4 people — group creative",
    },
}


def _build_observation(
    frame_seq: int,
    present: int,
    confidence: float,
    tenant_id: str,
    site_id: str,
    camera_id: str,
) -> bytes:
    """Build a valid ICD-2 cv-observation JSON payload."""
    obs = {
        "schema_version": "1.0.0",
        "message_type": "cv_observation",
        "message_id": str(uuid.uuid4()),
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id,
        "site_id": site_id,
        "camera_id": camera_id,
        "pipeline_id": "sim-injector-01",
        "frame_seq": frame_seq,
        "window_ms": 1000,
        "counts": {
            "present": present,
            "confidence": confidence,
        },
        "quality": {
            "frames_processed": 10,
            "frames_dropped": 0,
            "pipeline_degraded": False,
        },
        "privacy": {
            "contains_images": False,
            "contains_frame_urls": False,
            "contains_face_embeddings": False,
        },
    }
    return json.dumps(obs).encode("utf-8")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scenario", choices=list(SCENARIOS), default="single",
                   help="Audience scenario to simulate (default: single)")
    p.add_argument("--rate", type=float, default=1.0,
                   help="Observations per second (default: 1.0)")
    p.add_argument("--count", type=int, default=0,
                   help="Stop after N observations; 0 = run forever (default: 0)")
    p.add_argument("--host", default=None,
                   help="MQTT broker host (default: 127.0.0.1 or MQTT_HOST env)")
    p.add_argument("--port", type=int, default=None,
                   help="MQTT broker port (default: 1883 or MQTT_PORT env)")
    p.add_argument("--tenant", default=None,
                   help="Tenant ID (default: default-tenant or TENANT_ID env)")
    p.add_argument("--site", default=None,
                   help="Site ID (default: site-01 or SITE_ID env)")
    p.add_argument("--camera", default="cam-main-01",
                   help="Camera ID (default: cam-main-01)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    host = args.host or os.environ.get("MQTT_HOST", "127.0.0.1")
    port = args.port or int(os.environ.get("MQTT_PORT", "1883"))
    tenant_id = args.tenant or os.environ.get("TENANT_ID", "default-tenant")
    site_id = args.site or os.environ.get("SITE_ID", "site-01")
    camera_id = args.camera

    scenario = SCENARIOS[args.scenario]
    topic = f"cv/v1/observations/{tenant_id}/{site_id}/{camera_id}"
    interval = 1.0 / args.rate if args.rate > 0 else 1.0

    log.info("sim-cv-injector starting")
    log.info("  broker  : %s:%d", host, port)
    log.info("  topic   : %s", topic)
    log.info("  scenario: %s — %s", args.scenario, scenario["description"])
    log.info("  rate    : %.1f obs/s  interval: %.2fs", args.rate, interval)
    log.info("  count   : %s", args.count if args.count > 0 else "unlimited (Ctrl-C to stop)")

    client = mqtt.Client(
        client_id=f"sim-cv-injector-{uuid.uuid4().hex[:8]}",
        protocol=mqtt.MQTTv5,
    )

    try:
        client.connect(host, port, keepalive=60)
    except Exception as exc:
        log.error("Failed to connect to MQTT broker at %s:%d — %s", host, port, exc)
        log.error("Is the broker running? Start the stack with: docker compose up mosquitto")
        sys.exit(1)

    client.loop_start()
    log.info("Connected to MQTT broker.")

    shutdown = False

    def _stop(sig, frame):
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    frame_seq = 0
    sent = 0

    try:
        while not shutdown:
            payload = _build_observation(
                frame_seq=frame_seq,
                present=scenario["present"],
                confidence=scenario["confidence"],
                tenant_id=tenant_id,
                site_id=site_id,
                camera_id=camera_id,
            )
            result = client.publish(topic, payload, qos=1)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                log.warning("publish error rc=%d", result.rc)
            else:
                frame_seq += 1
                sent += 1
                if sent % 10 == 0 or sent == 1:
                    log.info("published %d observations (scenario=%s present=%d conf=%.2f)",
                             sent, args.scenario, scenario["present"], scenario["confidence"])

            if args.count > 0 and sent >= args.count:
                log.info("Reached target count %d — stopping.", args.count)
                break

            time.sleep(interval)
    finally:
        client.loop_stop()
        client.disconnect()
        log.info("sim-cv-injector stopped. Total observations published: %d", sent)


if __name__ == "__main__":
    main()
