"""Completed-game DvP observations from Arbit's canonical FFA actuals (M3-3 phase 1, spec §2-§3).

One row per completed regular-season team-game and FFA position group: the points the offense's
players scored there under the league's rules, which are the points the opposing defense allowed.
D/ST rows are the points the opposing D/ST scored against the offense, so their unit is the offense
(its vulnerability), not a defense.

Rules this module enforces:
- **The schedule decides who played whom.** Team codes become franchise codes (OAK -> LV,
  SD -> LAC, STL -> LA: the codes nflverse statistics use), and each cell's opponent comes from the
  schedule, never from the target row. Rows whose recorded opponent disagrees are counted.
- **Zero only when it is true.** A position with no scoring line in a team-game that has target
  rows is 0. A team-game with no target rows is `missing_coverage`; a cell holding a refused line
  (a statistic the scorer could not verify) is `invalid_refused_line`; a player with two lines in
  one game makes `invalid_duplicate_line`. Those cells carry no points.
- **Points are not rounded or clamped** before summing; negatives stay negative.
- **Availability:** a game's FFA actuals count from 12:00 UTC the day after its game day, the
  statistics rule (`timing.STATISTICS`), labeled retrospective: Arbit holds only final revisions
  for these seasons, so when each correction appeared is unknown.
"""

from collections.abc import Mapping, Sequence
from typing import Any

import polars as pl

from arbit_model.dvp.provenance import SourceType
from arbit_model.gamebook import POSITIONS
from arbit_model.teams import FRANCHISE

GROUPS = ("QB", "RB", "WR", "TE", "K")
DST = "DST"
POSITION_GROUPS = (*GROUPS, DST)
FINALITY = "retrospective-rule: statistics known 12:00 UTC the day after the game (final revisions)"
VALID = "valid"


def franchise(column: pl.Expr) -> pl.Expr:
    return column.cast(pl.String).replace(dict(FRANCHISE))


def games(schedule: pl.DataFrame, seasons: Sequence[int]) -> pl.DataFrame:
    """Every scheduled regular-season game of the seasons, with status, kickoff and availability."""
    local = pl.concat_str(
        [pl.col("gameday").cast(pl.String), pl.col("gametime").cast(pl.String)], separator=" "
    )
    day = pl.col("gameday").cast(pl.String).str.to_date("%Y-%m-%d")
    return (
        schedule.filter(
            (pl.col("game_type") == "REG") & pl.col("season").cast(pl.Int32).is_in(list(seasons))
        )
        .select(
            pl.col("game_id").cast(pl.String),
            pl.col("season").cast(pl.Int32),
            pl.col("week").cast(pl.Int32),
            franchise(pl.col("home_team")).alias("home"),
            franchise(pl.col("away_team")).alias("away"),
            pl.col("home_team").cast(pl.String).alias("home_code"),
            pl.col("away_team").cast(pl.String).alias("away_code"),
            pl.col("home_score").cast(pl.Float64),
            pl.col("away_score").cast(pl.Float64),
            local.str.to_datetime("%Y-%m-%d %H:%M", time_unit="us")
            .dt.replace_time_zone("America/New_York", ambiguous="earliest")
            .dt.convert_time_zone("UTC")
            .alias("kickoff"),
            (
                day.cast(pl.Datetime("us")).dt.replace_time_zone("UTC")
                + pl.duration(days=1, hours=12)
            ).alias("available_at"),
            pl.when(pl.col("home_score").is_not_null() & pl.col("away_score").is_not_null())
            .then(pl.lit("completed"))
            .otherwise(pl.lit("not_completed"))
            .alias("status"),
        )
        .sort("season", "week", "game_id")
    )


def team_games(schedule_games: pl.DataFrame) -> pl.DataFrame:
    """Exactly two rows per completed game: each team as the offense, the other as its opponent."""
    done = schedule_games.filter(pl.col("status") == "completed")
    keys = ("game_id", "season", "week", "kickoff", "available_at")
    home = done.select(
        *keys,
        pl.col("home").alias("team"),
        pl.col("away").alias("opponent"),
        pl.lit(True).alias("is_home"),
    )
    away = done.select(
        *keys,
        pl.col("away").alias("team"),
        pl.col("home").alias("opponent"),
        pl.lit(False).alias("is_home"),
    )
    return pl.concat([home, away]).sort("season", "week", "game_id", "team")


