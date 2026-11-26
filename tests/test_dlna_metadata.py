"""Tests for DLNA metadata, seeking, position and transport state."""

from __future__ import annotations

import asyncio
import unittest
import xml.etree.ElementTree as ET
from typing import Any, cast
from unittest.mock import AsyncMock

from aiohttp import ClientConnectionError

from aiomusiccast.exceptions import MusicCastConnectionException, MusicCastException
from aiomusiccast.musiccast_device import DLNA_SEEKABLE_FLAGS, MusicCastDevice
from aiomusiccast.pyamaha import AsyncDevice

AVT_NS = "urn:schemas-upnp-org:service:AVTransport:1"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
DIDL_NS = "urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
DC_NS = "http://purl.org/dc/elements/1.1/"
UPNP_NS = "urn:schemas-upnp-org:metadata-1-0/upnp/"


def _envelope(action: str, body: str) -> str:
    # As a CD-NT670D answers (metadata left out).
    return (
        '<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
        f'<u:{action}Response xmlns:u="{AVT_NS}">{body}</u:{action}Response></s:Body></s:Envelope>'
    )


ANSWERS = {
    "GetPositionInfo": _envelope(
        "GetPositionInfo",
        "<Track>1</Track><TrackDuration>1:56:32</TrackDuration><TrackMetaData></TrackMetaData>"
        "<TrackURI></TrackURI><RelTime>0:12:05</RelTime><AbsTime>NOT_IMPLEMENTED</AbsTime>"
        "<RelCount>2147483647</RelCount><AbsCount>2147483647</AbsCount>",
    ),
    "GetTransportInfo": _envelope(
        "GetTransportInfo",
        "<CurrentTransportState>PLAYING</CurrentTransportState>"
        "<CurrentTransportStatus>OK</CurrentTransportStatus><CurrentSpeed>1</CurrentSpeed>",
    ),
}


class FakeResponse:
    def __init__(self, status: int, text: str) -> None:
        self.status = status
        self._text = text

    async def text(self) -> str:
        return self._text


class FakeClient:
    """Answers the AVTransport actions and records the requests."""

    def __init__(self, status: int = 200, failures: int = 0) -> None:
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.status = status
        self.failures = failures

    async def request(self, method: str, url: str, *, headers: dict[str, str], data: bytes) -> FakeResponse:
        del method, url
        action = headers["SOAPACTION"].split("#")[1].strip('"')
        envelope = ET.fromstring(data.decode("utf-8"))
        body = envelope.find(f"{{{SOAP_NS}}}Body")[0]  # type: ignore[index]
        self.requests.append((action, {child.tag: child.text or "" for child in body}))
        if self.failures:
            self.failures -= 1
            raise ClientConnectionError("Connection closed")
        return FakeResponse(self.status, ANSWERS.get(action, _envelope(action, "")))


def _musiccast(client: FakeClient) -> MusicCastDevice:
    device = AsyncDevice(
        cast("Any", client),
        "192.0.2.1",
        asyncio.get_running_loop(),
        upnp_description="http://192.0.2.1:49154/MediaRenderer/desc.xml",
    )
    device.upnp_avt_ns = cast("Any", AVT_NS)
    device.upnp_avt_ctrl = cast("Any", "/AVTransport/ctrl")
    musiccast = MusicCastDevice.__new__(MusicCastDevice)
    musiccast.device = device
    cast("Any", musiccast).select_source = AsyncMock()
    return musiccast


class MetadataTest(unittest.IsolatedAsyncioTestCase):
    async def test_full_metadata(self) -> None:
        client = FakeClient()
        musiccast = _musiccast(client)

        await musiccast.play_url_media(
            "main",
            "http://192.0.2.2/episode.mp3?token=a&b=c",
            "Episode 329",
            "audio/mpeg",
            artist="Host & Guest",
            album="Łódź Radio",
            image_url="http://192.0.2.2/cover.jpg?x=1&y=2",
            duration=6992,
            size=111_872_000,
            seekable=True,
        )

        meta = ET.fromstring(client.requests[1][1]["CurrentURIMetaData"])
        item = meta.find(f"{{{DIDL_NS}}}item")
        assert item is not None
        assert item.findtext(f"{{{DC_NS}}}title") == "Episode 329"
        assert item.findtext(f"{{{DC_NS}}}creator") == "Host & Guest"
        assert item.findtext(f"{{{UPNP_NS}}}artist") == "Host & Guest"
        assert item.findtext(f"{{{UPNP_NS}}}album") == "Łódź Radio"
        assert item.findtext(f"{{{UPNP_NS}}}albumArtURI") == "http://192.0.2.2/cover.jpg?x=1&y=2"
        res = item.find(f"{{{DIDL_NS}}}res")
        assert res is not None
        assert res.text == "http://192.0.2.2/episode.mp3?token=a&b=c"
        assert res.get("protocolInfo") == f"http-get:*:audio/mpeg:{DLNA_SEEKABLE_FLAGS}"
        assert res.get("duration") == "1:56:32.000"
        assert res.get("size") == "111872000"

    async def test_title_only_as_before(self) -> None:
        client = FakeClient()
        musiccast = _musiccast(client)

        await musiccast.play_url_media("main", "http://192.0.2.2/a.mp3", "Title", "audio/mpeg")

        meta = ET.fromstring(client.requests[1][1]["CurrentURIMetaData"])
        item = meta.find(f"{{{DIDL_NS}}}item")
        assert item is not None
        assert [child.tag.split("}")[1] for child in item] == ["title", "class", "res"]
        res = item.find(f"{{{DIDL_NS}}}res")
        assert res is not None
        assert res.attrib == {"protocolInfo": "http-get:*:audio/mpeg:*"}


class TransportTest(unittest.IsolatedAsyncioTestCase):
    async def test_seek(self) -> None:
        client = FakeClient()

        await _musiccast(client).dlna_seek(3725.6)

        assert client.requests == [("Seek", {"InstanceID": "0", "Unit": "REL_TIME", "Target": "1:02:05"})]

    async def test_position_info(self) -> None:
        assert await _musiccast(FakeClient()).dlna_position_info() == (725.0, 6992.0)

    async def test_position_unknown(self) -> None:
        saved = dict(ANSWERS)
        try:
            ANSWERS["GetPositionInfo"] = _envelope(
                "GetPositionInfo", "<TrackDuration>0:00:00</TrackDuration><RelTime>NOT_IMPLEMENTED</RelTime>"
            )
            assert await _musiccast(FakeClient()).dlna_position_info() == (None, 0.0)
        finally:
            ANSWERS.update(saved)

    async def test_transport_state(self) -> None:
        assert await _musiccast(FakeClient()).dlna_transport_state() == "PLAYING"

    async def test_refused(self) -> None:
        error: MusicCastException | None = None
        try:
            await _musiccast(FakeClient(status=500)).dlna_seek(10)
        except MusicCastException as err:
            error = err
        assert error is not None
        assert "HTTP 500" in str(error)

    async def test_connection_error(self) -> None:
        # The request retries once; a second failure becomes a MusicCastConnectionException.
        try:
            await _musiccast(FakeClient(failures=2)).dlna_transport_state()
        except MusicCastConnectionException:
            pass
        else:
            self.fail("MusicCastConnectionException was not raised")
