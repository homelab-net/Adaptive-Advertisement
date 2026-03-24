"""
MQTT v5.0 publisher for ICD-2 CvObservation messages.

Topic pattern: cv/v1/observations/{tenant_id}/{site_id}/{camera_id}
QoS: 1 (at-least-once; consumers must deduplicate by message_id)
Protocol: MQTTv5

Credentials and broker config are injected via environment variables —
never baked into the image or the camera source config file.
"""
from __future__ import annotations

import logging

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

from .abstract import Publisher

logger = logging.getLogger(__name__)

_QOS_OBSERVATIONS = 1


class MqttPublisher(Publisher):
    def __init__(
        self,
        host: str,
        port: int,
        client_id: str,
        username: str | None = None,
        password: str | None = None,
        tls: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv5,
        )
        if username:
            self._client.username_pw_set(username, password)
        if tls:
            self._client.tls_set()
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc, properties=None) -> None:
        logger.info("input-cv MQTT: connected to %s:%d (rc=%s)", self._host, self._port, rc)

    def _on_disconnect(self, client, userdata, rc, properties=None) -> None:
        if rc != 0:
            logger.warning("input-cv MQTT: unexpected disconnect (rc=%d)", rc)

    def connect(self) -> None:
        self._client.connect(self._host, self._port)
        self._client.loop_start()

    def publish(self, topic: str, payload: bytes) -> None:
        props = Properties(PacketTypes.PUBLISH)
        props.ContentType = "application/json"
        result = self._client.publish(
            topic,
            payload=payload,
            qos=_QOS_OBSERVATIONS,
            retain=False,
            properties=props,
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error("input-cv MQTT: publish failed on topic %s (rc=%d)", topic, result.rc)

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
