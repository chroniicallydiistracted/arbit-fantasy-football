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


def without_decision(
    holdings: Mapping[str, Sequence[str]],
    free_agents: Sequence[str],
    playing: set[str],
    kind: str,
) -> dict[str, str]:
    """Teams `decide` skips for this kind, each with its reason, so none is omitted silently."""
    out = {}
    for team, held in sorted(holdings.items()):
        own = sorted({u for u in held if u in playing})
        pool = {u for u in free_agents if u in playing}
        if kind == START and len(own) < 2:
            if not held:
                out[team] = "holds no D/ST"
            elif not own:
                out[team] = "every D/ST it holds is on bye"
            else:
                out[team] = "holds one playing D/ST"
        elif kind != START and not own and not pool:
            out[team] = "no playing D/ST held and none in the pool"
    return out


ALL_WEEKS = "all_weeks"  # v2 (final directive PB-AUD-04): every evaluated week is a block
CHANGED_WEEKS = "changed_weeks"  # v1: only weeks where a decision changed


def summarize(
    table: pl.DataFrame,
    base: str,
    candidate: str,
    reps: int,
    seed: int,
    *,
    blocks: str = ALL_WEEKS,
    weeks: Sequence[int] | None = None,
) -> dict[str, Any]:
    """The declared metrics for one decision kind (rows with every option labelled).

    The bootstrap resamples week blocks of the cumulative B06-minus-B00 points. With ALL_WEEKS
    every week with an evaluated decision is a block, a week with no changed decision adding zero;
    weeks in `weeks` with no evaluable decision are listed as missing coverage. CHANGED_WEEKS
    reproduces v1, which resampled only weeks where a decision changed."""
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
    evaluated = sorted(set(rows.get_column("week").to_list()))
    changed_weeks = sorted(set(changed.get_column("week").to_list()))
    out["evaluatedWeeks"] = len(evaluated)
    out["zeroChangeWeeks"] = sorted(set(evaluated) - set(changed_weeks))
    if weeks is not None:
        out["weeksWithoutEvaluableDecisions"] = sorted(set(weeks) - set(evaluated))
    if blocks == CHANGED_WEEKS:
        if gain.size and reps > 0:
            week_of = changed.get_column("week").to_numpy()
            labels = np.unique(week_of)
            members = [np.flatnonzero(week_of == w) for w in labels]
            rng = np.random.default_rng(seed)
            totals = [
                float(
                    gain[
                        np.concatenate(
                            [members[i] for i in rng.integers(0, labels.size, labels.size)]
                        )
                    ].sum()
                )
                for _ in range(reps)
            ]
            out["pointsFromChanges95"] = [
                round(float(q), 2) for q in np.quantile(totals, [0.025, 0.975])
            ]
            out["bootstrap"] = {"method": CHANGED_WEEKS, "blocks": int(labels.size)}
        return out
    if evaluated and reps > 0:
        per_week = {w: 0.0 for w in evaluated}
        for w, g in zip(changed.get_column("week").to_list(), gain.tolist(), strict=True):
            per_week[w] += g
        values = np.array([per_week[w] for w in evaluated])
        rng = np.random.default_rng(seed)
        totals = [
            float(values[rng.integers(0, values.size, values.size)].sum()) for _ in range(reps)
        ]
        out["pointsFromChanges95"] = [
            round(float(q), 2) for q in np.quantile(totals, [0.025, 0.975])
        ]
        out["bootstrap"] = {
            "method": ALL_WEEKS,
            "blocks": int(values.size),
            "reps": reps,
            "seed": seed,
        }
    return out


# Feasibility of a streaming pick (final directive PB-AUD-05). Independent single-week,
# single-manager recommendations: no waiver priority, competition or multi-week value.
HELD = "HELD"
EXECUTABLE = "EXECUTABLE"
REQUIRES_DROP = "REQUIRES_DROP"
REQUIRES_DST_DROP = "REQUIRES_DST_DROP"
UNKNOWN_FEASIBILITY = "UNKNOWN"


def feasibility(
    pick: str, held: Sequence[str], roster_size: int | None, capacity: int, dst_limit: int
) -> str:
    """Can the team act on `pick` at the preweek cutoff (no player game-locked then)?"""
    if pick in held:
        return HELD
    if roster_size is None:
        return UNKNOWN_FEASIBILITY
    if len(held) >= dst_limit:
        return REQUIRES_DST_DROP
    if roster_size < capacity:
        return EXECUTABLE
    return REQUIRES_DROP


