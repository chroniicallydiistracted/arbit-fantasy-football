"""Gamebooks: completed games as known at a decision time, scored once per version (slice 3b)."""

from datetime import UTC, datetime

from arbit_model.gamebook import Gamebooks
from arbit_model.point_in_time import PointInTime
from test_model_targets import RULES
from test_point_in_time import MemorySource
from test_team_features import (
    CALENDAR,
    FIRST,
    SEASON,
    WEEK1_PLAYERS,
    WEEK2_KICKOFF,
    files,
    player,
)


def utc(*parts):
    return datetime(*parts, tzinfo=UTC)


def books(source_files):
    return Gamebooks(PointInTime(MemorySource(source_files), CALENDAR), RULES)


def test_a_game_counts_only_once_every_table_is_known():
    source = files()
    # Team statistics arrive a version later than the rest.
    versions, reads = source["stats_team/stats_team_week_2025"]
    source["stats_team/stats_team_week_2025"] = (
        [(utc(2025, 9, 13, 3), versions[0][1])],
        reads,
    )
    early = books(source).at(SEASON, utc(2025, 9, 12, 12))
    assert early.games.height == 0
    late = books(source).at(SEASON, WEEK2_KICKOFF)
    assert late.games.height == 2


def test_scored_games_are_cached_per_version_and_rescored_after_a_correction():
    gamebooks = books(files())
    first = gamebooks.at(SEASON, WEEK2_KICKOFF)
    assert first.lineage["scoredNow"] == 2
    again = gamebooks.at(SEASON, utc(2025, 9, 14, 20))
    assert again.lineage["scoredNow"] == 0
    corrected = [{**p, "receiving_yards": p["receiving_yards"] + 10} for p in WEEK1_PLAYERS]
    later = books(
        files([(utc(2025, 9, 16, 3), {"stats_player/stats_player_week_2025": corrected})])
    )
    before = later.at(SEASON, WEEK2_KICKOFF)
    after = later.at(SEASON, utc(2025, 9, 17))
    assert after.lineage["scoredNow"] == 2  # both games' player rows came from a new version
    assert sea_wr_points(after) > sea_wr_points(before)


def sea_wr_points(book):
    points = book.position_points
    return points.filter((points["team"] == "SEA") & (points["position"] == "WR"))["points"][0]


def test_a_fullback_scores_as_a_running_back():
    fullback = player("2025_01_NE_SEA", "SEA", "SEA-FB", "FB", rushing_yards=20, carries=4)
    source = files([(FIRST, {"stats_player/stats_player_week_2025": [*WEEK1_PLAYERS, fullback]})])
    # The added version replaces the first one at the same time; keep only it.
    for key, (versions, reads) in source.items():
        source[key] = (versions[-1:], reads)
    book = books(source).at(SEASON, WEEK2_KICKOFF)
    rb = book.position_points.filter(
        (book.position_points["team"] == "SEA") & (book.position_points["position"] == "RB")
    )
    assert rb["opportunities"][0] == 4
