"""Tests for path-based list browsing, playing and searching."""

from __future__ import annotations

import unittest
from typing import Any, cast
from unittest import mock

from aiomusiccast.list_navigation import ListNavigator, decode_steps, encode_steps
from aiomusiccast.musiccast_media_content import (
    MusicCastMediaContent,
    entry_content_id,
    page_content_id,
    parse_path_content_id,
)

from .fake_device import ALBUMS_ALPHABETICAL, ALBUMS_BY_DATE, FakeDevice

# Menu paths in the fake TIDAL menu
MY_MUSIC = (1,)
ALBUMS = (1, 1)
BY_DATE = (1, 1, 1)
FIRST_ALBUM = 2  # entries 0 and 1 are the sort entries


async def browse(device: FakeDevice, content_id: str, list_len: int = 8) -> MusicCastMediaContent:
    return await MusicCastMediaContent.browse_media(cast("Any", device), "main", content_id.split(":"), list_len)


async def play(device: FakeDevice, content_id: str) -> None:
    await MusicCastMediaContent.play_list_entry(cast("Any", device), "main", content_id)


def titles(content: MusicCastMediaContent) -> list[str | None]:
    return [child.title for child in content.children]


class ContentIdTest(unittest.TestCase):
    def test_entry_ids_keep_the_old_fields_first(self) -> None:
        content_id = entry_content_id("tidal", (*BY_DATE, 4))

        # older clients read <source>, <layer> and <index> from these fields
        assert content_id.split(":")[:4] == ["list", "tidal", "4", "4"]
        assert parse_path_content_id(content_id) == ("tidal", (*BY_DATE, 4), None, None)

    def test_page_ids(self) -> None:
        content_id = page_content_id("tidal", BY_DATE, 24)

        assert content_id == "list:tidal:3:<>24:1.1.1"
        assert parse_path_content_id(content_id) == ("tidal", BY_DATE, 24, None)

    def test_search_text_survives_encoding(self) -> None:
        query = "AC/DC: Back in Black / ünïcödé"
        content_id = entry_content_id("tidal", ("s2", 1), query)

        assert parse_path_content_id(content_id) == ("tidal", ("s2", 1), None, query)

    def test_steps_round_trip(self) -> None:
        steps = (1, "s7", 12)

        assert decode_steps(encode_steps(steps)) == steps
        assert decode_steps("") == ()

    def test_invalid_ids_are_rejected(self) -> None:
        for content_id in ("list:tidal:1:6", "list:tidal:1:x:1.y", "list:tidal:2:1:s7", "list:tidal:0:0:"):
            with self.assertRaises(ValueError):  # noqa: PT027 - unittest based test suite
                parse_path_content_id(content_id)


class BrowseTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        patcher = mock.patch.object(ListNavigator, "POLL_INTERVAL", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_input_root(self) -> None:
        device = FakeDevice()
        device.move_cursor(*BY_DATE)

        root = await browse(device, "input:tidal")

        assert root.title == "TIDAL"
        assert titles(root) == ["New", "My music", "Search"]
        assert root.children[1].content_id == entry_content_id("tidal", MY_MUSIC)
        assert root.children[2].can_search

    async def test_entry_opens_the_list_it_was_listed_in(self) -> None:
        """Opening an entry of a sorted list after browsing its parent.

        Browsing the parent (as the HA frontend does for its header)
        leaves the cursor on the alphabetical Albums list. Layer/index
        ids then opened the album at that index of the alphabetical
        list.
        """
        device = FakeDevice()
        by_date = await browse(device, page_content_id("tidal", BY_DATE))
        await browse(device, page_content_id("tidal", ALBUMS))
        assert device.current.name == "Albums"

        album = await browse(device, cast("str", by_date.children[FIRST_ALBUM].content_id))

        assert album.title == ALBUMS_BY_DATE[0]
        assert ALBUMS_BY_DATE[0] != ALBUMS_ALPHABETICAL[0]

    async def test_cursor_moved_by_another_client(self) -> None:
        device = FakeDevice()
        by_date = await browse(device, page_content_id("tidal", BY_DATE))
        device.move_cursor(0)  # someone opened "New" in the MusicCast app

        album = await browse(device, cast("str", by_date.children[FIRST_ALBUM + 1].content_id))

        assert album.title == ALBUMS_BY_DATE[1]

    async def test_device_reporting_stale_layers(self) -> None:
        device = FakeDevice(stale_reads=2)

        album = await browse(device, entry_content_id("tidal", (*BY_DATE, FIRST_ALBUM)))

        assert album.title == ALBUMS_BY_DATE[0]
        assert len(device.stack) == 5

    async def test_nested_sort_lists(self) -> None:
        device = FakeDevice()

        nested = await browse(device, page_content_id("tidal", (*BY_DATE, 0)))

        assert nested.title == "Sort by alphabet"
        assert titles(nested)[FIRST_ALBUM:] == ALBUMS_ALPHABETICAL

    async def test_paging(self) -> None:
        device = FakeDevice()

        first = await browse(device, page_content_id("tidal", (0,)), list_len=24)
        second = await browse(device, cast("str", first.children[-1].content_id), list_len=24)

        assert len(first.children) == 25
        assert first.children[-1].title == "Next Page"
        assert first.has_next_page
        assert second.has_previous_page
        assert not second.has_next_page
        assert titles(second) == [f"Track {n:02}" for n in range(24, 30)]
        assert second.children[0].content_id == entry_content_id("tidal", (0, 24))

    async def test_legacy_ids_still_browse(self) -> None:
        device = FakeDevice()

        my_music = await browse(device, "list:tidal:1:1")

        assert my_music.title == "My music"
        assert my_music.children[1].content_id == "list:tidal:2:1"


class PlayTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        patcher = mock.patch.object(ListNavigator, "POLL_INTERVAL", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_plays_from_the_list_it_was_listed_in(self) -> None:
        device = FakeDevice()
        by_date = await browse(device, page_content_id("tidal", BY_DATE))
        await browse(device, page_content_id("tidal", ALBUMS))

        await play(device, cast("str", by_date.children[FIRST_ALBUM].content_id))

        assert device.played == [ALBUMS_BY_DATE[0]]

    async def test_plays_a_track_of_an_album(self) -> None:
        device = FakeDevice()

        await play(device, entry_content_id("tidal", (*BY_DATE, FIRST_ALBUM, 1)))

        assert device.played == [f"{ALBUMS_BY_DATE[0]} - track 2"]

    async def test_legacy_ids_play_the_current_list(self) -> None:
        device = FakeDevice()
        device.move_cursor(*ALBUMS)

        await play(device, f"list:tidal:3:{FIRST_ALBUM}")

        assert device.played == [ALBUMS_ALPHABETICAL[0]]

    async def test_lists_cannot_be_played(self) -> None:
        device = FakeDevice()

        for content_id in (page_content_id("tidal", BY_DATE), "presets:1", entry_content_id("tidal", ("s2",), "x")):
            with self.assertRaises(ValueError):  # noqa: PT027 - unittest based test suite
                await play(device, content_id)


if __name__ == "__main__":
    unittest.main()
