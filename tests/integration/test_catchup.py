"""Catch-up after downtime (ENG-052) against real PostgreSQL.

The scenario is the one seen on 2026-11-22: the worker began in week 9, nothing ran during
week 10, and week 11 is the live week. A fake ESPN transport serves week 10's scoreboard and
summary; a fake NFL client serves the week's schedule and CHI at SEA's real final game record
from the fixture, standing in for a week 10 game.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from arbit_data import freshness
from arbit_data.errors import SourceError
from arbit_data.live import store
from arbit_data.live.feed import LiveFeed
from arbit_data.live.nfl_feed import DISCOVER_SECONDS, IDLE_SECONDS, RELINK_SECONDS, NflFeed
from arbit_data.live.nfl_log import LiveLog
from arbit_data.public_sources.requests import SourceRequest
from arbit_data.public_sources.transport import PublicResponse
from arbit_data.schema import nfl_api_game, nfl_game, nfl_play_revision, nfl_schedule_game, nfl_team
from arbit_worker import catchup
from arbit_worker.daemon import CatchupLane
from sqlalchemy import func, insert, select

FIXTURE = json.loads(
    (Path(__file__).parents[2] / "tests/fixtures/live/nfl-api-chi-at-sea.example.json").read_text()
)
GAME_ID = FIXTURE["game"]["id"]
MISSED = "401873036"  # CHI at SEA, played as if in week 10
MISSED_KICKOFF = datetime(2026, 11, 3, 1, 15, tzinfo=UTC)
WEEK9, WEEK11 = "401900009", "401900011"
NOW = datetime(2026, 11, 22, 23, 0, tzinfo=UTC)


def espn_event(event_id: str, date: str, state: str = "post") -> dict[str, Any]:
    names = {"post": "STATUS_FINAL", "in": "STATUS_IN_PROGRESS", "pre": "STATUS_SCHEDULED"}
    status = {
        "period": 4,
        "displayClock": "0:00",
        "type": {"name": names[state], "state": state, "completed": state == "post"},
    }
    competitors = [
        {"homeAway": "home", "id": "26", "score": "20"},
        {"homeAway": "away", "id": "3", "score": "17"},
    ]
    return {
        "id": event_id,
        "date": date,
        "season": {"year": 2026, "type": 2},
        "competitions": [
            {"id": event_id, "date": date, "status": status, "competitors": competitors}
        ],
    }


def espn_board(week: int, *events: dict[str, Any]) -> dict[str, Any]:
    return {"season": {"year": 2026, "type": 2}, "week": {"number": week}, "events": list(events)}


class FakeEspn:
    def __init__(self, responses: dict[str, Any]):
        self.responses, self.requests = responses, []

    def fetch(self, request: SourceRequest) -> PublicResponse:
        self.requests.append(request.kind)
        value = self.responses.get(request.kind)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise SourceError("NOT_FOUND")
        return PublicResponse(json.dumps(value).encode(), value, None)  # type: ignore[arg-type]


class OpenGate:
    def request(self):
        from contextlib import nullcontext

        return nullcontext()


class FakeNfl:
    def __init__(self, week: int = 10):
        self.week, self.calls = week, []

    def get(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, bytes]:
        self.calls.append(path)
        if path.startswith("/football/v2/weeks/date/"):
            body: Any = {"season": 2026, "seasonType": "REG", "week": self.week}
        elif path == f"/football/v2/games/season/2026/seasonType/REG/week/{self.week}":
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
            body = {"data": []}
        elif path == f"/experience/v2/gamedetails/{GAME_ID}":
            body = FIXTURE["game"]
        else:
            raise AssertionError(path)
        return body, json.dumps(body, sort_keys=True).encode()


def schedule(c, event_id: str, period: int, kickoff: datetime) -> None:
    c.execute(
        insert(nfl_schedule_game).values(
            event_id=event_id,
            season=2026,
            scoring_period=period,
            home_espn_id="26",
            away_espn_id="3",
            kickoff=kickoff,
            observed_at=NOW - timedelta(days=30),
        )
    )


def stored_game(c, event_id: str, week: int, phase: str, *, complete: bool, at: datetime) -> None:
    c.execute(
        insert(nfl_game).values(
            event_id=event_id,
            season=2026,
            season_type=2,
            week=week,
            phase=phase,
            state_hash="0" * 64,
            payload={"home_team_id": "26", "away_team_id": "3", "date": at.isoformat()},
            observed_at=at,
            changed_at=at,
            summary_observed_at=at if complete else None,
            plays_observed_at=at if complete else None,
            final_at=at if phase == "final" else None,
            final_checks=3 if complete else 0,
        )
    )


def seed(uow, *, live_week_phase: str = "final") -> None:
    """Week 9 complete, week 10 never read, week 11 the live week."""
    week9 = MISSED_KICKOFF - timedelta(days=7)
    week11 = datetime(2026, 11, 20, 1, 15, tzinfo=UTC)
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
                    observed_at=week9,
                )
            )
        schedule(c, WEEK9, 9, week9)
        schedule(c, MISSED, 10, MISSED_KICKOFF)
        schedule(c, WEEK11, 11, week11)
        stored_game(c, WEEK9, 9, "final", complete=True, at=week9 + timedelta(hours=4))
        stored_game(c, WEEK11, 11, live_week_phase, complete=False, at=week11)
        # The NFL lane began in week 9, so catch-up adds NFL records from week 9 on.
        c.execute(
            insert(nfl_api_game).values(
                game_id="week-9-game",
                season=2026,
                season_type="REG",
                week=9,
                event_id=WEEK9,
                details_phase="FINAL",
                details_observed_at=week9 + timedelta(hours=4),
                observed_at=week9,
            )
        )


def test_weeks_before_the_nfl_lane_began_keep_their_espn_record(uow, tmp_path):
    """Week 8 was reviewed with ESPN's plays; catch-up must not hand it to a new source."""
    seed(uow)
    with uow.engine.begin() as c:
        c.execute(nfl_api_game.delete())
    espn = missed_week_espn()
    live, nfl = feeds(uow, espn)
    outcome = catchup.run(uow, 2026, live=live, nfl=nfl, trigger="test", root=tmp_path)
    assert outcome.recovered == 1 and nfl.client.calls == []  # type: ignore[attr-defined]
    assert espn.requests.count("espn.plays") == 1


