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

import polars as pl
from arbit_core.rules import RuleSet
from arbit_data.db import UnitOfWork
from arbit_data.league_policy import read_policy
from arbit_data.nflverse.objects import ObjectStore
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
    "libs/arbit-model/src/arbit_model/teams.py",
    "scripts/model/dvp.py",
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


def code_version() -> str:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
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


def season_manifest(targets: Path, index: dict[str, Any], season: int) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads(
        (targets / "objects" / index["seasons"][str(season)]).read_bytes()
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
        path = targets / "objects" / digest
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
    for code, hypothesis in PLANNED.items():
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
    observations = pl.read_parquet(run / "observations.parquet")
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
            path = targets / "objects" / digest
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
            note="k from REML on adjusted points; bands from the season-bootstrap interval of k. "
            "Credibility inside a DvP estimate, not a share of a Sit/Start model.",
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
    g = commands.add_parser("registry")
    g.add_argument("--config", type=Path, required=True)
    g.add_argument("--receipts", type=Path, required=True)
    args = parser.parse_args()
    {
        "audit": audit,
        "reproduce-v0": reproduce,
        "reliability": reliability,
        "registry": registry,
    }[args.command](args)


if __name__ == "__main__":
    main()
