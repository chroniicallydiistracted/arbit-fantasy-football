"""Phase C of the M3-3 DvP study: does a forecast make better start/sit choices?

The owner's specification v1.1, §5 Phase C, §7 and §9 Phase 5. Phase C runs only for a group with a
credible group-level signal, and only D/ST has one. A D/ST is one unit per team, so its group-level
forecast is its player-level forecast. The forecast row for offense O carries the points of the
D/ST that faced O, and that D/ST is the unit.

Pure functions over frozen forecasts and their labels: nothing here fits a parameter, reads the
database or writes anything. The rule and every choice below were declared in
`config/dvp/sitstart.json` before any Phase C result was computed.
"""

from collections.abc import Sequence
from typing import Any

import numpy as np
import polars as pl

DST = "DST"
TIE = 1e-9


def units(
    forecasts: pl.DataFrame, observations: pl.DataFrame, models: Sequence[str]
) -> pl.DataFrame:
    """One row per D/ST and game: the D/ST that scores (`unit`), the offense it faced, its actual
    points and each model's forecast. In the canonical observations a D/ST row is oriented to the
    offense (its `unit` is the offense whose vulnerability is measured) and its `defense` is the
    D/ST that earned the points; both are checked. Only rows with a valid label and every model's
    forecast are kept (common rows)."""
    dst = forecasts.filter(pl.col("position") == DST)
    keys = observations.filter(pl.col("position") == DST).select(
        "game_id", "offense", pl.col("unit").alias("_studied"), "defense"
    )
    joined = dst.join(keys, on=["game_id", "offense"], how="left", validate="1:1")
    missing = joined.filter(pl.col("defense").is_null()).height
    if missing:
        raise ValueError(f"{missing} D/ST forecast rows have no canonical D/ST")
    wrong = joined.filter(
        (pl.col("defense") == pl.col("offense")) | (pl.col("_studied") != pl.col("offense"))
    ).height
    if wrong:
        raise ValueError(f"{wrong} D/ST rows are not oriented offense against the opposing D/ST")
    common = pl.all_horizontal([pl.col(m).is_not_null() & pl.col(m).is_finite() for m in models])
    return (
        joined.filter((pl.col("status") == "valid") & pl.col("points").is_not_null() & common)
        .select(
            "season",
            "week",
            "game_id",
            pl.col("defense").alias("unit"),
            "offense",
            "points",
            *models,
        )
        .sort("season", "week", "unit")
    )


def pairs(table: pl.DataFrame, models: Sequence[str], base: str) -> pl.DataFrame:
    """Every unordered pair of units playing in the same season and week, with each model's pick
    (1 = the first unit, -1 = the second, 0 = a forecast tie), the base model's rank of both units
    that week, and the actual points of both."""
    parts = []
    for (season, week), group in table.group_by(["season", "week"], maintain_order=True):
        group = group.sort("unit")
        n = group.height
        if n < 2:
            continue
        i, j = np.triu_indices(n, k=1)
        y = group.get_column("points").to_numpy()
        rank = group.get_column(base).rank("ordinal", descending=True).to_numpy().astype(np.int64)
        unit = group.get_column("unit").to_numpy()
        columns: dict[str, Any] = {
            "season": np.full(i.size, season, dtype=np.int32),
            "week": np.full(i.size, week, dtype=np.int32),
            "a": unit[i],
            "b": unit[j],
            "ya": y[i],
            "yb": y[j],
            "rank_a": rank[i],
            "rank_b": rank[j],
        }
        for m in models:
            f = group.get_column(m).to_numpy()
            columns[f"fa_{m}"] = f[i]
            columns[f"fb_{m}"] = f[j]
            diff = f[i] - f[j]
            columns[f"pick_{m}"] = np.where(np.abs(diff) <= TIE, 0, np.sign(diff)).astype(np.int8)
        parts.append(pl.DataFrame(columns))
    if not parts:
        raise ValueError("no week has two units")
    return pl.concat(parts)


