"""Owner audit AUD-04: contamination inside permitted columns, and store bytes checked by content.

Unknown-column rejection (T32) and the code scan (T31) stay. These tests plant forbidden or
unknown values inside columns the pipeline accepts, and corrupt a content-addressed object without
renaming it. Each must stop fitting or forecasting.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

import polars as pl
import pytest
from arbit_model.dvp import contract, provenance, shadow
from arbit_model.dvp import observations as obs
from arbit_model.dvp.provenance import LineageError
from test_dvp_walkforward import season_data

ROOT = Path(__file__).resolve().parents[3]
SCORING = {"athlete": "a" * 64, "defense": "d" * 64}


def clean() -> pl.DataFrame:
    """Synthetic observations with full lineage, as `observations.observations` writes them."""
    rows, _ = season_data(seasons=(2018, 2019), weeks=6)
    dst = pl.col("position") == obs.DST
    return rows.with_columns(
        pl.when(dst).then(pl.col("offense")).otherwise(pl.col("defense")).alias("unit"),
        pl.when(dst)
        .then(pl.lit("ffa_targets.defense"))
        .otherwise(pl.lit("ffa_targets.athlete"))
        .alias("source_id"),
        pl.when(dst)
        .then(pl.lit(SCORING["defense"]))
        .otherwise(pl.lit(SCORING["athlete"]))
        .alias("scoring_hash"),
        pl.lit(obs.FINALITY).alias("finality_basis"),
    )


def plant(frame: pl.DataFrame, column: str, value, rows: int = 3) -> pl.DataFrame:
    hit = pl.int_range(pl.len()) < rows
    return frame.with_columns(
        pl.when(hit).then(pl.lit(value)).otherwise(pl.col(column)).alias(column)
    )


def test_clean_observations_keep_the_contract():
    frame = clean()
    assert contract.violations(frame, SCORING) == {}
    assert contract.enforce(frame, SCORING) is frame
    assert shadow.prepare_checked(frame, SCORING).height == frame.height


@pytest.mark.parametrize(
    ("column", "value", "rule"),
    [
        (
            "source_type",
            "EXTERNAL_FANTASY_PROJECTION_FORBIDDEN",
            "source_type is not an FFA actual",
        ),
        ("source_type", "ARBIT_MODEL_OUTPUT", "source_type is not an FFA actual"),
        ("source_type", "PROVIDER_FORECAST", "source_type is not an FFA actual"),
        ("observed_or_generated", "generated", "row is not observed"),
        ("source_id", "espn.player_projections", "source_id is not this position's FFA table"),
        ("source_id", "ffa_targets.defense", "source_id is not this position's FFA table"),
        ("scoring_hash", "f" * 64, "scoring_hash is not the configured rules"),
        ("finality_basis", "provider pregame estimate", "finality_basis is not the declared rule"),
        ("status", "forecast", "unknown status"),
        ("position", "FLEX", "unknown position"),
    ],
)
def test_a_forbidden_value_in_a_permitted_column_stops_the_pipeline(column, value, rule):
    """An `opponent_expected` column is refused by name (T32); here the names are all allowed and
    the values are wrong."""
    bad = plant(clean().sort("position", descending=True), column, value)
    assert rule in contract.violations(bad, SCORING)
    with pytest.raises(LineageError, match="ROW_CONTRACT"):
        shadow.prepare_checked(bad, SCORING)


def test_points_must_agree_with_the_label_status():
    frame = clean()
    nan = frame.with_columns(
        pl.when(pl.int_range(pl.len()) == 0).then(float("nan")).otherwise("points").alias("points")
    )
    assert "valid cell without finite points" in contract.violations(nan, SCORING)
    scored_invalid = plant(frame, "status", "invalid_refused_line")
    assert "invalid cell with points" in contract.violations(scored_invalid, SCORING)


def test_timing_orientation_and_keys_are_checked_row_by_row():
    frame = clean()
    early = frame.with_columns(
        pl.when(pl.int_range(pl.len()) < 2)
        .then(pl.col("kickoff"))
        .otherwise(pl.col("available_at"))
        .alias("available_at")
    )
    assert "available before kickoff" in contract.violations(early, SCORING)
    flipped = frame.with_columns(pl.col("offense").alias("unit"))  # every QB-K row now wrong
    assert contract.violations(flipped, SCORING)["unit does not follow the position"] > 0
    doubled = pl.concat([frame, frame.head(1)])
    assert contract.violations(doubled, SCORING)["duplicate keys"] == 2
    missing = frame.drop("finality_basis")
    assert "missing column finality_basis" in contract.violations(missing, SCORING)
    nulls = frame.with_columns(pl.lit(None, dtype=pl.String).alias("source_id"))
    assert "null lineage or key" in contract.violations(nulls, SCORING)


def test_admission_refuses_unknown_values_inside_allowed_target_columns():
    """The target tables' `basis` and `season_type` admit only known values (provenance SOURCES)."""
    spec = provenance.SOURCES["ffa_targets.athlete"]
    frame = pl.DataFrame({c: [None] for c in spec.used}).with_columns(
        pl.lit("statistics").alias("basis"), pl.lit("REG").alias("season_type")
    )
    kwargs = {
        "ancestry": "test",
        "scoring_hash": SCORING["athlete"],
        "expected_scoring": SCORING,
    }
    provenance.admit(frame, spec.source_id, **kwargs)
    for column, value in (("basis", "provider_projection"), ("season_type", "PROJ")):
        bad = frame.with_columns(pl.lit(value).alias(column))
        with pytest.raises(LineageError, match="UNKNOWN_VALUE"):
            provenance.admit(bad, spec.source_id, **kwargs)


def cli():
    spec = importlib.util.spec_from_file_location("dvp_cli_contract", ROOT / "scripts/model/dvp.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_store_object_is_read_only_if_its_bytes_match_its_digest(tmp_path):
    dvp = cli()
    objects = tmp_path / "objects"
    objects.mkdir()
    manifest = json.dumps({"tables": {}}).encode()
    digest = hashlib.sha256(manifest).hexdigest()
    (objects / digest).write_bytes(manifest)
    index = {"seasons": {"2025": digest}}
    assert dvp.season_manifest(tmp_path, index, 2025) == {"tables": {}}
    (objects / digest).write_bytes(manifest.replace(b"tables", b"tablez"))  # same name, new bytes
    with pytest.raises(SystemExit, match="does not match its digest"):
        dvp.season_manifest(tmp_path, index, 2025)
    with pytest.raises(SystemExit, match="does not match its digest"):
        dvp.verified_object(tmp_path, digest)


def test_every_reader_of_observations_enforces_the_contract():
    """dvp.py's reliability, backtest, sitstart and verify read observations only through it."""
    text = (ROOT / "scripts/model/dvp.py").read_text()
    reads = text.count('pl.read_parquet(run / "observations.parquet")')
    assert reads == 4
    assert (
        text.count('contract.enforce(\n        pl.read_parquet(run / "observations.parquet")')
        == reads
    )
    harness = (ROOT / "scripts/model/dvp_prospective.py").read_text()
    assert "shadow.prepare_checked" in harness and "contract.enforce(obs.observations" in harness
