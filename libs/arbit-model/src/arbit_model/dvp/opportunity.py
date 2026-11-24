"""Opportunity volume and scoring efficiency allowed (owner audit AUD-02, remediation 2). EXPLORATORY.

A defense that allows 30 WR points on 25 targets (1.2 points per target) is not the same as one
that allows 30 on 15 targets (2.0). Total points allowed hides which part repeats. This module
splits each team-game-position cell into volume, and efficiency (FFA points per unit of volume),
and measures each part's repeatability.

**Sources.** nflverse weekly player and team statistics: the exact files (manifests) each
season's FFA targets were built from. They enter through `admit_realized`, which applies the
firewall's rules (`provenance.admit`'s checks and the same field catalog) to a versioned
allowlist of realized-statistics sources. `provenance.py` is frozen (config/dvp/frozen.json), so
its allowlist is not edited. Excluded columns (the generic fantasy points) are dropped and
recorded; an unknown column stops the run.

**Volume per cell**, from the players scored at that FFA group (positions mapped as the targets
map them, FB and HB to RB):

| Group | Volume | Also kept |
| --- | --- | --- |
| QB | dropbacks (pass attempts + sacks suffered) + carries | attempts, sacks, carries |
| RB | carries + targets | receptions |
| WR, TE | targets | receptions |
| K | field-goal + extra-point attempts | |
| D/ST | the offense's plays (pass attempts + sacks suffered + carries): the D/ST's opportunities | the offense's dropbacks, sacks suffered, turnovers |

**Efficiency** is FFA points per unit of volume. A cell with zero volume keeps volume 0 and has no
efficiency, never a division by zero. A cell with no statistics rows has `volume_status`
`missing`.
"""

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import polars as pl

from arbit_model.dvp import lab
from arbit_model.dvp import observations as obs
from arbit_model.dvp.provenance import (
    INPUT_TYPES,
    Admission,
    LineageError,
    SourceSpec,
    SourceType,
)
from arbit_model.fields import classify
from arbit_model.gamebook import POSITIONS
from arbit_model.teams import franchise_expr

PLAYER_VOLUME = (
    "attempts",
    "sacks_suffered",
    "carries",
    "targets",
    "receptions",
    "fg_att",
    "pat_att",
)
TEAM_VOLUME = (
    "attempts",
    "sacks_suffered",
    "carries",
    "passing_interceptions",
    "fumbles_lost_total",
)
SEASON_TYPES = frozenset({"REG", "POST"})
KEYS = ("game_id", "offense", "position")

SOURCES_V2: Mapping[str, SourceSpec] = {
    spec.source_id: spec
    for spec in (
        SourceSpec(
            "nflverse.stats_player",
            SourceType.REALIZED_NFL_STAT,
            "nflverse",
            "Weekly player statistics of completed games: opportunity counts only",
            used=(
                "game_id",
                "season",
                "week",
                "season_type",
                "team",
                "player_id",
                "position",
                *PLAYER_VOLUME,
            ),
            family="stats_player",
            values={"season_type": SEASON_TYPES},
        ),
        SourceSpec(
            "nflverse.stats_team",
            SourceType.REALIZED_NFL_STAT,
            "nflverse",
            "Weekly team statistics of completed games: plays, sacks and turnovers",
            used=("game_id", "season", "week", "season_type", "team", *TEAM_VOLUME),
            family="stats_team",
            values={"season_type": SEASON_TYPES},
        ),
    )
}


def admit_realized(
    frame: pl.DataFrame,
    source_id: str,
    *,
    ancestry: str | None,
    schema: Sequence[str] | None = None,
    sources: Mapping[str, SourceSpec] = SOURCES_V2,
) -> Admission:
    """`provenance.admit`'s checks for a source on the versioned realized-statistics allowlist:
    known source, input type, ancestry, every column classified by the field catalog (excluded
    ones dropped and recorded), used columns present and allowed, row values known."""
    spec = sources.get(source_id)
    if spec is None:
        raise LineageError("UNKNOWN_SOURCE", source_id)
    if spec.source_type not in INPUT_TYPES or spec.source_type is not SourceType.REALIZED_NFL_STAT:
        raise LineageError("FORBIDDEN_SOURCE_TYPE", f"{source_id}: {spec.source_type}")
    if not ancestry:
        raise LineageError("MISSING_ANCESTRY", source_id)
    if spec.family is None:
        raise LineageError("UNKNOWN_SOURCE", f"{source_id} has no catalog family")
    dropped: dict[str, str] = {}
    for column in list(schema) if schema is not None else frame.columns:
        rule = classify(spec.family, column)
        if rule is None:
            raise LineageError("UNKNOWN_COLUMN", f"{source_id}.{column}")
        if rule.use == "excluded":
            dropped[column] = rule.id
    for column in spec.used:
        if column not in frame.columns:
            raise LineageError("MISSING_COLUMN", f"{source_id}.{column}")
        if column in dropped:
            raise LineageError("EXCLUDED_COLUMN_USED", f"{source_id}.{column}")
    for column, allowed in spec.values.items():
        seen = set(frame.get_column(column).drop_nulls().unique().to_list())
        if not seen <= allowed:
            raise LineageError("UNKNOWN_VALUE", f"{source_id}.{column}: {sorted(seen - allowed)}")
    return Admission(
        source_id=source_id,
        source_type=spec.source_type,
        provider=spec.provider,
        ancestry=ancestry,
        scoring_hash=None,
        used=spec.used,
        dropped=dropped,
        rows=frame.height,
        frame=frame.select(spec.used),
    )


