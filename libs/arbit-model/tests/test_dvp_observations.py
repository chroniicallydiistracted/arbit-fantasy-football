"""DvP observations from canonical FFA actuals: tests T01-T07 of the owner's DvP specification.

A fixture 2016 slate that carries the real data's traps: the schedule says OAK and SD while the
target rows say LV and LAC, Raiders and Chargers home rows name the team itself as the opponent,
D/ST lines are missing around those teams, one line is refused, one player has two lines in a game,
one player changes teams, one game never finished and one is a playoff game.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import polars as pl
import pytest
from arbit_model.dvp import observations as obs
from arbit_model.dvp.provenance import admit

SCORING = {"athlete": "a" * 64, "defense": "d" * 64}
SEASON = 2016


def game(gid: str, week: int, day: str, clock: str, away: str, home: str, score: Any, kind="REG"):
    away_score, home_score = score if score else (None, None)
    return {
        "game_id": gid,
        "season": SEASON,
        "week": week,
        "game_type": kind,
        "gameday": day,
        "gametime": clock,
        "away_team": away,
        "home_team": home,
        "away_score": away_score,
        "home_score": home_score,
    }


SCHEDULE = [
    game("2016_01_ATL_OAK", 1, "2016-09-11", "16:05", "ATL", "OAK", (28, 35)),
    game("2016_01_SD_KC", 1, "2016-09-11", "13:00", "SD", "KC", (24, 27)),
    game("2016_02_OAK_SD", 2, "2016-09-15", "20:25", "OAK", "SD", (14, 10)),  # Thursday
    game("2016_02_KC_ATL", 2, "2016-09-18", "13:00", "KC", "ATL", (17, 20)),
    game("2016_03_ATL_SD", 3, "2016-09-25", "13:00", "ATL", "SD", None),  # never finished
    game("2016_19_KC_OAK", 19, "2017-01-07", "16:35", "KC", "OAK", (30, 20), "WC"),
]
ATHLETE_SCHEMA = {
    "season": pl.Int16,
    "week": pl.Int16,
    "season_type": pl.String,
    "game_id": pl.String,
    "team": pl.String,
    "opponent": pl.String,
    "player_id": pl.String,
    "position": pl.String,
    "basis": pl.String,
    "points": pl.Float64,
    "refusal": pl.String,
}


def line(gid, team, opponent, pid, position, points, basis="statistics", refusal=None, kind="REG"):
    return {
        "season": SEASON,
        "week": int(gid[5:7]),
        "season_type": kind,
        "game_id": gid,
        "team": team,
        "opponent": opponent,
        "player_id": pid,
        "position": position,
        "basis": basis,
        "points": points,
        "refusal": refusal,
    }


G1, G2, G3, G4 = "2016_01_ATL_OAK", "2016_01_SD_KC", "2016_02_KC_ATL", "2016_02_OAK_SD"
ATHLETE = [
    # Raiders at home: statistics rows say LV, and the opponent recorded is the team itself.
    line(G1, "LV", "OAK", "LV-QB", "QB", 20.5),
    line(G1, "LV", "OAK", "LV-WR1", "WR", 12.3),
    line(G1, "LV", "OAK", "LV-WR2", "WR", 4.5),
    line(G1, "LV", "OAK", "LV-WR3", "WR", -0.5),
    line(G1, "LV", "OAK", "LV-RB", "RB", 10.0),
    line(G1, "LV", "OAK", "LV-FB", "FB", 3.0),
    line(G1, "LV", "OAK", "LV-K", "K", 7.0),
    line(G1, "LV", "OAK", "LV-CB", "CB", 6.0),  # a return touchdown: not an FFA group
    line(G1, "OAK", "ATL", "LV-OL", None, 0.0, basis="snaps_without_statistics"),
    line(G1, "ATL", "OAK", "ATL-QB", "QB", -1.66),
    line(G1, "ATL", "OAK", "ATL-WR", "WR", 8.25),
    line(G1, "ATL", "OAK", "ATL-RB", "RB", 15.0),
    line(G1, "ATL", "OAK", "ATL-TE", "TE", 5.5),
    line(G1, "ATL", "OAK", "ATL-K", "K", 9.0),
    line(G1, "ATL", "OAK", "ATL-PK", "PK", 1.0),
    line(G2, "LAC", "KC", "LAC-QB", "QB", 18.0),
    line(
        G2, "LAC", "KC", "LAC-WR", "WR", None, refusal="MissingStatError: returns.two_point_returns"
    ),
    line(G2, "LAC", "KC", "LAC-WR2", "WR", 11.0),
    line(G2, "KC", "SD", "KC-QB", "QB", 22.0),
    line(G2, "KC", "SD", "TRADED", "TE", 6.0),
    line(G3, "ATL", "KC", "ATL-QB", "QB", 14.0),
    line(G3, "ATL", "KC", "ATL-WR", "WR", 7.0),
    line(G3, "ATL", "KC", "ATL-WR", "WR", 7.0),  # the same player twice in one game
    line(G3, "ATL", "KC", "TRADED", "TE", 9.0),  # now with Atlanta
    # (Kansas City's week 2 rows are absent: that team-game has no coverage.)
    line(G4, "LV", "SD", "LV-QB", "QB", 16.0),
    line(G4, "LAC", "SD", "LAC-QB", "QB", 9.0),  # Chargers at home: themselves as opponent
    line("2016_19_KC_OAK", "KC", "OAK", "KC-QB", "QB", 30.0, kind="POST"),
]
DEFENSE_SCHEMA = {k: v for k, v in ATHLETE_SCHEMA.items() if k not in ("player_id", "position")}


def dst(gid, team, opponent, points, kind="REG"):
    return {
        "season": SEASON,
        "week": int(gid[5:7]),
        "season_type": kind,
        "game_id": gid,
        "team": team,
        "opponent": opponent,
        "basis": "team_statistics",
        "points": points,
        "refusal": None,
    }


# As in the canonical table, games with OAK or SD have no D/ST lines for either side.
DEFENSE = [dst(G2, "KC", "SD", 12.0), dst(G3, "ATL", "KC", 4.0), dst(G3, "KC", "ATL", -2.0)]


@dataclass
class Built:
    scheduled: pl.DataFrame
    played: pl.DataFrame
    rows: pl.DataFrame
    athlete: dict[str, Any]
    dst: dict[str, Any]


def frames(athlete=ATHLETE, defense=DEFENSE, schedule=SCHEDULE):
    return (
        pl.DataFrame(athlete, schema=ATHLETE_SCHEMA),
        pl.DataFrame(defense, schema=DEFENSE_SCHEMA),
        pl.DataFrame(schedule),
    )


def build(athlete=ATHLETE, defense=DEFENSE, schedule=SCHEDULE) -> Built:
    a, d, s = frames(athlete, defense, schedule)
    sched = admit(s, "nflverse.schedules", ancestry="fixture")
    ath = admit(
        a,
        "ffa_targets.athlete",
        ancestry="fixture",
        scoring_hash=SCORING["athlete"],
        expected_scoring=SCORING,
    )
    dfn = admit(
        d,
        "ffa_targets.defense",
        ancestry="fixture",
        scoring_hash=SCORING["defense"],
        expected_scoring=SCORING,
    )
    scheduled = obs.games(sched.frame, [SEASON])
    played = obs.team_games(scheduled)
    cells, athlete_anomalies = obs.position_cells(ath.frame, played)
    lines, dst_anomalies = obs.dst_cells(dfn.frame, played)
    return Built(
        scheduled,
        played,
        obs.observations(cells, lines, SCORING),
        athlete_anomalies,
        dst_anomalies,
    )


def cell(rows: pl.DataFrame, gid: str, offense: str, position: str) -> dict[str, Any]:
    found = rows.filter(
        (pl.col("game_id") == gid)
        & (pl.col("offense") == offense)
        & (pl.col("position") == position)
    )
    assert found.height == 1, (gid, offense, position, found)
    return found.row(0, named=True)


@pytest.fixture(scope="module")
def built() -> Built:
    return build()


def test_t01_position_points_are_sums_of_canonical_lines(built):
    assert cell(built.rows, G1, "LV", "WR")["points"] == pytest.approx(12.3 + 4.5 - 0.5)
    assert cell(built.rows, G1, "LV", "QB")["points"] == 20.5
    again = build()
    assert again.rows.equals(built.rows)  # deterministic


def test_t02_fb_counts_as_rb_and_only_ffa_groups_are_summed(built):
    assert cell(built.rows, G1, "LV", "RB")["points"] == 13.0  # RB 10 + FB 3
    assert cell(built.rows, G1, "ATL", "K")["points"] == 10.0  # K 9 + PK 1
    assert set(built.rows["position"].unique()) == {"QB", "RB", "WR", "TE", "K", "DST"}
    assert built.athlete["pointsOnPositionsOutsideFfaGroups"] == {"lines": 1, "points": 6.0}


def test_t03_true_zero_is_distinct_from_missing_and_invalid(built):
    zero = cell(built.rows, G1, "LV", "TE")
    assert (zero["status"], zero["points"]) == ("valid", 0.0)
    for position in ("QB", "RB", "WR", "TE", "K"):
        missing = cell(built.rows, G3, "KC", position)
        assert (missing["status"], missing["points"]) == ("missing_coverage", None)
    refused = cell(built.rows, G2, "LAC", "WR")
    assert refused["status"] == "invalid_refused_line"
    assert refused["points"] is None and refused["points_partial"] == 11.0


def test_t04_negative_and_decimal_points_are_preserved(built):
    assert cell(built.rows, G1, "ATL", "QB")["points"] == -1.66
    assert cell(built.rows, G1, "ATL", "WR")["points"] == 8.25
    assert cell(built.rows, G3, "ATL", "DST")["points"] == -2.0


def test_t05_traded_player_duplicates_and_coverage(built):
    assert cell(built.rows, G2, "KC", "TE")["points"] == 6.0
    assert cell(built.rows, G3, "ATL", "TE")["points"] == 9.0
    duplicate = cell(built.rows, G3, "ATL", "WR")
    assert (duplicate["status"], duplicate["points"]) == ("invalid_duplicate_line", None)
    assert built.athlete["duplicatePlayerGameLines"] == 2
    assert built.athlete["rowsOutsideCompletedTeamGames"] == 0  # the playoff row is not REG


def test_t06_two_team_games_per_completed_regular_season_game(built):
    summary = obs.reconcile(built.scheduled, built.rows)
    assert summary["completedGames"] == 4 and summary["teamGames"] == 8
    assert summary["gamesWithoutExactlyTwoTeamGames"] == 0
    assert summary["teamGamesWithoutMirror"] == 0
    assert summary["seasons"]["2016"]["notCompleted"] == ["2016_03_ATL_SD"]
    assert (
        built.rows.filter(pl.col("game_id").is_in(["2016_03_ATL_SD", "2016_19_KC_OAK"])).height == 0
    )
    assert set(built.played["team"]) == {"ATL", "KC", "LAC", "LV"}  # franchise codes


def test_t07_defense_comes_from_the_schedule_and_dst_is_the_offense_vulnerability(built):
    raiders = cell(built.rows, G1, "LV", "WR")
    assert (raiders["defense"], raiders["unit"]) == ("ATL", "ATL")  # not LV, as the row said
    chargers = cell(built.rows, G4, "LAC", "QB")
    assert chargers["defense"] == "LV"
    # Eight Raiders rows at home and one Chargers row at home named the team itself.
    assert built.athlete["rowsWhoseRecordedOpponentDisagreesWithSchedule"] == 9
    conceded = cell(built.rows, G2, "LAC", "DST")
    assert (conceded["defense"], conceded["unit"], conceded["points"]) == ("KC", "LAC", 12.0)
    for gid, offense in ((G1, "LV"), (G1, "ATL"), (G2, "KC"), (G4, "LV"), (G4, "LAC")):
        missing = cell(built.rows, gid, offense, "DST")
        assert (missing["status"], missing["points"]) == ("missing_dst_line", None)
    assert built.dst["teamGamesWithoutOpposingDstLine"] == 5


def test_availability_is_the_day_after_the_game_at_noon_utc(built):
    first = built.scheduled.filter(pl.col("game_id") == G1).row(0, named=True)
    assert first["kickoff"] == datetime(2016, 9, 11, 20, 5, tzinfo=UTC)
    assert first["available_at"] == datetime(2016, 9, 12, 12, tzinfo=UTC)
    rows = built.rows.filter(pl.col("game_id") == G1)
    assert set(rows["source_type"]) == {"FFA_ACTUAL_FINAL"}
    assert set(rows["observed_or_generated"]) == {"observed"}
    assert set(rows["scoring_hash"]) == {SCORING["athlete"], SCORING["defense"]}