def _value(p: pl.DataFrame, model: str) -> np.ndarray:
    """Actual points of the unit a model starts; a forecast tie is a coin flip, so its mean."""
    pick = p.get_column(f"pick_{model}").to_numpy()
    ya, yb = p.get_column("ya").to_numpy(), p.get_column("yb").to_numpy()
    return np.where(pick > 0, ya, np.where(pick < 0, yb, (ya + yb) / 2))


def _credit(p: pl.DataFrame, model: str) -> np.ndarray:
    """1 if the model starts the unit that scored more, 0.5 for a forecast tie, 0 otherwise;
    NaN where the units scored the same (excluded from accuracy)."""
    pick = p.get_column(f"pick_{model}").to_numpy().astype(np.float64)
    actual = p.get_column("ya").to_numpy() - p.get_column("yb").to_numpy()
    sign = np.where(np.abs(actual) <= TIE, 0.0, np.sign(actual))
    credit = np.where(pick == 0, 0.5, (pick == sign).astype(np.float64))
    return np.where(sign == 0, np.nan, credit)


def _accuracy(p: pl.DataFrame, models: Sequence[str]) -> dict[str, Any]:
    out: dict[str, Any] = {"pairs": p.height}
    for m in models:
        c = _credit(p, m)
        out[m] = round(float(np.nanmean(c)) * 100, 3) if np.isfinite(c).any() else None
    return out


def _spearman_within_weeks(table: pl.DataFrame, model: str) -> float:
    values = []
    for _, group in table.group_by(["season", "week"]):
        if group.height < 3:
            continue
        rf = group.get_column(model).rank("average").to_numpy().astype(np.float64)
        ry = group.get_column("points").rank("average").to_numpy().astype(np.float64)
        if rf.std() == 0 or ry.std() == 0:
            continue
        values.append(float(np.corrcoef(rf, ry)[0, 1]))
    return round(float(np.mean(values)), 4) if values else float("nan")


def _top(table: pl.DataFrame, model: str, k: int) -> pl.DataFrame:
    """Actual points of the k highest-forecast units each week (ties broken by unit)."""
    return (
        table.sort(["season", "week", model, "unit"], descending=[False, False, True, False])
        .group_by(["season", "week"], maintain_order=True)
        .head(k)
        .group_by(["season", "week"], maintain_order=True)
        .agg(pl.col("points").sum().alias(model))
    )


