"""
Audience-state service entry point.

Data flow
---------
input-cv (ICD-2, MQTT) → ObservationConsumer → ObservationWindow
                                                      ↓ (1 Hz)
                                            SignalPublisher → MQTT (ICD-3)
                                                         ↓
                                             decision-optimizer

Startup sequence
----------------
1. Create ObservationWindow, ObservationConsumer, SignalPublisher.
2. Start health server.
3. Mark ready.
4. Run MQTT subscriber (inbound ICD-2) and publish loop (outbound ICD-3)
   concurrently via asyncio.gather.

Both tasks are essential: if either crashes, the process exits and the
supervisor (ICD-8) restarts it.
"""
import asyncio
import logging
import sys

import aiomqtt
from aiohttp import web

from . import config
from .observation_store import ObservationWindow
from .observation_consumer import ObservationConsumer
from .signal_publisher import SignalPublisher
from .health import make_health_app

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)
log = logging.getLogger(__name__)


async def _run_mqtt_subscribe(consumer: ObservationConsumer) -> None:
    """
    MQTT inbound loop — subscribes to ICD-2 cv-observation topic and feeds
    each payload into the observation consumer. Reconnects with exponential
    backoff on connection loss.
    """
    backoff = config.MQTT_RECONNECT_INITIAL_BACKOFF_S
    while True:
        try:
            log.info(
                "connecting to MQTT broker %s:%d subscribe=%s",
                config.MQTT_BROKER_HOST,
                config.MQTT_BROKER_PORT,
                config.MQTT_CV_OBSERVATION_TOPIC,
            )
            async with aiomqtt.Client(
                hostname=config.MQTT_BROKER_HOST,
                port=config.MQTT_BROKER_PORT,
                identifier=config.MQTT_CLIENT_ID,
            ) as client:
                backoff = config.MQTT_RECONNECT_INITIAL_BACKOFF_S
                await client.subscribe(config.MQTT_CV_OBSERVATION_TOPIC)
                log.info("subscribed: %s", config.MQTT_CV_OBSERVATION_TOPIC)
                async for message in client.messages:
                    consumer.process(message.payload)

        except aiomqtt.MqttError as exc:
            log.warning("MQTT connection lost: %s — reconnecting in %.1fs", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, config.MQTT_RECONNECT_MAX_BACKOFF_S)
        except asyncio.CancelledError:
            log.info("MQTT subscriber stopped")
            raise


async def _run_publish_loop(
    window: ObservationWindow, publisher: SignalPublisher
) -> None:
    """
    ICD-3 outbound publish loop. Connects to the broker, then on each interval:
    - builds a signal from the current window state
    - publishes it if non-None (window non-empty)

    Uses a separate MQTT client from the subscriber to keep concerns independent
    and avoid blocking the inbound message loop during publish.
    """
    interval = 1.0 / config.PUBLISH_HZ
    backoff = config.MQTT_RECONNECT_INITIAL_BACKOFF_S
    while True:
        try:
            async with aiomqtt.Client(
                hostname=config.MQTT_BROKER_HOST,
                port=config.MQTT_BROKER_PORT,
                identifier=f"{config.MQTT_CLIENT_ID}-pub",
            ) as client:
                backoff = config.MQTT_RECONNECT_INITIAL_BACKOFF_S
                log.info(
                    "publish loop connected: publish_hz=%.1f topic=%s",
                    config.PUBLISH_HZ,
                    config.MQTT_AUDIENCE_STATE_TOPIC,
                )
                while True:
                    await asyncio.sleep(interval)
                    signal = publisher.build_signal(window)
                    if signal is not None:
                        await publisher.publish(client, signal)

        except aiomqtt.MqttError as exc:
            log.warning(
                "publish loop MQTT error: %s — reconnecting in %.1fs", exc, backoff
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, config.MQTT_RECONNECT_MAX_BACKOFF_S)
        except asyncio.CancelledError:
            log.info("publish loop stopped")
            raise


async def run() -> None:
    log.info("audience-state starting")

    window = ObservationWindow(
        window_ms=config.WINDOW_MS,
        min_stability_observations=config.MIN_STABILITY_OBSERVATIONS,
        confidence_freeze_threshold=config.CONFIDENCE_FREEZE_THRESHOLD,
    )
    consumer = ObservationConsumer(window)
    publisher = SignalPublisher()

    # Health server
    is_ready: list = [False]
    health_app = await make_health_app(consumer, publisher, is_ready)
    runner = web.AppRunner(health_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.HEALTH_PORT)
    await site.start()
    log.info("health server listening port=%d", config.HEALTH_PORT)

    is_ready[0] = True
    log.info("audience-state ready")

    try:
        await asyncio.gather(
            _run_mqtt_subscribe(consumer),
            _run_publish_loop(window, publisher),
        )
    except asyncio.CancelledError:
        log.info("audience-state shutting down")
    finally:
        await runner.cleanup()
        log.info("audience-state stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
