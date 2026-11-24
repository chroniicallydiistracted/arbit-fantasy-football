"""Prospective (shadow) forecasting for the M3-3 DvP study: a versioned adapter around the frozen
walk-forward method. Owner audit remediations 1 and 5 (AUD-01, AUD-05).

**Why it exists.** The frozen `walkforward.walk` takes its targets from completed observation rows,
so it can forecast only games that already have a valid label. A true prospective forecast is made
before the game, and an honest backtest decides what to forecast before knowing which labels will
turn out valid. Here the stages are separate:

1. `scheduled_targets`: the target universe, from the schedule alone. Every scheduled team-game
   and position group, whatever its eventual score or label status.
2. `walk_targets`: the frozen estimator over those targets. It runs the same steps as `walk`,
   built from `walkforward`'s own functions (`_previous_season`, `_b00`, `_opponent_terms`,
   `_variants`) and `asof`'s cutoffs and feature views. Only the source of the targets differs.
3. `forecast_only`: keys, timing and forecast columns; never a label.
4. Persistence is the caller's: write once, hash, ledger (`ledger_entry`, `verify_ledger`).
5. `attach_labels`: later, actual outcomes joined to the stored forecasts without dropping a
   target. A missing or invalid label stays a row with its reason (`label_status`).

Nothing here fits anything new, reads a database or writes a file. `ADAPTER` versions it; the
frozen files are never edited (config/dvp/frozen.json pins their hashes).
"""

import hashlib
import json
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

import numpy as np
import polars as pl

from arbit_model.dvp import asof
from arbit_model.dvp import observations as obs
from arbit_model.dvp import walkforward as wf
from arbit_model.dvp.provenance import LineageError

ADAPTER = "arbit-dvp-shadow-v1"
TARGET_COLUMNS = (
    "game_id",
    "season",
    "week",
    "kickoff",
    "offense",
    "defense",
    "position",
    "side",
    "opp",
)
KEYS = ("game_id", "offense", "position")
# What a stored forecast may hold: keys, timing, history count and forecasts. Never a label.
FORECAST_META = ("season", "week", "kickoff", "defense", "feature_as_of", "n_d")
MISSING_LABEL = "missing"  # no observation row: the game was not completed or has no FFA lines


def scheduled_targets(
    schedule_games: pl.DataFrame,
    season: int,
    weeks: Iterable[int] | None,
    positions: Sequence[str],
) -> pl.DataFrame:
    """Every scheduled regular-season team-game of the season (and weeks) for each position group.

    Built from the schedule only: no score, status or label is read. For QB to K the offense
    scores and the defense is the opposing unit; for D/ST the scoring side is the defense (the
    D/ST that faces the offense) and the opposing unit is the offense, as in `walkforward.prepare`.
    """
    games = schedule_games.filter(pl.col("season") == season)
    if weeks is not None:
        games = games.filter(pl.col("week").is_in(list(weeks)))
    keys = ("game_id", "season", "week", "kickoff")
    bad = games.filter(
        pl.col("home").is_null() | pl.col("away").is_null() | (pl.col("home") == pl.col("away"))
    )
    if bad.height:
        raise LineageError("SCHEDULE_TEAMS", f"{bad.height} games lack two distinct teams")
    if games.select("game_id").is_duplicated().any():
        raise LineageError("DUPLICATE_KEY", "schedule game_id")
    sides = pl.concat(
        [
            games.select(*keys, pl.col("home").alias("offense"), pl.col("away").alias("defense")),
            games.select(*keys, pl.col("away").alias("offense"), pl.col("home").alias("defense")),
        ]
    )
    frames = []
    for position in positions:
        dst = position == obs.DST
        frames.append(
            sides.with_columns(
                pl.lit(position).alias("position"),
                pl.col("defense" if dst else "offense").alias("side"),
                pl.col("offense" if dst else "defense").alias("opp"),
            )
        )
    if not frames:
        return pl.DataFrame(schema=dict.fromkeys(TARGET_COLUMNS, pl.String))
    return pl.concat(frames).select(TARGET_COLUMNS).sort("position", "game_id", "offense")


