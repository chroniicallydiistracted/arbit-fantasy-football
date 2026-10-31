"""Dataset versions preserve history, last-good pointer, observation cutoffs and fenced jobs."""

from datetime import UTC, datetime, timedelta

import pytest
from arbit_data.nflverse.repository import DatasetManifest, get_dataset, publish_dataset
from sqlalchemy import text

pytestmark = pytest.mark.integration


def manifest(raw="a" * 64, when=None):
    return DatasetManifest(
        logical_key="nflverse/nflverse-data/stats_player/week_2026",
        family="stats_player",
        observed_at=when or datetime(2026, 10, 31, tzinfo=UTC),
        raw_hash=raw,
        parquet_hash=raw,
        row_count=1,
        schema_hash="b" * 64,
        columns=[{"name": "player_id", "type": "string", "nullable": True}],
        coverage={"seasons": [2026]},
        missing={},
        status="validated",
        source={
            "source_url": "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.parquet",
            "license": "CC-BY-4.0",
            "usage": "statistics",
        },
        limitations=["Historical publication not established by local observation"],
    )


def test_versions_replay_and_as_of_never_fabricate_earlier_knowledge(uow):
    first = manifest()
    one = publish_dataset(first, uow)
    assert (
        get_dataset(uow, first.logical_key, cutoff=first.observed_at - timedelta(microseconds=1))
        is None
    )
    assert get_dataset(uow, first.logical_key, cutoff=first.observed_at)["manifest_hash"] == one
    second = manifest("c" * 64, first.observed_at + timedelta(seconds=10))
    two = publish_dataset(second, uow)
    assert one != two
    assert publish_dataset(first, uow) == one
    assert get_dataset(uow, first.logical_key)["manifest_hash"] == two
    assert get_dataset(uow, first.logical_key, cutoff=first.observed_at)["manifest_hash"] == one
    with uow.engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM dataset_manifest")) == 2


def test_fenced_dataset_transaction_rollback_preserves_current(uow):
    from arbit_data.jobs import JobQueue, LeaseLostError

    first = manifest()
    publish_dataset(first, uow)
    q = JobQueue(uow, lease_seconds=10)
    queued = q.enqueue("nflverse.ingest", "catalog|1", "one", first.observed_at)
    lease = q.claim_job("slow", first.observed_at)
    times = iter((first.observed_at, first.observed_at + timedelta(seconds=11)))
    with pytest.raises(LeaseLostError):
        publish_dataset(
            manifest("d" * 64, first.observed_at + timedelta(seconds=1)),
            uow,
            lease=lease,
            clock=lambda: next(times),
        )
    assert get_dataset(uow, first.logical_key)["raw_hash"] == "a" * 64
    assert q.get_job(queued.id).status == "running"
