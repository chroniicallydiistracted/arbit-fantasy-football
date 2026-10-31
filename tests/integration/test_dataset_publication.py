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


def test_delayed_older_source_cannot_replace_a_newer_revision(uow):
    now = datetime(2026, 10, 31, tzinfo=UTC)
    old = manifest(when=now).model_copy(
        update={"source": {"source_updated_at": "2026-10-29T00:00:00Z"}}
    )
    new = manifest("d" * 64, now + timedelta(seconds=1)).model_copy(
        update={"source": {"source_updated_at": "2026-10-30T00:00:00Z"}}
    )
    publish_dataset(old, uow)
    latest = publish_dataset(new, uow)
    delayed = old.model_copy(update={"observed_at": now + timedelta(seconds=2)})
    with pytest.raises(ValueError, match="STALE_SOURCE_REVISION"):
        publish_dataset(delayed, uow)
    assert get_dataset(uow, old.logical_key)["manifest_hash"] == latest


def test_catalog_order_fences_delayed_git_like_revisions_without_update_times(uow):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from arbit_data.nflverse.catalog import build_catalog
    from arbit_data.nflverse.service import enqueue_catalog

    now = datetime(2026, 10, 31, tzinfo=UTC)

    def catalog(identity, digest, when):
        return build_catalog(
            [
                {
                    "tag_name": "stats_player",
                    "assets": [
                        {
                            "id": identity,
                            "name": "stats_player_week_2026.parquet",
                            "size": 10,
                            "digest": "sha256:" + digest,
                            "browser_download_url": "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.parquet",
                        }
                    ],
                }
            ],
            [],
            [],
            observed_at=when,
        )

    old = catalog(1, "a" * 64, now)
    new = catalog(2, "d" * 64, now + timedelta(seconds=10))
    old_key = enqueue_catalog(old, uow)
    new_key = enqueue_catalog(new, uow)
    a = manifest(when=now).model_copy(
        update={
            "logical_key": old.assets[0].logical_key,
            "source": old.assets[0].model_dump(mode="json"),
        }
    )
    b = manifest("d" * 64, now + timedelta(seconds=11)).model_copy(
        update={
            "logical_key": new.assets[0].logical_key,
            "source": new.assets[0].model_dump(mode="json"),
        }
    )
    publish_dataset(a, uow, catalog_hash=old_key)
    committed = threading.Event()

    def publish_new():
        result = publish_dataset(b, uow, catalog_hash=new_key)
        committed.set()
        return result

    def delayed_old():
        assert committed.wait(3)
        with pytest.raises(ValueError, match="STALE_SOURCE_REVISION"):
            publish_dataset(
                a.model_copy(update={"observed_at": now + timedelta(seconds=20)}),
                uow,
                catalog_hash=old_key,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        newest = pool.submit(publish_new)
        late = pool.submit(delayed_old)
        expected = newest.result()
        late.result()
    assert get_dataset(uow, a.logical_key)["manifest_hash"] == expected
