"""Live game storage against real PostgreSQL: revisions, corrections, events and failure isolation."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from arbit_data import events, freshness
from arbit_data.errors import SourceError
from arbit_data.live import store
from arbit_data.live.capture import CapturingTransport
from arbit_data.live.contracts import FieldPoint, LivePlay, Participant
from arbit_data.live.feed import LiveFeed, normalize_current_scoreboard
from arbit_data.public_sources.requests import SourceRequest
from arbit_data.public_sources.transport import PublicResponse
from arbit_data.schema import nfl_game, nfl_play_revision, nfl_schedule_game, nfl_team, outbox_event
from sqlalchemy import func, select

SEASON = 2026
NOW = datetime(2026, 11, 1, 18, 0, tzinfo=UTC)


def game(event_id: str = "401", phase: str = "in_progress", home_score: str | None = "7") -> dict:
    return {
        "event_id": event_id,
        "season": SEASON,
        "date": "2026-11-01T17:00:00Z",
        "home_team_id": "12",
        "away_team_id": "20",
        "home_score": home_score,
        "away_score": "3",
        "source_status": "STATUS_IN_PROGRESS",
        "phase": phase,
        "completed": phase == "final",
        "period": 2,
        "clock": "4:12",
        "neutral_site": False,
        "recommendations_enabled": False,
        "fantasy_scoring": "not_calculated; ESPN Fantasy remains authoritative",
    }


def board(*games: dict) -> dict[str, Any]:
    return {"season": SEASON, "season_type": 2, "week": 8, "games": list(games)}


def play(
    play_id: str = "1",
    *,
    text: str = "Pass complete for 12 yards",
    sequence: str = "10",
    cancelled: bool = False,
    modified: str | None = None,
) -> LivePlay:
    return LivePlay(
        event_id="401",
        provider_id=play_id,
        sequence=sequence,
        provider_type_id="24",
        provider_type_text="Pass Reception",
        kind="pass",
        text=text,
        period=2,
        clock="4:12",
        home_score="7",
        away_score="3",
        scoring_play=False,
        score_value="0",
        cancelled=cancelled,
        modified_at=modified,
        wallclock=None,
        participants=(),
        start=FieldPoint(),
        end=FieldPoint(),
        can_connect_endpoints=False,
        effects=(),
        point_after=None,
        stat_yardage="12",
        source_flags={},
    )


def event_types(uow) -> list[str]:
    with uow.engine.connect() as c:
        return list(c.scalars(select(outbox_event.c.event_type).order_by(outbox_event.c.sequence)))


def revisions(uow, play_id: str = "1") -> list[Any]:
    with uow.engine.connect() as c:
        return list(
            c.execute(select(nfl_play_revision).where(nfl_play_revision.c.play_id == play_id)).all()
        )


def test_unchanged_scoreboard_writes_freshness_but_no_event(uow):
    assert store.publish_scoreboard(uow, board(game()), NOW).changed == ("401",)
    assert event_types(uow) == ["games.updated"]
    later = NOW + timedelta(seconds=15)
    assert store.publish_scoreboard(uow, board(game()), later).changed == ()
    assert event_types(uow) == ["games.updated"], "an unchanged poll must not wake every client"
    with uow.engine.connect() as c:
        row = c.execute(select(nfl_game)).one()
    assert row.observed_at == later and row.changed_at == NOW


def test_changed_score_updates_state_and_emits_one_event(uow):
    store.publish_scoreboard(uow, board(game()), NOW)
    later = NOW + timedelta(seconds=15)
    assert store.publish_scoreboard(uow, board(game(home_score="14")), later).changed == ("401",)
    assert event_types(uow) == ["games.updated", "games.updated"]
    with uow.engine.connect() as c:
        row = c.execute(select(nfl_game)).one()
    assert row.payload["home_score"] == "14" and row.changed_at == later


def test_late_worker_cannot_overwrite_newer_scoreboard(uow):
    store.publish_scoreboard(uow, board(game(home_score="14")), NOW)
    earlier = NOW - timedelta(seconds=30)
    assert store.publish_scoreboard(uow, board(game(home_score="7")), earlier).changed == ()
    with uow.engine.connect() as c:
        row = c.execute(select(nfl_game)).one()
    assert row.payload["home_score"] == "14" and row.observed_at == NOW


def test_final_is_recorded_once_for_correction_checks(uow):
    store.publish_scoreboard(uow, board(game()), NOW)
    final_at = NOW + timedelta(hours=3)
    change = store.publish_scoreboard(uow, board(game(phase="final")), final_at)
    assert change.finished == ("401",)
    again = store.publish_scoreboard(
        uow, board(game(phase="final", home_score="9")), final_at + timedelta(hours=1)
    )
    assert again.finished == ()
    with uow.engine.connect() as c:
        assert c.scalar(select(nfl_game.c.final_at)) == final_at


def test_same_plays_twice_produce_one_revision_and_one_event(uow):
    store.publish_scoreboard(uow, board(game()), NOW)
    first = store.publish_plays(uow, "401", (play(),), NOW, body_hash="a" * 64)
    assert first.introduced == ("1",)
    again = store.publish_plays(
        uow, "401", (play(),), NOW + timedelta(seconds=15), body_hash="b" * 64
    )
    assert not again.any
    assert len(revisions(uow)) == 1
    assert event_types(uow).count("game.plays") == 1


def test_correction_keeps_history_and_marks_only_the_new_revision_current(uow):
    store.publish_scoreboard(uow, board(game()), NOW)
    store.publish_plays(uow, "401", (play(),), NOW, body_hash="a" * 64)
    later = NOW + timedelta(seconds=30)
    change = store.publish_plays(
        uow, "401", (play(text="Pass complete for 8 yards"),), later, body_hash="b" * 64
    )
    assert change.revised == ("1",)
    rows = revisions(uow)
    assert len(rows) == 2 and sum(r.is_current for r in rows) == 1
    assert event_types(uow)[-1] == "game.corrected"
    current = store.read_plays(uow, "401")
    assert current[0]["text"] == "Pass complete for 8 yards" and current[0]["corrected"] is True


def test_explicit_cancellation_is_reported_but_a_missing_play_is_not_a_deletion(uow):
    store.publish_scoreboard(uow, board(game()), NOW)
    store.publish_plays(uow, "401", (play("1"), play("2", sequence="20")), NOW, body_hash="a" * 64)
    later = NOW + timedelta(seconds=30)
    omitted = store.publish_plays(
        uow, "401", (play("2", sequence="20"),), later, body_hash="b" * 64
    )
    assert not omitted.any
    assert {p["provider_id"] for p in store.read_plays(uow, "401")} == {"1", "2"}
    cancelled = store.publish_plays(
        uow, "401", (play("2", sequence="20", cancelled=True),), later, body_hash="c" * 64
    )
    assert cancelled.cancelled == ("2",)
    assert event_types(uow)[-1] == "game.corrected"


def test_play_already_cancelled_when_first_seen_is_not_a_correction(uow):
    """Observed in real ESPN data: completed games include plays flagged no-play from the start."""
    store.publish_scoreboard(uow, board(game()), NOW)
    change = store.publish_plays(uow, "401", (play(cancelled=True),), NOW, body_hash="a" * 64)
    assert change.introduced == ("1",) and change.cancelled == ()
    assert event_types(uow)[-1] == "game.plays"


def test_older_provider_revision_arriving_late_cannot_undo_a_newer_one(uow):
    store.publish_scoreboard(uow, board(game()), NOW)
    store.publish_plays(
        uow, "401", (play(text="new", modified="2026-11-01T18:00:30Z"),), NOW, body_hash="a" * 64
    )
    later = NOW + timedelta(seconds=15)
    change = store.publish_plays(
        uow, "401", (play(text="old", modified="2026-11-01T18:00:00Z"),), later, body_hash="b" * 64
    )
    assert not change.any
    assert store.read_plays(uow, "401")[0]["text"] == "new"


def test_play_returning_to_an_earlier_revision_restores_it_without_a_duplicate(uow):
    store.publish_scoreboard(uow, board(game()), NOW)
    store.publish_plays(uow, "401", (play(text="a"),), NOW, body_hash="a" * 64)
    store.publish_plays(
        uow, "401", (play(text="b"),), NOW + timedelta(seconds=1), body_hash="b" * 64
    )
    store.publish_plays(
        uow, "401", (play(text="a"),), NOW + timedelta(seconds=2), body_hash="c" * 64
    )
    rows = revisions(uow)
    assert len(rows) == 2
    assert [r.payload["text"] for r in rows if r.is_current] == ["a"]


def test_plays_for_an_unknown_game_are_rejected(uow):
    with pytest.raises(ValueError, match="UNKNOWN_GAME"):
        store.publish_plays(uow, "401", (play(),), NOW, body_hash="a" * 64)


def test_roster_filter_uses_participant_ids_never_names(uow):
    store.publish_scoreboard(uow, board(game()), NOW)
    mentioned = play("1", text="Own Player catches a pass")
    involved = play("2", text="Someone else", sequence="20").model_copy(
        update={"participants": (Participant(espn_id="99", role="receiver"),)}
    )
    store.publish_plays(uow, "401", (mentioned, involved), NOW, body_hash="a" * 64)
    assert [p["provider_id"] for p in store.read_plays(uow, "401", espn_ids={"99"})] == ["2"]


def directory_payload() -> dict[str, Any]:
    return {
        "settings": {
            "proTeams": [
                {"id": 0, "abbrev": "FA", "location": "Free", "name": "Agent", "byeWeek": 0},
                {
                    "id": 12,
                    "abbrev": "KC",
                    "location": "Kansas City",
                    "name": "Chiefs",
                    "byeWeek": 5,
                    "proGamesByScoringPeriod": {
                        "9": [
                            {
                                "id": 401873045,
                                "date": 1794160800000,
                                "homeProTeamId": 12,
                                "awayProTeamId": 20,
                                "startTimeTBD": False,
                                "statsOfficial": False,
                            }
                        ]
                    },
                },
                {"id": 20, "abbrev": "NYJ", "location": "New York", "name": "Jets", "byeWeek": 9},
            ]
        }
    }


def test_directory_excludes_the_placeholder_and_is_idempotent(uow):
    directory = store.normalize_directory(directory_payload(), SEASON)
    assert {t.abbreviation for t in directory.teams} == {"KC", "NYJ"}
    assert store.publish_directory(uow, directory, SEASON, NOW, "c" * 64) is True
    assert (
        store.publish_directory(uow, directory, SEASON, NOW + timedelta(hours=6), "c" * 64) is False
    )
    assert event_types(uow).count("schedule.updated") == 1
    with uow.engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(nfl_team)) == 2
        assert c.scalar(select(func.count()).select_from(nfl_schedule_game)) == 1
    games = store.read_period_games(uow, SEASON, 9)
    assert games["12"].event_id == "401873045" and games["20"].event_id == "401873045"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"settings": {"proTeams": []}},
        {"settings": {"proTeams": [{"id": "12"}]}},
        {"settings": {"proTeams": [{"id": 12, "abbrev": "", "location": "x", "name": "y"}]}},
    ],
)
def test_directory_shape_change_fails_closed(payload):
    with pytest.raises(ValueError):
        store.normalize_directory(payload, SEASON)


def test_directory_game_with_unknown_team_fails_closed():
    payload = directory_payload()
    payload["settings"]["proTeams"].pop()
    with pytest.raises(ValueError, match="DIRECTORY_INCONSISTENT"):
        store.normalize_directory(payload, SEASON)


# ---- feed


def raw_competitor(side: str, team: str, score: str) -> dict[str, Any]:
    return {"homeAway": side, "id": team, "score": score}


def raw_board(phase_state: str = "in", *, event_id: str = "401", season: int = SEASON) -> dict:
    status = {
        "period": 2,
        "displayClock": "4:12",
        "type": {
            "name": {"in": "STATUS_IN_PROGRESS", "pre": "STATUS_SCHEDULED", "post": "STATUS_FINAL"}[
                phase_state
            ],
            "state": phase_state,
            "completed": phase_state == "post",
        },
    }
    return {
        "season": {"year": season, "type": 2},
        "week": {"number": 8},
        "events": [
            {
                "id": event_id,
                "date": "2026-11-01T17:00Z",
                "season": {"year": season, "type": 2},
                "competitions": [
                    {
                        "id": event_id,
                        "date": "2026-11-01T17:00Z",
                        "status": status,
                        "competitors": [
                            raw_competitor("home", "12", "7"),
                            raw_competitor("away", "20", "3"),
                        ],
                    }
                ],
            }
        ],
    }


class FakeTransport:
    def __init__(self, responses: dict[str, Any]):
        self.responses, self.requests = responses, []

    def fetch(self, request: SourceRequest) -> PublicResponse:
        self.requests.append(request.kind)
        value = self.responses.get(request.kind)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise SourceError("NOT_FOUND")
        return PublicResponse(repr(value).encode(), value, None)  # type: ignore[arg-type]


class OpenGate:
    def request(self):
        from contextlib import nullcontext

        return nullcontext()


def empty_plays() -> dict[str, Any]:
    return {"count": 0, "pageIndex": 1, "pageCount": 1, "pageSize": 300, "items": []}


def test_current_scoreboard_rejects_a_different_season():
    with pytest.raises(ValueError, match="SCOREBOARD_SEASON_MISMATCH"):
        normalize_current_scoreboard(raw_board(season=2027), SEASON)


def test_feed_reads_active_games_and_records_freshness(uow):
    transport = FakeTransport(
        {
            "espn.scoreboard.current": raw_board("in"),
            "espn.plays": empty_plays(),
            "espn.summary": {"header": {}},
        }
    )
    feed = LiveFeed(uow, transport, SEASON, gate=OpenGate(), clock=lambda: NOW)
    assert feed.step().mode == "active"
    assert transport.requests.count("espn.scoreboard.current") == 1
    assert transport.requests.count("espn.plays") == 1
    statuses = {s.source: s for s in freshness.read_sources(uow, SEASON, NOW)}
    assert statuses[freshness.SCOREBOARD].state == "current"
    assert statuses[freshness.SCOREBOARD].cadence_seconds == 15


def test_feed_does_not_read_plays_before_kickoff(uow):
    transport = FakeTransport({"espn.scoreboard.current": raw_board("pre")})
    feed = LiveFeed(uow, transport, SEASON, gate=OpenGate(), clock=lambda: NOW)
    feed.step()
    assert "espn.plays" not in transport.requests


def test_scoreboard_failure_backs_off_without_stopping_the_feed(uow):
    transport = FakeTransport({"espn.scoreboard.current": SourceError("UNAVAILABLE", status=503)})
    feed = LiveFeed(uow, transport, SEASON, gate=OpenGate(), clock=lambda: NOW)
    feed.step()
    feed.step()
    assert transport.requests.count("espn.scoreboard.current") == 1, "must wait out the backoff"
    assert freshness.failures_of(uow, freshness.SCOREBOARD) == 1
    assert feed.board_due is not None and feed.board_due > NOW


def test_one_failing_game_does_not_hold_up_the_scoreboard(uow):
    transport = FakeTransport(
        {"espn.scoreboard.current": raw_board("in"), "espn.plays": SourceError("UNAVAILABLE")}
    )
    feed = LiveFeed(uow, transport, SEASON, gate=OpenGate(), clock=lambda: NOW)
    assert feed.step().mode == "active"
    statuses = {s.source: s for s in freshness.read_sources(uow, SEASON, NOW)}
    assert statuses[freshness.SCOREBOARD].state == "current"
    assert statuses[freshness.PLAYS].error_code == "UNAVAILABLE"


def test_capture_keeps_every_live_response_without_adding_requests(uow, tmp_path):
    responses = {
        "espn.scoreboard.current": raw_board("in"),
        "espn.plays": empty_plays(),
        "espn.summary": {"header": {}},
    }
    plain = FakeTransport(responses)
    LiveFeed(uow, plain, SEASON, gate=OpenGate(), clock=lambda: NOW).step()

    wrapped = FakeTransport(responses)
    capturing = CapturingTransport(wrapped, tmp_path, clock=lambda: NOW)
    LiveFeed(
        uow, capturing, SEASON, gate=OpenGate(), clock=lambda: NOW + timedelta(minutes=5)
    ).step()
    assert wrapped.requests == plain.requests
    lines = (tmp_path / "2026-11-01.jsonl").read_text().splitlines()
    assert sorted(json.loads(line)["kind"] for line in lines) == sorted(wrapped.requests)
    assert {"espn.scoreboard.current", "espn.plays", "espn.summary"} == set(wrapped.requests)


def test_summary_detail_announces_changes_only_and_survives_older_rows(uow):
    store.publish_scoreboard(uow, board(game()), NOW)
    assert store.read_game(uow, "401")["detail"] == {}, "no summary read yet"
    detail = {"drives": [], "win_probability": [{"play_id": "1", "home": 0.5}], "team_stats": []}
    before = event_types(uow).count("game.summary")
    store.publish_summary(uow, "401", {"teams": []}, NOW, detail)
    store.publish_summary(uow, "401", {"teams": []}, NOW + timedelta(seconds=60), detail)
    assert event_types(uow).count("game.summary") == before + 1, "unchanged detail is silent"
    assert store.read_game(uow, "401")["detail"] == detail
    # A row from before detail existed holds a bare boxscore.
    with uow.engine.begin() as c:
        c.execute(nfl_game.update().values(boxscore={"teams": []}))
    assert store.read_game(uow, "401")["detail"] == {}


def test_identical_play_bytes_skip_processing(uow):
    transport = FakeTransport(
        {
            "espn.scoreboard.current": raw_board("in"),
            "espn.plays": empty_plays(),
            "espn.summary": {"header": {}},
        }
    )
    moments = iter(NOW + timedelta(seconds=i) for i in range(1000))
    feed = LiveFeed(uow, transport, SEASON, gate=OpenGate(), clock=lambda: next(moments))
    feed.read_board()
    feed.read_plays("401")
    before = event_types(uow)
    assert not feed.read_plays("401").any
    assert event_types(uow) == before
    with uow.engine.connect() as c:
        assert c.scalar(select(nfl_game.c.plays_observed_at)) is not None


# ---- freshness and events


def test_source_states_follow_age_and_failures(uow):
    freshness.record_success(
        uow, freshness.SCOREBOARD, now=NOW, cadence_seconds=15, stale_after_seconds=60
    )
    read = lambda at: {s.source: s.state for s in freshness.read_sources(uow, SEASON, at)}  # noqa: E731
    assert read(NOW + timedelta(seconds=59))[freshness.SCOREBOARD] == "current"
    assert read(NOW + timedelta(seconds=61))[freshness.SCOREBOARD] == "behind"
    assert read(NOW - timedelta(seconds=5))[freshness.SCOREBOARD] == "behind", (
        "future time is not fresh"
    )
    for _ in range(3):
        freshness.record_failure(
            uow,
            freshness.SCOREBOARD,
            "UNAVAILABLE",
            now=NOW,
            cadence_seconds=15,
            stale_after_seconds=60,
        )
    assert read(NOW)[freshness.SCOREBOARD] == "down"
    assert read(NOW)[freshness.PLAYS] == "never"


def test_statistics_age_comes_from_stored_imports_before_the_first_scheduled_run(uow):
    from arbit_data.schema import dataset_manifest
    from sqlalchemy import insert

    with uow.engine.begin() as c:
        c.execute(
            insert(dataset_manifest).values(
                hash="a" * 64,
                logical_key="k",
                family="f",
                observed_at=NOW,
                raw_hash="b" * 64,
                state_hash="c" * 64,
                payload={},
            )
        )
    read = lambda at: next(  # noqa: E731
        s for s in freshness.read_sources(uow, SEASON, at) if s.source == freshness.STATISTICS
    )
    assert read(NOW + timedelta(hours=1)).state == "current"
    assert read(NOW + timedelta(hours=37)).state == "behind"


def test_source_with_no_expected_reads_is_idle_not_stale(uow):
    freshness.record_success(
        uow, freshness.PLAYS, now=NOW, cadence_seconds=None, stale_after_seconds=None
    )
    statuses = {
        s.source: s.state for s in freshness.read_sources(uow, SEASON, NOW + timedelta(days=4))
    }
    assert statuses[freshness.PLAYS] == "idle"


def test_events_replay_in_order_and_report_expired_cursors(uow):
    assert events.replay_available(uow, 0)
    store.publish_scoreboard(uow, board(game()), NOW)
    store.publish_scoreboard(uow, board(game(home_score="14")), NOW + timedelta(seconds=1))
    all_events = events.read_after(uow, 0)
    assert [e.event_type for e in all_events] == ["games.updated", "games.updated"]
    first, second = all_events
    assert [e.sequence for e in events.read_after(uow, first.sequence)] == [second.sequence]
    assert events.replay_available(uow, first.sequence)
    assert not events.replay_available(uow, second.sequence + 100), "a future cursor is not valid"
    with uow.engine.begin() as c:
        c.execute(
            outbox_event.update()
            .where(outbox_event.c.sequence == first.sequence)
            .values(occurred_at=NOW - timedelta(days=2))
        )
    assert events.trim_before(uow, NOW - timedelta(days=1)) == 1
    assert not events.replay_available(uow, first.sequence - 1), (
        "trimmed history must force a refetch"
    )
    assert events.latest_sequence(uow) == second.sequence


def test_trim_keeps_the_newest_event_so_sequences_are_never_reused(uow):
    store.publish_scoreboard(uow, board(game()), NOW)
    with uow.engine.begin() as c:
        c.execute(outbox_event.update().values(occurred_at=NOW - timedelta(days=9)))
    assert events.trim_before(uow, NOW) == 0
    assert events.latest_sequence(uow) > 0
