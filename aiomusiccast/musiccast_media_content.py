from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import ClassVar

from .musiccast_device import MusicCastDevice

Logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MusicCastMediaContent:
    """Container for browsable MusicCast media entries."""

    BROWSABLE_INPUTS: ClassVar[tuple[str, ...]] = (
        "usb",
        "server",
        "net_radio",
        "rhapsody",
        "napster",
        "pandora",
        "siriusxm",
        "juke",
        "radiko",
        "qobuz",
        "deezer",
        "amazon_music",
    )

    musiccast: MusicCastDevice | None = None
    zone_id: str | None = None
    can_browse: bool = False
    can_play: bool = False
    can_search: bool = False
    title: str | None = None
    content_id: str | None = None
    menu_layer: int = -1
    thumbnail: str | None = None
    content_type: str | None = None
    list_len: int = 8
    start_index: int = 0
    has_next_page: bool = False
    has_previous_page: bool = False
    children: list[MusicCastMediaContent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.musiccast and not self.zone_id:
            msg = "Zone id must be provided when binding a musiccast device."
            raise ValueError(msg)

    @property
    def _zone_id(self) -> str:
        if self.zone_id is None:
            msg = "Zone id is required for this operation."
            raise ValueError(msg)
        return self.zone_id

    @property
    def _device(self) -> MusicCastDevice:
        if self.musiccast is None:
            msg = "MusicCast device must be provided for this operation."
            raise ValueError(msg)
        return self.musiccast

    @classmethod
    def from_info(cls, source: str, info: dict, menu_layer: int, index: int) -> MusicCastMediaContent:
        # b[1]     Capable of Select(common for all Net/USB sources
        # b[2]     Capable of Play(common for all Net/USB sources)
        # b[3]     Capable of Search
        attribute_raw = info.get("attribute")
        attribute = int(attribute_raw) if attribute_raw is not None else 0
        return cls(
            can_browse=attribute & 0b10 == 0b10,
            can_play=attribute & 0b100 == 0b100,
            can_search=attribute & 0b1000 == 0b1000,
            title=info.get("text"),
            content_id=f"list:{source}:{menu_layer}:{index}",
            thumbnail=info.get("thumbnail"),
            menu_layer=menu_layer,
            content_type="directory" if attribute & 0b10 == 0b10 else "track",
        )

    @classmethod
    def from_preset(cls, preset_num: str | int, preset: Sequence[str]) -> MusicCastMediaContent:
        return cls(
            can_play=True, title=preset[0] + " - " + preset[1], content_id=f"presets:{preset_num}", content_type="track"
        )

    @classmethod
    async def browse_media(
        cls, musiccast: MusicCastDevice, zone_id: str, media_content_path: Sequence[str], list_len: int = 8
    ) -> MusicCastMediaContent:
        self = cls(
            musiccast=musiccast,
            zone_id=zone_id,
            can_browse=True,
            content_id=":".join(media_content_path),
            list_len=list_len,
        )
        if media_content_path[-1].startswith("<>"):
            # just a page change
            self.start_index = int(media_content_path[-1][2:])
            self.content_id = ":".join(media_content_path[:-1])

        device = self._device

        if media_content_path[0] == "input":
            source = media_content_path[1]
            await self.return_in_list_info(source)
            await self.load_list(source)

        elif media_content_path[0] == "list":
            source = media_content_path[1]
            self.menu_layer = int(media_content_path[2])

            list_info = await device.get_list_info(source, 0)
            if self.menu_layer < list_info.get("menu_layer"):
                await self.return_in_list_info(source, self.menu_layer)

            elif media_content_path[3].isdigit():
                # an item was selected
                await device.select_list_item(media_content_path[3], self._zone_id)

            elif self.menu_layer != list_info.get("menu_layer"):
                Logger.warning(
                    "Unexpected menu layer. Expected %s, found %s",
                    self.menu_layer,
                    list_info.get("menu_layer"),
                )

            await self.load_list(source)

        elif media_content_path[0] == "presets":
            for i, preset in device.data.netusb_preset_list.items():
                self.children.append(self.from_preset(i, preset))

            self.title = "Presets"
            self.can_browse = True
            self.content_type = "directory"
        else:
            raise ValueError(f"{media_content_path[0]} is an unknown browse method.")

        return self

    @classmethod
    def categories(cls, musiccast: MusicCastDevice, zone_id: str) -> MusicCastMediaContent:
        self = cls(
            musiccast=musiccast,
            zone_id=zone_id,
            title="Library",
            content_id="",
            content_type="categories",
            can_browse=True,
        )
        device = self._device
        sources = sorted(set(cls.BROWSABLE_INPUTS).intersection(device.data.zones[self._zone_id].input_list))
        self.children.append(
            MusicCastMediaContent(title="Presets", content_id="presets", can_browse=True, content_type="directory")
        )
        for source in sources:
            self.children.append(
                MusicCastMediaContent(
                    title=device.data.input_names.get(source, source),
                    content_id=f"input:{source}",
                    can_browse=True,
                    content_type="directory",
                )
            )

        return self

    async def load_list(self, source: str) -> None:
        # load list info
        device = self._device
        list_info = await device.get_list_info(source, self.start_index)
        self.title = list_info.get("menu_name")
        self.menu_layer = int(list_info.get("menu_layer"))
        self.content_id = f"list:{source}:{self.menu_layer}:<>{self.start_index}"
        # get list items
        entries = list_info.get("list_info", [])
        for i in range(self.start_index + 8, self.start_index + self.list_len, 8):
            if i >= list_info.get("max_line", 8):
                break
            list_info_tmp = await device.get_list_info(source, i)
            entries += list_info_tmp.get("list_info", [])

        if int(self.start_index) != 0:
            self.has_previous_page = True

        for i, info in enumerate(list_info.get("list_info", [])):
            self.children.append(self.from_info(source, info, self.menu_layer + 1, self.start_index + i))
        self.can_play = not any(child.can_browse for child in self.children)
        self.can_browse = True
        self.content_type = "directory" if any(child.can_browse for child in self.children) else "track"
        if (list_info.get("max_line", 8) - self.start_index) >= self.list_len:
            self.has_next_page = True
            self.children.append(
                MusicCastMediaContent(
                    can_browse=True,
                    content_type="directory",
                    menu_layer=self.menu_layer,
                    content_id=":".join(self.content_id.split(":")[:-1]) + f":<>{self.start_index + self.list_len}",
                    title="Next Page",
                )
            )

    async def return_in_list_info(self, source: str, until_layer: int = 0) -> None:
        # reset list info
        while True:
            list_info = await self._device.get_list_info(source, 0)

            self.menu_layer = list_info.get("menu_layer")
            if self.menu_layer == until_layer:
                break
            await self._device.return_in_list(self._zone_id)
