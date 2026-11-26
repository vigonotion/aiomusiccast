"""Tests for the zone and system settings and their capabilities."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, cast

from aiomusiccast.capabilities import BinarySetter, Capability, NumberSetter, OptionSetter
from aiomusiccast.exceptions import MusicCastException, MusicCastUnsupportedException
from aiomusiccast.musiccast_device import MusicCastDevice

# Responses of an RX-A8A (main zone and zone2), trimmed.
RESPONSES = json.loads((Path(__file__).parent / "fixtures" / "settings_rx_a8a.json").read_text())
PREFIX = "http://{host}/YamahaExtendedControl/v1/"


class FakeApi:
    """Answers GET requests from the fixture and records commands."""

    def __init__(self) -> None:
        self.commands: list[str] = []

    async def request_json(self, url: str) -> dict[str, Any]:
        path = url.removeprefix(PREFIX).split("?")[0]
        return json.loads(json.dumps(RESPONSES.get(path, {"response_code": 0})))

    async def request(self, url: str) -> None:
        self.commands.append(url.removeprefix(PREFIX))


async def _device() -> tuple[MusicCastDevice, FakeApi]:
    device = MusicCastDevice("192.0.2.1", cast("Any", None))
    api = FakeApi()
    device.device.request_json = api.request_json  # type: ignore[method-assign]
    device.device.request = api.request  # type: ignore[method-assign]
    await device.fetch()
    device.build_capabilities()
    return device, api


async def _assert_raises(error: type[Exception], call: Any) -> None:
    # The feature check of the device raises before returning a coroutine.
    try:
        await call()
    except error:
        return
    raise AssertionError(f"{error.__name__} not raised")


def _by_id(capabilities: list[Capability]) -> dict[str, Any]:
    return {capability.id: capability for capability in capabilities}


class SettingsDataTest(unittest.IsolatedAsyncioTestCase):
    async def test_zone_status_is_read(self) -> None:
        device, _ = await _device()
        main = device.data.zones["main"]
        zone2 = device.data.zones["zone2"]

        assert main.adaptive_dsp_level is True
        assert (main.actual_volume, main.actual_volume_mode) == (-52.5, "db")
        assert main.auro_3d_listening_mode == "surround"
        assert main.auro_matic_preset == "large"
        assert main.auro_matic_strength == 12
        assert main.scene_num == 8
        assert (zone2.balance, zone2.mono) == (0, False)

    async def test_relative_commands_are_not_options(self) -> None:
        device, _ = await _device()
        main = device.data.zones["main"]

        assert main.auro_3d_listening_mode_list == ["auro_3d", "surround", "native"]
        assert main.auro_matic_preset_list == ["small", "medium", "large", "movie", "speech"]

    async def test_hdmi_outputs_are_read(self) -> None:
        device, _ = await _device()

        assert device.data.hdmi_out == {1: True, 2: False, 3: False}


class SettingsCapabilitiesTest(unittest.IsolatedAsyncioTestCase):
    async def test_device_capabilities(self) -> None:
        device, api = await _device()
        capabilities = _by_id(device.data.capabilities)

        hdmi = capabilities["HDMI_OUT_3"]
        assert isinstance(hdmi, BinarySetter)
        assert hdmi.current is False
        await hdmi.set(True)
        assert api.commands == ["system/setHdmiOut3?enable=true"]

    async def test_zone_capabilities(self) -> None:
        device, api = await _device()
        main = _by_id(device.data.zones["main"].capabilities)
        zone2 = _by_id(device.data.zones["zone2"].capabilities)

        assert isinstance(main["zone_ADAPTIVE_DSP_LEVEL"], BinarySetter)
        assert main["zone_ADAPTIVE_DSP_LEVEL"].current is True
        volume = main["zone_ACTUAL_VOLUME"]
        assert isinstance(volume, NumberSetter)
        assert volume.current == -52.5
        assert (volume.value_range.minimum, volume.value_range.maximum, volume.value_range.step) == (-80.5, 16.5, 0.5)
        listening_mode = main["zone_AURO_3D_LISTENING_MODE"]
        assert isinstance(listening_mode, OptionSetter)
        assert list(listening_mode.options) == ["auro_3d", "surround", "native"]
        assert main["zone_AURO_MATIC_STRENGTH"].current == 12
        assert "zone_BALANCE" not in main  # the main zone has no balance
        assert zone2["zone_BALANCE"].current == 0
        assert zone2["zone_MONO"].current is False

        await volume.set(-40.5)
        await listening_mode.set("native")
        await main["zone_AURO_MATIC_PRESET"].set("movie")
        await main["zone_AURO_MATIC_STRENGTH"].set(10)
        await zone2["zone_BALANCE"].set(-3)
        await zone2["zone_MONO"].set(True)
        await main["zone_ADAPTIVE_DSP_LEVEL"].set(False)
        assert api.commands == [
            "main/setActualVolume?mode=db&value=-40.5",
            "main/setAuro3dListeningMode?mode=native",
            "main/setAuroMaticPreset?preset=movie",
            "main/setAuroMaticStrength?value=10",
            "zone2/setBalance?value=-3",
            "zone2/setMono?enable=true",
            "main/setAdaptiveDspLevel?enable=false",
        ]

    async def test_volume_out_of_range_is_refused(self) -> None:
        device, api = await _device()
        volume = _by_id(device.data.zones["main"].capabilities)["zone_ACTUAL_VOLUME"]

        await _assert_raises(MusicCastException, lambda: volume.set(-40.3))
        assert not api.commands

    async def test_volume_db_unknown_in_numeric_mode(self) -> None:
        device, _ = await _device()
        device.data.zones["main"].actual_volume_mode = "numeric"

        assert _by_id(device.data.zones["main"].capabilities)["zone_ACTUAL_VOLUME"].current is None

    async def test_number_without_range_is_skipped(self) -> None:
        device, _ = await _device()
        del device.data.zones["main"].range_step["auro_matic_strength"]
        device.build_capabilities()

        assert "zone_AURO_MATIC_STRENGTH" not in _by_id(device.data.zones["main"].capabilities)


class ActionsTest(unittest.IsolatedAsyncioTestCase):
    async def test_scene_and_reboots(self) -> None:
        device, api = await _device()

        await device.recall_scene("zone2", 8)
        await device.reboot_network_module()
        await device.reboot()

        assert api.commands == [
            "zone2/recallScene?num=8",
            "system/requestNetworkReboot",
            "system/requestSystemReboot",
        ]

    async def test_scene_out_of_range(self) -> None:
        device, api = await _device()

        await _assert_raises(MusicCastException, lambda: device.recall_scene("main", 9))
        assert not api.commands

    async def test_unsupported(self) -> None:
        device, _ = await _device()

        await _assert_raises(MusicCastUnsupportedException, lambda: device.set_mono("main", True))
        await _assert_raises(MusicCastUnsupportedException, lambda: device.set_hdmi_out(4, True))
