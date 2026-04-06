"""Direct RIO SE client for MBX-PRE Source Mode."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from collections.abc import Callable

_LOGGER = logging.getLogger(__name__)

_SOURCE_LINE_RE = re.compile(
    r'^[NS]\s+S\[(?P<source_id>\d+)\]\.(?P<key>[A-Za-z0-9_.]+)=\"(?P<value>.*)\"$'
)
_VERSION_RE = re.compile(r'^S\s+VERSION=\"(?P<version>.*)\"$')


class MbxRioSeClient:
    """Minimal direct RIO SE client for MBX-PRE Source Mode."""

    def __init__(self, host: str, port: int, source_id: int, name: str) -> None:
        self.host = host
        self.port = port
        self.source_id = source_id
        self.name = name

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._listeners: list[Callable[[], None]] = []

        self.protocol_version: str | None = None
        self.state: dict[str, str] = {
            "mode": "",
            "artistName": "",
            "albumName": "",
            "songName": "",
            "channelName": "",
            "playlistName": "",
            "coverArtURL": "",
            "playStatus": "",
            "availableControls": "",
            "playTime": "0",
            "trackTime": "0",
        }

    @property
    def is_connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def _remove() -> None:
            with contextlib.suppress(ValueError):
                self._listeners.remove(listener)

        return _remove

    async def connect(self) -> None:
        """Open TCP connection and start read loop."""
        if self.is_connected:
            return

        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
        self._read_task = asyncio.create_task(self._read_loop(), name=f"mbx-riose-{self.name}")
        _LOGGER.info("Connected MBX RIO SE client %s at %s:%s", self.name, self.host, self.port)

    async def initialize(self) -> None:
        """Initialize RIO SE session."""
        await self.send_command("VERSION")
        await self.send_command(f"WATCH S[{self.source_id}] ON")

    async def disconnect(self) -> None:
        """Close TCP connection."""
        if self._read_task is not None:
            self._read_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._read_task
            self._read_task = None

        if self._writer is not None:
            self._writer.close()
            with contextlib.suppress(Exception):
                await self._writer.wait_closed()

        self._reader = None
        self._writer = None

    async def send_command(self, command: str) -> None:
        """Send a raw RIO SE command."""
        if not self.is_connected or self._writer is None:
            raise RuntimeError(f"MBX RIO SE client {self.name} is not connected")

        wire = f"{command}\r\n"
        _LOGGER.debug("MBX RIO SE -> %s", wire.strip())
        self._writer.write(wire.encode("utf-8"))
        await self._writer.drain()

    async def previous_track(self) -> None:
        await self.send_command(f"EVENT S[{self.source_id}]!KeyRelease Previous")

    async def next_track(self) -> None:
        await self.send_command(f"EVENT S[{self.source_id}]!KeyRelease Next")

    async def pause_toggle(self) -> None:
        await self.send_command(f"EVENT S[{self.source_id}]!KeyRelease Pause")

    async def mm_init(self) -> None:
        await self.send_command(f"EVENT S[{self.source_id}]!MMInit")

    async def mm_close(self) -> None:
        await self.send_command(f"EVENT S[{self.source_id}]!MMClose")

    async def mm_prev_screen(self) -> None:
        await self.send_command(f"EVENT S[{self.source_id}]!MMPrevScreen")

    async def mm_select_item(self, item_index: int) -> None:
        await self.send_command(f"EVENT S[{self.source_id}]!MMSelectItem {item_index}")

    async def _read_loop(self) -> None:
        assert self._reader is not None

        while True:
            raw = await self._reader.readline()
            if not raw:
                _LOGGER.warning("MBX RIO SE connection closed for %s", self.name)
                break

            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            _LOGGER.debug("MBX RIO SE <- %s", line)
            self._apply_line(line)

    def _apply_line(self, line: str) -> None:
        version_match = _VERSION_RE.match(line)
        if version_match:
            self.protocol_version = version_match.group("version")
            self._notify()
            return

        match = _SOURCE_LINE_RE.match(line)
        if not match:
            return

        source_id = int(match.group("source_id"))
        if source_id != self.source_id:
            return

        key = match.group("key")
        value = match.group("value")

        self.state[key] = value
        self._notify()

    def _notify(self) -> None:
        for listener in list(self._listeners):
            with contextlib.suppress(Exception):
                listener()
