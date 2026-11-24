"""T26 and T27 of the owner's DvP specification.

T26: the research speaks Arbit's identities (franchise codes, FFA position groups, one D/ST per team)
and cannot write to a prediction weight, a canonical table or a service: every database connection
it opens is read-only, it issues no write statement, and nothing in it imports the feature weights.

T27: artifacts read back and reproduce: a forecast file's content hash ignores row order, a rerun
never overwrites evidence, metrics survive a Parquet round trip and a shuffle, every committed
receipt carries its schema, and the committed verification still covers the committed receipts.
On a machine that holds the audit run, the real forecasts are checked against their receipts too.
"""

import ast
import importlib.util
import json
import os
import re
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from arbit_model.dvp import walkforward as wf
from arbit_model.gamebook import FFA_POSITIONS
from arbit_model.teams import franchise

ROOT = Path(__file__).resolve().parents[3]
RECEIPTS = ROOT / "docs/research/dvp"
CLI = ROOT / "scripts/model/dvp.py"
PACKAGE = ROOT / "libs/arbit-model/src/arbit_model/dvp"
# The frozen audit run; ARBIT_DVP_AUDIT_RUN points a worktree at the main checkout's copy.
AUDIT_RUN = Path(
    os.environ.get("ARBIT_DVP_AUDIT_RUN", ROOT / "artifacts/dvp/phase1-audit-20261124T024442Z")
)
STAGES = ("development", "validation", "holdout")
GROUPS = {*FFA_POSITIONS, "DST"}  # the FFA lineup groups the research models


