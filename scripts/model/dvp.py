"""M3-3 DvP research commands (the owner's specification v1.1, OWN-074): `audit`, `reproduce-v0`.

`audit` (phases 0-1): admits every input through the lineage allowlist, builds the completed-game
observations, reconciles them with the schedule, checks the targets' scoring hashes against the
league's current rules, scans the scoring path for provider projections, and writes receipts.

  ARBIT_NFLVERSE_PATH=<main>/data/nflverse uv run --env-file <main>/.env.local \\
    python scripts/model/dvp.py audit --config config/dvp/base.json \\
      --targets <main>/data/model --out <main>/artifacts/dvp --receipts docs/research/dvp

`reproduce-v0`: reruns the frozen v0 script unchanged on the pinned targets and diffs its output
with the v0 receipt, recomputes v0 independently, explains v0's k arithmetic, and runs v0's method
on an audit run's validated observations (`v0-validated`), with intervals.

  uv run python scripts/model/dvp.py reproduce-v0 --config config/dvp/base.json \\
    --targets <main>/data/model --run <main>/artifacts/dvp/<audit run> --receipts docs/research/dvp

Read only against the database, the nflverse store and the targets store. Bulky outputs go under
--out/<run id> (ignored by git); receipts under --receipts.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from arbit_core.rules import RuleSet
from arbit_data.db import UnitOfWork
from arbit_data.league_policy import read_policy
from arbit_data.nflverse.objects import ObjectStore
from arbit_model.dvp import contract
from arbit_model.dvp import observations as obs
from arbit_model.dvp import reliability as rel
from arbit_model.dvp.provenance import FORBIDDEN, SOURCES, Admission, admit, scan_code
from arbit_model.gamebook import FFA_POSITIONS, POSITIONS
from arbit_model.inputs import NflverseTables
from arbit_model.teams import franchise, franchise_expr
from sqlalchemy import create_engine, select, text

ROOT = Path(__file__).resolve().parents[2]
FORMAT = "arbit-dvp-m3-3"
V0_FILES = (
    "scripts/model/defense_position_study.py",
    "docs/research/defense-position-study-2026-11-23.json",
    "scripts/model/ffa_signal_study.py",
    "docs/research/ffa-signal-study-2026-11-09.json",
)
V0_CONSUMERS = ("libs/arbit-model/src/arbit_model/feature_specs.py",)
SCANNED = (
    "libs/arbit-model/src/arbit_model/dvp/__init__.py",
    "libs/arbit-model/src/arbit_model/dvp/observations.py",
    "libs/arbit-model/src/arbit_model/dvp/asof.py",
    "libs/arbit-model/src/arbit_model/dvp/reliability.py",
    "libs/arbit-model/src/arbit_model/dvp/results.py",
    "libs/arbit-model/src/arbit_model/dvp/lab.py",
    "libs/arbit-model/src/arbit_model/dvp/svg.py",
    "libs/arbit-model/src/arbit_model/dvp/walkforward.py",
    "libs/arbit-model/src/arbit_model/dvp/decisions.py",
    "libs/arbit-model/src/arbit_model/dvp/shadow.py",
    "libs/arbit-model/src/arbit_model/dvp/window.py",
    "libs/arbit-model/src/arbit_model/dvp/contract.py",
    "libs/arbit-model/src/arbit_model/dvp/explore.py",
    "libs/arbit-model/src/arbit_model/dvp/opportunity.py",
    "libs/arbit-model/src/arbit_model/dvp/league.py",
    "libs/arbit-model/src/arbit_model/ffa_history.py",
    "libs/arbit-model/src/arbit_model/teams.py",
    "scripts/model/dvp.py",
    "scripts/model/dvp_prospective.py",
    "scripts/model/dvp_explore.py",
    "scripts/model/dvp_league_2026.py",
    "scripts/model/defense_position_study.py",
    "scripts/model/ffa_signal_study.py",
    "scripts/model/build_targets.py",
    "libs/arbit-model/src/arbit_model/targets.py",
    "libs/arbit-model/src/arbit_model/storage.py",
    "libs/arbit-model/src/arbit_model/inputs.py",
    "libs/arbit-model/src/arbit_model/gamebook.py",
    "libs/arbit-data/src/arbit_data/nflverse/stat_lines.py",
    "libs/arbit-core/src/arbit_core/scoring.py",
    "libs/arbit-core/src/arbit_core/rules.py",
)
TARGET_INPUT_FAMILIES = frozenset(
    {"pbp", "players", "schedules", "snap_counts", "stats_player", "stats_team", "weekly_rosters"}
)
CANCELED = "2022_17_BUF_CIN"
EXPECTED_TEAM_GAMES = 5278


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


FORECAST_KEY = ("season", "week", "game_id", "offense", "position")
# Polars sums in parallel in a varying order, so a rerun's forecasts can differ in the last bit
# (measured: at most 7e-15 points). Two forecast files are the same within this tolerance.
FORECAST_TOLERANCE = 1e-9


def content_sha256(frame: pl.DataFrame) -> str:
    """A fingerprint of a forecast frame's content that ignores row and column order and the
    last-bit noise of parallel sums: rows sorted by key, columns by name, floats rounded to 6
    decimals, written as CSV. Byte hashes of Parquet files differ between such reruns."""
    keyed = frame.select(sorted(frame.columns)).sort(list(FORECAST_KEY))
    keyed = keyed.with_columns(
        [pl.col(c).round(6) for c, t in keyed.schema.items() if t.is_float()]
    )
    return hashlib.sha256(keyed.write_csv().encode()).hexdigest()


def same_forecasts(a: pl.DataFrame, b: pl.DataFrame) -> bool:
    """Same rows, same non-float values and missing cells, and floats within FORECAST_TOLERANCE."""
    if set(a.columns) != set(b.columns) or a.height != b.height:
        return False
    order = sorted(a.columns)
    a = a.select(order).sort(list(FORECAST_KEY))
    b = b.select(order).sort(list(FORECAST_KEY))
    for name in order:
        x, y = a.get_column(name), b.get_column(name)
        if not x.dtype.is_float():
            if not x.equals(y):
                return False
            continue
        xs, ys = x.to_numpy(), y.to_numpy()
        missing = np.isnan(xs)
        if not np.array_equal(missing, np.isnan(ys)):
            return False
        if (~missing).any() and np.abs(xs[~missing] - ys[~missing]).max() > FORECAST_TOLERANCE:
            return False
    return True


def write_forecasts(path: Path, frame: pl.DataFrame) -> None:
    """Write a stage's forecasts once. A rerun with the same forecasts leaves the file, and every
    receipt naming its hash, alone; a rerun with different forecasts refuses to overwrite evidence."""
    if path.exists():
        if same_forecasts(pl.read_parquet(path), frame):
            print(f"{path.name}: same forecasts as the existing file; left unchanged")
            return
        raise SystemExit(
            f"{path} holds different forecasts; run a new audit instead of overwriting evidence"
        )
    tmp = path.with_suffix(".parquet.tmp")
    frame.sort(list(FORECAST_KEY)).write_parquet(tmp)
    tmp.replace(path)


def code_version() -> str:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    # Code, not receipts: the runs themselves rewrite docs/research/dvp between steps.
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no", "--", ".", ":(exclude)docs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return head + ("+uncommitted" if dirty else "")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, sort_keys=True, default=str) + "\n")
    tmp.replace(path)


def check(passed: bool, detail: Any) -> dict[str, Any]:
    return {"status": "PASSED" if passed else "FAILED", "detail": detail}


def load_index(targets: Path, digest: str) -> dict[str, Any]:
    raw = (targets / "objects" / digest).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise SystemExit("targets index object does not match its digest")
    index: dict[str, Any] = json.loads(raw)
    return index


def verified_object(targets: Path, digest: str) -> Path:
    """A content-addressed store object whose bytes still match its digest (owner audit AUD-04):
    a file named by a digest is not trusted until its content is hashed."""
    path = targets / "objects" / digest
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise SystemExit(f"store object {digest[:12]} does not match its digest")
    return path


def season_manifest(targets: Path, index: dict[str, Any], season: int) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads(
        verified_object(targets, index["seasons"][str(season)]).read_bytes()
    )
    return manifest


def read_targets(
    targets: Path, index: dict[str, Any], config: dict[str, Any], role: str
) -> tuple[pl.DataFrame, list[Admission]]:
    source_id = f"ffa_targets.{role}"
    frames, admissions = [], []
    for season in config["seasons"]:
        manifest = season_manifest(targets, index, season)
        digest = manifest["tables"][role]["parquet"]
        path = verified_object(targets, digest)
        admitted = admit(
            pl.read_parquet(path, columns=list(SOURCES[source_id].used)),
            source_id,
            ancestry=f"targets index {config['targets_index']}, season {season} manifest "
            f"{index['seasons'][str(season)]}, parquet {digest}",
            scoring_hash=manifest["rules"][role],
            expected_scoring=config["expected_scoring"],
            schema=list(pl.read_parquet_schema(path)),
        )
        frames.append(admitted.frame)
        admissions.append(admitted)
    return pl.concat(frames, how="vertical_relaxed"), admissions


def audit(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    started = datetime.now(UTC)
    run_id = "phase1-audit-" + started.strftime("%Y%m%dT%H%M%SZ")
    out = args.out / run_id
    out.mkdir(parents=True, exist_ok=False)
    index = load_index(args.targets, config["targets_index"])
    seasons: list[int] = config["seasons"]
    manifests = {s: season_manifest(args.targets, index, s) for s in seasons}
    checks: dict[str, Any] = {}

    engine = create_engine(
        os.environ["ARBIT_DATABASE_URL"],
        hide_parameters=True,
        execution_options={"postgresql_readonly": True},
    )
    with engine.connect() as c:
        payload: dict[str, Any] = c.execute(
            text(
                "select r.payload from rule_version r "
                "join league_document d on d.rules_hash = r.hash "
                "join current_snapshot s on s.snapshot_id = d.snapshot_id"
            )
        ).scalar_one()
    league_rules = {
        role: RuleSet.model_validate_json(json.dumps(payload[f"{role}_rules"])).content_hash
        for role in ("athlete", "defense")
    }
    slots = read_policy(payload).lineup_slots
    checks["T37 targets index scored with the configured rules"] = check(
        index["rules"] == config["expected_scoring"]
        and all(m["rules"] == config["expected_scoring"] for m in manifests.values()),
        {"index": index["rules"], "configured": config["expected_scoring"]},
    )
    checks["T30 configured rules are the league's current FFA rules"] = check(
        league_rules == config["expected_scoring"], {"league": league_rules}
    )

    pins = {m["inputs"]["schedules/games"] for m in manifests.values()}
    if len(pins) != 1:
        raise SystemExit(f"seasons were built from different schedules: {sorted(pins)}")
    schedule_pin = pins.pop()
    nflverse = ObjectStore(Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects")
    tables = NflverseTables(UnitOfWork(engine), nflverse, {"schedules/games": schedule_pin})
    schedule = admit(
        pl.from_dicts(tables.read("schedules/games"), infer_schema_length=None),
        "nflverse.schedules",
        ancestry=f"nflverse manifest {schedule_pin} (the schedule the targets were built from)",
    )
    athlete, athlete_admissions = read_targets(args.targets, index, config, "athlete")
    defense, defense_admissions = read_targets(args.targets, index, config, "defense")
    admissions = [schedule, *athlete_admissions, *defense_admissions]

    scheduled = obs.games(schedule.frame, seasons)
    played = obs.team_games(scheduled)
    cells, athlete_anomalies = obs.position_cells(athlete, played)
    dst, dst_anomalies = obs.dst_cells(defense, played)
    rows = obs.observations(cells, dst, config["expected_scoring"])
    summary = obs.reconcile(scheduled, rows)

    per_team = rows.select("season", "offense", "game_id").unique().group_by("season", "offense")
    games_per_team = (
        per_team.len()
        .group_by("season")
        .agg(
            pl.col("len").min().alias("min"),
            pl.col("len").max().alias("max"),
            pl.len().alias("teams"),
        )
    )
    checks["T06 completed team-games reconcile to 5,278"] = check(
        summary["teamGames"] == EXPECTED_TEAM_GAMES,
        {"teamGames": summary["teamGames"], "expected": EXPECTED_TEAM_GAMES},
    )
    checks["T06 every completed game has exactly two mirrored team-games"] = check(
        summary["gamesWithoutExactlyTwoTeamGames"] == 0
        and summary["teamGamesWithoutMirror"] == 0
        and summary["duplicateGameIds"] == 0,
        {k: summary[k] for k in ("gamesWithoutExactlyTwoTeamGames", "teamGamesWithoutMirror")},
    )
    checks["T06 32 teams each season, 16 or 17 games each"] = check(
        all(
            r["teams"] == 32 and r["max"] == (16 if r["season"] <= 2020 else 17)
            for r in games_per_team.iter_rows(named=True)
        ),
        {
            str(r["season"]): [r["teams"], r["min"], r["max"]]
            for r in games_per_team.iter_rows(named=True)
        },
    )
    listed = scheduled.filter(pl.col("game_id") == CANCELED)
    teams_2022 = {
        r["offense"]: r["len"]
        for r in per_team.len()
        .filter((pl.col("season") == 2022) & pl.col("offense").is_in(["BUF", "CIN"]))
        .iter_rows(named=True)
    }
    checks["T34 the canceled 2022 BUF-CIN game has no team-games and no zeros"] = check(
        all(s == "not_completed" for s in listed.get_column("status").to_list())
        and rows.filter(pl.col("game_id") == CANCELED).height == 0
        and summary["seasons"]["2022"]["completedGames"] == 271
        and teams_2022 == {"BUF": 16, "CIN": 16},
        {
            "inSchedule": listed.select("game_id", "status").to_dicts(),
            "completedGames2022": summary["seasons"]["2022"]["completedGames"],
            "gamesPlayed2022": teams_2022,
        },
    )
    checks["T05 every target line belongs to a completed team-game"] = check(
        athlete_anomalies["rowsOutsideCompletedTeamGames"] == 0
        and dst_anomalies["dstLinesOutsideCompletedTeamGames"] == 0,
        {
            "athleteRowsOutside": athlete_anomalies["rowsOutsideCompletedTeamGames"],
            "dstLinesOutside": dst_anomalies["dstLinesOutsideCompletedTeamGames"],
        },
    )
    checks["T05 no player has two lines in one game"] = check(
        athlete_anomalies["duplicatePlayerGameLines"] == 0,
        athlete_anomalies["duplicatePlayerGameLines"],
    )
    raw_codes = {
        "athlete": _codes(athlete, "team"),
        "defense": _codes(defense, "team"),
        "schedule": _codes(schedule.frame.filter(pl.col("season").is_in(seasons)), "home_team"),
    }
    groups = sorted(rows.get_column("position").unique().to_list())
    status_counts = obs.count_by(rows, "position", "status")
    values = rows.filter(pl.col("status") == obs.VALID)
    by_position = values.group_by("position").agg(
        pl.len().alias("validCells"),
        (pl.col("points") == 0).sum().alias("trueZeros"),
        (pl.col("points") < 0).sum().alias("negative"),
        pl.col("points").min().alias("min"),
        pl.col("points").max().alias("max"),
        pl.col("points").mean().round(3).alias("mean"),
    )
    traded = (
        athlete.filter((pl.col("season_type") == "REG") & (pl.col("basis") == "statistics"))
        .with_columns(obs.franchise(pl.col("team")).alias("franchise"))
        .group_by("season", "player_id")
        .agg(pl.col("franchise").n_unique().alias("teams"))
        .filter(pl.col("teams") > 1)
    )
    contributions = _contribution_check(args.targets, index, seasons)
    checks["T30 each scored line's points equal the sum of its rule contributions"] = check(
        contributions["mismatched"] == 0, contributions
    )
    examples = _examples(args.targets, index, rows, athlete, defense)

    rows.write_parquet(out / "observations.parquet")
    scheduled.write_parquet(out / "schedule_games.parquet")
    outputs = {
        name: sha256(out / name) for name in ("observations.parquet", "schedule_games.parquet")
    }
    code = code_version()
    run_manifest = {
        "format": FORMAT + "-run-v1",
        "runId": run_id,
        "command": "audit",
        "startedAt": started.isoformat(),
        "code": code,
        "config": {"path": str(args.config), "sha256": sha256(args.config)},
        "targetsIndex": config["targets_index"],
        "scheduleManifest": schedule_pin,
        "outputs": outputs,
    }
    write_json(out / "run-manifest.json", run_manifest)

    findings = [f for p in SCANNED for f in scan_code(ROOT / p)]
    families = sorted({k.split("/")[0] for m in manifests.values() for k in m["inputs"]})
    outside = [f for f in families if f not in TARGET_INPUT_FAMILIES]
    forbidden_sources = [
        a.source_id for a in admissions if a.source_type.value.endswith("FORBIDDEN")
    ]
    dependencies = len(findings) + len(outside) + len(forbidden_sources)
    checks["T31 no provider projection in the scoring path or DvP code"] = check(
        dependencies == 0, {"codeFindings": findings, "inputFamiliesOutsideAllowlist": outside}
    )
    exclusion = {
        "format": FORMAT + "-projection-exclusion-v1",
        "generatedAt": started.isoformat(),
        "runId": run_id,
        "code": code,
        "forbidden_vendor_projection_dependencies": dependencies,
        "status": "PASSED" if dependencies == 0 else "FAILED",
        "admittedSources": [a.record() for a in admissions],
        "targetInputFamilies": {"seen": families, "allowed": sorted(TARGET_INPUT_FAMILIES)},
        "codeScan": {
            "files": {p: sha256(ROOT / p) for p in SCANNED},
            "policyFileNotScanned": "libs/arbit-model/src/arbit_model/dvp/provenance.py "
            "(it names the forbidden tokens to forbid them)",
            "findings": findings,
        },
        "forbiddenInventory": [
            {
                "source": f.source,
                "where": f.where,
                "reason": f.reason,
                "guard": f.guard,
                "decision": f.decision,
                "action": "REJECT",
                "reachableFromDvp": False,
            }
            for f in FORBIDDEN
        ],
        "slice2Agreement": "docs/research/ffa-targets-check-2026-11-10.json: 10,734 of 10,771 "
        "2026 lines equal ESPN's actual applied totals (actual blocks only; an audit, not an input)",
    }
    write_json(args.receipts / "PROJECTION_EXCLUSION_AUDIT.json", exclusion)

    observed = _manifest_times(engine, manifests)
    finality = {
        "format": FORMAT + "-score-finality-v1",
        "generatedAt": started.isoformat(),
        "runId": run_id,
        "policy": config["as_of_policy"],
        "targetsBuilt": {"startedAt": index["startedAt"], "finishedAt": index["finishedAt"]},
        "seasons": {
            str(s): {
                "scheduledGames": summary["seasons"][str(s)]["scheduledGames"],
                "completedGames": summary["seasons"][str(s)]["completedGames"],
                "notCompleted": summary["seasons"][str(s)]["notCompleted"],
                "inputsFirstObservedByArbit": observed[s],
            }
            for s in seasons
        },
        "eligibility": "A game's FFA actuals count from 12:00 UTC the day after its game day. Arbit "
        "first read these seasons' files in 2026, so every value is the final revision; when a "
        "stat correction first appeared is unknown and cannot be replayed (backtest limitation).",
        "status": "PASSED_WITH_LIMITATION",
    }
    write_json(args.receipts / "SCORE_FINALITY_AUDIT.json", finality)

    head = subprocess.run(
        ["git", "log", "-1", "--format=%H %cI", "--", V0_FILES[0]],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    frozen = json.loads((ROOT / V0_FILES[1]).read_text())
    continuity = {
        "format": FORMAT + "-continuity-v1",
        "workstream": "M3-3",
        "v0": {
            "experimentId": "M3-3-v0",
            "status": "EXISTING",
            "commit": head[0],
            "committedAt": head[1],
            "task": "TASK-20261123-004",
            "decisionRecords": ["ENG-056", "OWN-068"],
            "files": {p: sha256(ROOT / p) for p in V0_FILES},
            "targetsIndex": frozen["targetsIndex"],
            "seasons": frozen["seasons"],
            "method": frozen["method"],
            "gamesForHalfSignal": {
                k: v["gamesForHalfSignal"] for k, v in sorted(frozen["stability"].items())
            },
            "consumers": {p: sha256(ROOT / p) for p in V0_CONSUMERS},
        },
        "rule": "v0 files stay byte-identical; extensions write new receipts and runs",
    }
    write_json(args.receipts / "continuity-manifest.json", continuity)

    receipt = {
        "format": FORMAT + "-audit-v1",
        "generatedAt": started.isoformat(),
        "runId": run_id,
        "code": code,
        "runManifest": run_manifest,
        "positions": {
            "leagueLineupSlots": list(slots),
            "modeledGroups": groups,
            "mapping": dict(POSITIONS),
            "note": "FLEX and other multi-position slots draw on the same groups; K and D/ST are "
            "lineup slots, so both are in scope; FB counts as RB",
        },
        "checks": checks,
        "reconciliation": summary,
        "cellsByStatus": status_counts,
        "validCellsByPosition": {r["position"]: r for r in by_position.iter_rows(named=True)},
        "anomalies": {
            "athlete": athlete_anomalies,
            "dst": dst_anomalies,
            "rawTeamCodes": raw_codes,
            "playersWithTwoFranchisesInASeason": traded.height,
        },
        "examples": examples,
    }
    write_json(args.receipts / "audit-receipt.json", receipt)
    failed = [name for name, c in checks.items() if c["status"] != "PASSED"]
    print(f"run {run_id}: {summary['teamGames']} team-games; failed checks: {failed or 'none'}")
    print(json.dumps(status_counts, indent=1))


def _codes(frame: pl.DataFrame, column: str) -> dict[str, list[str]]:
    grouped = frame.group_by("season").agg(pl.col(column).cast(pl.String).unique().sort())
    return {
        str(s): [c for c in codes if c in ("OAK", "LV", "SD", "LAC", "STL", "LA")]
        for s, codes in grouped.sort("season").iter_rows()
    }


def _contribution_check(targets: Path, index: dict[str, Any], seasons: list[int]) -> dict[str, Any]:
    checked = mismatched = 0
    for season in seasons:
        manifest = season_manifest(targets, index, season)
        for role in ("athlete", "defense"):
            path = targets / "objects" / manifest["tables"][role]["parquet"]
            frame = pl.read_parquet(path, columns=["points", "contributions"]).filter(
                pl.col("points").is_not_null()
            )
            total = frame.select(
                pl.col("points").cast(pl.Float64),
                pl.col("contributions")
                .list.eval(pl.element().struct.field("points").cast(pl.Float64))
                .list.sum()
                .alias("sum"),
            )
            checked += total.height
            mismatched += total.filter((pl.col("points") - pl.col("sum")).abs() > 1e-6).height
    return {"checked": checked, "mismatched": mismatched}


def _examples(
    targets: Path,
    index: dict[str, Any],
    rows: pl.DataFrame,
    athlete: pl.DataFrame,
    defense: pl.DataFrame,
) -> dict[str, Any]:
    """Small fixed samples for manual verification (spec §3.3)."""
    valid = rows.filter((pl.col("status") == obs.VALID) & (pl.col("season") == 2025))
    zero_te = valid.filter((pl.col("position") == "TE") & (pl.col("points") == 0)).sort(
        "game_id", "offense"
    )
    multi_wr = valid.filter((pl.col("position") == "WR") & (pl.col("lines") >= 5)).sort(
        "game_id", "offense"
    )
    wr = multi_wr.row(0, named=True)
    wr_lines = athlete.filter(
        (pl.col("game_id") == wr["game_id"])
        & (pl.col("team") == wr["offense"])
        & (pl.col("position") == "WR")
    ).select("player_id", pl.col("points").cast(pl.Float64), "basis")
    traded = (
        athlete.filter((pl.col("season") == 2025) & (pl.col("basis") == "statistics"))
        .with_columns(pl.col("team").n_unique().over("player_id").alias("teams"))
        .filter(pl.col("teams") > 1)
        .sort("player_id", "week")
    )
    player = traded.get_column("player_id")[0]
    manifest = season_manifest(targets, index, 2025)
    stats = pl.read_parquet(targets / "objects" / manifest["tables"]["defense"]["parquet"])
    turnover = (
        stats.filter(
            (pl.col("season_type") == "REG")
            & (pl.col("defense.interceptions").cast(pl.Float64) >= 2)
        )
        .sort("game_id", "team")
        .row(0, named=True)
    )
    components = {
        k: float(v)
        for k, v in turnover.items()
        if k.startswith(("defense.", "returns.")) and v is not None and float(v) != 0
    }
    scored = {
        c["stat_id"] + "#" + c["rule_id"]: float(c["points"])
        for c in turnover["contributions"]
        if float(c["points"]) != 0
    }
    dst_row = rows.filter(
        (pl.col("position") == obs.DST)
        & (pl.col("game_id") == turnover["game_id"])
        & (pl.col("defense") == franchise(turnover["team"]))
    ).row(0, named=True)
    return {
        "zeroProductionTe": zero_te.select(
            "game_id", "offense", "defense", "points", "lines", "status"
        ).row(0, named=True)
        | {"validZeroTeCells2025": zero_te.height},
        "multiWrOffense": {
            "cell": {k: wr[k] for k in ("game_id", "offense", "defense", "points", "lines")},
            "lines": wr_lines.to_dicts(),
            "sumOfLines": round(float(wr_lines.get_column("points").sum()), 6),
        },
        "tradedPlayer": {
            "player_id": player,
            "games": traded.filter(pl.col("player_id") == player)
            .select("week", "game_id", "team", "opponent", pl.col("points").cast(pl.Float64))
            .to_dicts(),
        },
        "dstTurnover": {
            "game_id": turnover["game_id"],
            "dst": turnover["team"],
            "offense": turnover["opponent"],
            "points": float(turnover["points"]),
            "statistics": components,
            "ruleContributions": scored,
            "observationRow": {k: dst_row[k] for k in ("offense", "defense", "unit", "points")},
        },
    }


def _manifest_times(engine: Any, manifests: dict[int, dict[str, Any]]) -> dict[int, dict[str, str]]:
    from arbit_data.schema import dataset_manifest

    out: dict[int, dict[str, str]] = {}
    with engine.connect() as c:
        for season, manifest in manifests.items():
            hashes = {
                k: v
                for k, v in manifest["inputs"].items()
                if k.split("/")[0] in ("pbp", "stats_player", "stats_team", "schedules")
            }
            found = dict(
                c.execute(
                    select(dataset_manifest.c.hash, dataset_manifest.c.observed_at).where(
                        dataset_manifest.c.hash.in_(list(hashes.values()))
                    )
                ).all()
            )
            out[season] = {k: found[v].isoformat() for k, v in sorted(hashes.items())}
    return out


def _strip(report: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in report.items() if k not in ("startedAt", "reportSha256")}


def _diff(a: Any, b: Any, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        return [
            d for k in sorted(set(a) | set(b)) for d in _diff(a.get(k), b.get(k), f"{path}.{k}")
        ]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def _v0_frames(targets: Path, index: dict[str, Any], seasons: list[int]) -> pl.DataFrame:
    """v0's own data choices, recomputed independently: statistics lines, the targets' opponent,
    null points summed as nothing, zero-filled position grid, same-season leave-one-out."""
    parts = []
    for season in seasons:
        manifest = season_manifest(targets, index, season)
        path = targets / "objects" / manifest["tables"]["athlete"]["parquet"]
        columns = ["season_type", "basis", "game_id", "week", "team", "opponent", "position"]
        athletes = pl.read_parquet(path, columns=[*columns, "points"]).filter(
            (pl.col("season_type") == "REG") & (pl.col("basis") == "statistics")
        )
        keys = ["game_id", "week", "team", "opponent"]
        by_position = (
            athletes.with_columns(
                pl.col("position").replace_strict(dict(POSITIONS), default=None).alias("pos"),
                pl.col("points").cast(pl.Float64),
            )
            .filter(pl.col("pos").is_not_null())
            .group_by(*keys, "pos")
            .agg(pl.col("points").sum())
        )
        grid = (
            athletes.select(keys)
            .unique()
            .join(pl.DataFrame({"pos": list(FFA_POSITIONS)}), how="cross")
        )
        filled = grid.join(by_position, on=[*keys, "pos"], how="left").with_columns(
            pl.col("points").fill_null(0.0)
        )
        filled = filled.with_columns(
            (pl.col("points") - rel.leave_one_out(["team", "pos"], "points")).alias("adjusted")
        )
        path = targets / "objects" / manifest["tables"]["defense"]["parquet"]
        dst = (
            pl.read_parquet(path, columns=["season_type", *keys, "points"])
            .filter(pl.col("season_type") == "REG")
            .select(*keys, pl.col("points").cast(pl.Float64))
            .with_columns(pl.lit("DST").alias("pos"))
        )
        dst = dst.with_columns(
            (pl.col("points") - rel.leave_one_out(["team"], "points")).alias("adjusted")
        )
        parts.append(
            pl.concat([filled, dst.select(filled.columns)]).with_columns(
                pl.lit(season).alias("season")
            )
        )
    return pl.concat(parts)


def reproduce(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    started = datetime.now(UTC)
    v0_digest = config["v0_targets_index"]
    index = load_index(args.targets, v0_digest)
    seasons: list[int] = config["seasons"]
    audit_run = json.loads((args.run / "run-manifest.json").read_text())
    if audit_run["targetsIndex"] != config["targets_index"]:
        raise SystemExit("the audit run read a different targets index from the configured one")
    frozen = json.loads((ROOT / config["original_study_receipt"]).read_text())
    out = args.run / "v0"
    out.mkdir(parents=True, exist_ok=True)
    # v0 reads whatever `targets-current.json` names. It ran on the index before the R-072
    # repair, so it reads that index through a pointer of its own, beside the same objects.
    staged = out / "v0-targets"
    staged.mkdir(exist_ok=True)
    (staged / "targets-current.json").write_text(json.dumps({"index": v0_digest}) + "\n")
    if not (staged / "objects").exists():
        (staged / "objects").symlink_to((args.targets / "objects").resolve())
    rerun_path = out / "v0-rerun.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / config["original_study_script"]),
            "--targets",
            str(staged),
            str(rerun_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    rerun = json.loads(rerun_path.read_text())
    differences = _diff(_strip(frozen), _strip(rerun))

    v0 = _v0_frames(args.targets, index, seasons)
    independent: dict[str, Any] = {}
    formula: dict[str, Any] = {}
    for (pos,), part in v0.group_by(["pos"], maintain_order=True):
        for kind, column in (("raw", "points"), ("adjusted", "adjusted")):
            name = f"{pos}_{kind}"
            result = rel.split_half(rel.halves(part, ["opponent", "season"], column))
            stored = frozen["stability"][name]
            independent[name] = {
                "units": result.units,
                "pearson": round(result.r or 0, 3),
                "k": round(result.k or 0, 1),
                "matchesReceipt": result.units == stored["unitSeasons"]
                and round(result.r or 0, 3) == stored["splitHalfR"]
                and round(result.k or 0, 1) == stored["gamesForHalfSignal"],
            }
            m8 = rel.k_from_r(result.r, 8)
            formula[name] = {
                "pearson": round(result.r or 0, 5),
                "meanHalfGames": round(result.m or 0, 4),
                "kV0": stored["gamesForHalfSignal"],
                "kRecomputed": round(result.k or 0, 2),
                "kIfHalvesWere8": round(m8, 2) if m8 is not None else None,
                "singleGame": round(rel.single_game(result.k) or 0, 4),
                "weightAt8": round(rel.weight(8, result.k) or 0, 4),
            }

    rows = pl.read_parquet(args.run / "observations.parquet")
    validated: dict[str, Any] = {}
    for pos in config["position_groups"]:
        valid = rows.filter((pl.col("position") == pos) & (pl.col("status") == obs.VALID))
        expectation = ["defense", "season"] if pos == obs.DST else ["offense", "season"]
        valid = valid.with_columns(
            (pl.col("points") - rel.leave_one_out(expectation, "points")).alias("adjusted")
        )
        for kind, column in (("raw", "points"), ("adjusted", "adjusted")):
            name = f"{pos}_{kind}"
            pairs = rel.halves(valid, ["unit", "season"], column, config["min_split_half_games"])
            pairs.write_parquet(out / f"pairs-{name}.parquet")
            result = rel.split_half(pairs)
            stored = frozen["stability"][name]
            odd, even = pairs.get_column("odd_mean"), pairs.get_column("even_mean")
            spread = pl.concat([odd, even])
            mean, sd = float(spread.mean()), float(spread.std())  # type: ignore[arg-type]
            validated[name] = result.summary() | {
                "fisher95": _pair(rel.fisher_interval(result.r, result.units)),
                "bootstrapUnits": rel.bootstrap(
                    pairs, config["bootstrap_replicates"], config["random_seed"]
                ),
                "bootstrapSeasons": rel.bootstrap(
                    pairs, config["bootstrap_replicates"], config["random_seed"], "season"
                ),
                "halfMeans": {"mean": round(mean, 3), "sd": round(sd, 3)},
                "outlierHalves": int(((spread - mean).abs() > 3 * sd).sum()),
                "v0": {
                    "units": stored["unitSeasons"],
                    "pearson": stored["splitHalfR"],
                    "k": stored["gamesForHalfSignal"],
                },
            }
    report = {
        "format": FORMAT + "-v0-reproduction-v1",
        "generatedAt": started.isoformat(),
        "code": code_version(),
        "auditRun": args.run.name,
        "v0TargetsIndex": v0_digest,
        "validatedTargetsIndex": config["targets_index"],
        "rerun": {
            "command": f"{config['original_study_script']} --targets <targets> <out>",
            "comparedWith": config["original_study_receipt"],
            "ignored": ["startedAt", "reportSha256 (covers startedAt)"],
            "exact": not differences,
            "differences": differences,
        },
        "independent": independent,
        "kArithmetic": formula,
        "v0Validated": validated,
        "status": "REPRODUCED" if not differences else "DISCREPANCY",
    }
    write_json(args.receipts / "v0-reproduction.json", report)
    print("rerun exact:", not differences)
    for name, value in validated.items():
        print(name, value["units"], value["pearson"], value["k"], "v0", value["v0"])


PLANNED: dict[str, str] = {
    "A00": "Raw DvP landscape: distributions, team means, within-team spread, raw vs adjusted ranks",
    "A02": "Split-method sensitivity: alternating games, halves, 6+6, seeded random balanced splits",
    "A03": "Opponent-adjustment sensitivity: none, leave-one-out, robust median, strength-adjusted",
    "A04": "Position-specific sample stability by game count and era, with intervals",
    "A05": "Variance components (tau2, sigma2, season effects) with unequal game counts vs v0 k",
    "A06": "Temporal stability: first vs second half, decay with weeks apart, rolling windows",
    "A07": "Between-season carryover of a defense's tendency, with relocations",
    "A08": "Noise, placebo and null distributions; clustered and iid bootstrap",
    "A09": "Volume vs efficiency vs touchdowns: which part of DvP repeats",
    "A10": "Era robustness: 16 vs 17 games, leave-one-season-out, trimming, home/away, rest",
    "A12": "Completion and correction sensitivity of r, k and coverage",
    "B00": "Offense-only next-game forecast from prior FFA actuals: the comparator",
    "B01": "Raw prior-games DvP added to B00",
    "B02": "Prior-only offense-adjusted DvP added to B00, unshrunk",
    "B03": "v0-k-shrunk adjusted DvP with k estimated on training years only",
    "B04": "Prediction-tuned k on a predeclared grid (development and 2024 only)",
    "B05": "Recency-weighted DvP with effective sample size",
    "B06": "Hierarchical or dynamic DvP learned from past years only",
    "B07": "Opportunity and efficiency allowed, alone and jointly",
    "B08": "Context-stratified diagnostics (week, sample size, matchup type)",
    "B09": "Adversarial negative controls: shuffled defenses, noise, shifted labels",
    "B10": "Preweek vs per-game cutoff: accuracy and coverage",
    "B11": "Projection-contamination resistance of B00-B10 (integrity test)",
    "B12": "Availability of finalized actuals by cutoff: coverage lost under conservative rules",
    "C00": "Arbit-computed player baseline from eligible actuals, no DvP",
    "C01": "Group DvP allocated to players by past-known usage share",
    "C02": "Additive vs proportional vs opportunity x efficiency allocation",
    "C03": "Role interactions (slot/outside, target share) where coverage allows",
    "C04": "Historical same-position and lineup-slot Sit/Start comparisons",
    "C05": "Decision accuracy, points gained or lost, and regret vs the baseline",
}


def registry(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    receipts = args.receipts
    audit_receipt = json.loads((receipts / "audit-receipt.json").read_text())
    exclusion = json.loads((receipts / "PROJECTION_EXCLUSION_AUDIT.json").read_text())
    continuity = json.loads((receipts / "continuity-manifest.json").read_text())
    reproduction = json.loads((receipts / "v0-reproduction.json").read_text())
    from arbit_model.dvp import results

    ancestry = hashlib.sha256(
        json.dumps(exclusion["admittedSources"], sort_keys=True).encode()
    ).hexdigest()
    common = {
        "data_hash": config["targets_index"],
        "scoring_hash": config["expected_scoring"],
        "source_ancestry_hash": ancestry,
        "forbidden_vendor_projection_dependencies": exclusion[
            "forbidden_vendor_projection_dependencies"
        ],
        "actual_game_finality_policy": config["as_of_policy"]["availability_rule"],
    }
    descriptive = {
        "as_of_policy": "retrospective description over full seasons; the same-season "
        "leave-one-out adjustment uses later games, so it is never a forecast",
        "train_validation_test_periods": {"descriptive": "2016-2025 regular seasons"},
        "holdout_independence_status": "2025 used descriptively (v0); not an untouched holdout",
    }
    validated = reproduction["v0Validated"]
    v0_limits = [
        "Raiders home games 2016-2019 and Chargers home games 2016: 1,327 player lines name the "
        "team itself as the opponent, so those points were credited to the team's own defense "
        "and the visiting defenses lost a game (schedule OAK/SD vs statistics LV/LAC)",
        "156 regular-season team-games have no D/ST line (the same code mismatch in the D/ST "
        "scorer): the Raiders 2016-2019, the Chargers 2016 and every D/ST that played them",
        "58 team-game-position cells hold a refused line (null points) that v0 summed as zero",
        "Halves differ in size (7-9 games); k uses their mean (8.25), an approximation",
    ]
    entries = [
        results.record(
            "M3-3-v0",
            "REPRODUCED",
            hypothesis="RQ1: defenses have a repeatable position-specific tendency to allow FFA "
            "points (odd vs even NFL weeks, 2016-2025)",
            code_commit=continuity["v0"]["commit"],
            sample_count={k: v["units"] for k, v in reproduction["independent"].items()},
            estimator="odd/even split-half Pearson; k = m(1-r)/r with m the mean half size",
            parameters={"gamesForHalfSignal": continuity["v0"]["gamesForHalfSignal"]},
            tests_passed=["T29"],
            limitations=v0_limits
            + [f"Read targets index {config['v0_targets_index']}, built before the R-072 repair"],
            evidence_paths=[
                config["original_study_receipt"],
                "docs/research/dvp/v0-reproduction.json",
                "docs/research/dvp/V0_REPRODUCTION.md",
            ],
            reason="Frozen v0 rerun equals its receipt; an independent recompute matches all 12 "
            "measures",
            next_steps="Superseded for inference by M3-3-A01 (validated observations); kept as "
            "the baseline",
            **(common | {"data_hash": config["v0_targets_index"]}),
            **descriptive,
        ),
        results.record(
            "M3-3-A01",
            "EXECUTED",
            hypothesis="v0's method on validated observations gives the same repeatability",
            code_commit=reproduction["code"],
            sample_count={k: v["units"] for k, v in validated.items()},
            coverage_pct={k: round(100 * v["units"] / 320, 1) for k, v in validated.items()},
            estimator="v0 split-half on schedule-attributed cells; invalid and missing cells "
            "excluded; intervals: Fisher, bootstrap by unit and by season (2,000, seed 1729)",
            parameters={
                k: {
                    "pearson": v["pearson"],
                    "k": v["k"],
                    "k95Units": v["bootstrapUnits"]["k95"],
                    "k95Seasons": v["bootstrapSeasons"]["k95"],
                }
                for k, v in validated.items()
            },
            interval={k: v["fisher95"] for k, v in validated.items()},
            tests_passed=["T01-T07", "T08-T13", "T29"],
            limitations=[
                v0_limits[3],
                "Measured on the repaired targets (R-072): every completed team-game has its "
                "D/ST line and its schedule opponent",
            ],
            evidence_paths=["docs/research/dvp/v0-reproduction.json"],
            reason="Repeatability is real but weak for every position group except D/ST, and "
            "the WR, TE and K intervals overlap: their order is not established",
            next_steps="A00, A02-A08 on the validated observations; B00 comparator",
            **common,
            **descriptive,
        ),
        results.record(
            "M3-3-A11",
            "PASSED",
            hypothesis="v0 and the extension read only canonical FFA actuals under the league's "
            "current scoring, with no provider projection",
            code_commit=audit_receipt["code"],
            sample_count=audit_receipt["reconciliation"]["teamGames"],
            estimator="lineage allowlist admission, scoring-hash and contribution checks, code "
            "scan, schedule reconciliation",
            parameters={"checks": {k: v["status"] for k, v in audit_receipt["checks"].items()}},
            tests_passed=["T05", "T06", "T30", "T31", "T34", "T37"],
            limitations=[exclusion["slice2Agreement"]],
            evidence_paths=[
                "docs/research/dvp/audit-receipt.json",
                "docs/research/dvp/PROJECTION_EXCLUSION_AUDIT.json",
                "docs/research/dvp/SCORE_FINALITY_AUDIT.json",
            ],
            reason="Every audit check passed; data defects are recorded in DATA_QUALITY.md",
            next_steps="R-072 repaired in the canonical targets (TASK-20261123-007); v0 keeps "
            "reading the index it ran on",
            **common,
            **descriptive,
        ),
    ]
    executed = _phase_a_records(config, receipts, common, descriptive)
    executed += _phase_b_records(config, receipts, common)
    executed += _phase_c_records(config, receipts, common)
    entries.extend(executed)
    done = {e["experiment_id"].removeprefix("M3-3-") for e in executed}
    for code, hypothesis in PLANNED.items():
        if code in done:
            continue
        conditional = code.startswith("C")
        entries.append(
            results.record(
                f"M3-3-{code}",
                "PLANNED",
                hypothesis=hypothesis,
                forbidden_vendor_projection_dependencies=0,
                as_of_policy=None
                if code.startswith("A")
                else config["as_of_policy"]["default_cutoff"],
                train_validation_test_periods=None if code.startswith("A") else config["split"],
                holdout_independence_status="2025 exposed descriptively by v0: conditional "
                "holdout at best; 2026 games after a registered freeze for confirmation",
                next_steps="Runs only if Phase B finds a credible group-level signal"
                if conditional
                else None,
            )
        )
    problems = results.problems(entries)
    if problems:
        raise SystemExit("; ".join(problems))
    write_json(
        receipts / "experiment-registry.json",
        {"format": FORMAT + "-registry-v1", "workstream": "M3-3", "experiments": entries},
    )
    print(f"{len(entries)} experiments registered")


# --- Phase 2: the reliability lab (A00, A02-A10, A12) -------------------------------------------


def reliability(args: argparse.Namespace) -> None:
    """Every Phase A experiment on the audit run's validated observations; descriptive only."""
    from arbit_model.dvp import lab

    config = json.loads(args.config.read_text())
    base = json.loads((ROOT / config["base"]).read_text())
    started = datetime.now(UTC)
    run = args.run
    run_manifest = json.loads((run / "run-manifest.json").read_text())
    if run_manifest["targetsIndex"] != base["targets_index"]:
        raise SystemExit("the audit run read a different targets index from the configured one")
    for name, digest in run_manifest["outputs"].items():
        if sha256(run / name) != digest:
            raise SystemExit(f"{name} changed since the audit run wrote it")
    observations = contract.enforce(
        pl.read_parquet(run / "observations.parquet"),
        json.loads((ROOT / "config/dvp/base.json").read_text())["expected_scoring"],
    )
    schedule = pl.read_parquet(run / "schedule_games.parquet")
    seed, reps = base["random_seed"], base["bootstrap_replicates"]
    min_games = base["min_split_half_games"]
    out = run / "reliability"
    out.mkdir(exist_ok=True)

    def boot(result: Any, clusters: Any) -> dict[str, Any]:
        return lab.cluster_bootstrap(result, clusters, reps, seed)

    def unit_seasons(g: Any, result: Any) -> Any:
        import numpy as np

        return np.asarray([g.keys[i][1] for i in result.unit_index])

    def summary(result: Any) -> dict[str, Any]:
        return {
            "units": result.units,
            "pearson": None if result.r is None else round(result.r, 4),
            "meanHalfGames": None if result.m is None else round(result.m, 3),
            "k": None if result.k is None else round(result.k, 2),
        }

    def calendar(frame: pl.DataFrame, with_boot: bool = True) -> dict[str, Any]:
        g = lab.groups(frame)
        result = lab.split(g, lab.assignment(g, "calendar"), min_games)
        entry = summary(result)
        if with_boot and result.r is not None:
            entry["bootstrapSeasons"] = boot(result, unit_seasons(g, result))
        return entry

    results: dict[str, Any] = {e: {} for e in config["experiments"]}
    plots: dict[str, Any] = {"scatter": {}, "forest": [], "weights": [], "lags": [], "nulls": []}
    carry_rows: list[tuple[str, str, float | None, float | None, float | None]] = []
    joint: dict[str, Any] = {}
    joint_seasons: dict[str, Any] = {}
    contributions = _contribution_cells(args.targets, base, observations)

    for pos in base["position_groups"]:
        frame = lab.position_frame(observations, schedule, pos)
        raw = lab.adjust(frame, "none")
        centered = lab.adjust(frame, "season")
        adjusted = lab.adjust(frame, config["adjusted"])
        g_raw, g_cen, g_adj = lab.groups(raw), lab.groups(centered), lab.groups(adjusted)
        cal_raw = lab.split(g_raw, lab.assignment(g_raw, "calendar"), min_games)
        cal_adj = lab.split(g_adj, lab.assignment(g_adj, "calendar"), min_games)
        seasons_adj = unit_seasons(g_adj, cal_adj)

        # A00: the landscape.
        per_season = (
            frame.group_by("season")
            .agg(pl.col("points").mean().round(3).alias("mean"))
            .sort("season")
        )
        results["A00"][pos] = lab.landscape(frame) | {
            "seasonMeans": dict(
                zip(map(str, per_season["season"]), per_season["mean"], strict=True)
            ),
            "rankAgreement": lab.rank_agreement(raw, adjusted),
        }

        # A02: split methods, random splits and minimum games.
        a02: dict[str, Any] = {}
        for kind, g in (("raw", g_raw), ("adjusted", g_adj)):
            entry: dict[str, Any] = {}
            for method in lab.SPLITS:
                result = lab.split(g, lab.assignment(g, method), min_games)
                entry[method] = summary(result)
                if result.r is not None:
                    entry[method]["bootstrapSeasons"] = boot(result, unit_seasons(g, result))
            entry["random"] = lab.random_splits(g, config["random_splits"], seed, min_games)
            entry["minGames"] = {
                str(n): summary(lab.split(g, lab.assignment(g, "calendar"), n))
                for n in config["min_games_sensitivity"]
            }
            a02[kind] = entry
        results["A02"][pos] = a02

        # A03: what the cell is adjusted for.
        faced = lab.adjust(
            frame.rename({"entity": "_faced", "faced": "entity"}).rename({"_faced": "faced"}),
            "season",
        )
        k_faced = lab.reml_components(lab.groups(faced)).k
        a03: dict[str, Any] = {"kFaced": None if k_faced is None else round(k_faced, 2)}
        for method in lab.ADJUSTMENTS:
            variant = lab.adjust(frame, method, k_faced if method == "loo_shrunk" else None)
            g = lab.groups(variant)
            a03[method] = calendar(variant) | {"reml": lab.reml_components(g).summary()}
        results["A03"][pos] = a03

        # A05: variance components with each unit's own game count.
        a05: dict[str, Any] = {}
        for kind, g in (("raw", g_raw), ("seasonCentered", g_cen), ("adjusted", g_adj)):
            reml = lab.reml_components(g)
            entry = {
                "momentMethod": lab.anova_components(g).summary(),
                "reml": reml.summary(),
            }
            if kind != "raw":
                entry["remlBootstrapSeasons"] = lab.bootstrap_components(
                    g, reps, seed, lab.reml_components
                )
            split_result = cal_raw if kind == "raw" else (cal_adj if kind == "adjusted" else None)
            if split_result is not None and reml.k is not None:
                entry["oddEvenObserved"] = round(split_result.r or 0, 4)
                entry["oddEvenImpliedByReml"] = round(
                    lab.implied_split_r(split_result.a_n, split_result.b_n, reml.k), 4
                )
            a05[kind] = entry
        a05["seasonEffect"] = lab.season_component(g_raw)
        results["A05"][pos] = a05

        # A04: stability by era and half size; position orderings come after the loop.
        a04: dict[str, Any] = {"eras": {}, "halfSize": {}}
        for era, seasons in config["eras"].items():
            a04["eras"][era] = {
                kind: calendar(variant.filter(pl.col("season").is_in(seasons)))
                for kind, variant in (("raw", raw), ("adjusted", adjusted))
            }
        smallest = cal_adj.a_n.clip(max=cal_adj.b_n)
        for label, mask in (("bothHalves8Plus", smallest >= 8), ("aHalfUnder8", smallest < 8)):
            r = lab.corr(cal_adj.a_mean[mask], cal_adj.b_mean[mask])
            a04["halfSize"][label] = {
                "units": int(mask.sum()),
                "pearson": None if r is None else round(r, 4),
            }
        reml_adj = a05["adjusted"]["reml"]
        k_boot = a05["adjusted"]["remlBootstrapSeasons"]["k95"]
        a04["weights"] = {
            str(n): {
                "w": _r4(rel.weight(n, reml_adj["k"])),
                "low": _r4(rel.weight(n, k_boot[1])) if k_boot else None,
                "high": _r4(rel.weight(n, k_boot[0])) if k_boot else None,
            }
            for n in config["weight_curve_games"]
        }
        results["A04"][pos] = a04
        joint[pos], joint_seasons[pos] = cal_adj, seasons_adj

        # A06: within-season time.
        a06: dict[str, Any] = {}
        for kind, g, k in (
            ("seasonCentered", g_cen, a05["seasonCentered"]["reml"]["k"]),
            ("adjusted", g_adj, reml_adj["k"]),
        ):
            chrono = lab.split(g, lab.assignment(g, "chronological"), min_games)
            odd_even = lab.split(g, lab.assignment(g, "calendar"), min_games)
            profile = lab.lag_profile(g)
            a06[kind] = {
                "oddEven": summary(odd_even),
                "firstVsSecondHalf": summary(chrono),
                "oddEvenMinusHalves": _paired_difference(
                    lab,
                    odd_even,
                    unit_seasons(g, odd_even),
                    chrono,
                    unit_seasons(g, chrono),
                    reps,
                    seed,
                ),
                "lag": profile["bins"],
                "lag95": lab.lag_bootstrap(profile, reps, seed),
                "rolling": [
                    lab.rolling_window(g, w) | {"impliedByReml": _r4(lab.implied_window_r(k, w))}
                    for w in config["rolling_windows"]
                ],
            }
        results["A06"][pos] = a06

        # A07: between seasons.
        a07: dict[str, Any] = {}
        for kind, variant, k in (
            ("seasonCentered", centered, a05["seasonCentered"]["reml"]["k"]),
            ("adjusted", adjusted, reml_adj["k"]),
        ):
            pairs = lab.carryover(variant, config["carryover_min_games"])
            entry = lab.carryover_summary(pairs) | _carry_boot(lab, pairs, reps, seed)
            if k is not None and entry["pearson"] is not None:
                lam = 1 / k
                rel1 = (pairs["n"] * lam / (1 + pairs["n"] * lam)).mean()
                rel2 = (pairs["next_n"] * lam / (1 + pairs["next_n"] * lam)).mean()
                entry["persistence"] = round(entry["pearson"] / (rel1 * rel2) ** 0.5, 4)
            a07[kind] = entry
        results["A07"][pos] = a07
        lo, hi = a07["adjusted"].get("pearson95") or [None, None]
        carry_rows.append((f"{pos} adjusted", pos, a07["adjusted"]["pearson"], lo, hi))

        # A08: nulls and resampling schemes.
        a08: dict[str, Any] = {}
        for kind, variant in (("raw", raw), ("adjusted", adjusted)):
            null = lab.permutation_null(variant, config["permutations"], seed, min_games)
            values = null.pop("_values")
            pl.DataFrame({"r": values}).write_parquet(out / f"null-{pos}-{kind}.parquet")
            a08[kind] = {"permutation": null}
            if kind == "adjusted":
                plots["nulls"].append((pos, pos, values.tolist(), null["observed"]))
        import numpy as np

        entities = np.asarray([g_adj.keys[i][0] for i in cal_adj.unit_index])
        a08["adjusted"]["bootstrap"] = {
            "unit": boot(cal_adj, np.arange(cal_adj.units)),
            "season": boot(cal_adj, seasons_adj),
            "franchise": boot(cal_adj, entities),
        }
        results["A08"][pos] = a08

        # A09: which part of the points repeats.
        results["A09"][pos] = _components(
            lab, frame, contributions.get(pos), pos == obs.DST, min_games
        )

        # A10: robustness and influence.
        a10: dict[str, Any] = {}
        for kind, variant in (("raw", raw), ("adjusted", adjusted)):
            subsets = {"all": variant} | {
                f"exclude{s}": variant.filter(pl.col("season") != s)
                for s in config["exclude_seasons"]
            }
            entry = {name: calendar(part, with_boot=False) for name, part in subsets.items()}
            loso = [
                calendar(variant.filter(pl.col("season") != s), with_boot=False)
                for s in base["seasons"]
            ]
            entry["leaveOneSeasonOut"] = {
                "pearsonMin": min(e["pearson"] for e in loso),
                "pearsonMax": max(e["pearson"] for e in loso),
                "kMin": min(e["k"] for e in loso if e["k"] is not None),
                "kMax": max(e["k"] for e in loso if e["k"] is not None),
            }
            entry["winsorized"] = calendar(
                lab.winsorize(variant, *config["winsorize"]), with_boot=False
            )
            entry["trimmed"] = calendar(lab.trim(variant, config["trim_sd"]), with_boot=False)
            g = lab.groups(variant)
            result = lab.split(g, lab.assignment(g, "calendar"), min_games)
            entry["influence"] = lab.influence(result) | {
                "worstUnitKey": list(g.keys[lab.influence(result)["worstUnit"]])
            }
            biggest = variant.with_columns(pl.col("value").abs().alias("_abs")).sort("_abs").tail(1)
            without = variant.join(
                biggest.select("game_id", "entity"), on=["game_id", "entity"], how="anti"
            )
            entry["withoutLargestCell"] = calendar(without, with_boot=False) | {
                "cell": biggest.select("game_id", "entity", pl.col("value").round(2)).row(
                    0, named=True
                )
            }
            a10[kind] = entry
        a10["adjusted"]["homeAway"] = a02["adjusted"]["home_away"]
        a10["adjusted"]["afterBye"] = _after_bye(adjusted)
        results["A10"][pos] = a10

        # A12: refused lines kept as partial sums (v0's handling) against excluding them.
        results["A12"][pos] = _refusal_sensitivity(
            lab, observations, schedule, pos, config["adjusted"], min_games
        )

        # Plots.
        plots["scatter"][pos] = (cal_adj.a_mean.tolist(), cal_adj.b_mean.tolist(), cal_adj)
        for label, value, interval in (
            (
                "odd/even",
                a02["adjusted"]["calendar"]["k"],
                a02["adjusted"]["calendar"].get("bootstrapSeasons", {}).get("k95"),
            ),
            ("REML", reml_adj["k"], k_boot),
            (
                "1st/2nd half",
                a02["adjusted"]["chronological"]["k"],
                a02["adjusted"]["chronological"].get("bootstrapSeasons", {}).get("k95"),
            ),
        ):
            plots["forest"].append((f"{pos} {label}", pos, value, *(interval or [None, None])))
        weights = a04["weights"]
        plots["weights"].append(
            (
                pos,
                pos,
                [int(n) for n in weights],
                [weights[n]["w"] or 0 for n in weights],
                [weights[n]["low"] or 0 for n in weights],
                [weights[n]["high"] or 0 for n in weights],
            )
        )
        lag = a06["adjusted"]
        centers = [(a + b) / 2 for a, b in lab.LAG_BINS]
        plots["lags"].append(
            (
                pos,
                pos,
                centers,
                [lag["lag"][f"{a}-{b}"]["reliability"] or 0 for a, b in lab.LAG_BINS],
                [(lag["lag95"][f"{a}-{b}"] or [0, 0])[0] for a, b in lab.LAG_BINS],
                [(lag["lag95"][f"{a}-{b}"] or [0, 0])[1] for a, b in lab.LAG_BINS],
            )
        )

    results["A04"]["orderings"] = lab.joint_orderings(joint, joint_seasons, reps, seed)
    tests = {
        f"{pos}_{kind}": results["A08"][pos][kind]["permutation"]["pValue"]
        for pos in base["position_groups"]
        for kind in ("raw", "adjusted")
    }
    results["A08"]["holm"] = _holm(tests)
    if "A12" in results:
        results["A12"]["vintages"] = _vintage_diagnostic(base, config)

    report = {
        "format": FORMAT + "-reliability-v1",
        "generatedAt": started.isoformat(),
        "code": code_version(),
        "auditRun": run.name,
        "targetsIndex": base["targets_index"],
        "config": {"path": str(args.config), "sha256": sha256(args.config)},
        "seed": seed,
        "bootstrapReplicates": reps,
        "adjusted": config["adjusted"],
        "minSplitHalfGames": min_games,
        "results": results,
        "forbidden_vendor_projection_dependencies": 0,
    }
    write_json(args.receipts / "reliability-results.json", report)
    _write_plots(plots, carry_rows, args.receipts / "plots")
    print(f"reliability: {len(base['position_groups'])} groups, {len(results)} experiments")


