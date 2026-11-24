"""M3-3 DvP exploratory runs: decoupled historical stages and new estimators.

`--config` names the version: config/dvp/explore-v2.json (owner audit AUD-05 and AUD-03: rolling
windows, split-half k) or config/dvp/explore-v3.json (adds AUD-02: opportunity volume and
efficiency). EXPLORATORY: nothing here changes the frozen candidates or the 2026 confirmation.

  opportunity          (v3) Admit the nflverse player and team statistics the FFA targets were
                       built from, build each cell's volume, reconcile, report coverage and the
                       volume and efficiency reliability. Written once to the run folder.

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

import numpy as np
import polars as pl
from arbit_model.dvp import contract, explore, shadow
from arbit_model.dvp import observations as obs
from arbit_model.dvp import walkforward as wf

ROOT = Path(__file__).resolve().parents[2]
FORMAT = "arbit-dvp-m3-3"
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


def config_of(args: argparse.Namespace) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(Path(args.config).read_text())
    return value


def run_folder(args: argparse.Namespace) -> Path:
    root: Path = args.out or args.main / "artifacts/dvp" / config_of(args)["version"]
    return Path(root) / str(args.run)


def uses_opportunity(args: argparse.Namespace) -> bool:
    return any(name in config_of(args)["estimators"] for name in explore.OPPORTUNITY_COLUMNS)


def opportunity_table(args: argparse.Namespace, h: Any) -> pl.DataFrame:
    folder = run_folder(args)
    manifest = json.loads((folder / "opportunity-manifest.json").read_text())
    path = folder / "opportunity.parquet"
    if h.sha256(path) != manifest["sha256"]:
        raise SystemExit(f"{path} does not match its manifest")
    return pl.read_parquet(path)


def opportunity(args: argparse.Namespace) -> None:
    """Admit the statistics, build volumes, reconcile, report coverage and reliability."""
    import pyarrow.parquet as pq  # type: ignore[import-untyped]
    from arbit_data.db import UnitOfWork
    from arbit_data.nflverse.objects import ObjectStore
    from arbit_model.dvp import opportunity as op
    from arbit_model.inputs import NflverseTables

    h = harness()
    fz = h.load_frozen()
    config = config_of(args)
    folder = run_folder(args)
    target = folder / "opportunity.parquet"
    if target.exists():
        raise SystemExit(f"{target} exists; written once")
    folder.mkdir(parents=True, exist_ok=True)
    observations, _, lineage = h.history(fz, args.main)
    observations = contract.enforce(observations, fz.base["expected_scoring"])
    store_root = args.main / "data/model"
    index = fz.cli.load_index(store_root, fz.base["targets_index"])
    nflverse = Path(os.environ.get("ARBIT_NFLVERSE_PATH", args.main / "data/nflverse"))
    engine = h.engine_readonly()
    players: list[pl.DataFrame] = []
    teams: list[pl.DataFrame] = []
    admissions: list[dict[str, Any]] = []
    for season in fz.base["seasons"]:
        manifest = fz.cli.season_manifest(store_root, index, season)
        for key, source_id, bucket in (
            (f"stats_player/stats_player_week_{season}", "nflverse.stats_player", players),
            (f"stats_team/stats_team_week_{season}", "nflverse.stats_team", teams),
        ):
            pin = manifest["inputs"][key]
            tables = NflverseTables(
                UnitOfWork(engine), ObjectStore(nflverse / "objects"), {key: pin}
            )
            found = tables.manifest(key)
            assert found is not None
            path = tables.store.verify(str(found["parquet_hash"])).path  # bytes re-hashed
            spec = op.SOURCES_V2[source_id]
            admitted = op.admit_realized(
                pl.read_parquet(path, columns=list(spec.used)),
                source_id,
                ancestry=f"nflverse manifest {pin} ({key}), the file the {season} FFA targets "
                f"were built from (targets index {fz.base['targets_index'][:12]})",
                schema=pq.read_schema(path).names,
            )
            bucket.append(admitted.frame)
            admissions.append(admitted.record())
    player_frame = pl.concat(players, how="vertical_relaxed")
    team_frame = pl.concat(teams, how="vertical_relaxed")
    table = op.cells(observations, player_frame, team_frame)
    temporary = target.with_suffix(".parquet.tmp")
    table.write_parquet(temporary)
    os.rename(temporary, target)
    target.chmod(0o444)
    reps = config["reliabilityReplicates"]
    manifest_out = {
        "format": FORMAT + f"-{config['version']}-opportunity",
        "generatedAt": datetime.now(UTC).isoformat(),
        "code": h.code_version(),
        "config": {
            "path": str(Path(args.config).resolve().relative_to(ROOT)),
            "sha256": h.sha256(Path(args.config)),
        },
        "frozen": fz.verification,
        "history": lineage,
        "admissions": admissions,
        "reconciliation": op.reconcile(player_frame, team_frame),
        "coverage": op.coverage(table),
        "reliability": op.reliability(table, fz.positions, reps, fz.base["random_seed"]),
        "rows": table.height,
        "sha256": h.sha256(target),
    }
    (folder / "opportunity-manifest.json").write_text(
        json.dumps(manifest_out, indent=1, sort_keys=True, default=str) + "\n"
    )
    print(
        f"opportunity: {table.height} cells; reconciliation {json.dumps(manifest_out['reconciliation'])}"
    )


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
    volumes = (
        opportunity_table(args, h).filter(pl.col("volume_status") != "missing")
        if uses_opportunity(args)
        else None
    )
    frames, folds = [], {}
    for season in seasons:
        params = wf.fit_fold(rows, season, fz.positions)
        targets = shadow.scheduled_targets(schedule, season, None, fz.positions)
        extra = explore.make_extra(rows, season, fz.positions)
        hooks: list[Any] = [extra]
        fold: dict[str, Any] = {
            "kSplitHalf": explore.k_summary(extra.split_half_k)  # type: ignore[attr-defined]
        }
        if volumes is not None:
            opportunity_hook = explore.make_opportunity_extra(rows, season, fz.positions, volumes)
            hooks.append(opportunity_hook)
            fold["opportunity"] = {
                p: {k: (None if v == float("inf") else round(v, 4)) for k, v in values.items()}
                for p, values in opportunity_hook.parameters.items()  # type: ignore[attr-defined]
            }
        frozen = shadow.walk_targets(
            rows,
            targets,
            schedule,
            params,
            fz.positions,
            fz.settings(),
            extra=explore.compose(*hooks),
        )
        frames.append(shadow.forecast_only(frozen, targets))
        folds[str(season)] = params.summary() | fold
    out = pl.concat(frames, how="vertical_relaxed").sort(list(shadow.KEYS))
    temporary = target.with_suffix(".parquet.tmp")
    out.write_parquet(temporary)
    os.rename(temporary, target)
    target.chmod(0o444)
    manifest = {
        "format": FORMAT + f"-{config_of(args)['version']}-forecasts",
        "stage": args.stage,
        "seasons": seasons,
        "generatedAt": datetime.now(UTC).isoformat(),
        "code": h.code_version(),
        "config": {"path": args.config_name, "sha256": h.sha256(Path(args.config))},
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


def _term_correlations(part: pl.DataFrame) -> dict[str, float | None]:
    """How much the exploratory terms duplicate each other and the frozen DvP term (B03)."""
    terms = {
        name: (part.get_column(name) - part.get_column("b00")).to_numpy()
        for name in ("b03", "b07", "b07v", "b07e")
        if name in part.columns
    }
    out: dict[str, float | None] = {}
    names = sorted(terms)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            x, y = terms[a], terms[b]
            ok = x.std() > 0 and y.std() > 0
            out[f"{a}~{b}"] = round(float(np.corrcoef(x, y)[0, 1]), 4) if ok else None
    return out


def _opportunity_summary(folder: Path) -> dict[str, Any]:
    manifest = json.loads((folder / "opportunity-manifest.json").read_text())
    return {
        k: manifest[k]
        for k in ("sha256", "rows", "admissions", "reconciliation", "coverage", "reliability")
    }


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
                        for ref in ("b03", "b04_k8", "b04_k16", "b05_h4", "b05_h8", "b06", "b07")
                        if ref in m
                    }
                    for name in (*explore.COLUMNS, *explore.OPPORTUNITY_COLUMNS)
                    if name in m
                },
                "termCorrelations": _term_correlations(part),
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
        "format": FORMAT + f"-{config_of(args)['version']}-results",
        "generatedAt": datetime.now(UTC).isoformat(),
        "code": h.code_version(),
        "classification": "EXPLORATORY (estimators added after the 2025 holdout was inspected)",
        "config": {"path": args.config_name, "sha256": h.sha256(Path(args.config))},
        "run": args.run,
        "frozen": fz.verification,
        "history": lineage,
        "v1ReproducedOnValidRows": reproduced,
        "stages": out,
        "opportunity": _opportunity_summary(run_folder(args)) if uses_opportunity(args) else None,
        "decision": "none: descriptive; never changes frozen candidates",
        "forbidden_vendor_projection_dependencies": 0,
        "write_to_production": False,
    }
    target = Path(args.receipts) / f"{config_of(args)['version']}.json"
    target.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({"v1ReproducedOnValidRows": reproduced, "receipt": str(target)}))
    if not reproduced:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--main", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=ROOT / "config/dvp/explore-v2.json")
    parser.add_argument("--out", type=Path, help="default: <main>/artifacts/dvp/<version>")
    parser.add_argument("--run", required=True, help="one run id for all three stages and evaluate")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("opportunity")
    f = commands.add_parser("forecast")
    f.add_argument("--stage", choices=STAGES, required=True)
    e = commands.add_parser("evaluate")
    e.add_argument("--receipts", type=Path, default=ROOT / "docs/research/dvp")
    args = parser.parse_args()
    args.main = args.main.resolve()
    args.config = args.config.resolve()
    args.config_name = str(args.config.relative_to(ROOT))
    {"opportunity": opportunity, "forecast": forecast, "evaluate": evaluate}[args.command](args)


if __name__ == "__main__":
    main()
