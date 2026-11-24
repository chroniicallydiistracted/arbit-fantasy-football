"""M3-3 Phase B: walk-forward forecasts of next-game FFA position totals (spec §5 Phase B, §6, §7).

For every target cell (a team-game and position group) of a season, each forecast uses only the
FFA actuals available before its cutoff (`asof.features_as_of`) and parameters fit on earlier
seasons. Forecasts are frozen before any label is joined (`asof.evaluation_join`).

**Sides.** The side that scores is the offense for QB to K and the D/ST for D/ST; the opposing
unit, whose tendency DvP measures, is the defense for QB to K and the offense for D/ST.

**B00** (declared in METHODOLOGY.md before this ran) uses no opponent information: a prior from
the side's own last season, regressed toward last season's league mean by a slope fit on training
seasons, then updated with the side's completed games this season with its own k.

**DvP variants** add a term for the opposing unit's residuals in its completed games this season:
- residuals against the point-in-time B00 forecasts made for those games (`pit`), or against
  baselines recomputed from what is known at the current cutoff (`rec`);
- unshrunk, or shrunk by n / (n + k) with k fit on training seasons, or a grid of k (B04),
  recency-weighted (B05), with a prior from last season (B06), or on non-touchdown points (B07).
Controls (B09) replace the opponent's residuals with another unit's, noise, or last week's opponent.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import polars as pl

from arbit_model.dvp import asof, lab
from arbit_model.dvp import observations as obs
from arbit_model.dvp.provenance import LineageError

ALLOWED_COLUMNS = frozenset(
    {
        "game_id",
        "season",
        "week",
        "kickoff",
        "available_at",
        "position",
        "offense",
        "defense",
        "unit",
        "points",
        "points_partial",
        "status",
        "lines",
        "refused_lines",
        "source_id",
        "scoring_hash",
        "source_type",
        "observed_or_generated",
        "finality_basis",
        "nontd",
    }
)
NO_K = math.inf  # an unidentified k: the unit's own record earns no weight


@dataclass(frozen=True)
class FoldParams:
    """Parameters for forecasting `season`, fit on seasons before it only."""

    season: int
    training: tuple[int, ...]
    league_prev: Mapping[str, float]
    league_prev_nontd: Mapping[str, float]
    k_own: Mapping[str, float]
    slope_own: Mapping[str, float]
    k_dvp: Mapping[str, float]
    slope_dvp: Mapping[str, float]
    k_nontd: Mapping[str, float]
    k_own_nontd: Mapping[str, float]

    def summary(self) -> dict[str, Any]:
        def clean(values: Mapping[str, float]) -> dict[str, float | None]:
            return {k: None if math.isinf(v) else round(v, 3) for k, v in values.items()}

        return {
            "season": self.season,
            "training": list(self.training),
            "leaguePrev": clean(self.league_prev),
            "kOwn": clean(self.k_own),
            "slopeOwn": clean(self.slope_own),
            "kDvp": clean(self.k_dvp),
            "slopeDvp": clean(self.slope_dvp),
            "kNonTd": clean(self.k_nontd),
        }


def prepare(observations: pl.DataFrame) -> pl.DataFrame:
    """Valid regular-season cells with their scoring side and opposing unit. Fails closed on any
    column it does not know (a planted projection cannot ride along, T32/B11)."""
    unknown = set(observations.columns) - ALLOWED_COLUMNS
    if unknown:
        raise LineageError("UNKNOWN_COLUMN", ", ".join(sorted(unknown)))
    dst = pl.col("position") == obs.DST
    rows = observations.filter(pl.col("status") == obs.VALID).with_columns(
        pl.when(dst).then(pl.col("defense")).otherwise(pl.col("offense")).alias("side"),
        pl.when(dst).then(pl.col("offense")).otherwise(pl.col("defense")).alias("opp"),
        pl.col("points").cast(pl.Float64),
    )
    if "nontd" not in rows.columns:
        rows = rows.with_columns(pl.col("points").alias("nontd"))
    return rows


def _frame(rows: pl.DataFrame, entity: str, faced: str, value: str) -> pl.DataFrame:
    return rows.select(
        "season",
        "week",
        "game_id",
        pl.col(entity).alias("entity"),
        pl.col(faced).alias("faced"),
        pl.col(value).alias("points"),
        pl.lit(False).alias("home"),
    )


def _k(frame: pl.DataFrame, adjustment: str) -> float:
    g = lab.groups(lab.adjust(frame, adjustment))
    if g.size.size < 2:
        return NO_K
    fit = lab.reml_components(g)
    return NO_K if fit.k is None or not fit.converged else fit.k


def _slope(frame: pl.DataFrame, adjustment: str) -> float:
    pairs = lab.carryover(lab.adjust(frame, adjustment), 8)
    if pairs.height < 20:
        return 0.0  # not estimable: reset to the league (the conservative prior)
    b = lab.slope(pairs.get_column("mean").to_numpy(), pairs.get_column("next_mean").to_numpy())
    return 0.0 if b is None else max(b, 0.0)


def fit_fold(rows: pl.DataFrame, season: int, positions: Sequence[str]) -> FoldParams:
    """Every parameter for forecasting `season`, from seasons before it (T17, T18)."""
    train = rows.filter(pl.col("season") < season)
    if train.is_empty():
        raise ValueError(f"no training seasons before {season}")
    values: dict[str, dict[str, float]] = {
        name: {}
        for name in (
            "league",
            "league_nontd",
            "k_own",
            "slope_own",
            "k_dvp",
            "slope_dvp",
            "k_nontd",
            "k_own_nontd",
        )
    }
    for p in positions:
        part = train.filter(pl.col("position") == p)
        prev = part.filter(pl.col("season") == season - 1)
        values["league"][p] = float(prev.get_column("points").mean() or 0.0)  # type: ignore[arg-type]
        values["league_nontd"][p] = float(prev.get_column("nontd").mean() or 0.0)  # type: ignore[arg-type]
        own = _frame(part, "side", "opp", "points")
        values["k_own"][p] = _k(own, "season")
        values["slope_own"][p] = _slope(own, "season")
        values["k_own_nontd"][p] = _k(_frame(part, "side", "opp", "nontd"), "season")
        dvp = _frame(part, "opp", "side", "points")
        values["k_dvp"][p] = _k(dvp, "loo_mean")
        values["slope_dvp"][p] = _slope(dvp, "loo_mean")
        values["k_nontd"][p] = _k(_frame(part, "opp", "side", "nontd"), "loo_mean")
    return FoldParams(
        season=season,
        training=tuple(sorted(set(train.get_column("season").to_list()))),
        league_prev=values["league"],
        league_prev_nontd=values["league_nontd"],
        k_own=values["k_own"],
        slope_own=values["slope_own"],
        k_dvp=values["k_dvp"],
        slope_dvp=values["slope_dvp"],
        k_nontd=values["k_nontd"],
        k_own_nontd=values["k_own_nontd"],
    )


def _w(n: pl.Expr, k: float) -> pl.Expr:
    if math.isinf(k):
        return pl.lit(0.0)
    return n / (n + k)


@dataclass(frozen=True)
class Settings:
    mode: asof.Cutoff = asof.Cutoff.PREWEEK
    k_grid: tuple[float, ...] = (1, 2, 4, 8, 16, 32, 64, 128, 256)
    half_lives: tuple[float, ...] = (2, 4, 8)
    availability_delay: timedelta = timedelta(0)  # B12: extra delay on top of the rule
    seed: int = 1729
    extra: Mapping[str, Any] = field(default_factory=dict)


def walk(
    rows: pl.DataFrame,
    schedule_games: pl.DataFrame,
    params: FoldParams,
    positions: Sequence[str],
    settings: Settings,
) -> asof.FrozenForecasts:
    """Forecasts for every valid cell of `params.season`, each from the rows available by its
    cutoff. Returns them frozen, with no label column."""
    s = params.season
    if settings.availability_delay:
        rows = rows.with_columns(pl.col("available_at") + settings.availability_delay)
    cut = asof.cutoffs(schedule_games.filter(pl.col("season") == s), settings.mode)
    targets = (
        rows.filter((pl.col("season") == s) & pl.col("position").is_in(list(positions)))
        .join(cut, on="game_id", how="inner")
        .select("game_id", "offense", "position", "side", "opp", "week", "cutoff")
    )
    history = rows.filter(pl.col("season").is_in([s - 1, s]))
    previous = _previous_season(rows, s, positions)
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
    for cutoff in sorted(set(targets.get_column("cutoff").to_list())):
        view = asof.features_as_of(history, cutoff, settings.mode)
        hist = view.frame.filter(pl.col("season") == s)
        batch = targets.filter(pl.col("cutoff") == cutoff)
        forecast = _b00(batch, hist, previous, params, "points", "b00")
        forecast = _b00(forecast, hist, previous, params, "nontd", "b00_nontd")
        terms = _opponent_terms(hist, pit, params, settings)
        forecast = _variants(forecast, terms, previous, params, settings, rng, hist)
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


def _previous_season(rows: pl.DataFrame, s: int, positions: Sequence[str]) -> pl.DataFrame:
    """Last season's mean per side and per opposing unit (adjusted), all completed before s."""
    prev = rows.filter((pl.col("season") == s - 1) & pl.col("position").is_in(list(positions)))
    side = prev.group_by("side", "position").agg(
        pl.col("points").mean().alias("prev_mean"), pl.len().alias("prev_n")
    )
    adjusted = []
    for p in positions:
        part = prev.filter(pl.col("position") == p)
        if part.is_empty():
            continue
        frame = lab.adjust(_frame(part, "opp", "side", "points"), "loo_mean")
        adjusted.append(
            frame.group_by("entity")
            .agg(pl.col("value").mean().alias("prev_resid"))
            .with_columns(pl.lit(p).alias("position"))
            .rename({"entity": "opp"})
        )
    opp = (
        pl.concat(adjusted)
        if adjusted
        else pl.DataFrame(
            schema={"opp": pl.String, "prev_resid": pl.Float64, "position": pl.String}
        )
    )
    return side.join(
        opp.rename({"opp": "side"}), on=["side", "position"], how="full", coalesce=True
    )


