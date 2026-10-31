"""Durable fixed-league scheduling, recovery and offline replay. No in-memory work queue."""

import re
import secrets
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from arbit_data.archives import CaptureArchive, CapturedInput
from arbit_data.db import UnitOfWork
from arbit_data.espn.client import EspnClient
from arbit_data.espn.contracts import EspnAcquisition
from arbit_data.espn.gate import TRANSIENT, DatabaseGate, GatedEspnTransport, after
from arbit_data.espn.normalize import scoring_context
from arbit_data.espn.reader import EspnReader
from arbit_data.espn.scoring_audit import audit_scoring
from arbit_data.espn.transport import EspnError
from arbit_data.jobs import JobQueue, LeasedJob, LeaseLostError, require_lease
from arbit_data.league_store import (
    Publication,
    publish_capture,
    register_capture,
    verification_exists,
)
from arbit_data.schema import job, source_capture, sync_state


class SyncSource(Protocol):
    def acquire(self, season: int) -> EspnAcquisition: ...
    def audit(self, season: int) -> dict[str, Any]: ...


class EspnSyncSource:
    def __init__(self, uow: UnitOfWork):
        self.transport = GatedEspnTransport(DatabaseGate(uow))

    def acquire(self, season: int) -> EspnAcquisition:
        return EspnReader(self.transport).fetch_league_snapshot(season)

    def audit(self, season: int) -> dict[str, Any]:
        return audit_scoring(EspnClient(self.transport), season)


def schedule_sync(
    uow: UnitOfWork, season: int, *, now: datetime | None = None, force: bool = False
) -> UUID | None:
    if type(season) is not int or not 2026 <= season <= 2100:
        raise ValueError("unsupported season")
    now = now or datetime.now(UTC)
    with uow.engine.begin() as c:
        c.execute(select(func.pg_advisory_xact_lock(1729878439, season)))
        c.execute(
            insert(sync_state)
            .values(season=season, next_due_at=now, paused=False, consecutive_failures=0)
            .on_conflict_do_nothing(index_elements=[sync_state.c.season])
        )
        active = c.scalar(
            select(job.c.id).where(
                job.c.job_type == "espn.sync",
                job.c.input_ref == str(season),
                job.c.status.in_(("queued", "running")),
            )
        )
        if active:
            return UUID(str(active))
        state = c.execute(select(sync_state).where(sync_state.c.season == season)).mappings().one()
        if not force and (state["paused"] or state["next_due_at"] > now):
            return None
        c.execute(update(sync_state).where(sync_state.c.season == season).values(paused=False))
        return (
            JobQueue(uow, max_attempts=5)
            .enqueue_in_transaction(c, "espn.sync", str(season), "espn.sync:" + str(uuid4()), now)
            .id
        )


