"""League-constrained D/ST decisions in FFA (owner audit Phase B, C05L-2026). EXPLORATORY.

The rule is declared in config/dvp/league-2026-exploratory.json before results. The weekly
decision sets come from `arbit_model.ffa_history` (ownership and availability at the decision
time); the forecasts are the frozen B00 and B06. Pure functions: no I/O.

- **Start:** a team holding two or more D/STs with a game picks one. Each model starts its higher
  forecast (ties by franchise code).
- **Stream:** a team picks among its own playing D/STs and the claimable free agents.

For each decision and model: the pick, its actual points, the best option's points (regret), and
whether the two models' picks differ.
"""

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import polars as pl

START = "start"
STREAM = "stream"


def pick(options: Sequence[str], forecast: Mapping[str, float]) -> str:
    """The option with the highest forecast; ties by franchise code."""
    return sorted(options, key=lambda unit: (-forecast[unit], unit))[0]


def decide(
    week: int,
    holdings: Mapping[str, Sequence[str]],
    free_agents: Sequence[str],
    playing: set[str],
    forecasts: Mapping[str, Mapping[str, float]],
    points: Mapping[str, float],
    kind: str,
) -> list[dict[str, Any]]:
    """Every decision of one kind in one week. `forecasts` is model -> unit -> forecast; `points`
    is unit -> actual FFA points (a unit without a valid label is absent)."""
    out = []
    for team, held in sorted(holdings.items()):
        own = sorted({u for u in held if u in playing})
        options = (
            own if kind == START else sorted(set(own) | {u for u in free_agents if u in playing})
        )
        if len(options) < (2 if kind == START else 1):
            continue
        labelled = [u for u in options if u in points]
        row: dict[str, Any] = {
            "week": week,
            "team": team,
            "kind": kind,
            "options": len(options),
            "labelled": len(labelled) == len(options),
            "best": max(points[u] for u in labelled) if labelled else None,
        }
        for model, forecast in forecasts.items():
            chosen = pick(options, forecast)
            row[f"pick_{model}"] = chosen
            row[f"points_{model}"] = points.get(chosen)
        out.append(row)
    return out


def summarize(
    table: pl.DataFrame, base: str, candidate: str, reps: int, seed: int
) -> dict[str, Any]:
    """The declared metrics for one decision kind (rows with every option labelled)."""
    if table.is_empty():
        return {"decisions": 0}
    rows = table.filter(pl.col("labelled"))
    a, b = f"points_{base}", f"points_{candidate}"
    changed = rows.filter(pl.col(f"pick_{base}") != pl.col(f"pick_{candidate}"))
    gain = (changed.get_column(b) - changed.get_column(a)).to_numpy()
    out: dict[str, Any] = {
        "decisions": table.height,
        "fullyLabelled": rows.height,
        "actionable": int((rows.get_column("options") >= 2).sum()),
        "meanOptions": round(float(rows.get_column("options").mean() or 0.0), 2),  # type: ignore[arg-type]
        "changed": changed.height,
        "changedShare": round(changed.height / rows.height, 4) if rows.height else None,
        "pointsFromChanges": round(float(gain.sum()), 2),
        "pointsPerChange": round(float(gain.mean()), 3) if gain.size else None,
        "candidateRightWhenChanged": round(
            float(((gain > 0).sum() + 0.5 * (gain == 0).sum()) / gain.size), 4
        )
        if gain.size
        else None,
    }
    for model, column in ((base, a), (candidate, b)):
        regret = rows.get_column("best") - rows.get_column(column)
        out[model] = {
            "points": round(float(rows.get_column(column).sum()), 2),
            "hitRate": round(float((regret <= 1e-9).mean()), 4),  # type: ignore[arg-type]
            "meanRegret": round(float(regret.mean()), 3),  # type: ignore[arg-type]
        }
    if gain.size and reps > 0:
        weeks = changed.get_column("week").to_numpy()
        labels = np.unique(weeks)
        members = [np.flatnonzero(weeks == w) for w in labels]
        rng = np.random.default_rng(seed)
        totals = [
            float(
                gain[
                    np.concatenate([members[i] for i in rng.integers(0, labels.size, labels.size)])
                ].sum()
            )
            for _ in range(reps)
        ]
        out["pointsFromChanges95"] = [
            round(float(q), 2) for q in np.quantile(totals, [0.025, 0.975])
        ]
    return out


