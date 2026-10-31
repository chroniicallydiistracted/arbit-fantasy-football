"""Columnar normalization preserves source columns/nulls/scopes and never scores fantasy data."""

from datetime import UTC, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from arbit_data.nflverse.catalog import build_catalog
from arbit_data.nflverse.normalize import normalize
from arbit_data.nflverse.objects import ObjectStore


def asset(filename, family="stats_player", usage=None):
    record = {
        "tag_name": family,
        "assets": [
            {
                "id": 1,
                "name": filename,
                "size": 10,
                "browser_download_url": f"https://github.com/nflverse/nflverse-data/releases/download/{family}/{filename}",
            }
        ],
    }
    result = build_catalog([record], [], [], observed_at=datetime.now(UTC)).assets[0]
    return result if usage is None else result.model_copy(update={"usage": usage})


def test_parquet_keeps_all_fields_nulls_and_multiple_scopes(tmp_path):
    table = pa.table(
        {
            "player_id": ["00-0012345", "00-0012345"],
            "season": [2026, 2026],
            "season_type": ["REG", "POST"],
            "week": [1, 19],
            "passing_yards": [None, 12.5],
            "new_provider_field": ["007", "008"],
        }
    )
    path = tmp_path / "source.parquet"
    pq.write_table(table, path)
    store = ObjectStore(tmp_path / "objects")
    raw = store.write((path.read_bytes(),))
    result = normalize(asset("stats_player_week_2026.parquet"), raw, store)
    assert result.row_count == 2 and result.raw_hash == result.parquet_hash
    loaded = pq.read_table(store.verify(result.parquet_hash).path)
    assert loaded.equals(table)
    assert result.coverage["season_types"] == ["POST", "REG"]
    assert result.coverage["seasons"] == [2026]
    assert result.columns[-1]["name"] == "new_provider_field"
    assert result.missing["passing_yards"] == 1


def test_csv_keeps_leading_zero_identifiers_and_unknown_values(tmp_path):
    store = ObjectStore(tmp_path / "objects")
    raw = store.write(
        (
            b'player_id,season,season_type,week,novel\n00-0000007,2026,REG,1,\n00-0000008,2026,REG,2,"NA"\n',
        )
    )
    result = normalize(asset("stats_player_week_2026.csv"), raw, store)
    data = pq.read_table(store.verify(result.parquet_hash).path).to_pylist()
    assert data[0]["player_id"] == "00-0000007" and data[0]["novel"] is None
    assert data[1]["novel"] == "NA"
    assert result.coverage["weeks"] == [1, 2]


def test_invalid_core_schema_and_rds_fail_safely(tmp_path):
    store = ObjectStore(tmp_path / "objects")
    bad = store.write((b"wrong\nvalue\n",))
    with pytest.raises(ValueError, match="REQUIRED_COLUMNS_MISSING"):
        normalize(asset("stats_player_week_2026.csv"), bad, store)
    with pytest.raises(ValueError, match="RDS_"):
        normalize(asset("advstats_season_pass_2026.rds", "pfr_advstats"), bad, store)
    meta = normalize(
        asset("timestamp.json", "players"), store.write((b'{"timestamp":"2026"}',)), store
    )
    assert meta.parquet_hash is None and meta.status == "archive_only"


def test_quality_profile_exposes_missing_and_duplicate_keys_without_dropping_rows(tmp_path):
    store = ObjectStore(tmp_path / "objects")
    raw = store.write(
        (
            b"player_id,season,season_type,week\n00-0000007,2026,REG,1\n00-0000007,2026,REG,1\n,2026,REG,1\n",
        )
    )
    result = normalize(asset("stats_player_week_2026.csv"), raw, store)
    assert result.row_count == 3
    assert result.coverage["rows_missing_keys"] == 1
    assert result.coverage["duplicate_keys"] == 1


def test_integral_float_scope_values_are_profiled_without_changing_source_types(tmp_path):
    store = ObjectStore(tmp_path / "objects")
    table = pa.table({"season": ["2026", "2026"], "week": [1.0, 2.0], "value": [None, 1.25]})
    path = tmp_path / "float-weeks.parquet"
    pq.write_table(table, path)
    raw = store.write((path.read_bytes(),))
    result = normalize(asset("ep_weekly_2026.parquet", "misc"), raw, store)
    assert result.coverage["weeks"] == [1, 2]
    assert pq.read_table(store.path(result.parquet_hash)).equals(table)


def test_corrupt_csv_deflate_uses_safe_validation_boundary(tmp_path):
    import gzip

    store = ObjectStore(tmp_path / "objects")
    compressed = bytearray(gzip.compress(b"column\nvalue\n"))
    compressed[10] = 0x07
    raw = store.write((bytes(compressed),))
    with pytest.raises(ValueError, match="TABULAR_DECODE_FAILED"):
        normalize(asset("patch.csv.gz", "misc"), raw, store)


def test_nested_reference_serialization_preserves_table_fields():
    import pandas as pd
    from arbit_data.nflverse.rds_decode import nested_value

    inner = pd.DataFrame({"season": [2026], "amount": [12.5]})
    nested = nested_value(inner)
    assert nested["columns"] == ["season", "amount"]
    assert nested["rows"][0] == [2026, "12.5"]
