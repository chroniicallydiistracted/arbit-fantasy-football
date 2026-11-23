"""M3-3 continuity (T29): the v0 study stays as it was, and its reproduction is on record."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECEIPTS = ROOT / "docs/research/dvp"
SPEC_IDS = {
    *(f"M3-3-A{n:02d}" for n in range(13)),
    *(f"M3-3-B{n:02d}" for n in range(13)),
    *(f"M3-3-C{n:02d}" for n in range(6)),
}


def test_t29_v0_files_are_byte_identical_to_the_continuity_manifest():
    manifest = json.loads((RECEIPTS / "continuity-manifest.json").read_text())
    v0 = manifest["v0"]
    assert v0["status"] == "EXISTING" and v0["experimentId"] == "M3-3-v0"
    for path, digest in v0["files"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    study = json.loads((ROOT / "docs/research/defense-position-study-2026-11-23.json").read_text())
    assert {k: v["gamesForHalfSignal"] for k, v in study["stability"].items()} == v0[
        "gamesForHalfSignal"
    ]


def test_t29_v0_was_reproduced_exactly_and_independently():
    report = json.loads((RECEIPTS / "v0-reproduction.json").read_text())
    assert report["status"] == "REPRODUCED"
    assert report["rerun"]["exact"] and report["rerun"]["differences"] == []
    assert all(entry["matchesReceipt"] for entry in report["independent"].values())
    assert len(report["independent"]) == 12


def test_t29_every_specified_experiment_is_registered_with_a_status():
    registry = json.loads((RECEIPTS / "experiment-registry.json").read_text())
    ids = {e["experiment_id"] for e in registry["experiments"]}
    assert SPEC_IDS <= ids and "M3-3-v0" in ids
    assert all(e["workstream_id"] == "M3-3" for e in registry["experiments"])
