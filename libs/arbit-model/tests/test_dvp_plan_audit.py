"""The plan-completion audit (scripts/model/dvp_plan_audit.py) and its scope document.

The audit maps every action item of the owner's DvP specification v1.1 to checks, and
PLAN_COMPLETION_SCOPE.md explains each item under the same ID. These tests keep the catalog
complete, keep the committed receipt consistent with it, and check the comparisons it relies on.
They do not rerun the stages. The audit's `rerun` command does that, from a frozen tree, against
the database.
"""

import ast
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import numpy as np
import polars as pl
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/model/dvp_plan_audit.py"
RECEIPT = ROOT / "docs/research/dvp/plan-audit-receipt.json"
SCOPE = ROOT / "docs/research/dvp/PLAN_COMPLETION_SCOPE.md"
SPEC = ROOT / "docs/research/dvp/Arbit_FFA_M3_DvP_Plan.md"
TESTS = ROOT / "libs/arbit-model/tests"


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("dvp_plan_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_catalog_covers_every_specified_item(audit):
    ids = [item.id for item in audit.ITEMS]
    assert len(ids) == len(set(ids)), "item IDs repeat"
    wanted = {
        *(f"R{i:02d}" for i in range(1, 15)),  # §0 rules 1-14
        *(f"RQ{i}" for i in range(1, 8)),  # §1
        *(f"T{i:02d}" for i in range(1, 41)),  # §8
        *audit.EXPERIMENTS,  # §5 A00-A12, B00-B12, C00-C05
        *(f"O{i:02d}" for i in range(1, 12)),  # §11 deliverables 1-11
        *(f"P{i}" for i in range(6)),  # §9 phases 0-5
        *(f"Z0{i}" for i in range(1, 7)),  # §11 "before completion"
        *(f"V0{i}" for i in range(1, 8)),  # §4
    }
    assert wanted <= set(ids), sorted(wanted - set(ids))


def test_every_check_is_defined_and_used(audit):
    used = {c for item in audit.ITEMS for c in item.checks}
    assert used <= set(audit.CHECKS), sorted(used - set(audit.CHECKS))
    assert set(audit.CHECKS) <= used, sorted(set(audit.CHECKS) - used)
    assert all(item.checks for item in audit.ITEMS)
    assert {item.kind for item in audit.ITEMS} == {"done", "open", "not_applicable"}


def test_every_test_id_names_real_tests():
    """Each T check selects test functions by their tag; every tag T01-T40 must exist."""
    tagged: set[int] = set()
    for path in TESTS.glob("test_dvp_*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
                name = node.name.removeprefix("test")
                tagged |= {int(m) for m in re.findall(r"(?:^|_)t(\d{2})(?=_)", name)}
    assert set(range(1, 41)) <= tagged, sorted(set(range(1, 41)) - tagged)


def test_an_open_item_never_counts_as_done(audit, monkeypatch):
    checks = {
        "pass": ("passes", lambda ctx: (True, 1)),
        "fail": ("fails", lambda ctx: (False, 0)),
        "boom": ("raises", lambda ctx: 1 / 0),
    }
    items = (
        audit.Item("D1", "§x", "done and proven", ("pass",)),
        audit.Item("D2", "§x", "claimed but failing", ("pass", "fail")),
        audit.Item("O1", "§x", "open, state recorded", ("pass",), "open"),
        audit.Item("E1", "§x", "a check that cannot run", ("boom",)),
    )
    monkeypatch.setattr(audit, "CHECKS", checks)
    monkeypatch.setattr(audit, "ITEMS", items)
    result = audit.evaluate(None)
    status = {i["id"]: i["status"] for i in result["items"]}
    assert status == {"D1": "DONE", "D2": "FAILED", "O1": "OPEN", "E1": "FAILED"}
    assert result["status"] == "FAILED"
    assert result["summary"]["DONE"] == 1 and result["summary"]["OPEN"] == 1
    assert "ZeroDivisionError" in result["checks"]["boom"]["observed"]


def test_only_allowed_receipt_fields_may_differ(audit):
    committed = {"code": "a", "generatedAt": "t1", "results": {"DST": {"rmse": 6.6}}, "codeX": 1}
    rerun = {"code": "b", "generatedAt": "t2", "results": {"DST": {"rmse": 6.7}}, "codeX": 2}
    differ, unexpected = audit.unexpected_differences(committed, rerun, {"/code", "/generatedAt"})
    assert differ == ["/code", "/codeX", "/generatedAt", "/results/DST/rmse"]
    assert unexpected == ["/codeX", "/results/DST/rmse"]  # "/code" does not cover "/codeX"
    _, nested = audit.unexpected_differences(
        {"codeScan": {"files": {"a.py": "1"}}},
        {"codeScan": {"files": {"b.py": "2"}}},
        {"/codeScan/files"},
    )
    assert nested == []
    _, missing = audit.unexpected_differences({"a": 1}, {}, set())
    assert missing == ["/a"]


def _forecasts(n: int = 40) -> pl.DataFrame:
    rng = np.random.default_rng(5)
    return pl.DataFrame(
        {
            "season": [2025] * n,
            "week": list(range(1, n + 1)),
            "game_id": [f"g{i}" for i in range(n)],
            "offense": ["X"] * n,
            "position": ["DST"] * n,
            "b00": rng.normal(6, 1, n),
            "n_d": [None, *range(1, n)],
        }
    )


def test_forecast_difference_measures_noise_and_sees_real_changes(audit):
    a = _forecasts()
    same = audit.forecast_difference(a, a.reverse())
    assert same["maxAbsDifference"] == 0 and same["floatValuesDiffering"] == 0
    noise = a.with_columns(pl.col("b00") + 7e-15)
    small = audit.forecast_difference(a, noise)
    assert 0 < small["maxAbsDifference"] < audit.TOLERANCE
    real = audit.forecast_difference(a, a.with_columns(pl.col("b00") + 1e-6))
    assert real["maxAbsDifference"] > audit.TOLERANCE
    renamed = audit.forecast_difference(a, a.with_columns(pl.col("n_d").fill_null(0)))
    assert renamed["nonFloatOrMissingDifferences"] == ["n_d"]
    assert audit.forecast_difference(a, a.head(3)) == {"comparable": False}


def test_the_committed_receipt_passes_and_matches_the_catalog(audit):
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["format"] == audit.FORMAT
    assert receipt["status"] == "PASSED"
    assert [i["id"] for i in receipt["items"]] == [item.id for item in audit.ITEMS]
    assert {i["id"]: i["checks"] for i in receipt["items"]} == {
        item.id: list(item.checks) for item in audit.ITEMS
    }
    assert all(i["status"] in ("DONE", "OPEN", "NOT_APPLICABLE") for i in receipt["items"])
    assert all(c["passed"] for c in receipt["checks"].values())
    assert set(receipt["checks"]) == set(audit.CHECKS)
    assert receipt["tests"]["failed"] == 0 and receipt["tests"]["skipped"] == 0
    steps = {s["step"]: (s["exit"], s["expectedExit"]) for s in receipt["reruns"]["steps"]}
    assert all(e == x for e, x in steps.values())
    assert steps["backtest-holdout-refused-here"] == (1, 1)
    assert (
        receipt["reruns"]["frozenTree"]
        == json.loads((ROOT / "docs/research/dvp/backtest-holdout.json").read_text())["code"]
    )


def test_the_receipt_audited_this_specification(audit):
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["specification"]["sha256"] == hashlib.sha256(SPEC.read_bytes()).hexdigest()


def test_the_scope_document_explains_every_item_and_states_the_counts(audit):
    text = SCOPE.read_text()
    receipt = json.loads(RECEIPT.read_text())
    missing = [item.id for item in audit.ITEMS if f"| {item.id} |" not in text]
    assert not missing, missing
    for item in audit.ITEMS:
        if item.kind == "open":
            row = next(line for line in text.splitlines() if line.startswith(f"| {item.id} |"))
            assert "OPEN" in row or "BLOCKED" in row or "NOT BUILT" in row, item.id
        if item.kind == "not_applicable":
            row = next(line for line in text.splitlines() if line.startswith(f"| {item.id} |"))
            assert "NOT_APPLICABLE" in row, item.id
    summary = receipt["summary"]
    assert f"{summary['items']} action items" in text
    assert f"{summary['checks']} checks" in text
