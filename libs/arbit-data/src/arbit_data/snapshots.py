"""Atomic complete-snapshot publication with serial ordering and outbox insertion."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from arbit_core.identity import require_aware
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from arbit_data.contracts import LeagueSnapshotCandidate
from arbit_data.db import UnitOfWork
from arbit_data.jobs import LeasedJob, require_lease
from arbit_data.schema import current_snapshot, league_snapshot, outbox_event, roster_entry


class IncompleteSnapshotError(ValueError):
    pass


class StaleSnapshotError(ValueError):
    pass


@dataclass(frozen=True)
class SnapshotRef:
    id: UUID
    content_hash: str


@dataclass(frozen=True)
class LeagueSnapshot:
    id: UUID
    candidate: LeagueSnapshotCandidate


def publish_snapshot(
    candidate: LeagueSnapshotCandidate,
    unit_of_work: UnitOfWork,
    *,
    lease: LeasedJob | None = None,
    now: datetime | None = None,
) -> SnapshotRef:
    # Revalidate even model_copy/model_construct inputs before any write.
    candidate = LeagueSnapshotCandidate.model_validate(candidate.model_dump())
    if not candidate.complete:
        raise IncompleteSnapshotError("a partial snapshot cannot become current")
    timestamp = now or datetime.now(UTC)
    require_aware(timestamp)
    digest = candidate.content_hash
    with unit_of_work.engine.begin() as connection:
        if lease is not None:
            require_lease(connection, lease.id, lease.lease_token, timestamp)
        connection.execute(select(func.pg_advisory_xact_lock(1729878439, candidate.season)))
        existing = connection.execute(
            select(league_snapshot.c.id).where(league_snapshot.c.content_hash == digest)
        ).scalar_one_or_none()
        if existing is not None:
            return SnapshotRef(existing, digest)
        current = connection.execute(
            select(league_snapshot.c.observed_at)
            .join(current_snapshot, current_snapshot.c.snapshot_id == league_snapshot.c.id)
            .where(current_snapshot.c.season == candidate.season)
        ).scalar_one_or_none()
        if current is not None and candidate.observed_at <= current:
            raise StaleSnapshotError(
                "older or ambiguous observed revision cannot replace current state"
            )
        snapshot_id = uuid4()
        connection.execute(
            insert(league_snapshot).values(
                id=snapshot_id,
                season=candidate.season,
                content_hash=digest,
                rules_hash=candidate.rules_hash,
                manifest_hash=candidate.manifest_hash,
                observed_at=candidate.observed_at,
                complete=True,
                payload=candidate.model_dump(mode="json"),
            )
        )
        if candidate.roster:
            connection.execute(
                insert(roster_entry),
                [
                    {
                        "snapshot_id": snapshot_id,
                        "entity_id": item.entity_id,
                        "team_id": item.team_id,
                        "slot": item.slot,
                    }
                    for item in candidate.roster
                ],
            )
        connection.execute(
            insert(current_snapshot)
            .values(season=candidate.season, snapshot_id=snapshot_id)
            .on_conflict_do_update(
                index_elements=[current_snapshot.c.season], set_={"snapshot_id": snapshot_id}
            )
        )
        connection.execute(
            insert(outbox_event).values(
                event_type="league.updated",
                entity_id=snapshot_id,
                payload={
                    "snapshotId": str(snapshot_id),
                    "season": candidate.season,
                    "rulesHash": candidate.rules_hash,
                },
            )
        )
    return SnapshotRef(snapshot_id, digest)


def get_current_snapshot(season: int, unit_of_work: UnitOfWork) -> LeagueSnapshot | None:
    with unit_of_work.engine.connect() as connection:
        row = (
            connection.execute(
                select(league_snapshot.c.id, league_snapshot.c.payload)
                .join(current_snapshot, current_snapshot.c.snapshot_id == league_snapshot.c.id)
                .where(current_snapshot.c.season == season)
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return LeagueSnapshot(row["id"], LeagueSnapshotCandidate.model_validate(row["payload"]))
