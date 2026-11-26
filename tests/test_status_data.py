"""Tests for the status data: signal info, network status, tuner, web page."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, cast

from aiomusiccast.musiccast_data import MusicCastSignalInfo
from aiomusiccast.musiccast_device import MusicCastDevice

# Responses of a CD-NT670D (Wi-Fi, tuner) and an RX-A8A (wired), trimmed
# and anonymised.
DEVICES = json.loads((Path(__file__).parent / "fixtures" / "status_devices.json").read_text())
PREFIX = "http://{host}/YamahaExtendedControl/v1/"


class FakeApi:
    """Answers GET requests from the fixture and counts them."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.requests: list[str] = []

    async def request_json(self, url: str) -> dict[str, Any]:
        path = url.removeprefix(PREFIX).split("?")[0]
        self.requests.append(path)
        return json.loads(json.dumps(self.responses.get(path, {"response_code": 0})))


async def _device(name: str) -> tuple[MusicCastDevice, FakeApi]:
    device = MusicCastDevice("192.0.2.1", cast("Any", None))
    api = FakeApi(json.loads(json.dumps(DEVICES[name])))  # a copy: tests change it
    device.device.request_json = api.request_json  # type: ignore[method-assign]
    await device.fetch()
    return device, api


class SignalInfoTest(unittest.IsolatedAsyncioTestCase):
    async def test_signal_info(self) -> None:
        device, _ = await _device("cd_nt670d")

        assert device.data.zones["main"].signal_info == MusicCastSignalInfo(
            format="MP3", sample_rate="44.1 kHz", bit_depth=None, bitrate=None, error=0
        )

    async def test_no_signal(self) -> None:
        device, _ = await _device("rx_a8a")

        assert device.data.zones["main"].signal_info == MusicCastSignalInfo(
            format="---", sample_rate="---", bit_depth=None, bitrate=0, error=0
        )

    async def test_standby(self) -> None:
        device, api = await _device("cd_nt670d")
        api.responses["main/getSignalInfo"] = {"audio": {"error": 0, "format": "", "fs": "", "bit": "", "bitrate": 0}}

        await device.handle({"main": {"signal_info_updated": True}})

        assert device.data.zones["main"].signal_info == MusicCastSignalInfo(
            format=None, sample_rate=None, bit_depth=None, bitrate=0, error=0
        )

    async def test_event_refreshes_signal_info(self) -> None:
        device, api = await _device("cd_nt670d")
        api.responses["main/getSignalInfo"] = {"audio": {"error": 0, "format": "PCM", "fs": "48 kHz", "bit": "24 bit"}}

        await device.handle({"main": {"signal_info_updated": True}})

        signal = device.data.zones["main"].signal_info
        assert signal is not None
        assert (signal.format, signal.sample_rate, signal.bit_depth) == ("PCM", "48 kHz", "24 bit")

    async def test_zone_without_signal_info_is_not_asked(self) -> None:
        device, api = await _device("cd_nt670d")
        device.data.zones["main"].features = device.data.zones["main"].features.__class__.POWER
        api.requests.clear()

        await device.handle({"main": {"signal_info_updated": True}})

        assert "main/getSignalInfo" not in api.requests


class NetworkStatusTest(unittest.IsolatedAsyncioTestCase):
    async def test_wifi(self) -> None:
        device, _ = await _device("cd_nt670d")
        data = device.data

        assert (data.network_connection, data.ip_address) == ("wireless_lan", "192.0.2.20")
        assert (data.wlan_ssid, data.wlan_channel, data.wlan_strength) == ("Home", 1, 74)

    async def test_wired(self) -> None:
        device, _ = await _device("rx_a8a")
        data = device.data

        assert (data.network_connection, data.ip_address) == ("wired_lan", "192.0.2.10")
        # The device reports strength -1 and an empty SSID when not on Wi-Fi.
        assert (data.wlan_ssid, data.wlan_channel, data.wlan_strength) == (None, None, None)

    async def test_refreshed_on_every_fetch(self) -> None:
        device, api = await _device("cd_nt670d")
        api.responses["system/getNetworkStatus"]["wireless_lan"]["strength"] = 40

        await device.fetch()

        assert device.data.wlan_strength == 40
        assert api.requests.count("system/getNetworkStatus") == 2


class TunerTest(unittest.IsolatedAsyncioTestCase):
    async def test_tuner_details(self) -> None:
        device, _ = await _device("cd_nt670d")
        data = device.data

        assert (data.fm_preset, data.rds_program_service, data.rds_program_type) == (3, "RADIO 1", "POP M")
        assert (data.dab_preset, data.dab_ensemble_label, data.dab_channel_label) == (4, "Ensemble", "11B")
        assert (data.dab_program_type, data.dab_bit_rate, data.dab_quality, data.dab_plus) == (
            "Pop Music",
            128,
            82,
            True,
        )


class WebPageTest(unittest.IsolatedAsyncioTestCase):
    async def test_web_page(self) -> None:
        device, _ = await _device("rx_a8a")

        assert device.web_page_url == "http://192.0.2.1/AdvancedSettings.html?mc=true"

    async def test_no_web_page(self) -> None:
        device, _ = await _device("cd_nt670d")

        assert device.web_page_url is None
