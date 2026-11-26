"""Tests for the play queue, recent items, playlists and presets."""

from __future__ import annotations

import json
import unittest
from typing import Any, cast

from aiomusiccast.exceptions import MusicCastUnsupportedException
from aiomusiccast.features import DeviceFeature
from aiomusiccast.musiccast_data import MusicCastTunerPreset
from aiomusiccast.musiccast_device import MusicCastDevice
from aiomusiccast.pyamaha import Tuner

PREFIX = "http://{host}/YamahaExtendedControl/v1/"


def _queue_entry(n: int) -> dict[str, Any]:
    return {"input": "server", "text": f"Station {n}", "thumbnail": f"https://192.0.2.9/{n}.jpg", "attribute": 17}


# As a CD-NT670D answers, trimmed and with other names.
RESPONSES: dict[str, Any] = {
    "system/getFeatures": {
        "system": {"func_list": ["wired_lan"], "input_list": []},
        "zone": [{"id": "main", "func_list": ["power"], "range_step": [], "input_list": []}],
        "netusb": {
            "func_list": ["recent_info", "play_queue", "mc_playlist", "streaming_service_use"],
            "play_queue": {"size": 200},
            "mc_playlist": {"size": 200, "num": 5},
            "recent_info": {"num": 40},
        },
        "tuner": {"func_list": ["fm", "rds", "dab"], "preset": {"type": "separate", "num": 30}},
    },
    "main/getStatus": {"power": "on", "input": "server"},
    # 10 entries: two pages
    "netusb/getPlayQueue?index=0": {
        "type": "system",
        "max_line": 10,
        "playing_index": 9,
        "index": 0,
        "track_info": [_queue_entry(n) for n in range(8)],
    },
    "netusb/getPlayQueue?index=8": {
        "type": "system",
        "max_line": 10,
        "playing_index": 9,
        "index": 8,
        "track_info": [_queue_entry(n) for n in range(8, 10)],
    },
    "netusb/getRecentInfo": {
        "recent_info": [
            {"input": "server", "text": "Station 1", "albumart_url": "https://192.0.2.9/1.jpg"},
            {"input": "unknown", "text": "", "albumart_url": ""},
            {"input": "net_radio", "text": "Station 2", "albumart_url": "/YamahaRemoteControl/AlbumART/AlbumART.jpg"},
        ]
    },
    "netusb/getMcPlaylistName": {"name_list": ["Playlist 1", "Playlist 2", "Playlist 3", "Playlist 4", "Playlist 5"]},
    "netusb/getMcPlaylist?bank=2&index=0": {"bank": 2, "max_line": 1, "index": 0, "track_info": [_queue_entry(1)]},
    "netusb/getMcPlaylist?bank=1&index=0": {"bank": 1, "max_line": 0, "index": 0, "track_info": []},
    "tuner/getPresetInfo?band=fm": {
        "preset_info": [
            {"band": "fm", "number": 89400, "hd_program": 0, "text": " RADIO 1 "},
            {"band": "unknown", "number": 0, "hd_program": 0, "text": ""},
            {"band": "fm", "number": 96000, "hd_program": 0, "text": ""},
        ]
    },
}


