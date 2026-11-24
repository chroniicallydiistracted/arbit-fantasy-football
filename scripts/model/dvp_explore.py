"""M3-3 DvP exploratory run v2: decoupled historical stages and new estimators (config/dvp/explore-v2.json).

Owner audit AUD-05 (remediation 5) and AUD-03 (remediation 3). EXPLORATORY: nothing here changes
the frozen candidates or the 2026 confirmation.

  forecast --stage S   Scheduled targets -> point-in-time features (row contract checked) ->
                       forecast-only outputs (frozen walk steps + exploratory estimators) ->
                       written once with hashes. No label is read.
  evaluate             Checks every stage's forecast hashes, reads the labels, joins them without
                       dropping a target, reports coverage and metrics, and compares the frozen
                       variants with the committed v1 receipts. Writes docs/research/dvp/explore-v2.json.

  POLARS_MAX_THREADS=2 ARBIT_NFLVERSE_PATH=<main>/data/nflverse uv run --env-file <main>/.env.local \\
    python scripts/model/dvp_explore.py --main <main> forecast --stage development
"""

import argparse
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
from arbit_model.dvp import contract, explore, shadow
from arbit_model.dvp import observations as obs
from arbit_model.dvp import walkforward as wf

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/dvp/explore-v2.json"
FORMAT = "arbit-dvp-m3-3-explore-v2"
STAGES = ("development", "validation", "holdout")
CONTROLS = ("b09_shuffle", "b09_noise", "b09_lastopp", "b00_nontd")


def harness() -> Any:
    """The prospective harness, for its verified loaders (frozen hashes, audit run, store)."""
    spec = importlib.util.spec_from_file_location(
        "dvp_prospective", ROOT / "scripts/model/dvp_prospective.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dvp_prospective"] = module
    spec.loader.exec_module(module)
    return module


def run_folder(args: argparse.Namespace) -> Path:
    root: Path = args.out or args.main / "artifacts/dvp/explore-v2"
    return Path(root) / str(args.run)


