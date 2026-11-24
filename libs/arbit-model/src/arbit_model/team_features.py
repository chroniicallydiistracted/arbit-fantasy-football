"""Team environment, opponent defense and defense against the position, as of a decision time.

M3 slice 3b (OWN-068). One row per team per game: the team's own offense and defense to date
(raw, shrunk with measured constants, and last season), the opponent's defense, the opponent's
FFA points allowed to each position (raw and adjusted for the offenses it faced), the D/ST points
the opponent's offense gives up, and pre-game context. Definitions are in `feature_specs`.

Everything is computed from gamebooks at the decision time, so rows published after it never
change a feature (ADR-007; tested by mutation).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import polars as pl

from arbit_model.feature_specs import FEATURES, POSITIONS, SHRINKAGE, TEAM_RATES
from arbit_model.gamebook import Gamebook, Gamebooks
from arbit_model.point_in_time import KNOWN_FROM, PointInTime
from arbit_model.teams import franchise_columns

KEYS = ("game_id", "season", "week", "team", "opponent", "decision_at")
CONTEXT_COLUMNS = (
    "game_id",
    "season",
    "week",
    "home_team",
    "away_team",
    "home_rest",
    "away_rest",
    "roof",
    "surface",
    "div_game",
)
# Season-to-date team rates: (numerator, denominator; None means per game).
RATES: Mapping[str, tuple[str, str | None]] = {
    "off_plays_pg": ("plays", None),
    "off_dropback_rate": ("dropbacks", "plays"),
    "off_epa_per_play": ("epa", "plays"),
    "off_points_pg": ("points", None),
    "def_epa_per_play": ("opp_epa", "opp_plays"),
    "def_points_allowed_pg": ("allowed", None),
    "def_sack_rate": ("sacks", "opp_dropbacks"),
    "def_takeaways_pg": ("takeaways", None),
}
assert set(RATES) == {name for name, _, _ in TEAM_RATES}


@dataclass(frozen=True)
class TeamFeatures:
    frame: pl.DataFrame  # KEYS + every FEATURES column
    lineage: Mapping[str, Any]


def _ratio(numerator: str, denominator: str | None) -> pl.Expr:
    if denominator is None:
        return pl.col(numerator).sum() / pl.len()
    return pl.col(numerator).sum() / pl.col(denominator).sum()


def _rates(book: Gamebook) -> tuple[pl.DataFrame, dict[str, float | None]]:
    """Each team's rates over the book's games, and the league's."""
    games = book.team_games
    per_team = games.group_by("team").agg(
        pl.len().alias("games_played"),
        *(_ratio(*parts).alias(name) for name, parts in RATES.items()),
    )
    league = games.select(*(_ratio(*parts).alias(name) for name, parts in RATES.items()))
    means = league.row(0, named=True) if games.height else dict.fromkeys(RATES)
    return per_team, means


def _shrink(value: str, games: str, k: float, toward: pl.Expr) -> pl.Expr:
    n = pl.col(games).fill_null(0).cast(pl.Float64)
    return pl.when(n > 0).then((n * pl.col(value) + k * toward) / (n + k)).otherwise(toward)


def _positions(book: Gamebook) -> tuple[pl.DataFrame, dict[str, float | None]]:
    """Each defense's FFA points and opportunities allowed by position, raw and adjusted."""
    sides = book.team_games.select("game_id", "team", "opponent")
    grid = sides.join(pl.DataFrame({"position": list(POSITIONS)}), how="cross")
    rows = grid.join(
        book.position_points.select("game_id", "team", "position", "points", "opportunities"),
        on=["game_id", "team", "position"],
        how="left",
    ).with_columns(pl.col("points").fill_null(0.0), pl.col("opportunities").fill_null(0.0))
    league = (
        dict(rows.group_by("position").agg(pl.col("points").mean()).iter_rows())
        if rows.height
        else {}
    )
    by = ["team", "position"]
    total, count = pl.col("points").sum().over(by), pl.col("points").count().over(by)
    mean = pl.col("position").replace_strict(league, default=None, return_dtype=pl.Float64)
    rows = rows.with_columns(
        pl.when(count > 1)
        .then((total - pl.col("points")) / (count - 1))
        .otherwise(mean)
        .alias("expected")
    ).with_columns((pl.col("points") - pl.col("expected")).alias("adjusted"))
    allowed = rows.group_by(["opponent", "position"]).agg(
        pl.len().alias("n"),
        pl.col("points").mean().alias("pg"),
        pl.col("adjusted").mean().alias("adj"),
        pl.col("opportunities").mean().alias("opps_pg"),
    )
    return allowed.rename({"opponent": "defense"}), league


