from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import text

pytestmark = pytest.mark.integration


def test_partial_candidate_preserves_current_and_replay_is_idempotent(uow, candidate):
    from arbit_data.snapshots import IncompleteSnapshotError, get_current_snapshot, publish_snapshot

    first = publish_snapshot(candidate, uow)
    with pytest.raises(IncompleteSnapshotError):
        publish_snapshot(candidate.model_copy(update={"complete": False}), uow)
    assert publish_snapshot(candidate, uow) == first
    assert get_current_snapshot(2026, uow).id == first.id
    with uow.engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM league_snapshot")) == 1
        assert connection.scalar(text("SELECT count(*) FROM outbox_event")) == 1


def test_old_or_ambiguous_revision_cannot_replace_newer_state(uow, candidate):
    from arbit_data.snapshots import StaleSnapshotError, get_current_snapshot, publish_snapshot

    first = publish_snapshot(candidate, uow)
    newer = candidate.model_copy(
        update={"observed_at": candidate.observed_at + timedelta(seconds=1)}
    )
    second = publish_snapshot(newer, uow)
    assert second.id != first.id
    assert publish_snapshot(candidate, uow) == first
    with pytest.raises(StaleSnapshotError):
        publish_snapshot(candidate.model_copy(update={"rules_hash": "c" * 64}), uow)
    assert get_current_snapshot(2026, uow).id == second.id


def test_duplicate_or_owned_available_player_is_rejected_before_publication(candidate):
    from arbit_data.contracts import LeagueSnapshotCandidate

    data = candidate.model_dump()
    data["roster"] = (
        *candidate.roster,
        candidate.roster[0].model_copy(update={"team_id": UUID(int=2)}),
    )
    with pytest.raises(ValidationError, match="ownership"):
        LeagueSnapshotCandidate.model_validate(data)
    data = candidate.model_dump()
    data["available"] = (UUID(int=3),)
    with pytest.raises(ValidationError, match="owned"):
        LeagueSnapshotCandidate.model_validate(data)


def test_concurrent_same_snapshot_has_one_publication(uow, candidate):
    from arbit_data.snapshots import publish_snapshot

    with ThreadPoolExecutor(max_workers=2) as pool:
        refs = list(pool.map(lambda _: publish_snapshot(candidate, uow), range(2)))
    assert refs[0] == refs[1]
    with uow.engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM outbox_event")) == 1


def test_expired_worker_cannot_publish_and_order_only_changes_are_idempotent(uow, candidate):
    from datetime import UTC, datetime

    from arbit_data.jobs import JobQueue, LeaseLostError
    from arbit_data.snapshots import publish_snapshot

    now = datetime.now(UTC)
    queue = JobQueue(uow, lease_seconds=10)
    queue.enqueue("fixture", "fixture://one", "one", now)
    lease = queue.claim_job("old", now)
    queue.claim_job("new", now + timedelta(seconds=11))
    with pytest.raises(LeaseLostError):
        publish_snapshot(candidate, uow, lease=lease, now=now + timedelta(seconds=12))
    first = publish_snapshot(candidate, uow)
    reordered = candidate.model_copy(update={"teams": tuple(reversed(candidate.teams))})
    assert publish_snapshot(reordered, uow) == first


def test_timestamp_offsets_of_same_observation_are_one_revision(uow, candidate):
    from datetime import timezone

    from arbit_data.snapshots import publish_snapshot

    first = publish_snapshot(candidate, uow)
    same_instant = candidate.model_copy(
        update={"observed_at": candidate.observed_at.astimezone(timezone(timedelta(hours=-7)))}
    )
    assert publish_snapshot(same_instant, uow) == first
