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
import base64
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore
from arbit_model import teams
from arbit_model.dvp import (
    archive,
    asof,
    contract,
    decisions,
    evidence,
    lab,
    league,
    provenance,
    reliability,
    shadow,
)
from arbit_model.dvp import observations as obs
from arbit_model.dvp import walkforward as wf
from arbit_model.dvp import window as gate
from arbit_model.inputs import NflverseTables
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/dvp/prospective.json"
AMENDMENT = ROOT / "config/dvp/prospective-amendment-1.json"
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


STATISTICS_FILE = "stats_player/stats_player_week_{season}"


def statistics_revisions(
    engine: Any, manifests: dict[str, str], season: int
) -> tuple[datetime | None, datetime | None]:
    """When nflverse last revised the player-statistics file the build read, and the newest
    revision Arbit's catalog has seen (to tell 'not yet published' from 'not yet imported')."""
    key = STATISTICS_FILE.format(season=season)
    with engine.connect() as c:
        held = c.execute(
            text(
                "select payload->'source'->>'source_updated_at' from dataset_manifest "
                "where hash = :h"
            ),
            {"h": manifests.get(key, "")},
        ).scalar()
        newest = c.execute(
            text(
                "select max(a->>'source_updated_at') from nflverse_catalog, "
                "jsonb_array_elements(payload->'assets') a where a->>'logical_key' = :k"
            ),
            {"k": f"nflverse/nflverse-data/{key}"},
        ).scalar()

    def parse(value: str | None) -> datetime | None:
        return None if not value else datetime.fromisoformat(value.replace("Z", "+00:00"))

    return parse(held), parse(newest)


