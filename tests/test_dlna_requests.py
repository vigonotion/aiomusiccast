"""Tests for the DLNA AVTransport requests used to play URLs."""

from __future__ import annotations

import asyncio
import unittest
import xml.etree.ElementTree as ET
from typing import Any, cast
from unittest.mock import AsyncMock

from aiohttp import ClientConnectionError

from aiomusiccast.musiccast_device import MusicCastDevice
from aiomusiccast.pyamaha import AsyncDevice

AVT_NS = "urn:schemas-upnp-org:service:AVTransport:1"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
DIDL_NS = "urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
DC_NS = "http://purl.org/dc/elements/1.1/"


class FakeClient:
    """Records the requests instead of sending them."""

    def __init__(self, failures: int = 0) -> None:
        self.requests: list[dict[str, Any]] = []
        self.failures = failures

    async def request(self, method: str, url: str, *, headers: dict[str, str], data: bytes) -> str:
        self.requests.append({"method": method, "url": url, "headers": headers, "data": data})
        if self.failures:
            self.failures -= 1
            raise ClientConnectionError("Connection closed")
        return "ok"


def _device(client: FakeClient) -> AsyncDevice:
    device = AsyncDevice(
        cast("Any", client),
        "192.0.2.1",
        asyncio.get_running_loop(),
        upnp_description="http://192.0.2.1:49154/MediaRenderer/desc.xml",
    )
    device.upnp_avt_ns = cast("Any", AVT_NS)
    device.upnp_avt_ctrl = cast("Any", "/AVTransport/ctrl")
    return device


def _action_args(data: bytes) -> dict[str, str]:
    envelope = ET.fromstring(data.decode("utf-8"))
    action = envelope.find(f"{{{SOAP_NS}}}Body")[0]  # type: ignore[index]
    return {child.tag: child.text or "" for child in action}


class DlnaAvtRequestTest(unittest.IsolatedAsyncioTestCase):
    async def test_content_length_counts_utf8_bytes(self) -> None:
        client = FakeClient()
        device = _device(client)

        await device.dlna_avt_request("SetAVTransportURI", {"InstanceID": 0, "CurrentURI": "http://h/Łódź.mp3"})

        request = client.requests[0]
        assert isinstance(request["data"], bytes)
        assert request["headers"]["Content-Length"] == str(len(request["data"]))
        assert len(request["data"]) > len(request["data"].decode("utf-8"))

    async def test_retries_once_when_the_connection_is_closed(self) -> None:
        client = FakeClient(failures=1)
        device = _device(client)

        assert await device.dlna_avt_request("Stop", {"InstanceID": 0}) == "ok"
        assert len(client.requests) == 2

    async def test_second_failure_is_raised(self) -> None:
        client = FakeClient(failures=2)
        device = _device(client)

        try:
            await device.dlna_avt_request("Stop", {"InstanceID": 0})
        except ClientConnectionError:
            pass
        else:
            self.fail("ClientConnectionError was not raised")
        assert len(client.requests) == 2


class PlayUrlMediaTest(unittest.IsolatedAsyncioTestCase):
    async def _play(self, media_url: str, title: str) -> dict[str, str]:
        client = FakeClient()
        musiccast = MusicCastDevice.__new__(MusicCastDevice)
        musiccast.device = _device(client)
        cast("Any", musiccast).select_source = AsyncMock()

        await musiccast.play_url_media("main", media_url, title, "audio/mpeg")

        actions = [r["headers"]["SOAPACTION"].split("#")[1].strip('"') for r in client.requests]
        assert actions == ["Stop", "SetAVTransportURI", "Play"]
        request = client.requests[1]
        assert request["headers"]["Content-Length"] == str(len(request["data"]))
        return _action_args(request["data"])

    async def test_ampersands_and_brackets_give_well_formed_xml(self) -> None:
        url = "http://192.0.2.2/api/tts_proxy?token=a&b=c"
        title = "Rock & Roll <live>"

        args = await self._play(url, title)

        assert args["CurrentURI"] == url
        meta = ET.fromstring(args["CurrentURIMetaData"])
        assert meta.tag == f"{{{DIDL_NS}}}DIDL-Lite"
        assert meta.findtext(f".//{{{DC_NS}}}title") == title
        assert meta.findtext(f".//{{{DIDL_NS}}}res") == url

    async def test_non_ascii_title_and_url(self) -> None:
        url = "http://192.0.2.2/media/Zażółć gęślą jaźń.mp3"
        title = "Pchnąć w tę łódź jeża"

        args = await self._play(url, title)

        assert args["CurrentURI"] == url
        meta = ET.fromstring(args["CurrentURIMetaData"])
        assert meta.findtext(f".//{{{DC_NS}}}title") == title
        assert meta.findtext(f".//{{{DIDL_NS}}}res") == url


if __name__ == "__main__":
    unittest.main()
