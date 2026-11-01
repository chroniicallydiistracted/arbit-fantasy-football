from datetime import UTC, datetime, timedelta

import pytest
from arbit_data.live.cadence import (
    NFL_REQUESTS_PER_MINUTE,
    SCOREBOARD_REQUESTS_PER_MINUTE,
    GamePhase,
    backoff_seconds,
    final_check_due,
    league_seconds,
    league_stale_seconds,
    live_mode,
    play_seconds,
    scoreboard_seconds,
    scoreboard_stale_seconds,
)

NOW = datetime(2026, 11, 1, 18, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("phases", "expected"),
    [
        ([], "idle"),
        ([("final", -3)], "idle"),
        ([("scheduled", 3)], "idle"),
        ([("scheduled", 0.25)], "pregame"),
        ([("scheduled", -0.1)], "pregame"),  # past kickoff, source has not moved it yet
        ([("in_progress", -1)], "active"),
        ([("halftime", -1)], "active"),
        ([("overtime", -3)], "active"),
        ([("delayed", -1)], "active"),
        ([("final", -3), ("scheduled", 0.2), ("halftime", -1)], "active"),
        ([("postponed", 0.1)], "idle"),
        ([("cancelled", 0.1)], "idle"),
        ([("unknown", 0.1)], "idle"),
    ],
)
def test_mode_follows_the_observed_slate(phases, expected):
    games = [GamePhase(p, NOW + timedelta(hours=h)) for p, h in phases]
    assert live_mode(games, NOW) == expected


def test_scheduled_game_without_a_known_kickoff_never_forces_fast_reads():
    assert live_mode([GamePhase("scheduled", None)], NOW) == "idle"


def test_cadence_tightens_as_games_approach():
    assert league_seconds("idle") > league_seconds("pregame") > league_seconds("active") == 60
    assert scoreboard_seconds("idle") > scoreboard_seconds("pregame") > scoreboard_seconds("active")
    assert scoreboard_seconds("active") == 15


def test_stale_limits_match_the_cadence_in_force():
    assert league_stale_seconds("active") == 180
    assert league_stale_seconds("idle") == 900, "existing 15-minute normal-week limit is kept"
    assert scoreboard_stale_seconds("active") == 60, "floor applies above three 15 s reads"
    assert scoreboard_stale_seconds("idle") == 2700


@pytest.mark.parametrize("games", range(1, 17))
def test_every_slate_size_stays_inside_the_nfl_host_budget(games):
    plays_per_minute = games * 60 / play_seconds(games)
    summaries_per_minute = games  # one a minute per active game
    total = SCOREBOARD_REQUESTS_PER_MINUTE + summaries_per_minute + plays_per_minute
    assert total <= NFL_REQUESTS_PER_MINUTE


def test_small_slates_read_plays_at_the_fastest_cadence():
    assert play_seconds(1) == 15
    assert play_seconds(2) == 15
    assert play_seconds(14) > 15


def test_failures_back_off_from_the_normal_cadence_and_stop_at_a_ceiling():
    assert backoff_seconds(15, 0) == 15
    assert backoff_seconds(15, 1) == 30
    assert backoff_seconds(15, 2) == 60
    assert backoff_seconds(15, 50) == 900
    assert backoff_seconds(3600, 3) == 900, "slow sources retry sooner than their normal cadence"


def test_final_games_are_read_again_for_late_corrections_then_left_alone():
    final = NOW
    assert final_check_due(final, 0, NOW)
    assert not final_check_due(final, 1, NOW + timedelta(minutes=59))
    assert final_check_due(final, 1, NOW + timedelta(hours=1))
    assert final_check_due(final, 2, NOW + timedelta(hours=12))
    assert not final_check_due(final, 3, NOW + timedelta(days=30))