def position_cells(
    athlete: pl.DataFrame, played: pl.DataFrame
) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Each completed team-game's FFA points by position group, with the anomalies found."""
    # The target row's own opponent is kept only to compare; the schedule's is the one used.
    rows = (
        athlete.filter(pl.col("season_type") == "REG")
        .with_columns(
            franchise(pl.col("team")).alias("team"),
            franchise(pl.col("opponent")).alias("row_opponent"),
            pl.col("position")
            .cast(pl.String)
            .replace_strict(dict(POSITIONS), default=None, return_dtype=pl.String)
            .alias("group"),
            pl.col("points").cast(pl.Float64),
        )
        .drop("opponent")
    )
    lines = pl.len().over("game_id", "player_id")
    joined = rows.join(
        played.select("game_id", "team", "opponent"), on=["game_id", "team"], how="left"
    ).with_columns((lines > 1).alias("duplicate"))
    matched = joined.filter(pl.col("opponent").is_not_null())
    unmatched = joined.filter(pl.col("opponent").is_null())
    misattributed = matched.filter(pl.col("row_opponent") != pl.col("opponent"))
    covered = matched.select("game_id", "team").unique().with_columns(pl.lit(True).alias("covered"))
    sums = (
        matched.filter(pl.col("group").is_not_null())
        .group_by("game_id", "team", "group")
        .agg(
            pl.col("points").sum().alias("points_partial"),
            (pl.col("basis") == "statistics").sum().cast(pl.Int32).alias("lines"),
            pl.col("player_id").n_unique().cast(pl.Int32).alias("players"),
            pl.col("refusal").is_not_null().sum().cast(pl.Int32).alias("refused_lines"),
            pl.col("duplicate").sum().cast(pl.Int32).alias("duplicate_lines"),
        )
        .rename({"group": "position"})
    )
    grid = played.join(pl.DataFrame({"position": list(GROUPS)}), how="cross")
    cells = (
        grid.join(covered, on=["game_id", "team"], how="left", maintain_order="left")
        .join(sums, on=["game_id", "team", "position"], how="left", maintain_order="left")
        .with_columns(
            pl.col("lines", "players", "refused_lines", "duplicate_lines").fill_null(0),
            pl.when(pl.col("covered").is_null())
            .then(pl.lit("missing_coverage"))
            .when(pl.col("refused_lines") > 0)
            .then(pl.lit("invalid_refused_line"))
            .when(pl.col("duplicate_lines") > 0)
            .then(pl.lit("invalid_duplicate_line"))
            .otherwise(pl.lit(VALID))
            .alias("status"),
        )
        .with_columns(
            pl.when(pl.col("status") == VALID)
            .then(pl.col("points_partial").fill_null(0.0))
            .otherwise(None)
            .alias("points")
        )
        .drop("covered")
    )
    unmapped = matched.filter(pl.col("group").is_null() & (pl.col("points").fill_null(0) != 0))
    anomalies: dict[str, Any] = {
        "rowsOutsideCompletedTeamGames": unmatched.height,
        "rowsOutsideCompletedTeamGamesBySeason": _by_season(unmatched),
        "rowsWhoseRecordedOpponentDisagreesWithSchedule": misattributed.height,
        "misattributedByTeamSeason": count_by(misattributed, "season", "team", "row_opponent"),
        "duplicatePlayerGameLines": int(joined.get_column("duplicate").sum()),
        "pointsOnPositionsOutsideFfaGroups": {
            "lines": unmapped.height,
            "points": round(float(unmapped.get_column("points").sum()), 2),
        },
    }
    return cells, anomalies


