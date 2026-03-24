"""Publisher tests — NullPublisher behavior and topic format."""
from __future__ import annotations

import json

import pytest

from input_cv.publisher.null_publisher import NullPublisher


@pytest.fixture
def pub() -> NullPublisher:
    p = NullPublisher()
    p.connect()
    return p


def test_connect_sets_connected(pub):
    assert pub.connected is True


def test_publish_accumulates(pub):
    pub.publish("cv/v1/observations/t1/s1/cam-01", b'{"msg": 1}')
    pub.publish("cv/v1/observations/t1/s1/cam-01", b'{"msg": 2}')
    assert len(pub.published) == 2


def test_topic_format(pub):
    tenant, site, camera = "tenant-a", "site-b", "cam-main-01"
    topic = f"cv/v1/observations/{tenant}/{site}/{camera}"
    pub.publish(topic, b"{}")
    recorded_topic, _ = pub.published[0]
    assert recorded_topic == "cv/v1/observations/tenant-a/site-b/cam-main-01"


def test_payload_is_bytes(pub):
    pub.publish("test/topic", b'{"key": "value"}')
    _, payload = pub.published[0]
    assert isinstance(payload, bytes)


def test_published_payload_is_valid_json(pub):
    data = {"schema_version": "1.0.0", "message_type": "cv_observation"}
    pub.publish("test/topic", json.dumps(data).encode())
    _, payload = pub.published[0]
    parsed = json.loads(payload)
    assert parsed["message_type"] == "cv_observation"


def test_disconnect_clears_connected(pub):
    pub.disconnect()
    assert pub.connected is False
