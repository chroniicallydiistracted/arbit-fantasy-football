"""Session-bound server-sent events from the outbox, plus small read helpers.

One hub per API process polls the outbox once a second while anyone is connected, so the cost does
not grow with members. Events only say what changed; clients read it through authorized routes.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from arbit_data import events as outbox
from arbit_data.db import UnitOfWork
from arbit_data.events import Event

HEARTBEAT_SECONDS = 20.0
POLL_SECONDS = 1.0
QUEUE_LIMIT = 256
# Sentinel: this subscriber fell behind and has to re-read everything.
OVERFLOW = None


def frame(event: Event) -> str:
    return (
        f"id: {event.sequence}\nevent: {event.event_type}\n"
        f"data: {json.dumps(event.payload, separators=(',', ':'), default=str)}\n\n"
    )


def parse_cursor(value: str | None) -> int | None:
    if value is None or re.fullmatch(r"[0-9]{1,18}", value) is None:
        return None
    return int(value)


class EventHub:
    def __init__(
        self,
        uow: UnitOfWork,
        *,
        poll_seconds: float = POLL_SECONDS,
        queue_limit: int = QUEUE_LIMIT,
    ):
        self.uow, self.poll_seconds, self.queue_limit = uow, poll_seconds, queue_limit
        self.subscribers: set[asyncio.Queue[Any]] = set()
        self.task: asyncio.Task[None] | None = None
        self.last = 0

    async def subscribe(self) -> asyncio.Queue[Any]:
        queue: asyncio.Queue[Any] = asyncio.Queue(self.queue_limit)
        self.subscribers.add(queue)
        if self.task is None or self.task.done():
            self.last = await asyncio.to_thread(outbox.latest_sequence, self.uow)
            self.task = asyncio.create_task(self._run())
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Any]) -> None:
        self.subscribers.discard(queue)

    def publish(self, event: Event) -> None:
        for queue in list(self.subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop the backlog and tell this subscriber to re-read. Others are unaffected.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(OVERFLOW)

    async def _run(self) -> None:
        while self.subscribers:
            try:
                for event in await asyncio.to_thread(outbox.read_after, self.uow, self.last):
                    self.last = event.sequence
                    self.publish(event)
            except Exception:  # noqa: BLE001
                # Storage trouble must not end streams; each stream revalidates on its heartbeat.
                await asyncio.sleep(self.poll_seconds * 4)
            await asyncio.sleep(self.poll_seconds)


async def event_stream(
    hub: EventHub,
    cursor: int | None,
    still_authorized: Callable[[], Awaitable[bool]],
    *,
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """Replay from the client's cursor, then follow live. Closes when the session stops being valid."""
    # Subscribe before reading history so nothing falls between replay and live.
    queue = await hub.subscribe()
    try:
        yield "retry: 3000\n\n"
        last = cursor or 0
        if cursor is not None:
            available = await asyncio.to_thread(outbox.replay_available, hub.uow, cursor)
            if not available:
                yield "event: snapshot.required\ndata: {}\n\n"
            else:
                for event in await asyncio.to_thread(outbox.read_after, hub.uow, cursor):
                    last = event.sequence
                    yield frame(event)
        while True:
            try:
                next_event: Event | None = await asyncio.wait_for(queue.get(), heartbeat_seconds)
            except TimeoutError:
                if not await still_authorized():
                    yield "event: session.ended\ndata: {}\n\n"
                    return
                yield ": heartbeat\n\n"
                continue
            if next_event is None:
                yield "event: snapshot.required\ndata: {}\n\n"
                continue
            if next_event.sequence > last:
                last = next_event.sequence
                yield frame(next_event)
    finally:
        hub.unsubscribe(queue)


_DEVICE_OS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("Windows", "Windows"),
    ("Mac OS X", "Mac"),
    ("CrOS", "Chromebook"),
    ("Linux", "Linux"),
)
_DEVICE_BROWSER = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("Chrome/", "Chrome"),
    ("CriOS/", "Chrome"),
    ("Safari/", "Safari"),
)


def describe_device(user_agent: str | None) -> str | None:
    """A short label so a member can recognize a session. The raw header is never stored."""
    if not user_agent:
        return None
    browser = next((name for mark, name in _DEVICE_BROWSER if mark in user_agent), None)
    system = next((name for mark, name in _DEVICE_OS if mark in user_agent), None)
    if browser and system:
        return f"{browser} on {system}"
    return browser or system
