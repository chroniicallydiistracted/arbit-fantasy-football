"""Per-source freshness: when each changing source last answered, and whether that is too long ago."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import Connection, func, select
from sqlalchemy.dialects.postgresql import insert

from arbit_data.db import UnitOfWork
from arbit_data.events import emit
from arbit_data.schema import dataset_manifest, source_health, sync_state

LEAGUE = "espn.league"
SCOREBOARD = "espn.nfl.scoreboard"
PLAYS = "espn.nfl.plays"
DIRECTORY = "espn.nfl.teams"
STATISTICS = "nflverse"

# Member-facing names, in display order. Every source that changes must appear here.
SOURCES: tuple[tuple[str, str], ...] = (
    (LEAGUE, "FFA league"),
    (SCOREBOARD, "NFL scores"),
    (PLAYS, "NFL plays"),
    (DIRECTORY, "NFL teams and schedule"),
    (STATISTICS, "NFL statistics"),
)
SourceState = Literal["current", "behind", "down", "idle", "never"]
STATISTICS_STALE_SECONDS = 36 * 3600
# Errors stop reading as a blip after this many consecutive failures.
DOWN_AFTER_FAILURES = 3


@dataclass(frozen=True)
class SourceStatus:
    source: str
    label: str
    state: SourceState
    last_success_at: datetime | None
    cadence_seconds: int | None
    error_code: str | None


def classify(
    *,
    last_success_at: datetime | None,
    stale_after_seconds: int | None,
    consecutive_failures: int,
    now: datetime,
) -> SourceState:
    if consecutive_failures >= DOWN_AFTER_FAILURES:
        return "down"
    if last_success_at is None:
        return "never"
    if stale_after_seconds is None:
        return "idle"  # Not expected to be read right now, such as plays with no game on.
    age = (now - last_success_at).total_seconds()
    return "behind" if age > stale_after_seconds or age < 0 else "current"


def _write(
    c: Connection,
    source: str,
    now: datetime,
    *,
    ok: bool,
    cadence_seconds: int | None,
    stale_after_seconds: int | None,
    changed: bool,
    error_code: str | None,
) -> None:
    previous = c.execute(
        select(source_health.c.consecutive_failures, source_health.c.error_code).where(
            source_health.c.source == source
        )
    ).first()
    failures = 0 if ok else (previous.consecutive_failures if previous else 0) + 1
    values: dict[str, Any] = {
        "last_attempt_at": now,
        "cadence_seconds": cadence_seconds,
        "stale_after_seconds": stale_after_seconds,
        "consecutive_failures": failures,
        "error_code": None if ok else error_code,
    }
    if ok:
        values["last_success_at"] = now
    if ok and changed:
        values["last_change_at"] = now
    c.execute(
        insert(source_health)
        .values(source=source, **values)
        .on_conflict_do_update(index_elements=[source_health.c.source], set_=values)
    )
    # Tell clients when a source's state flips, and on each league confirmation so its age refreshes.
    flipped = previous is None or (previous.consecutive_failures > 0) != (failures > 0)
    if flipped or (ok and source == LEAGUE):
        emit(c, "source.status", {"source": source})


def record_success(
    uow: UnitOfWork,
    source: str,
    *,
    now: datetime,
    cadence_seconds: int | None,
    stale_after_seconds: int | None,
    changed: bool = False,
) -> None:
    with uow.engine.begin() as c:
        _write(
            c,
            source,
            now,
            ok=True,
            cadence_seconds=cadence_seconds,
            stale_after_seconds=stale_after_seconds,
            changed=changed,
            error_code=None,
        )


def record_failure(
    uow: UnitOfWork,
    source: str,
    code: str,
    *,
    now: datetime,
    cadence_seconds: int | None,
    stale_after_seconds: int | None,
) -> None:
    with uow.engine.begin() as c:
        _write(
            c,
            source,
            now,
            ok=False,
            cadence_seconds=cadence_seconds,
            stale_after_seconds=stale_after_seconds,
            changed=False,
            error_code=code,
        )


def failures_of(uow: UnitOfWork, source: str) -> int:
    with uow.engine.connect() as c:
        return int(
            c.scalar(
                select(source_health.c.consecutive_failures).where(source_health.c.source == source)
            )
            or 0
        )


def last_success_of(uow: UnitOfWork, source: str) -> datetime | None:
    with uow.engine.connect() as c:
        value: datetime | None = c.scalar(
            select(source_health.c.last_success_at).where(source_health.c.source == source)
        )
        return value


def read_sources(uow: UnitOfWork, season: int, now: datetime | None = None) -> list[SourceStatus]:
    now = now or datetime.now(UTC)
    with uow.engine.connect() as c:
        rows = {r.source: r for r in c.execute(select(source_health)).all()}
        league = c.execute(select(sync_state).where(sync_state.c.season == season)).first()
        imported = c.scalar(select(func.max(dataset_manifest.c.observed_at)))
    result = []
    for source, label in SOURCES:
        row = rows.get(source)
        last = row.last_success_at if row else None
        stale_after = row.stale_after_seconds if row else None
        failures = row.consecutive_failures if row else 0
        error = row.error_code if row else None
        cadence = row.cadence_seconds if row else None
        if source == LEAGUE and league is not None:
            # A manual `sync --once` is real evidence too; the sync state is authoritative.
            last = league.last_success_at
            failures = max(failures, league.consecutive_failures)
            error = error or league.error_code
            stale_after = stale_after or 900
            if league.paused:
                failures = max(failures, DOWN_AFTER_FAILURES)
        if source == STATISTICS and last is None and imported is not None:
            # A manual import is real evidence too, before the worker's first scheduled one.
            last, stale_after = imported, STATISTICS_STALE_SECONDS
        state = classify(
            last_success_at=last,
            stale_after_seconds=stale_after,
            consecutive_failures=failures,
            now=now,
        )
        result.append(SourceStatus(source, label, state, last, cadence, error))
    return result
