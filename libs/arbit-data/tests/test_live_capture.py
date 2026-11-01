import gzip
import hashlib
import json
import shutil
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest
from arbit_data.errors import SourceError
from arbit_data.live.capture import CapturingTransport
from arbit_data.public_sources.requests import build_source_request
from arbit_data.public_sources.transport import PublicResponse

NOW = datetime(2026, 11, 1, 18, 0, tzinfo=UTC)
PLAYS = build_source_request("espn.plays", event_id="401873024", page=2)
BOARD = build_source_request("espn.scoreboard.current")


class Source:
    def __init__(self, *results):
        self.results, self.calls = list(results), 0

    def fetch(self, _request):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return PublicResponse(result, {}, None)


def capture(root, *results, **options):
    source = Source(*results)
    return source, CapturingTransport(source, root, clock=lambda: NOW, **options)


def index(root: Path) -> list[dict]:
    return [json.loads(line) for line in (root / "2026-11-01.jsonl").read_text().splitlines()]


def test_keeps_exact_bytes_once_and_every_read_in_order(tmp_path):
    body = b'{"situation": {"down": 3}}'
    source, transport = capture(tmp_path, body, body)
    assert transport.fetch(PLAYS).body == body
    assert transport.fetch(PLAYS).body == body
    assert source.calls == 2, "capture must add no provider requests"

    digest = hashlib.sha256(body).hexdigest()
    assert gzip.decompress((tmp_path / "objects" / f"{digest}.json.gz").read_bytes()) == body
    assert len(list((tmp_path / "objects").iterdir())) == 1
    first, second = index(tmp_path)
    assert first == second
    assert first == {
        "at": NOW.isoformat(),
        "kind": "espn.plays",
        "url": PLAYS.url,
        "event_id": "401873024",
        "page": 2,
        "sha256": digest,
        "bytes": len(body),
    }


def test_captures_are_readable_only_by_their_owner(tmp_path):
    root = tmp_path / "captures"
    _, transport = capture(root, b"{}")
    transport.fetch(BOARD)
    for path in [root, root / "objects"]:
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
    for path in [root / "2026-11-01.jsonl", *(root / "objects").iterdir()]:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_failed_read_is_recorded_and_reaches_the_feed_unchanged(tmp_path):
    failure = SourceError("RATE_LIMITED", status=429, retry_after_seconds=30)
    _, transport = capture(tmp_path, failure)
    with pytest.raises(SourceError) as raised:
        transport.fetch(PLAYS)
    assert raised.value is failure
    assert index(tmp_path)[0]["error"] == "RATE_LIMITED"
    assert not list((tmp_path / "objects").iterdir())


def test_unwritable_capture_never_costs_a_score_and_reports_once(tmp_path):
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("")
    problems = []
    _, transport = capture(blocked, b"{}", b"{}", on_problem=problems.append)
    assert transport.fetch(BOARD).body == b"{}"
    assert transport.fetch(BOARD).body == b"{}"
    assert problems == ["CAPTURE_EEXIST"], "one report, with a code and no path"


def test_reports_again_after_recovering(tmp_path):
    blocked = tmp_path / "captures"
    blocked.write_text("")
    problems = []
    _, transport = capture(blocked, b"{}", b"{}", b"{}", on_problem=problems.append)
    transport.fetch(BOARD)
    blocked.unlink()
    transport.fetch(BOARD)
    assert index(blocked), "capture resumes once the path is usable"
    shutil.rmtree(blocked)
    blocked.write_text("")
    transport.fetch(BOARD)
    assert problems == ["CAPTURE_EEXIST", "CAPTURE_EEXIST"]


def test_stops_at_the_limit_counting_earlier_runs_and_keeps_serving(tmp_path):
    _, first = capture(tmp_path, b"a" * 200)
    first.fetch(BOARD)
    used = sum(p.stat().st_size for p in tmp_path.rglob("*") if p.is_file())

    problems = []
    _, second = capture(tmp_path, b"b" * 200, max_bytes=used + 10, on_problem=problems.append)
    assert second.fetch(BOARD).body == b"b" * 200
    assert problems == ["CAPTURE_FULL"]
    assert sum(p.stat().st_size for p in tmp_path.rglob("*") if p.is_file()) == used