def _dst(book: Gamebook) -> tuple[pl.DataFrame, float | None]:
    """D/ST points each offense gave up, raw and adjusted for the D/STs it faced."""
    rows = book.dst_points.filter(pl.col("points").is_not_null())
    if not rows.height:
        empty = {"offense": pl.String, "n": pl.UInt32, "pg": pl.Float64, "adj": pl.Float64}
        return pl.DataFrame(schema=empty), None
    league = float(rows["points"].mean())  # type: ignore[arg-type]
    total, count = pl.col("points").sum().over("team"), pl.col("points").count().over("team")
    rows = rows.with_columns(
        pl.when(count > 1)
        .then((total - pl.col("points")) / (count - 1))
        .otherwise(league)
        .alias("expected")
    ).with_columns((pl.col("points") - pl.col("expected")).alias("adjusted"))
    allowed = rows.group_by("opponent").agg(
        pl.len().alias("n"),
        pl.col("points").mean().alias("pg"),
        pl.col("adjusted").mean().alias("adj"),
    )
    return allowed.rename({"opponent": "offense"}), league


def team_features(
    pit: PointInTime,
    books: Gamebooks,
    game_ids: Sequence[str],
    *,
    at: datetime | None = None,
) -> TeamFeatures:
    """Features for both teams of each game, as of `at` or, by default, each game's kickoff."""
    groups: dict[datetime, list[str]] = {}
    for game_id in game_ids:
        game = pit.calendar.game(game_id)
        if game is None:
            raise LookupError(f"UNKNOWN_GAME: {game_id}")
        decision = at or game.kickoff
        if decision is None:
            raise ValueError(f"NO_KICKOFF: {game_id}")
        groups.setdefault(decision, []).append(game.game_id)
    frames, lineages = [], []
    for decision, ids in sorted(groups.items()):
        frame, lineage = _at(pit, books, ids, decision)
        frames.append(frame)
        lineages.append(lineage)
    frame = pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()
    coverage = {
        name: round(1 - frame[name].null_count() / frame.height, 3) if frame.height else None
        for name in FEATURES
    }
    return TeamFeatures(frame, {"decisions": lineages, "coverage": coverage})