def feeds(uow, espn: FakeEspn, clock=lambda: NOW) -> tuple[LiveFeed, NflFeed]:
    live = LiveFeed(uow, espn, 2026, gate=OpenGate(), clock=clock)
    nfl = NflFeed(uow, 2026, client=FakeNfl(), clock=clock, live_log=LiveLog(enabled=False))  # type: ignore[arg-type]
    nfl.ids, nfl.ids_at = FIXTURE["ids"], NOW
    return live, nfl


def missed_week_espn() -> FakeEspn:
    event = espn_event(MISSED, "2026-11-03T01:15Z")
    summary = {"header": {**event, "season": {"year": 2026, "type": 2}}, "boxscore": {}}
    return FakeEspn(
        {
            "espn.scoreboard": espn_board(10, event),
            "espn.summary": summary,
            "espn.plays": {
                "count": 0,
                "pageIndex": 1,
                "pageCount": 1,
                "pageSize": 300,
                "items": [],
            },
        }
    )


def test_only_finished_games_outside_the_live_week_since_capture_began_are_outstanding(uow):
    seed(uow)
    with uow.engine.begin() as c:
        schedule(c, "401900003", 3, MISSED_KICKOFF - timedelta(days=49))  # before capture began
        schedule(c, "401900099", 10, NOW - timedelta(hours=2))  # still being played
    plan = catchup.outstanding_games(uow, 2026, NOW)
    assert [(g.event_id, g.period, g.stored) for g in plan] == [(MISSED, 10, False)]
    everything = catchup.outstanding_games(uow, 2026, NOW, from_period=1)
    assert [g.event_id for g in everything] == ["401900003", MISSED]


