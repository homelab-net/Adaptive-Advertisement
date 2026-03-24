"""
NullPublisher: test stub. No network calls.

Accumulates (topic, payload) tuples in self.published for assertion.
"""
from __future__ import annotations

from .abstract import Publisher


class NullPublisher(Publisher):
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def publish(self, topic: str, payload: bytes) -> None:
        self.published.append((topic, payload))

    def disconnect(self) -> None:
        self.connected = False