def _at(
    pit: PointInTime, books: Gamebooks, game_ids: Iterable[str], at: datetime
) -> tuple[pl.DataFrame, dict[str, Any]]:
    seasons = {pit.calendar.game(g).season for g in game_ids}  # type: ignore[union-attr]
    if len(seasons) != 1:
        raise ValueError("ONE_SEASON_PER_DECISION")
    season = seasons.pop()
    book, last = books.at(season, at), books.at(season - 1, at)
    rates, league = _rates(book)
    prev_rates, prev_league = _rates(last)
    means = {k: (v if v is not None else prev_league.get(k)) for k, v in league.items()}
    context = (
        pit.read("schedules/games", CONTEXT_COLUMNS, at)
        .frame.filter(pl.col("game_id").is_in(list(game_ids)))
        .drop(KNOWN_FROM, "_basis", "_manifest")
        .pipe(franchise_columns)
    )
    sides = pl.concat(
        [
            context.select(
                "game_id",
                "season",
                "week",
                pl.col("home_team").alias("team"),
                pl.col("away_team").alias("opponent"),
                pl.lit(True).alias("is_home"),
                pl.col("home_rest").cast(pl.Float64).alias("rest_days"),
                pl.col("away_rest").cast(pl.Float64).alias("opp_rest_days"),
                "roof",
                "surface",
                pl.col("div_game").cast(pl.Boolean),
            ),
            context.select(
                "game_id",
                "season",
                "week",
                pl.col("away_team").alias("team"),
                pl.col("home_team").alias("opponent"),
                pl.lit(False).alias("is_home"),
                pl.col("away_rest").cast(pl.Float64).alias("rest_days"),
                pl.col("home_rest").cast(pl.Float64).alias("opp_rest_days"),
                "roof",
                "surface",
                pl.col("div_game").cast(pl.Boolean),
            ),
        ]
    ).with_columns(pl.lit(at).alias("decision_at"))
    own = rates.with_columns(
        *(
            _shrink(
                name, "games_played", SHRINKAGE[name][0], pl.lit(means[name], pl.Float64)
            ).alias(name + "_shrunk")
            for name in RATES
        )
    )
    prev = prev_rates.select("team", *(pl.col(n).alias("prev_" + n) for n in RATES))
    opp = own.select(
        pl.col("team").alias("opponent"),
        pl.col("games_played").alias("opp_games_played"),
        *(
            pl.col(f"{name}_shrunk").alias(f"opp_{name}_shrunk")
            for name in (
                "def_epa_per_play",
                "def_points_allowed_pg",
                "def_sack_rate",
                "def_takeaways_pg",
            )
        ),
    )
    allowed, position_league = _positions(book)
    dvp = []
    for pos in POSITIONS:
        mean = position_league.get(pos)
        part = allowed.filter(pl.col("position") == pos).select(
            pl.col("defense").alias("opponent"),
            pl.col("pg").alias(f"opp_dvp_{pos}_pg"),
            _shrink("pg", "n", SHRINKAGE[f"dvp_{pos}"][0], pl.lit(mean, pl.Float64)).alias(
                f"opp_dvp_{pos}_pg_shrunk"
            ),
            pl.col("adj").alias(f"opp_dvp_{pos}_adj"),
            _shrink("adj", "n", SHRINKAGE[f"dvp_{pos}_adj"][0], pl.lit(0.0)).alias(
                f"opp_dvp_{pos}_adj_shrunk"
            ),
            pl.col("opps_pg").alias(f"opp_dvp_{pos}_opps_pg"),
        )
        dvp.append(part)
    dst, dst_league = _dst(book)
    dst = dst.select(
        pl.col("offense").alias("opponent"),
        pl.col("pg").alias("opp_off_dst_allowed_pg"),
        _shrink("pg", "n", SHRINKAGE["dst_allowed"][0], pl.lit(dst_league, pl.Float64)).alias(
            "opp_off_dst_allowed_pg_shrunk"
        ),
        pl.col("adj").alias("opp_off_dst_allowed_adj"),
        _shrink("adj", "n", SHRINKAGE["dst_allowed_adj"][0], pl.lit(0.0)).alias(
            "opp_off_dst_allowed_adj_shrunk"
        ),
    )
    frame = sides.join(own, on="team", how="left").join(prev, on="team", how="left")
    frame = frame.join(opp, on="opponent", how="left")
    for part in (*dvp, dst):
        frame = frame.join(part, on="opponent", how="left")
    # Teams with no game yet: their shrunk values are the league means.
    frame = frame.with_columns(
        pl.col("games_played").fill_null(0),
        pl.col("opp_games_played").fill_null(0),
        *(pl.col(f"{n}_shrunk").fill_null(pl.lit(means[n], pl.Float64)) for n in RATES),
        *(
            pl.col(f"opp_{n}_shrunk").fill_null(pl.lit(means[n], pl.Float64))
            for n in (
                "def_epa_per_play",
                "def_points_allowed_pg",
                "def_sack_rate",
                "def_takeaways_pg",
            )
        ),
    )
    frame = frame.select(*KEYS, *FEATURES)
    lineage = {
        "at": at.isoformat(),
        "season": season,
        "games": sorted(game_ids),
        "gamebook": dict(book.lineage),
        "previousSeason": dict(last.lineage),
        "leagueMeans": {k: v for k, v in means.items()},
        "positionLeagueMeans": position_league,
        "dstLeagueMean": dst_league,
    }
    return frame, lineage