def test_playoff_periods_are_left_to_the_live_lanes(uow):
    """ESPN numbers playoff games as scoring periods 19 and later; catch-up reads only the regular
    season's 18 weeks, even with the live week in January."""
    seed(uow)
    with uow.engine.begin() as c:
        schedule(c, "401900019", 19, MISSED_KICKOFF + timedelta(days=63))
    later = MISSED_KICKOFF + timedelta(days=70)
    assert [g.period for g in catchup.outstanding_games(uow, 2026, later)] == [10]


def test_a_game_stored_mid_game_before_the_worker_stopped_is_outstanding(uow):
    seed(uow)
    with uow.engine.begin() as c:
        stored_game(c, MISSED, 10, "in_progress", complete=False, at=MISSED_KICKOFF)
    [game] = catchup.outstanding_games(uow, 2026, NOW)
    assert game.stored and not game.final


def test_a_recovered_past_week_never_becomes_the_live_schedule(uow):
    seed(uow)
    later = NOW + timedelta(minutes=5)
    live, _ = feeds(uow, missed_week_espn(), clock=lambda: later)
    live.read_week_board(10)
    assert {t.event_id for t in store.game_timings(uow, 2026)} == {WEEK11}


def test_catchup_recovers_the_missed_week_and_records_when_it_was_played(uow, tmp_path):
    seed(uow)
    espn = missed_week_espn()
    live, nfl = feeds(uow, espn)
    gaps = [{"source": "espn.league", "state": "behind", "lastSuccessAt": "2026-11-10T18:06:00Z"}]
    outcome = catchup.run(
        uow, 2026, live=live, nfl=nfl, trigger="test", gaps=gaps, root=tmp_path, clock=lambda: NOW
    )
    assert (outcome.weeks, outcome.recovered, outcome.failed) == (1, 1, 0)
    assert outcome.remaining_periods == () and outcome.stopped is None
    with uow.engine.connect() as c:
        row = c.execute(select(nfl_game).where(nfl_game.c.event_id == MISSED)).one()
        details = c.scalar(
            select(nfl_api_game.c.details_phase).where(nfl_api_game.c.game_id == GAME_ID)
        )
        plays = c.scalar(
            select(func.count())
            .select_from(nfl_play_revision)
            .where(nfl_play_revision.c.event_id == MISSED)
        )
    assert row.phase == "final" and row.summary_observed_at == NOW
    assert row.final_checks == 3, "a read days after the whistle is already final"
    assert details in ("FINAL", "FINAL_OVERTIME") and plays > 0, "the NFL record owns the plays"
    assert "espn.plays" not in espn.requests
    [line] = (tmp_path / catchup.RECEIPTS).read_text().splitlines()
    receipt = json.loads(line)
    [week] = receipt["weeks"]
    [game] = week["games"]
    assert week["period"] == 10 and receipt["sourcesBehindAtStart"] == gaps
    assert game == {
        "eventId": MISSED,
        "kickoff": MISSED_KICKOFF.isoformat(),
        "outcome": "recovered",
        "plays": "nfl",
        "readAt": NOW.isoformat(),
    }
    assert "payload" not in line and str(tmp_path) not in line


def test_espn_keeps_the_plays_when_the_nfl_record_is_unavailable(uow, tmp_path):
    seed(uow)
    espn = missed_week_espn()
    live, nfl = feeds(uow, espn)

    def unavailable(path, params=None):
        raise SourceError("UNAVAILABLE")

    nfl.client.get = unavailable  # type: ignore[method-assign]
    outcome = catchup.run(uow, 2026, live=live, nfl=nfl, trigger="test", root=tmp_path)
    assert outcome.recovered == 1 and espn.requests.count("espn.plays") == 1
    week = json.loads((tmp_path / catchup.RECEIPTS).read_text())["weeks"][0]
    assert week["nfl"] == {"error": "UNAVAILABLE"} and week["games"][0]["plays"] == "espn"


