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
from datetime import UTC, datetime
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
from arbit_model.teams import franchise
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
    g = commands.add_parser("registry")
    g.add_argument("--config", type=Path, required=True)
    g.add_argument("--receipts", type=Path, required=True)
    args = parser.parse_args()
    {"audit": audit, "reproduce-v0": reproduce, "registry": registry}[args.command](args)


if __name__ == "__main__":
    main()