def _b00(
    batch: pl.DataFrame,
    hist: pl.DataFrame,
    previous: pl.DataFrame,
    params: FoldParams,
    value: str,
    name: str,
) -> pl.DataFrame:
    own = hist.group_by("side", "position").agg(
        pl.col(value).mean().alias("_mean"), pl.len().alias("_n")
    )
    points = value == "points"
    league_prev = pl.col("position").replace_strict(
        dict(params.league_prev if points else params.league_prev_nontd), default=None
    )
    k_table = params.k_own if points else params.k_own_nontd
    k = pl.col("position").replace_strict(
        {p: (1e12 if math.isinf(v) else v) for p, v in k_table.items()}, default=1e12
    )
    frame = batch.join(own, on=["side", "position"], how="left")
    if points:
        # The side's own last season, regressed toward last season's league mean.
        slope = pl.col("position").replace_strict(dict(params.slope_own), default=0.0)
        frame = frame.join(
            previous.select("side", "position", "prev_mean"), on=["side", "position"], how="left"
        )
        prior = (
            pl.when(pl.col("prev_mean").is_not_null())
            .then(league_prev + slope * (pl.col("prev_mean") - league_prev))
            .otherwise(league_prev)
        )
    else:
        prior = league_prev
    n = pl.col("_n").fill_null(0).cast(pl.Float64)
    forecast = pl.when(n > 0).then((n * pl.col("_mean") + k * prior) / (n + k)).otherwise(prior)
    drop = [c for c in ("_mean", "_n", "prev_mean") if c in frame.columns]
    return frame.with_columns(forecast.alias(name)).drop(drop)


