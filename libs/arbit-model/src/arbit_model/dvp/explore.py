"""Exploratory DvP estimators, version 2 (owner audit remediation 3). Never frozen candidates.

They were added after the 2025 holdout had been inspected, so every result is EXPLORATORY
(AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS.md). Results can propose a new, separately frozen
test; they never change the 2026 confirmation, whose candidates stay as frozen.

They run inside `shadow.walk_targets` through its `extra` hook, after the frozen variants. They use
the same cutoff's feature view and the same point-in-time B00 baselines, so they share the frozen
variants' rows, timing and comparator exactly. A built-in check recomputes the frozen B03 from the
same residual history and stops if it differs.

- **Rolling windows (`b05w3`, `b05w5`, `b05w8`):** the mean of the opposing unit's last m
  point-in-time residuals this season, shrunk by n_m / (n_m + k), with n_m = min(m, games) and k
  the fold's REML k (`k_dvp`). With no game yet the term is zero, so the forecast is B00. Unlike
  B05's exponential weights, a game leaves the window entirely after m newer games.
- **Split-half k (`b03sh`):** B03 with k from the original v0 method, fit on the training seasons
  only. It uses odd and even NFL-week halves of each unit-season's leave-one-out-adjusted points,
  with at least 4 games per half, and k = m(1 - r)/r, m the mean half size. An unidentified k
  (r <= 0) gives the record no weight.
"""

import math
from collections.abc import Sequence
from typing import Any

import polars as pl

from arbit_model.dvp import lab, reliability, shadow
from arbit_model.dvp import walkforward as wf

WINDOWS = (3, 5, 8)
COLUMNS = (*(f"b05w{m}" for m in WINDOWS), "b03sh")


def split_half_k(rows: pl.DataFrame, season: int, positions: Sequence[str]) -> dict[str, float]:
    """v0's split-half k per position, from seasons before `season` only."""
    train = rows.filter(pl.col("season") < season)
    out: dict[str, float] = {}
    for position in positions:
        part = train.filter(pl.col("position") == position)
        frame = lab.adjust(wf._frame(part, "opp", "side", "points"), "loo_mean")
        pairs = reliability.halves(frame, ("entity", "season"), "value", min_games=4)
        fit = reliability.split_half(pairs)
        out[position] = math.inf if fit.k is None else fit.k
    return out


def residual_history(hist: pl.DataFrame, pit: pl.DataFrame) -> pl.DataFrame:
    """The opposing units' point-in-time residuals in their completed games this season:
    opp, position, age (1 = most recent), residual."""
    joined = hist.join(pit, on=["game_id", "side", "position"], how="left")
    missing = joined.filter(pl.col("b00_pit").is_null()).height
    if missing:
        raise ValueError(f"{missing} history rows lack a point-in-time B00")
    return joined.select(
        "opp",
        "position",
        pl.col("week").rank("ordinal", descending=True).over("opp", "position").alias("age"),
        (pl.col("points") - pl.col("b00_pit")).alias("residual"),
    )


def window_terms(history: pl.DataFrame, windows: Sequence[int] = WINDOWS) -> pl.DataFrame:
    """Per opposing unit and position: all residuals' mean and count, and each window's."""
    aggregations: list[pl.Expr] = [
        pl.len().alias("_n_all"),
        pl.col("residual").mean().alias("_r_all"),
    ]
    for m in windows:
        recent = pl.col("age") <= m
        aggregations += [
            pl.col("residual").filter(recent).mean().alias(f"_r_w{m}"),
            recent.sum().alias(f"_n_w{m}"),
        ]
    return history.group_by("opp", "position").agg(aggregations)


def _k_expr(table: dict[str, float] | Any) -> pl.Expr:
    return pl.col("position").replace_strict(
        {p: (1e12 if math.isinf(v) else v) for p, v in dict(table).items()}, default=1e12
    )


def make_extra(
    rows: pl.DataFrame, season: int, positions: Sequence[str], windows: Sequence[int] = WINDOWS
) -> shadow.Extra:
    """The `extra` hook for one season: adds the rolling-window and split-half-k columns."""
    k_sh = split_half_k(rows, season, positions)

    def extra(
        forecast: pl.DataFrame, hist: pl.DataFrame, pit: pl.DataFrame, params: wf.FoldParams
    ) -> pl.DataFrame:
        f = forecast.with_row_index("_row")
        if hist.height:
            f = f.join(
                window_terms(residual_history(hist, pit), windows),
                on=["opp", "position"],
                how="left",
            )
        else:
            f = f.with_columns(pl.lit(None, dtype=pl.Float64).alias("_r_all"))
        k_dvp, k_split = _k_expr(params.k_dvp), _k_expr(k_sh)

        def shrunk(n_column: str, r_column: str, k: pl.Expr) -> pl.Expr:
            n = (pl.col(n_column) if n_column in f.columns else pl.lit(0)).fill_null(0)
            r = (pl.col(r_column) if r_column in f.columns else pl.lit(0.0)).fill_null(0.0)
            n = n.cast(pl.Float64)
            return pl.when(n > 0).then(n / (n + k) * r).otherwise(0.0)

        columns = {
            f"b05w{m}": pl.col("b00") + shrunk(f"_n_w{m}", f"_r_w{m}", k_dvp) for m in windows
        }
        columns["b03sh"] = pl.col("b00") + shrunk("_n_all", "_r_all", k_split)
        check = pl.col("b00") + shrunk("_n_all", "_r_all", k_dvp)
        f = f.with_columns(**columns, _b03_check=check).sort("_row")
        gap = f.select((pl.col("_b03_check") - pl.col("b03")).abs().max()).item()
        if gap is not None and gap > 1e-9:
            raise ValueError(f"the residual history differs from the frozen B03's by {gap}")
        return f.select(*forecast.columns, *columns)

    extra.split_half_k = k_sh  # type: ignore[attr-defined]
    return extra


def k_summary(k: dict[str, float]) -> dict[str, float | None]:
    return {p: None if math.isinf(v) else round(v, 3) for p, v in sorted(k.items())}