def collisions(rows: Sequence[Mapping[str, Any]], model: str) -> dict[str, Any]:
    """Unowned units one model recommends to more than one team in the same week: only one team
    could acquire each."""
    picked: dict[tuple[int, str], list[str]] = {}
    for r in rows:
        if r[f"pick_{model}"] not in r.get("held", ()):
            picked.setdefault((r["week"], r[f"pick_{model}"]), []).append(r["team"])
    shared = {k: sorted(v) for k, v in picked.items() if len(v) > 1}
    return {
        "unownedPicks": sum(len(v) for v in picked.values()),
        "sharedUnits": len(shared),
        "decisionsInCollision": sum(len(v) for v in shared.values()),
        "byWeek": {
            str(w): {unit: teams for (week, unit), teams in shared.items() if week == w}
            for w in sorted({week for week, _ in shared})
        },
    }


def matchup_effects_v2(
    starts: Sequence[Mapping[str, Any]],
    lineups: pl.DataFrame,
    matchups: Sequence[Mapping[str, Any]],
    points: Mapping[tuple[int, str], float],
    base: str,
    candidate: str,
) -> dict[str, Any]:
    """Individual-decision counterfactual for start decisions (final directive PB-AUD-06): the
    team's official total minus the started D/ST's official points plus the pick's actual FFA
    points (`points`: (week, unit) -> canonical label), the opponent's official total held fixed.
    Only picks among the team's options at the cutoff (`optionUnits`) count; ties, unknown points and ineligible
    picks are counted apart. Not a change in league win probability."""
    opponent: dict[tuple[int, str], tuple[float, float]] = {}
    for match in matchups:
        if not match.get("winner") or len(match["scoringPeriods"]) != 1:
            continue
        week = match["scoringPeriods"][0]
        home, away = match["home"], match["away"]
        hp, ap = float(home["officialPoints"]), float(away["officialPoints"])
        opponent[(week, home["team"])] = (hp, ap)
        opponent[(week, away["team"])] = (ap, hp)
    started: dict[tuple[int, str], float | None] = {}
    for entry in lineups.iter_rows(named=True):
        if entry["slot"] == "DST":
            value = entry["points"]
            started[(entry["week"], entry["team"])] = None if value is None else float(value)

    def result(own: float, other: float) -> str:
        return "W" if own > other else ("L" if own < other else "T")

    counts = {"counted": 0, "noMatchupResult": 0, "unknownPoints": 0, "ineligiblePick": 0}
    outcomes: dict[str, dict[str, int]] = {
        model: {"lossesToWins": 0, "winsToLosses": 0, "toTies": 0, "fromTies": 0, "unchanged": 0}
        for model in (base, candidate)
    }
    differ = {"candidateWins": 0, "baseWins": 0, "other": 0}
    for r in starts:
        key = (r["week"], r["team"])
        if key not in opponent:
            counts["noMatchupResult"] += 1
            continue
        if any(r[f"pick_{model}"] not in r["optionUnits"] for model in (base, candidate)):
            counts["ineligiblePick"] += 1
            continue
        pick_points = {
            model: points.get((r["week"], r[f"pick_{model}"])) for model in (base, candidate)
        }
        actual_dst = started.get(key, 0.0)
        if actual_dst is None or any(v is None for v in pick_points.values()):
            counts["unknownPoints"] += 1
            continue
        own, other = opponent[key]
        actual = result(own, other)
        outcome = {
            model: result(own - actual_dst + float(v), other)  # type: ignore[arg-type]
            for model, v in pick_points.items()
        }
        counts["counted"] += 1
        for model in (base, candidate):
            change = (actual, outcome[model])
            name = (
                "unchanged"
                if actual == outcome[model]
                else "lossesToWins"
                if change == ("L", "W")
                else "winsToLosses"
                if change == ("W", "L")
                else "toTies"
                if outcome[model] == "T"
                else "fromTies"
            )
            outcomes[model][name] += 1
        if outcome[base] != outcome[candidate]:
            if outcome[candidate] == "W" or (outcome[candidate] == "T" and outcome[base] == "L"):
                differ["candidateWins"] += 1
            elif outcome[base] == "W" or (outcome[base] == "T" and outcome[candidate] == "L"):
                differ["baseWins"] += 1
            else:
                differ["other"] += 1
    return {
        "kind": "individual-decision counterfactual; opponent's actual total held fixed",
        **counts,
        "againstActual": outcomes,
        "resultsDifferBetweenModels": differ,
    }


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
