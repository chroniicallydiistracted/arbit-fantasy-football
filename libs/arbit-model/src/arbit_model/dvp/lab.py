"""The M3-3 reliability lab (spec Phase A, §6): how repeatable a defense's tendency is.

Everything here is descriptive and retrospective: it reads completed-game FFA actuals (the
validated observations) and never forecasts. Functions are pure over polars frames and numpy
arrays; randomness comes only from seeded numpy generators (T13).

**The unit and what it faced.** For QB, RB, WR, TE and K the unit is the defense and the cell's
points are what the offense's players at that position scored against it. For D/ST the unit is
the offense: the points opposing D/STs scored against it (spec §2). `entity` is the unit's
franchise and `faced` the other side.

**The model** behind k (spec §6): a unit-season's cells are y = mu + a + e with a the unit-season
effect (variance tau2) and e game noise (variance sigma2). k = sigma2 / tau2 games give the unit's
own record half the weight. Split-half k (v0's) approximates this with the mean half size; the
variance-component fits here use every unit's actual game count.
"""

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import polars as pl

from arbit_model.dvp import observations as obs
from arbit_model.dvp.reliability import k_from_r, leave_one_out

ADJUSTMENTS = ("none", "season", "loo_mean", "loo_median", "loo_shrunk")
SPLITS = ("calendar", "alternating", "chronological", "first6_next6", "home_away")
LAG_BINS = ((1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12), (13, 17))


# --- Frames -----------------------------------------------------------------------------------


def position_frame(
    observations: pl.DataFrame, schedule: pl.DataFrame, position: str
) -> pl.DataFrame:
    """Valid cells of one position group: season, week, game_id, entity, faced, points, home
    (whether the unit played at home), sorted by entity, season and week."""
    dst = position == obs.DST
    cells = observations.filter(
        (pl.col("position") == position) & (pl.col("status") == obs.VALID)
    ).select(
        "season",
        "week",
        "game_id",
        pl.col("offense" if dst else "defense").alias("entity"),
        pl.col("defense" if dst else "offense").alias("faced"),
        pl.col("points").cast(pl.Float64),
    )
    homes = schedule.select("game_id", pl.col("home").alias("home_team"))
    return (
        cells.join(homes, on="game_id", how="left")
        .with_columns((pl.col("entity") == pl.col("home_team")).alias("home"))
        .drop("home_team")
        .sort("entity", "season", "week")
    )


def adjust(frame: pl.DataFrame, method: str, k_faced: float | None = None) -> pl.DataFrame:
    """The frame with `value`: the points, or the points less an expectation for what was faced.

    - `none`: the points (v0's raw).
    - `season`: less the season's mean at the position (removes scoring-era effects only).
    - `loo_mean`: less the faced side's mean in its other games that season (v0's adjusted).
    - `loo_median`: less the faced side's median in its other games (robust to one big game).
    - `loo_shrunk`: less the faced side's other-game mean shrunk toward the season mean with
      `k_faced` games ((n·mean + k·league) / (n + k)), so a thin record expects less.

    The leave-one-out expectations use the faced side's later games: retrospective, for
    description only, never a forecast (spec §13)."""
    season_mean = pl.col("points").mean().over("season")
    if method == "none":
        value = pl.col("points")
    elif method == "season":
        value = pl.col("points") - season_mean
    elif method == "loo_mean":
        value = pl.col("points") - leave_one_out(["faced", "season"], "points")
    elif method == "loo_median":
        return _loo_median(frame)
    elif method == "loo_shrunk":
        if k_faced is None or k_faced < 0:
            raise ValueError("loo_shrunk needs a nonnegative k for the faced side")
        others = pl.col("points").count().over("faced", "season") - 1
        loo = leave_one_out(["faced", "season"], "points")
        expected = (others * loo + k_faced * season_mean) / (others + k_faced)
        value = pl.col("points") - pl.when(others > 0).then(expected).otherwise(season_mean)
    else:
        raise ValueError(f"unknown adjustment {method}")
    return frame.with_columns(value.alias("value"))