def forecast(args: argparse.Namespace) -> None:
    h = harness()
    fz = h.load_frozen()
    seasons: list[int] = fz.backtest["stages"][args.stage]
    folder = run_folder(args)
    target = folder / f"forecasts-{args.stage}.parquet"
    if target.exists():
        raise SystemExit(f"{target} exists; forecasts are written once")
    folder.mkdir(parents=True, exist_ok=True)
    observations, schedule, lineage = h.history(fz, args.main)
    rows = shadow.prepare_checked(observations, fz.base["expected_scoring"])
    frames, folds = [], {}
    for season in seasons:
        params = wf.fit_fold(rows, season, fz.positions)
        targets = shadow.scheduled_targets(schedule, season, None, fz.positions)
        extra = explore.make_extra(rows, season, fz.positions)
        frozen = shadow.walk_targets(
            rows, targets, schedule, params, fz.positions, fz.settings(), extra=extra
        )
        frames.append(shadow.forecast_only(frozen, targets))
        folds[str(season)] = params.summary() | {
            "kSplitHalf": explore.k_summary(extra.split_half_k)  # type: ignore[attr-defined]
        }
    out = pl.concat(frames, how="vertical_relaxed").sort(list(shadow.KEYS))
    temporary = target.with_suffix(".parquet.tmp")
    out.write_parquet(temporary)
    os.rename(temporary, target)
    target.chmod(0o444)
    manifest = {
        "format": FORMAT + "-forecasts",
        "stage": args.stage,
        "seasons": seasons,
        "generatedAt": datetime.now(UTC).isoformat(),
        "code": h.code_version(),
        "config": {"path": "config/dvp/explore-v2.json", "sha256": h.sha256(CONFIG)},
        "frozen": fz.verification,
        "history": lineage,
        "labelsRead": False,
        "rows": out.height,
        "columns": out.columns,
        "sha256": h.sha256(target),
        "contentSha256": shadow.content_sha256(out),
        "folds": folds,
    }
    (folder / f"manifest-{args.stage}.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    )
    print(f"{args.stage}: {out.height} forecasts over {seasons} written to {target}")


def _variants(frame: pl.DataFrame) -> list[str]:
    return [c for c in shadow.forecast_columns(frame) if c not in CONTROLS]


def evaluate(args: argparse.Namespace) -> None:
    h = harness()
    fz = h.load_frozen()
    folder = run_folder(args)
    observations, _, lineage = h.history(fz, args.main)
    labels = contract.enforce(observations, fz.base["expected_scoring"])  # read only here
    reps, seed = fz.base["bootstrap_replicates"], fz.base["random_seed"]
    out: dict[str, Any] = {}
    for stage in STAGES:
        manifest = json.loads((folder / f"manifest-{stage}.json").read_text())
        path = folder / f"forecasts-{stage}.parquet"
        if h.sha256(path) != manifest["sha256"]:
            raise SystemExit(f"{path} does not match its manifest")
        forecasts = pl.read_parquet(path)
        labelled = shadow.attach_labels(forecasts, labels)
        valid = labelled.filter(pl.col("label_status") == obs.VALID)
        block = "season" if len(manifest["seasons"]) > 1 else "week"
        names = _variants(forecasts)
        committed = json.loads((ROOT / f"docs/research/dvp/backtest-{stage}.json").read_text())
        per_position: dict[str, Any] = {}
        reproduction: dict[str, Any] = {}
        for position in fz.positions:
            part = valid.filter(pl.col("position") == position)
            m = wf.metrics(part, names, block=block, reps=reps, seed=seed)
            v1 = committed["results"][position]
            differ = {
                name: {
                    k: [v1[name][k], m[name][k]]
                    for k in ("rmse", "mae", "meanError", "deltaRmse", "delta95")
                    if v1[name][k] != m[name][k]
                }
                for name in names
                if name in v1
            }
            reproduction[position] = {
                "rowsV1": v1["rows"],
                "rowsV2": m["rows"],
                "differences": {k: v for k, v in differ.items() if v},
            }
            base = m["b00"]["rmse"]
            per_position[position] = {
                "rows": m["rows"],
                "blocks": m["blocks"],
                "estimators": {
                    name: {
                        "relativeDelta": m[name]["relativeDelta"],
                        "delta95": m[name]["delta95"],
                        "rmse": m[name]["rmse"],
                        "mae": m[name]["mae"],
                    }
                    for name in names
                },
                "b00Rmse": base,
                "exploratoryAgainst": {
                    name: {
                        ref: round((m[name]["rmse"] - m[ref]["rmse"]) / base, 5)
                        for ref in ("b03", "b04_k8", "b04_k16", "b05_h4", "b05_h8", "b06")
                        if ref in m
                    }
                    for name in explore.COLUMNS
                },
            }
        out[stage] = {
            "seasons": manifest["seasons"],
            "forecastsSha256": manifest["sha256"],
            "coverage": shadow.coverage(labelled),
            "positions": per_position,
            "reproductionOfV1": reproduction,
            "kByFold": {
                s: {"reml": f["kDvp"], "splitHalf": f["kSplitHalf"]}
                for s, f in manifest["folds"].items()
            },
        }
    reproduced = all(
        not v["differences"] and v["rowsV1"] == v["rowsV2"]
        for stage in out.values()
        for v in stage["reproductionOfV1"].values()
    )
    receipt = {
        "format": FORMAT + "-results",
        "generatedAt": datetime.now(UTC).isoformat(),
        "code": h.code_version(),
        "classification": "EXPLORATORY (estimators added after the 2025 holdout was inspected)",
        "config": {"path": "config/dvp/explore-v2.json", "sha256": h.sha256(CONFIG)},
        "run": args.run,
        "frozen": fz.verification,
        "history": lineage,
        "v1ReproducedOnValidRows": reproduced,
        "stages": out,
        "decision": "none: descriptive; never changes frozen candidates",
        "forbidden_vendor_projection_dependencies": 0,
        "write_to_production": False,
    }
    target = Path(args.receipts) / "explore-v2.json"
    target.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({"v1ReproducedOnValidRows": reproduced, "receipt": str(target)}))
    if not reproduced:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--main", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, help="default: <main>/artifacts/dvp/explore-v2")
    parser.add_argument("--run", required=True, help="one run id for all three stages and evaluate")
    commands = parser.add_subparsers(dest="command", required=True)
    f = commands.add_parser("forecast")
    f.add_argument("--stage", choices=STAGES, required=True)
    e = commands.add_parser("evaluate")
    e.add_argument("--receipts", type=Path, default=ROOT / "docs/research/dvp")
    args = parser.parse_args()
    args.main = args.main.resolve()
    {"forecast": forecast, "evaluate": evaluate}[args.command](args)


if __name__ == "__main__":
    main()
