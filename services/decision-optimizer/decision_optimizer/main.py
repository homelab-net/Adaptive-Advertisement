"""
Decision-optimizer service entry point.

Startup sequence
----------------
1. Load policy rules from RULES_FILE — fail fast if missing or malformed.
2. Start WebSocket server (player gateway).
3. Start health server.
4. Mark ready.
5. Run MQTT subscriber and decision loop concurrently.

The MQTT subscriber calls signal_consumer.process() for each message.
The decision loop reads from signal_consumer.latest_signal on each 1 Hz tick.
Both run as asyncio tasks and are supervised by a simple gather with
error propagation — if either crashes, the process exits and the supervisor
(ICD-8) restarts it.
"""
import asyncio
import logging
import sys
from typing import Optional

import aiomqtt
from aiohttp import web

from adaptive_shared.log_config import setup_logging

from . import config
from .policy import load_policy
from .signal_consumer import SignalConsumer
from .player_gateway import PlayerGateway
from .decision_loop import DecisionLoop
from .health import make_health_app

setup_logging("decision-optimizer", config.LOG_LEVEL)
log = logging.getLogger(__name__)


async def _run_mqtt(consumer: SignalConsumer) -> None:
    """
    MQTT subscriber loop — connects to Mosquitto and feeds signals to the consumer.
    Reconnects automatically with exponential backoff on connection loss.
    """
    backoff = config.MQTT_RECONNECT_INITIAL_BACKOFF_S
    while True:
        try:
            log.info(
                "connecting to MQTT broker %s:%d topic=%s",
                config.MQTT_BROKER_HOST,
                config.MQTT_BROKER_PORT,
                config.MQTT_AUDIENCE_STATE_TOPIC,
            )
            async with aiomqtt.Client(
                hostname=config.MQTT_BROKER_HOST,
                port=config.MQTT_BROKER_PORT,
                identifier=config.MQTT_CLIENT_ID,
            ) as client:
                backoff = config.MQTT_RECONNECT_INITIAL_BACKOFF_S
                await client.subscribe(config.MQTT_AUDIENCE_STATE_TOPIC)
                log.info("MQTT subscribed: %s", config.MQTT_AUDIENCE_STATE_TOPIC)
                async for message in client.messages:
                    consumer.process(message.payload)

        except aiomqtt.MqttError as exc:
            log.warning(
                "MQTT connection lost: %s — reconnecting in %.1fs", exc, backoff
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, config.MQTT_RECONNECT_MAX_BACKOFF_S)

        except asyncio.CancelledError:
            log.info("MQTT subscriber stopped")
            raise


async def run() -> None:
    log.info("decision-optimizer starting")

    # Step 1: load policy
    try:
        policy = load_policy(config.RULES_FILE)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        log.critical("STARTUP ABORTED — failed to load rules: %s", exc)
        sys.exit(1)

    # Step 2: instantiate components
    consumer = SignalConsumer()
    gateway = PlayerGateway()
    loop = DecisionLoop(policy=policy, consumer=consumer, gateway=gateway)

    # Step 3: start WebSocket server
    await gateway.start()

    # Step 4: health server
    is_ready: list = [False]
    health_app = await make_health_app(loop, consumer, gateway, is_ready)
    runner = web.AppRunner(health_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.HEALTH_PORT)
    await site.start()
    log.info("health server listening port=%d", config.HEALTH_PORT)

    is_ready[0] = True
    log.info("decision-optimizer ready")

    # Step 5: run MQTT subscriber and decision loop concurrently
    try:
        await asyncio.gather(
            _run_mqtt(consumer),
            loop.run(),
        )
    except asyncio.CancelledError:
        log.info("decision-optimizer shutting down")
    finally:
        await gateway.stop()
        await runner.cleanup()
        log.info("decision-optimizer stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
