"""The transactional outbox as a replayable event log for member streams.

Events carry a safe summary only: identifiers and counts, never private data. Consumers treat
an event as "this changed, read it again" and are at-least-once.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, delete, func, insert, select

from arbit_data.db import UnitOfWork
from arbit_data.schema import outbox_event

RETENTION_HOURS = 24
MAX_REPLAY = 500


@dataclass(frozen=True)
class Event:
    sequence: int
    event_type: str
    payload: dict[str, Any]


def emit(connection: Connection, event_type: str, payload: dict[str, Any]) -> None:
    connection.execute(
        insert(outbox_event).values(event_type=event_type, entity_id=uuid4(), payload=payload)
    )


def read_after(uow: UnitOfWork, sequence: int, *, limit: int = MAX_REPLAY) -> list[Event]:
    with uow.engine.connect() as c:
        rows = c.execute(
            select(outbox_event.c.sequence, outbox_event.c.event_type, outbox_event.c.payload)
            .where(outbox_event.c.sequence > sequence)
            .order_by(outbox_event.c.sequence)
            .limit(limit)
        ).all()
    return [Event(int(r.sequence), str(r.event_type), dict(r.payload)) for r in rows]


def latest_sequence(uow: UnitOfWork) -> int:
    with uow.engine.connect() as c:
        return int(c.scalar(select(func.coalesce(func.max(outbox_event.c.sequence), 0))) or 0)


def replay_available(uow: UnitOfWork, cursor: int) -> bool:
    """A cursor can replay only if nothing after it has been trimmed and it isn't in the future."""
    with uow.engine.connect() as c:
        row = c.execute(
            select(
                func.min(outbox_event.c.sequence).label("oldest"),
                func.max(outbox_event.c.sequence).label("newest"),
            )
        ).one()
    if row.newest is None:
        return cursor == 0
    return bool(row.oldest <= cursor + 1 and cursor <= row.newest)


def trim_before(uow: UnitOfWork, cutoff: datetime) -> int:
    """Remove old events, always keeping the newest so a cursor can never rewind or reuse IDs."""
    with uow.engine.begin() as c:
        newest = c.scalar(select(func.max(outbox_event.c.sequence)))
        if newest is None:
            return 0
        result = c.execute(
            delete(outbox_event).where(
                outbox_event.c.occurred_at < cutoff, outbox_event.c.sequence < newest
            )
        )
        return int(result.rowcount)
