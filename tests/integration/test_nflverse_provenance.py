"""A size-only download cannot become trusted data until immutable asset identity is confirmed."""

from datetime import timedelta

import pytest
from arbit_data.nflverse.provenance import confirm_catalog
from arbit_data.nflverse.repository import get_dataset
from arbit_data.nflverse.service import DatasetService, enqueue_staged_publications
from test_nflverse_ingestion import setup

pytestmark = pytest.mark.integration


def test_hashless_stage_then_confirm_and_publish_with_honest_availability(uow, tmp_path):
    key, source, store, catalog = setup(uow, tmp_path, hashless=True)
    now = catalog.observed_at
    service = DatasetService(uow, store, source, key, clock=lambda: now + timedelta(seconds=1))
    assert service.run_one()["status"] == "staged"
    assert get_dataset(uow, catalog.assets[0].logical_key) is None
    fresh = catalog.model_copy(update={"observed_at": now + timedelta(seconds=10)})
    report = confirm_catalog(uow, store, key, fresh)
    assert report["confirmed"] == 1 and report["changed"] == []
    enqueue_staged_publications(uow, key, now=fresh.observed_at)
    service.clock = lambda: fresh.observed_at
    assert service.run_one()["status"] == "published"
    assert (
        get_dataset(uow, catalog.assets[0].logical_key, cutoff=now + timedelta(seconds=2)) is None
    )
    assert get_dataset(uow, catalog.assets[0].logical_key, cutoff=fresh.observed_at) is not None


def test_same_size_replacement_id_fails_closed(uow, tmp_path):
    key, source, store, catalog = setup(uow, tmp_path, hashless=True)
    service = DatasetService(uow, store, source, key)
    assert service.run_one()["status"] == "staged"
    replacement = catalog.assets[0].model_copy(update={"source_id": "nflverse/nflverse-data:999"})
    fresh = catalog.model_copy(
        update={
            "assets": (replacement,),
            "observed_at": catalog.observed_at + timedelta(seconds=10),
        }
    )
    report = confirm_catalog(uow, store, key, fresh)
    assert report["confirmed"] == 0 and len(report["changed"]) == 1
    enqueue_staged_publications(uow, key)
    assert service.run_one()["status"] == "failed"
    assert get_dataset(uow, catalog.assets[0].logical_key) is None
