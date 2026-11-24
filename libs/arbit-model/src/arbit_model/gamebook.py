"""Completed games as known at a decision time, with FFA points by position and by D/ST.

Rows come only through the point-in-time reader (ADR-007). A game counts once its schedule score,
play-by-play, player statistics and team statistics are all known before the decision. Its FFA
lines are scored by the shared engine (`targets`, ADR-006) once per combination of the file
versions that supplied its rows, then cached: a stat correction in a later version is scored
again, and only decisions after that version see it.

Positions are nflverse's labels mapped to FFA's (`FB` scores as RB). A player-game nflverse lists
without a position, or at a position FFA doesn't score, adds to no position.

Only regular-season games count (R-074): every shrinkage constant was measured on regular seasons.
Team codes are franchise codes (`arbit_model.teams`, R-072), so the schedule's OAK and the
statistics' LV are one team.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import polars as pl
from arbit_core.rules import RuleSet
from arbit_data.nflverse.stat_lines import PLAY_COLUMNS

from arbit_model.point_in_time import KNOWN_FROM, MANIFEST, PointInTime
from arbit_model.targets import STAT_COLUMNS, SeasonRows, targets
from arbit_model.teams import franchise_columns

POSITIONS: Mapping[str, str] = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "HB": "RB",
    "WR": "WR",
    "TE": "TE",
    "K": "K",
    "PK": "K",
}
FFA_POSITIONS = ("QB", "RB", "WR", "TE", "K")
SCHEDULE_COLUMNS = (
    "game_id",
    "season",
    "week",
    "game_type",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
)
OPPORTUNITY_COLUMNS = ("attempts", "carries", "targets", "fg_att", "pat_att")
PLAYER_COLUMNS = tuple(
    dict.fromkeys(
        ("game_id", "season", "week", "team", "player_id", "position")
        + STAT_COLUMNS
        + OPPORTUNITY_COLUMNS
    )
)
TEAM_COLUMNS = (
    "game_id",
    "season",
    "week",
    "team",
    "attempts",
    "sacks_suffered",
    "carries",
    "passing_epa",
    "rushing_epa",
    "passing_interceptions",
    "fumbles_lost_total",
    "passing_yards",
    "rushing_yards",
    "sack_yards_lost",
    "def_interceptions",
    "fumble_recovery_opp",
    "def_fg_blocks",
    "def_punt_blocks",
    "def_pat_blocks",
)


@dataclass(frozen=True)
class Gamebook:
    season: int
    at: datetime
    games: pl.DataFrame  # game_id, week, game_type, home, away, home_score, away_score, known
    team_games: pl.DataFrame  # one row per team in each game: its own and its opponent's rows
    position_points: pl.DataFrame  # game_id, team (offense), opponent, position, points, opps
    dst_points: pl.DataFrame  # game_id, team (D/ST), opponent (offense), points
    lineage: Mapping[str, Any]


def _number(name: str) -> pl.Expr:
    return pl.col(name).cast(pl.Float64).fill_null(0.0)


def _opportunities(position: pl.Expr) -> pl.Expr:
    """The volume each FFA position's points come from."""
    return (
        pl.when(position == "QB")
        .then(_number("attempts") + _number("carries"))
        .when(position == "RB")
        .then(_number("carries") + _number("targets"))
        .when(position.is_in(["WR", "TE"]))
        .then(_number("targets"))
        .when(position == "K")
        .then(_number("fg_att") + _number("pat_att"))
        .otherwise(None)
    )