def _loo_median(frame: pl.DataFrame) -> pl.DataFrame:
    keys = frame.select("faced", "season", "points").rows()
    groups: dict[tuple[Any, Any], list[float]] = {}
    for faced, season, points in keys:
        groups.setdefault((faced, season), []).append(points)
    medians = []
    for faced, season, points in keys:
        others = list(groups[(faced, season)])
        others.remove(points)
        medians.append(float(np.median(others)) if others else None)
    expected = pl.Series("expected", medians, dtype=pl.Float64)
    return frame.with_columns((pl.col("points") - expected).alias("value"))


# --- Groups as arrays ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Groups:
    """A frame's non-null values as arrays, grouped by unit-season, in entity-season-week order."""

    group: np.ndarray  # group index per cell
    value: np.ndarray
    week: np.ndarray
    season: np.ndarray  # per cell
    home: np.ndarray
    start: np.ndarray  # first cell of each group
    size: np.ndarray
    keys: list[tuple[str, int]]  # (entity, season) per group

    @property
    def cells(self) -> int:
        return int(self.value.size)

    def position_in_group(self) -> np.ndarray:
        position: np.ndarray = np.arange(self.cells) - self.start[self.group]
        return position


def groups(frame: pl.DataFrame, value: str = "value") -> Groups:
    rows = frame.filter(pl.col(value).is_not_null()).sort("entity", "season", "week")
    entity = rows.get_column("entity").to_list()
    season = rows.get_column("season").to_numpy().astype(np.int64)
    keys: list[tuple[str, int]] = []
    index = np.empty(len(entity), dtype=np.int64)
    for i, key in enumerate(zip(entity, season.tolist(), strict=True)):
        if not keys or keys[-1] != key:
            keys.append(key)
        index[i] = len(keys) - 1
    size = np.bincount(index, minlength=len(keys)) if keys else np.zeros(0, dtype=np.int64)
    start = np.concatenate([[0], np.cumsum(size)[:-1]]) if keys else np.zeros(0, dtype=np.int64)
    return Groups(
        group=index,
        value=rows.get_column(value).to_numpy().astype(np.float64),
        week=rows.get_column("week").to_numpy().astype(np.int64),
        season=season,
        home=rows.get_column("home").fill_null(False).to_numpy().astype(bool),
        start=start.astype(np.int64),
        size=size.astype(np.int64),
        keys=keys,
    )


# --- Splits -------------------------------------------------------------------------------------