def readiness(
    schedule: pl.DataFrame,
    observations: pl.DataFrame,
    season: int,
    week: int,
    now: datetime,
    held: datetime | None = None,
    catalog: datetime | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Are the inputs the frozen method would use at week W's cutoff all present now? Every
    earlier game gets a state (config/dvp/prospective-amendment-1.json, readiness)."""
    return gate.game_readiness(
        schedule, observations, season, week, now, NO_RESULT_GRACE, held, catalog
    )


OBSERVED = {"owned": "OWNED", "free_agent": "FREE_AGENT", "waivers": "WAIVERS"}
CAPTURE_FORMAT = FORMAT + "-league-capture-v2"


def league_capture(
    engine: Any,
    schedule_teams: set[str],
    now: datetime,
    snapshot_id: str | None = None,
) -> dict[str, Any]:
    """The league's D/ST state from one snapshot, read in one repeatable-read transaction
    (config/dvp/prospective-amendment-1.json, leagueCapture).

    Ownership comes from the snapshot's roster entries; availability is what ESPN reported in the
    same snapshot. Every team is listed, including any holding no D/ST. A unit whose roster entry
    and reported availability disagree is UNKNOWN and the capture is marked contradictory. A
    drop-time reconstruction is kept only as a labelled fallback, never as observed."""
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as c:
        if snapshot_id is None:
            snapshot = c.execute(
                text(
                    "select s.id, s.observed_at, s.content_hash, d.rules_hash, d.payload "
                    "from league_snapshot s join current_snapshot c on c.snapshot_id = s.id "
                    "join league_document d on d.snapshot_id = s.id"
                )
            ).one()
        else:
            snapshot = c.execute(
                text(
                    "select s.id, s.observed_at, s.content_hash, d.rules_hash, d.payload "
                    "from league_snapshot s join league_document d on d.snapshot_id = s.id "
                    "where s.id = :s"
                ),
                {"s": snapshot_id},
            ).one()
        rules = c.execute(
            text("select payload from rule_version where hash = :h"), {"h": snapshot.rules_hash}
        ).scalar_one()
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
        nfl = {
            str(entity): str(abbreviation)
            for entity, abbreviation in c.execute(
                text("select entity_id::text, abbreviation from nfl_team")
            )
        }
        drops = c.execute(
            text(
                "select max(case when t.type = 'WAIVER' then t.processed_at "
                "else t.proposed_at end) as dropped, n.abbreviation "
                "from fantasy_transaction t, jsonb_array_elements(t.items) i "
                "join canonical_entity e on e.id = (i->>'player_id')::uuid "
                "and e.kind = 'defense_unit' "
                "join team_affiliation a on a.entity_id = e.id and a.valid_to is null "
                "join nfl_team n on n.entity_id = a.team_id "
                "where t.status = 'EXECUTED' and i->>'type' = 'DROP' "
                "and (case when t.type = 'WAIVER' then t.processed_at else t.proposed_at end) "
                "<= :at "
                "group by n.abbreviation"
            ),
            {"at": snapshot.observed_at},
        ).all()

    def code(abbreviation: str) -> str:
        return ESPN_TO_FRANCHISE.get(abbreviation, abbreviation)

    document = snapshot.payload
    teams = sorted(str(t["id"]) for t in document["teams"])
    rosters: dict[str, list[str]] = {t: [] for t in teams}
    slots: dict[str, dict[str, str]] = {t: {} for t in teams}
    owner: dict[str, str] = {}
    for team_id, abbreviation, slot in held:
        unit = code(abbreviation)
        rosters.setdefault(str(team_id), []).append(unit)
        slots.setdefault(str(team_id), {})[unit] = slot
        owner[unit] = str(team_id)
    reported: dict[str, tuple[str, str | None]] = {}
    for player in document["players"]:
        if player.get("kind") != "defense_unit":
            continue
        unit = code(nfl.get(str(player.get("nfl_team_id")), "?"))
        reported[unit] = (
            str(player.get("availability")),
            None if player.get("team_id") is None else str(player.get("team_id")),
        )
    units = sorted(set(reported) | set(owner))
    availability: dict[str, str] = {}
    contradictions: list[dict[str, Any]] = []
    for unit in units:
        state, team = reported.get(unit, ("missing", None))
        observed = OBSERVED.get(state, "UNKNOWN")
        if unit in owner and (observed != "OWNED" or team != owner[unit]):
            contradictions.append({"unit": unit, "roster": owner[unit], "reported": [state, team]})
            observed = "UNKNOWN"
        elif unit not in owner and observed == "OWNED":
            contradictions.append({"unit": unit, "roster": None, "reported": [state, team]})
            observed = "UNKNOWN"
        availability[unit] = observed
    hours = int(rules["waiver_hours"])
    last_drop = {code(r.abbreviation): r.dropped for r in drops}
    fallback: dict[str, str] = {}
    for unit in units:
        if unit in owner:
            fallback[unit] = "OWNED"
        elif unit in last_drop and snapshot.observed_at - last_drop[unit] < timedelta(hours=hours):
            fallback[unit] = "WAIVERS"
        elif unit in last_drop and snapshot.observed_at - last_drop[unit] < timedelta(
            hours=2 * hours
        ):
            fallback[unit] = "WAIVERS_OR_FREE_AGENT"
        else:
            fallback[unit] = "FREE_AGENT"
    unknown = sorted(u for u in units if u not in schedule_teams)
    if unknown or len(units) != 32:
        raise SystemExit(f"BLOCKED: D/ST universe is not the schedule's 32 teams: {unknown}")
    rostered = set(owner)
    return {
        "format": CAPTURE_FORMAT,
        "snapshotId": str(snapshot.id),
        "observedAt": snapshot.observed_at.isoformat(),
        "contentHash": snapshot.content_hash,
        "rulesHash": snapshot.rules_hash,
        "capturedAt": now.isoformat(),
        "snapshotAgeMinutes": round((now - snapshot.observed_at).total_seconds() / 60, 1),
        "teams": teams,
        "rosters": {t: sorted(u) for t, u in sorted(rosters.items())},
        "slots": slots,
        "freeAgents": sorted(set(units) - rostered),
        "availability": availability,
        "availabilityBasis": "observed: ESPN's reported availability in the same snapshot",
        "contradictions": contradictions,
        "reconstructedFallback": {
            "basis": "drop times and the waiver hold; not observed, used only if observed is UNKNOWN",
            "states": fallback,
        },
        "waiverHours": hours,
        "waiverType": rules.get("waiver_type"),
        "lineupLockType": rules.get("lineup_lock_type"),
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


def files_match(folder: Path, files: dict[str, str]) -> bool:
    """Every file a ledger entry names still has the hash the entry recorded."""
    try:
        return all(sha256(folder / name) == digest for name, digest in files.items())
    except OSError:
        return False


def league_for_evaluation(root: Path, entry: dict[str, Any], folder: Path) -> dict[str, Any]:
    """The league state a week's descriptive league evaluation uses: the capture archived with the
    forecasts, replaced by the last decision-time capture before the cutoff when one exists
    (config/dvp/prospective-amendment-1.json, leagueCapture)."""
    capture: dict[str, Any] = json.loads((folder / "league.json").read_text())
    capture["source"] = "forecast-time capture"
    if capture.get("format") != CAPTURE_FORMAT:
        # A capture from before amendment 1 (week 12) has no observed availability; a separately
        # versioned supplement read from the same snapshot may supply it.
        for record in read_ledger(root / "supplements.jsonl"):
            path = root / record["file"]
            if record.get("week") == entry["week"] and sha256(path) == record["sha256"]:
                observed = json.loads(path.read_text())["capture"]
                capture["availability"] = observed["availability"]
                capture["availabilityBasis"] = "SUPPLEMENTAL: " + observed["availabilityBasis"]
                capture["teams"] = observed["teams"]
                capture["source"] = "forecast-time capture with supplemental observed availability"
    later = [
        c
        for c in read_ledger(root / "captures.jsonl")
        if c.get("week") == entry["week"] and c.get("observedAt", "") < entry["cutoff"]
    ]
    if later:
        last = later[-1]
        path = root / last["file"]
        if sha256(path) == last["sha256"]:
            capture = json.loads(path.read_text()) | {"source": "last capture before the cutoff"}
    return capture


def export(
    args: argparse.Namespace, season: int, week_folder: str, files: dict[str, bytes], ledger: Path
) -> None:
    """Copy a week's forecasts and manifest, and the ledger, for committing. The league capture
    holds per-team rosters, so it stays in the local archive; the manifest carries its hash."""
    target = Path(args.export) / str(season)
    folder = target / week_folder
    if folder.exists():
        raise SystemExit(f"{folder} exists; exported forecasts are never overwritten")
    folder.mkdir(parents=True)
    for name in ("forecasts.csv", "manifest.json"):
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


def run_forecast(
    args: argparse.Namespace, week: int, classification: str
) -> tuple[int, dict[str, Any]]:
    """Forecast and archive one week. Returns (0 archived, 2 waiting, 3 missed) and what was
    found. Call under `archive.exclusive`."""
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
        return 0, {"week": week, "state": previous[0]["classification"]}
    fz = load_frozen()
    started = now_utc()
    work = Path(tempfile.mkdtemp(prefix=f"dvp-{season}-w{week}-"))
    try:
        return _forecast_in(args, fz, season, root, ledger, week, classification, started, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _forecast_in(
    args: argparse.Namespace,
    fz: Frozen,
    season: int,
    root: Path,
    ledger: Path,
    week: int,
    classification: str,
    started: datetime,
    work: Path,
) -> tuple[int, dict[str, Any]]:
    prep = prepare_season(
        fz,
        args,
        season,
        work,
        f"M3-3 DvP {classification.lower()} forecast, {season} week {week} (TASK-20261124-006)",
    )
    cutoff = cutoff_of(prep.schedule, season, week)
    info: dict[str, Any] = {"week": week, "cutoff": cutoff.isoformat()}
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
        print(f"week {week}: cutoff {cutoff} passed; recorded MISSED ({entry['entrySha256'][:12]})")
        return 3, info | {"state": "MISSED"}
    engine = engine_readonly()
    held, catalog = statistics_revisions(
        engine, prep.lineage["season"]["nflverseManifests"], season
    )
    ready, detail = readiness(prep.schedule, prep.season_rows, season, week, started, held, catalog)
    info["readiness"] = detail
    if classification == "PROSPECTIVE" and not ready:
        print(
            f"week {week}: inputs not complete yet; retry later: {json.dumps(detail['blocking'])}"
        )
        return 2, info | {"state": "WAITING"}
    frame, params = forecast_frame(fz, prep.rows, prep.schedule, season, week)
    week_games = prep.season_schedule.filter(pl.col("week") == week)
    playing = set(week_games.get_column("home").to_list()) | set(
        week_games.get_column("away").to_list()
    )
    every_team = set(prep.season_schedule.get_column("home").to_list()) | set(
        prep.season_schedule.get_column("away").to_list()
    )
    generated = now_utc()
    league = league_capture(engine, every_team, generated)
    league["playingThisWeek"] = sorted(playing)
    league["week"] = week
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
        "format": FORMAT + "-forecast-v2",
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
        "amendment": {
            "path": "config/dvp/prospective-amendment-1.json",
            "sha256": sha256(AMENDMENT),
        },
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
        "league": {
            "sha256": sha256_bytes(league_json),
            "snapshotObservedAt": league["observedAt"],
            "snapshotAgeMinutes": league["snapshotAgeMinutes"],
            "contradictions": len(league["contradictions"]),
        },
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
    stored = archive.commit(folder, files, now_utc, inputs=inputs)
    archived_at: datetime = stored["archivedAt"]
    if classification == "PROSPECTIVE" and archived_at >= cutoff:
        append_ledger(
            ledger,
            {
                "season": season,
                "week": week,
                "classification": "MISSED",
                "recordedAt": now_utc().isoformat(),
                "cutoff": cutoff.isoformat(),
                "folder": folder.name,
                "reason": "archival completed at or after the cutoff; kept as evidence only",
            },
        )
        return 3, info | {"state": "MISSED"}
    entry = append_ledger(
        ledger,
        {
            "season": season,
            "week": week,
            "classification": classification,
            "recordedAt": now_utc().isoformat(),
            "generatedAt": generated.isoformat(),
            "archivedAt": archived_at.isoformat(),
            "cutoff": cutoff.isoformat(),
            "folder": folder.name,
            "files": stored["files"],
            "contentSha256": manifest["forecasts"]["contentSha256"],
            "code": manifest["code"],
        },
    )
    if args.export:
        export(args, season, folder.name, files, ledger)
    print(
        f"week {week}: {classification} archived at {archived_at:%Y-%m-%d %H:%M:%S} UTC, "
        f"{manifest['minutesBeforeCutoff']} minutes before the cutoff; {frame.height} rows; "
        f"ledger {entry['entrySha256'][:12]}"
    )
    return 0, info | {"state": "ARCHIVED", "entrySha256": entry["entrySha256"]}


def recover_archive(args: argparse.Namespace, season: int) -> list[dict[str, Any]]:
    """Resolve an interrupted run's leftovers (archive.recover) and record each resolution."""
    root = archive_root(args, season)
    ledger = root / "ledger.jsonl"
    lines = read_ledger(ledger)
    now = now_utc()
    actions = archive.recover(root, lines, {}, now)
    for action in actions:
        if action["action"] == "recover":
            m = action["manifest"]
            append_ledger(
                ledger,
                {
                    "season": season,
                    "week": action["week"],
                    "classification": m["classification"],
                    "recordedAt": now.isoformat(),
                    "generatedAt": m["generatedAt"],
                    "archivedAt": now.isoformat(),
                    "archivedAtBasis": "recovered: the archive existed no later than this time",
                    "cutoff": m["cutoff"],
                    "folder": action["folder"],
                    "files": action["files"],
                    "contentSha256": m["forecasts"]["contentSha256"],
                    "code": m["code"],
                    "recovered": True,
                },
            )
        elif action["action"] == "missed-unproven":
            append_ledger(
                ledger,
                {
                    "season": season,
                    "week": action["week"],
                    "classification": "MISSED",
                    "recordedAt": now.isoformat(),
                    "folder": action["folder"],
                    "reason": "an archive without a ledger entry was found after the cutoff; "
                    "durable archival before the cutoff is not proven",
                },
            )
    return actions


def forecast(args: argparse.Namespace) -> None:
    season = int(args.season or json.loads(CONFIG.read_text())["season"])
    with archive.exclusive(archive_root(args, season)):
        recover_archive(args, season)
        code, _ = run_forecast(args, args.week, "PROSPECTIVE")
        publish_pending(args, season)
    sys.exit(code)


def reconstruct(args: argparse.Namespace) -> None:
    season = int(args.season or json.loads(CONFIG.read_text())["season"])
    with archive.exclusive(archive_root(args, season)):
        code, _ = run_forecast(args, args.week, "RETROSPECTIVE")
    sys.exit(code)


ALERT_WINDOW = timedelta(hours=18)


def write_status(root: Path, record: dict[str, Any]) -> None:
    """status.json beside the ledger, replaced atomically on every run."""
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / ".status.json.tmp"
    temporary.write_text(json.dumps(record, indent=1, sort_keys=True, default=str) + "\n")
    os.replace(temporary, root / "status.json")


def alert(root: Path, title: str, message: str) -> None:
    """An actionable alert: the service journal, alerts.jsonl beside the ledger, and a Windows
    notification on this PC when Windows is reachable from WSL."""
    print(f"ALERT: {title}: {message}", file=sys.stderr)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "alerts.jsonl").open("a") as handle:
        handle.write(json.dumps({"at": now_utc().isoformat(), "title": title, "message": message}))
        handle.write("\n")
    powershell = shutil.which("powershell.exe")
    if powershell is None or os.environ.get("ARBIT_DVP_NO_TOAST"):
        return

    def quoted(value: str) -> str:
        return "'" + value.replace("'", "''")[:240] + "'"

    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] > $null;"
        "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        "$t = $x.GetElementsByTagName('text');"
        f"$null = $t.Item(0).AppendChild($x.CreateTextNode({quoted('Arbit research: ' + title)}));"
        f"$null = $t.Item(1).AppendChild($x.CreateTextNode({quoted(message)}));"
        "$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe';"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app)"
        ".Show([Windows.UI.Notifications.ToastNotification]::new($x))"
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    subprocess.run(  # noqa: S603
        [powershell, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True,
        timeout=60,
        check=False,
    )


def sweep(args: argparse.Namespace) -> None:
    """Forecast each window week when ready, record misses, capture the league before each
    archived week's cutoff and publish pending commitments. Safe to run repeatedly; one run at a
    time. Exits 0 unless something failed."""
    config = json.loads(CONFIG.read_text())
    season = int(args.season or config["season"])
    root = archive_root(args, season)
    status: dict[str, Any] = {"run": now_utc().isoformat(), "code": code_version(), "weeks": {}}
    failed = False
    try:
        with archive.exclusive(root):
            status["recovery"] = recover_archive(args, season)
            for action in status["recovery"]:
                if action["action"] in ("quarantined", "missed-unproven"):
                    alert(root, "archive recovery", json.dumps(action, default=str)[:200])
            for week in config["weeks"]:
                lines = read_ledger(root / "ledger.jsonl")
                done = [
                    e
                    for e in entries_for(lines, week)
                    if e["classification"] in ("PROSPECTIVE", "MISSED")
                ]
                if done:
                    status["weeks"][str(week)] = {"state": done[0]["classification"]}
                    continue
                code, info = run_forecast(args, week, "PROSPECTIVE")
                status["weeks"][str(week)] = info
                if code == 3:
                    alert(root, f"week {week} missed", f"cutoff {info['cutoff']} passed")
                if code == 2:
                    left = datetime.fromisoformat(info["cutoff"]) - now_utc()
                    if left < ALERT_WINDOW:
                        alert(
                            root,
                            f"week {week} not ready",
                            f"{left.total_seconds() / 3600:.1f} h to the cutoff; blocking: "
                            + json.dumps(info["readiness"]["blocking"])[:160],
                        )
                    break  # later weeks need this week's results first
            status["captures"] = capture_pending(args, season)
            status["publications"] = publish_pending(args, season)
            for record in status["publications"]:
                if not record.get("verified"):
                    left = datetime.fromisoformat(record["cutoff"]) - now_utc()
                    if left < ALERT_WINDOW:
                        alert(
                            root,
                            f"week {record['week']} commitment not verified",
                            f"{record.get('result')}: {record.get('error') or ''}"[:200],
                        )
            status["outcome"] = "OK"
    except archive.Busy as error:
        status["outcome"] = "BUSY"
        status["error"] = str(error)
        print(str(error))
    except (SystemExit, Exception) as error:  # noqa: BLE001 - every failure is reported
        failed = True
        status["outcome"] = "FORECAST_EXECUTION_FAILURE"
        status["error"] = f"{type(error).__name__}: {error}"[:500]
        alert(root, "sweep failed", status["error"][:200])
    if status["outcome"] != "BUSY":
        write_status(root, status)
    print(json.dumps({k: status.get(k) for k in ("outcome", "weeks")}, default=str))
    if failed:
        sys.exit(1)


# --- decision-time league captures, supplements and external evidence ---------------------------


def _write_once(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:  # refuses an existing file
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o444)
    return sha256_bytes(data)


def _schedule_teams(folder: Path, week: int) -> tuple[set[str], list[str]]:
    schedule = pl.read_parquet(folder / "inputs/schedule-season.parquet")
    every = set(schedule.get_column("home").to_list()) | set(schedule.get_column("away").to_list())
    games = schedule.filter(pl.col("week") == week)
    playing = set(games.get_column("home").to_list()) | set(games.get_column("away").to_list())
    return every, sorted(playing)


def capture_pending(args: argparse.Namespace, season: int) -> list[dict[str, Any]]:
    """For each archived week whose cutoff hasn't passed, record the league as it stands when its
    snapshot changed since the last capture (the decision-time state)."""
    root = archive_root(args, season)
    captures_log = root / "captures.jsonl"
    now = now_utc()
    out = []
    for e in read_ledger(root / "ledger.jsonl"):
        if e["classification"] != "PROSPECTIVE" or datetime.fromisoformat(e["cutoff"]) <= now:
            continue
        folder = root / e["folder"]
        every, playing = _schedule_teams(folder, e["week"])
        capture = league_capture(engine_readonly(), every, now)
        capture |= {"week": e["week"], "playingThisWeek": playing}
        earlier = [c for c in read_ledger(captures_log) if c.get("week") == e["week"]]
        last = earlier[-1]["snapshotId"] if earlier else None
        if last is None:
            last = json.loads((folder / "league.json").read_text()).get("snapshotId")
        if capture["snapshotId"] == last:
            continue
        observed = datetime.fromisoformat(capture["observedAt"])
        name = f"captures/week-{e['week']:02d}-{observed:%Y%m%dT%H%M%SZ}.json"
        data = (json.dumps(capture, indent=1, sort_keys=True) + "\n").encode()
        digest = _write_once(root / name, data)
        record = append_ledger(
            captures_log,
            {
                "week": e["week"],
                "file": name,
                "sha256": digest,
                "snapshotId": capture["snapshotId"],
                "observedAt": capture["observedAt"],
                "capturedAt": capture["capturedAt"],
                "contradictions": len(capture["contradictions"]),
            },
        )
        out.append({"week": e["week"], "file": name, "entrySha256": record["entrySha256"]})
    return out


def evidence_settings() -> tuple[str | None, str | None, dict[str, str]]:
    remote = os.environ.get("ARBIT_EVIDENCE_REMOTE")
    slug = os.environ.get("ARBIT_EVIDENCE_SLUG")
    key = os.environ.get("ARBIT_EVIDENCE_KEY")
    env = {"GIT_SSH_COMMAND": f"ssh -i {key} -o IdentitiesOnly=yes -o BatchMode=yes"} if key else {}
    return remote, slug, env


def publish_pending(args: argparse.Namespace, season: int) -> list[dict[str, Any]]:
    """Publish and verify the commitment of every prospective archive without a verified one.
    Each attempt is recorded in publications.jsonl; nothing is regenerated."""
    root = archive_root(args, season)
    log = root / "publications.jsonl"
    branch = json.loads(AMENDMENT.read_text())["externalEvidence"]["branch"]
    # Every archive gets its evidence-branch commitment, even one with other verified evidence.
    verified = {
        p["ledgerEntrySha256"]
        for p in read_ledger(log)
        if p.get("verified") and p.get("kind") == "github-branch"
    }
    remote, slug, env = evidence_settings()
    clone = root.parent / "evidence-clone"
    out = []
    for e in read_ledger(root / "ledger.jsonl"):
        if e["classification"] != "PROSPECTIVE" or e["entrySha256"] in verified:
            continue
        folder = root / e["folder"]
        record: dict[str, Any] = {
            "kind": "github-branch",
            "week": e["week"],
            "ledgerEntrySha256": e["entrySha256"],
            "attemptAt": now_utc().isoformat(),
            "ref": f"refs/heads/{branch}",
            "cutoff": e["cutoff"],
            "verified": False,
        }
        if not files_match(folder, e["files"]):
            record |= {"result": "archive-mismatch", "error": "the archive no longer matches"}
        elif not remote or not slug:
            record |= {"result": "not-configured", "error": "ARBIT_EVIDENCE_REMOTE/SLUG unset"}
        else:
            payload = (
                json.dumps(evidence.commitment(e, sha256(AMENDMENT)), indent=1, sort_keys=True)
                + "\n"
            ).encode()
            commitment_path, csv_path = evidence.paths_for(e)
            files = {commitment_path: payload, csv_path: (folder / "forecasts.csv").read_bytes()}
            expected = {path: sha256_bytes(data) for path, data in files.items()}
            try:
                pushed = evidence.publish(
                    clone,
                    remote,
                    branch,
                    files,
                    f"M3-3 DvP prospective commitment: {season} week {e['week']}",
                    env,
                )
                problems = evidence.verify_remote(clone, branch, pushed["commit"], expected, env)
                stamp, activity = None, None
                for attempt in range(6):
                    if problems:
                        break
                    stamp, activity = evidence.external_timestamp(
                        clone, pushed["commit"], evidence.read_activity(slug, branch)
                    )
                    if stamp or attempt == 5:
                        break
                    time.sleep(10)
                record |= {
                    "commit": pushed["commit"],
                    "files": expected,
                    "remoteProblems": problems,
                    "externalTimestamp": stamp,
                    "activityId": None if activity is None else activity.get("id"),
                    "verified": bool(stamp) and not problems,
                    "beforeCutoff": evidence.before(stamp, datetime.fromisoformat(e["cutoff"])),
                    "result": "verified"
                    if stamp and not problems
                    else ("remote-mismatch" if problems else "pushed-awaiting-timestamp"),
                }
            except (
                evidence.PublicationError,
                OSError,
                subprocess.SubprocessError,
                ValueError,
            ) as error:
                record |= {"result": "failed", "error": str(error)[:300]}
        append_ledger(log, record)
        out.append(record)
    return out


def publish(args: argparse.Namespace) -> None:
    season = int(args.season or json.loads(CONFIG.read_text())["season"])
    with archive.exclusive(archive_root(args, season)):
        records = publish_pending(args, season)
    print(json.dumps(records, indent=1, default=str))
    if any(not r.get("verified") for r in records):
        sys.exit(1)


def record_prior(args: argparse.Namespace) -> None:
    """Record a week's earlier external publication (week 12's GitHub push) once verified:
    GitHub's activity record of the push, and the pushed files equal to the ledger's hashes."""
    season = int(args.season or json.loads(CONFIG.read_text())["season"])
    root = archive_root(args, season)
    _, slug, _ = evidence_settings()
    slug = slug or args.slug
    entry = next(
        e
        for e in read_ledger(root / "ledger.jsonl")
        if e.get("week") == args.week and e["classification"] == "PROSPECTIVE"
    )
    problems = []
    for name in ("forecasts.csv", "manifest.json", "league.json"):
        shown = subprocess.run(
            ["git", "show", f"{args.commit}:{args.path}/{name}"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        if shown.returncode != 0 or sha256_bytes(shown.stdout) != entry["files"][name]:
            problems.append(f"{name} at {args.commit[:12]} differs from the ledger")
    stamp, activity = evidence.external_timestamp(
        ROOT, args.commit, evidence.read_activity(slug, args.ref)
    )
    record = {
        "kind": "prior-github-push",
        "week": args.week,
        "ledgerEntrySha256": entry["entrySha256"],
        "attemptAt": now_utc().isoformat(),
        "ref": f"refs/heads/{args.ref}",
        "commit": args.commit,
        "path": args.path,
        "remoteProblems": problems,
        "externalTimestamp": stamp,
        "activityId": None if activity is None else activity.get("id"),
        "cutoff": entry["cutoff"],
        "verified": bool(stamp) and not problems,
        "beforeCutoff": evidence.before(stamp, datetime.fromisoformat(entry["cutoff"])),
        "result": "verified" if stamp and not problems else "not-verified",
    }
    with archive.exclusive(root):
        append_ledger(root / "publications.jsonl", record)
    print(json.dumps(record, indent=1, default=str))


def supplement(args: argparse.Namespace) -> None:
    """A separately versioned record of the availability ESPN reported in the snapshot a week's
    original capture used (PB-AUD-07). The original archive is not touched."""
    season = int(args.season or json.loads(CONFIG.read_text())["season"])
    root = archive_root(args, season)
    entry = next(
        e
        for e in read_ledger(root / "ledger.jsonl")
        if e.get("week") == args.week and e["classification"] == "PROSPECTIVE"
    )
    folder = root / entry["folder"]
    original = json.loads((folder / "league.json").read_text())
    every, playing = _schedule_teams(folder, args.week)
    now = now_utc()
    capture = league_capture(engine_readonly(), every, now, snapshot_id=original["snapshotId"])
    same = {t: u for t, u in capture["rosters"].items() if u} == original["rosters"]
    record = {
        "format": FORMAT + "-league-supplement-v1",
        "classification": "SUPPLEMENTAL",
        "season": season,
        "week": args.week,
        "createdAt": now.isoformat(),
        "basis": "Read after the forecast from the stored snapshot the week's original capture "
        "named; the original archive is unchanged. Observed availability as ESPN reported it in "
        "that snapshot.",
        "forecastArchive": {
            "folder": entry["folder"],
            "entrySha256": entry["entrySha256"],
            "leagueSha256": entry["files"]["league.json"],
        },
        "rostersEqualOriginal": same,
        "snapshotAgeAtForecastMinutes": round(
            (
                datetime.fromisoformat(entry["generatedAt"])
                - datetime.fromisoformat(capture["observedAt"])
            ).total_seconds()
            / 60,
            1,
        ),
        "capture": capture | {"week": args.week, "playingThisWeek": playing},
    }
    data = (json.dumps(record, indent=1, sort_keys=True) + "\n").encode()
    name = f"supplements/week-{args.week:02d}-availability-v1.json"
    with archive.exclusive(root):
        digest = _write_once(root / name, data)
        append_ledger(
            root / "supplements.jsonl",
            {"week": args.week, "file": name, "sha256": digest, "kind": "observed-availability"},
        )
    print(json.dumps({"file": name, "sha256": digest, "rostersEqualOriginal": same}))


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
        league_out[str(week)] = league_week(labelled, valid, capture, week, models)
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


LEAGUE_KINDS = {
    # kind: (decision, which unowned units join the held ones)
    "rosterOnly": (league.START, ()),
    "unownedPool": (league.STREAM, ("FREE_AGENT", "WAIVERS", "UNKNOWN", "*")),
    "claimablePool": (league.STREAM, ("FREE_AGENT",)),
    "claimableWithWaivers": (league.STREAM, ("FREE_AGENT", "WAIVERS")),
}


def league_week(
    labelled: pl.DataFrame,
    valid: pl.DataFrame,
    capture: dict[str, Any],
    week: int,
    models: tuple[str, str],
) -> dict[str, Any]:
    """The descriptive league evaluation of one week (amendment 1, leagueCapture.evaluation):
    roster-only starts; streaming from every unowned unit, from those observed free agents (even
    when there are none), and with those on waivers; teams without a decision listed."""
    dst = labelled.filter((pl.col("position") == obs.DST) & (pl.col("week") == week))
    forecasts = {
        m: dict(zip(dst.get_column("defense"), dst.get_column(m), strict=True)) for m in models
    }
    actual = valid.filter((pl.col("position") == obs.DST) & (pl.col("week") == week))
    points = dict(zip(actual.get_column("defense"), actual.get_column("points"), strict=True))
    playing = set(capture.get("playingThisWeek", [])) & set(forecasts[models[0]])
    teams = capture.get("teams") or sorted(capture["rosters"])
    holdings = {t: capture["rosters"].get(t, []) for t in teams}
    availability = capture.get("availability", {})
    observed = capture.get("format") == CAPTURE_FORMAT or str(
        capture.get("availabilityBasis", "")
    ).startswith("SUPPLEMENTAL")
    out: dict[str, Any] = {"source": capture.get("source"), "observedAvailability": observed}
    for name, (kind, states) in LEAGUE_KINDS.items():
        if "*" in states:
            pool = list(capture["freeAgents"])
        elif not states:
            pool = []
        elif not observed:
            out[name] = {"skipped": "no observed availability for this week"}
            continue
        else:
            pool = sorted(u for u, st in availability.items() if st in states)
        rows = league.decide(week, holdings, pool, playing, forecasts, points, kind)
        a, b = models
        differ = [r for r in rows if r[f"pick_{a}"] != r[f"pick_{b}"]]
        both = [r for r in differ if r[f"points_{a}"] is not None and r[f"points_{b}"] is not None]
        gain = [float(r[f"points_{b}"]) - float(r[f"points_{a}"]) for r in both]
        out[name] = {
            "decisions": len(rows),
            "poolSize": len(pool),
            "differ": len(differ),
            "withLabels": len(both),
            "pointsB06MinusB00": sum(gain),
            "b06Better": (sum(g > 0 for g in gain) + 0.5 * sum(g == 0 for g in gain)) / len(gain)
            if gain
            else None,
            "teamsWithoutDecision": league.without_decision(holdings, pool, playing, kind),
            "decisionRows": rows,
        }
    return out


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
    archived: dict[int, pl.DataFrame] = {}
    retrospective: dict[int, pl.DataFrame] = {}
    leagues: dict[int, dict[str, Any]] = {}
    weeks: list[int] = args.weeks or config["weeks"]
    publications = read_ledger(root / "publications.jsonl")
    if shadow.verify_ledger(publications):
        raise SystemExit(
            "publications log is broken: " + "; ".join(shadow.verify_ledger(publications))
        )
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
    now = now_utc()
    archive_states: dict[int, dict[str, Any]] = {}
    label_states: dict[int, dict[str, Any]] = {}
    for week in weeks:
        found = entries_for(lines, week)
        matches = {
            str(e["folder"]): files_match(root / e["folder"], e["files"])
            for e in found
            if e["classification"] in ("PROSPECTIVE", "RETROSPECTIVE")
        }
        state = gate.archive_state(
            gate.WeekArchive(
                week=week,
                cutoff=cutoff_of(label_schedule, season, week),
                entries=found,
                files_match=matches,
                publications=publications,
            ),
            now,
        )
        archive_states[week] = state
        labelled_week = None
        if state["status"] == gate.PROSPECTIVE:
            e = next(x for x in found if x["classification"] == "PROSPECTIVE")
            folder = root / e["folder"]
            archived[week] = pl.read_parquet(folder / "forecasts.parquet")
            leagues[week] = league_for_evaluation(root, e, folder)
            labelled_week = shadow.attach_labels(archived[week], labels)
        label_states[week] = gate.label_state(
            week, label_schedule, labelled_week, now, NO_RESULT_GRACE
        )
        for e in found:
            if e["classification"] == "RETROSPECTIVE" and matches.get(str(e["folder"])):
                retrospective[week] = pl.read_parquet(root / e["folder"] / "forecasts.parquet")
    window = gate.window_state(weeks, config["weeks"], archive_states, label_states)
    status = {str(w): archive_states[w]["status"] for w in weeks}
    complete = window["confirmationAllowed"]
    result: dict[str, Any] = {
        "weeks": status,
        "archiveStates": {str(w): v for w, v in archive_states.items()},
        "labelStates": {str(w): v for w, v in label_states.items()},
        "window": window,
        "predeclaredWindow": weeks == config["weeks"],
        "windowComplete": complete,
        "amendment": {
            "path": "config/dvp/prospective-amendment-1.json",
            "sha256": sha256(AMENDMENT),
        },
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
            else f"{window['status']}: no confirmation label (config/dvp/prospective-amendment-1.json)",
        )
    if retrospective:
        result["retrospectiveOnly"] = evaluate_frame(
            fz,
            pl.concat(list(retrospective.values()), how="vertical_relaxed"),
            labels,
            descriptive="RETROSPECTIVE: made after the cutoff; never a confirmation",
        )
    receipt = {
        "format": FORMAT + "-evaluation-v2",
        "generatedAt": now_utc().isoformat(),
        "code": code_version(),
        "season": season,
        "frozen": fz.verification,
        "labels": label_lineage,
        **result,
        "forbidden_vendor_projection_dependencies": 0,
    }
    predeclared = weeks == config["weeks"]
    name = "evaluation.json" if predeclared else f"evaluation-weeks-{min(weeks)}-{max(weeks)}.json"
    out = Path(args.receipts) / str(season) / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n")
    shutil.rmtree(work, ignore_errors=True)
    print(json.dumps({"weeks": status, "window": window["status"], "windowComplete": complete}))


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
                    if (exported / name).exists() and sha256(exported / name) != e["files"][name]:
                        problems.append(f"export {e['folder']}/{name} differs from the archive")
    # The other append-only logs: hash chains, and each capture or supplement file's bytes.
    for log in ("captures.jsonl", "supplements.jsonl", "publications.jsonl"):
        records = read_ledger(root / log)
        problems += [f"{log}: {p}" for p in shadow.verify_ledger(records)]
        for r in records:
            if "file" in r and sha256(root / r["file"]) != r["sha256"]:
                problems.append(f"{r['file']} does not match {log}")
    prospective = {e["entrySha256"]: e for e in lines if e["classification"] == "PROSPECTIVE"}
    published = {
        p["ledgerEntrySha256"]
        for p in read_ledger(root / "publications.jsonl")
        if p.get("verified") and p.get("beforeCutoff")
    }
    unpublished = sorted(e["week"] for h, e in prospective.items() if h not in published)
    print(
        json.dumps(
            {"entries": len(lines), "problems": problems, "withoutPreCutoffCommitment": unpublished}
        )
    )
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
    commands.add_parser("publish", help="publish and verify pending external commitments")
    c = commands.add_parser("record-prior", help="record a verified earlier external publication")
    c.add_argument("--week", type=int, required=True)
    c.add_argument("--commit", required=True)
    c.add_argument("--ref", required=True, help="the branch GitHub recorded the push to")
    c.add_argument("--path", required=True, help="the folder holding the week's files")
    c.add_argument("--slug", default="chroniicallydiistracted/arbit-fantasy-football")
    u = commands.add_parser("supplement", help="observed availability from a week's snapshot")
    u.add_argument("--week", type=int, required=True)
    args = parser.parse_args()
    args.main = args.main.resolve()
    {
        "forecast": forecast,
        "reconstruct": reconstruct,
        "sweep": sweep,
        "rehearse": rehearse,
        "evaluate": evaluate,
        "verify": verify,
        "publish": publish,
        "record-prior": record_prior,
        "supplement": supplement,
    }[args.command](args)


if __name__ == "__main__":
    main()