def _opponent_terms(
    hist: pl.DataFrame, pit: pl.DataFrame, params: FoldParams, settings: Settings
) -> pl.DataFrame:
    """Per opposing unit and position, its residual summaries over its available games."""
    if hist.is_empty():
        schema: dict[str, Any] = {"opp": pl.String, "position": pl.String, "n_d": pl.UInt32}
        names = ["r_pit", "r_rec", "r_raw", "r_nontd"]
        names += [f"{p}_h{h:g}" for h in settings.half_lives for p in ("r", "neff")]
        return pl.DataFrame(schema=schema | dict.fromkeys(names, pl.Float64))
    joined = hist.join(pit, on=["game_id", "side", "position"], how="left")
    missing = joined.filter(pl.col("b00_pit").is_null()).height
    if missing:
        raise LineageError(
            "BASELINE_NOT_POINT_IN_TIME", f"{missing} history rows lack a frozen B00"
        )
    league = pl.col("points").mean().over("position")
    side_n = pl.len().over("side", "position")
    side_total = pl.col("points").sum().over("side", "position")
    k_own = pl.col("position").replace_strict(
        {p: (1e12 if math.isinf(v) else v) for p, v in params.k_own.items()}, default=1e12
    )
    other_n = (side_n - 1).cast(pl.Float64)
    other_mean = (side_total - pl.col("points")) / other_n
    recomputed = (
        pl.when(other_n > 0)
        .then((other_n * other_mean + k_own * league) / (other_n + k_own))
        .otherwise(league)
    )
    frame = joined.with_columns(
        (pl.col("points") - pl.col("b00_pit")).alias("res_pit"),
        (pl.col("points") - recomputed).alias("res_rec"),
        (pl.col("points") - league).alias("res_raw"),
        (pl.col("nontd") - pl.col("b00_nontd_pit")).alias("res_nontd"),
        pl.col("week").rank("ordinal", descending=True).over("opp", "position").alias("_age"),
    )
    aggregations: list[pl.Expr] = [
        pl.len().alias("n_d"),
        pl.col("res_pit").mean().alias("r_pit"),
        pl.col("res_rec").mean().alias("r_rec"),
        pl.col("res_raw").mean().alias("r_raw"),
        pl.col("res_nontd").mean().alias("r_nontd"),
    ]
    for h in settings.half_lives:
        weight = 0.5 ** ((pl.col("_age") - 1) / h)
        aggregations += [
            ((weight * pl.col("res_pit")).sum() / weight.sum()).alias(f"r_h{h:g}"),
            (weight.sum() ** 2 / (weight**2).sum()).alias(f"neff_h{h:g}"),
        ]
    return frame.group_by("opp", "position").agg(aggregations)


