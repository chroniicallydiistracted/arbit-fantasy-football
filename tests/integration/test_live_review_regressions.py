import hashlib
import json
from datetime import UTC, datetime, timedelta
from functools import partial

from arbit_data.espn.gate import DatabaseGate
from arbit_data.espn.transport import SourceReceipt
from arbit_data.live.normalize import normalize_play
from arbit_data.live.reader import LiveReader, normalize_collection
from arbit_data.live.replay import PlaySnapshot, merge_observations
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.public_sources.requests import build_source_request
from arbit_data.public_sources.service import SourceService
from arbit_data.public_sources.transport import PublicResponse
from arbit_data.schema import public_source_refresh
from arbit_worker.source_commands import inspect_live, replay_observations
from sqlalchemy import select

T = datetime(2026, 10, 31, tzinfo=UTC)


def play(pid="12301", cancelled=False):
    return {
        "id": pid,
        "sequenceNumber": "1",
        "type": {"text": "Penalty" if cancelled else "Rush"},
        "text": "No Play." if cancelled else "Synthetic rush",
        "modified": "2026-10-30T00:00:00Z",
    }


def service(uow, store, clock, fetch, monkeypatch):
    class Responses:
        def fetch(self, request):
            payload = fetch(request)
            body = json.dumps(payload).encode()
            return PublicResponse(
                body,
                payload,
                SourceReceipt(request.url, clock[0], hashlib.sha256(body).hexdigest(), len(body)),
            )

    # Preserve real PostgreSQL gate logic; advance a fake clock instead of delaying fake I/O.
    def gate(uow, *, provider):
        def advance(seconds):
            clock[0] += timedelta(seconds=seconds)

        return DatabaseGate(uow, provider=provider, clock=lambda: clock[0], sleep=advance)

    monkeypatch.setattr("arbit_data.public_sources.service.DatabaseGate", gate)
    return SourceService(uow, store, Responses(), clock=lambda: clock[0])


def test_mixed_page_offline_replay_cannot_revert_newer_correction(uow, tmp_path, monkeypatch):
    store = ObjectStore(tmp_path)
    clock = [T]

    def fetch(req):
        return {
            "count": 2,
            "pageIndex": req.page,
            "pageCount": 2,
            "pageSize": 1,
            "items": [play("12301" if req.page == 1 else "12302")],
        }

    source = service(uow, store, clock, fetch, monkeypatch)
    first = source.acquire(
        build_source_request("espn.plays", event_id="123"),
        partial(normalize_collection, event_id="123", season=2026, page=1),
    )
    clock[0] = T + timedelta(seconds=60)
    second = source.acquire(
        build_source_request("espn.plays", event_id="123", page=2),
        partial(normalize_collection, event_id="123", season=2026, page=2),
    )
    replayed = replay_observations(uow, store, [first.hash, second.hash])
    previous = PlaySnapshot(
        "123",
        T + timedelta(seconds=30),
        (
            normalize_play(play(cancelled=True), "123", 2026),
            normalize_play(play("12302"), "123", 2026),
        ),
    )
    result = merge_observations(previous, replayed)
    assert next(p for p in result.snapshot.plays if p.provider_id == "12301").cancelled


def test_malformed_reference_records_failure_and_continues_other_game(uow, tmp_path, monkeypatch):
    clock = [T]
    store = ObjectStore(tmp_path)

    def game(event):
        return {
            "id": event,
            "season": {"year": 2026, "type": 2},
            "competitions": [
                {
                    "id": event,
                    "competitors": [
                        {"homeAway": "home", "id": "1"},
                        {"homeAway": "away", "id": "2"},
                    ],
                    "status": {
                        "type": {"name": "STATUS_FINAL", "state": "post", "completed": True}
                    },
                }
            ],
        }

    def fetch(req):
        if req.kind == "espn.scoreboard":
            return {
                "season": {"year": 2026, "type": 2},
                "week": {"number": 8},
                "events": [game("123"), game("124")],
            }
        if req.kind == "espn.summary":
            return {"header": game(req.event_id)}
        if req.event_id == "123":
            return {"$ref": 42}
        return {
            "count": 1,
            "pageIndex": 1,
            "pageCount": 1,
            "pageSize": 300,
            "items": [play("12401")],
        }

    source = service(uow, store, clock, fetch, monkeypatch)
    report = inspect_live(LiveReader(source), uow, 2026, 8, ["123", "124"])
    assert not report["success"] and report["games"][0]["error"] == "VALIDATION_FAILED"
    assert report["games"][1]["plays"] == 1
    with uow.engine.connect() as c:
        row = (
            c.execute(
                select(public_source_refresh).where(
                    public_source_refresh.c.request_key
                    == build_source_request("espn.plays", event_id="123").key
                )
            )
            .mappings()
            .one()
        )
    assert row["last_error"] == "VALIDATION_FAILED" and row["token"] is None
