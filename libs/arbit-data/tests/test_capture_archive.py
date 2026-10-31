"""Private captures are bounded, immutable, verified and stripped of unused identity fields."""

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from arbit_data.archives import CaptureArchive, CapturedInput
from arbit_data.espn.contracts import EspnAcquisition, League
from arbit_data.espn.transport import SourceReceipt

FIXTURE = Path(__file__).resolve().parents[3] / "tests/fixtures/espn/league.synthetic.json"


def capture():
    raw = json.loads(FIXTURE.read_text())
    raw["members"] = [
        {
            "id": "manager-a",
            "displayName": "Commissioner",
            "firstName": "PRIVATE-FIRST",
            "notificationSettings": {"email": "private@example.invalid"},
        }
    ]
    t = datetime(2026, 10, 30, 12, tzinfo=UTC)
    return CapturedInput(
        acquisition=EspnAcquisition(
            League.model_validate(raw),
            (),
            (SourceReceipt("https://lm-api-reads.fantasy.espn.com/synthetic", t, "a" * 64, 100),),
            t,
            t,
        ),
        verification=None,
    )


def test_archive_roundtrip_is_private_and_idempotent(tmp_path):
    store = CaptureArchive(tmp_path / "captures")
    item = capture()
    digest = store.write(item)
    assert store.write(item) == digest
    assert store.read(digest) == item
    path = store.path(digest)
    assert path.stat().st_mode & 0o777 == 0o600
    data = gzip.decompress(path.read_bytes())
    assert hashlib.sha256(data).hexdigest() == digest
    assert b"PRIVATE-FIRST" not in data and b"private@example" not in data
    assert b"Commissioner" in data
    assert item.acquisition.league.members[0].id == "manager-a"
    assert store.read(digest).acquisition.receipts[0].sha256 == "a" * 64


def test_archive_rejects_tamper_paths_and_oversized_content(tmp_path, monkeypatch):
    store = CaptureArchive(tmp_path)
    digest = store.write(capture())
    store.path(digest).write_bytes(gzip.compress(b"{}"))
    with pytest.raises(ValueError):
        store.read(digest)
    with pytest.raises(ValueError):
        store.write(capture())  # Never accept an existing corrupt immutable object.
    for invalid in ("../escape", "A" * 64, ""):
        with pytest.raises(ValueError):
            store.read(invalid)
    monkeypatch.setattr("arbit_data.archives.MAX_CAPTURE_BYTES", 100)
    with pytest.raises(ValueError):
        store.write(capture())
    bomb = gzip.compress(b" " * 101)
    token = hashlib.sha256(b" " * 101).hexdigest()
    store.path(token).write_bytes(bomb)
    with pytest.raises(ValueError):
        store.read(token)
