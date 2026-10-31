"""Trusted explicit crosswalks reuse UUIDs, preserve conflicting aliases and enforce observation times."""

from datetime import UTC, datetime, timedelta

import pytest
from arbit_core.identity import ProviderRef
from arbit_data.identities import resolve_native
from arbit_data.nflverse.crosswalk import apply_crosswalk
from arbit_data.nflverse.repository import publish_dataset
from arbit_data.schema import entity_alias
from sqlalchemy import select, text
from test_dataset_publication import manifest

pytestmark = pytest.mark.integration


def test_crosswalk_reuses_ffa_uuid_and_is_not_retroactive(uow):
    now = datetime(2026, 10, 31, tzinfo=UTC)
    ref = ProviderRef(provider="espn", entity_kind="athlete", external_id="12345")
    with uow.engine.begin() as c:
        existing = resolve_native(c, [ref], now - timedelta(days=1), "f" * 64)[ref]
    version = manifest(when=now)

    def attach(c, key):
        report = apply_crosswalk(c, [{"gsis_id": "00-0012345", "espn_id": "12345"}], key, now)
        assert report["linked"] == 1 and report["conflicts"] == 0

    key = publish_dataset(version, uow, on_publish=attach)
    with uow.engine.begin() as c:
        row = (
            c.execute(select(entity_alias).where(entity_alias.c.provider == "gsis"))
            .mappings()
            .one()
        )
        assert row["entity_id"] == existing and row["valid_from"] == now
        assert row["method"] == "verified_crosswalk"
        assert (
            apply_crosswalk(c, [{"gsis_id": "00-0012345", "espn_id": "12345"}], key, now)["linked"]
            == 1
        )
    with uow.engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM identity_import")) == 1


def test_ambiguous_directory_ids_and_existing_alias_disagreement_never_merge(uow):
    now = datetime(2026, 10, 31, tzinfo=UTC)
    with uow.engine.begin() as c:
        resolve_native(
            c,
            [
                ProviderRef(provider="espn", entity_kind="athlete", external_id="12345"),
                ProviderRef(provider="gsis", entity_kind="athlete", external_id="00-0012345"),
            ],
            now - timedelta(days=1),
            "e" * 64,
        )
    rows = [
        {"gsis_id": "00-0012345", "espn_id": "12345"},
        {"gsis_id": "00-0012346", "espn_id": "23456"},
        {"gsis_id": "00-0012347", "espn_id": "23456"},
        {"gsis_id": "00-0012348", "espn_id": None},
        {"gsis_id": None, "espn_id": "56789"},
    ]
    report = {}

    def attach(c, key):
        report.update(apply_crosswalk(c, rows, key, now))

    publish_dataset(manifest(when=now), uow, on_publish=attach)
    assert report["conflicts"] == 3 and report["unresolved"] == 1
    with uow.engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM mapping_review")) == 4
        assert c.scalar(text("SELECT count(*) FROM canonical_entity")) == 3
        assert (
            c.scalar(
                text(
                    "SELECT count(DISTINCT entity_id) FROM entity_alias WHERE external_id IN ('12345','00-0012345')"
                )
            )
            == 2
        )


def test_stored_player_stats_join_exact_uuid_with_cutoff_and_missingness(uow, tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from arbit_data.nflverse.objects import ObjectStore
    from arbit_data.nflverse.reads import player_stats

    now = datetime(2026, 10, 31, tzinfo=UTC)
    path = tmp_path / "source.parquet"
    pq.write_table(
        pa.table(
            {
                "player_id": ["00-0012345"],
                "season": [2026],
                "season_type": ["REG"],
                "week": [1],
                "passing_yards": [None],
                "fantasy_points": [12.34],
            }
        ),
        path,
    )
    store = ObjectStore(tmp_path / "objects")
    raw = store.write((path.read_bytes(),))
    version = manifest(raw.sha256, now).model_copy(
        update={"logical_key": "nflverse/nflverse-data/stats_player/stats_player_week_2026"}
    )
    publish_dataset(
        version,
        uow,
        on_publish=lambda c, key: apply_crosswalk(
            c, [{"gsis_id": "00-0012345", "espn_id": "12345"}], key, now
        ),
    )
    with uow.engine.connect() as c:
        uid = c.scalar(select(entity_alias.c.entity_id).where(entity_alias.c.provider == "gsis"))
    result = player_stats(uow, store, uid, 2026, week=1, cutoff=now)
    assert result["status"] == "available" and result["rows"][0]["passing_yards"] is None
    assert result["rows"][0]["fantasy_points"] == "12.34"
    assert result["recommendations_enabled"] is False
    assert (
        player_stats(uow, store, uid, 2026, cutoff=now - timedelta(microseconds=1))["status"]
        == "unresolved_identity"
    )