def _holm(p_values: dict[str, float]) -> dict[str, Any]:
    """Holm's step-down adjustment across the permutation tests (exploratory family)."""
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (name, p) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - rank) * p))
        adjusted[name] = round(running, 5)
    return {"family": len(ordered), "adjusted": dict(sorted(adjusted.items()))}


def _r4(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _paired_difference(
    lab: Any, a: Any, seasons_a: Any, b: Any, seasons_b: Any, reps: int, seed: int
) -> dict[str, Any]:
    """r(a) - r(b) with a season-cluster interval: whole seasons resampled for both together."""
    import numpy as np

    seasons = np.unique(np.concatenate([seasons_a, seasons_b]))
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(reps):
        picks = seasons[rng.integers(0, seasons.size, seasons.size)]
        ia = np.concatenate([np.flatnonzero(seasons_a == s) for s in picks])
        ib = np.concatenate([np.flatnonzero(seasons_b == s) for s in picks])
        ra = lab.corr(a.a_mean[ia], a.b_mean[ia])
        rb = lab.corr(b.a_mean[ib], b.b_mean[ib])
        if ra is not None and rb is not None:
            diffs.append(ra - rb)
    point = (a.r or 0) - (b.r or 0)
    return {"difference": round(point, 4), "interval95": lab.interval95(diffs)}


def _carry_boot(lab: Any, pairs: pl.DataFrame, reps: int, seed: int) -> dict[str, Any]:
    import numpy as np

    x = pairs.get_column("mean").to_numpy()
    y = pairs.get_column("next_mean").to_numpy()
    seasons = pairs.get_column("season").to_numpy()
    labels = np.unique(seasons)
    rng = np.random.default_rng(seed)
    rs, slopes = [], []
    for _ in range(reps):
        picks = labels[rng.integers(0, labels.size, labels.size)]
        index = np.concatenate([np.flatnonzero(seasons == s) for s in picks])
        r = lab.corr(x[index], y[index])
        if r is not None:
            rs.append(r)
        slope = lab.slope(x[index], y[index])
        if slope is not None:
            slopes.append(slope)
    return {"pearson95": lab.interval95(rs), "slope95": lab.interval95(slopes)}


def _after_bye(adjusted: pl.DataFrame) -> dict[str, Any]:
    gaps = adjusted.sort("entity", "season", "week").with_columns(
        (pl.col("week") - pl.col("week").shift(1).over("entity", "season")).alias("gap")
    )
    after = gaps.filter(pl.col("gap") > 1).get_column("value").drop_nulls()
    regular = gaps.filter(pl.col("gap") == 1).get_column("value").drop_nulls()
    difference = float(after.mean()) - float(regular.mean())  # type: ignore[arg-type]
    se = (float(after.var()) / after.len() + float(regular.var()) / regular.len()) ** 0.5  # type: ignore[arg-type]
    return {
        "afterByeCells": after.len(),
        "otherCells": regular.len(),
        "meanDifference": round(difference, 3),
        "approxSe": round(se, 3),
    }


COMPONENTS = {
    "passing.yards": "pass_yards",
    "passing.touchdowns": "pass_td",
    "passing.interceptions": "turnovers",
    "misc.fumbles_lost": "turnovers",
    "rushing.yards": "rush_yards",
    "rushing.touchdowns": "rush_td",
    "receiving.receptions": "receptions",
    "receiving.yards": "rec_yards",
    "receiving.touchdowns": "rec_td",
    "passing.two_point_conversions": "two_point",
    "rushing.two_point_conversions": "two_point",
    "receiving.two_point_conversions": "two_point",
    "kicking.field_goals_0_39": "field_goals",
    "kicking.field_goals_40_49": "field_goals",
    "kicking.field_goals_50_59": "field_goals",
    "kicking.field_goals_60_plus": "field_goals",
    "kicking.field_goals_missed": "fg_missed",
    "kicking.extra_points_made": "extra_points",
    "defense.sacks": "sacks",
    "defense.interceptions": "takeaways",
    "defense.fumbles_recovered": "takeaways",
    "defense.points_allowed": "points_allowed_tier",
    "defense.yards_allowed": "yards_allowed_tier",
    "defense.safeties": "safeties_blocks",
    "defense.blocked_kicks": "safeties_blocks",
    "returns.kickoff_touchdowns": "return_td",
    "returns.punt_touchdowns": "return_td",
    "returns.interception_touchdowns": "return_td",
    "returns.fumble_touchdowns": "return_td",
    "returns.blocked_kick_touchdowns": "return_td",
    "misc.fumble_recovery_touchdowns": "return_td",
}


def _contribution_cells(
    targets: Path, base: dict[str, Any], observations: pl.DataFrame
) -> dict[str, pl.DataFrame]:
    """Each valid cell's FFA points split by scoring component, from the rule contributions."""
    index = load_index(targets, base["targets_index"])
    parts: dict[str, list[pl.DataFrame]] = {"athlete": [], "defense": []}
    for season in base["seasons"]:
        manifest = season_manifest(targets, index, season)
        for role in ("athlete", "defense"):
            digest = manifest["tables"][role]["parquet"]
            path = verified_object(targets, digest)
            spec = SOURCES[f"ffa_targets.{role}_contributions"]
            admitted = admit(
                pl.read_parquet(path, columns=list(spec.used)),
                spec.source_id,
                ancestry=f"targets index {base['targets_index']}, season {season}, parquet {digest}",
                scoring_hash=manifest["rules"][role],
                expected_scoring=base["expected_scoring"],
                schema=list(pl.read_parquet_schema(path)),
            )
            parts[role].append(admitted.frame.filter(pl.col("season_type") == "REG"))
    component = pl.col("stat_id").replace_strict(
        COMPONENTS, default="other", return_dtype=pl.String
    )
    athlete = (
        pl.concat(parts["athlete"])
        .with_columns(
            franchise_expr(pl.col("team")).alias("offense"),
            pl.col("position")
            .cast(pl.String)
            .replace_strict(dict(POSITIONS), default=None)
            .alias("pos"),
        )
        .filter(pl.col("pos").is_not_null())
        .select("game_id", "offense", "pos", "contributions")
        .explode("contributions", empty_as_null=True)
        .drop_nulls("contributions")
        .unnest("contributions")
        .with_columns(component.alias("component"), pl.col("points").cast(pl.Float64))
        .group_by("game_id", "offense", "pos", "component")
        .agg(pl.col("points").sum())
    )
    defense = (
        pl.concat(parts["defense"])
        .with_columns(franchise_expr(pl.col("team")).alias("defense"), pl.lit("DST").alias("pos"))
        .select("game_id", "defense", "pos", "contributions")
        .explode("contributions", empty_as_null=True)
        .drop_nulls("contributions")
        .unnest("contributions")
        .with_columns(component.alias("component"), pl.col("points").cast(pl.Float64))
        .group_by("game_id", "defense", "pos", "component")
        .agg(pl.col("points").sum())
    )
    valid = observations.filter(pl.col("status") == obs.VALID)
    out: dict[str, pl.DataFrame] = {}
    for pos in (*obs.GROUPS, obs.DST):
        cells = valid.filter(pl.col("position") == pos).select("game_id", "offense", "defense")
        if pos == obs.DST:
            joined = cells.join(
                defense.filter(pl.col("pos") == pos), on=["game_id", "defense"], how="left"
            )
        else:
            joined = cells.join(
                athlete.filter(pl.col("pos") == pos), on=["game_id", "offense"], how="left"
            )
        out[pos] = (
            joined.filter(pl.col("component").is_not_null())
            .pivot(on="component", index=["game_id", "offense", "defense"], values="points")
            .fill_null(0.0)
        )
    return out


def _components(
    lab: Any, frame: pl.DataFrame, parts: pl.DataFrame | None, dst: bool, min_games: int
) -> dict[str, Any]:
    """Each scoring component's share of the cell variance and its own repeatability."""
    import numpy as np

    if parts is None or parts.is_empty():
        return {}
    keys = ("entity", "faced") if dst else ("faced", "entity")
    matched = frame.join(
        parts, left_on=["game_id", *keys], right_on=["game_id", "offense", "defense"], how="left"
    )
    if matched.height != frame.height:
        raise SystemExit("component cells do not match the observation cells one to one")
    names = sorted(c for c in parts.columns if c not in ("game_id", "offense", "defense"))
    matched = matched.with_columns(pl.col(names).fill_null(0.0))
    total = matched.get_column("points").to_numpy()
    total_var = float(np.var(total, ddof=1))
    out: dict[str, Any] = {}
    for name in names:
        values = matched.get_column(name).to_numpy()
        if float(np.var(values)) == 0:
            continue
        variant = lab.adjust(matched.with_columns(pl.col(name).alias("points")), "season")
        g = lab.groups(variant)
        result = lab.split(g, lab.assignment(g, "calendar"), min_games)
        reml = lab.reml_components(g)
        out[name] = {
            "meanPoints": round(float(values.mean()), 3),
            "varianceShare": round(float(np.cov(values, total)[0, 1]) / total_var, 3),
            "oddEvenPearson": _r4(result.r),
            "oddEvenK": None if result.k is None else round(result.k, 2),
            "remlK": None if reml.k is None else round(reml.k, 2),
            "remlBoundary": reml.boundary,
        }
    gap = total - matched.select(pl.sum_horizontal(names)).to_series().to_numpy()
    out["_check"] = {"maxAbsDifferenceFromCellPoints": round(float(np.abs(gap).max()), 6)}
    return out


def _refusal_sensitivity(
    lab: Any,
    observations: pl.DataFrame,
    schedule: pl.DataFrame,
    pos: str,
    adjusted: str,
    min_games: int,
) -> dict[str, Any]:
    """r and k with refused-line cells excluded (validated) or kept as their partial sums (v0)."""
    refused = pl.col("status") == "invalid_refused_line"
    with_partial = observations.with_columns(
        pl.when(refused).then(pl.col("points_partial")).otherwise(pl.col("points")).alias("points"),
        pl.when(refused).then(pl.lit(obs.VALID)).otherwise(pl.col("status")).alias("status"),
    )
    out: dict[str, Any] = {
        "refusedCells": observations.filter((pl.col("position") == pos) & refused).height
    }
    for label, source in (("excluded", observations), ("partialSums", with_partial)):
        frame = lab.position_frame(source, schedule, pos)
        for kind in ("none", adjusted):
            g = lab.groups(lab.adjust(frame, kind))
            result = lab.split(g, lab.assignment(g, "calendar"), min_games)
            out.setdefault(label, {})["raw" if kind == "none" else "adjusted"] = {
                "cells": g.cells,
                "units": result.units,
                "pearson": _r4(result.r),
                "k": None if result.k is None else round(result.k, 2),
            }
    return out


def _vintage_diagnostic(base: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Late stat corrections, measured where Arbit holds them: each completed game's FFA points by
    position as first known (the first nflverse version Arbit held with the game) against the
    latest version, through the point-in-time gamebooks."""
    from arbit_data.schema import dataset_manifest
    from arbit_model.gamebook import Gamebooks
    from arbit_model.point_in_time import PointInTime

    season = config["vintage_season"]
    engine = create_engine(
        os.environ["ARBIT_DATABASE_URL"],
        hide_parameters=True,
        execution_options={"postgresql_readonly": True},
    )
    with engine.connect() as c:
        payload: dict[str, Any] = c.execute(
            text(
                "select r.payload from rule_version r "
                "join league_document d on d.rules_hash = r.hash "
                "join current_snapshot s on s.snapshot_id = d.snapshot_id"
            )
        ).scalar_one()
        times: list[datetime] = sorted(
            c.execute(
                select(dataset_manifest.c.observed_at).where(
                    dataset_manifest.c.logical_key
                    == f"nflverse/nflverse-data/stats_player/stats_player_week_{season}"
                )
            ).scalars()
        )
    rules = {
        role: RuleSet.model_validate_json(json.dumps(payload[f"{role}_rules"]))
        for role in ("athlete", "defense")
    }
    hashes = {role: rs.content_hash for role, rs in rules.items()}
    if hashes != base["expected_scoring"]:
        raise SystemExit("the league's rules are not the configured scoring")
    store = ObjectStore(Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects")
    books = Gamebooks(PointInTime.from_store(UnitOfWork(engine), store), rules)

    def frames(at: datetime) -> tuple[pl.DataFrame, pl.DataFrame]:
        book = books.at(season, at)
        ancestry = f"gamebook {season} at {at.isoformat()}"
        positions = admit(
            book.position_points,
            "gamebook.position_points",
            ancestry=ancestry,
            scoring_hash=hashes["athlete"],
            expected_scoring=base["expected_scoring"],
        ).frame.select("game_id", "team", "position", "points", "refused")
        dst = admit(
            book.dst_points,
            "gamebook.dst_points",
            ancestry=ancestry,
            scoring_hash=hashes["defense"],
            expected_scoring=base["expected_scoring"],
        ).frame.select("game_id", "team", pl.lit("DST").alias("position"), "points")
        return positions, dst.with_columns(pl.lit(0, dtype=pl.UInt32).alias("refused"))

    first: dict[tuple[str, str, str], tuple[float | None, int, str]] = {}
    seen_games: set[str] = set()
    for observed in times:
        at = observed + timedelta(minutes=1)
        positions, dst = frames(at)
        both = pl.concat([positions, dst.select(positions.columns)], how="vertical_relaxed")
        new = both.filter(~pl.col("game_id").is_in(list(seen_games)))
        for row in new.iter_rows(named=True):
            first[(row["game_id"], row["team"], row["position"])] = (
                row["points"],
                int(row["refused"]),
                at.isoformat(),
            )
        seen_games |= set(new.get_column("game_id").to_list())
    now = datetime.now(UTC)
    positions, dst = frames(now)
    latest = pl.concat([positions, dst.select(positions.columns)], how="vertical_relaxed")
    rows = []
    for row in latest.iter_rows(named=True):
        key = (row["game_id"], row["team"], row["position"])
        if key in first:
            before, refused_before, at_text = first[key]
            rows.append(
                {
                    "game_id": key[0],
                    "position": key[2],
                    "first": before,
                    "latest": row["points"],
                    "firstAt": at_text,
                }
            )
    compared = pl.DataFrame(rows).with_columns(
        (pl.col("latest") - pl.col("first")).alias("change"),
        pl.col("game_id").str.slice(5, 2).cast(pl.Int32).alias("week"),
    )
    first_times = compared.group_by("week").agg(pl.col("firstAt").min()).sort("week")
    by_position: dict[str, Any] = {}
    for (pos,), part in compared.group_by(["position"], maintain_order=True):
        changes = part.get_column("change").drop_nulls()
        by_position[str(pos)] = {
            "cells": part.height,
            "changed": int((changes.abs() > 1e-9).sum()),
            "meanAbsChange": round(float(changes.abs().mean() or 0.0), 4),  # type: ignore[arg-type]
            "maxAbsChange": round(float(changes.abs().max() or 0.0), 3),  # type: ignore[arg-type]
            "changeVariance": round(float(changes.var() or 0.0), 5),  # type: ignore[arg-type]
        }
    return {
        "season": season,
        "versionsHeld": len(times),
        "firstVersionHeld": times[0].isoformat() if times else None,
        "games": compared.get_column("game_id").n_unique(),
        "firstKnownByWeek": dict(
            zip(map(str, first_times["week"]), first_times["firstAt"], strict=True)
        ),
        "byPosition": by_position,
        "limitation": "Arbit's nflverse vintages start 2026-10-31 and miss 2026-11-10 to 11-22, so "
        "games of weeks 1-7 and 10 were first held long after their corrections; their change is "
        "a lower bound. Seasons 2016-2025 have only final revisions.",
    }


def _write_plots(plots: dict[str, Any], carry_rows: list[Any], folder: Path) -> None:
    from arbit_model.dvp import svg

    folder.mkdir(parents=True, exist_ok=True)
    for pos, (xs, ys, result) in plots["scatter"].items():
        (folder / f"split-scatter-{pos}.svg").write_text(
            svg.scatter(
                f"{pos}: odd-week vs even-week means, adjusted",
                xs,
                ys,
                color=svg.COLORS[pos],
                xlabel="Odd NFL weeks: mean adjusted FFA points",
                ylabel="Even NFL weeks",
                note=f"{result.units} unit-seasons, 2016-2025; r = {result.r:.3f}; dashed: identity",
            )
        )
    (folder / "k-forest.svg").write_text(
        svg.forest(
            "Games for half signal (k), adjusted, with 95% season-bootstrap intervals",
            plots["forest"],
            xlabel="k (games, log scale)",
            xlim=(2, 1000),
            note="Odd/even and 1st/2nd half: split-half k. REML: variance components with each "
            "unit's own game count. Arrow: no upper bound.",
        )
    )
    (folder / "weight-curves.svg").write_text(
        svg.lines(
            "Weight on a unit's own record after n games, w(n) = n / (n + k)",
            plots["weights"],
            xlabel="Games played this season",
            ylabel="w(n)",
            ylim=(0, 1),
            note="k: REML, adjusted points; bands: season-bootstrap interval of k. Not a Sit/Start "
            "weight.",
        )
    )
    (folder / "lag-decay.svg").write_text(
        svg.lines(
            "Single-game reliability by weeks apart, adjusted",
            plots["lags"],
            xlabel="Weeks between two games of the same unit-season",
            ylabel="Covariance / variance",
            ylim=(-0.05, 0.25),
            note="A stable trait is flat; a drifting one decays. Bands: 95% season bootstrap.",
            xticks=[1.5, 3.5, 5.5, 7.5, 9.5, 11.5, 15],
        )
    )
    (folder / "null-distributions.svg").write_text(
        svg.histograms(
            "Odd/even r under within-week permutation (1,000 shuffles), adjusted",
            plots["nulls"],
            xlabel="split-half r",
            note="Grey: r after shuffling which unit each cell belongs to within its week. "
            "Line: the observed r.",
        )
    )
    (folder / "carryover.svg").write_text(
        svg.forest(
            "Season-to-next-season correlation of a unit's adjusted mean",
            carry_rows,
            xlabel="Pearson r (95% season bootstrap)",
            xlim=(-0.3, 0.8),
            note="Same franchise, consecutive seasons, 8+ games each.",
            log=False,
        )
    )


def _phase_a_records(
    config: dict[str, Any], receipts: Path, common: dict[str, Any], descriptive: dict[str, Any]
) -> list[dict[str, Any]]:
    """Registry records of the reliability lab, from its receipt (none before it has run)."""
    from arbit_model.dvp import results as records

    path = receipts / "reliability-results.json"
    if not path.exists():
        return []
    lab_receipt = json.loads(path.read_text())
    r = lab_receipt["results"]
    groups = config["position_groups"]
    evidence = [
        "docs/research/dvp/reliability-results.json",
        "docs/research/dvp/RELIABILITY_REPORT.md",
    ]
    shared = common | descriptive | {"code_commit": lab_receipt["code"]}

    def per(fn: Any) -> dict[str, Any]:
        return {pos: fn(pos) for pos in groups}

    reml = per(lambda p: r["A05"][p]["adjusted"]["reml"]["k"])
    reml95 = per(lambda p: r["A05"][p]["adjusted"]["remlBootstrapSeasons"]["k95"])
    specs: list[tuple[str, str, str, dict[str, Any], dict[str, Any]]] = [
        (
            "A00",
            "Raw DvP landscape: distributions, unit-season spread and raw vs adjusted ranks",
            "descriptive statistics per position; per-season Spearman of raw vs adjusted ranks",
            per(
                lambda p: (
                    {
                        k: r["A00"][p][k]
                        for k in (
                            "cells",
                            "mean",
                            "sd",
                            "skew",
                            "unitSeasonMeanSd",
                            "withinUnitSeasonSd",
                        )
                    }
                    | {"rankSpearmanMean": r["A00"][p]["rankAgreement"]["spearmanMean"]}
                )
            ),
            {"tests_passed": ["T03", "T04"]},
        ),
        (
            "A02",
            "Split-method sensitivity of the repeatability estimate",
            "split-half r and k for odd/even weeks, alternating games, first vs second half, "
            "first 6 vs next 6, home vs away and 1,000 seeded balanced random splits",
            per(
                lambda p: (
                    {
                        m: r["A02"][p]["adjusted"][m]["k"]
                        for m in (
                            "calendar",
                            "alternating",
                            "chronological",
                            "first6_next6",
                            "home_away",
                        )
                    }
                    | {"randomMedian": r["A02"][p]["adjusted"]["random"]["k"]["median"]}
                )
            ),
            {"tests_passed": ["T09", "T10", "T13"]},
        ),
        (
            "A03",
            "Opponent-adjustment sensitivity of repeatability",
            "odd/even k and REML k for none, season-centered, leave-one-out mean, leave-one-out "
            "median and leave-one-out mean shrunk toward the season mean",
            per(
                lambda p: {
                    m: r["A03"][p][m]["reml"]["k"]
                    for m in ("none", "season", "loo_mean", "loo_median", "loo_shrunk")
                }
            ),
            {"tests_passed": ["T08"]},
        ),
        (
            "A04",
            "Position-specific stability by era and half size, with joint orderings",
            "odd/even k by era with season-bootstrap intervals; joint season bootstrap of which "
            "position's k is lower",
            {
                "eras": per(
                    lambda p: {e: v["adjusted"]["k"] for e, v in r["A04"][p]["eras"].items()}
                ),
                "pKLower": r["A04"]["orderings"]["pKLower"],
            },
            {"tests_passed": ["T13"]},
        ),
        (
            "A05",
            "Variance components with each unit's own game count, compared with v0's k",
            "one-way random effects by unit-season: method of moments and REML, season-cluster "
            "bootstrap of the REML k",
            {"remlK": reml, "remlK95Seasons": reml95},
            {"tests_passed": ["T11", "T12", "T14"], "interval": reml95},
        ),
        (
            "A06",
            "Temporal stability within a season",
            "odd/even minus first-vs-second-half r with a paired season bootstrap; covariance by "
            "weeks apart; rolling-window correlations against the stable-trait model",
            per(lambda p: r["A06"][p]["adjusted"]["oddEvenMinusHalves"]),
            {"tests_passed": ["T23"]},
        ),
        (
            "A07",
            "Between-season carryover of a unit's tendency",
            "same-franchise consecutive-season means (8+ games): r, slope and leave-one-season-out "
            "error of a decayed prior against a reset",
            per(
                lambda p: {
                    k: r["A07"][p]["adjusted"][k]
                    for k in ("pearson", "pearson95", "slope", "cvMseDecay", "cvMseReset")
                }
            ),
            {},
        ),
        (
            "A08",
            "Noise, placebo and null distributions",
            "1,000 within-week permutations of unit labels; Holm across 12 tests; unit, season and "
            "franchise cluster bootstraps",
            per(
                lambda p: {k: r["A08"][p][k]["permutation"]["pValue"] for k in ("raw", "adjusted")}
            ),
            {"tests_passed": ["T13", "T24"], "placebo_summary": r["A08"]["holm"]},
        ),
        (
            "A09",
            "Which part of the points repeats: yards, receptions, touchdowns, turnovers, kicking",
            "the scorer's rule contributions summed per cell; variance share and REML k per component",
            per(
                lambda p: {
                    c: v["remlK"]
                    for c, v in r["A09"][p].items()
                    if c != "_check" and abs(v["varianceShare"]) >= 0.05
                }
            ),
            {},
        ),
        (
            "A10",
            "Era and data robustness, and one unit's influence",
            "odd/even k excluding 2020 or 2022, leaving out each season, winsorized, trimmed, without "
            "the largest cell; jackknife influence; home/away; after a bye",
            per(lambda p: r["A10"][p]["adjusted"]["leaveOneSeasonOut"]),
            {"tests_passed": ["T28"]},
        ),
        (
            "A12",
            "Completion and correction sensitivity",
            "refused-line cells excluded vs kept as partial sums; 2026 FFA points as first held vs "
            "latest through the point-in-time gamebooks",
            {
                "refusal": per(
                    lambda p: {
                        k: r["A12"][p][k]["adjusted"]["k"] for k in ("excluded", "partialSums")
                    }
                ),
                "vintages2026": r["A12"]["vintages"]["byPosition"],
            },
            {"limitations": [r["A12"]["vintages"]["limitation"]]},
        ),
    ]
    out = []
    for code, hypothesis, estimator, parameters, extra in specs:
        out.append(
            records.record(
                f"M3-3-{code}",
                "EXECUTED",
                hypothesis=hypothesis,
                estimator=estimator,
                parameters=parameters,
                sample_count=lab_receipt["results"]["A00"][groups[0]]["cells"]
                if code == "A00"
                else {p: r["A02"][p]["adjusted"]["calendar"]["units"] for p in groups},
                evidence_paths=evidence,
                reason="See RELIABILITY_REPORT.md: descriptive repeatability only, no forecast",
                next_steps="Phase B walk-forward against the offense-only B00",
                **(shared | extra),
            )
        )
    return out


# --- Phase 3: the walk-forward backtest (B00-B12) ---------------------------------------------

TOUCHDOWN_COMPONENTS = ("pass_td", "rush_td", "rec_td", "return_td")


def backtest(args: argparse.Namespace) -> None:
    """Development folds (2017-2023, with tuning) or the 2024 validation from frozen candidates.
    The holdout (2025) is refused here."""
    from arbit_model.dvp import asof
    from arbit_model.dvp import walkforward as wf

    config = json.loads(args.config.read_text())
    base = json.loads((ROOT / config["base"]).read_text())
    stage = args.stage
    seasons: list[int] = config["stages"][stage]
    started = datetime.now(UTC)
    run = args.run
    frozen_manifest: dict[str, Any] | None = None
    blocked: str | None = None
    if stage == "holdout":
        frozen_manifest = json.loads((ROOT / config["frozen"]).read_text())
        mismatches = _verify_frozen(frozen_manifest, run, base)
        if mismatches:
            blocked = "frozen manifest does not match: " + "; ".join(mismatches)
            raise SystemExit(blocked)
    wf.check_stage(stage, seasons, base["split"], frozen_verified=frozen_manifest is not None)
    run_manifest = json.loads((run / "run-manifest.json").read_text())
    if run_manifest["targetsIndex"] != base["targets_index"]:
        raise SystemExit("the audit run read a different targets index from the configured one")
    for name, digest in run_manifest["outputs"].items():
        if sha256(run / name) != digest:
            raise SystemExit(f"{name} changed since the audit run wrote it")
    observations = contract.enforce(
        pl.read_parquet(run / "observations.parquet"),
        json.loads((ROOT / "config/dvp/base.json").read_text())["expected_scoring"],
    )
    schedule = pl.read_parquet(run / "schedule_games.parquet")
    observations = _with_nontd(observations, _contribution_cells(args.targets, base, observations))
    rows = wf.prepare(observations)
    positions: list[str] = base["position_groups"]
    seed, reps = base["random_seed"], base["bootstrap_replicates"]
    candidates_path = ROOT / config["candidates"]
    candidates = None
    if stage in ("validation", "holdout"):
        if not candidates_path.exists():
            raise SystemExit("validation needs the candidates frozen after development")
        candidates = json.loads(candidates_path.read_text())

    def run_stage(settings: Any) -> tuple[pl.DataFrame, dict[str, Any]]:
        joined, folds = [], {}
        for season in seasons:
            params = wf.fit_fold(rows, season, positions)
            frozen = wf.walk(rows, schedule, params, positions, settings)
            joined.append(wf.evaluate(frozen, rows, season))
            folds[str(season)] = params.summary()
        return pl.concat(joined), folds

    settings = wf.Settings(
        mode=asof.Cutoff(config["cutoff"]),
        k_grid=tuple(config["k_grid"]),
        half_lives=tuple(config["half_lives"]),
        seed=seed,
    )
    joined, folds = run_stage(settings)
    out = run / f"backtest-{stage}"
    out.mkdir(exist_ok=True)
    write_forecasts(out / "forecasts.parquet", joined)
    block = "season" if len(seasons) > 1 else "week"
    variants = sorted(c for c in joined.columns if c.startswith("b0") and c not in ("b00_nontd",))
    week_bin = _bin_expr("week", config["week_bins"])
    history_bin = _bin_expr("n_d", config["history_bins"])
    by_position: dict[str, Any] = {}
    for pos in positions:
        part = joined.filter(pl.col("position") == pos).with_columns(
            week_bin.alias("weekBin"), history_bin.alias("historyBin")
        )
        entry = wf.metrics(part, variants, block=block, reps=reps, seed=seed)
        entry["calibrationB00"] = wf.calibration(part, "b00")
        by_position[pos] = entry
    selection = _select(by_position, positions, config) if stage == "development" else None
    chosen = selection if selection is not None else candidates
    assert chosen is not None
    for pos in positions:
        part = joined.filter(pl.col("position") == pos).with_columns(
            week_bin.alias("weekBin"), history_bin.alias("historyBin")
        )
        focus = chosen["positions"][pos]["bestDvp"]
        by_position[pos]["focus"] = {
            "variant": focus,
            "bySeason": wf.breakdown(part, focus, "season"),
            "byWeek": wf.breakdown(part, focus, "weekBin"),
            "byOpponentGames": wf.breakdown(part, focus, "historyBin"),
            "calibration": wf.calibration(part, focus),
        }

    # B10: per-game cutoffs; B12: a slower availability rule. B00 and B03 only; not on the holdout.
    sensitivity: dict[str, Any] = {}
    for label, variant_settings in (
        ()
        if stage == "holdout"
        else (
            (
                "B10_perGame",
                wf.Settings(mode=asof.Cutoff.PER_GAME, k_grid=(), half_lives=(), seed=seed),
            ),
            (
                "B12_delay48h",
                wf.Settings(
                    mode=asof.Cutoff(config["cutoff"]),
                    k_grid=(),
                    half_lives=(),
                    availability_delay=timedelta(hours=config["availability_delay_hours_b12"]),
                    seed=seed,
                ),
            ),
        )
    ):
        alt, _ = run_stage(variant_settings)
        compare = joined.select(
            "game_id",
            "offense",
            "position",
            "season",
            "week",
            "points",
            pl.col("b00").alias("b00_default"),
            pl.col("b03").alias("b03_default"),
            pl.col("n_d").alias("n_d_default"),
        ).join(
            alt.select("game_id", "offense", "position", "b00", "b03", "n_d"),
            on=["game_id", "offense", "position"],
            how="inner",
        )
        sensitivity[label] = {
            pos: _sensitivity(compare.filter(pl.col("position") == pos), block, reps, seed)
            for pos in positions
        }

    report = {
        "format": FORMAT + f"-backtest-{stage}-v1",
        "generatedAt": started.isoformat(),
        "code": code_version(),
        "auditRun": run.name,
        "targetsIndex": base["targets_index"],
        "config": {"path": str(args.config), "sha256": sha256(args.config)},
        "polarsMaxThreads": os.environ.get("POLARS_MAX_THREADS"),
        "stage": stage,
        "seasons": seasons,
        "cutoff": config["cutoff"],
        "seed": seed,
        "bootstrapReplicates": reps,
        "bootstrapBlock": block,
        "practicalMinimumRelativeRmse": config["practical_minimum_relative_rmse"],
        "folds": folds,
        "results": by_position,
        "sensitivity": sensitivity,
        "forecastsSha256": sha256(out / "forecasts.parquet"),
        "forecastsContentSha256": content_sha256(pl.read_parquet(out / "forecasts.parquet")),
        "forbidden_vendor_projection_dependencies": 0,
        "holdout": "not run: 2025 needs a frozen manifest (Phase 4)",
    }
    if stage == "development":
        assert selection is not None
        report["selection"] = selection
        write_json(args.receipts / "backtest-development.json", report)
        frozen = {
            "format": FORMAT + "-frozen-candidates-v1",
            "frozenAt": started.isoformat(),
            "fromDevelopment": {
                "receipt": "docs/research/dvp/backtest-development.json",
                "code": report["code"],
                "auditRun": run.name,
                "forecastsSha256": report["forecastsSha256"],
            },
            "practicalMinimumRelativeRmse": config["practical_minimum_relative_rmse"],
        } | selection
        if candidates_path.exists():
            # Frozen inputs are never rewritten: a rerun must select the same candidates.
            existing = json.loads(candidates_path.read_text())
            fresh = json.loads(json.dumps(selection, default=str))
            if {key: existing.get(key) for key in fresh} != fresh:
                raise SystemExit(
                    f"development selected other candidates than the frozen {candidates_path}; "
                    "refusing to rewrite it"
                )
            print(f"{candidates_path.name}: selection reproduced; frozen file left unchanged")
        else:
            write_json(candidates_path, frozen)
    elif stage == "validation":
        assert candidates is not None
        report["candidates"] = {
            "path": config["candidates"],
            "sha256": sha256(candidates_path),
            "frozenAt": candidates["frozenAt"],
        }
        report["validationOfCandidates"] = {
            pos: _validate_candidate(by_position[pos], candidates["positions"][pos], config)
            for pos in positions
        }
        write_json(args.receipts / "backtest-validation.json", report)
    else:
        assert candidates is not None and frozen_manifest is not None
        report["candidates"] = {
            "path": config["candidates"],
            "sha256": sha256(candidates_path),
            "frozenAt": candidates["frozenAt"],
        }
        report["frozenManifest"] = {
            "path": config["frozen"],
            "sha256": sha256(ROOT / config["frozen"]),
            "frozenAt": frozen_manifest["frozenAt"],
        }
        report["holdoutStatus"] = frozen_manifest["holdout"]["status"]
        expected = rows.filter(pl.col("season").is_in(seasons)).height
        coverage_problem = (
            None if joined.height == expected else f"{joined.height} forecasts for {expected} cells"
        )
        report["decisions"] = _decisions(by_position, frozen_manifest, positions, coverage_problem)
        write_json(args.receipts / "backtest-holdout.json", report)
    print(f"backtest {stage}: {joined.height} forecasts over {seasons}")


def _with_nontd(observations: pl.DataFrame, parts: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Each valid cell's points without touchdown components (for B07)."""
    frames = []
    for pos, table in parts.items():
        touchdowns = [c for c in TOUCHDOWN_COMPONENTS if c in table.columns]
        frames.append(
            table.select(
                "game_id",
                "offense",
                "defense",
                pl.lit(pos).alias("position"),
                pl.sum_horizontal([pl.col(c) for c in touchdowns] or [pl.lit(0.0)]).alias("_td"),
            )
        )
    tds = pl.concat(frames)
    joined = observations.join(tds, on=["game_id", "offense", "defense", "position"], how="left")
    return joined.with_columns(
        pl.when(pl.col("status") == obs.VALID)
        .then(pl.col("points") - pl.col("_td").fill_null(0.0))
        .otherwise(None)
        .alias("nontd")
    ).drop("_td")


def _bin_expr(column: str, bins: list[list[int]]) -> pl.Expr:
    expr = pl.lit(None, dtype=pl.String)
    for low, high in reversed(bins):
        expr = (
            pl.when(pl.col(column).fill_null(0).is_between(low, high))
            .then(pl.lit(f"{low}-{high}"))
            .otherwise(expr)
        )
    return expr


def _select(
    by_position: dict[str, Any], positions: list[str], config: dict[str, Any]
) -> dict[str, Any]:
    """Tuned settings and each position's candidate, from development folds only."""
    minimum = config["practical_minimum_relative_rmse"]
    out: dict[str, Any] = {"positions": {}}
    for pos in positions:
        result = by_position[pos]
        k_best = min(
            (name for name in result if name.startswith("b04_k")), key=lambda n: result[n]["rmse"]
        )
        h_best = min(
            (name for name in result if name.startswith("b05_h")), key=lambda n: result[n]["rmse"]
        )
        pool = [v for v in ("b01", "b02", "b02r", "b03", "b03r", "b06", "b07") if v in result]
        pool += [k_best, h_best]
        best = min(pool, key=lambda n: result[n]["rmse"])
        relative = result[best]["relativeDelta"]
        out["positions"][pos] = {
            "b04Selected": k_best,
            "b05Selected": h_best,
            "bestDvp": best,
            "bestRelativeDelta": relative,
            "bestDelta95": result[best]["delta95"],
            "candidate": best if relative is not None and relative <= -minimum else "b00",
            "rule": f"best DvP variant by development RMSE; candidate only if it cuts B00's RMSE by "
            f"at least {minimum:.0%}",
        }
    return out


def _validate_candidate(
    result: dict[str, Any], frozen: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    best = frozen["bestDvp"]
    entry = result[best]
    return {
        "candidate": frozen["candidate"],
        "bestDvp": best,
        "developmentRelativeDelta": frozen["bestRelativeDelta"],
        "validationRelativeDelta": entry["relativeDelta"],
        "validationDelta95": entry["delta95"],
        "sameDirection": (entry["relativeDelta"] or 0) < 0,
        "meetsPracticalMinimum": (entry["relativeDelta"] or 0)
        <= -config["practical_minimum_relative_rmse"],
    }


def _sensitivity(compare: pl.DataFrame, block: str, reps: int, seed: int) -> dict[str, Any]:
    from arbit_model.dvp import walkforward as wf

    y = compare.get_column("points").to_numpy()
    out: dict[str, Any] = {"rows": compare.height}
    for name in ("b00", "b03"):
        default = compare.get_column(f"{name}_default").to_numpy()
        alt = compare.get_column(name).to_numpy()
        out[name] = {
            "rmseDefault": round(wf._rmse(default, y), 4),
            "rmseAlternative": round(wf._rmse(alt, y), 4),
            "rowsChanged": int((abs(alt - default) > 1e-9).sum()),
        }
    for key, column in (
        ("meanOpponentGamesDefault", "n_d_default"),
        ("meanOpponentGamesAlternative", "n_d"),
    ):
        values = compare.get_column(column).fill_null(0).cast(pl.Float64).to_numpy()
        out[key] = round(float(values.mean()), 3) if values.size else None
    return out


def report(args: argparse.Namespace) -> None:
    """Plots drawn from the backtest receipts alone (nothing is recomputed)."""
    from arbit_model.dvp import svg

    receipts = args.receipts
    rows: list[tuple[str, str, float | None, float | None, float | None]] = []
    for stage in ("development", "validation", "holdout"):
        path = receipts / f"backtest-{stage}.json"
        if not path.exists():
            continue
        receipt = json.loads(path.read_text())
        chosen = receipt.get("selection") or json.loads(
            (ROOT / receipt["candidates"]["path"]).read_text()
        )
        for pos, result in receipt["results"].items():
            variant = chosen["positions"][pos]["bestDvp"]
            base = result["b00"]["rmse"]
            low, high = result[variant]["delta95"]
            rows.append(
                (
                    f"{pos} {variant.upper()} {stage[:3]}",
                    pos,
                    100 * result[variant]["relativeDelta"],
                    100 * low / base,
                    100 * high / base,
                )
            )
    stages = {"dev": 0, "val": 1, "hol": 2}
    rows.sort(key=lambda r: (r[1], stages[r[0].rsplit(" ", 1)[1]]))
    (receipts / "plots").mkdir(parents=True, exist_ok=True)
    (receipts / "plots" / "backtest-delta.svg").write_text(
        svg.forest(
            "Best DvP variant vs the offense-only B00: change in RMSE",
            rows,
            xlabel="% change in RMSE (negative is better); 95% block bootstrap",
            xlim=(-10.0, 4.0),
            note="dev: 2017-2023 folds (chosen here); val: 2024; hol: 2025 conditional holdout. Frozen in between.",
            log=False,
        )
    )
    _metrics_csv(receipts)
    _calibration_plot(receipts)
    _season_plot(receipts)
    _sitstart_plot(receipts)
    print(f"report: {len(rows)} rows")


def _receipt(receipts: Path, stage: str) -> dict[str, Any] | None:
    path = receipts / f"backtest-{stage}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _metrics_csv(receipts: Path) -> None:
    """METRICS.csv: every variant's metrics per stage and position, from the receipts."""
    frozen = json.loads((ROOT / "config/dvp/frozen-candidates.json").read_text())["positions"]
    rows = []
    for stage in STAGES:
        receipt = _receipt(receipts, stage)
        if receipt is None:
            continue
        for pos, result in receipt["results"].items():
            for variant, m in sorted(result.items()):
                if not variant.startswith("b0"):  # not "blocks"
                    continue
                rows.append(
                    {
                        "stage": stage,
                        "seasons": "-".join(
                            str(x) for x in (receipt["seasons"][0], receipt["seasons"][-1])
                        ),
                        "position": pos,
                        "variant": variant,
                        "rows": result["rows"],
                        "rmse": m["rmse"],
                        "mae": m["mae"],
                        "mean_error": m["meanError"],
                        "spearman": m["spearman"],
                        "delta_rmse_vs_b00": m["deltaRmse"],
                        "relative_delta": m["relativeDelta"],
                        "delta95_low": m["delta95"][0],
                        "delta95_high": m["delta95"][1],
                        "best_dvp": variant == frozen[pos]["bestDvp"],
                        "frozen_candidate": variant == frozen[pos]["candidate"],
                    }
                )
    pl.DataFrame(rows).write_csv(receipts / "METRICS.csv", float_precision=5)


def _calibration_plot(receipts: Path) -> None:
    """Mean forecast against mean outcome by forecast decile: B00 and the best DvP variant in
    development, and the best DvP variant in the 2025 holdout; one panel per position."""
    from arbit_model.dvp import svg

    dev, hold = _receipt(receipts, "development"), _receipt(receipts, "holdout")
    if dev is None:
        return
    frozen = json.loads((ROOT / "config/dvp/frozen-candidates.json").read_text())["positions"]
    positions = list(dev["results"])
    canvas = svg.Canvas(780, 610, "Calibration by forecast decile: mean forecast vs mean outcome")
    for i, pos in enumerate(positions):
        col, row = i % 3, i // 3
        series = [("B00 dev", dev["results"][pos]["calibrationB00"], svg.MUTED, "")]
        best = frozen[pos]["bestDvp"].upper()
        series.append(
            (f"{best} dev", dev["results"][pos]["focus"]["calibration"], svg.COLORS[pos], "")
        )
        if hold is not None:
            series.append(
                (
                    f"{best} 2025",
                    hold["results"][pos]["focus"]["calibration"],
                    svg.COLORS[pos],
                    "5 3",
                )
            )
        values = [
            v for _, table, _, _ in series for r in table for v in (r["forecast"], r["observed"])
        ]
        lim = svg._limits(values)
        left, top = 60 + col * 250, 60 + row * 265
        panel = svg.Panel(canvas, (left, top + 16, 190, 170), lim, lim)
        panel.axes("forecast", "outcome")
        panel.line([lim[0], lim[1]], [lim[0], lim[1]], svg.MUTED, 1, "2 3")
        canvas.text(left, top + 8, pos, fill=svg.INK)
        for j, (label, table, color, dash) in enumerate(series):
            xs = [r["forecast"] for r in table]
            ys = [r["observed"] for r in table]
            panel.line(xs, ys, color, 1.6, dash)
            panel.dots(xs, ys, color, 2)
            canvas.text(left + 30 + 58 * j, top + 8, label, fill=color)
    canvas.text(
        16,
        600,
        "Deciles of each variant's own forecast. Dotted: perfect calibration. Holdout dashed.",
        fill=svg.MUTED,
    )
    (receipts / "plots" / "calibration.svg").write_text(canvas.render())


def _season_plot(receipts: Path) -> None:
    """The best DvP variant's change in RMSE against B00, by season, per position."""
    from arbit_model.dvp import svg

    by: dict[str, dict[int, float]] = {}
    for stage in STAGES:
        receipt = _receipt(receipts, stage)
        if receipt is None:
            continue
        for pos, result in receipt["results"].items():
            for season, value in result["focus"]["bySeason"].items():
                by.setdefault(pos, {})[int(season)] = value["deltaRmse"]
    if not by:
        return
    series = []
    for pos, values in by.items():
        seasons = sorted(values)
        series.append((pos, pos, seasons, [values[x] for x in seasons], None, None))
    ys = [y for s in series for y in s[3]]
    seasons = sorted({x for s in series for x in s[2]})
    (receipts / "plots" / "error-by-season.svg").write_text(
        svg.lines(
            "Best DvP variant vs B00 by season: change in RMSE (points)",
            series,
            xlabel="season (2017-2023 development folds, 2024 validation, 2025 holdout)",
            ylabel="RMSE change, points (negative is better)",
            ylim=(min(min(ys), 0.0) - 0.05, max(max(ys), 0.0) + 0.05),
            note="Each position's best DvP variant as chosen on development; per-season ΔRMSE from the receipts.",
            xticks=seasons,
        )
    )


def _sitstart_plot(receipts: Path) -> None:
    """Phase C: change in pairwise start/sit accuracy, frozen candidate vs B00, per period."""
    from arbit_model.dvp import svg

    path = receipts / "sitstart.json"
    if not path.exists():
        return
    c = json.loads(path.read_text())
    rows: list[tuple[str, str, float | None, float | None, float | None]] = []
    for stage in STAGES:
        m = c["periods"][stage]
        low, high = m["deltaPp95"]
        rows.append((f"all pairs {stage[:3]}", c["position"], m["deltaPp"], low, high))
    for stage in STAGES:
        m = c["periods"][stage]
        for name, key, group in (
            ("close pairs", "close", "QB"),
            ("waiver pool", "waiverPool", "WR"),
        ):
            point = m[key].get("deltaPp")
            rows.append((f"{name} {stage[:3]}", group, point, point, point))  # point estimate only
    values = [v for r in rows for v in r[2:] if v is not None]
    (receipts / "plots" / "sitstart.svg").write_text(
        svg.forest(
            f"D/ST start/sit: {c['candidate'].upper()} vs B00, change in pairwise accuracy",
            rows,
            xlabel="percentage points (positive is better); all pairs with 95% week-block interval",
            xlim=(min(min(values), 0.0) - 1.0, max(values) + 1.0),
            note=f"Minimum {c['decision']['practicalMinimumPp']} points, declared before the run; "
            f"decision {c['decision']['label']}. Subgroups: point estimates.",
            log=False,
        )
    )


def _phase_b_records(
    config: dict[str, Any], receipts: Path, common: dict[str, Any]
) -> list[dict[str, Any]]:
    """Registry records of the walk-forward, from its receipts (none before it has run)."""
    from arbit_model.dvp import results as records

    paths = {s: receipts / f"backtest-{s}.json" for s in ("development", "validation")}
    if not all(p.exists() for p in paths.values()):
        return []
    dev = json.loads(paths["development"].read_text())
    val = json.loads(paths["validation"].read_text())
    groups = config["position_groups"]
    selection = dev["selection"]["positions"]
    evidence = [
        "docs/research/dvp/backtest-development.json",
        "docs/research/dvp/backtest-validation.json",
        "docs/research/dvp/BACKTEST_REPORT.md",
        "config/dvp/frozen-candidates.json",
    ]
    shared = common | {
        "code_commit": val["code"],
        "as_of_policy": config["as_of_policy"]["default_cutoff"],
        "train_validation_test_periods": {
            "development": dev["seasons"],
            "validation": val["seasons"],
            "holdout": "2025, not run (Phase 4 from frozen-candidates.json)",
        },
        "holdout_independence_status": "2025 exposed descriptively by v0 and Phase A: conditional "
        "holdout at best; no 2025 forecast made or inspected",
        "primary_metric": "RMSE per position on common rows",
    }

    def stat(receipt: dict[str, Any], name: str) -> dict[str, Any]:
        return {
            p: {
                "rmse": receipt["results"][p][name]["rmse"],
                "relativeDelta": receipt["results"][p][name]["relativeDelta"],
                "delta95": receipt["results"][p][name]["delta95"],
            }
            for p in groups
        }

    rows: list[tuple[str, str, list[str], dict[str, Any]]] = [
        (
            "B00",
            "Offense-only next-game forecast from prior FFA actuals: the comparator",
            ["b00"],
            {},
        ),
        ("B01", "Raw prior-games DvP added to B00, unshrunk", ["b01"], {}),
        (
            "B02",
            "Point-in-time residual DvP added to B00, unshrunk (and with recomputed baselines)",
            ["b02", "b02r"],
            {},
        ),
        ("B03", "Residual DvP shrunk with k fit on training seasons only", ["b03", "b03r"], {}),
        (
            "B04",
            "Prediction-tuned k on a declared grid (development only)",
            [f"b04_k{k:g}" for k in (1, 2, 4, 8, 16, 32, 64, 128, 256)],
            {"parameters": {p: selection[p]["b04Selected"] for p in groups}},
        ),
        (
            "B05",
            "Recency-weighted DvP with effective sample size",
            ["b05_h2", "b05_h4", "b05_h8"],
            {"parameters": {p: selection[p]["b05Selected"] for p in groups}},
        ),
        (
            "B06",
            "Dynamic DvP with a prior from last season (slope fit on training seasons)",
            ["b06"],
            {},
        ),
        ("B07", "DvP on non-touchdown points only", ["b07"], {}),
        (
            "B09",
            "Negative controls: shuffled opponents, noise, last week's opponent",
            ["b09_shuffle", "b09_noise", "b09_lastopp"],
            {"tests_passed": ["T24"]},
        ),
    ]
    out = []
    for code, hypothesis, variants, extra in rows:
        development = {v: stat(dev, v) for v in variants}
        validation = {v: stat(val, v) for v in variants}
        out.append(
            records.record(
                f"M3-3-{code}",
                "EXECUTED",
                hypothesis=hypothesis,
                estimator="walk-forward, preweek cutoff, forecasts frozen before labels join",
                sample_count={p: dev["results"][p]["rows"] for p in groups},
                baseline_metric={
                    p: {
                        "development": dev["results"][p]["b00"]["rmse"],
                        "validation": val["results"][p]["b00"]["rmse"],
                    }
                    for p in groups
                },
                subgroups={"development": development, "validation": validation},
                evidence_paths=evidence,
                reason="See BACKTEST_REPORT.md",
                next_steps="Phase 4: 2025 conditional holdout from frozen-candidates.json",
                **(shared | extra),
            )
        )
    out.append(
        records.record(
            "M3-3-B08",
            "EXECUTED",
            hypothesis="Context-stratified diagnostics of the best DvP variant",
            estimator="RMSE change by season, week bin and opponent games",
            subgroups={p: dev["results"][p]["focus"] for p in groups},
            evidence_paths=evidence,
            **shared,
        )
    )
    for code, key, hypothesis in (
        ("B10", "B10_perGame", "Preweek vs per-game cutoff"),
        ("B12", "B12_delay48h", "Availability of finalized actuals: a 48-hour slower rule"),
    ):
        out.append(
            records.record(
                f"M3-3-{code}",
                "EXECUTED",
                hypothesis=hypothesis,
                estimator="B00 and B03 rerun under the alternative, compared row by row",
                subgroups={
                    "development": dev["sensitivity"][key],
                    "validation": val["sensitivity"][key],
                },
                evidence_paths=evidence,
                **shared,
            )
        )
    holdout_path = receipts / "backtest-holdout.json"
    if holdout_path.exists():
        holdout = json.loads(holdout_path.read_text())
        decisions = holdout["decisions"]
        out.append(
            records.record(
                "M3-3-HOLDOUT-2025",
                "EXECUTED",
                hypothesis="The frozen candidates (D/ST B06; B00 elsewhere) hold on 2025",
                estimator="the Phase 3 method frozen in config/dvp/frozen.json, parameters fit on "
                "2016-2024, every frozen hash verified before running",
                sample_count={p: holdout["results"][p]["rows"] for p in groups},
                baseline_metric={p: holdout["results"][p]["b00"]["rmse"] for p in groups},
                subgroups=decisions["positions"],
                decision=decisions["global"]["label"],
                reason=f"Promising: {', '.join(decisions['global']['promisingPositions']) or 'none'}; "
                "see MODEL_CARD.md",
                next_steps="Prospective 2026 weeks frozen in config/dvp/frozen.json; any production "
                "use needs the owner (OWN-074)",
                evidence_paths=[
                    "docs/research/dvp/backtest-holdout.json",
                    "config/dvp/frozen.json",
                    "docs/research/dvp/MODEL_CARD.md",
                ],
                **(
                    shared
                    | {
                        "code_commit": holdout["code"],
                        "holdout_independence_status": holdout["holdoutStatus"],
                    }
                ),
            )
        )
    out.append(
        records.record(
            "M3-3-B11",
            "PASSED",
            hypothesis="A planted provider projection cannot reach a B-phase forecast",
            estimator="walkforward.prepare fails closed on unknown columns; admission by lineage",
            tests_passed=["T32", "T33", "B11"],
            evidence_paths=["libs/arbit-model/tests/test_dvp_walkforward.py"],
            **shared,
        )
    )
    return out


FROZEN_METHOD = (
    "libs/arbit-model/src/arbit_model/dvp/walkforward.py",
    "libs/arbit-model/src/arbit_model/dvp/lab.py",
    "libs/arbit-model/src/arbit_model/dvp/asof.py",
    "libs/arbit-model/src/arbit_model/dvp/observations.py",
    "libs/arbit-model/src/arbit_model/dvp/reliability.py",
    "libs/arbit-model/src/arbit_model/dvp/provenance.py",
    "libs/arbit-model/src/arbit_model/teams.py",
    "scripts/model/dvp.py",
    "config/dvp/base.json",
    "config/dvp/backtest.json",
    "config/dvp/frozen-candidates.json",
)
DECISION_RULE = (
    "Per position, with the best DvP variant's relative change in RMSE against B00 in development "
    "(2017-2023), validation (2024) and the holdout (2025): PROMISING if the frozen candidate is a "
    "DvP variant and it cuts RMSE by at least the practical minimum (1%) in all three periods; "
    "NOT_USEFUL if the best DvP variant misses the minimum in all three; INCONCLUSIVE otherwise; "
    "BLOCKED if an integrity check fails (frozen hashes, coverage, projection dependency). Globally: "
    "PROMISING with the positions that are; NOT_USEFUL if every position is; INCONCLUSIVE otherwise. "
    "A paired holdout interval that excludes 0 is reported as stronger evidence, not required."
)


def freeze(args: argparse.Namespace) -> None:
    """Fix the Phase 3 method, its inputs and the decision rule before 2025 is forecast."""
    from arbit_model.dvp import observations as observation_rules

    config = json.loads(args.config.read_text())
    base = json.loads((ROOT / config["base"]).read_text())
    code = code_version()
    if code.endswith("+uncommitted"):
        raise SystemExit("freeze from committed code only")
    run_manifest = json.loads((args.run / "run-manifest.json").read_text())
    if run_manifest["targetsIndex"] != base["targets_index"]:
        raise SystemExit("the audit run read a different targets index from the configured one")
    receipts = args.receipts
    development = json.loads((receipts / "backtest-development.json").read_text())
    validation = json.loads((receipts / "backtest-validation.json").read_text())
    candidates = json.loads((ROOT / config["candidates"]).read_text())
    if candidates["fromDevelopment"]["forecastsSha256"] != development["forecastsSha256"]:
        raise SystemExit("the frozen candidates don't come from this development receipt")
    if validation["candidates"]["sha256"] != sha256(ROOT / config["candidates"]):
        raise SystemExit("validation ran on different candidates")
    now = datetime.now(UTC)
    engine = create_engine(
        os.environ["ARBIT_DATABASE_URL"],
        hide_parameters=True,
        execution_options={"postgresql_readonly": True},
    )
    nflverse = ObjectStore(Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects")
    schedule = pl.from_dicts(
        NflverseTables(UnitOfWork(engine), nflverse).read("schedules/games"),
        infer_schema_length=None,
    )
    upcoming = (
        observation_rules.games(schedule, [now.year])
        .group_by("week")
        .agg(pl.col("kickoff").min().alias("first"))
        .filter(pl.col("first") > now)
        .sort("week")
    )
    weeks = upcoming.get_column("week").to_list()
    periods = {
        pos: {
            "candidate": candidates["positions"][pos]["candidate"],
            "bestDvp": candidates["positions"][pos]["bestDvp"],
            "development": candidates["positions"][pos]["bestRelativeDelta"],
            "validation": validation["results"][pos][candidates["positions"][pos]["bestDvp"]][
                "relativeDelta"
            ],
        }
        for pos in base["position_groups"]
    }
    manifest = {
        "format": FORMAT + "-frozen-v1",
        "frozenAt": now.isoformat(),
        "code": code,
        "method": {path: sha256(ROOT / path) for path in FROZEN_METHOD},
        "auditRun": args.run.name,
        "auditOutputs": run_manifest["outputs"],
        "targetsIndex": base["targets_index"],
        "receipts": {
            "development": sha256(receipts / "backtest-development.json"),
            "validation": sha256(receipts / "backtest-validation.json"),
        },
        "holdout": {
            "season": 2025,
            "trainingThrough": 2024,
            "status": "CONDITIONALLY_HELD_OUT",
            "exposure": "v0 (2026-11-23) and Phase A (reliability lab) described 2016-2025, 2025 "
            "included, for repeatability only. No 2025 forecast was made or inspected, and no "
            "parameter was estimated on 2025: candidates came from development folds 2017-2023 and "
            "were frozen before the 2024 validation. The Phase B variant designs (a last-season "
            "prior, non-touchdown points) drew on Phase A's descriptive findings, which included 2025.",
        },
        "protocol": {
            "metric": "RMSE per position on common rows, relative to B00",
            "block": "week",
            "bootstrapReplicates": base["bootstrap_replicates"],
            "seed": base["random_seed"],
            "practicalMinimumRelativeRmse": config["practical_minimum_relative_rmse"],
        },
        "decisionRule": DECISION_RULE,
        "periods": periods,
        "prospective": {
            "season": now.year,
            "weeks": weeks,
            "firstKickoff": upcoming.get_column("first").min().isoformat() if weeks else None,  # type: ignore[union-attr]
            "plan": "Forecast these weeks with this frozen method, each from the actuals available "
            "before its cutoff, once the season is complete and the targets are rebuilt; evaluate "
            "with the same protocol. Confirmatory, independent of every earlier season.",
        },
        "forbidden_vendor_projection_dependencies": 0,
    }
    write_json(ROOT / config["frozen"], manifest)
    print(f"frozen at {manifest['frozenAt']}; prospective {now.year} weeks {weeks}")


def _verify_frozen(manifest: dict[str, Any], run: Path, base: dict[str, Any]) -> list[str]:
    """Every way the files on disk differ from the frozen manifest."""
    problems = [
        f"{path} changed"
        for path, digest in manifest["method"].items()
        if sha256(ROOT / path) != digest
    ]
    if run.name != manifest["auditRun"]:
        problems.append(f"audit run {run.name} is not {manifest['auditRun']}")
    problems += [
        f"{name} changed"
        for name, digest in manifest["auditOutputs"].items()
        if sha256(run / name) != digest
    ]
    if manifest["targetsIndex"] != base["targets_index"]:
        problems.append("targets index changed")
    if manifest.get("forbidden_vendor_projection_dependencies") != 0:
        problems.append("projection dependency recorded")
    return problems


def _decisions(
    by_position: dict[str, Any],
    manifest: dict[str, Any],
    positions: list[str],
    coverage_problem: str | None,
) -> dict[str, Any]:
    from arbit_model.dvp import walkforward as wf

    minimum = manifest["protocol"]["practicalMinimumRelativeRmse"]
    out: dict[str, Any] = {"rule": manifest["decisionRule"], "positions": {}}
    for pos in positions:
        period = manifest["periods"][pos]
        result = by_position[pos][period["bestDvp"]]
        decision = wf.decide(
            period["candidate"],
            period["development"],
            period["validation"],
            result["relativeDelta"],
            minimum,
            blocked=coverage_problem,
        )
        out["positions"][pos] = decision | {
            "candidate": period["candidate"],
            "bestDvp": period["bestDvp"],
            "relativeDelta": {
                "development": period["development"],
                "validation": period["validation"],
                "holdout": result["relativeDelta"],
            },
            "holdoutDelta95": result["delta95"],
            "holdoutIntervalExcludesZero": result["delta95"][1] < 0 or result["delta95"][0] > 0,
        }
    labels = {p: d["label"] for p, d in out["positions"].items()}
    promising = sorted(p for p, label in labels.items() if label == "PROMISING")
    if any(label == "BLOCKED" for label in labels.values()):
        overall = "BLOCKED"
    elif promising:
        overall = "PROMISING"
    elif all(label == "NOT_USEFUL" for label in labels.values()):
        overall = "NOT_USEFUL"
    else:
        overall = "INCONCLUSIVE"
    out["global"] = {"label": overall, "promisingPositions": promising}
    return out


# --- Phase C: start/sit decisions (C00-C05), D/ST only -------------------------------------------

SITSTART_CLOSE = 1.0  # config/dvp/sitstart.json: "differ by less than 1.0 point"
SITSTART_POOL = (9, 24)  # "both units rank 9-24 by B00 that week"
SITSTART_TOP = 8  # "the 8 highest-forecast D/STs each week"
STAGES = ("development", "validation", "holdout")


def _stage_forecasts(run: Path, receipt: dict[str, Any], stage: str) -> tuple[pl.DataFrame, str]:
    """A stage's frozen forecasts, after checking them against the hash its receipt recorded."""
    path = run / f"backtest-{stage}" / "forecasts.parquet"
    if not path.exists():
        raise SystemExit(f"{path} is missing")
    frame = pl.read_parquet(path)
    if sha256(path) == receipt["forecastsSha256"]:
        return frame, "bytes"
    if content_sha256(frame) == receipt.get("forecastsContentSha256"):
        return frame, "content"
    raise SystemExit(f"{path} does not match backtest-{stage}.json")


def sitstart(args: argparse.Namespace) -> None:
    """Phase C for D/ST: the frozen b06 against b00 as start/sit choices, on every stage's frozen
    forecasts. Fits nothing; the rule was declared in config/dvp/sitstart.json beforehand."""
    from arbit_model.dvp import decisions
    from arbit_model.dvp.provenance import PROJECTION_TOKENS

    config = json.loads(args.config.read_text())
    backtest_config = json.loads((ROOT / config["backtest"]).read_text())
    frozen = json.loads((ROOT / backtest_config["frozen"]).read_text())
    candidates_rel = backtest_config["candidates"]
    candidates = json.loads((ROOT / candidates_rel).read_text())
    started = datetime.now(UTC)
    run, receipts = args.run, args.receipts
    problems: list[str] = []
    if sha256(ROOT / candidates_rel) != frozen["method"][candidates_rel]:
        problems.append("frozen candidates changed since the freeze")
    if run.name != frozen["auditRun"]:
        problems.append(f"audit run {run.name} is not the frozen {frozen['auditRun']}")
    run_manifest = json.loads((run / "run-manifest.json").read_text())
    if sha256(run / "observations.parquet") != run_manifest["outputs"]["observations.parquet"]:
        problems.append("observations changed since the audit run")
    (position,) = config["scope"]["positions"]
    model = candidates["positions"][position]["candidate"]
    if not config["candidate"].startswith(model + ","):
        problems.append(f"declared candidate is not the frozen {model}")
    observations = contract.enforce(
        pl.read_parquet(run / "observations.parquet"),
        json.loads((ROOT / "config/dvp/base.json").read_text())["expected_scoring"],
    )
    models = ("b00", model)
    periods: dict[str, Any] = {}
    checks: dict[str, Any] = {}
    for stage in STAGES:
        receipt = json.loads((receipts / f"backtest-{stage}.json").read_text())
        forecasts, matched = _stage_forecasts(run, receipt, stage)
        flagged = [c for c in forecasts.columns if PROJECTION_TOKENS.search(c)]
        if flagged:
            problems.append(f"{stage}: projection-like columns {flagged}")
        table = decisions.units(forecasts, observations, models)
        rows = forecasts.filter(pl.col("position") == position)
        labelled = rows.filter(pl.col("status") == "valid").height
        checks[stage] = {
            "forecastsMatchedBy": matched,
            "seasons": receipt["seasons"],
            "dstForecastRows": rows.height,
            "validLabels": labelled,
            "commonRows": table.height,
            "unitsPerGameAreOne": table.group_by("game_id", "unit").len().get_column("len").max()
            == 1,
        }
        if table.height != labelled:
            problems.append(f"{stage}: {labelled - table.height} labelled rows lack a forecast")
        pairs = decisions.pairs(table, models, "b00")
        periods[stage] = decisions.metrics(
            table,
            pairs,
            "b00",
            model,
            close=SITSTART_CLOSE,
            pool=SITSTART_POOL,
            top=SITSTART_TOP,
            reps=config["bootstrapReplicates"],
            seed=config["seed"],
        )
        print(stage, periods[stage]["pairs"], "pairs", periods[stage]["deltaPp"], "pp")
    minimum = config["practicalMinimumAccuracyPp"]
    if problems:
        label, reason = "BLOCKED", "; ".join(problems)
    else:
        label, reason = decisions.decide(periods, minimum)
    write_json(
        receipts / "sitstart.json",
        {
            "format": FORMAT + "-sitstart-v1",
            "generatedAt": started.isoformat(),
            "code": code_version(),
            "auditRun": run.name,
            "config": {"path": str(args.config), "sha256": sha256(args.config)},
            "candidates": {"path": candidates_rel, "sha256": sha256(ROOT / candidates_rel)},
            "frozenManifest": {
                "path": backtest_config["frozen"],
                "sha256": sha256(ROOT / backtest_config["frozen"]),
            },
            "polarsMaxThreads": os.environ.get("POLARS_MAX_THREADS"),
            "position": position,
            "baseline": "b00",
            "candidate": model,
            "parameters": {
                "close": SITSTART_CLOSE,
                "waiverPoolRanks": list(SITSTART_POOL),
                "top": SITSTART_TOP,
                "bootstrapReplicates": config["bootstrapReplicates"],
                "bootstrapBlock": "season-week",
                "seed": config["seed"],
            },
            "checks": checks,
            "periods": periods,
            "decision": {"label": label, "reason": reason, "practicalMinimumPp": minimum},
            "holdoutStatus": frozen["holdout"]["status"],
            "forbidden_vendor_projection_dependencies": 0,
            "notAvailable": config["notAvailable"],
        },
    )
    print("Phase C:", label, "-", reason)


def _phase_c_records(
    config: dict[str, Any], receipts: Path, common: dict[str, Any]
) -> list[dict[str, Any]]:
    """Registry records of Phase C, from its receipt (none before it has run)."""
    from arbit_model.dvp import results as records

    path = receipts / "sitstart.json"
    if not path.exists():
        return []
    c = json.loads(path.read_text())
    periods = c["periods"]
    evidence = [
        "docs/research/dvp/sitstart.json",
        "config/dvp/sitstart.json",
        "docs/research/dvp/PLAYER_LEVEL_REPORT.md",
    ]
    shared = common | {
        "code_commit": c["code"],
        "as_of_policy": config["as_of_policy"]["default_cutoff"],
        "train_validation_test_periods": {stage: c["checks"][stage]["seasons"] for stage in STAGES},
        "holdout_independence_status": f"{c['holdoutStatus']}: the same frozen 2025 forecasts "
        "were scored for group-level RMSE before; no Phase C quantity was computed before its "
        "rule was declared",
        "primary_metric": "pairwise start/sit accuracy, candidate minus baseline (points)",
        "evidence_paths": evidence,
    }
    scope = (
        "D/ST only: Phase C runs for a group with a credible group-level signal (§5); QB is "
        "INCONCLUSIVE and RB, WR, TE, K NOT_USEFUL, so they are not run, by the specification's gate"
    )
    out = [
        records.record(
            "M3-3-C00",
            "EXECUTED",
            hypothesis="An Arbit-computed, actuals-only D/ST baseline exists for player-level tests",
            estimator="B00, the offense-only forecast from prior FFA actuals; Arbit has no other "
            "player projection and uses no provider projection",
            sample_count={s: c["checks"][s]["commonRows"] for s in STAGES},
            reason=scope,
            **shared,
        ),
        records.record(
            "M3-3-C01",
            "EXECUTED",
            hypothesis="The group-level D/ST term allocates to players by past-known share",
            estimator="a D/ST is one unit per team: each D/ST forecast row maps to exactly one "
            "canonical unit, the defense of the game, so the share is 1",
            parameters={s: c["checks"][s]["unitsPerGameAreOne"] for s in STAGES},
            tests_passed=["T26"],
            reason="Identity for D/ST: the player-level forecast is the group-level forecast",
            **shared,
        ),
        records.record(
            "M3-3-C02",
            "EXECUTED",
            hypothesis="Additive, proportional and opportunity x efficiency allocation differ",
            estimator="with a share of 1 and no opportunity split, all three allocations give "
            "the same D/ST forecast",
            reason="Identical by construction for D/ST; nothing to choose between",
            **shared,
        ),
        records.record(
            "M3-3-C03",
            "BLOCKED",
            hypothesis="Role interactions (slot, outside, target share) refine the matchup",
            reason=c["notAvailable"]["roles"],
            next_steps="Only for a position group that first shows a group-level signal",
            **shared,
        ),
        records.record(
            "M3-3-C04",
            "EXECUTED",
            hypothesis="The frozen D/ST candidate picks the higher-scoring D/ST more often",
            estimator="every unordered pair of D/STs playing the same week; each model starts "
            "the higher forecast",
            sample_count={s: periods[s]["pairs"] for s in STAGES},
            baseline_metric={s: periods[s]["accuracy"]["b00"] for s in STAGES},
            absolute_delta={s: periods[s]["deltaPp"] for s in STAGES},
            interval={s: periods[s]["deltaPp95"] for s in STAGES},
            subgroups={
                s: {"close": periods[s]["close"], "waiverPool": periods[s]["waiverPool"]}
                for s in STAGES
            },
            decision=c["decision"]["label"],
            reason=c["decision"]["reason"],
            limitations=[
                c["notAvailable"]["leagueLineups"],
                "The waiver-pool subgroup assumes an 8-team league rosters the top 8 by B00",
            ],
            next_steps="Score 2026 weeks 12-18 with the same frozen rule (PROSPECTIVE_2026.md)",
            **shared,
        ),
        records.record(
            "M3-3-C05",
            "EXECUTED",
            hypothesis="Changed D/ST choices gain actual FFA points without large regret",
            estimator="actual(candidate pick) - actual(baseline pick) over changed decisions; "
            "worst single decision and week; league top-8 points",
            parameters={
                s: {
                    "changed": periods[s]["changed"],
                    "pointsFromChanges": periods[s]["pointsFromChanges"],
                    "worstCase": periods[s]["worstCase"],
                    "top8": periods[s]["top8"],
                }
                for s in STAGES
            },
            decision=c["decision"]["label"],
            reason=c["decision"]["reason"],
            limitations=[c["notAvailable"]["leagueLineups"]],
            **shared,
        ),
    ]
    return out


# --- Verify: read every artifact back and reproduce its receipt (T27) -----------------------------


def verify(args: argparse.Namespace) -> None:
    """Verify-only: nothing is recomputed into the receipts. Checks v0's files, the frozen manifest
    against the frozen commit and the working tree, the audit run's outputs, each stage's forecasts
    against its receipt, every metric recomputed from those forecasts, and label joins, units and
    the sign of the D/ST term. Writes verify-receipt.json."""
    from arbit_model.dvp import walkforward as wf

    config = json.loads(args.config.read_text())
    base = json.loads((ROOT / config["base"]).read_text())
    frozen = json.loads((ROOT / config["frozen"]).read_text())
    receipts, run = args.receipts, args.run
    started = datetime.now(UTC)
    out: dict[str, Any] = {}

    continuity = json.loads((receipts / "continuity-manifest.json").read_text())["v0"]["files"]
    out["v0ByteIdentical"] = {p: sha256(ROOT / p) == d for p, d in continuity.items()}

    def at_commit(path: str) -> str:
        blob = subprocess.run(
            ["git", "show", f"{frozen['code']}:{path}"], cwd=ROOT, capture_output=True, check=True
        ).stdout
        return hashlib.sha256(blob).hexdigest()

    method = frozen["method"]
    out["frozen"] = {
        "code": frozen["code"],
        "frozenCommitMatchesManifest": {p: at_commit(p) == d for p, d in method.items()},
        "changedInWorkingTreeSinceFreeze": sorted(
            p for p, d in method.items() if sha256(ROOT / p) != d
        ),
        "receiptsMatchManifest": {
            stage: sha256(receipts / f"backtest-{stage}.json") == digest
            for stage, digest in frozen["receipts"].items()
        },
        "rule": "Frozen stages (holdout, prospective) run from the frozen commit's tree, which "
        "matches every frozen hash; the working tree may differ only outside the method",
    }
    manifest = json.loads((run / "run-manifest.json").read_text())
    out["auditOutputs"] = {n: sha256(run / n) == d for n, d in manifest["outputs"].items()}
    observations = contract.enforce(
        pl.read_parquet(run / "observations.parquet"),
        json.loads((ROOT / "config/dvp/base.json").read_text())["expected_scoring"],
    )
    labels = observations.select("game_id", "offense", "position", pl.col("points").alias("_obs"))

    stages: dict[str, Any] = {}
    for stage in STAGES:
        receipt = json.loads((receipts / f"backtest-{stage}.json").read_text())
        joined, matched = _stage_forecasts(run, receipt, stage)
        variants = sorted(
            c for c in joined.columns if c.startswith("b0") and c not in ("b00_nontd",)
        )
        mismatched: list[str] = []
        compared = 0
        for pos, expected in receipt["results"].items():
            part = joined.filter(pl.col("position") == pos)
            again = wf.metrics(
                part,
                variants,
                block=receipt["bootstrapBlock"],
                reps=receipt["bootstrapReplicates"],
                seed=receipt["seed"],
            )
            again["calibrationB00"] = wf.calibration(part, "b00")
            for key, value in expected.items():
                if key == "focus":
                    continue
                compared += 1
                if again.get(key) != value:
                    mismatched.append(f"{pos}.{key}")
        join = joined.join(labels, on=["game_id", "offense", "position"], how="left")
        dst = joined.filter(pl.col("position") == "DST")
        dst_points = dst.get_column("points").to_numpy()
        residual = dst_points - dst.get_column("b00").to_numpy()
        adjustment = (dst.get_column("b06") - dst.get_column("b00")).to_numpy()
        stages[stage] = {
            "forecastsMatchedBy": matched,
            "rows": joined.height,
            "metricsCompared": compared,
            "metricsMismatched": mismatched,
            "labelsJoinObservationsOneToOne": join.height == joined.height
            and join.filter(pl.col("_obs").is_null()).height == 0,
            "labelsEqualObservations": join.filter(
                (pl.col("points") - pl.col("_obs")).abs() > 1e-9
            ).height
            == 0,
            "dstLabelsAreWholePoints": bool(np.allclose(dst_points, np.round(dst_points))),
            # A units check, not an accuracy one: a scale or scoring mix-up shifts the mean by
            # far more than a season's level does (WR 2025: 1.7 points on ~28, about 6%).
            "meanBiasRelativeToMeanLabel": {
                pos: round(
                    float(
                        joined.filter(pl.col("position") == pos)
                        .select(
                            (pl.col("b00").mean() - pl.col("points").mean())
                            / pl.col("points").mean()
                        )
                        .item()
                    ),
                    4,
                )
                for pos in receipt["results"]
            },
            "dstTermSignCorrelation": round(float(np.corrcoef(adjustment, residual)[0, 1]), 4),
            "sample": dst.sort("game_id", "offense")
            .gather_every(max(1, dst.height // 6))
            .head(6)
            .select("game_id", "offense", "week", "n_d", "b00", "b06", "points")
            .with_columns(pl.col("b00", "b06").round(3))
            .to_dicts(),
        }
    out["stages"] = stages
    # The receipts this verification read, so a later change to any of them is detectable (T27).
    out["receiptsVerified"] = {
        name: sha256(receipts / name)
        for name in [f"backtest-{stage}.json" for stage in STAGES] + ["sitstart.json"]
        if (receipts / name).exists()
    }
    passed = (
        all(out["v0ByteIdentical"].values())
        and all(out["frozen"]["frozenCommitMatchesManifest"].values())
        and all(out["frozen"]["receiptsMatchManifest"].values())
        and all(out["auditOutputs"].values())
        and all(
            not s["metricsMismatched"]
            and s["labelsJoinObservationsOneToOne"]
            and s["labelsEqualObservations"]
            and s["dstLabelsAreWholePoints"]
            and s["dstTermSignCorrelation"] > 0
            and all(abs(v) < 0.2 for v in s["meanBiasRelativeToMeanLabel"].values())
            for s in stages.values()
        )
    )
    write_json(
        receipts / "verify-receipt.json",
        {
            "format": FORMAT + "-verify-v1",
            "generatedAt": started.isoformat(),
            "code": code_version(),
            "auditRun": run.name,
            "targetsIndex": base["targets_index"],
            "polarsMaxThreads": os.environ.get("POLARS_MAX_THREADS"),
            "status": "PASSED" if passed else "FAILED",
            **out,
        },
    )
    print("verify:", "PASSED" if passed else "FAILED")
    if not passed:
        raise SystemExit(1)


def _pair(value: tuple[float, float] | None) -> list[float] | None:
    return None if value is None else [round(value[0], 4), round(value[1], 4)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    a = commands.add_parser("audit")
    a.add_argument("--config", type=Path, required=True)
    a.add_argument("--targets", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--receipts", type=Path, required=True)
    r = commands.add_parser("reproduce-v0")
    r.add_argument("--config", type=Path, required=True)
    r.add_argument("--targets", type=Path, required=True)
    r.add_argument("--run", type=Path, required=True)
    r.add_argument("--receipts", type=Path, required=True)
    q = commands.add_parser("reliability")
    q.add_argument("--config", type=Path, required=True)
    q.add_argument("--targets", type=Path, required=True)
    q.add_argument("--run", type=Path, required=True)
    q.add_argument("--receipts", type=Path, required=True)
    b = commands.add_parser("backtest")
    b.add_argument("--config", type=Path, required=True)
    b.add_argument("--stage", choices=("development", "validation", "holdout"), required=True)
    b.add_argument("--targets", type=Path, required=True)
    b.add_argument("--run", type=Path, required=True)
    b.add_argument("--receipts", type=Path, required=True)
    fz = commands.add_parser("freeze")
    fz.add_argument("--config", type=Path, required=True)
    fz.add_argument("--run", type=Path, required=True)
    fz.add_argument("--receipts", type=Path, required=True)
    rp = commands.add_parser("report")
    rp.add_argument("--receipts", type=Path, required=True)
    g = commands.add_parser("registry")
    g.add_argument("--config", type=Path, required=True)
    g.add_argument("--receipts", type=Path, required=True)
    c = commands.add_parser("sitstart")
    c.add_argument("--config", type=Path, required=True)
    c.add_argument("--run", type=Path, required=True)
    c.add_argument("--receipts", type=Path, required=True)
    v = commands.add_parser("verify")
    v.add_argument("--config", type=Path, required=True)
    v.add_argument("--run", type=Path, required=True)
    v.add_argument("--receipts", type=Path, required=True)
    args = parser.parse_args()
    {
        "audit": audit,
        "reproduce-v0": reproduce,
        "reliability": reliability,
        "backtest": backtest,
        "freeze": freeze,
        "report": report,
        "registry": registry,
        "sitstart": sitstart,
        "verify": verify,
    }[args.command](args)


if __name__ == "__main__":
    main()
