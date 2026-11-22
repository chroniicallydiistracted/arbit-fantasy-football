"""ESPN's fantasy injury status as of a moment (OWN-064): the Model's game-day availability.

The league lane stores a new ESPN league document whenever ESPN's data changes
(`league_document.published_at`), and records every read, changed or not (`source_capture`).
A player's status at a moment is the one in the latest document published by then. It is
**current** only if Arbit read ESPN shortly before that moment. Otherwise the status is stale:
the PC slept or the worker stopped (R-066), and ESPN may have changed it unseen. Then a game-day
decision is unknown, never assumed active. The stored document holds status only, no projection.

In week 9 of 2026, ESPN switched 39 of 41 inactive players to `OUT` 62–86 minutes before
kickoff (SRC-33).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from arbit_core.identity import require_aware
from sqlalchemy import func, select

from arbit_data.db import UnitOfWork
from arbit_data.espn.normalize import injury_designation
from arbit_data.league import InjuryDesignation
from arbit_data.schema import league_document, league_snapshot, source_capture

# The league lane reads every 1 to 5 minutes; three missed idle reads is no longer current.
CURRENT_WITHIN = timedelta(minutes=15)
READ_STATUSES = ("published", "unchanged")


@dataclass(frozen=True)
class PlayerStatus:
    entity_id: str
    code: str | None  # ESPN's injury_status, such as OUT or QUESTIONABLE
    designation: InjuryDesignation | None  # plain terms; None is no designation


@dataclass(frozen=True)
class StatusAsOf:
    at: datetime
    document_published_at: datetime | None
    last_read_at: datetime | None
    current: bool
    players: Mapping[str, PlayerStatus]


def status_from(
    at: datetime,
    document: tuple[datetime, Sequence[Mapping[str, Any]]] | None,
    last_read_at: datetime | None,
) -> StatusAsOf:
    """Every player's status from the latest document at or before `at`, and whether it is
    current: Arbit read ESPN within `CURRENT_WITHIN` before `at`."""
    require_aware(at)
    if document is not None and document[0] > at or last_read_at is not None and last_read_at > at:
        raise ValueError("FUTURE_EVIDENCE")
    players: dict[str, PlayerStatus] = {}
    if document is not None:
        for player in document[1]:
            code = player.get("injury_status")
            code = code if isinstance(code, str) and code else None
            players[str(player["id"])] = PlayerStatus(
                str(player["id"]), code, injury_designation(code, bool(player.get("injured")))
            )
    current = (
        document is not None and last_read_at is not None and at - last_read_at <= CURRENT_WITHIN
    )
    return StatusAsOf(
        at=at,
        document_published_at=document[0] if document else None,
        last_read_at=last_read_at,
        current=current,
        players=players,
    )


def status_as_of(uow: UnitOfWork, season: int, at: datetime) -> StatusAsOf:
    """ESPN's status for every pool player as Arbit knew it at `at`. Read-only."""
    require_aware(at)
    with uow.engine.connect() as c:
        row = c.execute(
            select(league_document.c.published_at, league_document.c.payload["players"])
            .join(league_snapshot, league_snapshot.c.id == league_document.c.snapshot_id)
            .where(league_snapshot.c.season == season, league_document.c.published_at <= at)
            .order_by(league_document.c.published_at.desc())
            .limit(1)
        ).first()
        last_read = c.scalar(
            select(func.max(source_capture.c.finished_at)).where(
                source_capture.c.season == season,
                source_capture.c.finished_at <= at,
                source_capture.c.status.in_(READ_STATUSES),
            )
        )
    document = (row[0], list(row[1] or [])) if row is not None else None
    return status_from(at, document, last_read)
