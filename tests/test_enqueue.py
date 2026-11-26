"""Tests for adding list entries to the play queue."""

from __future__ import annotations

import unittest
from typing import Any, cast
from unittest import mock

from aiomusiccast.list_navigation import ListNavigator
from aiomusiccast.musiccast_media_content import MusicCastMediaContent, entry_content_id, page_content_id
from aiomusiccast.pyamaha import NetUSB

from .fake_device import ALBUMS_BY_DATE, FakeDevice

BY_DATE = (1, 1, 1)  # My music > Albums > Sort by date added
FIRST_ALBUM = 2  # entries 0 and 1 are the sort entries


class QueueingDevice(FakeDevice):
    """FakeDevice that records what is queued."""

    def __init__(self) -> None:
        super().__init__()
        self.queued: list[tuple[str, str]] = []

    async def enqueue_list_media(self, item: int | str, zone_id: str, mode: str) -> None:
        assert zone_id == "main"
        self.queued.append((mode, self.current.items[int(item)].text))


async def enqueue(device: QueueingDevice, content_id: str, mode: str = "add_to_queue") -> None:
    await MusicCastMediaContent.enqueue_list_entry(cast("Any", device), "main", content_id, mode)


class EnqueueTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        patcher = mock.patch.object(ListNavigator, "POLL_INTERVAL", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_track_of_an_album(self) -> None:
        device = QueueingDevice()

        await enqueue(device, entry_content_id("tidal", (*BY_DATE, FIRST_ALBUM, 1)), "play_next")

        assert device.queued == [("play_next", f"{ALBUMS_BY_DATE[0]} - track 2")]

    async def test_whole_album(self) -> None:
        device = QueueingDevice()

        await enqueue(device, page_content_id("tidal", (*BY_DATE, FIRST_ALBUM)))

        assert device.queued == [("add_to_queue", ALBUMS_BY_DATE[0])]

    async def test_cursor_moved_by_another_client(self) -> None:
        device = QueueingDevice()
        device.move_cursor(1, 1)  # the alphabetical album list

        await enqueue(device, entry_content_id("tidal", (*BY_DATE, FIRST_ALBUM)))

        assert device.queued == [("add_to_queue", ALBUMS_BY_DATE[0])]

    async def test_invalid(self) -> None:
        device = QueueingDevice()

        for content_id, mode in (
            ("list:tidal:3:2", "add_to_queue"),  # no path: the entry can't be found again
            (entry_content_id("tidal", ("s2",), "x"), "add_to_queue"),  # a search, no entry
            (entry_content_id("tidal", (1,)), "shuffle"),
        ):
            try:
                await enqueue(device, content_id, mode)
            except ValueError:
                continue
            self.fail(f"ValueError not raised for {content_id} {mode}")
        assert not device.queued

    def test_request(self) -> None:
        assert NetUSB.manage_list("main", "play_next", 3, "zone2").endswith(
            "netusb/manageList?list_id=main&type=play_next&index=3&zone=zone2&timeout=60000"
        )
