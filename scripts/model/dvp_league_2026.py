"""C05L-2026-EXP: exploratory league-constrained D/ST decisions on completed 2026 weeks.

Owner audit Phase B (B6). The rule is config/dvp/league-2026-exploratory.json, committed before any
result. EXPLORATORY and RETROSPECTIVE: weeks 1-11 were known before the prospective freeze, and
these forecasts are reconstructed now with the frozen method. Never a confirmation.

  POLARS_MAX_THREADS=2 ARBIT_NFLVERSE_PATH=<main>/data/nflverse uv run --env-file <main>/.env.local \\
    python scripts/model/dvp_league_2026.py --main <main>

Read-only against the database. Writes docs/research/dvp/league-2026-exploratory.json.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
from arbit_model import ffa_history as fh
from arbit_model.dvp import league, shadow
from arbit_model.dvp import walkforward as wf
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/dvp/league-2026-exploratory.json"
SEASON = 2026


def script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/model/{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def forecasts(
    h: Any, fz: Any, main: Path, weeks: list[int]
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    """The frozen B00..B09 for the weeks, from the archived 2026 inputs, and the 2026 labels."""
    archive = main / "artifacts/dvp/prospective/2026/week-12"
    manifest = json.loads((archive / "manifest.json").read_text())
    inputs = archive / "inputs"
    for name, digest in manifest["inputs"].items():
        if sha256(inputs / name) != digest:
            raise SystemExit(f"archived input {name} does not match the week-12 manifest")
    season_rows = pl.read_parquet(inputs / "observations-season.parquet")
    season_schedule = pl.read_parquet(inputs / "schedule-season.parquet")
    past, past_schedule, lineage = h.history(fz, main)
    rows, schedule = h.combine(past, past_schedule, season_rows, season_schedule)
    prepared = shadow.prepare_checked(rows, fz.base["expected_scoring"])
    params = wf.fit_fold(prepared, SEASON, fz.positions)
    targets = shadow.scheduled_targets(schedule, SEASON, range(1, max(weeks) + 1), fz.positions)
    frozen = shadow.walk_targets(prepared, targets, schedule, params, fz.positions, fz.settings())
    out = shadow.forecast_only(frozen, targets).filter(pl.col("week").is_in(weeks))
    return (
        out,
        season_rows,
        {
            "weekTwelveManifest": manifest["forecasts"]["contentSha256"],
            "inputs": manifest["inputs"],
            "seasonTargetsIndex": manifest["lineage"]["season"]["targetsIndex"],
            "history": lineage,
            "parameters": params.summary(),
            "forecastsContentSha256": shadow.content_sha256(out),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--main", type=Path, default=ROOT)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "docs/research/dvp/league-2026-exploratory.json"
    )
    args = parser.parse_args()
    main_root = args.main.resolve()
    config = json.loads(CONFIG.read_text())
    weeks: list[int] = config["weeks"]
    base, candidate = config["models"]["baseline"], config["models"]["candidate"]
    h = script("dvp_prospective")
    inventory = script("ffa_2026_inventory")
    fz = h.load_frozen()
    frame, season_rows, lineage = forecasts(h, fz, main_root, weeks)

    engine = create_engine(
        os.environ["ARBIT_DATABASE_URL"],
        hide_parameters=True,
        execution_options={"postgresql_readonly": True},
    )
    data = inventory.load(engine)
    document, rules = data["current"].payload, data["current"].rules
    code = {
        r["entity"]: inventory.ESPN_TO_FRANCHISE.get(r["abbreviation"], r["abbreviation"])
        for r in data["dst"]
    }
    draft = [(p["player_id"], p["team_id"]) for p in document["draft_picks"]]
    all_moves = fh.moves(data["transactions"])
    latest = {c["scoring_period"]: c["id"] for c in data["captures"]}
    captured = {
        p: {(e["player"], e["team"]) for e in data["entries"] if e["capture_id"] == cid}
        for p, cid in latest.items()
    }
    verification = fh.verify_periods(draft, all_moves, captured)
    if not all(verification[w]["verified"] for w in weeks):
        raise SystemExit("the ownership replay does not reproduce every captured roster; stopping")
    hold = timedelta(hours=int(rules["waiver_hours"]))
    schedule = pl.read_parquet(
        main_root / "artifacts/dvp/prospective/2026/week-12/inputs/schedule-season.parquet"
    )
    cut = inventory.cutoffs(schedule)

    dst = frame.filter(pl.col("position") == "DST")
    labels = season_rows.filter((pl.col("position") == "DST") & (pl.col("status") == "valid"))
    rows: dict[str, list[dict[str, Any]]] = {
        "start": [],
        "stream": [],
        "streamIncludingWaivers": [],
    }
    availability_counts: dict[str, Any] = {}
    lineup_units: list[dict[str, Any]] = []
    reconciliation: Counter[str] = Counter()
    for week in weeks:
        week_forecasts = dst.filter(pl.col("week") == week)
        playing = set(week_forecasts.get_column("defense").to_list())
        model_forecasts = {
            m: dict(
                zip(week_forecasts.get_column("defense"), week_forecasts.get_column(m), strict=True)
            )
            for m in (base, candidate)
        }
        points = dict(
            zip(
                labels.filter(pl.col("week") == week).get_column("defense"),
                labels.filter(pl.col("week") == week).get_column("points"),
                strict=True,
            )
        )
        rebuilt = fh.replay(draft, all_moves, until=cut[week])
        states = fh.availability(code, rebuilt.owners, all_moves, cut[week], hold)
        holdings: dict[str, list[str]] = {}
        for entity, state in states.items():
            if state.startswith("OWNED:"):
                holdings.setdefault(state.split(":", 1)[1], []).append(code[entity])
        free = [code[e] for e, s in states.items() if s == fh.FREE_AGENT]
        waiver_wire = [code[e] for e, s in states.items() if s in (fh.WAIVERS, fh.UNCERTAIN)]
        availability_counts[str(week)] = {
            "cutoff": cut[week].isoformat(),
            "owned": sum(len(v) for v in holdings.values()),
            "freeAgents": len(free),
            "waiverWire": len(waiver_wire),
            "byes": sorted(set(code.values()) - playing),
        }
        for team in document["teams"]:
            holdings.setdefault(team["id"], [])
        rows["start"] += league.decide(
            week, holdings, free, playing, model_forecasts, points, league.START
        )
        rows["stream"] += league.decide(
            week, holdings, free, playing, model_forecasts, points, league.STREAM
        )
        rows["streamIncludingWaivers"] += league.decide(
            week, holdings, free + waiver_wire, playing, model_forecasts, points, league.STREAM
        )
        # The captured lineup's D/STs: managers' starts and ESPN's official points.
        for e in data["entries"]:
            if e["capture_id"] != latest[week] or e["position"] != "DST":
                continue
            unit = code.get(e["player"])
            espn = None if e["official_points"] is None else float(e["official_points"])
            lineup_units.append(
                {"week": week, "team": e["team"], "unit": unit, "slot": e["slot"], "points": espn}
            )
            if unit in points and espn is not None:
                reconciliation["equal" if abs(points[unit] - espn) < 0.005 else "differ"] += 1
            elif unit not in playing:
                reconciliation["byeNoGame"] += 1
            else:
                reconciliation["playedWithoutLabel"] += 1

    tables = {k: pl.DataFrame(v) for k, v in rows.items()}
    reps, seed = 2000, 1729
    results = {k: league.summarize(t, base, candidate, reps, seed) for k, t in tables.items()}
    lineups = pl.DataFrame(lineup_units)
    starts = tables["start"]
    manager: dict[str, Any] = {}
    if starts.height:
        started = lineups.filter(pl.col("slot") == "DST").select(
            "week",
            "team",
            pl.col("unit").alias("managerPick"),
            pl.col("points").alias("managerEspnPoints"),
        )
        joined = starts.join(started, on=["week", "team"], how="left")
        labelled = joined.filter(pl.col("labelled"))
        manager_points = [
            None
            if r["managerPick"] is None
            else dict(
                zip(
                    labels.filter(pl.col("week") == r["week"]).get_column("defense"),
                    labels.filter(pl.col("week") == r["week"]).get_column("points"),
                    strict=True,
                )
            ).get(r["managerPick"])
            for r in labelled.iter_rows(named=True)
        ]
        valid = [
            (p, r)
            for p, r in zip(manager_points, labelled.iter_rows(named=True), strict=True)
            if p is not None
        ]
        manager = {
            "startDecisionsWithManagerStart": len(valid),
            "managerPoints": round(sum(p for p, _ in valid), 2),
            "managerHitRate": round(
                sum(abs(r["best"] - p) < 1e-9 for p, r in valid) / len(valid), 4
            )
            if valid
            else None,
            "managerMeanRegret": round(sum(r["best"] - p for p, r in valid) / len(valid), 3)
            if valid
            else None,
            "agreesWith": {
                m: round(sum(r["managerPick"] == r[f"pick_{m}"] for _, r in valid) / len(valid), 4)
                if valid
                else None
                for m in (base, candidate)
            },
        }
    effects = (
        league.matchup_effects(starts, lineups, document["matchups"], base, candidate)
        if starts.height
        else {}
    )
    by_week = {
        k: {
            str(w): league.summarize(t.filter(pl.col("week") == w), base, candidate, 0, seed)
            for w in weeks
            if t.height and t.filter(pl.col("week") == w).height
        }
        for k, t in tables.items()
    }
    teams = len(document["teams"])
    receipt = {
        "format": "arbit-dvp-m3-3-league-2026-v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "code": h.code_version(),
        "config": {"path": "config/dvp/league-2026-exploratory.json", "sha256": sha256(CONFIG)},
        "classification": config["classification"],
        "frozen": fz.verification,
        "forecastLineage": lineage,
        "ownership": {
            "replayVerifiedForEveryWeek": True,
            "periods": {str(w): verification[w] for w in weeks},
            "availabilityAtCutoff": availability_counts,
        },
        "labels": {
            "source": "canonical FFA D/ST actuals (archived 2026 observations)",
            "espnOfficialAgainstCanonicalForLineupDst": dict(reconciliation),
        },
        "coverage": {
            "teamWeeks": teams * len(weeks),
            "startDecisions": tables["start"].height,
            "streamDecisions": tables["stream"].height,
        },
        "results": results,
        "byWeek": by_week,
        "managers": manager,
        "matchups": effects,
        "decisions": {k: t.to_dicts() for k, t in tables.items()},
        "decisionRule": "none: descriptive and exploratory",
        "forbidden_vendor_projection_dependencies": 0,
        "write_to_production": False,
    }
    args.out.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n")
    print(
        json.dumps(
            {
                k: {
                    x: v.get(x)
                    for x in (
                        "decisions",
                        "changed",
                        "pointsFromChanges",
                        "candidateRightWhenChanged",
                    )
                }
                for k, v in results.items()
            }
        )
    )


if __name__ == "__main__":
    main()