def assignment(g: Groups, method: str) -> np.ndarray:
    """Per cell: 0 for half A, 1 for half B, -1 when the cell is in neither (first6_next6)."""
    position = g.position_in_group()
    n = g.size[g.group]
    if method == "calendar":
        return np.where(g.week % 2 == 1, 0, 1)
    if method == "alternating":
        return position % 2
    if method == "chronological":
        return np.where(position < (n + 1) // 2, 0, 1)
    if method == "first6_next6":
        return np.where(position < 6, 0, np.where(position < 12, 1, -1))
    if method == "home_away":
        return np.where(g.home, 0, 1)
    raise ValueError(f"unknown split {method}")


def random_assignment(g: Groups, rng: np.random.Generator) -> np.ndarray:
    """A balanced random split of each unit-season (half A gets n // 2 cells)."""
    keys = rng.random(g.cells)
    order = np.lexsort((keys, g.group))
    rank = np.empty(g.cells, dtype=np.int64)
    rank[order] = np.arange(g.cells) - g.start[g.group[order]]
    return np.where(rank < g.size[g.group] // 2, 0, 1)


@dataclass(frozen=True)
class Split:
    units: int
    r: float | None
    m: float | None
    k: float | None
    a_mean: np.ndarray = field(repr=False)
    b_mean: np.ndarray = field(repr=False)
    a_n: np.ndarray = field(repr=False)
    b_n: np.ndarray = field(repr=False)
    unit_index: np.ndarray = field(repr=False)  # group index of each kept unit


def split(g: Groups, half: np.ndarray, min_games: int = 4) -> Split:
    """Split-half correlation of the halves' means across unit-seasons with at least `min_games`
    cells in each half; k from the mean half size (v0's shortcut, flagged in T12)."""
    groups_n = g.size.size
    sums, counts = [], []
    for h in (0, 1):
        mask = half == h
        sums.append(np.bincount(g.group[mask], weights=g.value[mask], minlength=groups_n))
        counts.append(np.bincount(g.group[mask], minlength=groups_n))
    keep = (counts[0] >= min_games) & (counts[1] >= min_games)
    a = sums[0][keep] / counts[0][keep]
    b = sums[1][keep] / counts[1][keep]
    r = corr(a, b)
    m = float(((counts[0][keep] + counts[1][keep]) / 2).mean()) if keep.any() else None
    return Split(
        units=int(keep.sum()),
        r=r,
        m=m,
        k=k_from_r(r, m) if m else None,
        a_mean=a,
        b_mean=b,
        a_n=counts[0][keep],
        b_n=counts[1][keep],
        unit_index=np.flatnonzero(keep),
    )


def corr(x: np.ndarray, y: np.ndarray, minimum: int = 20) -> float | None:
    if x.size < minimum:
        return None
    xc, yc = x - x.mean(), y - y.mean()
    denominator = math.sqrt(float((xc * xc).sum()) * float((yc * yc).sum()))
    return float((xc * yc).sum() / denominator) if denominator else None


def random_splits(g: Groups, reps: int, seed: int, min_games: int = 4) -> dict[str, Any]:
    """`reps` seeded balanced random splits. They reuse the same data, so their spread shows the
    split's arbitrariness, not sampling uncertainty (spec A02)."""
    rng = np.random.default_rng(seed)
    rs, ks = [], []
    for _ in range(reps):
        result = split(g, random_assignment(g, rng), min_games)
        if result.r is not None:
            rs.append(result.r)
        if result.k is not None:
            ks.append(result.k)
    return {
        "reps": reps,
        "seed": seed,
        "pearson": _quantiles(rs),
        "k": _quantiles(ks),
        "unidentified": reps - len(ks),
    }


def _quantiles(values: Sequence[float]) -> dict[str, float] | None:
    if not values:
        return None
    array = np.asarray(values, dtype=np.float64)
    q = np.quantile(array, [0.025, 0.5, 0.975])
    return {
        "mean": round(float(array.mean()), 4),
        "p2_5": round(float(q[0]), 4),
        "median": round(float(q[1]), 4),
        "p97_5": round(float(q[2]), 4),
    }


# --- Variance components (A05; T14) -------------------------------------------------------------


@dataclass(frozen=True)
class Components:
    method: str
    groups: int
    cells: int
    mean_size: float
    tau2: float
    sigma2: float
    k: float | None  # sigma2 / tau2; None on the boundary (tau2 = 0)
    icc: float  # single-game reliability, tau2 / (tau2 + sigma2)
    boundary: bool
    converged: bool
    detail: Mapping[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "groups": self.groups,
            "cells": self.cells,
            "meanSize": round(self.mean_size, 3),
            "tau2": round(self.tau2, 5),
            "sigma2": round(self.sigma2, 4),
            "k": None if self.k is None else round(self.k, 2),
            "singleGameReliability": round(self.icc, 4),
            "boundary": self.boundary,
            "converged": self.converged,
        } | dict(self.detail)


def _group_stats(g: Groups) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = g.size.astype(np.float64)
    means = np.bincount(g.group, weights=g.value, minlength=n.size) / n
    ssw = np.bincount(g.group, weights=(g.value - means[g.group]) ** 2, minlength=n.size)
    return n, means, ssw


def anova_components(g: Groups) -> Components:
    """Method of moments for unequal group sizes: tau2 = (MSB - MSW) / n0, truncated at 0."""
    n, means, ssw = _group_stats(g)
    groups_n, cells = n.size, float(n.sum())
    if groups_n < 2 or cells <= groups_n:
        raise ValueError("need at least two groups and some within-group replication")
    grand = float((n * means).sum() / cells)
    msb = float((n * (means - grand) ** 2).sum() / (groups_n - 1))
    msw = float(ssw.sum() / (cells - groups_n))
    n0 = (cells - float((n * n).sum()) / cells) / (groups_n - 1)
    tau2 = (msb - msw) / n0
    boundary = tau2 <= 0
    tau2 = max(tau2, 0.0)
    return Components(
        method="method_of_moments",
        groups=groups_n,
        cells=int(cells),
        mean_size=cells / groups_n,
        tau2=tau2,
        sigma2=msw,
        k=None if boundary else msw / tau2,
        icc=tau2 / (tau2 + msw) if msw + tau2 > 0 else 0.0,
        boundary=boundary,
        converged=True,
        detail={"n0": round(n0, 3), "msb": round(msb, 4), "msw": round(msw, 4)},
    )


def _reml_profile(
    n: np.ndarray, means: np.ndarray, ssw: float, ratio: float
) -> tuple[float, float]:
    """Profile REML log-likelihood (up to a constant) and sigma2 at tau2/sigma2 = ratio."""
    cells = float(n.sum())
    w = n / (1 + n * ratio)
    mu = float((w * means).sum() / w.sum())
    q = ssw + float((w * (means - mu) ** 2).sum())
    sigma2 = max(q / (cells - 1), 1e-12)  # no within-group noise at all: keep the log finite
    loglik = -0.5 * (
        (cells - 1) * math.log(sigma2) + float(np.log1p(n * ratio).sum()) + math.log(w.sum())
    )
    return loglik, sigma2


def reml_components(g: Groups, grid: int = 81, tolerance: float = 1e-7) -> Components:
    """Restricted maximum likelihood for the one-way model with each group's own size.

    Profiles mu and sigma2 out and maximizes over lambda = tau2 / sigma2 >= 0: a log-scale grid
    over 1e-6 to 1e3, then golden-section refinement. A maximum at lambda = 0 (or the grid's
    lower edge) is reported as a boundary estimate with no k, never as an identified effect."""
    n, means, ssw_g = _group_stats(g)
    if n.size < 2:
        raise ValueError("need at least two groups")
    ssw = float(ssw_g.sum())
    logs = np.linspace(math.log(1e-6), math.log(1e3), grid)
    values = [_reml_profile(n, means, ssw, math.exp(t))[0] for t in logs]
    at_zero = _reml_profile(n, means, ssw, 0.0)[0]
    best = int(np.argmax(values))
    if at_zero >= values[best] or best == 0:
        _, sigma2 = _reml_profile(n, means, ssw, 0.0)
        return Components(
            method="reml",
            groups=n.size,
            cells=int(n.sum()),
            mean_size=float(n.mean()),
            tau2=0.0,
            sigma2=sigma2,
            k=None,
            icc=0.0,
            boundary=True,
            converged=True,
            detail={"loglik": round(at_zero, 4), "iterations": 0},
        )
    low = logs[max(best - 1, 0)]
    high = logs[min(best + 1, grid - 1)]
    golden = (math.sqrt(5) - 1) / 2
    iterations = 0
    c, d = high - golden * (high - low), low + golden * (high - low)
    fc = _reml_profile(n, means, ssw, math.exp(c))[0]
    fd = _reml_profile(n, means, ssw, math.exp(d))[0]
    while high - low > tolerance and iterations < 200:
        iterations += 1
        if fc > fd:
            high, d, fd = d, c, fc
            c = high - golden * (high - low)
            fc = _reml_profile(n, means, ssw, math.exp(c))[0]
        else:
            low, c, fc = c, d, fd
            d = low + golden * (high - low)
            fd = _reml_profile(n, means, ssw, math.exp(d))[0]
    ratio = math.exp((low + high) / 2)
    loglik, sigma2 = _reml_profile(n, means, ssw, ratio)
    at_upper = best == grid - 1
    return Components(
        method="reml",
        groups=n.size,
        cells=int(n.sum()),
        mean_size=float(n.mean()),
        tau2=ratio * sigma2,
        sigma2=sigma2,
        k=1 / ratio,
        icc=ratio / (1 + ratio),
        boundary=False,
        converged=high - low <= tolerance and not at_upper,
        detail={"loglik": round(loglik, 4), "iterations": iterations},
    )


def season_component(g: Groups) -> dict[str, float]:
    """How much whole seasons differ: the variance of season means less their sampling noise."""
    seasons = np.unique(g.season)
    season_means, noise = [], []
    total_variance = float(g.value.var(ddof=1))
    for s in seasons:
        values = g.value[g.season == s]
        season_means.append(float(values.mean()))
        noise.append(total_variance / values.size)
    between = (
        float(np.var(season_means, ddof=1)) - float(np.mean(noise)) if len(seasons) > 1 else 0.0
    )
    return {
        "seasons": int(seasons.size),
        "seasonMeanSd": round(float(np.std(season_means, ddof=1)), 4) if len(seasons) > 1 else 0.0,
        "seasonVariance": round(max(between, 0.0), 5),
        "boundary": between <= 0,
    }


def implied_split_r(sizes_a: np.ndarray, sizes_b: np.ndarray, k: float) -> float:
    """The mean of the model's split-half correlation over units with their own half sizes."""
    return float(np.mean(np.sqrt(sizes_a / (sizes_a + k) * sizes_b / (sizes_b + k))))


# --- Temporal (A06) -----------------------------------------------------------------------------


def lag_profile(g: Groups) -> dict[str, Any]:
    """Within unit-season covariance of two games by weeks apart, over the total variance: the
    single-game reliability at that distance. A stable trait gives a flat profile; a drifting one
    decays. Values are centered on their season mean first."""
    centered = _season_centered(g)
    variance = float((centered**2).mean())
    sums = {b: [0.0, 0] for b in LAG_BINS}
    by_season: dict[int, dict[tuple[int, int], list[float]]] = {}
    for gi in range(g.size.size):
        lo, hi = g.start[gi], g.start[gi] + g.size[gi]
        weeks, values = g.week[lo:hi], centered[lo:hi]
        season = int(g.season[lo])
        bucket = by_season.setdefault(season, {b: [0.0, 0.0] for b in LAG_BINS})
        for i in range(values.size):
            for j in range(i + 1, values.size):
                lag = abs(int(weeks[j] - weeks[i]))
                for b in LAG_BINS:
                    if b[0] <= lag <= b[1]:
                        product = float(values[i] * values[j])
                        sums[b][0] += product
                        sums[b][1] += 1
                        bucket[b][0] += product
                        bucket[b][1] += 1
                        break
    return {
        "variance": variance,
        "bins": {
            f"{b[0]}-{b[1]}": {
                "pairs": int(sums[b][1]),
                "reliability": round(sums[b][0] / sums[b][1] / variance, 4) if sums[b][1] else None,
            }
            for b in LAG_BINS
        },
        "_bySeason": by_season,
    }


def _season_centered(g: Groups) -> np.ndarray:
    centered = g.value.copy()
    for s in np.unique(g.season):
        mask = g.season == s
        centered[mask] -= centered[mask].mean()
    return centered


def rolling_window(g: Groups, window: int) -> dict[str, Any]:
    """Correlation between a unit's mean over its previous `window` games and its next game,
    within a season (season-centered values)."""
    centered = _season_centered(g)
    xs, ys = [], []
    for gi in range(g.size.size):
        lo, hi = g.start[gi], g.start[gi] + g.size[gi]
        values = centered[lo:hi]
        for t in range(window, values.size):
            xs.append(float(values[t - window : t].mean()))
            ys.append(float(values[t]))
    r = corr(np.asarray(xs), np.asarray(ys))
    return {"window": window, "pairs": len(xs), "pearson": None if r is None else round(r, 4)}


def implied_window_r(k: float | None, window: int) -> float | None:
    """The stable-trait model's correlation between a w-game mean and one further game."""
    if k is None:
        return None
    lam = 1 / k
    return lam / math.sqrt((lam + 1 / window) * (lam + 1))


# --- Between seasons (A07) ----------------------------------------------------------------------


def carryover(frame: pl.DataFrame, min_games: int = 8) -> pl.DataFrame:
    """Each franchise's season mean beside its next season's (both with `min_games` cells)."""
    means = (
        frame.filter(pl.col("value").is_not_null())
        .group_by("entity", "season")
        .agg(pl.col("value").mean().alias("mean"), pl.len().alias("n"))
        .filter(pl.col("n") >= min_games)
    )
    following = means.with_columns((pl.col("season") - 1).alias("season")).rename(
        {"mean": "next_mean", "n": "next_n"}
    )
    return means.join(following, on=["entity", "season"], how="inner").sort("season", "entity")


def carryover_summary(pairs: pl.DataFrame) -> dict[str, Any]:
    x = pairs.get_column("mean").to_numpy()
    y = pairs.get_column("next_mean").to_numpy()
    seasons = pairs.get_column("season").to_numpy()
    r = corr(x, y)
    fitted = slope(x, y)
    # Leave one season pair out: predict next season as slope x last (centered), or reset to 0.
    errors_decay, errors_reset = [], []
    for s in np.unique(seasons):
        train, test = seasons != s, seasons == s
        b = slope(x[train], y[train])
        if b is None:
            continue
        mx, my = x[train].mean(), y[train].mean()
        predicted = my + b * (x[test] - mx)
        errors_decay.extend(((y[test] - predicted) ** 2).tolist())
        errors_reset.extend(((y[test] - my) ** 2).tolist())
    return {
        "pairs": int(x.size),
        "pearson": None if r is None else round(r, 4),
        "slope": None if fitted is None else round(fitted, 4),
        "cvMseDecay": round(float(np.mean(errors_decay)), 4) if errors_decay else None,
        "cvMseReset": round(float(np.mean(errors_reset)), 4) if errors_reset else None,
    }


def slope(x: np.ndarray, y: np.ndarray) -> float | None:
    xc = x - x.mean()
    sxx = float((xc * xc).sum())
    return float((xc * (y - y.mean())).sum() / sxx) if sxx else None


# --- Nulls and resampling (A08; T24) ------------------------------------------------------------


def permutation_null(
    frame: pl.DataFrame, reps: int, seed: int, min_games: int = 4
) -> dict[str, Any]:
    """Odd/even split-half r after shuffling which unit each cell belongs to among the cells of
    the same season and week. Every unit keeps its number of games per week and every week its
    values, so only the link between a unit and its own results is broken."""
    rows = frame.filter(pl.col("value").is_not_null()).sort("season", "week", "entity")
    entity_codes = rows.get_column("entity").cast(pl.Categorical).to_physical().to_numpy()
    season = rows.get_column("season").to_numpy().astype(np.int64)
    week = rows.get_column("week").to_numpy().astype(np.int64)
    value = rows.get_column("value").to_numpy().astype(np.float64)
    block = (season - season.min()) * 100 + week
    stable = np.lexsort((np.arange(value.size), block))
    rng = np.random.default_rng(seed)
    nulls = []
    for _ in range(reps):
        shuffled = np.lexsort((rng.random(value.size), block))
        labels = np.empty_like(entity_codes)
        labels[stable] = entity_codes[shuffled]
        r = _parity_r(labels, season, week, value, min_games)
        if r is not None:
            nulls.append(r)
    observed = _parity_r(entity_codes, season, week, value, min_games)
    array = np.asarray(nulls)
    exceed = int((array >= observed).sum()) if observed is not None else None
    return {
        "reps": reps,
        "seed": seed,
        "observed": None if observed is None else round(observed, 4),
        "null": (_quantiles(nulls) or {}) | {"p99": round(float(np.quantile(array, 0.99)), 4)}
        if nulls
        else None,
        "pValue": None if exceed is None else round((1 + exceed) / (1 + array.size), 5),
        "_values": array,
    }


def _parity_r(
    labels: np.ndarray, season: np.ndarray, week: np.ndarray, value: np.ndarray, min_games: int
) -> float | None:
    key = labels.astype(np.int64) * 10_000 + season
    _, group = np.unique(key, return_inverse=True)
    groups_n = int(group.max()) + 1
    odd = week % 2 == 1
    sa = np.bincount(group[odd], weights=value[odd], minlength=groups_n)
    na = np.bincount(group[odd], minlength=groups_n)
    sb = np.bincount(group[~odd], weights=value[~odd], minlength=groups_n)
    nb = np.bincount(group[~odd], minlength=groups_n)
    keep = (na >= min_games) & (nb >= min_games)
    return corr(sa[keep] / na[keep], sb[keep] / nb[keep])


def cluster_bootstrap(result: Split, clusters: np.ndarray, reps: int, seed: int) -> dict[str, Any]:
    """Percentile intervals for r and k, resampling whole clusters of kept units (a season, a
    franchise) or single units (when every unit is its own cluster)."""
    labels = np.unique(clusters)
    members = [np.flatnonzero(clusters == label) for label in labels]
    rng = np.random.default_rng(seed)
    rs, ks = [], []
    for _ in range(reps):
        picks = rng.integers(0, labels.size, labels.size)
        index = np.concatenate([members[p] for p in picks])
        r = corr(result.a_mean[index], result.b_mean[index])
        m = float(((result.a_n[index] + result.b_n[index]) / 2).mean())
        if r is not None:
            rs.append(r)
        k = k_from_r(r, m)
        if k is not None:
            ks.append(k)
    return {
        "reps": reps,
        "seed": seed,
        "clusters": int(labels.size),
        "pearson95": interval95(rs),
        "k95": interval95(ks),
        "unidentifiedShare": round(1 - len(ks) / reps, 4),
    }


def interval95(values: Sequence[float]) -> list[float] | None:
    if not values:
        return None
    q = np.quantile(np.asarray(values), [0.025, 0.975])
    return [round(float(q[0]), 4), round(float(q[1]), 4)]


def bootstrap_components(
    g: Groups, reps: int, seed: int, estimator: Callable[[Groups], Components]
) -> dict[str, Any]:
    """Season-cluster bootstrap of a variance-component estimate of k."""
    seasons = np.unique(g.season)
    by_season = {s: np.flatnonzero(g.season[g.start] == s) for s in seasons}
    rng = np.random.default_rng(seed)
    ks, boundary = [], 0
    for _ in range(reps):
        picks = rng.integers(0, seasons.size, seasons.size)
        chosen = np.concatenate([by_season[seasons[p]] for p in picks])
        sample = subset_groups(g, chosen)
        fit = estimator(sample)
        if fit.k is None:
            boundary += 1
        else:
            ks.append(fit.k)
    return {
        "reps": reps,
        "seed": seed,
        "k95": interval95(ks),
        "boundaryShare": round(boundary / reps, 4),
    }


def subset_groups(g: Groups, chosen: np.ndarray) -> Groups:
    """The listed groups (repeats allowed) as a new Groups."""
    pieces = [np.arange(g.start[c], g.start[c] + g.size[c]) for c in chosen]
    index = np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.int64)
    sizes = g.size[chosen]
    new_group = np.repeat(np.arange(chosen.size), sizes)
    return Groups(
        group=new_group,
        value=g.value[index],
        week=g.week[index],
        season=g.season[index],
        home=g.home[index],
        start=np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int64),
        size=sizes,
        keys=[g.keys[c] for c in chosen],
    )


