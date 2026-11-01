"""The supervised sync process: one lane per source family so a slow source can't delay a score.

Runs until SIGTERM. A failure in one lane is recorded and retried; it never stops the others.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from arbit_core.config import load_league_config
from arbit_data import events, freshness
from arbit_data.archives import CaptureArchive
from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.espn.endpoints import Endpoint, EndpointOptions
from arbit_data.espn.gate import DatabaseGate, GatedEspnTransport
from arbit_data.live import cadence, store
from arbit_data.live.feed import LiveFeed
from arbit_data.public_sources.transport import PublicTransport
from arbit_data.schema import dataset_manifest, sync_state
from arbit_data.sync import EspnSyncSource, SyncService, schedule_sync
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError

from arbit_worker.sync_commands import local_database_url

LANES = ("league", "live", "statistics")
Clock = Callable[[], datetime]


def log(lane: str, **fields: Any) -> None:
    """Safe structured line: codes, counts and modes. Never bodies, names or credentials."""
    record = {"at": datetime.now(UTC).isoformat(), "lane": lane, **fields}
    print(json.dumps(record, sort_keys=True, default=str), flush=True)


def current_mode(uow: UnitOfWork, season: int, now: datetime) -> cadence.Mode:
    return cadence.live_mode(store.slate(store.game_timings(uow, season)), now)


class LeagueLane:
    """FFA rosters, locks, matchups and availability, plus the NFL team directory and schedule."""

    name = "league"

    def __init__(
        self,
        uow: UnitOfWork,
        season: int,
        *,
        service: SyncService | None = None,
        directory_fetch: Callable[[], Any] | None = None,
        clock: Clock = lambda: datetime.now(UTC),
    ):
        self.uow, self.season, self.clock = uow, season, clock
        self.service = service or SyncService(
            uow,
            CaptureArchive(Path(os.environ.get("ARBIT_STORAGE_PATH", "data/source-archives"))),
            EspnSyncSource(uow),
        )
        self.directory_fetch = directory_fetch or self._fetch_directory
        self.next_trim: datetime | None = None
        self.directory_retry: datetime | None = None

    def _fetch_directory(self) -> Any:
        transport = GatedEspnTransport(DatabaseGate(self.uow))
        return transport.fetch(Endpoint.PRO_SCHEDULES, EndpointOptions(season=self.season))

    def _sync_league(self, now: datetime) -> None:
        mode = current_mode(self.uow, self.season, now)
        seconds = cadence.league_seconds(mode)
        stale_after = cadence.league_stale_seconds(mode)
        self.service.interval_seconds = seconds
        with self.uow.engine.connect() as c:
            state = c.execute(select(sync_state).where(sync_state.c.season == self.season)).first()
        if state is not None and state.paused:
            # Access or rule failures need a person. Polling harder would not fix them.
            return
        retrying = state is not None and state.consecutive_failures > 0
        due = True
        if state is not None:
            if retrying:
                due = now >= state.next_due_at
            elif state.last_attempt_at is not None:
                due = now >= state.last_attempt_at + timedelta(seconds=seconds)
        if not due:
            return
        schedule_sync(self.uow, self.season, now=now, force=not retrying)
        result = self.service.run_one()
        if result is None:
            return
        status = result.get("status")
        if status == "succeeded":
            freshness.record_success(
                self.uow,
                freshness.LEAGUE,
                now=self.clock(),
                cadence_seconds=seconds,
                stale_after_seconds=stale_after,
                changed=bool(result.get("changed")),
            )
            if result.get("changed"):
                log(self.name, event="league_changed", mode=mode)
        elif status != "lease_lost":
            code = str(result.get("error_code") or "SYNC_FAILED")
            freshness.record_failure(
                self.uow,
                freshness.LEAGUE,
                code,
                now=self.clock(),
                cadence_seconds=seconds,
                stale_after_seconds=stale_after,
            )
            log(self.name, event="league_failed", code=code, status=status)

    def _sync_directory(self, now: datetime) -> None:
        last = freshness.last_success_of(self.uow, freshness.DIRECTORY)
        if last is not None and now - last < timedelta(seconds=cadence.DIRECTORY_SECONDS):
            return
        if self.directory_retry is not None and now < self.directory_retry:
            return
        try:
            fetched = self.directory_fetch()
            directory = store.normalize_directory(fetched.payload, self.season)
            changed = store.publish_directory(
                self.uow, directory, self.season, self.clock(), fetched.receipt.sha256
            )
        except (SourceError, ValueError, OSError) as error:
            code = error.code if isinstance(error, SourceError) else "DIRECTORY_INVALID"
            freshness.record_failure(
                self.uow,
                freshness.DIRECTORY,
                code,
                now=self.clock(),
                cadence_seconds=cadence.DIRECTORY_SECONDS,
                stale_after_seconds=cadence.DIRECTORY_STALE_SECONDS,
            )
            failures = freshness.failures_of(self.uow, freshness.DIRECTORY)
            self.directory_retry = self.clock() + timedelta(
                seconds=cadence.backoff_seconds(300, failures, ceiling_seconds=3600)
            )
            log(self.name, event="directory_failed", code=code)
            return
        self.directory_retry = None
        freshness.record_success(
            self.uow,
            freshness.DIRECTORY,
            now=self.clock(),
            cadence_seconds=cadence.DIRECTORY_SECONDS,
            stale_after_seconds=cadence.DIRECTORY_STALE_SECONDS,
            changed=changed,
        )
        log(self.name, event="directory_read", changed=changed, teams=len(directory.teams))

    def _trim(self, now: datetime) -> None:
        if self.next_trim is not None and now < self.next_trim:
            return
        self.next_trim = now + timedelta(hours=1)
        events.trim_before(self.uow, now - timedelta(hours=events.RETENTION_HOURS))

    def step(self) -> float:
        now = self.clock()
        self._sync_league(now)
        self._sync_directory(self.clock())
        self._trim(self.clock())
        return 5.0


class LiveLane:
    """NFL scoreboard and active games, on the cadence the observed slate calls for."""

    name = "live"

    def __init__(self, uow: UnitOfWork, season: int, *, feed: LiveFeed | None = None):
        self.feed = feed or LiveFeed(uow, PublicTransport(), season)
        self.mode: cadence.Mode | None = None

    def step(self) -> float:
        result = self.feed.step()
        if result.mode != self.mode:
            log(self.name, event="mode", mode=result.mode)
            self.mode = result.mode
        return result.wait_seconds


class StatisticsLane:
    """Daily nflverse catalog check and import of changed files, as a child process.

    An import can run for many minutes and uses a lot of memory, so it stays out of this process.
    Unchanged files are reused; changed ones publish new immutable manifests.
    """

    name = "statistics"

    def __init__(
        self,
        uow: UnitOfWork,
        *,
        run: Callable[[list[str]], tuple[int, str]] | None = None,
        clock: Clock = lambda: datetime.now(UTC),
    ):
        self.uow, self.clock = uow, clock
        self.run = run or self._run
        self.retry: datetime | None = None

    @staticmethod
    def _run(arguments: list[str]) -> tuple[int, str]:
        program = shutil.which("arbit-worker")
        command = [program] if program else [sys.executable, "-m", "arbit_worker.main"]
        done = subprocess.run(  # noqa: S603
            [*command, *arguments], capture_output=True, text=True, timeout=4 * 3600, check=False
        )
        return done.returncode, done.stdout

    def _last_success(self) -> datetime | None:
        last = freshness.last_success_of(self.uow, freshness.STATISTICS)
        if last is not None:
            return last
        # Before the first daemon run, the newest stored manifest is the true age.
        with self.uow.engine.connect() as c:
            value: datetime | None = c.scalar(select(func.max(dataset_manifest.c.observed_at)))
            return value

    def step(self) -> float:
        now = self.clock()
        last = self._last_success()
        due = last is None or now - last >= timedelta(seconds=cadence.STATISTICS_SECONDS)
        if not due or (self.retry is not None and now < self.retry):
            return 300.0
        code = self._import()
        finished = self.clock()
        if code is None:
            self.retry = None
            freshness.record_success(
                self.uow,
                freshness.STATISTICS,
                now=finished,
                cadence_seconds=cadence.STATISTICS_SECONDS,
                stale_after_seconds=cadence.STATISTICS_STALE_SECONDS,
                changed=True,
            )
            log(self.name, event="statistics_imported")
        else:
            freshness.record_failure(
                self.uow,
                freshness.STATISTICS,
                code,
                now=finished,
                cadence_seconds=cadence.STATISTICS_SECONDS,
                stale_after_seconds=cadence.STATISTICS_STALE_SECONDS,
            )
            self.retry = finished + timedelta(hours=2)
            log(self.name, event="statistics_failed", code=code)
        return 300.0

    def _import(self) -> str | None:
        try:
            status, output = self.run(["nflverse-catalog", "--live"])
            if status != 0:
                return "CATALOG_FAILED"
            digest = json.loads(output)["catalog_hash"]
            status, _ = self.run(["nflverse-import", "--catalog", digest, "--workers", "2"])
            return None if status == 0 else "IMPORT_FAILED"
        except (ValueError, KeyError, OSError, subprocess.SubprocessError):
            return "IMPORT_FAILED"


def run_lane(lane: Any, stop: threading.Event) -> None:
    """Keep a lane alive through anything short of a stop signal."""
    log(lane.name, event="started")
    while not stop.is_set():
        try:
            wait = lane.step()
        except SQLAlchemyError:
            log(lane.name, event="error", code="DATABASE_UNAVAILABLE")
            wait = 10.0
        except Exception as error:  # noqa: BLE001
            # Type name only: messages can carry paths or provider text.
            log(lane.name, event="error", code="LANE_ERROR", kind=type(error).__name__)
            wait = 15.0
        stop.wait(wait)
    log(lane.name, event="stopped")


def execute(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    try:
        url = local_database_url()
        config = load_league_config(Path("config/league.json"))
    except (ValueError, OSError):
        parser.exit(2, '{"error":"LOCAL_DATABASE_REQUIRED"}\n')
    selected = [name.strip() for name in arguments.lanes.split(",") if name.strip()]
    if not selected or set(selected) - set(LANES):
        parser.exit(2, '{"error":"UNKNOWN_LANE"}\n')
    engine = create_engine(
        url,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
        pool_pre_ping=True,
        pool_size=8,
    )
    uow = UnitOfWork(engine)
    factories: dict[str, Callable[[], Any]] = {
        "league": lambda: LeagueLane(uow, config.season),
        "live": lambda: LiveLane(uow, config.season),
        "statistics": lambda: StatisticsLane(uow),
    }
    stop = threading.Event()
    previous = {
        sig: signal.signal(sig, lambda *_: stop.set()) for sig in (signal.SIGINT, signal.SIGTERM)
    }
    threads = [
        threading.Thread(target=run_lane, args=(factories[name](), stop), name=name, daemon=True)
        for name in selected
    ]
    try:
        for thread in threads:
            thread.start()
        while not stop.is_set():
            stop.wait(1.0)
        for thread in threads:
            thread.join(timeout=30)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        engine.dispose()


def add_command(subcommands: Any) -> None:
    run = subcommands.add_parser(
        "run", help="Keep every changing source current until stopped (supervised worker)"
    )
    run.add_argument(
        "--lanes", default=",".join(LANES), help="Comma-separated lanes: league,live,statistics"
    )