def dst_cells(defense: pl.DataFrame, played: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Each completed team-game's D/ST points conceded: the opposing D/ST's FFA line."""
    rows = defense.filter(pl.col("season_type") == "REG").select(
        "game_id",
        franchise(pl.col("team")).alias("dst_team"),
        franchise(pl.col("opponent")).alias("row_opponent"),
        pl.col("points").cast(pl.Float64).alias("points_partial"),
        pl.col("refusal"),
        (pl.len().over("game_id", "team") > 1).alias("duplicate"),
        pl.lit(True).alias("matched"),
    )
    joined = played.join(
        rows,
        left_on=["game_id", "opponent"],
        right_on=["game_id", "dst_team"],
        how="left",
        maintain_order="left",
    )
    cells = joined.with_columns(
        pl.lit(DST).alias("position"),
        pl.when(pl.col("matched").is_null())
        .then(pl.lit("missing_dst_line"))
        .when(pl.col("refusal").is_not_null())
        .then(pl.lit("invalid_refused_line"))
        .when(pl.col("duplicate"))
        .then(pl.lit("invalid_duplicate_line"))
        .otherwise(pl.lit(VALID))
        .alias("status"),
        pl.col("matched").fill_null(False).cast(pl.Int32).alias("lines"),
        pl.col("refusal").is_not_null().cast(pl.Int32).alias("refused_lines"),
    ).with_columns(
        pl.when(pl.col("status") == VALID)
        .then(pl.col("points_partial"))
        .otherwise(None)
        .alias("points")
    )
    unplaced = rows.join(
        played.select("game_id", pl.col("opponent").alias("dst_team")),
        on=["game_id", "dst_team"],
        how="anti",
    )
    missing = cells.filter(pl.col("status") == "missing_dst_line")
    anomalies = {
        "dstLinesOutsideCompletedTeamGames": unplaced.height,
        "teamGamesWithoutOpposingDstLine": missing.height,
        "missingDstLineByOpposingTeamSeason": count_by(missing, "season", "opponent"),
    }
    return cells, anomalies


def observations(
    cells: pl.DataFrame, dst: pl.DataFrame, scoring: Mapping[str, str]
) -> pl.DataFrame:
    """The DvP observation table (`defense_game_position`), with row lineage (spec §2.1).

    `offense` scored the points; `defense` allowed them. `unit` is whose tendency the row
    measures: the defense for QB-K, the offense for D/ST (points conceded to opposing D/STs)."""
    keys = ("game_id", "season", "week", "kickoff", "available_at", "position")
    measures = ("points", "points_partial", "status", "lines", "refused_lines")
    athlete = cells.select(
        *keys,
        pl.col("team").alias("offense"),
        pl.col("opponent").alias("defense"),
        pl.col("opponent").alias("unit"),
        *measures,
        pl.lit("ffa_targets.athlete").alias("source_id"),
        pl.lit(scoring["athlete"]).alias("scoring_hash"),
    )
    defense = dst.select(
        *keys,
        pl.col("team").alias("offense"),
        pl.col("opponent").alias("defense"),
        pl.col("team").alias("unit"),
        *measures,
        pl.lit("ffa_targets.defense").alias("source_id"),
        pl.lit(scoring["defense"]).alias("scoring_hash"),
    )
    return (
        pl.concat([athlete, defense])
        .with_columns(
            pl.lit(SourceType.FFA_ACTUAL_FINAL.value).alias("source_type"),
            pl.lit("observed").alias("observed_or_generated"),
            pl.lit(FINALITY).alias("finality_basis"),
        )
        .sort("season", "week", "game_id", "offense", "position")
    )


def reconcile(schedule_games: pl.DataFrame, rows: pl.DataFrame) -> dict[str, Any]:
    """Per-season counts and structural checks of the observations against the schedule (§3.3)."""
    played = rows.select("game_id", "season", "offense", "defense").unique()
    seasons: dict[str, Any] = {}
    for (season,), part in schedule_games.group_by(["season"], maintain_order=True):
        done = part.filter(pl.col("status") == "completed")
        mine = played.filter(pl.col("season") == season)
        per_team = mine.group_by("offense").len()
        cells = rows.filter(pl.col("season") == season)
        seasons[str(season)] = {
            "scheduledGames": part.height,
            "completedGames": done.height,
            "notCompleted": sorted(part.filter(pl.col("status") != "completed")["game_id"]),
            "teamGames": mine.height,
            "teams": per_team.height,
            "gamesPerTeamValues": sorted(set(per_team.get_column("len").to_list())),
            "cellsByStatus": count_by(cells, "position", "status"),
        }
    pairs = played.join(
        played.select(
            "game_id", pl.col("offense").alias("defense"), pl.col("defense").alias("offense")
        ).with_columns(pl.lit(True).alias("mirrored")),
        on=["game_id", "offense", "defense"],
        how="left",
    )
    per_game = played.group_by("game_id").len()
    return {
        "seasons": seasons,
        "teamGames": played.height,
        "completedGames": per_game.height,
        "gamesWithoutExactlyTwoTeamGames": per_game.filter(pl.col("len") != 2).height,
        "teamGamesWithoutMirror": pairs.filter(pl.col("mirrored").is_null()).height,
        "duplicateGameIds": int(schedule_games.get_column("game_id").is_duplicated().sum()),
    }


def _by_season(frame: pl.DataFrame) -> dict[str, int]:
    counts = frame.group_by("season").len().sort("season")
    return {str(s): int(n) for s, n in counts.iter_rows()}


def count_by(frame: pl.DataFrame, *keys: str) -> dict[str, int]:
    counts = frame.group_by(*keys).len().sort(*keys)
    return {"/".join(str(v) for v in row[:-1]): int(row[-1]) for row in counts.iter_rows()}