class FakeApi:
    """Answers GET requests from RESPONSES and records commands."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = json.loads(json.dumps(responses))
        self.commands: list[str] = []

    async def request_json(self, url: str) -> dict[str, Any]:
        path = url.removeprefix(PREFIX)
        if path not in self.responses:
            path = path.split("?")[0]
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


class FeaturesTest(unittest.IsolatedAsyncioTestCase):
    async def test_detected_from_the_netusb_func_list(self) -> None:
        device, _ = await _device()

        for feature in (DeviceFeature.RECENT_INFO, DeviceFeature.PLAY_QUEUE, DeviceFeature.MC_PLAYLIST):
            assert feature in device.features

    async def test_device_without_lists(self) -> None:
        responses = json.loads(json.dumps(RESPONSES))
        responses["system/getFeatures"]["netusb"]["func_list"] = []
        device, _ = await _device(responses)

        await _assert_raises(MusicCastUnsupportedException, device.get_play_queue)
        await _assert_raises(MusicCastUnsupportedException, device.get_recent_items)
        await _assert_raises(MusicCastUnsupportedException, device.get_mc_playlist_names)


class PlayQueueTest(unittest.IsolatedAsyncioTestCase):
    async def test_all_pages(self) -> None:
        device, _ = await _device()

        queue = await device.get_play_queue()

        assert [item.text for item in queue.items] == [f"Station {n}" for n in range(10)]
        assert queue.items[9].index == 9
        assert queue.items[0].thumbnail == "https://192.0.2.9/0.jpg"
        assert queue.items[0].raw["attribute"] == 17
        assert queue.playing_index == 9

    async def test_empty(self) -> None:
        responses = json.loads(json.dumps(RESPONSES))
        responses["netusb/getPlayQueue?index=0"] = {"max_line": 0, "playing_index": -1, "index": 0, "track_info": []}
        device, _ = await _device(responses)

        queue = await device.get_play_queue()

        assert (queue.items, queue.playing_index) == ([], None)

    async def test_commands(self) -> None:
        device, api = await _device()

        await device.play_queue_item("main", 2)
        await device.remove_play_queue_item("main", 3)
        await device.clear_play_queue()

        assert api.commands == [
            "netusb/managePlayQueue?type=play&index=2&zone=main",
            "netusb/managePlayQueue?type=remove&index=3&zone=main",
            "netusb/clearPlayQueue",
        ]


class RecentTest(unittest.IsolatedAsyncioTestCase):
    async def test_unused_slots_are_left_out(self) -> None:
        device, _ = await _device()

        items = await device.get_recent_items()

        assert [(item.index, item.text, item.input) for item in items] == [
            (0, "Station 1", "server"),
            (2, "Station 2", "net_radio"),
        ]
        assert items[0].thumbnail == "https://192.0.2.9/1.jpg"

    async def test_recall_counts_from_one_on_the_device(self) -> None:
        device, api = await _device()

        await device.recall_recent_item("main", 2)

        assert api.commands == ["netusb/recallRecentItem?zone=main&num=3"]


class PlaylistTest(unittest.IsolatedAsyncioTestCase):
    async def test_names_and_tracks(self) -> None:
        device, _ = await _device()

        assert (await device.get_mc_playlist_names())[1] == "Playlist 2"
        assert [item.text for item in await device.get_mc_playlist(2)] == ["Station 1"]
        assert await device.get_mc_playlist(1) == []

    async def test_play(self) -> None:
        device, api = await _device()

        await device.play_mc_playlist("main", 2)
        await device.play_mc_playlist("main", 2, 4)

        assert api.commands == [
            "netusb/manageMcPlaylist?bank=2&type=play&index=0&zone=main",
            "netusb/manageMcPlaylist?bank=2&type=play&index=4&zone=main",
        ]


class TunerPresetsTest(unittest.IsolatedAsyncioTestCase):
    async def test_separate_bands(self) -> None:
        device, _ = await _device()

        assert device.tuner_preset_bands == ["fm", "dab"]
        assert await device.get_tuner_presets("fm") == [
            MusicCastTunerPreset(num=1, band="fm", number=89400, text="RADIO 1"),
            MusicCastTunerPreset(num=3, band="fm", number=96000, text=""),
        ]

    async def test_common_presets(self) -> None:
        responses = json.loads(json.dumps(RESPONSES))
        responses["system/getFeatures"]["tuner"]["preset"]["type"] = "common"
        device, _ = await _device(responses)

        assert device.tuner_preset_bands == ["common"]

    async def test_recall(self) -> None:
        device, api = await _device()

        await device.recall_tuner_preset("main", "fm", 3)

        assert api.commands == ["tuner/recallPreset?zone=main&band=fm&num=3"]
        await _assert_raises(MusicCastUnsupportedException, lambda: device.recall_tuner_preset("main", "am", 1))

    def test_recall_preset_accepts_bands(self) -> None:
        # Used to accept only "common" and "separate", which are preset types, not bands.
        assert Tuner.recall_preset("main", "dab", 2).endswith("tuner/recallPreset?zone=main&band=dab&num=2")