def _variants(
    forecast: pl.DataFrame,
    terms: pl.DataFrame,
    previous: pl.DataFrame,
    params: FoldParams,
    settings: Settings,
    rng: np.random.Generator,
    hist: pl.DataFrame,
) -> pl.DataFrame:
    # Joins don't promise row order; sort so seeded draws land on the same rows every run (T13).
    f = (
        forecast.join(terms, on=["opp", "position"], how="left")
        .join(
            previous.select(pl.col("side").alias("opp"), "position", "prev_resid"),
            on=["opp", "position"],
            how="left",
        )
        .sort("position", "game_id", "offense")
    )
    n_d = pl.col("n_d").fill_null(0).cast(pl.Float64)
    has = n_d > 0

    def k_of(table: Mapping[str, float]) -> pl.Expr:
        return pl.col("position").replace_strict(
            {p: (1e12 if math.isinf(v) else v) for p, v in table.items()}, default=1e12
        )

    k_dvp, k_nontd = k_of(params.k_dvp), k_of(params.k_nontd)
    slope_dvp = pl.col("position").replace_strict(dict(params.slope_dvp), default=0.0)
    b00 = pl.col("b00")
    exprs = {
        "b01": b00 + pl.when(has).then(pl.col("r_raw")).otherwise(0.0),
        "b02": b00 + pl.when(has).then(pl.col("r_pit")).otherwise(0.0),
        "b02r": b00 + pl.when(has).then(pl.col("r_rec")).otherwise(0.0),
        "b03": b00 + pl.when(has).then(n_d / (n_d + k_dvp) * pl.col("r_pit")).otherwise(0.0),
        "b03r": b00 + pl.when(has).then(n_d / (n_d + k_dvp) * pl.col("r_rec")).otherwise(0.0),
        "b06": b00
        + (
            n_d * pl.col("r_pit").fill_null(0.0)
            + k_dvp * slope_dvp * pl.col("prev_resid").fill_null(0.0)
        )
        / (n_d + k_dvp),
        "b07": b00 + pl.when(has).then(n_d / (n_d + k_nontd) * pl.col("r_nontd")).otherwise(0.0),
    }
    for k in settings.k_grid:
        exprs[f"b04_k{k:g}"] = b00 + pl.when(has).then(n_d / (n_d + k) * pl.col("r_pit")).otherwise(
            0.0
        )
    for h in settings.half_lives:
        neff = pl.col(f"neff_h{h:g}").fill_null(0.0)
        exprs[f"b05_h{h:g}"] = b00 + pl.when(has).then(
            neff / (neff + k_dvp) * pl.col(f"r_h{h:g}")
        ).otherwise(0.0)
    f = f.with_columns(**exprs)
    # B09 controls: another unit's residuals, noise of the same spread, last week's opponent.
    shuffled = _shuffled_opponents(f, rng)
    f = f.join(shuffled, on=["game_id", "offense", "position"], how="left")
    f = f.join(
        terms.select(
            pl.col("opp").alias("_shuffled_opp"),
            "position",
            pl.col("n_d").alias("_n_s"),
            pl.col("r_pit").alias("_r_s"),
        ),
        on=["_shuffled_opp", "position"],
        how="left",
    )
    spread = f.select(pl.col("r_pit").std()).item() or 0.0
    noise = pl.Series("_noise", rng.normal(0.0, spread, f.height))
    previous_opp = _last_opponent(hist)
    f = (
        f.with_columns(noise)
        .join(previous_opp, on=["side", "position"], how="left")
        .join(
            terms.select(
                pl.col("opp").alias("_last_opp"),
                "position",
                pl.col("n_d").alias("_n_l"),
                pl.col("r_pit").alias("_r_l"),
            ),
            on=["_last_opp", "position"],
            how="left",
        )
    )
    n_s = pl.col("_n_s").fill_null(0).cast(pl.Float64)
    n_l = pl.col("_n_l").fill_null(0).cast(pl.Float64)
    f = f.with_columns(
        (b00 + pl.when(n_s > 0).then(n_s / (n_s + k_dvp) * pl.col("_r_s")).otherwise(0.0)).alias(
            "b09_shuffle"
        ),
        (b00 + pl.when(has).then(n_d / (n_d + k_dvp) * pl.col("_noise")).otherwise(0.0)).alias(
            "b09_noise"
        ),
        (b00 + pl.when(n_l > 0).then(n_l / (n_l + k_dvp) * pl.col("_r_l")).otherwise(0.0)).alias(
            "b09_lastopp"
        ),
    )
    keep = [
        "game_id",
        "offense",
        "position",
        "side",
        "opp",
        "week",
        "cutoff",
        "n_d",
        "b00",
        "b00_nontd",
    ]
    variants = [
        c
        for c in f.columns
        if c.startswith(("b01", "b02", "b03", "b04", "b05", "b06", "b07", "b09"))
    ]
    return f.select(*keep, *variants)


