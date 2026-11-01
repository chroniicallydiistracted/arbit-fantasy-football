import asyncio
from datetime import UTC, datetime

import pytest
from arbit_api import realtime
from arbit_api.realtime import EventHub, describe_device, event_stream, frame, parse_cursor
from arbit_data import events as outbox
from arbit_data.events import Event


class FakeLog:
    """In-memory outbox behind the same read functions the hub uses."""

    def __init__(self, monkeypatch, rows=(), available=True):
        self.rows, self.available = list(rows), available
        monkeypatch.setattr(
            outbox,
            "read_after",
            lambda _uow, after, limit=500: [e for e in self.rows if e.sequence > after][:limit],
        )
        monkeypatch.setattr(
            outbox, "latest_sequence", lambda _uow: self.rows[-1].sequence if self.rows else 0
        )
        monkeypatch.setattr(outbox, "replay_available", lambda _uow, _c: self.available)


def event(sequence: int, kind: str = "games.updated") -> Event:
    return Event(sequence, kind, {"n": sequence})


async def always() -> bool:
    return True


async def collect(stream, count: int) -> list[str]:
    frames = []
    async for item in stream:
        frames.append(item)
        if len(frames) >= count:
            await stream.aclose()
            break
    return frames


def test_frames_are_well_formed_and_cursors_are_strict():
    assert frame(event(7)) == 'id: 7\nevent: games.updated\ndata: {"n":7}\n\n'
    assert parse_cursor("12") == 12
    assert parse_cursor(None) is None
    for hostile in ("-1", "1;drop", "1 2", "", "9" * 40):
        assert parse_cursor(hostile) is None


def test_reconnect_replays_only_what_was_missed(monkeypatch):
    FakeLog(monkeypatch, [event(1), event(2), event(3)])

    async def run():
        hub = EventHub(None, poll_seconds=0.01)
        frames = await collect(event_stream(hub, 1, always, heartbeat_seconds=5), 3)
        return frames

    frames = asyncio.run(run())
    assert frames[0].startswith("retry:")
    assert [f.split("\n")[0] for f in frames[1:]] == ["id: 2", "id: 3"]


def test_expired_cursor_tells_the_client_to_read_everything_again(monkeypatch):
    FakeLog(monkeypatch, [event(50)], available=False)

    async def run():
        hub = EventHub(None, poll_seconds=0.01)
        return await collect(event_stream(hub, 3, always, heartbeat_seconds=5), 2)

    assert "snapshot.required" in asyncio.run(run())[1]


def test_new_events_reach_every_subscriber_once_without_replaying_history(monkeypatch):
    log = FakeLog(monkeypatch, [event(1)])

    async def run():
        hub = EventHub(None, poll_seconds=0.01)
        one = event_stream(hub, None, always, heartbeat_seconds=5)
        two = event_stream(hub, None, always, heartbeat_seconds=5)
        results = asyncio.gather(collect(one, 2), collect(two, 2))
        await asyncio.sleep(0.05)
        log.rows.append(event(2))
        return await asyncio.wait_for(results, 3)

    first, second = asyncio.run(run())
    assert [f.split("\n")[0] for f in first[1:]] == ["id: 2"]
    assert [f.split("\n")[0] for f in second[1:]] == ["id: 2"]


def test_stream_closes_when_the_session_stops_being_valid(monkeypatch):
    FakeLog(monkeypatch)

    async def revoked() -> bool:
        return False

    async def run():
        hub = EventHub(None, poll_seconds=0.01)
        return [f async for f in event_stream(hub, None, revoked, heartbeat_seconds=0.02)]

    frames = asyncio.run(asyncio.wait_for(run(), 3))
    assert "session.ended" in frames[-1], "a revoked member must lose the stream"


def test_valid_session_gets_heartbeats_to_hold_the_connection_open(monkeypatch):
    FakeLog(monkeypatch)

    async def run():
        hub = EventHub(None, poll_seconds=0.01)
        return await collect(event_stream(hub, None, always, heartbeat_seconds=0.02), 3)

    assert asyncio.run(run())[-1] == ": heartbeat\n\n"


def test_a_slow_client_is_told_to_refetch_and_cannot_block_others(monkeypatch):
    FakeLog(monkeypatch)

    async def run():
        hub = EventHub(None, poll_seconds=10, queue_limit=2)
        slow, healthy = await hub.subscribe(), await hub.subscribe()
        for number in range(1, 4):
            hub.publish(event(number))
            await healthy.get()
        queued = [slow.get_nowait() for _ in range(slow.qsize())]
        for queue in (slow, healthy):
            hub.unsubscribe(queue)
        hub.task.cancel()
        return queued

    assert realtime.OVERFLOW in asyncio.run(run())


def test_hub_stops_polling_when_nobody_is_connected(monkeypatch):
    FakeLog(monkeypatch)

    async def run():
        hub = EventHub(None, poll_seconds=0.01)
        queue = await hub.subscribe()
        hub.unsubscribe(queue)
        await asyncio.wait_for(hub.task, 2)
        return hub.task.done()

    assert asyncio.run(run())


@pytest.mark.parametrize(
    ("agent", "label"),
    [
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebKit/537.36 Chrome/149.0 Safari/537.36",
            "Chrome on Windows",
        ),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Version/18.0 Mobile Safari/604.1",
            "Safari on iPhone",
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
            "Firefox on Linux",
        ),
        ("curl/8.0", None),
        (None, None),
    ],
)
def test_device_label_is_recognizable_and_never_the_raw_header(agent, label):
    assert describe_device(agent) == label


def test_event_payload_times_serialize(monkeypatch):
    FakeLog(monkeypatch)
    assert "2026" in frame(Event(1, "x", {"at": datetime(2026, 1, 1, tzinfo=UTC)}))