def test_a_source_asking_arbit_to_wait_stops_the_run_and_leaves_the_week_outstanding(uow, tmp_path):
    seed(uow)
    espn = missed_week_espn()
    espn.responses["espn.summary"] = SourceError("RATE_LIMITED", status=429)
    live, nfl = feeds(uow, espn)
    outcome = catchup.run(uow, 2026, live=live, nfl=nfl, trigger="test", root=tmp_path)
    assert outcome.stopped == "RATE_LIMITED" and outcome.remaining_periods == (10,)


def test_the_lane_waits_while_a_slate_is_active(uow, tmp_path):
    seed(uow, live_week_phase="in_progress")
    espn = missed_week_espn()
    live, nfl = feeds(uow, espn)
    lane = CatchupLane(uow, 2026, live=live, nfl=nfl, clock=lambda: NOW, root=tmp_path)
    assert lane.step() == CatchupLane.DEFER_SECONDS
    assert espn.requests == [] and nfl.client.calls == []  # type: ignore[attr-defined]


def test_the_lane_recovers_one_week_then_rests(uow, tmp_path):
    seed(uow)
    live, nfl = feeds(uow, missed_week_espn())
    lane = CatchupLane(uow, 2026, live=live, nfl=nfl, clock=lambda: NOW, root=tmp_path)
    assert lane.step() == CatchupLane.IDLE_SECONDS
    assert catchup.outstanding_games(uow, 2026, NOW) == []
    assert lane.step() == CatchupLane.IDLE_SECONDS
    assert len((tmp_path / catchup.RECEIPTS).read_text().splitlines()) == 1


def test_the_lane_records_sources_that_were_behind_when_it_started(uow, tmp_path):
    seed(uow)
    freshness.record_success(
        uow,
        freshness.LEAGUE,
        now=NOW - timedelta(days=12),
        cadence_seconds=300,
        stale_after_seconds=900,
        changed=False,
    )
    with uow.engine.begin() as c:
        c.execute(nfl_schedule_game.delete().where(nfl_schedule_game.c.event_id == MISSED))
    live, nfl = feeds(uow, missed_week_espn())
    lane = CatchupLane(uow, 2026, live=live, nfl=nfl, clock=lambda: NOW, root=tmp_path)
    assert lane.step() == CatchupLane.IDLE_SECONDS
    receipt = json.loads((tmp_path / catchup.RECEIPTS).read_text())
    assert receipt["weeks"] == []
    assert [g["source"] for g in receipt["sourcesBehindAtStart"]] == [freshness.LEAGUE]


def test_nfl_games_link_within_minutes_when_espn_lists_them_after_discovery(uow):
    """R-069: on 2026-11-22 discovery ran six seconds before ESPN's scoreboard and left every
    game unlinked for six hours."""
    seed(uow)
    at = NOW
    client = FakeNfl(week=10)
    nfl = NflFeed(uow, 2026, client=client, clock=lambda: at, live_log=LiveLog(enabled=False))  # type: ignore[arg-type]
    nfl.ids, nfl.ids_at = FIXTURE["ids"], NOW
    nfl.step()
    assert nfl.unlinked == 1
    with uow.engine.begin() as c:
        stored_game(c, MISSED, 10, "scheduled", complete=False, at=MISSED_KICKOFF)
    # Idle polls come every IDLE_SECONDS; relinking needs only RELINK_SECONDS, not six hours.
    assert RELINK_SECONDS <= IDLE_SECONDS < DISCOVER_SECONDS
    at = NOW + timedelta(seconds=IDLE_SECONDS + 1)
    nfl.step()
    with uow.engine.connect() as c:
        assert (
            c.scalar(select(nfl_api_game.c.event_id).where(nfl_api_game.c.game_id == GAME_ID))
            == MISSED
        )
    assert nfl.unlinked == 0