def matchup_effects(
    starts: pl.DataFrame,
    lineups: pl.DataFrame,
    matchups: Sequence[Mapping[str, Any]],
    base: str,
    candidate: str,
) -> dict[str, Any]:
    """For start decisions: each team's official total with each model's D/ST in place of the one
    it started (ESPN official points from the captured lineup), against the opponent's official
    total. Counts results that differ between the two models' picks and from the actual result.

    `lineups` has week, team, unit (D/ST franchise code or null), slot and official points."""
    opponent: dict[tuple[int, str], tuple[str, float, float]] = {}
    for m in matchups:
        if not m.get("winner") or len(m["scoring_periods"]) != 1:
            continue
        week = m["scoring_periods"][0]
        home, away = m["home"], m["away"]
        hp, ap = float(home["official_points"]), float(away["official_points"])
        opponent[(week, home["team_id"])] = (away["team_id"], hp, ap)
        opponent[(week, away["team_id"])] = (home["team_id"], ap, hp)
    official: dict[tuple[int, str, str], float] = {}
    started: dict[tuple[int, str], float] = {}
    for r in lineups.iter_rows(named=True):
        if r["unit"] is None:
            continue
        # A D/ST without official points (a bye) scored nothing for the team.
        value = 0.0 if r["points"] is None else float(r["points"])
        if r["points"] is not None:
            official[(r["week"], r["team"], r["unit"])] = value
        if r["slot"] == "DST":
            started[(r["week"], r["team"])] = value

    def result(own: float, other: float) -> str:
        return "W" if own > other else ("L" if own < other else "T")

    counted = differ = missing = 0
    flips: dict[str, int] = {"candidateWins": 0, "baseWins": 0}
    changes_actual = {base: 0, candidate: 0}
    against_actual = {
        m: {"lossesToWins": 0, "winsToLosses": 0, "other": 0} for m in (base, candidate)
    }
    for r in starts.iter_rows(named=True):
        key = (r["week"], r["team"])
        if key not in opponent:
            continue
        _, own_total, other_total = opponent[key]
        picks = {m: official.get((r["week"], r["team"], r[f"pick_{m}"])) for m in (base, candidate)}
        if any(v is None for v in picks.values()):
            missing += 1
            continue
        actual_dst = started.get(key, 0.0)
        outcome = {
            m: result(own_total - actual_dst + float(v), other_total)  # type: ignore[arg-type]
            for m, v in picks.items()
        }
        actual = result(own_total, other_total)
        counted += 1
        for model in (base, candidate):
            changes_actual[model] += outcome[model] != actual
            if outcome[model] != actual:
                direction = (
                    "lossesToWins"
                    if (actual, outcome[model]) == ("L", "W")
                    else "winsToLosses"
                    if (actual, outcome[model]) == ("W", "L")
                    else "other"
                )
                against_actual[model][direction] += 1
        if outcome[base] != outcome[candidate]:
            differ += 1
            if outcome[candidate] == "W" or (outcome[candidate] == "T" and outcome[base] == "L"):
                flips["candidateWins"] += 1
            else:
                flips["baseWins"] += 1
    return {
        "startDecisionsWithResults": counted,
        "missingOfficialPoints": missing,
        "resultsDifferBetweenModels": differ,
        **flips,
        "resultDiffersFromActual": changes_actual,
        "againstActual": against_actual,
    }