def _n(name: str) -> pl.Expr:
    return pl.col(name).cast(pl.Float64).fill_null(0.0)


def player_volumes(players: pl.DataFrame) -> pl.DataFrame:
    """Regular-season opportunity counts per game, franchise and FFA group."""
    rows = players.filter(pl.col("season_type") == "REG").with_columns(
        franchise_expr(pl.col("team")).alias("offense"),
        pl.col("position")
        .cast(pl.String)
        .replace_strict(dict(POSITIONS), default=None)
        .alias("position"),
    )
    grouped = (
        rows.filter(pl.col("position").is_not_null())
        .group_by("game_id", "offense", "position")
        .agg(*[_n(c).sum().alias(c) for c in PLAYER_VOLUME], pl.len().alias("players"))
    )
    dropbacks = pl.col("attempts") + pl.col("sacks_suffered")
    volume = (
        pl.when(pl.col("position") == "QB")
        .then(dropbacks + pl.col("carries"))
        .when(pl.col("position") == "RB")
        .then(pl.col("carries") + pl.col("targets"))
        .when(pl.col("position").is_in(["WR", "TE"]))
        .then(pl.col("targets"))
        .when(pl.col("position") == "K")
        .then(pl.col("fg_att") + pl.col("pat_att"))
        .otherwise(None)
    )
    return grouped.with_columns(volume.alias("volume"), dropbacks.alias("dropbacks"))


def dst_volumes(teams: pl.DataFrame) -> pl.DataFrame:
    """Per game and offense: the plays a D/ST faced, and the offense's sacks and turnovers."""
    rows = teams.filter(pl.col("season_type") == "REG").with_columns(
        franchise_expr(pl.col("team")).alias("offense")
    )
    dropbacks = _n("attempts") + _n("sacks_suffered")
    return rows.select(
        "game_id",
        "offense",
        pl.lit(obs.DST).alias("position"),
        (dropbacks + _n("carries")).alias("volume"),
        dropbacks.alias("dropbacks"),
        _n("sacks_suffered").alias("sacks_suffered"),
        (_n("passing_interceptions") + _n("fumbles_lost_total")).alias("turnovers"),
        _n("carries").alias("carries"),
    )


def cells(observations: pl.DataFrame, players: pl.DataFrame, teams: pl.DataFrame) -> pl.DataFrame:
    """Every observation cell with its volume, the volume's components and `volume_status`:
    `ok`, `zero` (statistics present, no volume) or `missing` (no statistics rows)."""
    athletes = player_volumes(players)
    dst = dst_volumes(teams)
    if athletes.select(KEYS).is_duplicated().any() or dst.select(KEYS).is_duplicated().any():
        raise LineageError("DUPLICATE_KEY", "opportunity cells")
    volumes = pl.concat([athletes, dst], how="diagonal_relaxed")
    joined = observations.select(
        "game_id", "season", "week", "offense", "defense", "unit", "position", "points", "status"
    ).join(volumes, on=list(KEYS), how="left")
    status = (
        pl.when(pl.col("volume").is_null())
        .then(pl.lit("missing"))
        .when(pl.col("volume") == 0)
        .then(pl.lit("zero"))
        .otherwise(pl.lit("ok"))
    )
    efficiency = pl.when(pl.col("volume") > 0).then(pl.col("points") / pl.col("volume"))
    return joined.with_columns(status.alias("volume_status"), efficiency.alias("efficiency"))


