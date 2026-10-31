"""A shared PostgreSQL request gate for automatic ESPN reads across local workers."""

import math
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from time import monotonic
from time import sleep as real_sleep
from typing import Literal

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.espn.endpoints import Endpoint, EndpointOptions
from arbit_data.espn.transport import EndpointFetchResult, EspnError, EspnTransport
from arbit_data.schema import provider_budget

TRANSIENT = {
    "NETWORK_ERROR",
    "UNAVAILABLE",
    "RATE_LIMITED",
    "SOURCE_COOLDOWN",
    "PROVIDER_BUSY",
    "SOURCE_CHANGED",
    "SCHEMA_DRIFT",
    "INVALID_RESPONSE",
    "INVALID_JSON",
    "INCONSISTENT_DATA",
    "PAGE_LIMIT",
}


def after(now: datetime, seconds: int | float) -> datetime:
    # Arbitrarily long provider Retry-After values fail closed instead of overflowing a timestamp.
    maximum = datetime.max.replace(tzinfo=UTC)
    if seconds >= (maximum - now).total_seconds():
        return maximum
    return now + timedelta(seconds=max(0, seconds))


class DatabaseGate:
    def __init__(
        self,
        uow: UnitOfWork,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], None] = real_sleep,
        provider: Literal["espn", "nflverse"] = "espn",
    ):
        self.uow, self.clock, self.sleep = uow, clock, sleep
        self.provider = provider
        self.lock_key = {"espn": -2, "nflverse": -3}[provider]
        self.spacing = {"espn": 2.0, "nflverse": 0.1}[provider]

    @contextmanager
    def request(self) -> Iterator[None]:
        # A session advisory lock spans the bounded HTTP request without an open SQL transaction.
        # Dedicated autocommit connection is held until unlock; never return a locked session to pool.
        with self.uow.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            acquired = False
            try:
                deadline = monotonic() + 30
                while not acquired:
                    acquired = bool(
                        c.scalar(select(func.pg_try_advisory_lock(1729878439, self.lock_key)))
                    )
                    if not acquired:
                        if monotonic() >= deadline:
                            raise EspnError("PROVIDER_BUSY", retry_after_seconds=5)
                        self.sleep(0.1)
                now = self.clock()
                c.execute(
                    insert(provider_budget)
                    .values(
                        provider=self.provider, next_allowed_at=now, blocked_until=now, failures=0
                    )
                    .on_conflict_do_nothing(index_elements=[provider_budget.c.provider])
                )
                row = (
                    c.execute(
                        select(provider_budget).where(provider_budget.c.provider == self.provider)
                    )
                    .mappings()
                    .one()
                )
                if row["blocked_until"] > now:
                    raise EspnError(
                        "SOURCE_COOLDOWN",
                        retry_after_seconds=math.ceil((row["blocked_until"] - now).total_seconds()),
                    )
                self.sleep(max(0, (row["next_allowed_at"] - now).total_seconds()))
                c.execute(
                    update(provider_budget)
                    .where(provider_budget.c.provider == self.provider)
                    .values(next_allowed_at=after(self.clock(), self.spacing))
                )
                try:
                    yield
                except SourceError as error:
                    failures = row["failures"] + 1 if error.code in TRANSIENT else 0
                    delay = max(
                        error.retry_after_seconds or 0,
                        60 if error.code == "RATE_LIMITED" or failures >= 3 else 0,
                    )
                    c.execute(
                        update(provider_budget)
                        .where(provider_budget.c.provider == self.provider)
                        .values(failures=failures, blocked_until=after(self.clock(), delay))
                    )
                    raise
                else:
                    c.execute(
                        update(provider_budget)
                        .where(provider_budget.c.provider == self.provider)
                        .values(failures=0)
                    )
            finally:
                if acquired:
                    try:
                        if not c.scalar(select(func.pg_advisory_unlock(1729878439, self.lock_key))):
                            c.invalidate()
                    except Exception:
                        c.invalidate()
                        raise


class GatedEspnTransport(EspnTransport):
    def __init__(self, gate: DatabaseGate):
        super().__init__()
        self.gate = gate

    def fetch(self, endpoint: Endpoint, options: EndpointOptions) -> EndpointFetchResult:
        with self.gate.request():
            return super().fetch(endpoint, options)
