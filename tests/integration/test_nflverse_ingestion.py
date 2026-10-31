"""Durable complete import: typed source failures, recovery, identity publication and restart."""

from datetime import UTC, datetime, timedelta

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from arbit_data.errors import SourceError
from arbit_data.nflverse.catalog import build_catalog
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.nflverse.repository import get_dataset
from arbit_data.nflverse.service import DatasetService, enqueue_catalog, import_status
from sqlalchemy import text

pytestmark = pytest.mark.integration


def setup(uow, tmp_path, *, hashless=False):
    path = tmp_path / "players.parquet"
    pq.write_table(pa.table({"gsis_id": ["00-0012345"], "espn_id": ["12345"]}), path)
    data = path.read_bytes()
    import hashlib

    catalog = build_catalog(
        [
            {
                "tag_name": "players",
                "assets": [
                    {
                        "id": 1,
                        "name": "players.parquet",
                        "size": len(data),
                        "digest": None
                        if hashless
                        else "sha256:" + hashlib.sha256(data).hexdigest(),
                        "browser_download_url": "https://github.com/nflverse/nflverse-data/releases/download/players/players.parquet",
                    }
                ],
            }
        ],
        [],
        [],
        observed_at=datetime(2026, 10, 31, tzinfo=UTC),
    )
    key = enqueue_catalog(catalog, uow, now=catalog.observed_at)

    class Source:
        error = None
        calls = 0

        def download(self, asset, store):
            self.calls += 1
            if self.error:
                raise self.error
            return store.write((data,), expected_size=asset.size)

    return key, Source(), ObjectStore(tmp_path / "objects"), catalog


def test_complete_import_is_idempotent_and_attaches_identities_atomically(uow, tmp_path):
    key, source, store, catalog = setup(uow, tmp_path)
    assert enqueue_catalog(catalog, uow) == key
    service = DatasetService(uow, store, source, key)
    result = service.run_one()
    assert result["status"] == "published"
    assert service.run_one() is None
    assert import_status(uow, key)["statuses"] == {"published": 1}
    with uow.engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM dataset_manifest")) == 1
        assert c.scalar(text("SELECT count(*) FROM identity_import")) == 1
        assert c.scalar(text("SELECT count(*) FROM entity_alias WHERE provider='gsis'")) == 1


def test_retry_after_persists_and_new_worker_resumes(uow, tmp_path):
    key, source, store, catalog = setup(uow, tmp_path)
    now = catalog.observed_at
    source.error = SourceError("RATE_LIMITED", retry_after_seconds=120)
    service = DatasetService(uow, store, source, key, clock=lambda: now, jitter=lambda: 0)
    assert service.run_one()["status"] == "retrying"
    assert service.run_one() is None
    source.error = None
    restarted = DatasetService(uow, store, source, key, clock=lambda: now + timedelta(seconds=120))
    assert restarted.run_one()["status"] == "published"


def test_failed_input_never_becomes_current_and_can_retry_explicitly(uow, tmp_path):
    key, source, store, catalog = setup(uow, tmp_path)
    source.error = SourceError("NOT_FOUND", status=404)
    assert DatasetService(uow, store, source, key).run_one()["status"] == "failed"
    assert get_dataset(uow, catalog.assets[0].logical_key) is None
    source.error = None
    enqueue_catalog(catalog, uow, retry_failed=True)
    assert DatasetService(uow, store, source, key).run_one()["status"] == "published"
    with uow.engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM job WHERE status='failed'")) == 1
        assert c.scalar(text("SELECT count(*) FROM job WHERE status='succeeded'")) == 1


def test_an_expired_importer_cannot_mark_dataset_success_or_failure(uow, tmp_path):
    key, source, store, catalog = setup(uow, tmp_path)
    now = catalog.observed_at
    service = DatasetService(uow, store, source, key, clock=lambda: now)

    def expired(asset, objects):
        service.clock = lambda: now + timedelta(seconds=181)
        replacement = service.queue.claim_job(
            "replacement", service.clock(), job_type="nflverse.ingest", input_prefix=key + "|"
        )
        assert replacement is not None
        raise SourceError("UNAVAILABLE")

    source.download = expired
    outcome = service.run_one()
    assert outcome["status"] == "lease_lost"
    assert get_dataset(uow, catalog.assets[0].logical_key) is None
    assert import_status(uow, key)["statuses"] == {"queued": 1}