# --- Robustness (A10; T28) ----------------------------------------------------------------------


def influence(result: Split) -> dict[str, Any]:
    """How far one unit-season can move r: leave each kept unit out in turn (jackknife)."""
    if result.r is None:
        return {"maxAbsChange": None}
    changes = []
    for i in range(result.units):
        keep = np.ones(result.units, dtype=bool)
        keep[i] = False
        r = corr(result.a_mean[keep], result.b_mean[keep])
        changes.append(0.0 if r is None else r - result.r)
    array = np.asarray(changes)
    worst = int(np.argmax(np.abs(array)))
    jackknife_se = math.sqrt(
        (array.size - 1) / array.size * float(((array - array.mean()) ** 2).sum())
    )
    return {
        "maxAbsChange": round(float(abs(array[worst])), 4),
        "worstUnit": int(result.unit_index[worst]),
        "jackknifeSe": round(jackknife_se, 4),
    }


def winsorize(frame: pl.DataFrame, low: float, high: float) -> pl.DataFrame:
    lo, hi = frame.get_column("value").quantile(low), frame.get_column("value").quantile(high)
    return frame.with_columns(pl.col("value").clip(lo, hi))


def trim(frame: pl.DataFrame, sds: float) -> pl.DataFrame:
    values = frame.get_column("value")
    mean, sd = values.mean(), values.std()
    return frame.filter((pl.col("value") - mean).abs() <= sds * sd)  # type: ignore[operator]


