"""External commitments (owner directive AUD-01a), against a local bare repository as the remote.

Covers: the sanitized commitment; publish, read back and verify; idempotent retries; a failed push
retried without regenerating anything; a remote that disagrees; GitHub's activity record as the
timestamp; and the harness's publish step after the ledger append (AUD-01d).
"""

import hashlib
import importlib.util
import json
import subprocess
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from arbit_model.dvp import evidence, shadow

ROOT = Path(__file__).resolve().parents[3]
BRANCH = "research-evidence/dvp-prospective"
CUTOFF = datetime(2026, 12, 4, 1, 15, tzinfo=UTC)


def bare(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    return remote


def entry(week=13):
    return shadow.ledger_entry(
        None,
        {
            "season": 2026,
            "week": week,
            "classification": "PROSPECTIVE",
            "generatedAt": (CUTOFF - timedelta(days=1)).isoformat(),
            "archivedAt": (CUTOFF - timedelta(days=1)).isoformat(),
            "cutoff": CUTOFF.isoformat(),
            "folder": f"week-{week}",
            "files": {"forecasts.csv": "a" * 64, "league.json": "b" * 64},
            "contentSha256": "c" * 64,
            "code": "d" * 40,
            "rosters": {"team-uuid": ["KC"]},  # never published
        },
    )


def test_the_commitment_holds_hashes_and_times_only():
    record = evidence.commitment(entry(), "e" * 64)
    text = json.dumps(record)
    assert "team-uuid" not in text and "rosters" not in text
    assert record["ledgerEntry"]["files"]["league.json"] == "b" * 64
    assert record["ledgerEntry"]["entrySha256"] == entry()["entrySha256"]


def test_publish_reads_back_and_is_idempotent(tmp_path):
    remote, clone = bare(tmp_path), tmp_path / "clone"
    files = {"2026/week-13/commitment.json": b'{"a": 1}\n', "2026/week-13/forecasts.csv": b"x\n"}
    first = evidence.publish(clone, str(remote), BRANCH, files, "week 13")
    assert first["committed"]
    expected = {p: hashlib.sha256(b).hexdigest() for p, b in files.items()}
    assert evidence.verify_remote(clone, BRANCH, first["commit"], expected) == []
    again = evidence.publish(clone, str(remote), BRANCH, files, "week 13")
    assert again == {"commit": first["commit"], "committed": False}
    # A later week appends; the first commit stays on the branch.
    later = evidence.publish(clone, str(remote), BRANCH, {"2026/week-14/c.json": b"{}\n"}, "w14")
    assert evidence.verify_remote(clone, BRANCH, first["commit"], expected) == []
    assert later["commit"] != first["commit"]


def test_a_failed_push_is_retried_without_regenerating(tmp_path):
    remote, clone = bare(tmp_path), tmp_path / "clone"
    files = {"2026/week-13/commitment.json": b'{"a": 1}\n'}
    missing = tmp_path / "unreachable.git"
    with pytest.raises(evidence.PublicationError):
        evidence.publish(clone, str(missing), BRANCH, files, "week 13")
    # The same bytes, published again once the remote is reachable.
    done = evidence.publish(clone, str(remote), BRANCH, files, "week 13")
    expected = {p: hashlib.sha256(b).hexdigest() for p, b in files.items()}
    assert evidence.verify_remote(clone, BRANCH, done["commit"], expected) == []


def test_a_remote_that_disagrees_is_reported(tmp_path):
    remote, clone = bare(tmp_path), tmp_path / "clone"
    files = {"2026/week-13/commitment.json": b'{"a": 1}\n'}
    done = evidence.publish(clone, str(remote), BRANCH, files, "week 13")
    problems = evidence.verify_remote(
        clone, BRANCH, done["commit"], {"2026/week-13/commitment.json": "0" * 64}
    )
    assert problems == ["2026/week-13/commitment.json differs from the archive"]


def test_the_external_timestamp_is_githubs_record_of_the_push(tmp_path):
    remote, clone = bare(tmp_path), tmp_path / "clone"
    one = evidence.publish(clone, str(remote), BRANCH, {"a.json": b"1"}, "one")["commit"]
    two = evidence.publish(clone, str(remote), BRANCH, {"b.json": b"2"}, "two")["commit"]
    activity = [
        {"activity_type": "push", "after": two, "timestamp": "2026-12-02T10:00:05Z"},
        {"activity_type": "branch_creation", "after": one, "timestamp": "2026-12-02T09:00:00Z"},
    ]
    assert evidence.external_timestamp(clone, one, activity)[0] == "2026-12-02T09:00:00Z"
    assert evidence.external_timestamp(clone, two, activity)[0] == "2026-12-02T10:00:05Z"
    # Pushed together: the push that carried it is when GitHub first had it.
    assert evidence.external_timestamp(clone, one, activity[:1])[0] == "2026-12-02T10:00:05Z"
    assert evidence.external_timestamp(clone, two, activity[1:]) == (None, None)
    assert evidence.before("2026-12-02T10:00:05Z", CUTOFF)
    assert not evidence.before(None, CUTOFF)


@pytest.fixture
def harness():
    spec = importlib.util.spec_from_file_location(
        "dvp_prospective_ev", ROOT / "scripts/model/dvp_prospective.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_publication_after_the_ledger_append_is_retried_until_verified(
    harness, tmp_path, monkeypatch
):
    """The run stopped after the ledger append and before publication, then publication failed
    once: each later run retries the same archive's commitment until it is verified."""
    season_root = tmp_path / "prospective" / "2026"
    folder = season_root / "week-13"
    folder.mkdir(parents=True)
    (folder / "forecasts.csv").write_bytes(b"game_id,b00\ng,1\n")
    digest = hashlib.sha256(b"game_id,b00\ng,1\n").hexdigest()
    harness.append_ledger(
        season_root / "ledger.jsonl",
        {
            "season": 2026,
            "week": 13,
            "classification": "PROSPECTIVE",
            "generatedAt": (CUTOFF - timedelta(days=1)).isoformat(),
            "archivedAt": (CUTOFF - timedelta(days=1)).isoformat(),
            "cutoff": CUTOFF.isoformat(),
            "folder": "week-13",
            "files": {"forecasts.csv": digest},
        },
    )
    remote = bare(tmp_path)
    args = Namespace(archive=tmp_path / "prospective", main=tmp_path, season=2026)
    monkeypatch.setenv("ARBIT_EVIDENCE_SLUG", "owner/repo")
    monkeypatch.setenv("ARBIT_EVIDENCE_REMOTE", str(tmp_path / "unreachable.git"))
    monkeypatch.setattr(harness.time, "sleep", lambda s: None)
    failed = harness.publish_pending(args, 2026)
    assert failed[0]["result"] == "failed" and not failed[0]["verified"]

    pushed: dict[str, str] = {}

    def activity(slug, branch):
        head = subprocess.run(
            ["git", "rev-parse", f"refs/heads/{branch}"],
            cwd=remote,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        pushed["head"] = head
        return [
            {"activity_type": "branch_creation", "after": head, "timestamp": "2026-12-02T09:00:00Z"}
        ]

    monkeypatch.setattr(harness.evidence, "read_activity", activity)
    monkeypatch.setenv("ARBIT_EVIDENCE_REMOTE", str(remote))
    done = harness.publish_pending(args, 2026)
    assert done[0]["result"] == "verified" and done[0]["beforeCutoff"]
    assert done[0]["commit"] == pushed["head"]
    # Verified once: later runs publish nothing; the archive was never touched.
    assert harness.publish_pending(args, 2026) == []
    assert (folder / "forecasts.csv").read_bytes() == b"game_id,b00\ng,1\n"
    log = harness.read_ledger(season_root / "publications.jsonl")
    assert [r["result"] for r in log] == ["failed", "verified"]
    assert shadow.verify_ledger(log) == []