def walk_targets(
    rows: pl.DataFrame,
    targets: pl.DataFrame,
    schedule_games: pl.DataFrame,
    params: wf.FoldParams,
    positions: Sequence[str],
    settings: wf.Settings,
) -> asof.FrozenForecasts:
    """The frozen walk-forward forecasts for explicitly given targets of `params.season`.

    The steps are `walkforward.walk`'s, in the same order and with the same random stream: cutoffs
    from the schedule, then per cutoff the feature view, B00, the non-touchdown B00, the opposing
    units' terms and the variants, accumulating each cutoff's B00 as the point-in-time baseline of
    later residuals. Targets of earlier cutoffs must be included, because later residuals need
    their B00. Returns frozen forecasts with no label column."""
    s = params.season
    if settings.availability_delay:
        rows = rows.with_columns(pl.col("available_at") + settings.availability_delay)
    cut = asof.cutoffs(schedule_games.filter(pl.col("season") == s), settings.mode)
    wanted = targets.filter(
        (pl.col("season") == s) & pl.col("position").is_in(list(positions))
    ).select("game_id", "offense", "position", "side", "opp", "week")
    if wanted.select(KEYS).is_duplicated().any():
        raise LineageError("DUPLICATE_KEY", "targets")
    batch_all = wanted.join(cut, on="game_id", how="inner")
    if batch_all.height != wanted.height:
        raise LineageError("NO_CUTOFF", f"{wanted.height - batch_all.height} targets lack a cutoff")
    history = rows.filter(pl.col("season").is_in([s - 1, s]))
    previous = wf._previous_season(rows, s, positions)
    rng = np.random.default_rng(settings.seed + s)
    pit = pl.DataFrame(
        schema={
            "game_id": pl.String,
            "side": pl.String,
            "position": pl.String,
            "b00_pit": pl.Float64,
            "b00_nontd_pit": pl.Float64,
        }
    )
    out = []
    for cutoff in sorted(set(batch_all.get_column("cutoff").to_list())):
        view = asof.features_as_of(history, cutoff, settings.mode)
        hist = view.frame.filter(pl.col("season") == s)
        batch = batch_all.filter(pl.col("cutoff") == cutoff)
        forecast = wf._b00(batch, hist, previous, params, "points", "b00")
        forecast = wf._b00(forecast, hist, previous, params, "nontd", "b00_nontd")
        terms = wf._opponent_terms(hist, pit, params, settings)
        forecast = wf._variants(forecast, terms, previous, params, settings, rng, hist)
        out.append(forecast.with_columns(pl.lit(cutoff).alias("feature_as_of")))
        pit = pl.concat(
            [
                pit,
                forecast.select(
                    "game_id",
                    "side",
                    "position",
                    pl.col("b00").alias("b00_pit"),
                    pl.col("b00_nontd").alias("b00_nontd_pit"),
                ),
            ]
        )
    frame = pl.concat(out, how="diagonal_relaxed").drop("cutoff", "side", "opp")
    return asof.FrozenForecasts(frozen_at=datetime.now(UTC), frame=frame)


def forecast_columns(frame: pl.DataFrame) -> list[str]:
    return sorted(c for c in frame.columns if c.startswith("b0"))


def forecast_only(forecasts: asof.FrozenForecasts, targets: pl.DataFrame) -> pl.DataFrame:
    """The stored artifact: keys, season, week, kickoff, the defense, the cutoff, the opposing
    unit's game count and every forecast; never a label, score or status."""
    leaked = asof.LABEL_COLUMNS & set(forecasts.frame.columns)
    if leaked:
        raise LineageError("LABEL_IN_FORECAST", ", ".join(sorted(leaked)))
    meta = targets.select(*KEYS, "season", "kickoff", "defense")
    frame = forecasts.frame.join(meta, on=list(KEYS), how="left", validate="1:1")
    columns = [*KEYS, *FORECAST_META, *forecast_columns(frame)]
    return frame.select(columns).sort("position", "game_id", "offense")


def content_sha256(frame: pl.DataFrame) -> str:
    """Order-free fingerprint: rows by key, columns by name, floats to 6 decimals, as CSV."""
    keyed = frame.select(sorted(frame.columns)).sort(list(KEYS))
    keyed = keyed.with_columns(
        [pl.col(c).round(6) for c, t in keyed.schema.items() if t.is_float()]
    )
    return hashlib.sha256(keyed.write_csv().encode()).hexdigest()