def cli():
    spec = importlib.util.spec_from_file_location("dvp_cli", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def forecasts(seed: int = 3, n: int = 60) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    week = rng.integers(1, 18, n).astype(np.int32)
    return pl.DataFrame(
        {
            "season": np.full(n, 2020, dtype=np.int32),
            "week": week,
            "game_id": [f"2020_{w:02d}_G{i}" for i, w in enumerate(week)],
            "offense": [f"T{i % 7}" for i in range(n)],
            "position": ["DST" if i % 2 else "WR" for i in range(n)],
            "points": rng.normal(8, 5, n).round(2),
            "b00": rng.normal(8, 1, n),
            "b06": rng.normal(8, 1.5, n),
        }
    )


# --- T27 ------------------------------------------------------------------------------------------


def test_t27_content_hash_ignores_order_and_sees_every_value():
    dvp = cli()
    frame = forecasts()
    shuffled = frame.sample(fraction=1.0, shuffle=True, seed=1).select(reversed(frame.columns))
    assert dvp.content_sha256(shuffled) == dvp.content_sha256(frame)
    changed = frame.with_columns(
        pl.when(pl.int_range(pl.len()) == 7)
        .then(pl.col("b06") + 1e-6)
        .otherwise("b06")
        .alias("b06")
    )
    assert dvp.content_sha256(changed) != dvp.content_sha256(frame)


def test_t27_a_rerun_never_overwrites_evidence(tmp_path):
    dvp = cli()
    path = tmp_path / "forecasts.parquet"
    frame = forecasts()
    dvp.write_forecasts(path, frame)
    written = path.read_bytes()
    dvp.write_forecasts(path, frame.sample(fraction=1.0, shuffle=True, seed=2))
    assert path.read_bytes() == written  # same content: the file and its hash stay
    with pytest.raises(SystemExit, match="different forecasts"):
        dvp.write_forecasts(path, frame.with_columns(pl.col("b06") * 2))
    assert path.read_bytes() == written


def test_t27_metrics_survive_a_round_trip_and_a_shuffle(tmp_path):
    frame = forecasts(n=400)
    path = tmp_path / "f.parquet"
    frame.write_parquet(path)
    again = pl.read_parquet(path).sample(fraction=1.0, shuffle=True, seed=5)
    a = wf.metrics(frame, ["b00", "b06"], block="week", reps=200, seed=1729)
    b = wf.metrics(again, ["b00", "b06"], block="week", reps=200, seed=1729)
    assert a == b
    assert wf.calibration(frame, "b06") == wf.calibration(again, "b06")


REQUIRED = {
    "format",
    "generatedAt",
    "code",
    "auditRun",
    "targetsIndex",
    "config",
    "stage",
    "seasons",
    "seed",
    "bootstrapReplicates",
    "bootstrapBlock",
    "results",
    "forecastsSha256",
    "forbidden_vendor_projection_dependencies",
}
METRIC_KEYS = {"rmse", "mae", "meanError", "spearman", "deltaRmse", "relativeDelta", "delta95"}


@pytest.mark.parametrize("stage", STAGES)
def test_t27_committed_receipts_carry_their_schema(stage):
    receipt = json.loads((RECEIPTS / f"backtest-{stage}.json").read_text())
    assert REQUIRED <= receipt.keys()
    assert receipt["forbidden_vendor_projection_dependencies"] == 0
    assert set(receipt["results"]) == GROUPS
    for result in receipt["results"].values():
        for name, value in result.items():
            if name.startswith("b0"):
                assert METRIC_KEYS <= value.keys(), name


def test_t27_the_committed_verification_covers_the_committed_receipts():
    verified = json.loads((RECEIPTS / "verify-receipt.json").read_text())
    assert verified["status"] == "PASSED"
    dvp = cli()
    for name, digest in verified["receiptsVerified"].items():
        assert dvp.sha256(RECEIPTS / name) == digest, f"{name} changed since it was verified"
    assert set(verified["receiptsVerified"]) >= {f"backtest-{s}.json" for s in STAGES}
    for stage in verified["stages"].values():
        assert stage["metricsMismatched"] == [] and stage["metricsCompared"] > 0
        assert stage["labelsJoinObservationsOneToOne"] and stage["labelsEqualObservations"]
    assert all(verified["v0ByteIdentical"].values())
    assert all(verified["frozen"]["frozenCommitMatchesManifest"].values())


@pytest.mark.skipif(not AUDIT_RUN.exists(), reason="the audit run lives only on the main machine")
def test_t27_real_holdout_forecasts_reproduce_their_receipt():
    dvp = cli()
    receipt = json.loads((RECEIPTS / "backtest-holdout.json").read_text())
    frame, matched = dvp._stage_forecasts(AUDIT_RUN, receipt, "holdout")
    assert matched in ("bytes", "content")
    part = frame.filter(pl.col("position") == "DST")
    again = wf.metrics(
        part, ["b00", "b06"], block=receipt["bootstrapBlock"], reps=200, seed=receipt["seed"]
    )
    for name in ("rmse", "mae", "meanError", "spearman", "deltaRmse", "relativeDelta"):
        assert again["b06"][name] == receipt["results"]["DST"]["b06"][name]


# --- T26 ------------------------------------------------------------------------------------------


@pytest.mark.skipif(not AUDIT_RUN.exists(), reason="the audit run lives only on the main machine")
def test_t26_forecasts_use_arbit_franchise_codes_and_ffa_groups():
    frame = pl.read_parquet(AUDIT_RUN / "backtest-holdout" / "forecasts.parquet")
    codes = set(frame.get_column("offense").unique().to_list())
    assert len(codes) == 32
    assert all(franchise(code) == code for code in codes)
    assert set(frame.get_column("position").unique().to_list()) == GROUPS


def _python_files() -> list[Path]:
    return [CLI, *sorted(PACKAGE.glob("*.py"))]


def test_t26_every_database_connection_is_read_only():
    tree = ast.parse(CLI.read_text())
    engines = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "create_engine"
    ]
    assert engines, "expected the CLI's read-only engines"
    for call in engines:
        options = next(k for k in call.keywords if k.arg == "execution_options")
        assert isinstance(options.value, ast.Dict)
        pairs = dict(zip(options.value.keys, options.value.values, strict=True))
        (key,) = [
            k for k in pairs if isinstance(k, ast.Constant) and k.value == "postgresql_readonly"
        ]
        assert isinstance(pairs[key], ast.Constant) and pairs[key].value is True


WRITES = ("insert", "update", "delete", "merge", "upsert", "truncate", "drop", "create", "alter")
SQL_WRITE = re.compile(
    r"^\s*(insert\s+into|update\s+\w+\s+set|delete\s+from|truncate\s|drop\s+(table|schema)"
    r"|alter\s+table|create\s+(table|schema|index))",
    re.IGNORECASE,
)


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_t26_no_write_statement_commit_or_weight_import(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            # A write persists only through a commit (or a session flush); an SVG's .add() is not one.
            assert node.func.attr not in ("commit", "add_all", "flush", "bulk_save_objects"), (
                f"{path.name}:{node.lineno} calls .{node.func.attr}()"
            )
            if node.func.attr in WRITES and isinstance(node.func.value, ast.Name):
                assert node.func.value.id not in ("sa", "sqlalchemy"), f"{path.name}:{node.lineno}"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not SQL_WRITE.search(node.value), f"{path.name}:{node.lineno} holds a write"
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module != "arbit_model.feature_specs", (
                f"{path.name} imports feature weights"
            )
            if path.parent == PACKAGE:
                assert not node.module.startswith(("sqlalchemy", "arbit_data.db")), path.name
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "arbit_model.feature_specs"
                if path.parent == PACKAGE:
                    assert not alias.name.startswith("sqlalchemy"), path.name
