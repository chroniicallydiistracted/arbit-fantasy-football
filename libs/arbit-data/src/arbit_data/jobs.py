"""At-least-once durable work with expiring, fenced leases."""

import hashlib
import json
import re
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from arbit_core.identity import require_aware
from sqlalchemy import Connection, and_, or_, select, true, update
from sqlalchemy.dialects.postgresql import insert

from arbit_data.db import UnitOfWork
from arbit_data.schema import job


class LeaseLostError(ValueError):
    pass


class IdempotencyConflictError(ValueError):
    pass


@dataclass(frozen=True)
class JobRecord:
    id: UUID
    status: str
    attempts: int
    result_ref: str | None
    error_code: str | None


@dataclass(frozen=True)
class LeasedJob:
    id: UUID
    lease_token: UUID
    expires_at: datetime
    attempts: int
    job_type: str = ""
    input_ref: str = ""


def require_lease(connection: Connection, job_id: UUID, token: UUID, now: datetime) -> None:
    require_aware(now)
    row = connection.execute(
        select(job.c.id)
        .where(
            job.c.id == job_id,
            job.c.status == "running",
            job.c.lease_token == token,
            job.c.lease_until > now,
        )
        .with_for_update()
    ).first()
    if row is None:
        raise LeaseLostError("job lease is expired, replaced or no longer running")


class JobQueue:
    def __init__(self, unit_of_work: UnitOfWork, lease_seconds: int = 60, max_attempts: int = 5):
        if lease_seconds < 1 or max_attempts < 1:
            raise ValueError("lease duration and max attempts must be positive")
        self.uow = unit_of_work
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    def enqueue(
        self, job_type: str, input_ref: str, idempotency_key: str, not_before: datetime
    ) -> JobRecord:
        with self.uow.engine.begin() as connection:
            return self.enqueue_in_transaction(
                connection, job_type, input_ref, idempotency_key, not_before
            )

    def enqueue_in_transaction(
        self,
        connection: Connection,
        job_type: str,
        input_ref: str,
        idempotency_key: str,
        not_before: datetime,
    ) -> JobRecord:
        require_aware(not_before)
        if not job_type or not input_ref or not idempotency_key:
            raise ValueError("job type, input reference and idempotency key are required")
        request_hash = hashlib.sha256(
            json.dumps([job_type, input_ref], separators=(",", ":")).encode()
        ).hexdigest()
        connection.execute(
            insert(job)
            .values(
                id=uuid4(),
                job_type=job_type,
                input_ref=input_ref,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                status="queued",
                attempts=0,
                max_attempts=self.max_attempts,
                ready_at=not_before,
            )
            .on_conflict_do_nothing(index_elements=[job.c.idempotency_key])
        )
        row = (
            connection.execute(select(job).where(job.c.idempotency_key == idempotency_key))
            .mappings()
            .one()
        )
        if row["request_hash"] != request_hash:
            raise IdempotencyConflictError("idempotency key reused with different job input")
        return JobRecord(
            row["id"], row["status"], row["attempts"], row["result_ref"], row["error_code"]
        )

    def get_job(self, job_id: UUID) -> JobRecord:
        with self.uow.engine.connect() as connection:
            row = connection.execute(select(job).where(job.c.id == job_id)).mappings().one()
            return JobRecord(
                row["id"], row["status"], row["attempts"], row["result_ref"], row["error_code"]
            )

    def claim_job(
        self,
        worker_id: str,
        now: datetime,
        *,
        job_type: str | None = None,
        input_prefix: str | None = None,
    ) -> LeasedJob | None:
        require_aware(now)
        if not worker_id:
            raise ValueError("worker identity is required")
        with self.uow.engine.begin() as connection:
            # Maintenance must obey the same nonblocking claim semantics as useful work.
            exhausted = (
                select(job.c.id)
                .where(
                    job.c.status == "running",
                    job.c.lease_until <= now,
                    job.c.attempts >= job.c.max_attempts,
                    job.c.job_type == job_type if job_type else true(),
                    job.c.input_ref.startswith(input_prefix) if input_prefix else true(),
                )
                .order_by(job.c.lease_until, job.c.id)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
            connection.execute(
                update(job)
                .where(job.c.id.in_(exhausted))
                .values(
                    status="failed",
                    lease_token=None,
                    lease_until=None,
                    error_code="LEASE_EXHAUSTED",
                )
            )
            row = (
                connection.execute(
                    select(job)
                    .where(
                        job.c.attempts < job.c.max_attempts,
                        job.c.job_type == job_type if job_type else true(),
                        job.c.input_ref.startswith(input_prefix) if input_prefix else true(),
                        or_(
                            and_(job.c.status == "queued", job.c.ready_at <= now),
                            and_(job.c.status == "running", job.c.lease_until <= now),
                        ),
                    )
                    .order_by(job.c.ready_at, job.c.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            token, expires = uuid4(), now + timedelta(seconds=self.lease_seconds)
            attempts = int(row["attempts"]) + 1
            connection.execute(
                update(job)
                .where(job.c.id == row["id"])
                .values(
                    status="running",
                    attempts=attempts,
                    lease_token=token,
                    lease_until=expires,
                    worker_id=worker_id,
                )
            )
            return LeasedJob(row["id"], token, expires, attempts, row["job_type"], row["input_ref"])

    def heartbeat(self, job_id: UUID, lease_token: UUID, now: datetime) -> datetime:
        with self.uow.engine.begin() as connection:
            require_lease(connection, job_id, lease_token, now)
            expires = now + timedelta(seconds=self.lease_seconds)
            connection.execute(update(job).where(job.c.id == job_id).values(lease_until=expires))
            return expires

    def complete_job(
        self, job_id: UUID, lease_token: UUID, result_ref: str, now: datetime
    ) -> JobRecord:
        if not result_ref:
            raise ValueError("result reference is required")
        with self.uow.engine.begin() as connection:
            require_lease(connection, job_id, lease_token, now)
            connection.execute(
                update(job)
                .where(job.c.id == job_id)
                .values(
                    status="succeeded",
                    result_ref=result_ref,
                    error_code=None,
                    lease_token=None,
                    lease_until=None,
                )
            )
        return self.get_job(job_id)

    def fail_job(
        self, job_id: UUID, lease_token: UUID, error_code: str, now: datetime
    ) -> JobRecord:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", error_code):
            raise ValueError("persist a safe error code, never exception text")
        with self.uow.engine.begin() as connection:
            require_lease(connection, job_id, lease_token, now)
            row = connection.execute(select(job).where(job.c.id == job_id)).mappings().one()
            exhausted = row["attempts"] >= row["max_attempts"]
            delay = min(900, 5 * 2 ** (row["attempts"] - 1))
            connection.execute(
                update(job)
                .where(job.c.id == job_id)
                .values(
                    status="failed" if exhausted else "queued",
                    ready_at=now + timedelta(seconds=delay),
                    error_code=error_code,
                    lease_token=None,
                    lease_until=None,
                )
            )
        return self.get_job(job_id)


@contextmanager
def maintain_lease(
    queue: JobQueue, lease: LeasedJob, *, clock: Callable[[], datetime], interval: float = 10
) -> Iterator[None]:
    stop = threading.Event()
    errors: list[Exception] = []

    def beat() -> None:
        while not stop.wait(interval):
            try:
                queue.heartbeat(lease.id, lease.lease_token, clock())
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
    queue.heartbeat(lease.id, lease.lease_token, clock())
