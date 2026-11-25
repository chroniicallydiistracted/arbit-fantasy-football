"""AUD-06: the M3-3 DvP simulation and robustness suite (config/dvp/simulation-v1.json).

  POLARS_MAX_THREADS=1 uv run python scripts/model/dvp_simulate.py run --experiment E2 \\
      --scenarios SIM-01,SIM-04 --reps 300 --workers 8
  uv run python scripts/model/dvp_simulate.py pilot          # time 5 E2 repetitions per scenario
  uv run python scripts/model/dvp_simulate.py summarize      # receipt, plots, acceptance

Every repetition writes one JSON line to artifacts/dvp/simulation-v1/<experiment>/<scenario>.jsonl
(git-ignored); a rerun skips repetitions already recorded. Exercises Arbit's actual estimators and
rules (see the config's `code.actualImplementations`); the frozen development selection is loaded
from git at the frozen commit. Synthetic data only; no database, network or production access.
"""

import os

os.environ.setdefault("POLARS_MAX_THREADS", "1")  # before polars loads, in workers too

import argparse
import importlib.util
import json
import math
import multiprocessing
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from arbit_model.dvp import decisions, explore, lab, league, opportunity, reliability, shadow
from arbit_model.dvp import simulate as sim
from arbit_model.dvp import walkforward as wf

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/dvp/simulation-v1.json"
OUT = Path(os.environ.get("ARBIT_SIM_OUT", ROOT / "artifacts/dvp/simulation-v1"))
MASTER = 20261125
EXPERIMENTS = ("E1", "E2", "E3", "U")
DEV, VAL, HOLD = tuple(range(2017, 2024)), (2024,), (2025,)
MINIMUM = 0.01
MINIMUM_PP = 1.8
SITSTART_CLOSE, SITSTART_POOL, SITSTART_TOP = 1.0, (9, 24), 8
_FROZEN: Any = None