def _shuffled_opponents(f: pl.DataFrame, rng: np.random.Generator) -> pl.DataFrame:
    """Each row's opponent replaced by another row's, within position (a placebo)."""
    parts = []
    for position in sorted(f.get_column("position").unique().to_list()):
        part = f.filter(pl.col("position") == position).sort("game_id", "offense")
        order = rng.permutation(part.height)
        parts.append(
            part.select("game_id", "offense", "position").with_columns(
                pl.Series("_shuffled_opp", part.get_column("opp").to_numpy()[order])
            )
        )
    return pl.concat(parts) if parts else pl.DataFrame()


def _last_opponent(hist: pl.DataFrame) -> pl.DataFrame:
    if hist.is_empty():
        return pl.DataFrame(
            schema={"side": pl.String, "position": pl.String, "_last_opp": pl.String}
        )
    return (
        hist.sort("week").group_by("side", "position").agg(pl.col("opp").last().alias("_last_opp"))
    )


# --- Evaluation --------------------------------------------------------------------------------


def evaluate(
    forecasts: asof.FrozenForecasts,
    rows: pl.DataFrame,
    season: int,
) -> pl.DataFrame:
    """Frozen forecasts beside their labels (one to one, T20)."""
    labels = asof.labels_for(
        rows.filter(pl.col("season") == season).select(
            "game_id", "offense", "position", "kickoff", "points", "status"
        ),
        forecasts.frame.get_column("game_id").unique().to_list(),
    )
    return (
        asof.evaluation_join(forecasts, labels)
        .with_columns(pl.lit(season).alias("season"))
        .sort("position", "game_id", "offense")
    )