def lag_bootstrap(
    profile: Mapping[str, Any], reps: int, seed: int
) -> dict[str, list[float] | None]:
    """Season-cluster intervals for each lag bin's reliability."""
    by_season: Mapping[int, Mapping[tuple[int, int], list[float]]] = profile["_bySeason"]
    seasons = sorted(by_season)
    rng = np.random.default_rng(seed)
    draws: dict[tuple[int, int], list[float]] = {b: [] for b in LAG_BINS}
    for _ in range(reps):
        picks = rng.integers(0, len(seasons), len(seasons))
        for b in LAG_BINS:
            total = sum(by_season[seasons[p]][b][0] for p in picks)
            count = sum(by_season[seasons[p]][b][1] for p in picks)
            if count:
                draws[b].append(total / count / profile["variance"])
    return {f"{b[0]}-{b[1]}": interval95(draws[b]) for b in LAG_BINS}


# --- Landscape (A00) ----------------------------------------------------------------------------


def landscape(frame: pl.DataFrame) -> dict[str, Any]:
    """Distribution of a position's cell points and of unit-season means."""
    points = frame.get_column("points").to_numpy().astype(np.float64)
    q = np.quantile(points, [0.05, 0.25, 0.5, 0.75, 0.95])
    mean, sd = float(points.mean()), float(points.std(ddof=1))
    unit = frame.group_by("entity", "season").agg(
        pl.col("points").mean().alias("mean"), pl.col("points").std().alias("sd")
    )
    return {
        "cells": int(points.size),
        "mean": round(mean, 3),
        "sd": round(sd, 3),
        "cv": round(sd / mean, 3) if mean > 0 else None,
        "percentiles": {
            k: round(float(v), 2)
            for k, v in zip(("p5", "p25", "p50", "p75", "p95"), q, strict=True)
        },
        "min": round(float(points.min()), 2),
        "max": round(float(points.max()), 2),
        "zeros": int((points == 0).sum()),
        "negative": int((points < 0).sum()),
        "beyond3Sd": int((np.abs(points - mean) > 3 * sd).sum()),
        "skew": round(float(((points - mean) ** 3).mean() / sd**3), 3),
        "unitSeasonMeanSd": round(float(unit.get_column("mean").std() or 0.0), 3),  # type: ignore[arg-type]
        "withinUnitSeasonSd": round(float(unit.get_column("sd").mean() or 0.0), 3),  # type: ignore[arg-type]
    }


