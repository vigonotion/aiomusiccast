"""Tests for the CD player."""

from __future__ import annotations

import json
import unittest
from typing import Any, cast

from aiomusiccast.exceptions import MusicCastException, MusicCastUnsupportedException
from aiomusiccast.features import DeviceFeature
from aiomusiccast.musiccast_device import MusicCastDevice
from aiomusiccast.pyamaha import CD

PREFIX = "http://{host}/YamahaExtendedControl/v1/"

# Responses of a CD-NT670D, trimmed; cd/getPlayInfo as reported with a disc.
RESPONSES: dict[str, Any] = {
    "system/getFeatures": {
        "system": {
            "func_list": ["wired_lan", "wireless_lan"],
            "input_list": [
                {"id": "net_radio", "distribution_enable": True, "play_info_type": "netusb"},
                {"id": "cd", "distribution_enable": True, "play_info_type": "cd"},
            ],
        },
        "zone": [
            {
                "id": "main",
                "func_list": ["power", "volume", "mute"],
                "range_step": [{"id": "volume", "min": 0, "max": 63, "step": 1}],
                "input_list": ["net_radio", "cd"],
            }
        ],
    },
    "main/getStatus": {"power": "on", "volume": 14, "mute": False, "input": "cd"},
    "cd/getPlayInfo": {
        "device_status": "ready",
        "playback": "play",
        "repeat": "off",
        "shuffle": "off",
        "play_time": 42,
        "total_time": 200,
        "disc_time": 3021,
        "track_number": 3,
        "total_tracks": 12,
        "artist": "Band",
        "album": "Album",
        "track": "",
        "repeat_available": ["off", "one", "all"],
        "shuffle_available": ["off", "on"],
    },
}


class FakeApi:
    """Answers GET requests from RESPONSES and records commands."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = json.loads(json.dumps(responses))
        self.reads: list[str] = []
        self.commands: list[str] = []

    async def request_json(self, url: str) -> dict[str, Any]:
        path = url.removeprefix(PREFIX).split("?")[0]
        self.reads.append(path)
        return json.loads(json.dumps(self.responses.get(path, {"response_code": 0})))

    async def request(self, url: str) -> None:
        self.commands.append(url.removeprefix(PREFIX))


async def _device(responses: dict[str, Any] = RESPONSES) -> tuple[MusicCastDevice, FakeApi]:
    device = MusicCastDevice("192.0.2.1", cast("Any", None))
    api = FakeApi(responses)
    device.device.request_json = api.request_json  # type: ignore[method-assign]
    device.device.request = api.request  # type: ignore[method-assign]
    await device.fetch()
    return device, api


async def _assert_raises(error: type[Exception], call: Any) -> None:
    # The feature check of the device raises before returning a coroutine.
    try:
        await call()
    except error:
        return
    raise AssertionError(f"{error.__name__} not raised")


class CdDataTest(unittest.IsolatedAsyncioTestCase):
    async def test_detected_from_the_input_list(self) -> None:
        device, _ = await _device()

        assert DeviceFeature.CD in device.features

    async def test_play_info(self) -> None:
        device, _ = await _device()
        data = device.data

        assert (data.cd_device_status, data.cd_playback) == ("ready", "play")
        assert (data.cd_track_number, data.cd_total_tracks) == (3, 12)
        assert (data.cd_play_time, data.cd_total_time, data.cd_disc_time) == (42, 200, 3021)
        assert (data.cd_artist, data.cd_album, data.cd_track) == ("Band", "Album", None)
        assert data.cd_repeat_available == ["off", "one", "all"]
        assert data.cd_play_time_updated is not None

    async def test_play_info_event(self) -> None:
        device, api = await _device()
        api.responses["cd/getPlayInfo"]["playback"] = "pause"

        await device.handle({"cd": {"play_info_updated": True}})

        assert device.data.cd_playback == "pause"

    async def test_play_time_event(self) -> None:
        device, api = await _device()
        api.reads.clear()

        await device.handle({"cd": {"play_time": 60}})

        assert device.data.cd_play_time == 60
        assert not api.reads

    async def test_device_without_cd(self) -> None:
        responses = json.loads(json.dumps(RESPONSES))
        responses["system/getFeatures"]["system"]["input_list"].pop()
        device, api = await _device(responses)

        assert DeviceFeature.CD not in device.features
        assert "cd/getPlayInfo" not in api.reads
        await device.handle({"cd": {"play_info_updated": True}})
        assert "cd/getPlayInfo" not in api.reads
        await _assert_raises(MusicCastUnsupportedException, device.cd_play)


class CdCommandsTest(unittest.IsolatedAsyncioTestCase):
    async def test_commands(self) -> None:
        device, api = await _device()

        await device.cd_play()
        await device.cd_pause()
        await device.cd_stop()
        await device.cd_previous_track()
        await device.cd_next_track()
        await device.cd_select_track(12)
        await device.cd_toggle_tray()
        await device.cd_toggle_repeat()
        await device.cd_toggle_shuffle()

        assert api.commands == [
            "cd/setPlayback?playback=play",
            "cd/setPlayback?playback=pause",
            "cd/setPlayback?playback=stop",
            "cd/setPlayback?playback=previous",
            "cd/setPlayback?playback=next",
            "cd/setPlayback?playback=track_select&num=12",
            "cd/toggleTray",
            "cd/toggleRepeat",
            "cd/toggleShuffle",
        ]

    async def test_track_not_on_disc(self) -> None:
        device, api = await _device()

        await _assert_raises(MusicCastException, lambda: device.cd_select_track(13))
        assert not api.commands


class CdRequestTest(unittest.TestCase):
    def test_set_playback_accepts_cd_commands(self) -> None:
        # Used to check against the NetUSB commands, which have no track_select.
        assert CD.set_playback("track_select", 2).endswith("cd/setPlayback?playback=track_select&num=2")
        # Without a track, no "num=None" in the URL.
        assert CD.set_playback("next").endswith("cd/setPlayback?playback=next")