def frozen_cli() -> Any:
    """The frozen scripts/model/dvp.py (config/dvp/frozen.json `code`), for its _select."""
    global _FROZEN
    if _FROZEN is None:
        code = json.loads((ROOT / "config/dvp/frozen.json").read_text())["code"]
        source = subprocess.run(
            ["git", "show", f"{code}:scripts/model/dvp.py"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        spec = importlib.util.spec_from_loader("dvp_frozen_sim", loader=None)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        module.__file__ = str(ROOT / "scripts/model/dvp.py")
        sys.modules["dvp_frozen_sim"] = module
        exec(compile(source, "<frozen dvp.py>", "exec"), module.__dict__)  # noqa: S102
        _FROZEN = module
    return _FROZEN


def scenario_key(scenario: str) -> int:
    """A deterministic number for a scenario name (Python's hash() varies by process)."""
    return int(sum(ord(c) * 31**i for i, c in enumerate(scenario)) % 2**31)


def seeds(experiment: str, scenario: str, rep: int) -> list[np.random.SeedSequence]:
    """Separate streams for data, the walk, permutations and bootstraps (config randomStreams)."""
    key = (EXPERIMENTS.index(experiment), scenario_key(scenario), rep)
    return np.random.SeedSequence(MASTER, spawn_key=key).spawn(4)


def r5(x: Any) -> Any:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return None
    return round(float(x), 5)


# --- E1: estimator recovery -----------------------------------------------------------------------


def e1(scenario: str, rep: int) -> dict[str, Any]:
    base = sim.SCENARIOS[scenario]
    sc = sim.Scenario(**{**base.__dict__, "seasons": DEV})
    s_data, _, _, s_boot = seeds("E1", scenario, rep)
    data = sim.generate(sc, np.random.default_rng(s_data))
    rows = wf.prepare(data.observations)
    out: dict[str, Any] = {"rep": rep, "positions": {}}
    for p in sc.positions:
        frame = lab.adjust(
            wf._frame(rows.filter(pl.col("position") == p), "opp", "side", "points"), "loo_mean"
        )
        g = lab.groups(frame)
        fit = lab.reml_components(g)
        pairs = reliability.halves(frame, ("entity", "season"), "value", min_games=4)
        half = reliability.split_half(pairs)
        entry = {
            "kTrue": None if math.isinf(sc.k_true) else sc.k_true,
            "tau2True": sc.trait_sd(p) ** 2,
            "sigma2True": sim.NOISE[p] ** 2,
            "kReml": r5(fit.k),
            "tau2": r5(fit.tau2),
            "sigma2": r5(fit.sigma2),
            "icc": r5(fit.icc),
            "converged": fit.converged,
            "boundary": fit.boundary,
            "splitHalfR": r5(half.r),
            "kSplitHalf": r5(half.k),
            "units": half.units,
        }
        if rep < 200:
            boot = lab.bootstrap_components(
                g, 200, int(s_boot.generate_state(1)[0]), lab.reml_components
            )
            entry["k95"] = boot["k95"]
            entry["bootBoundaryShare"] = boot["boundaryShare"]
        out["positions"][p] = entry
    if sc.channel != "points":
        table = data.observations.join(
            data.volumes, on=["game_id", "offense", "position"]
        ).with_columns((pl.col("points") / pl.col("volume")).alias("efficiency"))
        rel = opportunity.reliability(
            table, list(sc.positions), 20, int(s_boot.generate_state(1)[0])
        )
        out["opportunity"] = {
            p: {
                m: {"k": v[m]["k"], "boundary": v[m]["boundary"]}
                for m in ("points", "volume", "efficiency")
            }
            for p, v in rel.items()
        }
    return out


# --- E2: the complete procedure ------------------------------------------------------------------


def _stage(
    data: sim.Synthetic,
    rows: pl.DataFrame,
    labels: pl.DataFrame,
    season: int,
    positions: list[str],
    seed: int,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    params = wf.fit_fold(rows, season, positions)
    targets = shadow.scheduled_targets(data.schedule, season, None, positions)
    extra = explore.compose(
        explore.make_extra(rows, season, positions),
        explore.make_opportunity_extra(rows, season, positions, data.volumes),
    )
    frozen = shadow.walk_targets(
        rows, targets, data.schedule, params, positions, wf.Settings(seed=seed), extra
    )
    forecasts = shadow.forecast_only(frozen, targets)
    labelled = (
        shadow.attach_labels(forecasts, labels)
        .join(data.oracle, on=["game_id", "offense", "position"], how="left")
        .with_columns(pl.lit(season).alias("season"))
    )
    return labelled, {
        "kDvp": {p: r5(params.k_dvp[p]) for p in positions},
        "slopeDvp": {p: r5(params.slope_dvp[p]) for p in positions},
    }


def _metrics(frame: pl.DataFrame, positions: list[str], block: str, seed: int) -> dict[str, Any]:
    valid = frame.filter(pl.col("label_status") == "valid")
    variants = [c for c in valid.columns if c.startswith("b0") and c not in ("b00", "b00_nontd")]
    variants += ["oracle"]
    return {
        p: wf.metrics(
            valid.filter(pl.col("position") == p), variants, block=block, reps=50, seed=seed
        )
        for p in positions
    }


def e2(scenario: str, rep: int) -> dict[str, Any]:
    started = time.time()
    sc = sim.SCENARIOS[scenario]
    s_data, s_walk, _, s_boot = seeds("E2", scenario, rep)
    data = sim.generate(sc, np.random.default_rng(s_data))
    rows = wf.prepare(data.observations)
    labels = data.observations
    positions = list(sc.positions)
    walk_seed = int(s_walk.generate_state(1)[0] % 2**31)
    boot_seed = int(s_boot.generate_state(1)[0] % 2**31)
    stages: dict[str, pl.DataFrame] = {}
    params: dict[str, Any] = {}
    for name, seasons in (("development", DEV), ("validation", VAL), ("holdout", HOLD)):
        parts = []
        for season in seasons:
            frame, fold = _stage(data, rows, labels, season, positions, walk_seed)
            parts.append(frame)
            params[str(season)] = fold
        stages[name] = pl.concat(parts, how="diagonal_relaxed")
    dev = _metrics(stages["development"], positions, "season", boot_seed)
    val = _metrics(stages["validation"], positions, "week", boot_seed)
    hold = _metrics(stages["holdout"], positions, "week", boot_seed)
    selection = frozen_cli()._select(dev, positions, {"practical_minimum_relative_rmse": MINIMUM})
    out: dict[str, Any] = {"rep": rep, "positions": {}, "params": params}
    for p in positions:
        chosen = selection["positions"][p]
        best = chosen["bestDvp"]
        decision = wf.decide(
            chosen["candidate"],
            chosen["bestRelativeDelta"],
            val[p][best]["relativeDelta"],
            hold[p][best]["relativeDelta"],
            MINIMUM,
        )

        def rel(m: dict[str, Any]) -> dict[str, Any]:
            return {
                v: r5(x["relativeDelta"])
                for v, x in m.items()
                if isinstance(x, dict) and "relativeDelta" in x
            }

        out["positions"][p] = {
            "selection": {
                k: chosen[k]
                for k in ("bestDvp", "candidate", "b04Selected", "b05Selected", "bestRelativeDelta")
            },
            "label": decision["label"],
            "development": rel(dev[p]),
            "validation": rel(val[p]),
            "holdout": rel(hold[p]),
            "b00Rmse": {"development": dev[p]["b00"]["rmse"] if "b00" in dev[p] else None},
        }
    if "DST" in positions:
        chosen = selection["positions"]["DST"]
        model = chosen["bestDvp"] if chosen["candidate"] != "b00" else "b06"
        periods = {}
        for name, frame in stages.items():
            table = decisions.units(frame, labels, ("b00", model))
            pairs = decisions.pairs(table, ("b00", model), "b00")
            periods[name] = decisions.metrics(
                table,
                pairs,
                "b00",
                model,
                close=SITSTART_CLOSE,
                pool=SITSTART_POOL,
                top=SITSTART_TOP,
                reps=50,
                seed=boot_seed,
            )
        label, _ = decisions.decide(periods, MINIMUM_PP)
        out["phaseC"] = {
            "model": model,
            "label": label,
            "periods": {
                k: {
                    "deltaPp": r5(v["deltaPp"]),
                    "points": r5(v["pointsFromChanges"]["total"]),
                    "pairs": v["pairs"],
                }
                for k, v in periods.items()
            },
        }
    out["seconds"] = round(time.time() - started, 2)
    return out


# --- E3: small-sample league-constrained evaluation (SIM-17, SIM-18) ------------------------------

LEAGUE_CASES: dict[str, dict[str, Any]] = {
    "SIM-17-null": {"extra": 0.0},
    "SIM-17-alt": {"extra": 0.6},
    "SIM-18-null": {"extra": 0.0, "near": 0.97},
    "SIM-18-alt": {"extra": 0.6, "near": 0.97},
}


def _league_week(
    rng: np.random.Generator, case: dict[str, Any], holdings: dict[str, list[str]], free: list[str]
) -> dict[str, Any]:
    units = sorted({u for v in holdings.values() for u in v} | set(free))
    z = rng.normal(0, 1, len(units))  # the predictable part of each unit's points
    y = 6 + 6 * (0.25 * z + math.sqrt(1 - 0.25**2) * rng.normal(0, 1, len(units)))
    b00 = z + rng.normal(0, 1.5, len(units))
    # B06 shares B00's view ("near" sets how often they agree) and may add information.
    near = case.get("near", 0.85)
    b06 = near * b00 + math.sqrt(1 - near**2) * rng.normal(0, 1.5, len(units)) + case["extra"] * z
    return {
        "points": dict(zip(units, y.tolist(), strict=True)),
        "forecasts": {
            "b00": dict(zip(units, b00.tolist(), strict=True)),
            "b06": dict(zip(units, b06.tolist(), strict=True)),
        },
        "z": dict(zip(units, z.tolist(), strict=True)),
    }


def e3(scenario: str, rep: int) -> dict[str, Any]:
    case = LEAGUE_CASES[scenario]
    s_data, _, s_perm, s_boot = seeds("E3", scenario, rep)
    rng = np.random.default_rng(s_data)
    units = [f"U{i:02d}" for i in range(32)]
    rows: dict[str, list[dict[str, Any]]] = {"start": [], "stream": []}
    for week in range(1, 12):
        order = rng.permutation(units).tolist()
        holdings = {f"t{t}": order[2 * t : 2 * t + (2 if t < 5 else 1)] for t in range(8)}
        held = {u for v in holdings.values() for u in v}
        free = [u for u in order if u not in held][:18]
        w = _league_week(rng, case, holdings, free)
        playing = set(w["points"])
        for kind, pool in (("start", []), ("stream", free)):
            rows[kind] += league.decide(
                week,
                holdings,
                pool,
                playing,
                w["forecasts"],
                w["points"],
                league.START if kind == "start" else league.STREAM,
            )
    out: dict[str, Any] = {"rep": rep}
    boot = int(s_boot.generate_state(1)[0] % 2**31)
    for kind, decided in rows.items():
        table = pl.DataFrame(decided)
        allw = league.summarize(table, "b00", "b06", 1000, boot, weeks=list(range(1, 12)))
        changed = league.summarize(table, "b00", "b06", 1000, boot, blocks=league.CHANGED_WEEKS)
        # A naive decision-level bootstrap (ignores weeks), for comparison only.
        gain = (table.get_column("points_b06") - table.get_column("points_b00")).to_numpy()
        prng = np.random.default_rng(s_perm)
        naive = [float(gain[prng.integers(0, gain.size, gain.size)].sum()) for _ in range(1000)]
        out[kind] = {
            "decisions": allw["decisions"],
            "changed": allw["changed"],
            "points": allw["pointsFromChanges"],
            "zeroChangeWeeks": len(allw.get("zeroChangeWeeks", [])),
            "allWeeks95": allw.get("pointsFromChanges95"),
            "changedWeeks95": changed.get("pointsFromChanges95"),
            "naive95": [round(float(q), 2) for q in np.quantile(naive, [0.025, 0.975])],
        }
    return out


def truth_chunk(scenario: str, start: int, count: int) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {"start": [], "stream": []}
    for rep in range(start, start + count):
        totals = e3_points_only(scenario, rep)
        for k in out:
            out[k].append(totals[k])
    return out


def league_truth(reps: int, workers: int) -> dict[str, Any]:
    """The expected cumulative B06-minus-B00 points per season for each league case, from a large
    simulation on its own random stream (the truth E3's intervals should cover)."""
    spawn = multiprocessing.get_context("spawn")
    chunk = 500
    results: dict[str, dict[str, list[float]]] = {
        s: {"start": [], "stream": []} for s in LEAGUE_CASES
    }
    with ProcessPoolExecutor(max_workers=workers, mp_context=spawn) as pool:
        futures = {
            pool.submit(truth_chunk, s, start, chunk): s
            for s in LEAGUE_CASES
            for start in range(0, reps, chunk)
        }
        for future in as_completed(futures):
            part = future.result()
            for k in ("start", "stream"):
                results[futures[future]][k] += part[k]
    return {
        s: {k: float(np.mean(v)) for k, v in r.items()}
        | {f"{k}Se": float(np.std(v) / math.sqrt(len(v))) for k, v in r.items()}
        | {"reps": len(r["start"])}
        for s, r in results.items()
    }


def e3_points_only(scenario: str, rep: int) -> dict[str, float]:
    case = LEAGUE_CASES[scenario]
    rng = np.random.default_rng(
        np.random.SeedSequence(MASTER + 7, spawn_key=(scenario_key(scenario), rep))
    )
    units = [f"U{i:02d}" for i in range(32)]
    totals = {"start": 0.0, "stream": 0.0}
    for week in range(1, 12):
        order = rng.permutation(units).tolist()
        holdings = {f"t{t}": order[2 * t : 2 * t + (2 if t < 5 else 1)] for t in range(8)}
        held = {u for v in holdings.values() for u in v}
        free = [u for u in order if u not in held][:18]
        w = _league_week(rng, case, holdings, free)
        for kind, pool in (("start", []), ("stream", free)):
            for r in league.decide(
                week,
                holdings,
                pool,
                set(w["points"]),
                w["forecasts"],
                w["points"],
                league.START if kind == "start" else league.STREAM,
            ):
                totals[kind] += r["points_b06"] - r["points_b00"]
    return totals


# --- U: bootstrap interval coverage of walkforward.metrics ----------------------------------------

U_CONDITIONS: dict[str, dict[str, Any]] = {
    "independent": {"block": "week"},
    "weekShock": {"block": "week", "week_sd": 1.0},
    "weekShockRowBlocks": {"block": "row", "week_sd": 1.0},
    "season7": {"block": "season", "seasons": 7, "season_var": True},
    "season5": {"block": "season", "seasons": 5, "season_var": True},
    "season3": {"block": "season", "seasons": 3, "season_var": True},
    "sharedGame": {"block": "week", "game_sd": 1.5},
    "temporalAR": {"block": "week", "week_sd": 1.0, "ar": 0.6},
    "unequalExposure": {"block": "week", "unequal": True},
}
U_SIGNAL, U_NOISE, U_C = 1.0, 4.0, 0.8


def u(scenario: str, rep: int) -> dict[str, Any]:
    cond = U_CONDITIONS[scenario]
    s_data, _, _, s_boot = seeds("U", scenario, rep)
    rng = np.random.default_rng(s_data)
    seasons = cond.get("seasons", 1)
    frames = []
    for season in range(seasons):
        scale = rng.uniform(0.25, 1.75) if cond.get("season_var") else 1.0
        shock = 0.0
        for week in range(1, 18):
            n = int(rng.integers(20, 180)) if cond.get("unequal") else 100
            shock = (
                cond.get("ar", 0.0) * shock + math.sqrt(1 - cond.get("ar", 0.0) ** 2) * rng.normal()
            )
            s = rng.normal(0, U_SIGNAL * math.sqrt(scale), n)
            e = rng.normal(0, U_NOISE, n) + cond.get("week_sd", 0.0) * shock
            if cond.get("game_sd"):
                g = np.repeat(rng.normal(0, cond["game_sd"], n // 2 + 1), 2)[:n]
                e = e + g
            y = s + e
            frames.append(
                pl.DataFrame(
                    {
                        "season": season,
                        "week": week,
                        "points": y,
                        "b00": np.zeros(n),
                        "b0x": U_C * s,
                    }
                )
            )
    joined = pl.concat(frames).with_row_index("row")
    # Truth: the population RMSE difference under the generating distribution.
    noise_var = U_NOISE**2 + cond.get("week_sd", 0.0) ** 2 + cond.get("game_sd", 0.0) ** 2
    signal_var = U_SIGNAL**2  # E[scale] = 1 when seasons vary
    truth = math.sqrt((1 - U_C) ** 2 * signal_var + noise_var) - math.sqrt(signal_var + noise_var)
    block = cond["block"]
    m = wf.metrics(
        joined, ["b0x"], block=block, reps=1000, seed=int(s_boot.generate_state(1)[0] % 2**31)
    )
    low, high = m["b0x"]["delta95"]
    return {
        "rep": rep,
        "truth": truth,
        "estimate": m["b0x"]["deltaRmse"],
        "low": low,
        "high": high,
        "covered": bool(low <= truth <= high),
        "blocks": m["blocks"],
    }


# --- running ---------------------------------------------------------------------------------------

RUNNERS: dict[str, Callable[[str, int], dict[str, Any]]] = {"E1": e1, "E2": e2, "E3": e3, "U": u}


def _one(experiment: str, scenario: str, rep: int) -> dict[str, Any]:
    try:
        return RUNNERS[experiment](scenario, rep)
    except Exception as error:  # noqa: BLE001 - every failure is recorded, never dropped
        return {
            "rep": rep,
            "failed": f"{type(error).__name__}: {error}",
            "trace": traceback.format_exc()[-800:],
        }


def run(experiment: str, scenarios: list[str], reps: int, workers: int) -> None:
    folder = OUT / experiment
    folder.mkdir(parents=True, exist_ok=True)
    jobs = []
    for scenario in scenarios:
        path = folder / f"{scenario}.jsonl"
        done = set()
        if path.exists():
            done = {
                json.loads(line)["rep"] for line in path.read_text().splitlines() if line.strip()
            }
        jobs += [(scenario, rep) for rep in range(reps) if rep not in done]
    print(json.dumps({"experiment": experiment, "jobs": len(jobs)}), flush=True)
    handles = {s: (folder / f"{s}.jsonl").open("a") for s in scenarios}
    started = time.time()
    spawn = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=spawn) as pool:
        futures = {pool.submit(_one, experiment, s, r): s for s, r in jobs}
        for i, future in enumerate(as_completed(futures), start=1):
            scenario = futures[future]
            result = future.result()
            handles[scenario].write(json.dumps(result, default=str) + "\n")
            handles[scenario].flush()
            if i % 50 == 0:
                print(
                    json.dumps(
                        {
                            "done": i,
                            "of": len(jobs),
                            "minutes": round((time.time() - started) / 60, 1),
                        }
                    ),
                    flush=True,
                )
    for h in handles.values():
        h.close()


def pilot(workers: int) -> None:
    config = json.loads(CONFIG.read_text())
    scenarios = config["experiments"]["E2"]["scenarios"]
    started = time.time()
    spawn = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=spawn) as pool:
        futures = [pool.submit(_one, "E2", s, 10_000 + r) for s in scenarios for r in range(5)]
        results = [f.result() for f in futures]
    seconds = [float(r["seconds"]) for r in results if "seconds" in r]
    failed = [r["failed"] for r in results if "failed" in r]
    per_rep = float(np.mean(seconds)) if seconds else float("nan")
    planned = per_rep * config["experiments"]["E2"]["reps"] * len(scenarios) / workers / 3600
    print(
        json.dumps(
            {
                "wallMinutes": round((time.time() - started) / 60, 1),
                "secondsPerRep": round(per_rep, 2),
                "plannedE2Hours": round(planned, 2),
                "failed": failed[:3],
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    r = commands.add_parser("run")
    r.add_argument("--experiment", required=True, choices=EXPERIMENTS)
    r.add_argument("--scenarios", required=True)
    r.add_argument("--reps", type=int, required=True)
    r.add_argument("--workers", type=int, default=8)
    p = commands.add_parser("pilot")
    p.add_argument("--workers", type=int, default=8)
    t = commands.add_parser("truth")
    t.add_argument("--reps", type=int, default=20000)
    t.add_argument("--workers", type=int, default=8)
    commands.add_parser("summarize")
    args = parser.parse_args()
    if args.command == "run":
        run(args.experiment, args.scenarios.split(","), args.reps, args.workers)
    elif args.command == "pilot":
        pilot(args.workers)
    elif args.command == "truth":
        out = league_truth(args.reps, args.workers)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "league-truth.json").write_text(json.dumps(out, indent=1) + "\n")
        print(json.dumps(out))
    else:
        spec = importlib.util.spec_from_file_location(
            "dvp_simulate_summary", ROOT / "scripts/model/dvp_simulate_summary.py"
        )
        assert spec is not None and spec.loader is not None
        summary = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(summary)
        summary.main(ROOT, CONFIG, OUT)


if __name__ == "__main__":
    main()
