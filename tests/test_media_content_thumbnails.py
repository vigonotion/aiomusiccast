"""Tests for thumbnail URL handling."""

from __future__ import annotations

import unittest

from aiomusiccast.musiccast_media_content import MusicCastMediaContent, secure_thumbnail

TIDAL_HTTP = "http://resources.tidal.com:80/images/f1055fea/4564/4a53/8301/c9198500f439/750x750.jpg"
TIDAL_HTTPS = "https://resources.tidal.com/images/f1055fea/4564/4a53/8301/c9198500f439/750x750.jpg"


class SecureThumbnailTest(unittest.TestCase):
    def test_tidal_artwork_is_switched_to_https(self) -> None:
        assert secure_thumbnail(TIDAL_HTTP) == TIDAL_HTTPS
        assert secure_thumbnail("http://resources.tidal.com/a.jpg") == "https://resources.tidal.com/a.jpg"

    def test_other_urls_are_left_alone(self) -> None:
        for url in (
            None,
            "",
            TIDAL_HTTPS,
            "http://192.168.1.10/YamahaRemoteControl/AlbumART/AlbumART.jpg",
            "http://resources.tidal.com:8080/a.jpg",
            "http://evil.example/resources.tidal.com/a.jpg",
        ):
            assert secure_thumbnail(url) == url

    def test_list_entries_use_the_https_url(self) -> None:
        item = MusicCastMediaContent.from_info(
            "tidal", {"text": "You Still Got Me", "thumbnail": TIDAL_HTTP, "attribute": 125830150}, 4, 4
        )

        assert item.thumbnail == TIDAL_HTTPS


if __name__ == "__main__":
    unittest.main()
