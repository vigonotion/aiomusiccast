"""Tests for the device category read from getDeviceInfo."""

from __future__ import annotations

import asyncio
import contextlib
import unittest
from typing import Any, cast
from unittest.mock import AsyncMock

from aiomusiccast.musiccast_data import Category, MusicCastData
from aiomusiccast.musiccast_device import MusicCastDevice


class _StopFetch(Exception):
    """Ends fetch() after getNetworkStatus and getDeviceInfo."""


def _fetch_category(device_info: dict[str, Any]) -> Category:
    device = MusicCastDevice("192.0.2.1", cast("Any", object()))
    request_json = AsyncMock(side_effect=[{}, device_info, _StopFetch()])
    device.device.request_json = request_json  # type: ignore[method-assign]
    with contextlib.suppress(_StopFetch):
        asyncio.run(device.fetch())
    assert request_json.await_count == 3
    return device.data.category


class CategoryTest(unittest.TestCase):
    def test_known_codes(self) -> None:
        assert Category(1) is Category.AV_RECEIVER
        assert Category(2) is Category.SOUNDBAR
        assert Category(6) is Category.DESKTOP_AUDIO_1

    def test_unknown_code_falls_back_to_unknown(self) -> None:
        with self.assertLogs("aiomusiccast.musiccast_data", level="WARNING") as logs:
            assert Category(99) is Category.UNKNOWN
        assert "99" in logs.output[0]

    def test_default_is_unknown(self) -> None:
        assert MusicCastData().category is Category.UNKNOWN

    def test_fetch_reads_category_code(self) -> None:
        assert _fetch_category({"model_name": "RX-A4A", "category_code": 1}) is Category.AV_RECEIVER

    def test_fetch_without_category_code(self) -> None:
        assert _fetch_category({"model_name": "R-N402D"}) is Category.UNKNOWN

    def test_fetch_with_unknown_category_code(self) -> None:
        with self.assertLogs("aiomusiccast.musiccast_data", level="WARNING"):
            assert _fetch_category({"model_name": "Future", "category_code": 42}) is Category.UNKNOWN


if __name__ == "__main__":
    unittest.main()
