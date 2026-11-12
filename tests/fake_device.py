"""A simulated netusb list menu, modelled on a TIDAL menu."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SELECT = 0b10
PLAY = 0b100
SEARCH = 0b1000


@dataclass
class Node:
    """A list in the menu."""

    name: str
    items: list[Item] = field(default_factory=list)


@dataclass
class Item:
    """An entry of a list."""

    text: str
    attribute: int
    child: Node | None = None


ALBUMS_ALPHABETICAL = ["Abbey Road", "Blue Train", "Kind of Blue", "Revolver"]
ALBUMS_BY_DATE = ["Revolver", "Kind of Blue", "Blue Train", "Abbey Road"]


def _album(title: str) -> Item:
    tracks = Node(title, [Item(f"{title} - track {n}", PLAY) for n in (1, 2)])
    return Item(title, SELECT | PLAY, tracks)


def _albums(name: str, titles: list[str]) -> Node:
    node = Node(name)
    # Every sorted list offers the sort entries again, one level deeper.
    node.items = [
        Item("Sort by alphabet", SELECT),
        Item("Sort by date added", SELECT),
    ] + [_album(title) for title in titles]
    return node


def build_menu() -> Node:
    """Return a TIDAL-like menu with nested sorted album lists."""
    albums = _albums("Albums", ALBUMS_ALPHABETICAL)

    def sorted_lists(node: Node, depth: int) -> None:
        if depth == 0:
            return
        by_alphabet = _albums("Sort by alphabet", ALBUMS_ALPHABETICAL)
        by_date = _albums("Sort by date added", ALBUMS_BY_DATE)
        node.items[0].child = by_alphabet
        node.items[1].child = by_date
        sorted_lists(by_alphabet, depth - 1)
        sorted_lists(by_date, depth - 1)

    sorted_lists(albums, 2)
    my_music = Node("My music", [Item("Playlists", SELECT), Item("Albums", SELECT, albums)])
    many = Node("New", [Item(f"Track {n:02}", PLAY) for n in range(30)])
    return Node(
        "TIDAL",
        [Item("New", SELECT, many), Item("My music", SELECT, my_music), Item("Search", SELECT | SEARCH)],
    )


class FakeDevice:
    """List methods of ``MusicCastDevice`` on a simulated menu.

    Parameters
    ----------
    stale_reads
        After each command, this many list info reads report the previous
        layer number together with the new list, like real devices do.
    """

    def __init__(self, stale_reads: int = 0) -> None:
        self.root = build_menu()
        self.stack: list[Node] = [self.root]
        self.stale_reads = stale_reads
        self._stale_left = 0
        self._stale_layer = 0
        self.played: list[str] = []
        self.searches: list[str] = []
        self.last_search = ""

    # -- helpers for tests --------------------------------------------------
    @property
    def current(self) -> Node:
        return self.stack[-1]

    def move_cursor(self, *selections: int) -> None:
        """Simulate another client: go to root and select ``selections``."""
        self.stack = [self.root]
        for index in selections:
            child = self.current.items[index].child
            assert child is not None
            self.stack.append(child)

    def _moved(self, previous_layer: int) -> None:
        self._stale_left = self.stale_reads
        self._stale_layer = previous_layer

    def _search_results(self, text: str) -> Node:
        return Node("Search", [Item("Albums", 0)] + [_album(f"{text} album {n}") for n in (1, 2)])

    # -- MusicCastDevice API ------------------------------------------------
    async def get_list_info(self, source: str, start_index: int) -> dict[str, Any]:
        assert source == "tidal"
        layer = len(self.stack) - 1
        if self._stale_left:
            self._stale_left -= 1
            layer = self._stale_layer
        node = self.current
        return {
            "response_code": 0,
            "input": source,
            "menu_layer": layer,
            "menu_name": node.name,
            "max_line": len(node.items),
            "index": start_index,
            "list_info": [
                {"text": item.text, "attribute": item.attribute, "thumbnail": ""}
                for item in node.items[start_index : start_index + 8]
            ],
        }

    async def select_list_item(self, item: int | str, zone_id: str) -> None:
        assert zone_id == "main"
        entry = self.current.items[int(item)]
        previous = len(self.stack) - 1
        if entry.attribute & SEARCH:
            self.stack.append(self._search_results(self.last_search))
        else:
            assert entry.child is not None, f"{entry.text} cannot be selected"
            self.stack.append(entry.child)
        self._moved(previous)

    async def return_in_list(self, zone_id: str) -> None:
        assert zone_id == "main"
        previous = len(self.stack) - 1
        if len(self.stack) > 1:
            self.stack.pop()
        self._moved(previous)

    async def play_list_media(self, item: int | str, zone_id: str) -> None:
        assert zone_id == "main"
        self.played.append(self.current.items[int(item)].text)

    async def search_list_item(self, search_string: str, item: int | str) -> dict[str, Any]:
        entry = self.current.items[int(item)]
        assert entry.attribute & SEARCH, f"{entry.text} is not searchable"
        previous = len(self.stack) - 1
        self.last_search = search_string
        self.searches.append(search_string)
        self.stack.append(self._search_results(search_string))
        self._moved(previous)
        return {"response_code": 0}
