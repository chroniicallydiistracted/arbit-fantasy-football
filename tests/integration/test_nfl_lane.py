"""The NFL API lane against real PostgreSQL (OWN-041): discover, poll, detect, publish.

A fake client returns recorded responses: the week, its schedule, empty game summaries (as week 9
gave before kickoff) and CHI at SEA's real v2 game record from the fixture. The clock is set an
hour after kickoff, so the game is live by its own kickoff time even though the summaries don't
list it.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest
from arbit_data.errors import SourceError
from arbit_data.live import cadence, nfl_feed, store
from arbit_data.live.contracts import LivePlay
from arbit_data.live.feed import LiveFeed
from arbit_data.live.nfl_feed import STALE_SECONDS, NflFeed, nfl_primary
from arbit_data.live.nfl_log import LiveLog
from arbit_data.schema import (
    nfl_api_game,
    nfl_game,
    nfl_play_revision,
    nfl_team,
    outbox_event,
    source_health,
)
from sqlalchemy import func, insert, select, update

FIXTURE = json.loads(
    (Path(__file__).parents[2] / "tests/fixtures/live/nfl-api-chi-at-sea.example.json").read_text()
)
GAME_ID = FIXTURE["game"]["id"]
EVENT = "401873036"
KICKOFF = datetime(2026, 11, 3, 1, 15, tzinfo=UTC)
LIVE_GAME = {
    **FIXTURE["game"],
    "summary": {**FIXTURE["game"]["summary"], "phase": "INGAME"},
}


class FakeClient:
    def __init__(self, details: dict[str, Any], summaries: list[dict[str, Any]] | None = None):
        self.details, self.summaries, self.calls = details, summaries or [], []
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self.detail_error: SourceError | None = None
        self.summary_error: SourceError | None = None
        # What the real client keeps of a response: Varnish's cache headers among them.
        self.last = {
            "status": 200,
            "headers": {"age": "3", "cache-control": "max-age=5", "x-cache": "HIT"},
        }

    def get(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, bytes]:
        self.calls.append(path)
        self.queries.append((path, params or {}))
        if path.startswith("/football/v2/weeks/date/"):
            body: Any = {"season": 2026, "seasonType": "REG", "week": 8}
        elif path == "/football/v2/games/season/2026/seasonType/REG/week/8":
            body = {
                "games": [
                    {
                        "id": GAME_ID,
                        "time": "2026-11-03T01:15:00Z",
                        "date": "2026-11-03",
                        "homeTeam": {"currentLogo": "https://static.www.nfl.com/x/logos/SEA"},
                        "awayTeam": {"currentLogo": "https://static.www.nfl.com/x/logos/CHI"},
                    }
                ]
            }
        elif path == "/football/v2/stats/live/game-summaries":
            if self.summary_error is not None:
                raise self.summary_error
            body = {"data": self.summaries}
        elif path == f"/experience/v2/gamedetails/{GAME_ID}":
            if self.detail_error is not None:
                raise self.detail_error
            body = self.details
        else:
            raise AssertionError(path)
        return body, json.dumps(body, sort_keys=True).encode()


@pytest.fixture
def seeded(uow):
    now = KICKOFF - timedelta(days=1)
    with uow.engine.begin() as c:
        for espn_id, code, location, name in (
            ("26", "SEA", "Seattle", "Seahawks"),
            ("3", "CHI", "Chicago", "Bears"),
        ):
            c.execute(
                insert(nfl_team).values(
                    espn_id=espn_id,
                    entity_id=uuid4(),
                    abbreviation=code,
                    location=location,
                    name=name,
                    observed_at=now,
                )
            )
        c.execute(
            insert(nfl_game).values(
                event_id=EVENT,
                season=2026,
                season_type=2,
                week=8,
                phase="final",
                state_hash="0" * 64,
                payload={"home_team_id": "26", "away_team_id": "3", "date": "2026-11-03T01:15Z"},
                observed_at=now,
                changed_at=now,
                final_checks=0,
            )
        )
    return uow


def feed(uow, client: FakeClient, at: datetime, log: LiveLog | None = None) -> NflFeed:
    lane = NflFeed(
        uow, 2026, client=client, clock=lambda: at, live_log=log or LiveLog(enabled=False)
    )  # type: ignore[arg-type]
    lane.ids, lane.ids_at = FIXTURE["ids"], at  # the crosswalk, as the identity tables give it
    return lane


def test_a_kicked_off_game_is_discovered_read_and_published(seeded):
    uow = seeded
    at = KICKOFF + timedelta(hours=1)
    client = FakeClient(LIVE_GAME)
    wait = feed(uow, client, at).step()
    assert wait <= 1.0
    with uow.engine.connect() as c:
        link = c.execute(select(nfl_api_game.c.event_id, nfl_api_game.c.details_observed_at)).one()
        current = c.execute(
            select(nfl_play_revision.c.payload).where(
                nfl_play_revision.c.event_id == EVENT, nfl_play_revision.c.is_current
            )
        ).all()
        published = c.execute(select(outbox_event.c.event_type)).scalars().all()
        health = c.execute(
            select(source_health).where(source_health.c.source == "nfl.api.plays")
        ).one()
    assert link.event_id == EVENT and link.details_observed_at == at
    assert len(current) >= 150 and all(r.payload["source"] == "nfl" for r in current)
    assert "game.plays" in published
    assert health.consecutive_failures == 0 and health.cadence_seconds == 2


def test_an_unchanged_game_publishes_nothing_more(seeded):
    uow = seeded
    at = KICKOFF + timedelta(hours=1)
    client = FakeClient(LIVE_GAME)
    feed(uow, client, at).step()
    with uow.engine.connect() as c:
        before = c.scalar(select(func.count()).select_from(outbox_event))
    later = feed(uow, client, at + timedelta(seconds=6))
    later.week, later.discovered_at = ("REG", 8), at
    later.step()
    with uow.engine.connect() as c:
        after = c.scalar(select(func.count()).select_from(outbox_event))
    assert client.calls.count(f"/experience/v2/gamedetails/{GAME_ID}") == 2  # fetched again
    assert after == before  # same plays: no new revision, no event


def test_a_correction_to_an_earlier_play_is_published_as_one(seeded):
    uow = seeded
    at = KICKOFF + timedelta(hours=1)
    client = FakeClient(LIVE_GAME, [summary(1)])
    lane = feed(uow, client, at)
    lane.step()
    corrected = json.loads(json.dumps(LIVE_GAME))
    play = next(p for p in corrected["driveChart"]["plays"] if p["playType"] == "RUSH")
    play["playDescription"] = play["playDescription"].replace(" yard", " yards", 1) + " (corrected)"
    client.details = corrected
    lane.clock = lambda: at + timedelta(seconds=2)
    lane.step()
    with uow.engine.connect() as c:
        published = c.execute(select(outbox_event.c.event_type)).scalars().all()
    assert published.count("game.corrected") == 1


def test_the_espn_lane_leaves_a_game_the_nfl_lane_has_fresh(seeded):
    uow = seeded
    at = KICKOFF + timedelta(hours=1)
    feed(uow, FakeClient(LIVE_GAME), at).step()
    assert nfl_primary(uow, EVENT, at + timedelta(seconds=30))
    # Past the stale limit, ESPN's feed is the emergency fallback again.
    assert not nfl_primary(uow, EVENT, at + timedelta(seconds=STALE_SECONDS + 1))


def test_espns_own_timeouts_stop_showing_once_the_nfl_has_the_game(seeded):
    uow = seeded
    at = KICKOFF + timedelta(hours=1)
    espn_only = LivePlay.model_validate(
        {
            "event_id": EVENT,
            "provider_id": "4018730361741",  # ESPN's own ID; the NFL numbers this timeout 1756
            "sequence": "174100",
            "provider_type_id": None,
            "provider_type_text": "Timeout",
            "kind": "administrative",
            "text": "Timeout #1 by CHI at 01:12.",
            "period": 2,
            "clock": "1:12",
            "home_score": "3",
            "away_score": "13",
            "scoring_play": False,
            "score_value": "0",
            "cancelled": False,
            "modified_at": None,
            "wallclock": None,
            "participants": [],
            "start": {},
            "end": {},
            "can_connect_endpoints": False,
            "effects": ["administrative"],
            "point_after": None,
            "stat_yardage": None,
            "source_flags": {},
        }
    )
    store.publish_plays(uow, EVENT, (espn_only,), at - timedelta(minutes=5), body_hash="espn")
    feed(uow, FakeClient(FIXTURE["game"]), at).step()
    with uow.engine.connect() as c:
        still = c.scalar(
            select(nfl_play_revision.c.is_current).where(
                nfl_play_revision.c.play_id == "4018730361741"
            )
        )
    assert still is False


def test_an_empty_nfl_record_leaves_the_game_with_espn(seeded):
    """If the NFL's record has no plays yet, the NFL lane doesn't take the game over: ESPN keeps
    reading its plays, so the page never goes empty."""
    uow = seeded
    at = KICKOFF + timedelta(hours=1)
    slug = "bears-at-seahawks-2026-reg-8"
    empty = {
        **FIXTURE["game"],
        "driveChart": {"plays": []},
        "externalIds": [{"source": "slug", "id": slug}],
    }
    lane = feed(uow, FakeClient(empty), at)
    lane.step()
    assert not nfl_primary(uow, EVENT, at + timedelta(seconds=1))
    # The detail identifies the probe's by-slug route even before there are plays.
    with uow.engine.connect() as c:
        assert c.scalar(select(nfl_api_game.c.slug)) == slug
    lane.discover(at + timedelta(minutes=1))
    with uow.engine.connect() as c:
        assert c.scalar(select(nfl_api_game.c.slug)) == slug


def summary(offset: int) -> dict[str, Any]:
    return {
        "gameId": GAME_ID,
        "offset": offset,
        "phase": "INGAME",
        "quarter": "Q2",
        "clock": "05:30",
        "homeTeam": {"hasPossession": False, "score": {"total": 0}},
        "awayTeam": {"hasPossession": True, "score": {"total": 0}},
    }


def test_unchanged_summary_still_gets_fresh_details_every_two_seconds(seeded, monkeypatch):
    at = KICKOFF + timedelta(hours=1)
    now = at
    client = FakeClient(LIVE_GAME, [summary(1)])
    lane = feed(seeded, client, at)
    lane.clock = lambda: now
    detail_path = f"/experience/v2/gamedetails/{GAME_ID}"
    get = client.get

    def get_with_latency(path, params=None):
        nonlocal now
        response = get(path, params)
        if path == detail_path:
            now += timedelta(milliseconds=300)
        return response

    monkeypatch.setattr(client, "get", get_with_latency)
    lane.step()
    now = at + timedelta(seconds=1, milliseconds=999)
    lane.step()
    assert client.calls.count(detail_path) == 1
    now = at + timedelta(seconds=2)
    lane.step()
    assert client.calls.count(detail_path) == 2
    polling = [
        params
        for path, params in client.queries
        if path in (detail_path, "/football/v2/stats/live/game-summaries")
    ]
    assert len({p.get("_cache_probe") for p in polling if p.get("_cache_probe")}) == 4


def test_summary_failure_does_not_gate_active_detail_reads(seeded):
    at = KICKOFF + timedelta(hours=1)
    client = FakeClient(LIVE_GAME)
    client.summary_error = SourceError("NFL_API_UNREACHABLE")
    lane = feed(seeded, client, at)
    lane.step()
    lane.clock = lambda: at + timedelta(seconds=2)
    lane.step()
    assert client.calls.count(f"/experience/v2/gamedetails/{GAME_ID}") == 2
    assert nfl_primary(seeded, EVENT, at + timedelta(seconds=2))
    with seeded.engine.connect() as c:
        assert c.scalar(select(nfl_api_game.c.phase)) == "INGAME"


def test_provider_retry_after_pauses_fresh_requests(seeded):
    at = KICKOFF + timedelta(hours=1)
    client = FakeClient(LIVE_GAME)
    client.detail_error = SourceError("RATE_LIMITED", retry_after_seconds=17)
    lane = feed(seeded, client, at)
    lane.step()
    lane.clock = lambda: at + timedelta(seconds=16)
    lane.step()
    assert client.calls.count(f"/experience/v2/gamedetails/{GAME_ID}") == 1
    client.detail_error = None
    lane.clock = lambda: at + timedelta(seconds=17)
    lane.step()
    assert client.calls.count(f"/experience/v2/gamedetails/{GAME_ID}") == 2


def test_overlapping_games_fetch_details_concurrently(seeded, monkeypatch):
    at = KICKOFF + timedelta(hours=1)
    second_game, second_event = str(uuid4()), "401873038"
    with seeded.engine.begin() as c:
        first = c.execute(select(nfl_game).where(nfl_game.c.event_id == EVENT)).mappings().one()
        c.execute(insert(nfl_game).values(dict(first) | {"event_id": second_event}))
        for game, event in ((GAME_ID, EVENT), (second_game, second_event)):
            c.execute(
                insert(nfl_api_game).values(
                    game_id=game,
                    event_id=event,
                    season=2026,
                    season_type="REG",
                    week=8,
                    kickoff=KICKOFF,
                    observed_at=at,
                )
            )

    both_fetching = Barrier(2, timeout=3)
    keys = []

    class ParallelClient(FakeClient):
        def __init__(self):
            super().__init__(LIVE_GAME)

        def get(self, path, params=None):
            if not path.startswith("/experience/v2/gamedetails/"):
                return super().get(path, params)
            keys.append(params["_cache_probe"])
            both_fetching.wait()
            body = LIVE_GAME | {"id": path.rsplit("/", 1)[-1]}
            return body, json.dumps(body).encode()

    monkeypatch.setattr(nfl_feed, "NflApiClient", ParallelClient)
    lane = NflFeed(seeded, 2026, clock=lambda: at, live_log=LiveLog(enabled=False))
    lane.week, lane.discovered_at = ("REG", 8), at
    lane.ids, lane.ids_at = FIXTURE["ids"], at
    try:
        lane.step()
        assert len(set(keys)) == 2
        assert nfl_primary(seeded, EVENT, at) and nfl_primary(seeded, second_event, at)
    finally:
        if lane.detail_pool is not None:
            lane.detail_pool.shutdown()


def test_the_live_log_keeps_cache_headers_and_what_each_response_says(seeded, tmp_path):
    uow = seeded
    at = KICKOFF + timedelta(hours=1)
    feed(uow, FakeClient(FIXTURE["game"], [summary(7)]), at, LiveLog(tmp_path)).step()
    lines = [
        json.loads(line)
        for path in tmp_path.glob("*.jsonl")
        for line in path.read_text().splitlines()
    ]
    routes = {line["route"] for line in lines}
    assert {"week", "schedule", "summaries", "v2"} <= routes
    summaries = next(line for line in lines if line["route"] == "summaries")
    assert summaries["headers"]["age"] == "3" and summaries["games"][GAME_ID]["offset"] == 7
    record = next(line for line in lines if line["route"] == "v2")
    assert (
        record["count"] >= 150
        and record["newest_timed"]["whistle_at"]
        and record["reason"] == "active"
    )
    assert record["cache_key"] and summaries["cache_key"] != record["cache_key"]
    assert len(record["fingerprints"]) == record["count"]
    text = "\n".join(path.read_text() for path in tmp_path.glob("*.jsonl"))
    assert "Bearer" not in text and "accessToken" not in text


def test_final_summary_retries_failed_and_cached_live_details(seeded):
    at = KICKOFF + timedelta(hours=3)
    live = {**FIXTURE["game"], "summary": {"phase": "INGAME"}}
    client = FakeClient(live, [summary(1)])
    lane = feed(seeded, client, at)
    lane.step()

    client.summaries = [{**summary(2), "phase": "FINAL"}]
    client.detail_error = SourceError("NFL_API_UNREACHABLE")
    lane.clock = lambda: at + timedelta(seconds=2)
    lane.step()
    client.detail_error = None
    lane.clock = lambda: at + timedelta(seconds=7)
    lane.step()
    assert lane.summaries_due == at + timedelta(seconds=9)

    client.details = FIXTURE["game"]
    lane.clock = lambda: at + timedelta(seconds=9)
    lane.step()
    assert client.calls.count(f"/experience/v2/gamedetails/{GAME_ID}") == 4
    assert lane.summaries_due == at + timedelta(seconds=309)
    with seeded.engine.connect() as c:
        assert c.scalar(select(nfl_api_game.c.phase)) == "FINAL"


def test_confirmed_nfl_final_keeps_ownership_after_freshness_expires(seeded):
    at = KICKOFF + timedelta(hours=3)
    feed(seeded, FakeClient(FIXTURE["game"]), at).step()
    assert nfl_primary(seeded, EVENT, at + timedelta(hours=12))


def test_final_reconciles_a_mixed_replay_and_rejects_a_late_fallback(seeded):
    at = KICKOFF + timedelta(hours=3)
    feed(seeded, FakeClient(LIVE_GAME), at).step()
    payload = store.read_plays(seeded, EVENT, limit=1)[0]
    payload.pop("corrected")
    prior = LivePlay.model_validate(payload)
    espn = prior.model_copy(update={"source": None, "snap_at": None, "text": "Fallback"})
    extra = espn.model_copy(update={"provider_id": EVENT + "999999"})
    store.publish_plays(
        seeded,
        EVENT,
        (espn, extra),
        at + timedelta(seconds=91),
        body_hash="fallback",
        fallback=True,
    )
    assert {p["provider_id"] for p in store.read_plays(seeded, EVENT, limit=400)} >= {
        extra.provider_id
    }
    final_at = at + timedelta(seconds=93)
    feed(seeded, FakeClient(FIXTURE["game"]), final_at).step()
    later = final_at + timedelta(hours=12)
    assert not store.publish_plays(
        seeded, EVENT, (espn, extra), later, body_hash="fallback", fallback=True
    ).any
    active = store.read_plays(seeded, EVENT, limit=400)
    assert all(p["source"] == "nfl" and p["provider_id"] != extra.provider_id for p in active)
    with seeded.engine.connect() as c:
        retired = c.scalar(
            select(nfl_play_revision.c.is_current).where(
                nfl_play_revision.c.play_id == extra.provider_id
            )
        )
    assert retired is False


def test_late_final_summary_cannot_claim_a_live_detail_as_final(seeded):
    at = KICKOFF + timedelta(hours=7)
    client = FakeClient(LIVE_GAME, [{**summary(1), "phase": "FINAL"}])
    feed(seeded, client, at).step()
    assert not nfl_primary(seeded, EVENT, at + timedelta(seconds=STALE_SECONDS + 1))
    with seeded.engine.connect() as c:
        assert c.scalar(select(nfl_api_game.c.phase)) != "FINAL"


def test_a_live_poll_started_before_the_final_cannot_reopen_it(seeded):
    at = KICKOFF + timedelta(hours=3)
    client = FakeClient(LIVE_GAME, [summary(1)])
    stale = feed(seeded, client, at)
    stale.step()
    watched = stale._watched()[0]
    final_at = at + timedelta(seconds=2)
    feed(seeded, FakeClient(FIXTURE["game"]), final_at).step()

    stale.clock = lambda: at + timedelta(seconds=4)
    client.details = {**LIVE_GAME, "summary": {"phase": "HALFTIME"}}
    stale._poll_game(watched, {**summary(2), "phase": "HALFTIME"}, stale.clock())

    with seeded.engine.connect() as c:
        row = c.execute(select(nfl_api_game)).one()
        assert (row.phase, row.details_phase, row.details_observed_at) == (
            "FINAL",
            "FINAL",
            final_at,
        )
    assert nfl_primary(seeded, EVENT, at + timedelta(hours=12))


@pytest.mark.parametrize("problem", ["no_end", "truncated", "score_mismatch"])
def test_unusable_final_detail_leaves_the_game_available_to_fallback(seeded, problem):
    at = KICKOFF + timedelta(hours=3)
    final = json.loads(json.dumps(FIXTURE["game"]))
    if problem == "no_end":
        final["driveChart"]["plays"].pop()
    elif problem == "truncated":
        final["driveChart"]["plays"] = final["driveChart"]["plays"][-20:]
    else:
        final["summary"]["homeTeam"]["score"]["total"] = 18
    client = FakeClient(final, [{**summary(2), "phase": "FINAL"}])
    lane = feed(seeded, client, at)
    lane.step()
    assert not nfl_primary(seeded, EVENT, at)
    assert store.read_plays(seeded, EVENT) == []

    client.details = FIXTURE["game"]
    lane.clock = lambda: at + timedelta(seconds=2)
    lane.step()
    assert nfl_primary(seeded, EVENT, at + timedelta(hours=12))


def test_final_correction_retries_when_the_changed_summary_arrives_first(seeded):
    at = KICKOFF + timedelta(hours=3)
    client = FakeClient(FIXTURE["game"], [{**summary(1), "phase": "FINAL"}])
    lane = feed(seeded, client, at)
    lane.step()

    client.summaries = [{**summary(2), "phase": "FINAL"}]
    client.details = LIVE_GAME  # this detail has not caught up with the new summary
    lane.clock = lambda: at + timedelta(minutes=5)
    lane.step()

    corrected = json.loads(json.dumps(FIXTURE["game"]))
    play = next(p for p in corrected["driveChart"]["plays"] if p["playType"] == "RUSH")
    play["playDescription"] += " (corrected)"
    client.details = corrected
    lane.clock = lambda: at + timedelta(minutes=10)
    lane.step()
    assert any(
        p["text"].endswith(" (corrected)") for p in store.read_plays(seeded, EVENT, limit=400)
    )


def test_an_unconfirmed_final_is_recovered_after_its_week_rolls_over(seeded):
    at = KICKOFF + timedelta(days=7)
    with seeded.engine.begin() as c:
        c.execute(
            insert(nfl_api_game).values(
                game_id=GAME_ID,
                event_id=EVENT,
                season=2026,
                season_type="REG",
                week=7,
                kickoff=KICKOFF,
                phase="FINAL",
                details_observed_at=KICKOFF + timedelta(hours=3),
                observed_at=KICKOFF + timedelta(hours=3),
            )
        )
    lane = feed(seeded, FakeClient(FIXTURE["game"]), at)
    lane.week, lane.discovered_at = ("REG", 8), at
    lane.step()
    assert nfl_primary(seeded, EVENT, at + timedelta(hours=12))


def test_espn_shadow_reads_on_its_own_cadence_then_yields_to_fallback(seeded, monkeypatch):
    at = KICKOFF + timedelta(hours=1)
    feed(seeded, FakeClient(LIVE_GAME), at).step()
    with seeded.engine.begin() as c:
        c.execute(update(nfl_game).where(nfl_game.c.event_id == EVENT).values(phase="in_progress"))
    espn = LiveFeed(seeded, Mock(), 2026, clock=lambda: at)
    shadow = Mock()
    fallback = Mock(return_value=store.PlayChange())
    monkeypatch.setattr(espn, "shadow_plays", shadow)
    monkeypatch.setattr(espn, "read_plays", fallback)
    monkeypatch.setattr(espn, "read_summary", Mock())

    espn._games_step(at)
    espn._games_step(at + timedelta(seconds=1))
    shadow.assert_called_once_with(EVENT)
    espn._games_step(at + timedelta(seconds=cadence.play_seconds(1)))
    assert shadow.call_count == 2
    fallback.assert_not_called()
    espn._games_step(at + timedelta(seconds=STALE_SECONDS + 1))
    fallback.assert_called_once_with(EVENT)


def test_animation_uses_the_try_clock_and_keeps_the_final_board(seeded):
    from arbit_data.live import animation

    at = KICKOFF + timedelta(hours=3)
    feed(seeded, FakeClient(FIXTURE["game"]), at).step()
    data = animation.build(seeded, EVENT)
    assert data is not None
    tried = next(e for e in data["entries"] if e["part"] == "try")
    assert tried["snap_at"] == "2026-11-03T01:31:27Z"
    assert tried["whistle_at"] is None
    assert tried["clock"] == tried["board"].before.clock == "5:25"
    assert tried["board"].after.home.score == 0
    assert data["entries"][-1]["board"].after.status == "FINAL"
