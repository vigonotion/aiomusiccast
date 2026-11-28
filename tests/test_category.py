"""Tests for the device category read from getDeviceInfo."""

from __future__ import annotations

import asyncio
import unittest
from typing import Any, cast
from unittest.mock import AsyncMock

from aiomusiccast.musiccast_data import Category, MusicCastData
from aiomusiccast.musiccast_device import MusicCastDevice


class _StopFetch(Exception):
    """Ends fetch() after getNetworkStatus and getDeviceInfo."""


class CategoryTest(unittest.TestCase):
    def _fetch_category(self, device_info: dict[str, Any]) -> Category:
        device = MusicCastDevice("192.0.2.1", cast("Any", object()))
        device.device.request_json = AsyncMock(side_effect=[{}, device_info, _StopFetch()])  # type: ignore[method-assign]
        with self.assertRaises(_StopFetch):
            asyncio.run(device.fetch())
        return device.data.category

    def test_known_codes(self) -> None:
        self.assertIs(Category(1), Category.AV_RECEIVER)
        self.assertIs(Category(2), Category.SOUNDBAR)
        self.assertIs(Category(6), Category.DESKTOP_AUDIO_1)

    def test_unknown_code_falls_back_to_unknown(self) -> None:
        with self.assertLogs("aiomusiccast.musiccast_data", level="WARNING") as logs:
            self.assertIs(Category(99), Category.UNKNOWN)
        self.assertIn("99", logs.output[0])

    def test_default_is_unknown(self) -> None:
        self.assertIs(MusicCastData().category, Category.UNKNOWN)

    def test_fetch_reads_category_code(self) -> None:
        self.assertIs(self._fetch_category({"model_name": "RX-A4A", "category_code": 1}), Category.AV_RECEIVER)

    def test_fetch_without_category_code(self) -> None:
        self.assertIs(self._fetch_category({"model_name": "R-N402D"}), Category.UNKNOWN)

    def test_fetch_with_unknown_category_code(self) -> None:
        with self.assertLogs("aiomusiccast.musiccast_data", level="WARNING"):
            self.assertIs(self._fetch_category({"model_name": "Future", "category_code": 42}), Category.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