def metrics(
    table: pl.DataFrame,
    p: pl.DataFrame,
    base: str,
    candidate: str,
    *,
    close: float,
    pool: tuple[int, int],
    top: int,
    reps: int,
    seed: int,
) -> dict[str, Any]:
    """Every Phase C measure for one period (config/dvp/sitstart.json)."""
    models = (base, candidate)
    credit = {m: _credit(p, m) for m in models}
    tie = np.isnan(credit[base])
    changed = (
        p.get_column(f"pick_{candidate}").to_numpy() != p.get_column(f"pick_{base}").to_numpy()
    )
    gain = _value(p, candidate) - _value(p, base)
    accuracy = _accuracy(p, models)
    delta = accuracy[candidate] - accuracy[base]

    week_key = (p.get_column("season").to_numpy().astype(np.int64) * 100) + p.get_column(
        "week"
    ).to_numpy()
    weeks, inverse = np.unique(week_key, return_inverse=True)
    valid = ~tie
    per_week = {
        "n": np.bincount(inverse, weights=valid.astype(np.float64), minlength=weeks.size),
        base: np.bincount(
            inverse, weights=np.where(valid, credit[base], 0.0), minlength=weeks.size
        ),
        candidate: np.bincount(
            inverse, weights=np.where(valid, credit[candidate], 0.0), minlength=weeks.size
        ),
        "gain": np.bincount(inverse, weights=np.where(changed, gain, 0.0), minlength=weeks.size),
    }
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, weeks.size, size=(reps, weeks.size))
    n = per_week["n"][draws].sum(axis=1)
    boot_delta = (per_week[candidate][draws].sum(axis=1) - per_week[base][draws].sum(axis=1)) / n
    boot_gain = per_week["gain"][draws].mean(axis=1)

    close_pairs = p.filter((pl.col(f"fa_{base}") - pl.col(f"fb_{base}")).abs() < close)
    lo, hi = pool
    pool_pairs = p.filter(pl.col("rank_a").is_between(lo, hi) & pl.col("rank_b").is_between(lo, hi))
    tops = _top(table, base, top).join(_top(table, candidate, top), on=["season", "week"])
    top_base = tops.get_column(base).to_numpy()
    top_candidate = tops.get_column(candidate).to_numpy()
    weekly_gain = per_week["gain"]
    changed_gain = gain[changed]

    def sub(part: pl.DataFrame) -> dict[str, Any]:
        a = _accuracy(part, models)
        if a[base] is not None and a[candidate] is not None:
            a["deltaPp"] = round(a[candidate] - a[base], 3)
        return a

    return {
        "units": table.height,
        "weeks": int(weeks.size),
        "pairs": p.height,
        "actualTies": int(tie.sum()),
        "accuracy": {base: accuracy[base], candidate: accuracy[candidate]},
        "deltaPp": round(delta, 3),
        "deltaPp95": [round(float(q) * 100, 3) for q in np.quantile(boot_delta, [0.025, 0.975])],
        "changed": {
            "count": int(changed.sum()),
            "share": round(float(changed.mean()), 4),
            "candidateRightWhenChanged": round(
                float(np.nanmean(credit[candidate][changed & valid])) * 100, 2
            )
            if (changed & valid).any()
            else None,
        },
        "pointsFromChanges": {
            "total": round(float(changed_gain.sum()), 2),
            "perChangedDecision": round(float(changed_gain.mean()), 4) if changed.any() else 0.0,
            "perWeek": round(float(weekly_gain.mean()), 3),
            "perWeek95": [round(float(q), 3) for q in np.quantile(boot_gain, [0.025, 0.975])],
        },
        "worstCase": {
            "singleDecision": round(float(changed_gain.min()), 2) if changed.any() else 0.0,
            "week": round(float(weekly_gain.min()), 2),
            "weeksWithNetLoss": int((weekly_gain < 0).sum()),
        },
        "spearmanWithinWeek": {m: _spearman_within_weeks(table, m) for m in models},
        f"top{top}": {
            base: round(float(top_base.mean()), 3),
            candidate: round(float(top_candidate.mean()), 3),
            "deltaPerWeek": round(float((top_candidate - top_base).mean()), 3),
        },
        "close": {"threshold": close, **sub(close_pairs)},
        "waiverPool": {"ranks": list(pool), **sub(pool_pairs)},
    }


def decide(periods: dict[str, dict[str, Any]], minimum_pp: float) -> tuple[str, str]:
    """The predeclared Phase C rule over development, validation and holdout."""
    clears = {
        name: m["deltaPp"] >= minimum_pp and m["pointsFromChanges"]["total"] > 0
        for name, m in periods.items()
    }
    misses = {name: m["deltaPp"] < minimum_pp for name, m in periods.items()}
    detail = ", ".join(
        f"{name} {m['deltaPp']:+.2f} pp, {m['pointsFromChanges']['total']:+.1f} points"
        for name, m in periods.items()
    )
    if all(clears.values()):
        return (
            "PROMISING",
            f"clears {minimum_pp} pp with net points gained in every period: {detail}",
        )
    if all(misses.values()):
        return "NOT_USEFUL", f"misses {minimum_pp} pp in every period: {detail}"
    return "INCONCLUSIVE", f"mixed against {minimum_pp} pp: {detail}"