def reconcile(players: pl.DataFrame, teams: pl.DataFrame) -> dict[str, Any]:
    """Player opportunity counts summed per team-game against the team statistics."""
    p = (
        players.filter(pl.col("season_type") == "REG")
        .with_columns(franchise_expr(pl.col("team")).alias("offense"))
        .group_by("game_id", "offense")
        .agg(*[_n(c).sum().alias(c) for c in ("attempts", "sacks_suffered", "carries")])
    )
    t = (
        teams.filter(pl.col("season_type") == "REG")
        .with_columns(franchise_expr(pl.col("team")).alias("offense"))
        .select(
            "game_id",
            "offense",
            *[_n(c).alias(f"{c}_team") for c in ("attempts", "sacks_suffered", "carries")],
        )
    )
    joined = t.join(p, on=["game_id", "offense"], how="full", coalesce=True)
    out: dict[str, Any] = {
        "teamGames": t.height,
        "teamGamesWithoutPlayers": joined.filter(pl.col("attempts").is_null()).height,
        "playerTeamGamesWithoutTeam": joined.filter(pl.col("attempts_team").is_null()).height,
    }
    both = joined.drop_nulls()
    for c in ("attempts", "sacks_suffered", "carries"):
        gap = (both.get_column(c) - both.get_column(f"{c}_team")).abs()
        out[c] = {
            "equal": int((gap == 0).sum()),
            "differ": int((gap > 0).sum()),
            "maxDifference": float(gap.max() or 0.0),  # type: ignore[arg-type]
        }
    return out


def coverage(table: pl.DataFrame) -> dict[str, Any]:
    """Per position: cells by label status and volume status, and valid cells usable for
    efficiency (volume above zero)."""
    out: dict[str, Any] = {}
    for (position,), part in table.group_by(["position"], maintain_order=True):
        valid = part.filter(pl.col("status") == obs.VALID)
        out[str(position)] = {
            "cells": part.height,
            "validLabels": valid.height,
            "volume": dict(sorted(valid.group_by("volume_status").len().iter_rows())),
            "validWithEfficiency": valid.filter(pl.col("efficiency").is_not_null()).height,
            "trueZeroPointsWithVolume": valid.filter(
                (pl.col("points") == 0) & (pl.col("volume") > 0)
            ).height,
            "pointsWithoutVolume": valid.filter(
                (pl.col("points") != 0) & (pl.col("volume") == 0)
            ).height,
            # No statistics row: players who played without one. Kept missing, never imputed.
            "missingVolumeWithPoints": valid.filter(
                (pl.col("volume_status") == "missing") & (pl.col("points") != 0)
            ).height,
        }
    return dict(sorted(out.items()))


def unit_frame(table: pl.DataFrame, position: str, value: str) -> pl.DataFrame:
    """The lab's frame for one measure of one group: the unit whose tendency is measured (the
    defense for QB-K, the offense for D/ST) and the side it faced."""
    dst = position == obs.DST
    rows = table.filter(
        (pl.col("position") == position)
        & (pl.col("status") == obs.VALID)
        & pl.col(value).is_not_null()
    )
    return rows.select(
        "season",
        "week",
        "game_id",
        pl.col("unit").alias("entity"),
        pl.col("defense" if dst else "offense").alias("faced"),
        pl.col(value).cast(pl.Float64).alias("points"),
        pl.lit(False).alias("home"),
    )


def reliability(
    table: pl.DataFrame, positions: Sequence[str], reps: int, seed: int
) -> dict[str, Any]:
    """REML k for points, volume and efficiency allowed (leave-one-out adjusted for the side
    faced), with season-cluster intervals, and how the unit-season tendencies correlate."""
    out: dict[str, Any] = {}
    for position in positions:
        entry: dict[str, Any] = {}
        means: dict[str, pl.DataFrame] = {}
        for measure in ("points", "volume", "efficiency"):
            frame = lab.adjust(unit_frame(table, position, measure), "loo_mean")
            g = lab.groups(frame)
            fit = lab.reml_components(g)
            boot = lab.bootstrap_components(g, reps, seed, lab.reml_components)
            entry[measure] = {
                "cells": g.cells,
                "unitSeasons": int(g.size.size),
                "k": None if fit.k is None else round(fit.k, 2),
                "converged": fit.converged,
                "boundary": fit.boundary,
                "k95Seasons": boot["k95"],
                "boundaryShare": boot["boundaryShare"],
            }
            means[measure] = frame.group_by("entity", "season").agg(
                pl.col("value").mean().alias(measure)
            )
        joined = (
            means["points"]
            .join(means["volume"], on=["entity", "season"])
            .join(means["efficiency"], on=["entity", "season"], how="left")
            .drop_nulls()
        )
        entry["unitSeasonCorrelation"] = {
            f"{a}~{b}": _corr(joined.get_column(a).to_numpy(), joined.get_column(b).to_numpy())
            for a, b in (("volume", "efficiency"), ("points", "volume"), ("points", "efficiency"))
        }
        out[position] = entry
    return out


def _corr(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size < 3 or np.std(a) == 0 or np.std(b) == 0:
        return None
    value = float(np.corrcoef(a, b)[0, 1])
    return None if math.isnan(value) else round(value, 4)