class SyncService:
    def __init__(
        self,
        uow: UnitOfWork,
        archive: CaptureArchive,
        source: SyncSource,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        jitter: Callable[[], float] = lambda: secrets.randbelow(1000) / 1000,
        interval_seconds: int = 300,
        heartbeat_seconds: float = 10,
    ):
        if interval_seconds < 60 or heartbeat_seconds <= 0 or heartbeat_seconds >= 60:
            raise ValueError("invalid sync cadence")
        self.uow, self.archive, self.source = uow, archive, source
        self.clock, self.jitter = clock, jitter
        self.interval_seconds, self.heartbeat_seconds = interval_seconds, heartbeat_seconds
        self.queue = JobQueue(uow, lease_seconds=120, max_attempts=5)
        self.worker_id = "ffa-sync-" + uuid4().hex

    @contextmanager
    def _heartbeat(self, lease: LeasedJob) -> Iterator[None]:
        stop = threading.Event()
        errors: list[Exception] = []

        def beat() -> None:
            while not stop.wait(self.heartbeat_seconds):
                try:
                    self.queue.heartbeat(lease.id, lease.lease_token, self.clock())
                except Exception as error:
                    errors.append(error)
                    return

        thread = threading.Thread(target=beat, daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join()
        if errors:
            raise LeaseLostError("heartbeat failed; publication is fenced")
        self.queue.heartbeat(lease.id, lease.lease_token, self.clock())

    def _archive(self, captured: CapturedInput, lease: LeasedJob) -> str:
        manifest = self.archive.write(captured)
        with self.uow.engine.begin() as c:
            require_lease(c, lease.id, lease.lease_token, self.clock())
            register_capture(c, captured, manifest)
        return manifest

    def _recover_exhausted(self) -> None:
        now = self.clock()
        with self.uow.engine.begin() as c:
            rows = (
                c.execute(
                    select(job)
                    .where(
                        job.c.job_type == "espn.sync",
                        job.c.status == "running",
                        job.c.lease_until <= now,
                        job.c.attempts >= job.c.max_attempts,
                    )
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .all()
            )
            for row in rows:
                c.execute(
                    update(job)
                    .where(job.c.id == row["id"])
                    .values(
                        status="failed",
                        lease_token=None,
                        lease_until=None,
                        error_code="LEASE_EXHAUSTED",
                    )
                )
                c.execute(
                    update(sync_state)
                    .where(sync_state.c.season == int(row["input_ref"]))
                    .values(
                        error_code="LEASE_EXHAUSTED",
                        next_due_at=after(now, 900),
                        consecutive_failures=sync_state.c.consecutive_failures + 1,
                    )
                )

    def run_one(self) -> dict[str, Any] | None:
        self._recover_exhausted()
        lease = self.queue.claim_job(self.worker_id, self.clock(), job_type="espn.sync")
        if not lease:
            return None
        season = int(lease.input_ref)
        manifest: str | None = None
        try:
            with self.uow.engine.begin() as c:
                require_lease(c, lease.id, lease.lease_token, self.clock())
                c.execute(
                    update(sync_state)
                    .where(sync_state.c.season == season)
                    .values(last_attempt_at=self.clock())
                )
            with self._heartbeat(lease):
                acquisition = self.source.acquire(season)
                if acquisition.league.season_id != season:
                    raise ValueError("SCOPE_MISMATCH")
                try:
                    key, _ = scoring_context(acquisition.league)
                except ValueError:
                    manifest = self._archive(
                        CapturedInput(acquisition=acquisition, verification=None), lease
                    )
                    raise
                report = None if verification_exists(self.uow, key) else self.source.audit(season)
                captured = CapturedInput(acquisition=acquisition, verification=report)
                manifest = self._archive(captured, lease)
                if report is not None and not report.get("success"):
                    issue = report.get("issues", [{}])[0] if report.get("issues") else {}
                    raise EspnError(
                        issue.get("code", "SCORING_VERIFICATION_FAILED"),
                        status=issue.get("status"),
                        retry_after_seconds=issue.get("retryAfterSeconds"),
                    )
            result = publish_capture(
                captured,
                manifest,
                self.uow,
                lease=lease,
                interval_seconds=self.interval_seconds,
                clock=self.clock,
            )
            return {
                "status": "succeeded",
                "snapshot_id": str(result.snapshot_id),
                "changed": result.changed,
                "replayed": result.replayed,
                "manifest_hash": manifest,
            }
        except LeaseLostError:
            return {"status": "lease_lost", "error_code": "LEASE_LOST"}
        except EspnError as error:
            return self._fail(
                lease,
                season,
                error.code,
                error.code in TRANSIENT,
                error.retry_after_seconds,
                manifest,
            )
        except (ValueError, OSError) as error:
            # Persist only explicitly safe domain codes; never raw exception text, paths or identities.
            code = (
                str(error)
                if isinstance(error, ValueError)
                and re.fullmatch("[A-Z][A-Z0-9_]{0,63}", str(error))
                else "CANONICAL_VALIDATION_FAILED"
                if isinstance(error, ValueError)
                else "ARCHIVE_UNAVAILABLE"
            )
            return self._fail(
                lease,
                season,
                code,
                code in TRANSIENT or code == "ARCHIVE_UNAVAILABLE",
                None,
                manifest,
            )
        except SQLAlchemyError:
            # If DB itself is unavailable the durable lease expires for another worker to recover.
            return {"status": "database_unavailable", "error_code": "DATABASE_UNAVAILABLE"}

    def _fail(
        self,
        lease: LeasedJob,
        season: int,
        code: str,
        retryable: bool,
        retry_after: int | None,
        manifest: str | None,
    ) -> dict[str, Any]:
        now = self.clock()
        code = code if re.fullmatch("[A-Z][A-Z0-9_]{0,63}", code) else "SYNC_FAILED"
        try:
            with self.uow.engine.begin() as c:
                require_lease(c, lease.id, lease.lease_token, now)
                row = c.execute(select(job).where(job.c.id == lease.id)).mappings().one()
                retry = retryable and row["attempts"] < row["max_attempts"]
                delay = max(
                    retry_after or 0, min(900, 5 * 2 ** (row["attempts"] - 1)) + self.jitter() * 2
                )
                ready = after(now, delay)
                c.execute(
                    update(job)
                    .where(job.c.id == lease.id)
                    .values(
                        status="queued" if retry else "failed",
                        ready_at=ready,
                        error_code=code,
                        lease_token=None,
                        lease_until=None,
                    )
                )
                c.execute(
                    update(sync_state)
                    .where(sync_state.c.season == season)
                    .values(
                        paused=not retryable,
                        consecutive_failures=sync_state.c.consecutive_failures + 1,
                        error_code=code,
                        next_due_at=ready if retry else after(now, max(900, retry_after or 0)),
                    )
                )
                if manifest:
                    c.execute(
                        update(source_capture)
                        .where(
                            source_capture.c.manifest_hash == manifest,
                            source_capture.c.snapshot_id.is_(None),
                        )
                        .values(status="quarantined", error_code=code)
                    )
            return {
                "status": "retrying" if retry else "exhausted" if retryable else "paused",
                "error_code": code,
            }
        except LeaseLostError:
            return {"status": "lease_lost", "error_code": "LEASE_LOST"}
        except SQLAlchemyError:
            return {"status": "database_unavailable", "error_code": "DATABASE_UNAVAILABLE"}

    def replay(self, manifest_hash: str) -> Publication:
        with self.uow.engine.connect() as c:
            known = c.scalar(
                select(source_capture.c.manifest_hash).where(
                    source_capture.c.manifest_hash == manifest_hash
                )
            )
        if not known:
            raise ValueError("UNKNOWN_CAPTURE")
        captured = self.archive.read(manifest_hash)
        return publish_capture(
            captured, manifest_hash, self.uow, interval_seconds=self.interval_seconds
        )