def rank_agreement(raw: pl.DataFrame, adjusted: pl.DataFrame) -> dict[str, Any]:
    """Per season, how units' ranks by raw season mean agree with their ranks adjusted for the
    offenses (or defenses) they faced: Spearman, and how many moved 8 or more places."""

    def season_means(frame: pl.DataFrame, name: str) -> pl.DataFrame:
        return (
            frame.filter(pl.col("value").is_not_null())
            .group_by("entity", "season")
            .agg(pl.col("value").mean().alias(name))
        )

    joined = season_means(raw, "raw").join(season_means(adjusted, "adj"), on=["entity", "season"])
    rhos, moved, units = [], 0, 0
    for (_,), part in joined.group_by(["season"], maintain_order=True):
        raw_rank = part.get_column("raw").rank("ordinal").to_numpy()
        adj_rank = part.get_column("adj").rank("ordinal").to_numpy()
        r = corr(raw_rank.astype(np.float64), adj_rank.astype(np.float64), minimum=3)
        if r is not None:
            rhos.append(r)
        moved += int((np.abs(raw_rank - adj_rank) >= 8).sum())
        units += part.height
    return {
        "seasons": len(rhos),
        "spearmanMean": round(float(np.mean(rhos)), 4) if rhos else None,
        "spearmanMin": round(float(np.min(rhos)), 4) if rhos else None,
        "movedEightOrMore": moved,
        "units": units,
    }


