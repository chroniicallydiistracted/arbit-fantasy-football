"""Split-half reliability arithmetic of the v0 study, with its checks (spec §4, §6; T08-T12).

Under an equal-size, stable-trait, independent-error model, two halves of m games each correlate at
r_m = m·tau2 / (m·tau2 + sigma2). Then k = sigma2 / tau2 = m(1 - r)/r games give the defense's own
record half the weight, one game's reliability is 1/(1 + k), and after n games the record earns
w(n) = n / (n + k). v0 used m = the mean half size over units (8.25 for 2016-2025, since 17-game
seasons split 8/9); that is why its WR k is 44.1 and not the 42.6 that m = 8 gives. A correlation
at or below zero identifies no k: the functions return None rather than a negative or infinite
weight. With unequal halves m_a, m_b the model's expected correlation is
sqrt(m_a/(m_a + k) · m_b/(m_b + k)); the m-averaged shortcut is an approximation of it.
"""

import math
import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import polars as pl

MIN_PAIRS = 20  # v0's pearson returns nothing below 20 units


def pearson(xs: Sequence[float], ys: Sequence[float], minimum: int = MIN_PAIRS) -> float | None:
    if len(xs) != len(ys):
        raise ValueError("unpaired")
    if len(xs) < minimum:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else None


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for position in range(i, j + 1):
            ranks[order[position]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    return pearson(_ranks(xs), _ranks(ys))


def k_from_r(r: float | None, m: float) -> float | None:
    """Games for half signal from a split-half correlation of m-game halves; None if unidentified."""
    if m <= 0:
        raise ValueError("half size must be positive")
    if r is None or math.isnan(r) or r <= 0:
        return None
    if r >= 1:
        return 0.0
    return m * (1 - r) / r


def single_game(k: float | None) -> float | None:
    return None if k is None else 1 / (1 + k)


def weight(n: float, k: float | None) -> float | None:
    """The defense's own record's credibility after n games: n / (n + k)."""
    if n < 0:
        raise ValueError("games must be nonnegative")
    if k is None:
        return None
    if n == 0:
        return 0.0
    return n / (n + k)


def expected_split_r(m_a: float, m_b: float, k: float) -> float:
    """The model's split-half correlation for halves of m_a and m_b games (spec §6)."""
    if k < 0 or m_a <= 0 or m_b <= 0:
        raise ValueError("k must be nonnegative and halves positive")
    return math.sqrt(m_a / (m_a + k) * m_b / (m_b + k))


def leave_one_out(by: Sequence[str], value: str) -> pl.Expr:
    """Mean of `value` over the group's other rows; null when the group has one row (v0)."""
    total = pl.col(value).sum().over(by)
    count = pl.col(value).count().over(by)
    return pl.when(count > 1).then((total - pl.col(value)) / (count - 1)).otherwise(None)


def halves(
    frame: pl.DataFrame, unit: Sequence[str], value: str, min_games: int = 4
) -> pl.DataFrame:
    """Each unit's odd-week and even-week means (NFL week parity, not game order) and game
    counts, keeping units with at least `min_games` non-null values in both halves (v0)."""
    rows = frame.filter(pl.col(value).is_not_null()).with_columns(
        (pl.col("week") % 2 == 1).alias("odd")
    )
    parts = rows.group_by(*unit, "odd").agg(
        pl.col(value).mean().alias("mean"), pl.len().cast(pl.Int32).alias("n")
    )
    odd = parts.filter(pl.col("odd")).select(
        *unit, pl.col("mean").alias("odd_mean"), pl.col("n").alias("odd_n")
    )
    even = parts.filter(~pl.col("odd")).select(
        *unit, pl.col("mean").alias("even_mean"), pl.col("n").alias("even_n")
    )
    return (
        odd.join(even, on=list(unit), how="inner")
        .filter((pl.col("odd_n") >= min_games) & (pl.col("even_n") >= min_games))
        .sort(*unit)
    )


@dataclass(frozen=True)
class SplitHalf:
    units: int
    r: float | None
    spearman: float | None
    m: float | None
    k: float | None
    half_sizes: dict[str, int]

    @property
    def single_game(self) -> float | None:
        return single_game(self.k)

    @property
    def season_reliability(self) -> float | None:
        return None if self.r is None else 2 * self.r / (1 + self.r)

    def summary(self) -> dict[str, Any]:
        return {
            "units": self.units,
            "pearson": _round(self.r, 4),
            "spearman": _round(self.spearman, 4),
            "meanHalfGames": _round(self.m, 3),
            "k": _round(self.k, 2),
            "singleGameReliability": _round(self.single_game, 4),
            "seasonReliability": _round(self.season_reliability, 4),
            "weight": {str(n): _round(weight(n, self.k), 4) for n in (4, 8, 12, 16)},
            "halfSizes": self.half_sizes,
        }


def split_half(pairs: pl.DataFrame) -> SplitHalf:
    odd = pairs.get_column("odd_mean").to_list()
    even = pairs.get_column("even_mean").to_list()
    sizes = ((pairs.get_column("odd_n") + pairs.get_column("even_n")) / 2).to_list()
    m = statistics.fmean(sizes) if sizes else None
    r = pearson(odd, even)
    games = pl.concat([pairs.get_column("odd_n"), pairs.get_column("even_n")]).alias("n")
    counts = games.value_counts().sort("n") if pairs.height else None
    return SplitHalf(
        units=pairs.height,
        r=r,
        spearman=spearman(odd, even) if r is not None else None,
        m=m,
        k=k_from_r(r, m) if m else None,
        half_sizes={str(n): int(c) for n, c in counts.iter_rows()} if counts is not None else {},
    )


def fisher_interval(r: float | None, n: int, z: float = 1.959964) -> tuple[float, float] | None:
    """Normal-theory interval for a correlation; assumes independent units (often too narrow)."""
    if r is None or n <= 3 or abs(r) >= 1:
        return None
    centre, half = math.atanh(r), z / math.sqrt(n - 3)
    return math.tanh(centre - half), math.tanh(centre + half)


def bootstrap(
    pairs: pl.DataFrame, reps: int, seed: int, cluster: str | None = None
) -> dict[str, Any]:
    """Percentile intervals for r and k from resampling units (or whole clusters of units, e.g.
    seasons) with replacement. Deterministic for a seed (T13)."""
    rows = pairs.select(
        "odd_mean", "even_mean", "odd_n", "even_n", *([cluster] if cluster else [])
    ).rows()
    groups: list[list[tuple[Any, ...]]]
    if cluster:
        by: dict[Any, list[tuple[Any, ...]]] = {}
        for row in rows:
            by.setdefault(row[-1], []).append(row)
        groups = [by[key] for key in sorted(by)]
    else:
        groups = [[row] for row in rows]
    rng = random.Random(seed)
    rs: list[float] = []
    ks: list[float] = []
    unidentified = 0
    for _ in range(reps):
        sample = [row for _ in groups for row in groups[rng.randrange(len(groups))]]
        r = pearson([s[0] for s in sample], [s[1] for s in sample])
        m = statistics.fmean((s[2] + s[3]) / 2 for s in sample)
        k = k_from_r(r, m)
        if r is not None:
            rs.append(r)
        if k is None:
            unidentified += 1
        else:
            ks.append(k)
    return {
        "reps": reps,
        "seed": seed,
        "resampled": cluster or "unit",
        "pearson95": _percentiles(rs),
        "k95": _percentiles(ks),
        "unidentifiedShare": round(unidentified / reps, 4),
    }


def _percentiles(values: list[float]) -> list[float] | None:
    if not values:
        return None
    ordered = sorted(values)

    def at(q: float) -> float:
        return ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))]

    return [round(at(0.025), 4), round(at(0.975), 4)]


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)
