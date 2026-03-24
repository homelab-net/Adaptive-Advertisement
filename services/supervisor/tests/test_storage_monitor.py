"""Tests for storage_monitor.check_storage()."""
import pytest
from unittest.mock import patch
from collections import namedtuple

from supervisor.storage_monitor import check_storage, StorageStatus

_Usage = namedtuple("_Usage", ["total", "used", "free"])


def _mock_usage(used_pct: float):
    total = 1_000_000_000  # 1 GB
    used = int(total * used_pct / 100)
    return _Usage(total=total, used=used, free=total - used)


def test_ok_below_warn():
    with patch("shutil.disk_usage", return_value=_mock_usage(50.0)):
        status = check_storage("/data")
    assert not status.is_warning
    assert not status.is_critical
    assert abs(status.used_pct - 50.0) < 0.1


def test_warning_at_80():
    with patch("shutil.disk_usage", return_value=_mock_usage(80.0)):
        status = check_storage("/data")
    assert status.is_warning
    assert not status.is_critical


def test_critical_at_90():
    with patch("shutil.disk_usage", return_value=_mock_usage(90.0)):
        status = check_storage("/data")
    assert status.is_warning
    assert status.is_critical


def test_critical_at_95():
    with patch("shutil.disk_usage", return_value=_mock_usage(95.0)):
        status = check_storage("/data")
    assert status.is_critical


def test_oserror_returns_zero_status():
    with patch("shutil.disk_usage", side_effect=OSError("no such file")):
        status = check_storage("/nonexistent")
    assert status.used_pct == 0.0
    assert status.total_bytes == 0


def test_custom_thresholds():
    with patch("shutil.disk_usage", return_value=_mock_usage(70.0)):
        status = check_storage("/data", warn_pct=65.0, critical_pct=85.0)
    assert status.is_warning  # 70 >= 65
    assert not status.is_critical  # 70 < 85


def test_free_gb_property():
    # _mock_usage uses total=1_000_000_000 (1 GB); 75% used → 25% free = 0.25 GB
    with patch("shutil.disk_usage", return_value=_mock_usage(75.0)):
        status = check_storage("/data")
    assert abs(status.free_gb - 0.25) < 0.001


def test_total_gb_property():
    with patch("shutil.disk_usage", return_value=_mock_usage(0.0)):
        status = check_storage("/data")
    # total is exactly 1_000_000_000 bytes = 1.0 GB
    assert abs(status.total_gb - 1.0) < 0.001
