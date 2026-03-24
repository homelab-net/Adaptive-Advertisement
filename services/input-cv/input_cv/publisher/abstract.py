from __future__ import annotations

from abc import ABC, abstractmethod


class Publisher(ABC):
    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the message broker."""

    @abstractmethod
    def publish(self, topic: str, payload: bytes) -> None:
        """
        Publish a payload to a topic.

        Args:
            topic: fully-qualified MQTT topic string.
            payload: serialized message bytes (JSON UTF-8).
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close the broker connection."""