# --- Joint orderings (A04) ----------------------------------------------------------------------


def joint_orderings(
    results: Mapping[str, Split], unit_seasons: Mapping[str, np.ndarray], reps: int, seed: int
) -> dict[str, Any]:
    """Resample whole seasons once per replicate for every position together, and report how
    often each position's split-half k is below another's: whether their order is established."""
    names = list(results)
    seasons = np.unique(np.concatenate([unit_seasons[n] for n in names]))
    members = {n: {s: np.flatnonzero(unit_seasons[n] == s) for s in seasons} for n in names}
    rng = np.random.default_rng(seed)
    wins = {(a, b): 0 for a in names for b in names if a < b}
    valid = {(a, b): 0 for a in names for b in names if a < b}
    for _ in range(reps):
        picks = seasons[rng.integers(0, seasons.size, seasons.size)]
        ks: dict[str, float | None] = {}
        for n in names:
            result = results[n]
            index = np.concatenate([members[n][s] for s in picks])
            r = corr(result.a_mean[index], result.b_mean[index])
            m = float(((result.a_n[index] + result.b_n[index]) / 2).mean())
            ks[n] = k_from_r(r, m)
        for a, b in wins:
            ka, kb = ks[a], ks[b]
            if ka is not None and kb is not None:
                valid[(a, b)] += 1
                wins[(a, b)] += int(ka < kb)
    return {
        "reps": reps,
        "seed": seed,
        "pKLower": {
            f"{a}<{b}": round(wins[(a, b)] / valid[(a, b)], 4) if valid[(a, b)] else None
            for a, b in wins
        },
    }
