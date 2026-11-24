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
    WEEK1_PLAYS,
    WEEK1_TEAMS,
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


def recoded(source, codes_by_table):
    """Source files with team codes replaced per table (`codes_by_table[table prefix]`)."""
    out = {}
    for key, (versions, reads) in source.items():
        codes = codes_by_table.get(key.split("/")[0], {})
        out[key] = (
            [
                (
                    at,
                    [
                        {c: codes.get(v, v) if isinstance(v, str) else v for c, v in r.items()}
                        for r in rows
                    ],
                )
                for at, rows in versions
            ],
            reads,
        )
    return out


def test_r072_a_relocated_team_keeps_its_games_and_its_opponents():
    # Seattle as a relocated franchise: OAK in the schedule, LV in play-by-play and statistics.
    source = recoded(
        files(),
        {
            "schedules": {"SEA": "OAK"},
            "pbp": {"SEA": "LV"},
            "stats_player": {"SEA": "LV"},
            "stats_team": {"SEA": "LV"},
        },
    )
    book = books(source).at(SEASON, WEEK2_KICKOFF)
    plain = books(files()).at(SEASON, WEEK2_KICKOFF)

    assert set(book.games["home"]) == {"LV", "KC"}
    assert book.team_games.height == plain.team_games.height == 4
    assert sorted(book.dst_points["points"]) == sorted(plain.dst_points["points"])
    lv = book.position_points.filter(book.position_points["team"] == "LV")
    assert set(lv["opponent"]) == {"NE"}
    assert sea_wr_points(plain) == lv.filter(lv["position"] == "WR")["points"][0]


def test_r074_playoff_games_are_left_out():
    source = files()
    versions, reads = source["schedules/games"]
    playoff = {**versions[0][1][0], "game_id": "2025_19_NE_SEA", "week": 19, "game_type": "WC"}
    source["schedules/games"] = ([(versions[0][0], [*versions[0][1], playoff])], reads)
    for key, extra in (
        ("pbp/play_by_play_2025", [{**r, "game_id": "2025_19_NE_SEA"} for r in WEEK1_PLAYS[:2]]),
        (
            "stats_player/stats_player_week_2025",
            [{**r, "game_id": "2025_19_NE_SEA"} for r in WEEK1_PLAYERS[:3]],
        ),
        (
            "stats_team/stats_team_week_2025",
            [{**r, "game_id": "2025_19_NE_SEA"} for r in WEEK1_TEAMS[:2]],
        ),
    ):
        versions, reads = source[key]
        source[key] = ([(versions[0][0], [*versions[0][1], *extra])], reads)
    book = books(source).at(SEASON, utc(2026, 2, 1))
    assert set(book.games["game_type"]) == {"REG"}
    assert "2025_19_NE_SEA" not in set(book.position_points["game_id"])
