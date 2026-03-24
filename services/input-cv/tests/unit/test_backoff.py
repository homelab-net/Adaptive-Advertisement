"""Backoff calculator tests."""
from __future__ import annotations

import pytest

from input_cv.recovery.backoff import next_backoff_seconds


def test_attempt_zero_returns_initial():
    result = next_backoff_seconds(attempt=0, initial_ms=500, max_ms=10000)
    assert result == pytest.approx(0.5)


def test_attempt_one_doubles():
    result = next_backoff_seconds(attempt=1, initial_ms=500, max_ms=10000)
    assert result == pytest.approx(1.0)


def test_attempt_two_doubles_again():
    result = next_backoff_seconds(attempt=2, initial_ms=500, max_ms=10000)
    assert result == pytest.approx(2.0)


def test_clamps_at_max():
    result = next_backoff_seconds(attempt=100, initial_ms=500, max_ms=10000)
    assert result == pytest.approx(10.0)


def test_max_equals_initial_always_returns_initial():
    for attempt in range(5):
        result = next_backoff_seconds(attempt=attempt, initial_ms=1000, max_ms=1000)
        assert result == pytest.approx(1.0)


def test_returns_float():
    result = next_backoff_seconds(attempt=0, initial_ms=500, max_ms=10000)
    assert isinstance(result, float)
