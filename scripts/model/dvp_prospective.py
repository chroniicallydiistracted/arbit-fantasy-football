"""M3-3 DvP prospective shadow forecasts: archive before kickoff, evaluate after the games.

Owner audit remediation 1 (AUD-01). Everything it does is predeclared in
config/dvp/prospective.json; the method is the frozen one (config/dvp/frozen.json,
config/dvp/frozen-phase-c.json), run through the versioned adapter `arbit_model.dvp.shadow`.

  forecast  --week W        Archive week W's forecasts if its cutoff hasn't passed and its inputs
                            are complete. After the cutoff it records the week as MISSED.
  sweep                     For every window week: forecast it when ready, record a miss when its
                            cutoff passed unarchived, otherwise wait. Safe to run repeatedly.
  reconstruct --week W      A forecast made after the cutoff, stored apart as RETROSPECTIVE.
  rehearse                  2025 from the frozen audit run: the adapter's forecasts against the
                            committed holdout forecasts, then the evaluation path on 2025 labels.
  evaluate                  Score the archived forecasts with the frozen rules (labels from a fresh
                            targets build after the games). Interim until the window is complete.
  verify                    The ledger's hash chain, every archived file and its exported copy.

Run from a checkout whose library modules equal the frozen hashes, with the main checkout's data:

  POLARS_MAX_THREADS=2 ARBIT_NFLVERSE_PATH=<main>/data/nflverse uv run --env-file <main>/.env.local \\
    python scripts/model/dvp_prospective.py sweep --main <main>

Read-only against the database and the nflverse store. Writes only the archive, the export folder
and, for `rehearse` and `evaluate`, their receipts.
"""

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore
from arbit_model import teams
from arbit_model.dvp import asof, contract, decisions, lab, provenance, reliability, shadow
from arbit_model.dvp import observations as obs
from arbit_model.dvp import walkforward as wf
from arbit_model.inputs import NflverseTables
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/dvp/prospective.json"
FORMAT = "arbit-dvp-m3-3-prospective"
ESPN_TO_FRANCHISE = {"LAR": "LA", "WSH": "WAS"}
NO_RESULT_GRACE = timedelta(days=4)
IMPORTED = {
    "libs/arbit-model/src/arbit_model/dvp/walkforward.py": wf,
    "libs/arbit-model/src/arbit_model/dvp/asof.py": asof,
    "libs/arbit-model/src/arbit_model/dvp/observations.py": obs,
    "libs/arbit-model/src/arbit_model/dvp/provenance.py": provenance,
    "libs/arbit-model/src/arbit_model/dvp/lab.py": lab,
    "libs/arbit-model/src/arbit_model/dvp/reliability.py": reliability,
    "libs/arbit-model/src/arbit_model/teams.py": teams,
    "libs/arbit-model/src/arbit_model/dvp/decisions.py": decisions,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def code_version() -> str:
    dirty = git("status", "--porcelain", "--untracked-files=no", "--", ".", ":(exclude)docs")
    return git("rev-parse", "HEAD") + ("+uncommitted" if dirty else "")


def now_utc() -> datetime:
    return datetime.now(UTC)


# --- the frozen method ---------------------------------------------------------------------------


@dataclass
class Frozen:
    cli: Any  # the frozen scripts/model/dvp.py, loaded from git by hash
    group: dict[str, Any]
    phase_c: dict[str, Any]
    base: dict[str, Any]
    backtest: dict[str, Any]
    candidates: dict[str, Any]
    sitstart: dict[str, Any]
    verification: dict[str, Any]

    @property
    def positions(self) -> list[str]:
        return list(self.base["position_groups"])

    def settings(self) -> wf.Settings:
        return wf.Settings(
            mode=asof.Cutoff(self.backtest["cutoff"]),
            k_grid=tuple(self.backtest["k_grid"]),
            half_lives=tuple(self.backtest["half_lives"]),
            seed=self.base["random_seed"],
        )


def load_frozen() -> Frozen:
    """Verify every frozen hash, then load the frozen dvp.py from git. Stops on any mismatch."""
    group = json.loads((ROOT / "config/dvp/frozen.json").read_text())
    phase_c = json.loads((ROOT / "config/dvp/frozen-phase-c.json").read_text())
    checks: dict[str, bool] = {}
    for path, digest in {**group["method"], **phase_c["method"]}.items():
        if path != "scripts/model/dvp.py":
            checks[path] = sha256(ROOT / path) == digest
    checks["config/dvp/frozen.json = Phase C's groupLevelFreeze"] = (
        sha256(ROOT / "config/dvp/frozen.json") == phase_c["groupLevelFreeze"]["sha256"]
    )
    for path, module in IMPORTED.items():
        checks[f"imported from {path}"] = Path(module.__file__ or "").resolve() == ROOT / path
    source = subprocess.run(
        ["git", "show", f"{group['code']}:scripts/model/dvp.py"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    checks[f"scripts/model/dvp.py at {group['code'][:7]}"] = (
        sha256_bytes(source) == group["method"]["scripts/model/dvp.py"]
    )
    failed = sorted(k for k, ok in checks.items() if not ok)
    if failed:
        raise SystemExit("BLOCKED: frozen method does not match: " + "; ".join(failed))
    name = "dvp_frozen_cli"
    spec = importlib.util.spec_from_loader(name, loader=None)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(ROOT / "scripts/model/dvp.py")  # its ROOT resolves to this checkout
    sys.modules[name] = module
    exec(compile(source, f"<frozen dvp.py {group['code'][:7]}>", "exec"), module.__dict__)  # noqa: S102

    def read(path: str) -> dict[str, Any]:
        value: dict[str, Any] = json.loads((ROOT / path).read_text())
        return value

    return Frozen(
        cli=module,
        group=group,
        phase_c=phase_c,
        base=read("config/dvp/base.json"),
        backtest=read("config/dvp/backtest.json"),
        candidates=read("config/dvp/frozen-candidates.json"),
        sitstart=read("config/dvp/sitstart.json"),
        verification={
            "groupLevelCode": group["code"],
            "frozenSha256": sha256(ROOT / "config/dvp/frozen.json"),
            "phaseCSha256": sha256(ROOT / "config/dvp/frozen-phase-c.json"),
            "filesVerified": len(checks),
            "allMatch": True,
        },
    )


# --- data ----------------------------------------------------------------------------------------


def engine_readonly() -> Any:
    return create_engine(
        os.environ["ARBIT_DATABASE_URL"],
        hide_parameters=True,
        execution_options={"postgresql_readonly": True},
    )


def verify_store(root: Path, index_digest: str, seasons: list[int]) -> dict[str, str]:
    """Recompute the SHA-256 of every object a season read touches: the index, each season
    manifest and each table's Parquet (owner audit AUD-04). Returns the verified digests."""
    objects = root / "objects"
    verified: dict[str, str] = {}

    def check(digest: str, what: str) -> bytes:
        data = (objects / digest).read_bytes()
        if sha256_bytes(data) != digest:
            raise SystemExit(f"BLOCKED: {what} {digest[:12]} does not match its digest")
        verified[what] = digest
        return data

    index = json.loads(check(index_digest, "index"))
    for season in seasons:
        manifest = json.loads(check(index["seasons"][str(season)], f"{season} manifest"))
        for role, table in manifest["tables"].items():
            check(table["parquet"], f"{season} {role}")
    return verified


def history(fz: Frozen, main: Path) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    """Seasons 2016-2025 as the frozen audit run holds them, with non-touchdown points."""
    run = main / "artifacts/dvp" / fz.group["auditRun"]
    for name, digest in fz.group["auditOutputs"].items():
        if sha256(run / name) != digest:
            raise SystemExit(f"BLOCKED: {name} of the frozen audit run changed")
    targets = main / "data/model"
    verified = verify_store(targets, fz.base["targets_index"], fz.base["seasons"])
    observations = pl.read_parquet(run / "observations.parquet")
    parts = fz.cli._contribution_cells(targets, fz.base, observations)
    observations = fz.cli._with_nontd(observations, parts)
    schedule = pl.read_parquet(run / "schedule_games.parquet")
    lineage = {
        "auditRun": fz.group["auditRun"],
        "auditOutputs": fz.group["auditOutputs"],
        "targetsIndex": fz.base["targets_index"],
        "objectsVerified": len(verified),
    }
    return observations, schedule, lineage


def build_season(main: Path, season: int, out: Path, reason: str) -> str:
    """A fresh targets store for one season from the nflverse files Arbit holds now."""
    out.mkdir(parents=True, exist_ok=False)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/model/build_targets.py"), "--output", str(out)]
        + ["--seasons", f"{season}-{season}", "--reason", reason],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "ARBIT_NFLVERSE_PATH": os.environ.get(
                "ARBIT_NFLVERSE_PATH", str(main / "data/nflverse")
            ),
        },
    )
    (out / "build.log").write_text(result.stdout + result.stderr)
    if result.returncode != 0:
        raise SystemExit(f"targets build failed ({result.returncode}); see {out / 'build.log'}")
    return str(json.loads(result.stdout.strip().splitlines()[-1])["index"])


def season_observations(
    fz: Frozen, store: Path, index_digest: str, season: int, engine: Any, nflverse: Path
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    """One season's observations and schedule, built and admitted as the frozen audit does."""
    verified = verify_store(store, index_digest, [season])
    index = fz.cli.load_index(store, index_digest)
    manifest = fz.cli.season_manifest(store, index, season)
    expected = fz.base["expected_scoring"]
    if index["rules"] != expected or manifest["rules"] != expected:
        raise SystemExit("BLOCKED: the build's scoring hashes are not the configured FFA rules")
    config = {"seasons": [season], "targets_index": index_digest, "expected_scoring": expected}
    schedule_pin = manifest["inputs"]["schedules/games"]
    tables = NflverseTables(
        UnitOfWork(engine), ObjectStore(nflverse / "objects"), {"schedules/games": schedule_pin}
    )
    schedule = provenance.admit(
        pl.from_dicts(tables.read("schedules/games"), infer_schema_length=None),
        "nflverse.schedules",
        ancestry=f"nflverse manifest {schedule_pin} (the schedule the {season} build read)",
    )
    athlete, athlete_admissions = fz.cli.read_targets(store, index, config, "athlete")
    defense, defense_admissions = fz.cli.read_targets(store, index, config, "defense")
    scheduled = obs.games(schedule.frame, [season])
    played = obs.team_games(scheduled)
    cells, athlete_anomalies = obs.position_cells(athlete, played)
    dst, dst_anomalies = obs.dst_cells(defense, played)
    rows = contract.enforce(obs.observations(cells, dst, expected), expected)
    rows = fz.cli._with_nontd(rows, fz.cli._contribution_cells(store, config, rows))
    admissions = [schedule, *athlete_admissions, *defense_admissions]
    with engine.connect() as c:
        observed = {
            key: str(
                c.execute(
                    text("select observed_at from dataset_manifest where hash = :h"), {"h": digest}
                ).scalar()
            )
            for key, digest in manifest["inputs"].items()
        }
    lineage = {
        "targetsIndex": index_digest,
        "seasonManifest": index["seasons"][str(season)],
        "objectsVerified": verified,
        "nflverseManifests": manifest["inputs"],
        "nflverseObservedAt": observed,
        "scoring": manifest["rules"],
        "sourceAncestrySha256": provenance.ancestry_hash(admissions),
        "anomalies": {
            "athleteRowsOutsideCompletedTeamGames": athlete_anomalies[
                "rowsOutsideCompletedTeamGames"
            ],
            "duplicatePlayerGameLines": athlete_anomalies["duplicatePlayerGameLines"],
            "dstLinesOutsideCompletedTeamGames": dst_anomalies["dstLinesOutsideCompletedTeamGames"],
        },
        "cells": dict(
            sorted(
                (f"{r['position']}/{r['status']}", r["len"])
                for r in rows.group_by("position", "status").len().iter_rows(named=True)
            )
        ),
    }
    return rows, scheduled, lineage


def combine(
    past: pl.DataFrame, past_schedule: pl.DataFrame, now: pl.DataFrame, now_schedule: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame]:
    seasons = set(now.get_column("season").unique().to_list())
    if seasons & set(past.get_column("season").unique().to_list()):
        raise SystemExit("BLOCKED: a season is in both the frozen history and the fresh build")
    columns = past.columns
    if set(now.columns) != set(columns):
        raise SystemExit(f"BLOCKED: observation columns differ: {set(now.columns) ^ set(columns)}")
    rows = pl.concat([past, now.select(columns)], how="vertical_relaxed")
    schedule = pl.concat(
        [past_schedule, now_schedule.select(past_schedule.columns)], how="vertical_relaxed"
    )
    return rows, schedule


def readiness(
    schedule: pl.DataFrame, observations: pl.DataFrame, season: int, week: int, now: datetime
) -> tuple[bool, dict[str, Any]]:
    """Are the inputs the frozen method would use at week W's cutoff all present now?"""
    earlier = schedule.filter((pl.col("season") == season) & (pl.col("week") < week))
    done = earlier.filter(pl.col("status") == "completed")
    pending = earlier.filter(
        (pl.col("status") != "completed") & (pl.col("kickoff") + NO_RESULT_GRACE > now)
    )
    no_result = earlier.filter(
        (pl.col("status") != "completed") & (pl.col("kickoff") + NO_RESULT_GRACE <= now)
    )
    scored = set(observations.filter(pl.col("season") == season).get_column("game_id").to_list())
    unscored = sorted(set(done.get_column("game_id").to_list()) - scored)
    latest = done.get_column("available_at").max()
    detail = {
        "earlierGames": earlier.height,
        "completed": done.height,
        "awaitingResult": pending.get_column("game_id").to_list(),
        "noResultAfterGrace": no_result.get_column("game_id").to_list(),
        "completedWithoutFfaLines": unscored,
        "latestAvailability": str(latest),
    }
    ready = bool(not pending.height and not unscored and (latest is None or latest <= now))  # type: ignore[operator]
    return ready, detail


def league_capture(engine: Any, schedule_teams: set[str]) -> dict[str, Any]:
    """The league's current rosters of D/STs, read-only (config `leagueEvaluation.capture`)."""
    with engine.connect() as c:
        snapshot = c.execute(
            text(
                "select s.id, s.observed_at, s.content_hash from league_snapshot s "
                "join current_snapshot c on c.snapshot_id = s.id"
            )
        ).one()
        held = c.execute(
            text(
                "select r.team_id, n.abbreviation, r.slot from roster_entry r "
                "join canonical_entity e on e.id = r.entity_id and e.kind = 'defense_unit' "
                "join team_affiliation a on a.entity_id = e.id and a.valid_to is null "
                "join nfl_team n on n.entity_id = a.team_id "
                "where r.snapshot_id = :s order by 1, 2"
            ),
            {"s": snapshot.id},
        ).all()
        every = (
            c.execute(
                text(
                    "select n.abbreviation from canonical_entity e "
                    "join team_affiliation a on a.entity_id = e.id and a.valid_to is null "
                    "join nfl_team n on n.entity_id = a.team_id where e.kind = 'defense_unit'"
                )
            )
            .scalars()
            .all()
        )

    def code(abbreviation: str) -> str:
        return ESPN_TO_FRANCHISE.get(abbreviation, abbreviation)

    units = sorted({code(a) for a in every})
    rosters: dict[str, list[str]] = {}
    slots: dict[str, dict[str, str]] = {}
    for team_id, abbreviation, slot in held:
        rosters.setdefault(str(team_id), []).append(code(abbreviation))
        slots.setdefault(str(team_id), {})[code(abbreviation)] = slot
    rostered = {u for held_units in rosters.values() for u in held_units}
    # Decision-time availability of each unrostered D/ST (Phase B, C05L-2026-PRO): a unit dropped
    # within the league's waiver hold is on waivers, within two holds it may still be.
    with engine.connect() as c:
        hours = int(
            c.execute(
                text(
                    "select r.payload->>'waiver_hours' from rule_version r join league_document d on "
                    "d.rules_hash = r.hash join current_snapshot c on c.snapshot_id = d.snapshot_id"
                )
            ).scalar_one()
        )
        drops = c.execute(
            text(
                "select max(coalesce(t.processed_at, t.proposed_at)) as dropped, n.abbreviation "
                "from fantasy_transaction t, jsonb_array_elements(t.items) i "
                "join canonical_entity e on e.id = (i->>'player_id')::uuid and e.kind = 'defense_unit' "
                "join team_affiliation a on a.entity_id = e.id and a.valid_to is null "
                "join nfl_team n on n.entity_id = a.team_id "
                "where t.status = 'EXECUTED' and i->>'type' = 'DROP' group by n.abbreviation"
            )
        ).all()
    captured_at = snapshot.observed_at
    last_drop = {code(r.abbreviation): r.dropped for r in drops}
    hold = timedelta(hours=hours)
    states: dict[str, str] = {}
    for unit in units:
        if unit in rostered:
            states[unit] = "OWNED"
        elif unit in last_drop and captured_at - last_drop[unit] < hold:
            states[unit] = "WAIVERS"
        elif unit in last_drop and captured_at - last_drop[unit] < 2 * hold:
            states[unit] = "WAIVERS_OR_FREE_AGENT"
        else:
            states[unit] = "FREE_AGENT"
    unknown = sorted(u for u in units if u not in schedule_teams)
    if unknown or len(units) != 32:
        raise SystemExit(f"BLOCKED: D/ST codes {unknown} do not map to the schedule's teams")
    return {
        "snapshotId": str(snapshot.id),
        "observedAt": snapshot.observed_at.isoformat(),
        "contentHash": snapshot.content_hash,
        "rosters": {t: sorted(u) for t, u in sorted(rosters.items())},
        "slots": slots,
        "freeAgents": sorted(set(units) - rostered),
        "availability": dict(sorted(states.items())),
        "waiverHours": hours,
        "units": len(units),
        "unitsNotInSchedule": unknown,
    }


# --- archive -------------------------------------------------------------------------------------


def archive_root(args: argparse.Namespace, season: int) -> Path:
    return Path(args.archive or args.main / "artifacts/dvp/prospective") / str(season)


def read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append_ledger(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        lines = [json.loads(line) for line in handle.read().splitlines() if line.strip()]
        problems = shadow.verify_ledger(lines)
        if problems:
            raise SystemExit("ledger is broken: " + "; ".join(problems))
        entry = shadow.ledger_entry(lines[-1]["entrySha256"] if lines else None, record)
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return entry


def entries_for(lines: list[dict[str, Any]], week: int) -> list[dict[str, Any]]:
    return [e for e in lines if e.get("week") == week]


def write_once(folder: Path, files: dict[str, bytes], keep: Path | None = None) -> dict[str, str]:
    """Write a week's files to a temporary folder, then rename it into place. Refuses if the
    folder exists. Files become read-only. Returns each file's SHA-256."""
    if folder.exists():
        raise SystemExit(f"{folder} exists; archived forecasts are never overwritten")
    folder.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{folder.name}.", dir=folder.parent))
    digests = {}
    for name, data in files.items():
        (temporary / name).parent.mkdir(parents=True, exist_ok=True)
        (temporary / name).write_bytes(data)
        digests[name] = sha256_bytes(data)
    if keep is not None:
        shutil.move(str(keep), str(temporary / "inputs"))
    os.rename(temporary, folder)  # fails if another run created it meanwhile
    for path in folder.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    return digests


def export(
    args: argparse.Namespace, season: int, week_folder: str, files: dict[str, bytes], ledger: Path
) -> None:
    """Copy a week's forecasts, manifest and league capture, and the ledger, for committing."""
    target = Path(args.export) / str(season)
    folder = target / week_folder
    if folder.exists():
        raise SystemExit(f"{folder} exists; exported forecasts are never overwritten")
    folder.mkdir(parents=True)
    for name in ("forecasts.csv", "manifest.json", "league.json"):
        if name in files:
            (folder / name).write_bytes(files[name])
    shutil.copyfile(ledger, target / "ledger.jsonl")


# --- forecasting ---------------------------------------------------------------------------------


@dataclass
class Prepared:
    rows: pl.DataFrame
    schedule: pl.DataFrame
    season_rows: pl.DataFrame
    season_schedule: pl.DataFrame
    lineage: dict[str, Any]
    store: Path


def prepare_season(
    fz: Frozen, args: argparse.Namespace, season: int, work: Path, reason: str
) -> Prepared:
    engine = engine_readonly()
    nflverse = Path(os.environ.get("ARBIT_NFLVERSE_PATH", args.main / "data/nflverse"))
    past, past_schedule, past_lineage = history(fz, args.main)
    store = work / "targets"
    digest = build_season(args.main, season, store, reason)
    now_rows, now_schedule, now_lineage = season_observations(
        fz, store, digest, season, engine, nflverse
    )
    rows, schedule = combine(past, past_schedule, now_rows, now_schedule)
    return Prepared(
        rows=shadow.prepare_checked(rows, fz.base["expected_scoring"]),
        schedule=schedule,
        season_rows=now_rows,
        season_schedule=now_schedule,
        lineage={"history": past_lineage, "season": now_lineage},
        store=store,
    )


def forecast_frame(
    fz: Frozen, rows: pl.DataFrame, schedule: pl.DataFrame, season: int, week: int
) -> tuple[pl.DataFrame, dict[str, Any]]:
    params = wf.fit_fold(rows, season, fz.positions)
    targets = shadow.scheduled_targets(schedule, season, range(1, week + 1), fz.positions)
    frozen = shadow.walk_targets(rows, targets, schedule, params, fz.positions, fz.settings())
    out = shadow.forecast_only(frozen, targets).filter(pl.col("week") == week)
    return out, params.summary()


def cutoff_of(schedule: pl.DataFrame, season: int, week: int) -> datetime:
    games = schedule.filter((pl.col("season") == season) & (pl.col("week") == week))
    if games.is_empty():
        raise SystemExit(f"no scheduled games in {season} week {week}")
    cut = asof.cutoffs(games, asof.Cutoff.PREWEEK).get_column("cutoff").min()
    assert isinstance(cut, datetime)
    return cut


def csv_bytes(frame: pl.DataFrame) -> bytes:
    return frame.sort(list(shadow.KEYS)).write_csv().encode()


def run_forecast(args: argparse.Namespace, week: int, classification: str) -> int:
    config = json.loads(CONFIG.read_text())
    season = int(args.season or config["season"])
    root = archive_root(args, season)
    ledger = root / "ledger.jsonl"
    lines = read_ledger(ledger)
    problems = shadow.verify_ledger(lines)
    if problems:
        raise SystemExit("ledger is broken: " + "; ".join(problems))
    previous = entries_for(lines, week)
    if classification == "PROSPECTIVE" and any(
        e["classification"] in ("PROSPECTIVE", "MISSED") for e in previous
    ):
        print(f"week {week}: already {previous[0]['classification']}; nothing to do")
        return 0
    fz = load_frozen()
    started = now_utc()
    work = Path(tempfile.mkdtemp(prefix=f"dvp-{season}-w{week}-"))
    prep = prepare_season(
        fz,
        args,
        season,
        work,
        f"M3-3 DvP {classification.lower()} forecast, {season} week {week} (TASK-20261124-006)",
    )
    cutoff = cutoff_of(prep.schedule, season, week)
    if classification == "PROSPECTIVE" and started >= cutoff:
        entry = append_ledger(
            ledger,
            {
                "season": season,
                "week": week,
                "classification": "MISSED",
                "recordedAt": now_utc().isoformat(),
                "cutoff": cutoff.isoformat(),
                "reason": "no forecast was archived before the cutoff",
            },
        )
        print(
            f"week {week}: cutoff {cutoff} has passed; recorded MISSED ({entry['entrySha256'][:12]})"
        )
        shutil.rmtree(work, ignore_errors=True)
        return 3
    ready, detail = readiness(prep.schedule, prep.season_rows, season, week, started)
    if classification == "PROSPECTIVE" and not ready:
        print(f"week {week}: inputs not complete yet; retry later: {json.dumps(detail)}")
        shutil.rmtree(work, ignore_errors=True)
        return 2
    frame, params = forecast_frame(fz, prep.rows, prep.schedule, season, week)
    week_games = prep.season_schedule.filter(pl.col("week") == week)
    playing = set(week_games.get_column("home").to_list()) | set(
        week_games.get_column("away").to_list()
    )
    every_team = set(prep.season_schedule.get_column("home").to_list()) | set(
        prep.season_schedule.get_column("away").to_list()
    )
    league = league_capture(engine_readonly(), every_team)
    league["playingThisWeek"] = sorted(playing)
    generated = now_utc()
    if classification == "PROSPECTIVE" and generated >= cutoff:
        raise SystemExit(
            "the cutoff passed while forecasting; nothing archived (rerun records MISSED)"
        )
    inputs = work / "inputs"
    inputs.mkdir()
    prep.season_rows.write_parquet(inputs / "observations-season.parquet")
    prep.season_schedule.write_parquet(inputs / "schedule-season.parquet")
    shutil.move(str(prep.store), str(inputs / "targets"))
    parquet = work / "forecasts.parquet"
    frame.sort(list(shadow.KEYS)).write_parquet(parquet)
    forecasts_csv = csv_bytes(frame)
    league_json = (json.dumps(league, indent=1, sort_keys=True) + "\n").encode()
    manifest: dict[str, Any] = {
        "format": FORMAT + "-forecast-v1",
        "classification": classification,
        "season": season,
        "week": week,
        "generatedAt": generated.isoformat(),
        "startedAt": started.isoformat(),
        "cutoff": cutoff.isoformat(),
        "minutesBeforeCutoff": round((cutoff - generated).total_seconds() / 60, 1),
        "code": code_version(),
        "adapter": shadow.ADAPTER,
        "config": {"path": "config/dvp/prospective.json", "sha256": sha256(CONFIG)},
        "frozen": fz.verification,
        "readiness": detail,
        "parameters": params,
        "lineage": prep.lineage,
        "inputs": {
            "observations-season.parquet": sha256(inputs / "observations-season.parquet"),
            "schedule-season.parquet": sha256(inputs / "schedule-season.parquet"),
        },
        "forecasts": {
            "rows": frame.height,
            "positions": dict(
                sorted(
                    (r["position"], r["len"])
                    for r in frame.group_by("position").len().iter_rows(named=True)
                )
            ),
            "columns": frame.columns,
            "csvSha256": sha256_bytes(forecasts_csv),
            "parquetSha256": sha256(parquet),
            "contentSha256": shadow.content_sha256(frame),
        },
        "league": {"sha256": sha256_bytes(league_json), "snapshotObservedAt": league["observedAt"]},
        "labels": "none: forecast-only; labels are joined only by `evaluate` after the games",
        "forbidden_vendor_projection_dependencies": 0,
        "write_to_production": False,
    }
    manifest_json = (json.dumps(manifest, indent=1, sort_keys=True, default=str) + "\n").encode()
    folder = root / (
        f"week-{week:02d}"
        if classification == "PROSPECTIVE"
        else f"week-{week:02d}-{classification.lower()}-{generated:%Y%m%dT%H%M%SZ}"
    )
    files = {
        "forecasts.parquet": parquet.read_bytes(),
        "forecasts.csv": forecasts_csv,
        "manifest.json": manifest_json,
        "league.json": league_json,
    }
    digests = write_once(folder, files, keep=inputs)
    entry = append_ledger(
        ledger,
        {
            "season": season,
            "week": week,
            "classification": classification,
            "recordedAt": now_utc().isoformat(),
            "generatedAt": generated.isoformat(),
            "cutoff": cutoff.isoformat(),
            "folder": folder.name,
            "files": digests,
            "contentSha256": manifest["forecasts"]["contentSha256"],
            "code": manifest["code"],
        },
    )
    if args.export:
        export(args, season, folder.name, files, ledger)
    shutil.rmtree(work, ignore_errors=True)
    print(
        f"week {week}: {classification} archived at {generated:%Y-%m-%d %H:%M:%S} UTC, "
        f"{manifest['minutesBeforeCutoff']} minutes before the cutoff; {frame.height} rows; "
        f"ledger {entry['entrySha256'][:12]}"
    )
    return 0


def forecast(args: argparse.Namespace) -> None:
    sys.exit(run_forecast(args, args.week, "PROSPECTIVE"))


def reconstruct(args: argparse.Namespace) -> None:
    sys.exit(run_forecast(args, args.week, "RETROSPECTIVE"))


def sweep(args: argparse.Namespace) -> None:
    """Forecast each window week when ready; record misses. Exits 0 unless something failed."""
    config = json.loads(CONFIG.read_text())
    codes = []
    for week in config["weeks"]:
        lines = read_ledger(
            archive_root(args, int(args.season or config["season"])) / "ledger.jsonl"
        )
        if any(e["classification"] in ("PROSPECTIVE", "MISSED") for e in entries_for(lines, week)):
            continue
        code = run_forecast(args, week, "PROSPECTIVE")
        codes.append((week, code))
        if code == 2:
            break  # later weeks need this week's results first
    print(json.dumps({"sweep": codes}))


# --- evaluation ----------------------------------------------------------------------------------


def evaluate_frame(
    fz: Frozen,
    forecasts: pl.DataFrame,
    labels: pl.DataFrame,
    leagues: dict[int, dict[str, Any]] | None = None,
    *,
    descriptive: str | None = None,
) -> dict[str, Any]:
    """The frozen Phase B protocol and Phase C rule on stored forecasts, keeping every target.

    A confirmation label (CONFIRMED / NOT_CONFIRMED) is assigned only for the complete,
    predeclared prospective window. Otherwise `descriptive` says why there is none, and the rule's
    outcome stays visible as `ruleOutcome`."""
    labelled = shadow.attach_labels(forecasts, labels)
    reps, seed = fz.group["protocol"]["bootstrapReplicates"], fz.group["protocol"]["seed"]
    minimum = fz.group["protocol"]["practicalMinimumRelativeRmse"]
    valid = labelled.filter(pl.col("label_status") == obs.VALID)
    variants = [c for c in shadow.forecast_columns(forecasts) if c != "b00_nontd"]
    phase_b: dict[str, Any] = {}
    for position in fz.positions:
        part = valid.filter(pl.col("position") == position)
        if part.is_empty():
            phase_b[position] = {"rows": 0}
            continue
        block = "week" if part.get_column("week").n_unique() > 1 else "game_id"
        entry = wf.metrics(part, variants, block=block, reps=reps, seed=seed)
        chosen = fz.candidates["positions"][position]
        candidate, best = chosen["candidate"], chosen["bestDvp"]
        if candidate != "b00":
            change = entry[candidate]["relativeDelta"]
            label = "CONFIRMED" if change is not None and change <= -minimum else "NOT_CONFIRMED"
        else:
            change, label = entry[best]["relativeDelta"], "NO_CANDIDATE (noted, never promoted)"
        phase_b[position] = {
            "candidate": candidate,
            "bestDvpAtFreeze": best,
            "relativeDelta": change,
            "label": label,
            "metrics": entry,
        }
    dst = labelled.filter((pl.col("position") == obs.DST) & (pl.col("label_status") != "missing"))
    models = ("b00", fz.group["periods"]["DST"]["candidate"])
    parameters = fz.phase_c["parameters"]
    table = decisions.units(dst, labels, models)
    phase_c: dict[str, Any] = {"units": table.height, "parameters": parameters}
    if table.height:
        pairs = decisions.pairs(table, models, "b00")
        m = decisions.metrics(
            table,
            pairs,
            "b00",
            models[1],
            close=parameters["close"],
            pool=tuple(parameters["waiverPoolRanks"]),
            top=parameters["top"],
            reps=parameters["bootstrapReplicates"],
            seed=parameters["seed"],
        )
        label, reason = decisions.decide(
            {"prospective": m}, fz.phase_c["practicalMinimumAccuracyPp"]
        )
        phase_c |= {
            "metrics": m,
            "rule": label,
            "reason": reason,
            "label": "CONFIRMED" if label == "PROMISING" else "NOT_CONFIRMED",
        }
    league_out: dict[str, Any] = {}
    for week, capture in sorted((leagues or {}).items()):
        week_rows = labelled.filter(pl.col("week") == week)
        choices = shadow.league_choices(
            week_rows, capture["rosters"], capture["freeAgents"], models
        )
        # Phase B: also the free agents claimable at once (captured from week 13; week 12's
        # capture has no availability states).
        claimable = [u for u, s in capture.get("availability", {}).items() if s == "FREE_AGENT"]
        if claimable:
            only = (
                shadow.league_choices(week_rows, capture["rosters"], claimable, models)
                .filter(pl.col("decision") == "stream")
                .with_columns(pl.lit("streamClaimableOnly").alias("decision"))
            )
            choices = pl.concat([choices, only])
        actual = valid.filter((pl.col("position") == obs.DST) & (pl.col("week") == week)).select(
            pl.col("defense").alias("unit"), "points"
        )
        scored = choices
        for model in models:
            scored = scored.join(
                actual.rename({"unit": f"pick_{model}", "points": f"pts_{model}"}),
                on=f"pick_{model}",
                how="left",
            )
        per_kind: dict[str, Any] = {}
        for (kind,), part in scored.group_by(["decision"], maintain_order=True):
            differ = part.filter(pl.col(f"pick_{models[0]}") != pl.col(f"pick_{models[1]}"))
            both = differ.filter(
                pl.col(f"pts_{models[0]}").is_not_null() & pl.col(f"pts_{models[1]}").is_not_null()
            )
            gain = [
                float(b) - float(a)
                for a, b in both.select(f"pts_{models[0]}", f"pts_{models[1]}").iter_rows()
            ]
            per_kind[str(kind)] = {
                "decisions": part.height,
                "differ": differ.height,
                "withLabels": both.height,
                "pointsB06MinusB00": sum(gain),
                "b06Better": (sum(g > 0 for g in gain) + 0.5 * sum(g == 0 for g in gain))
                / len(gain)
                if gain
                else None,
            }
        league_out[str(week)] = dict(sorted(per_kind.items()))
    if descriptive is not None:
        for value in [*phase_b.values(), phase_c]:
            if "label" in value:
                value["ruleOutcome"] = value["label"]
                value["label"] = descriptive
    return {
        "coverage": shadow.coverage(labelled),
        "phaseB": phase_b,
        "phaseC": phase_c,
        "league": league_out,
    }


def rehearse(args: argparse.Namespace) -> None:
    """2025 through the adapter, against the committed holdout forecasts, then evaluated."""
    fz = load_frozen()
    rows_all, schedule, lineage = history(fz, args.main)
    rows = shadow.prepare_checked(rows_all, fz.base["expected_scoring"])
    params = wf.fit_fold(rows, 2025, fz.positions)
    targets = shadow.scheduled_targets(schedule, 2025, None, fz.positions)
    frozen = shadow.walk_targets(rows, targets, schedule, params, fz.positions, fz.settings())
    adapter = shadow.forecast_only(frozen, targets)
    committed = pl.read_parquet(
        args.main / "artifacts/dvp" / fz.group["auditRun"] / "backtest-holdout/forecasts.parquet"
    )
    keys = list(shadow.KEYS)
    joined = committed.join(adapter, on=keys, how="left", suffix="_adapter")
    compared: dict[str, Any] = {}
    for column in sorted(c for c in committed.columns if c.startswith("b0")):
        a, b = joined.get_column(column), joined.get_column(f"{column}_adapter")
        both = a.is_not_null() & b.is_not_null()
        gap = (a.filter(both) - b.filter(both)).abs()
        compared[column] = {
            "maxAbsDifference": float(gap.max() or 0.0),  # type: ignore[arg-type]
            "nullPatternEqual": bool((a.is_null() == b.is_null()).all()),
        }
    controls = {c for c in compared if c.startswith("b09")}
    exact = all(
        v["maxAbsDifference"] <= 1e-9 and v["nullPatternEqual"]
        for c, v in compared.items()
        if c not in controls
    )
    extra = adapter.join(committed.select(keys), on=keys, how="anti")
    labels = rows_all.filter(pl.col("season") == 2025)
    by_week = {}
    for week in (12, 13, 14, 15, 16, 17, 18):
        part = adapter.filter(pl.col("week") == week)
        by_week[week] = part
    window = pl.concat(by_week.values())
    evaluation = evaluate_frame(
        fz, window, labels, descriptive="REHEARSAL: 2025 was known; never a confirmation"
    )
    receipt = {
        "format": FORMAT + "-rehearsal-v1",
        "generatedAt": now_utc().isoformat(),
        "code": code_version(),
        "classification": "REHEARSAL (2025, completed; never prospective)",
        "frozen": fz.verification,
        "history": lineage,
        "equivalence": {
            "committedRows": committed.height,
            "adapterRows": adapter.height,
            "adapterOnlyTargets": extra.height,
            "adapterOnlyByPosition": dict(
                sorted(
                    (r["position"], r["len"])
                    for r in extra.group_by("position").len().iter_rows(named=True)
                )
            ),
            "columns": compared,
            "everyNonControlColumnWithin1e-9": exact,
            "note": "B09 controls draw random numbers per batch; the adapter's extra targets "
            "(cells whose label turned out invalid) change the batch size, so controls may differ.",
        },
        "evaluationOfWeeks12to18": evaluation,
        "forbidden_vendor_projection_dependencies": 0,
    }
    out = Path(args.receipts) / "rehearsal-2025.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n")
    print(
        json.dumps(
            {
                "exact": exact,
                "adapterOnlyTargets": extra.height,
                "dst": evaluation["phaseB"].get("DST", {}).get("label"),
                "phaseC": evaluation["phaseC"].get("label"),
            }
        )
    )
    if not exact:
        sys.exit(1)


def evaluate(args: argparse.Namespace) -> None:
    config = json.loads(CONFIG.read_text())
    season = int(args.season or config["season"])
    root = archive_root(args, season)
    lines = read_ledger(root / "ledger.jsonl")
    problems = shadow.verify_ledger(lines)
    if problems:
        raise SystemExit("ledger is broken: " + "; ".join(problems))
    fz = load_frozen()
    status: dict[str, Any] = {}
    archived: dict[int, pl.DataFrame] = {}
    retrospective: dict[int, pl.DataFrame] = {}
    leagues: dict[int, dict[str, Any]] = {}
    weeks: list[int] = args.weeks or config["weeks"]
    for week in weeks:
        found = entries_for(lines, week)
        prospective = [e for e in found if e["classification"] == "PROSPECTIVE"]
        if prospective:
            e = prospective[0]
            folder = root / e["folder"]
            for name, digest in e["files"].items():
                if sha256(folder / name) != digest:
                    raise SystemExit(f"BLOCKED: {folder / name} does not match the ledger")
            archived[week] = pl.read_parquet(folder / "forecasts.parquet")
            leagues[week] = json.loads((folder / "league.json").read_text())
            status[str(week)] = "PROSPECTIVE"
        elif any(e["classification"] == "MISSED" for e in found):
            status[str(week)] = "MISSED"
        else:
            status[str(week)] = "PENDING"
        for e in found:
            if e["classification"] == "RETROSPECTIVE":
                retrospective[week] = pl.read_parquet(root / e["folder"] / "forecasts.parquet")
    work = Path(tempfile.mkdtemp(prefix=f"dvp-eval-{season}-"))
    labels_store = Path(args.labels) if args.labels else work / "targets"
    if args.labels:
        digest = json.loads((labels_store / "targets-current.json").read_text())["index"]
    else:
        digest = build_season(
            args.main, season, labels_store, f"M3-3 DvP prospective evaluation labels, {season}"
        )
    nflverse = Path(os.environ.get("ARBIT_NFLVERSE_PATH", args.main / "data/nflverse"))
    labels, label_schedule, label_lineage = season_observations(
        fz, labels_store, digest, season, engine_readonly(), nflverse
    )
    weeks_done = set(
        label_schedule.filter(pl.col("status") == "completed").get_column("week").unique().to_list()
    )
    predeclared = weeks == config["weeks"]
    complete = (
        predeclared
        and all(status[str(w)] in ("PROSPECTIVE", "MISSED") for w in weeks)
        and all(w in weeks_done for w in weeks)
    )
    result: dict[str, Any] = {
        "weeks": status,
        "predeclaredWindow": predeclared,
        "windowComplete": complete,
    }
    if archived:
        frame = pl.concat(list(archived.values()), how="vertical_relaxed")
        result["prospective"] = evaluate_frame(
            fz,
            frame,
            labels,
            leagues,
            descriptive=None
            if complete
            else "INTERIM: no label until the predeclared window is complete",
        )
    if retrospective:
        result["retrospectiveOnly"] = evaluate_frame(
            fz,
            pl.concat(list(retrospective.values()), how="vertical_relaxed"),
            labels,
            descriptive="RETROSPECTIVE: made after the cutoff; never a confirmation",
        )
    receipt = {
        "format": FORMAT + "-evaluation-v1",
        "generatedAt": now_utc().isoformat(),
        "code": code_version(),
        "season": season,
        "frozen": fz.verification,
        "labels": label_lineage,
        **result,
        "forbidden_vendor_projection_dependencies": 0,
    }
    name = "evaluation.json" if predeclared else f"evaluation-weeks-{min(weeks)}-{max(weeks)}.json"
    out = Path(args.receipts) / str(season) / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n")
    shutil.rmtree(work, ignore_errors=True)
    print(json.dumps({"weeks": status, "windowComplete": complete}))


def verify(args: argparse.Namespace) -> None:
    config = json.loads(CONFIG.read_text())
    season = int(args.season or config["season"])
    root = archive_root(args, season)
    lines = read_ledger(root / "ledger.jsonl")
    problems = shadow.verify_ledger(lines)
    for e in lines:
        if e["classification"] in ("PROSPECTIVE", "RETROSPECTIVE"):
            for name, digest in e["files"].items():
                if sha256(root / e["folder"] / name) != digest:
                    problems.append(f"{e['folder']}/{name} does not match the ledger")
            if e["classification"] == "PROSPECTIVE" and e["generatedAt"] >= e["cutoff"]:
                problems.append(f"week {e['week']}: generated after its cutoff")
            exported = Path(args.export) / str(season) / e["folder"] if args.export else None
            if exported is not None and exported.exists():
                for name in ("forecasts.csv", "manifest.json", "league.json"):
                    if sha256(exported / name) != e["files"][name]:
                        problems.append(f"export {e['folder']}/{name} differs from the archive")
    print(json.dumps({"entries": len(lines), "problems": problems}))
    if problems:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--main", type=Path, default=ROOT, help="checkout holding data/ and artifacts/"
    )
    parser.add_argument("--archive", type=Path, help="default: <main>/artifacts/dvp/prospective")
    parser.add_argument("--export", type=Path, default=ROOT / "docs/research/dvp/prospective")
    parser.add_argument("--season", type=int)
    commands = parser.add_subparsers(dest="command", required=True)
    f = commands.add_parser("forecast")
    f.add_argument("--week", type=int, required=True)
    r = commands.add_parser("reconstruct")
    r.add_argument("--week", type=int, required=True)
    commands.add_parser("sweep")
    h = commands.add_parser("rehearse")
    h.add_argument("--receipts", type=Path, default=ROOT / "docs/research/dvp/prospective")
    e = commands.add_parser("evaluate")
    e.add_argument("--labels", type=Path, help="a targets store built after the games")
    e.add_argument(
        "--weeks",
        type=lambda v: [int(w) for w in v.split(",")],
        help="weeks other than the predeclared window, for checks only: never a confirmation",
    )
    e.add_argument("--receipts", type=Path, default=ROOT / "docs/research/dvp/prospective")
    commands.add_parser("verify")
    args = parser.parse_args()
    args.main = args.main.resolve()
    {
        "forecast": forecast,
        "reconstruct": reconstruct,
        "sweep": sweep,
        "rehearse": rehearse,
        "evaluate": evaluate,
        "verify": verify,
    }[args.command](args)


if __name__ == "__main__":
    main()
