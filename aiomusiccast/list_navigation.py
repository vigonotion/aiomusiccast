"""Walk the netusb list menu of a device along a path of selections.

A MusicCast device keeps a single list cursor per device. Every client that
uses the list API (the MusicCast app, Home Assistant, scripts) moves the same
cursor, and the device only reports the current ``menu_layer`` and
``menu_name``. Identifying an entry by "index N of whatever list is at layer
L" therefore breaks as soon as the cursor moved to a different list at that
layer, for example when a browser re-fetches a parent level, or when an
input's own menu has sort variants (Albums -> Sort by date added) that put a
different list one level up.

:class:`ListNavigator` identifies a list by the full path of selections from
the input's root menu instead. Before the list is read or an entry is
played, the cursor is walked to that exact list: back up to the common prefix
of where it was left and where it must go, then down, waiting after every
command until the device reports the expected layer.
"""

from __future__ import annotations

import asyncio
import logging
import time
import weakref
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .exceptions import MusicCastException

if TYPE_CHECKING:
    from .musiccast_device import MusicCastDevice

_LOGGER = logging.getLogger(__name__)

#: A path step: an ``int`` selects that index, ``"s<index>"`` runs the search
#: text on the search-capable entry at ``<index>`` (``setSearchString``).
Step = int | str

SEARCH_STEP_PREFIX = "s"


def search_step(index: int) -> str:
    """Return the step that searches with the entry at ``index``."""
    return f"{SEARCH_STEP_PREFIX}{index}"


def is_search_step(step: Step) -> bool:
    """Return whether ``step`` runs a search."""
    return isinstance(step, str)


def encode_steps(steps: tuple[Step, ...]) -> str:
    """Encode path steps for use in a content id."""
    return ".".join(str(step) for step in steps)


def decode_steps(raw: str) -> tuple[Step, ...]:
    """Decode path steps from a content id.

    Raises
    ------
    ValueError
        If a step is neither an index nor a search step.
    """
    steps: list[Step] = []
    for part in raw.split(".") if raw else ():
        if part.startswith(SEARCH_STEP_PREFIX):
            int(part[len(SEARCH_STEP_PREFIX) :])
            steps.append(part)
        else:
            steps.append(int(part))
    return tuple(steps)


@dataclass
class _Cursor:
    """Where a navigator last left the device's list cursor."""

    steps: tuple[Step, ...]
    query: str | None
    layer: int
    name: str | None


@dataclass
class _DeviceState:
    lock: asyncio.Lock
    cursors: dict[str, _Cursor]


_STATES: weakref.WeakKeyDictionary[Any, _DeviceState] = weakref.WeakKeyDictionary()


def _state(device: MusicCastDevice) -> _DeviceState:
    state = _STATES.get(device)
    if state is None:
        state = _STATES[device] = _DeviceState(asyncio.Lock(), {})
    return state