class Gamebooks:
    """Gamebooks for any season and decision time, sharing scored games across decisions."""

    def __init__(self, pit: PointInTime, rules: Mapping[str, RuleSet]) -> None:
        self.pit, self.rules = pit, rules
        self._scored: dict[tuple[str, ...], tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}

    def at(self, season: int, at: datetime) -> Gamebook:
        read = self.pit.read
        text = pl.String
        schedule = (
            read("schedules/games", SCHEDULE_COLUMNS, at)
            .frame.with_columns(
                pl.col("game_id", "game_type", "home_team", "away_team").cast(text),
                pl.col("season", "week").cast(pl.Int32),
                pl.col("home_score", "away_score").cast(pl.Float64),
            )
            .filter(
                (pl.col("season") == season)
                & (pl.col("game_type") == "REG")
                & pl.col("home_score").is_not_null()
            )
            .pipe(franchise_columns)
        )
        plays = read(f"pbp/play_by_play_{season}", PLAY_COLUMNS, at).frame.with_columns(
            pl.col("game_id").cast(text)
        )
        players = read(
            f"stats_player/stats_player_week_{season}", PLAYER_COLUMNS, at
        ).frame.with_columns(pl.col("game_id", "team", "player_id", "position").cast(text))
        players = franchise_columns(players)
        teams = franchise_columns(
            read(f"stats_team/stats_team_week_{season}", TEAM_COLUMNS, at).frame.with_columns(
                pl.col("game_id", "team").cast(text)
            )
        )
        complete = (
            set(schedule["game_id"].to_list())
            & set(plays["game_id"].drop_nulls().to_list())
            & set(players["game_id"].drop_nulls().to_list())
            & set(teams["game_id"].drop_nulls().to_list())
        )
        schedule = schedule.filter(pl.col("game_id").is_in(list(complete)))
        athletes: list[dict[str, Any]] = []
        defenses: list[dict[str, Any]] = []
        rescored = 0
        by_game = {
            name: frame.filter(pl.col("game_id").is_in(list(complete))).partition_by(
                "game_id", as_dict=True
            )
            for name, frame in (("plays", plays), ("players", players), ("teams", teams))
        }
        for game in schedule.iter_rows(named=True):
            gid = game["game_id"]
            parts = {name: frames[(gid,)] for name, frames in by_game.items()}
            key = (gid, game[MANIFEST], *(p[MANIFEST][0] for p in parts.values()))
            if key not in self._scored:
                self._scored[key] = self._score(season, game, parts)
                rescored += 1
            found_athletes, found_defenses = self._scored[key]
            athletes += found_athletes
            defenses += found_defenses
        position_points = self._by_position(athletes, players)
        dst_points = (
            pl.DataFrame(
                defenses,
                schema={
                    "game_id": pl.String,
                    "team": pl.String,
                    "opponent": pl.String,
                    "points": pl.Float64,
                },
            )
            if defenses
            else pl.DataFrame(
                schema={
                    "game_id": pl.String,
                    "team": pl.String,
                    "opponent": pl.String,
                    "points": pl.Float64,
                }
            )
        )
        games = schedule.select(
            "game_id",
            "week",
            "game_type",
            pl.col("home_team").alias("home"),
            pl.col("away_team").alias("away"),
            "home_score",
            "away_score",
            pl.col(KNOWN_FROM).alias("known"),
        )
        lineage = {
            "season": season,
            "at": at.isoformat(),
            "games": games.height,
            "scoredNow": rescored,
            "refusedAthleteLines": sum(1 for a in athletes if a["points"] is None),
        }
        return Gamebook(
            season, at, games, _team_games(games, teams), position_points, dst_points, lineage
        )

    def _score(
        self, season: int, game: Mapping[str, Any], parts: Mapping[str, pl.DataFrame]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows = SeasonRows(
            season=season,
            games=[dict(game)],
            plays=parts["plays"].to_dicts(),
            players=parts["players"].to_dicts(),
            teams=parts["teams"].to_dicts(),
            snaps=[],
            rosters=[],
            pfr_to_gsis={},
        )
        athletes, defenses = [], []
        for target in targets(rows, self.rules, []):
            points = float(target.points) if isinstance(target.points, Decimal) else None
            if target.role == "athlete":
                athletes.append(
                    {
                        "game_id": target.game_id,
                        "team": target.team,
                        "opponent": target.opponent,
                        "player_id": target.player_id,
                        "points": points,
                    }
                )
            else:
                defenses.append(
                    {
                        "game_id": target.game_id,
                        "team": target.team,
                        "opponent": target.opponent,
                        "points": points,
                    }
                )
        return athletes, defenses

    def _by_position(self, athletes: list[dict[str, Any]], players: pl.DataFrame) -> pl.DataFrame:
        schema = {
            "game_id": pl.String,
            "team": pl.String,
            "opponent": pl.String,
            "position": pl.String,
            "points": pl.Float64,
            "refused": pl.UInt32,
            "opportunities": pl.Float64,
        }
        if not athletes:
            return pl.DataFrame(schema=schema)
        lines = pl.DataFrame(
            athletes,
            schema={
                "game_id": pl.String,
                "team": pl.String,
                "opponent": pl.String,
                "player_id": pl.String,
                "points": pl.Float64,
            },
        )
        positioned = players.select(
            "game_id",
            pl.col("player_id").cast(pl.String),
            pl.col("position")
            .cast(pl.String)
            .replace_strict(dict(POSITIONS), default=None)
            .alias("position"),
            *OPPORTUNITY_COLUMNS,
        ).with_columns(_opportunities(pl.col("position")).alias("opportunities"))
        joined = lines.join(positioned, on=["game_id", "player_id"], how="inner").filter(
            pl.col("position").is_not_null()
        )
        return (
            joined.group_by(["game_id", "team", "opponent", "position"], maintain_order=True)
            .agg(
                pl.col("points").sum().alias("points"),
                pl.col("points").null_count().alias("refused"),
                pl.col("opportunities").sum().alias("opportunities"),
            )
            .select(list(schema))
            .cast(schema)  # type: ignore[arg-type]
        )


def _team_games(games: pl.DataFrame, teams: pl.DataFrame) -> pl.DataFrame:
    """One row per team per game with the signal study's definitions (ffa_signal_study.py):
    plays = attempts + sacks + carries; dropbacks = attempts + sacks; offensive EPA = passing +
    rushing EPA; sacks forced and takeaways from the opponent's row."""
    own = teams.select(
        "game_id",
        pl.col("team").cast(pl.String),
        (_number("attempts") + _number("sacks_suffered") + _number("carries")).alias("plays"),
        (_number("attempts") + _number("sacks_suffered")).alias("dropbacks"),
        (_number("passing_epa") + _number("rushing_epa")).alias("epa"),
        _number("sacks_suffered").alias("sacked"),
        (_number("passing_interceptions") + _number("fumbles_lost_total")).alias("giveaways"),
    )
    sides = pl.concat(
        [
            games.select(
                "game_id",
                "week",
                pl.col("home").alias("team"),
                pl.col("away").alias("opponent"),
                pl.lit(True).alias("home"),
                pl.col("home_score").cast(pl.Float64).alias("points"),
                pl.col("away_score").cast(pl.Float64).alias("allowed"),
            ),
            games.select(
                "game_id",
                "week",
                pl.col("away").alias("team"),
                pl.col("home").alias("opponent"),
                pl.lit(False).alias("home"),
                pl.col("away_score").cast(pl.Float64).alias("points"),
                pl.col("home_score").cast(pl.Float64).alias("allowed"),
            ),
        ]
    )
    theirs = own.rename(
        {
            "team": "opponent",
            "plays": "opp_plays",
            "dropbacks": "opp_dropbacks",
            "epa": "opp_epa",
            "sacked": "sacks",
            "giveaways": "takeaways",
        }
    )
    return sides.join(own, on=["game_id", "team"], how="inner").join(
        theirs, on=["game_id", "opponent"], how="inner"
    )