def metrics(
    joined: pl.DataFrame,
    variants: Sequence[str],
    *,
    block: str,
    reps: int,
    seed: int,
) -> dict[str, Any]:
    """Per variant: RMSE, MAE, mean error and Spearman; and its RMSE less B00's on the same rows,
    with a block-bootstrap interval (blocks: seasons, or weeks within one season)."""
    y = joined.get_column("points").to_numpy()
    blocks = joined.get_column(block).to_numpy()
    labels = np.unique(blocks)
    members = [np.flatnonzero(blocks == b) for b in labels]
    rng = np.random.default_rng(seed)
    draws = [
        np.concatenate([members[i] for i in rng.integers(0, labels.size, labels.size)])
        for _ in range(reps)
    ]
    base = joined.get_column("b00").to_numpy()
    out: dict[str, Any] = {"rows": int(y.size), "blocks": int(labels.size)}
    base_rmse = _rmse(base, y)
    for name in variants:
        pred = joined.get_column(name).to_numpy()
        rmse = _rmse(pred, y)
        deltas = [(_rmse(pred[d], y[d]) - _rmse(base[d], y[d])) for d in draws]
        out[name] = {
            "rmse": round(rmse, 4),
            "mae": round(float(np.abs(pred - y).mean()), 4),
            "meanError": round(float((pred - y).mean()), 4),
            "spearman": round(_spearman(pred, y), 4),
            "deltaRmse": round(rmse - base_rmse, 4),
            "relativeDelta": round((rmse - base_rmse) / base_rmse, 5) if base_rmse else None,
            "delta95": [round(float(q), 4) for q in np.quantile(deltas, [0.025, 0.975])],
        }
    return out


def _rmse(pred: np.ndarray, y: np.ndarray) -> float:
    return float(np.sqrt(((pred - y) ** 2).mean()))


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = pl.Series(a).rank("average").to_numpy()
    rb = pl.Series(b).rank("average").to_numpy()
    r = lab.corr(ra.astype(np.float64), rb.astype(np.float64), minimum=3)
    return 0.0 if r is None else r


def calibration(joined: pl.DataFrame, name: str, bins: int = 10) -> list[dict[str, float]]:
    """Mean forecast and mean outcome by forecast decile."""
    ranked = joined.with_columns(
        (pl.col(name).rank("ordinal") * bins / (pl.len() + 1)).floor().cast(pl.Int32).alias("_bin")
    )
    table = (
        ranked.group_by("_bin")
        .agg(
            pl.col(name).mean().alias("forecast"),
            pl.col("points").mean().alias("observed"),
            pl.len().alias("n"),
        )
        .sort("_bin")
    )
    return [
        {
            "decile": int(r["_bin"]) + 1,
            "forecast": round(r["forecast"], 3),
            "observed": round(r["observed"], 3),
            "n": int(r["n"]),
        }
        for r in table.iter_rows(named=True)
    ]


def breakdown(joined: pl.DataFrame, name: str, column: str) -> dict[str, Any]:
    """RMSE of a variant less B00's within each value of a column (season, week bin, n_d bin)."""
    out = {}
    for (key,), part in joined.group_by([column], maintain_order=True):
        y = part.get_column("points").to_numpy()
        out[str(key)] = {
            "rows": part.height,
            "deltaRmse": round(
                _rmse(part.get_column(name).to_numpy(), y)
                - _rmse(part.get_column("b00").to_numpy(), y),
                4,
            ),
        }
    return dict(sorted(out.items()))


def check_stage(stage: str, seasons: Sequence[int], split: Mapping[str, Sequence[int]]) -> None:
    """Refuse a stage that would forecast outside its split. The holdout never runs from here:
    Phase 4 needs a frozen manifest (spec §9, T18)."""
    holdout = [s for s in seasons if s in split["holdout"]]
    if holdout:
        raise ValueError(f"seasons {holdout} are the holdout and need a frozen manifest")
    outside = [s for s in seasons if s not in split[stage]]
    if outside:
        raise ValueError(f"seasons {outside} are not in the {stage} split")
