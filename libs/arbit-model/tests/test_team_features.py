"""Team environment and defense against the position (M3 slice 3b, OWN-068).

A synthetic 2025 season: week 1 is NE at SEA and BUF at KC; week 2's decisions are SEA at KC and
NE at BUF, at kickoff. Arbit first read the files on 10 September, so week 1 counts from the
statistics rule (12:00 UTC the day after the game).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from arbit_data.nflverse.stat_lines import PLAY_COLUMNS
from arbit_model.feature_specs import FEATURES, SHRINKAGE
from arbit_model.gamebook import Gamebooks
from arbit_model.point_in_time import PointInTime
from arbit_model.targets import STAT_COLUMNS
from arbit_model.team_features import KEYS, team_features
from arbit_model.timing import Calendar
from test_model_targets import RULES
from test_point_in_time import MemorySource

ROOT = Path(__file__).resolve().parents[3]
SEASON = 2025


def utc(*parts):
    return datetime(*parts, tzinfo=UTC)


GAMES = [
    # game_id, week, gameday, gametime, away, home, away_score, home_score
    ("2025_01_NE_SEA", 1, "2025-09-07", "13:00", "NE", "SEA", 10, 24),
    ("2025_01_BUF_KC", 1, "2025-09-07", "16:25", "BUF", "KC", 20, 17),
    ("2025_02_SEA_KC", 2, "2025-09-14", "13:00", "SEA", "KC", 13, 27),
    ("2025_02_NE_BUF", 2, "2025-09-14", "16:25", "NE", "BUF", 3, 31),
]
CALENDAR = Calendar(
    {
        "game_id": g,
        "season": SEASON,
        "week": week,
        "game_type": "REG",
        "gameday": day,
        "gametime": clock,
        "away_team": away,
        "home_team": home,
    }
    for g, week, day, clock, away, home, _, _ in GAMES
)
WEEK2_KICKOFF = CALENDAR.game("2025_02_SEA_KC").kickoff


def schedule(played_through):
    rows = []
    for g, week, _, _, away, home, away_score, home_score in GAMES:
        done = week <= played_through
        rows.append(
            {
                "game_id": g,
                "season": SEASON,
                "week": week,
                "game_type": "REG",
                "home_team": home,
                "away_team": away,
                "home_score": home_score if done else None,
                "away_score": away_score if done else None,
                "home_rest": 7,
                "away_rest": 6 if home == "KC" else 7,
                "roof": "outdoors",
                "surface": "grass",
                "div_game": 1 if {home, away} == {"NE", "BUF"} else 0,
            }
        )
    return rows


def plays(game, away, home):
    base = dict.fromkeys(PLAY_COLUMNS, 0) | {
        "game_id": game,
        "posteam": home,
        "defteam": away,
        "play_type": "pass",
        "td_team": None,
        "td_player_id": None,
        "field_goal_result": None,
        "extra_point_result": None,
        "fumbled_1_team": None,
        "fumbled_2_team": None,
        "fumble_recovery_1_team": None,
        "fumble_recovery_2_team": None,
    }
    return [base, base | {"posteam": away, "defteam": home}]


def player(game, team, pid, position, **values):
    week = int(game[5:7])
    return (
        {
            "game_id": game,
            "season": SEASON,
            "week": week,
            "team": team,
            "player_id": pid,
            "position": position,
            "attempts": 0,
            "carries": 0,
            "targets": 0,
            "fg_att": 0,
            "pat_att": 0,
        }
        | dict.fromkeys(STAT_COLUMNS, 0)
        | values
    )


def team_row(game, team, **values):
    week = int(game[5:7])
    return {
        "game_id": game,
        "season": SEASON,
        "week": week,
        "team": team,
        "attempts": 30,
        "sacks_suffered": 2,
        "carries": 25,
        "passing_epa": 3.0,
        "rushing_epa": -1.0,
        "passing_interceptions": 1,
        "fumbles_lost_total": 0,
        "passing_yards": 220,
        "rushing_yards": 100,
        "sack_yards_lost": 12,
        "def_interceptions": 1,
        "fumble_recovery_opp": 0,
        "def_fg_blocks": 0,
        "def_punt_blocks": 0,
        "def_pat_blocks": 0,
    } | values


WEEK1_PLAYERS = [
    player("2025_01_NE_SEA", "SEA", "SEA-WR", "WR", receptions=6, receiving_yards=90, targets=9),
    player("2025_01_NE_SEA", "NE", "NE-WR", "WR", receptions=3, receiving_yards=30, targets=5),
    player("2025_01_NE_SEA", "NE", "NE-RB", "RB", rushing_yards=50, carries=12),
    player(
        "2025_01_BUF_KC",
        "BUF",
        "BUF-WR",
        "WR",
        receptions=8,
        receiving_yards=120,
        receiving_tds=1,
        targets=11,
    ),
    player("2025_01_BUF_KC", "KC", "KC-WR", "WR", receptions=4, receiving_yards=40, targets=6),
    player("2025_01_BUF_KC", "KC", "KC-QB", "QB", passing_yards=250, passing_tds=2, attempts=35),
]
WEEK1_TEAMS = [
    team_row("2025_01_NE_SEA", "SEA", passing_epa=8.0),
    team_row("2025_01_NE_SEA", "NE", carries=20, passing_epa=-4.0),
    team_row("2025_01_BUF_KC", "BUF", attempts=36),
    team_row("2025_01_BUF_KC", "KC"),
]
WEEK1_PLAYS = plays("2025_01_NE_SEA", "NE", "SEA") + plays("2025_01_BUF_KC", "BUF", "KC")

FIRST = utc(2025, 9, 10, 3)
READS = [utc(2025, 9, 11, 3), utc(2025, 9, 12, 3), utc(2025, 9, 13, 3)]


def files(extra_versions=()):
    """Every table, first read on 10 September; `extra_versions` add (at, table rows) later."""
    base = {
        "schedules/games": [(FIRST, schedule(1))],
        "pbp/play_by_play_2025": [(FIRST, WEEK1_PLAYS)],
        "stats_player/stats_player_week_2025": [(FIRST, WEEK1_PLAYERS)],
        "stats_team/stats_team_week_2025": [(FIRST, WEEK1_TEAMS)],
    }
    for at, tables in extra_versions:
        for key, rows in tables.items():
            base[key] = sorted([*base[key], (at, rows)], key=lambda v: v[0])
    return {key: (versions, READS) for key, versions in base.items()}


def build(source_files, games=("2025_02_SEA_KC", "2025_02_NE_BUF")):
    pit = PointInTime(MemorySource(source_files), CALENDAR)
    return team_features(pit, Gamebooks(pit, RULES), list(games))


def row(result, team):
    return result.frame.filter(pl.col("team") == team).row(0, named=True)


def test_every_column_is_a_specified_feature_with_its_cutoff_and_sources():
    result = build(files())
    assert result.frame.columns == [*KEYS, *FEATURES]
    for spec in FEATURES.values():
        assert spec.definition and spec.unit and spec.window and spec.cutoff and spec.sources
        assert spec.shrinkage is None or spec.shrinkage in SHRINKAGE
    assert set(result.lineage["coverage"]) == set(FEATURES)


def test_shrinkage_constants_are_the_measured_ones():
    for name, (k, receipt, measure) in SHRINKAGE.items():
        data = json.loads((ROOT / receipt).read_text())
        node = data["stability"]
        for part in measure.split("/"):
            node = node[part]
        assert node["gamesForHalfSignal"] == k, name


def test_team_rates_follow_the_signal_study_definitions_and_context_is_pre_game():
    result = build(files())
    sea = row(result, "SEA")
    assert sea["games_played"] == 1 and sea["opp_games_played"] == 1
    assert sea["off_plays_pg"] == 30 + 2 + 25
    assert sea["off_dropback_rate"] == pytest.approx(32 / 57)
    assert sea["off_epa_per_play"] == pytest.approx(7.0 / 57)
    assert sea["off_points_pg"] == 24 and sea["def_points_allowed_pg"] == 10
    # NE's offense: 30 attempts, 2 sacks, 20 carries; one interception, so one takeaway.
    assert sea["def_epa_per_play"] == pytest.approx(-5.0 / 52)
    assert sea["def_sack_rate"] == pytest.approx(2 / 32)
    assert sea["def_takeaways_pg"] == 1
    league = result.lineage["decisions"][0]["leagueMeans"]["off_epa_per_play"]
    k = SHRINKAGE["off_epa_per_play"][0]
    assert sea["off_epa_per_play_shrunk"] == pytest.approx((7.0 / 57 + k * league) / (1 + k))
    assert (sea["is_home"], sea["rest_days"], sea["opp_rest_days"]) == (False, 6, 7)
    assert row(result, "BUF")["div_game"] is True


def test_defense_against_the_position_is_raw_and_adjusted_for_the_offense_faced():
    result = build(files())
    pit = PointInTime(MemorySource(files()), CALENDAR)
    book = Gamebooks(pit, RULES).at(SEASON, WEEK2_KICKOFF)
    points = {
        (r["team"], r["position"]): r["points"] for r in book.position_points.iter_rows(named=True)
    }
    sea = row(result, "SEA")  # SEA's opponent is KC, whose defense faced BUF in week 1.
    assert sea["opp_dvp_WR_pg"] == pytest.approx(points[("BUF", "WR")])
    league_wr = sum(v for (_, pos), v in points.items() if pos == "WR") / 4
    assert result.lineage["decisions"][0]["positionLeagueMeans"]["WR"] == pytest.approx(league_wr)
    # BUF has no other game, so its expectation at WR is the league mean.
    assert sea["opp_dvp_WR_adj"] == pytest.approx(points[("BUF", "WR")] - league_wr)
    k, k_adj = SHRINKAGE["dvp_WR"][0], SHRINKAGE["dvp_WR_adj"][0]
    assert sea["opp_dvp_WR_pg_shrunk"] == pytest.approx(
        (points[("BUF", "WR")] + k * league_wr) / (1 + k)
    )
    assert sea["opp_dvp_WR_adj_shrunk"] == pytest.approx(sea["opp_dvp_WR_adj"] / (1 + k_adj))
    assert sea["opp_dvp_WR_opps_pg"] == 11
    # Nobody played TE against KC: zero allowed, not unknown.
    assert sea["opp_dvp_TE_pg"] == 0
    # The D/ST points SEA's D/ST can expect from KC's offense: what BUF's D/ST scored vs KC.
    dst = {(r["team"], r["opponent"]): r["points"] for r in book.dst_points.iter_rows(named=True)}
    assert sea["opp_off_dst_allowed_pg"] == pytest.approx(dst[("BUF", "KC")])


def test_rows_published_after_the_decision_never_change_a_feature():
    before = build(files())
    week2 = {
        "schedules/games": schedule(2),
        "pbp/play_by_play_2025": WEEK1_PLAYS
        + plays("2025_02_SEA_KC", "SEA", "KC")
        + plays("2025_02_NE_BUF", "NE", "BUF"),
        "stats_player/stats_player_week_2025": [
            {**p, "receiving_yards": p["receiving_yards"] + 50} for p in WEEK1_PLAYERS
        ]
        + [player("2025_02_SEA_KC", "SEA", "SEA-WR", "WR", receptions=12, targets=14)],
        "stats_team/stats_team_week_2025": [{**t, "passing_epa": 20.0} for t in WEEK1_TEAMS]
        + [team_row("2025_02_SEA_KC", "SEA"), team_row("2025_02_SEA_KC", "KC")],
    }
    after = build(files([(utc(2025, 9, 15, 3), week2)]))
    assert after.frame.equals(before.frame)


def test_a_stat_correction_published_before_the_decision_does_change_features():
    corrected = {
        "stats_player/stats_player_week_2025": [
            {**p, "receiving_yards": p["receiving_yards"] + 50} for p in WEEK1_PLAYERS
        ]
    }
    before = build(files())
    after = build(files([(utc(2025, 9, 12, 3), corrected)]))
    assert not after.frame.equals(before.frame)
    assert row(after, "SEA")["opp_dvp_WR_pg"] > row(before, "SEA")["opp_dvp_WR_pg"]