class ListNavigator:
    """Moves a device's list cursor along step paths of one input.

    Use :meth:`lock` around :meth:`goto` and everything that relies on the
    cursor staying there (reading the list, playing an entry), so concurrent
    requests for the same device don't interleave.

    Parameters
    ----------
    device
        The device whose list cursor is moved.
    zone_id
        Zone used for list control commands.
    source
        Input whose list menu is walked, e.g. ``"tidal"``.
    """

    #: Seconds to wait for the device to reach a layer after a command.
    STEP_TIMEOUT = 4.0
    #: Seconds between list info requests while waiting.
    POLL_INTERVAL = 0.15
    #: Maximum number of "return" commands to reach the root menu.
    MAX_RETURNS = 15

    def __init__(self, device: MusicCastDevice, zone_id: str, source: str) -> None:
        self.device = device
        self.zone_id = zone_id
        self.source = source
        self._state = _state(device)

    @property
    def lock(self) -> asyncio.Lock:
        """Lock serialising list cursor use for this device."""
        return self._state.lock

    async def list_info(self, start_index: int = 0) -> dict[str, Any]:
        """Return list info of the current list from ``start_index``.

        Raises
        ------
        MusicCastException
            If the device returned no list.
        """
        data: dict[str, Any] = await self.device.get_list_info(self.source, start_index)
        if "menu_layer" not in data:
            msg = f"No list returned for {self.source}: {data}"
            raise MusicCastException(msg)
        return data

    async def read(self, data: dict[str, Any], start_index: int, count: int) -> list[dict[str, Any]]:
        """Read up to ``count`` entries of the current list.

        Parameters
        ----------
        data
            List info of the current list from index 0, as returned by
            :meth:`goto`.
        start_index
            First entry to read.
        count
            Maximum number of entries.

        Returns
        -------
        list[dict[str, Any]]
            The ``list_info`` entries.
        """
        max_line = int(data.get("max_line", 0))
        entries: list[dict[str, Any]] = []
        position = start_index
        while position < min(start_index + count, max_line):
            page = data if position == 0 else await self.list_info(position)
            got = page.get("list_info", [])
            if not got:
                break
            entries.extend(got)
            position += len(got)
        return entries[:count]

    async def goto(self, steps: tuple[Step, ...], query: str | None = None) -> dict[str, Any]:
        """Move the cursor into the list at ``steps``.

        The caller must hold :attr:`lock`. If a step fails, for example
        because another client moved the cursor while walking, the walk is
        started again from the root once.

        Parameters
        ----------
        steps
            Path from the input's root menu.
        query
            Search text for a search step in ``steps``.

        Returns
        -------
        dict[str, Any]
            List info of the reached list from index 0.
        """
        try:
            return await self._goto(steps, query)
        except MusicCastException as err:
            _LOGGER.debug("List walk failed (%s), retrying from the root", err)
            self._state.cursors.pop(self.source, None)
            return await self._goto(steps, query)

    async def _goto(self, target: tuple[Step, ...], query: str | None) -> dict[str, Any]:
        try:
            data = await self.list_info()
            known = self._state.cursors.get(self.source)
            if (
                known is not None
                and int(data["menu_layer"]) == known.layer
                and data.get("menu_name") == known.name
                and known.layer == len(known.steps)
            ):
                current = list(known.steps)
                current_query = known.query
            else:
                data = await self._to_root()
                current = []
                current_query = None

            common = 0
            while (
                common < min(len(current), len(target))
                and current[common] == target[common]
                and (not is_search_step(current[common]) or current_query == query)
            ):
                common += 1

            while len(current) > common:
                await self.device.return_in_list(self.zone_id)
                current.pop()
                data = await self._wait_for_layer(len(current))

            for step in target[len(current) :]:
                await self._step(step, query)
                current.append(step)
                data = await self._wait_for_layer(len(current))

            reached = tuple(current)
            self._state.cursors[self.source] = _Cursor(
                reached,
                query if any(is_search_step(step) for step in reached) else None,
                int(data["menu_layer"]),
                data.get("menu_name"),
            )
            return data
        except Exception:
            self._state.cursors.pop(self.source, None)
            raise

    async def _step(self, step: Step, query: str | None) -> None:
        if isinstance(step, int):
            await self.device.select_list_item(step, self.zone_id)
            return
        result = await self.device.search_list_item(query or "", int(step[len(SEARCH_STEP_PREFIX) :]))
        if result and result.get("response_code") not in (0, None):
            msg = f"Search failed: {result}"
            raise MusicCastException(msg)

    async def _to_root(self) -> dict[str, Any]:
        data = await self.list_info()
        for _ in range(self.MAX_RETURNS):
            layer = int(data["menu_layer"])
            if layer == 0:
                return data
            await self.device.return_in_list(self.zone_id)
            data = await self._wait_for_layer(layer - 1)
        msg = f"Could not return to the root menu of {self.source}"
        raise MusicCastException(msg)

    async def _wait_for_layer(self, layer: int) -> dict[str, Any]:
        """Wait until the device reports ``layer`` twice in a row.

        Devices sometimes report a layer that doesn't match the list
        they return yet, so a single matching read is not trusted.
        """
        deadline = time.monotonic() + self.STEP_TIMEOUT
        previous: tuple[int, Any, Any] | None = None
        while True:
            data = await self.list_info()
            signature = (int(data["menu_layer"]), data.get("menu_name"), data.get("max_line"))
            if signature[0] == layer and signature == previous:
                return data
            previous = signature if signature[0] == layer else None
            if time.monotonic() > deadline:
                msg = f"List did not reach layer {layer} (at {signature[0]} {signature[1]!r})"
                raise MusicCastException(msg)
            await asyncio.sleep(self.POLL_INTERVAL)
