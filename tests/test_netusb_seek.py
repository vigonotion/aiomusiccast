"""Tests for seeking in the track playing on a netusb input."""

from __future__ import annotations

import json
import unittest
from typing import Any, cast

from aiomusiccast.exceptions import MusicCastException, MusicCastUnsupportedException
from aiomusiccast.musiccast_device import MusicCastDevice
from aiomusiccast.pyamaha import NetUSB

PREFIX = "http://{host}/YamahaExtendedControl/v1/"

# netusb/getPlayInfo as the devices reported it (track names replaced).
TIDAL_WX_021 = {"input": "tidal", "playback": "play", "play_time": 21, "total_time": 140, "attribute": 3439337887}
TIDAL_RX_A8A = {"input": "tidal", "playback": "play", "play_time": 0, "total_time": 323, "attribute": 3439337887}
SERVER_WX_021 = {"input": "server", "playback": "play", "play_time": 63, "total_time": 0, "attribute": 2231370239}
TIDAL_CD_NT670D = {"input": "tidal", "playback": "play", "play_time": 54, "total_time": 262, "attribute": 218112415}


class FakeApi:
    def __init__(self, play_info: dict[str, Any]) -> None:
        self.play_info = {"track": "Track", "artist": "Artist", "album": "Album", **play_info}
        self.commands: list[str] = []

    async def request_json(self, url: str) -> dict[str, Any]:
        assert url.endswith("netusb/getPlayInfo")
        return json.loads(json.dumps(self.play_info))

    async def request(self, url: str) -> None:
        self.commands.append(url.removeprefix(PREFIX))


async def _device(play_info: dict[str, Any]) -> tuple[MusicCastDevice, FakeApi]:
    device = MusicCastDevice("192.0.2.1", cast("Any", None))
    api = FakeApi(play_info)
    device.device.request_json = api.request_json  # type: ignore[method-assign]
    device.device.request = api.request  # type: ignore[method-assign]
    await device._fetch_netusb()
    return device, api


async def _assert_raises(error: type[Exception], call: Any) -> None:
    try:
        await call()
    except error:
        return
    raise AssertionError(f"{error.__name__} not raised")


class SeekableTest(unittest.IsolatedAsyncioTestCase):
    async def test_seekable_sources(self) -> None:
        for play_info in (TIDAL_WX_021, TIDAL_RX_A8A, SERVER_WX_021):
            device, _ = await _device(play_info)
            assert device.netusb_seekable, play_info

    async def test_not_seekable(self) -> None:
        device, _ = await _device(TIDAL_CD_NT670D)

        assert not device.netusb_seekable

    async def test_unknown_before_the_first_fetch(self) -> None:
        assert not MusicCastDevice("192.0.2.1", cast("Any", None)).netusb_seekable


class SeekTest(unittest.IsolatedAsyncioTestCase):
    async def test_seek(self) -> None:
        device, api = await _device(TIDAL_WX_021)

        await device.netusb_seek(51.4)

        assert api.commands == ["netusb/setPlayPosition?position=51"]
        assert device.data.netusb_play_time == 51

    async def test_seek_without_known_duration(self) -> None:
        # Media servers: the device reports total time 0 but seeks.
        device, api = await _device(SERVER_WX_021)

        await device.netusb_seek(200)

        assert api.commands == ["netusb/setPlayPosition?position=200"]

    async def test_beyond_the_track(self) -> None:
        device, api = await _device(TIDAL_WX_021)

        await _assert_raises(MusicCastException, lambda: device.netusb_seek(141))
        assert not api.commands

    async def test_track_does_not_allow_it(self) -> None:
        device, api = await _device(TIDAL_CD_NT670D)

        await _assert_raises(MusicCastUnsupportedException, lambda: device.netusb_seek(100))
        assert not api.commands

    def test_request(self) -> None:
        assert NetUSB.set_play_position(75.9).endswith("netusb/setPlayPosition?position=75")
