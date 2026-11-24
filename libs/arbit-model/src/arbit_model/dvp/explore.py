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


# --- Opportunity and efficiency (owner audit AUD-02, remediation 2) ---------------------------

OPPORTUNITY_COLUMNS = ("b07v", "b07e", "b07ve")
OPP_KEYS = ["game_id", "offense", "position"]


def _reml_k(frame: pl.DataFrame, adjustment: str) -> float:
    g = lab.groups(lab.adjust(frame, adjustment))
    if g.size.size < 2:
        return math.inf
    fit = lab.reml_components(g)
    return math.inf if fit.k is None or not fit.converged else fit.k


def opportunity_parameters(
    rows: pl.DataFrame, season: int, positions: Sequence[str], volumes: pl.DataFrame
) -> dict[str, dict[str, float]]:
    """Per position, from seasons before `season` only: the side's own volume k (season
    adjusted), the opposing unit's volume-allowed and efficiency-allowed k (leave-one-out
    adjusted), and last season's league volume per game and points per unit of volume."""
    train = rows.filter(pl.col("season") < season).join(
        volumes.select(*OPP_KEYS, "volume"), on=OPP_KEYS, how="inner"
    )
    out: dict[str, dict[str, float]] = {}
    for position in positions:
        part = train.filter(pl.col("position") == position)
        with_volume = part.filter(pl.col("volume") > 0).with_columns(
            (pl.col("points") / pl.col("volume")).alias("eff")
        )
        prev = part.filter(pl.col("season") == season - 1)
        volume_sum = float(prev.get_column("volume").sum() or 0.0)
        out[position] = {
            "kSideVolume": _reml_k(wf._frame(part, "side", "opp", "volume"), "season"),
            "kOppVolume": _reml_k(wf._frame(part, "opp", "side", "volume"), "loo_mean"),
            "kOppEfficiency": _reml_k(wf._frame(with_volume, "opp", "side", "eff"), "loo_mean"),
            "leagueVolume": float(prev.get_column("volume").mean() or 0.0),  # type: ignore[arg-type]
            "leagueEfficiency": float(prev.get_column("points").sum()) / volume_sum
            if volume_sum
            else 0.0,
        }
    return out


def make_opportunity_extra(
    rows: pl.DataFrame, season: int, positions: Sequence[str], volumes: pl.DataFrame
) -> shadow.Extra:
    """The `extra` hook adding the volume channel (`b07v`), the efficiency channel (`b07e`)
    and both (`b07ve`), from the opposing unit's completed games before the cutoff.

    For each history row, against what the scoring side usually produces (its other games this
    season, shrunk toward last season's league level with its own volume k):
    - volume residual = volume - expected volume;
    - efficiency residual (per unit of volume) = (points - volume * expected efficiency) / volume.
    The opposing unit's terms are its mean volume residual and its volume-weighted efficiency
    residual, each shrunk by n / (n + k) with its own training k. The forecast adds
    volume residual x the side's expected efficiency, and/or efficiency residual x the side's
    expected volume. Without history the terms are zero (B00)."""
    parameters = opportunity_parameters(rows, season, positions, volumes)
    table = volumes.select(*OPP_KEYS, "volume")

    def by_position(key: str) -> pl.Expr:
        return pl.col("position").replace_strict(
            {p: (1e12 if math.isinf(v[key]) else v[key]) for p, v in parameters.items()},
            default=1e12,
        )

    def extra(
        forecast: pl.DataFrame, hist: pl.DataFrame, pit: pl.DataFrame, params: wf.FoldParams
    ) -> pl.DataFrame:
        f = forecast.with_row_index("_row")
        league_v, league_e, k_side = (
            by_position("leagueVolume"),
            by_position("leagueEfficiency"),
            by_position("kSideVolume"),
        )
        prior_mass = k_side * league_v  # pseudo-volume behind the league efficiency
        hv = hist.join(table, on=OPP_KEYS, how="inner").filter(pl.col("volume").is_not_null())
        if hv.height:
            side = hv.group_by("side", "position").agg(
                pl.len().alias("_n_s"),
                pl.col("volume").sum().alias("_v_s"),
                pl.col("points").sum().alias("_p_s"),
            )
            hv = hv.join(side, on=["side", "position"])
            others = (pl.col("_n_s") - 1).cast(pl.Float64)
            expected_v = (
                pl.when(others > 0)
                .then((pl.col("_v_s") - pl.col("volume") + k_side * league_v) / (others + k_side))
                .otherwise(league_v)
            )
            expected_e = (pl.col("_p_s") - pl.col("points") + prior_mass * league_e) / (
                pl.col("_v_s") - pl.col("volume") + prior_mass
            )
            terms = (
                hv.with_columns(
                    (pl.col("volume") - expected_v).alias("_rv"),
                    (pl.col("points") - pl.col("volume") * expected_e).alias("_re"),
                )
                .group_by("opp", "position")
                .agg(
                    pl.len().alias("_n_o"),
                    pl.col("_rv").mean().alias("_r_vol"),
                    pl.col("_re").sum().alias("_re_sum"),
                    pl.col("volume").sum().alias("_v_o"),
                )
            )
            f = f.join(terms, on=["opp", "position"], how="left").join(
                side, on=["side", "position"], how="left"
            )
        else:
            f = f.with_columns(
                *[
                    pl.lit(None, dtype=pl.Float64).alias(c)
                    for c in ("_n_o", "_r_vol", "_re_sum", "_v_o", "_n_s", "_v_s", "_p_s")
                ]
            )
        n_o = pl.col("_n_o").fill_null(0).cast(pl.Float64)
        n_s = pl.col("_n_s").fill_null(0).cast(pl.Float64)
        side_v = (pl.col("_v_s").fill_null(0.0) + k_side * league_v) / (n_s + k_side)
        side_e = (pl.col("_p_s").fill_null(0.0) + prior_mass * league_e) / (
            pl.col("_v_s").fill_null(0.0) + prior_mass
        )
        r_eff = (
            pl.when(pl.col("_v_o").fill_null(0.0) > 0)
            .then(pl.col("_re_sum") / pl.col("_v_o"))
            .otherwise(0.0)
        )
        w_v = pl.when(n_o > 0).then(n_o / (n_o + by_position("kOppVolume"))).otherwise(0.0)
        w_e = pl.when(n_o > 0).then(n_o / (n_o + by_position("kOppEfficiency"))).otherwise(0.0)
        volume_term = (w_v * pl.col("_r_vol").fill_null(0.0) * side_e).fill_null(0.0)
        efficiency_term = (w_e * r_eff * side_v).fill_null(0.0)
        f = f.with_columns(
            (pl.col("b00") + volume_term).alias("b07v"),
            (pl.col("b00") + efficiency_term).alias("b07e"),
            (pl.col("b00") + volume_term + efficiency_term).alias("b07ve"),
        ).sort("_row")
        return f.select(*forecast.columns, *OPPORTUNITY_COLUMNS)

    extra.parameters = parameters  # type: ignore[attr-defined]
    return extra


def compose(*hooks: shadow.Extra) -> shadow.Extra:
    """One hook that runs several in turn; each only adds columns."""

    def extra(
        forecast: pl.DataFrame, hist: pl.DataFrame, pit: pl.DataFrame, params: wf.FoldParams
    ) -> pl.DataFrame:
        for hook in hooks:
            forecast = hook(forecast, hist, pit, params)
        return forecast

    return extra
