"""Tests for handling the UDP events the device sends."""

from __future__ import annotations

import asyncio
import gc
import logging
import unittest
from typing import Any, cast
from unittest.mock import AsyncMock

from aiomusiccast.exceptions import MusicCastConnectionException
from aiomusiccast.musiccast_data import MusicCastZoneData
from aiomusiccast.musiccast_device import MusicCastDevice
from aiomusiccast.pyamaha import MusicCastUdpProtocol


class HandleTest(unittest.IsolatedAsyncioTestCase):
    async def test_unreadable_event_fetches_everything_and_notifies(self) -> None:
        device = MusicCastDevice("192.0.2.1", cast("Any", None))
        fetch = AsyncMock()
        device.fetch = fetch  # type: ignore[method-assign]
        calls: list[bool] = []
        device.register_callback(lambda: calls.append(True))

        await device.handle(None)

        fetch.assert_awaited_once()
        assert calls == [True]

    async def test_zone_power_is_the_reported_string(self) -> None:
        device = MusicCastDevice("192.0.2.1", cast("Any", None))
        device.data.zones["main"] = MusicCastZoneData()

        await device.handle({"main": {"power": "standby"}})

        assert device.data.zones["main"].power == "standby"


class UdpProtocolTest(unittest.IsolatedAsyncioTestCase):
    async def _receive(self, handler: Any, data: bytes = b'{"main": {}}') -> MusicCastUdpProtocol:
        protocol = MusicCastUdpProtocol(handler)
        protocol.datagram_received(data, ("192.0.2.1", 41100))
        for _ in range(3):
            await asyncio.sleep(0)
        return protocol

    async def test_handler_task_is_kept_until_done(self) -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        done: list[bool] = []

        async def handler(_message: Any) -> None:
            started.set()
            await release.wait()
            done.append(True)

        protocol = await self._receive(handler)
        await started.wait()
        gc.collect()
        assert len(protocol._tasks) == 1
        release.set()
        for _ in range(3):
            await asyncio.sleep(0)
        assert done == [True]
        assert not protocol._tasks

    async def test_unreadable_message_is_passed_as_none(self) -> None:
        handler = AsyncMock()

        await self._receive(handler, b"not json")

        handler.assert_awaited_once_with(None)

    async def test_connection_errors_are_logged_quietly(self) -> None:
        handler = AsyncMock(side_effect=MusicCastConnectionException())

        with self.assertLogs("aiomusiccast.pyamaha", logging.DEBUG) as logs:
            await self._receive(handler)

        assert [r.levelno for r in logs.records] == [logging.DEBUG]

    async def test_other_errors_are_logged_with_traceback(self) -> None:
        handler = AsyncMock(side_effect=KeyError("zone"))

        with self.assertLogs("aiomusiccast.pyamaha", logging.ERROR) as logs:
            await self._receive(handler)

        assert logs.records[0].exc_info is not None
