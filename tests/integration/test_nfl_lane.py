"""The NFL API lane against real PostgreSQL (OWN-041): discover, poll, detect, publish.

A fake client returns recorded responses: the week, its schedule, empty game summaries (as week 9
gave before kickoff) and CHI at SEA's real v2 game record from the fixture. The clock is set an
hour after kickoff, so the game is live by its own kickoff time even though the summaries don't
list it.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest
from arbit_data.errors import SourceError
from arbit_data.live import cadence, store
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


class FakeClient:
    def __init__(self, details: dict[str, Any], summaries: list[dict[str, Any]] | None = None):
        self.details, self.summaries, self.calls = details, summaries or [], []
        self.detail_error: SourceError | None = None
        # What the real client keeps of a response: Varnish's cache headers among them.
        self.last = {
            "status": 200,
            "headers": {"age": "3", "cache-control": "max-age=5", "x-cache": "HIT"},
        }

    def get(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, bytes]:
        self.calls.append(path)
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
    client = FakeClient(FIXTURE["game"])
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
    client = FakeClient(FIXTURE["game"])
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
    feed(uow, FakeClient(FIXTURE["game"]), at).step()
    corrected = json.loads(json.dumps(FIXTURE["game"]))
    play = next(p for p in corrected["driveChart"]["plays"] if p["playType"] == "RUSH")
    play["playDescription"] = play["playDescription"].replace(" yard", " yards", 1) + " (corrected)"
    feed(uow, FakeClient(corrected), at + timedelta(seconds=30)).step()
    with uow.engine.connect() as c:
        published = c.execute(select(outbox_event.c.event_type)).scalars().all()
    assert published.count("game.corrected") == 1


def test_the_espn_lane_leaves_a_game_the_nfl_lane_has_fresh(seeded):
    uow = seeded
    at = KICKOFF + timedelta(hours=1)
    feed(uow, FakeClient(FIXTURE["game"]), at).step()
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


def test_a_summary_change_keeps_fetching_a_stale_record_until_it_catches_up(seeded):
    """The summaries are cached for 5 seconds and a record can be cached longer. When the summary
    moves but the record hasn't, the collector fetches the record again each poll until it does."""
    uow = seeded
    at = KICKOFF + timedelta(hours=1)
    older = {
        **FIXTURE["game"],
        "driveChart": {"plays": FIXTURE["game"]["driveChart"]["plays"][:-5]},
    }
    client = FakeClient(older, [summary(1)])
    lane = feed(uow, client, at)
    lane.step()  # the summary appears: the record is read
    reads = lambda: client.calls.count(f"/experience/v2/gamedetails/{GAME_ID}")  # noqa: E731
    assert reads() == 1
    client.summaries = [summary(2)]  # a new play: the summary moves, the record is still cached
    lane.clock = lambda: at + timedelta(seconds=2)
    lane.summaries_due = None
    lane.step()
    assert reads() == 2 and GAME_ID in lane.chasing
    lane.clock = lambda: at + timedelta(seconds=4)
    lane.summaries_due = None
    lane.step()  # still cached: fetched again
    assert reads() == 3
    client.details = FIXTURE["game"]  # the record catches up
    lane.clock = lambda: at + timedelta(seconds=6)
    lane.summaries_due = None
    lane.step()
    assert reads() == 4 and GAME_ID not in lane.chasing


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
        and record["reason"] == "summary"
    )
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


def test_espn_shadow_reads_on_its_own_cadence_then_yields_to_fallback(seeded, monkeypatch):
    at = KICKOFF + timedelta(hours=1)
    feed(seeded, FakeClient(FIXTURE["game"]), at).step()
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
