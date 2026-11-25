"""Tests for the inputs offered by the media browser."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any, cast

from aiomusiccast.musiccast_media_content import MusicCastMediaContent


def _device(input_list: list[str]) -> Any:
    zone = SimpleNamespace(input_list=input_list)
    data = SimpleNamespace(zones={"main": zone}, input_names={"tidal": "TIDAL"})
    return cast("Any", SimpleNamespace(data=data))


class CategoriesTest(unittest.TestCase):
    def test_tidal_is_listed_when_the_zone_has_it(self) -> None:
        library = MusicCastMediaContent.categories(_device(["tidal", "deezer", "airplay"]), "main")

        ids = [child.content_id for child in library.children]
        assert ids == ["presets", "input:deezer", "input:tidal"]
        assert library.children[2].title == "TIDAL"

    def test_tidal_is_not_listed_when_the_zone_lacks_it(self) -> None:
        library = MusicCastMediaContent.categories(_device(["deezer"]), "main")

        assert "input:tidal" not in [child.content_id for child in library.children]


if __name__ == "__main__":
    unittest.main()