def attach_labels(forecasts: pl.DataFrame, observations: pl.DataFrame) -> pl.DataFrame:
    """Stored forecasts beside their actual outcomes, keeping every target.

    `label_status` is the observation's status (`valid`, `invalid_*`, `missing_coverage`) or
    `missing` when no observation exists (a game not completed, canceled or not yet scored).
    `points` is null unless the label is valid. A forecast whose cutoff is after its game's
    kickoff is refused."""
    if forecasts.select(KEYS).is_duplicated().any():
        raise LineageError("DUPLICATE_KEY", "forecasts")
    if (forecasts.get_column("feature_as_of") > forecasts.get_column("kickoff")).any():
        raise LineageError("FEATURE_AFTER_KICKOFF", "a forecast used data after its game began")
    labels = observations.select(
        *KEYS, pl.col("status").alias("label_status"), pl.col("points").alias("label_points")
    )
    if labels.select(KEYS).is_duplicated().any():
        raise LineageError("DUPLICATE_KEY", "labels")
    joined = forecasts.join(labels, on=list(KEYS), how="left", validate="1:1")
    return (
        joined.with_columns(
            pl.col("label_status").fill_null(MISSING_LABEL),
            pl.when(pl.col("label_status") == obs.VALID)
            .then(pl.col("label_points").cast(pl.Float64))
            .otherwise(None)
            .alias("points"),
        )
        .drop("label_points")
        .with_columns(pl.col("label_status").alias("status"))
    )


def coverage(labelled: pl.DataFrame) -> dict[str, Any]:
    """Targets, forecasts and labels by status, per position: nothing is dropped silently."""
    out: dict[str, Any] = {}
    for (position,), part in labelled.group_by(["position"], maintain_order=True):
        counts = part.group_by("label_status").len().sort("label_status")
        out[str(position)] = {
            "targets": part.height,
            "labels": {r["label_status"]: r["len"] for r in counts.iter_rows(named=True)},
            "evaluated": part.filter(pl.col("label_status") == obs.VALID).height,
        }
    return dict(sorted(out.items()))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def ledger_entry(previous: str | None, record: dict[str, Any]) -> dict[str, Any]:
    """An append-only ledger line: the record, the previous line's hash, and its own hash over
    both. Editing or deleting an earlier line breaks every later hash."""
    entry = {**record, "previousEntrySha256": previous}
    entry["entrySha256"] = hashlib.sha256(_canonical(entry)).hexdigest()
    return entry


def verify_ledger(lines: Sequence[dict[str, Any]]) -> list[str]:
    """Problems in a ledger's hash chain, or [] when every line links to the one before it."""
    problems, previous = [], None
    for number, line in enumerate(lines, start=1):
        body = {k: v for k, v in line.items() if k != "entrySha256"}
        if line.get("previousEntrySha256") != previous:
            problems.append(f"line {number}: previous hash does not match line {number - 1}")
        if hashlib.sha256(_canonical(body)).hexdigest() != line.get("entrySha256"):
            problems.append(f"line {number}: its hash does not match its content")
        previous = line.get("entrySha256")
    return problems


def league_choices(
    forecasts: pl.DataFrame,
    rosters: dict[str, list[str]],
    free_agents: Sequence[str],
    models: Sequence[str],
) -> pl.DataFrame:
    """League-constrained D/ST choices (config/dvp/prospective.json, `leagueEvaluation`).

    Per FFA team and model: `start`, the highest-forecast D/ST among those the team rostered at
    the capture (only teams holding two or more D/STs have a choice), and `stream`, the
    highest-forecast D/ST among those rostered and the free agents at the capture. Ties break by
    franchise code. A D/ST with no game that week (a bye) can't be chosen."""
    dst = forecasts.filter(pl.col("position") == obs.DST).select(
        pl.col("defense").alias("unit"), *models
    )
    playing = set(dst.get_column("unit").to_list())
    rows = []
    for team, held in sorted(rosters.items()):
        for decision, pool in (("start", held), ("stream", [*held, *free_agents])):
            candidates = sorted({u for u in pool if u in playing})
            if len(candidates) < (2 if decision == "start" else 1):
                continue  # one playing D/ST is no start choice; none is no stream choice
            options = dst.filter(pl.col("unit").is_in(candidates))
            row: dict[str, Any] = {"team": team, "decision": decision, "options": len(candidates)}
            for model in models:
                best = options.sort([model, "unit"], descending=[True, False]).row(0, named=True)
                row[f"pick_{model}"] = best["unit"]
            rows.append(row)
    schema = {"team": pl.String, "decision": pl.String, "options": pl.Int64}
    schema |= {f"pick_{m}": pl.String for m in models}
    return pl.DataFrame(rows, schema=schema)
